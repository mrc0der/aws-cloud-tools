import boto3
import csv
import datetime
from datetime import timedelta

# Change these to your preferred AWS region and output CSV path.
AWS_REGION = "us-east-1"
OUTPUT_CSV = "workspaces_report.csv"

# Adjust the metrics, namespace, statistic, and period as needed.
METRIC_NAMESPACE = "AWS/WorkSpaces"
METRIC_NAMES = ["Available"]  # Example metric; you can add more.
METRIC_STAT = "Sum"           # or "Average", "Maximum", etc.
METRIC_PERIOD = 86400         # 1 day in seconds (for daily aggregation)
LOOKBACK_DAYS = 30

def get_all_workspaces(region: str):
    """
    Fetch all WorkSpaces in the specified region using pagination.
    Returns a list of WorkSpaces as dictionaries.
    """
    client = boto3.client('workspaces', region_name=region)
    workspaces = []
    next_token = None
    
    while True:
        if next_token:
            response = client.describe_workspaces(NextToken=next_token)
        else:
            response = client.describe_workspaces()
        
        workspaces.extend(response.get('Workspaces', []))
        
        next_token = response.get('NextToken')
        if not next_token:
            break
    
    return workspaces

def get_workspace_tags(region: str, workspace_id: str):
    """
    Retrieve tags for a specific WorkSpace.
    Returns a dict of tag key->value.
    """
    client = boto3.client('workspaces', region_name=region)
    response = client.describe_tags(ResourceId=workspace_id)
    tag_list = response.get('TagList', [])
    
    return {tag['Key']: tag['Value'] for tag in tag_list}

def get_workspace_metrics(region: str, workspace_id: str, metric_name: str, 
                          start_time: datetime.datetime, end_time: datetime.datetime):
    """
    Retrieve the specified metric from CloudWatch for a single WorkSpace.
    Returns a value (e.g., sum of the metric) across the time period, or None if data is not found.
    """
    cw = boto3.client('cloudwatch', region_name=region)
    
    # We use get_metric_data to retrieve metric across the time window.
    # For daily sum, we might do 86400-second periods, or break it up differently.
    query_id = f"m_{workspace_id}_{metric_name}"
    
    metric_query = {
        'Id': query_id,
        'MetricStat': {
            'Metric': {
                'Namespace': METRIC_NAMESPACE,
                'MetricName': metric_name,
                'Dimensions': [
                    {
                        'Name': 'WorkspaceId',
                        'Value': workspace_id
                    }
                ]
            },
            'Period': METRIC_PERIOD,
            'Stat': METRIC_STAT
        },
        'ReturnData': True
    }
    
    response = cw.get_metric_data(
        MetricDataQueries=[metric_query],
        StartTime=start_time,
        EndTime=end_time
    )
    
    results = response['MetricDataResults']
    if not results:
        return None
    
    # For simplicity, assume only one metric result in this query
    metric_result = results[0]
    # The output is typically a list of Timestamps and Values
    # We can sum them, take the max, or otherwise combine as needed.
    # Below, we just sum all data points if you used "Sum" or "Average" as the stat.
    values = metric_result.get('Values', [])
    
    if not values:
        return 0
    return sum(values)  # Summation of daily sums, or daily averages, etc.

def main():
    # 1. Set up time window for the last 30 days
    end_time = datetime.datetime.utcnow()
    start_time = end_time - timedelta(days=LOOKBACK_DAYS)

    # 2. Retrieve all WorkSpaces
    all_workspaces = get_all_workspaces(AWS_REGION)

    # 3. Prepare CSV output
    fieldnames = [
        'WorkspaceId', 'DirectoryId', 'UserName', 'State', 'BundleId',
        'ComputerName', 'IpAddress', 'RootVolumeEncryptionEnabled',
        'UserVolumeEncryptionEnabled', 'VolumeEncryptionKey', 
        'Tags'
    ] + [f"{mn}_metric" for mn in METRIC_NAMES]  # For each metric

    with open(OUTPUT_CSV, mode='w', newline='', encoding='utf-8') as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        
        for ws in all_workspaces:
            workspace_id = ws.get('WorkspaceId', '')
            
            # Retrieve tags as a dictionary
            ws_tags = get_workspace_tags(AWS_REGION, workspace_id)
            
            # Build row data from WorkSpace metadata
            row = {
                'WorkspaceId': workspace_id,
                'DirectoryId': ws.get('DirectoryId', ''),
                'UserName': ws.get('UserName', ''),
                'State': ws.get('State', ''),
                'BundleId': ws.get('BundleId', ''),
                'ComputerName': ws.get('ComputerName', ''),
                'IpAddress': ws.get('IpAddress', ''),
                'RootVolumeEncryptionEnabled': ws.get('RootVolumeEncryptionEnabled', ''),
                'UserVolumeEncryptionEnabled': ws.get('UserVolumeEncryptionEnabled', ''),
                'VolumeEncryptionKey': ws.get('VolumeEncryptionKey', ''),
                'Tags': ws_tags
            }
            
            # 4. Optionally get CloudWatch metrics for each WorkSpace
            for metric_name in METRIC_NAMES:
                metric_value = get_workspace_metrics(
                    region=AWS_REGION,
                    workspace_id=workspace_id,
                    metric_name=metric_name,
                    start_time=start_time,
                    end_time=end_time
                )
                row[f"{metric_name}_metric"] = metric_value
            
            writer.writerow(row)

    print(f"Report saved to {OUTPUT_CSV}")

if __name__ == "__main__":
    main()