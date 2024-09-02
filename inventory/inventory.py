"""inventory4."""

import os
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

from botocore.client import Config

config = Config(connect_timeout=5, retries={"max_attempts": 0})


import boto3
import botocore


def get_aws_account_id():
    """get the aws account id."""
    return boto3.client("sts").get_caller_identity()["Account"]


AWS_ID = get_aws_account_id()
WORKERS = 35
DATA_DIR = f"./data/{AWS_ID}"

if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)


def get_all_regions():
    """get all regions."""
    ec2 = boto3.client("ec2")
    # FIXME: this is a temp hardcoded region
    return [region["RegionName"] for region in ec2.describe_regions()["Regions"]]
    # return ["us-west-1"]


def paginate_and_collect(client, method_name, key):
    """paginate and collect."""
    paginator = client.get_paginator(method_name)
    resources = []
    for page in paginator.paginate():
        resources.extend(page.get(key, []))
    return resources


def handle_non_paginated_service(client, method_name, key, params=None):
    """handle non paginated service."""
    if params is None:
        params = {}

    method = getattr(client, method_name)

    svc_name = client.meta.service_model.service_name

    # Special handling for services that require specific parameters
    if svc_name == "ssm" and method_name == "get_parameters_by_path":
        if "Path" not in params:
            params["Path"] = "/"  # Specify the root path or another base path here

    # if svc_name == "wafv2" and method_name == "list_ip_sets":
    #     if "Scope" not in params:
    #         params["Scope"] = "CLOUDFRONT"  # CLOUDFRONT or REGIONAL

    resources = []
    while True:
        response = method(**params)
        resources.extend(response.get(key, []))
        if "NextToken" in response:
            params["NextToken"] = response["NextToken"]
        else:
            break
    return resources


def get_resource_tags(client, resource_arn):
    """get tags for a resource."""
    try:
        response = client.list_tags_for_resource(ResourceArn=resource_arn)
        return response.get("Tags", [])
    except botocore.exceptions.BotoCoreError as e:
        print(f"Error retrieving tags for {resource_arn}: {e}")
        return []


def enrich_with_metadata(client, resource, resource_type):
    """enrich a resource with metadata."""
    if resource_type == "sns-topic":
        resource["Tags"] = get_resource_tags(client, resource["TopicArn"])
        print(resource["Tags"])
    elif resource_type == "ec2-instance":
        resource["Tags"] = resource.get("Tags", [])
        print(resource["Tags"])
    # Add more conditions here for other resource types as needed
    return resource


def list_targets_for_target_groups(client, region):
    print(f"Getting elbv2 info for {region}")
    all_target_groups = paginate_and_collect(
        client, "describe_target_groups", "TargetGroups"
    )
    all_resources = []
    for target_group in all_target_groups:
        target_group_arn = target_group["TargetGroupArn"]
        targets = client.describe_target_health(TargetGroupArn=target_group_arn).get(
            "TargetHealthDescriptions", []
        )
        all_resources.extend(targets)
        # print(f"Collected targets for {target_group_arn}")

    file_name = f"{AWS_ID}-elbv2-{region}-details.json"
    write_to_file(all_resources, file_name)
    return all_resources


def get_guardduty_info(client, region):
    """get guardduty info."""
    all_detectors = paginate_and_collect(client, "list_detectors", "DetectorIds")
    all_resources = []
    for detector in all_detectors:
        # print(detector)
        detector_id = detector
        list_findings = client.get_paginator("list_findings")
        for page in list_findings.paginate(DetectorId=detector_id):
            all_resources.extend(page.get("FindingIds", []))

        list_threat_intel_sets = client.list_threat_intel_sets(DetectorId=detector_id)
        all_resources.extend(list_threat_intel_sets.get("ThreatIntelSetIds", []))

        list_ip_sets = client.list_ip_sets(DetectorId=detector_id)
        all_resources.extend(list_ip_sets.get("IpSetIds", []))

        # print(f"Collected findings for {detector_id}")

    file_name = f"{AWS_ID}-guardduty-{region}-details.json"
    write_to_file(all_resources, file_name)
    return all_resources


def get_ec2_info(client, region):
    """get ec2 info."""
    print(f"Getting ec2 info for {region}")
    # ("describe_images", "Images"),  # lots of requests....
    # all_snaps = paginate_and_collect(client, "describe_snapshots", "Snapshots")
    all_resources = []

    snaps = client.get_paginator("describe_snapshots")
    for page in snaps.paginate(
        Filters=[
            {
                "Name": "owner-id",
                "Values": [AWS_ID],
            },
        ]
    ):
        all_resources.extend(page.get("Snapshots", []))
    # gets public images
    images = client.get_paginator("describe_images")
    for page in images.paginate(
        Filters=[
            {
                "Name": "owner-id",
                "Values": [AWS_ID],
            },
            # this is how we grab all aws amis available to us...
            # {
            #     "Name": "owner-alias",
            #     "Values": ["amazon"],
            # },
        ]
    ):
        all_resources.extend(page.get("Images", []))

        # print(f"Collected findings for {detector_id}")

    file_name = f"{AWS_ID}-ec2-{region}-details.json"
    write_to_file(all_resources, file_name)
    return all_resources


def collect_and_save_resources():
    """collect and save resources."""
    session = boto3.Session()
    regions = get_all_regions()

    services = {
        "acm": [("list_certificates", "CertificateSummaryList")],
        "autoscaling": [
            ("describe_auto_scaling_groups", "AutoScalingGroups"),
            ("describe_launch_configurations", "LaunchConfigurations"),
            ("describe_auto_scaling_instances", "AutoScalingInstances"),
        ],
        "athena": [("list_databases", "DatabaseList")],
        "appstream": [
            ("describe_fleets", "Fleets"),
            ("describe_images", "Images"),
            ("describe_stacks", "Stacks"),
            # ("describe_users", "Users"), # AuthenticationType='API'|'SAML'|'USERPOOL'|'AWS_AD'
        ],
        "config": [
            ("describe_config_rules", "ConfigRules"),
            ("describe_configuration_aggregators", "ConfigurationAggregators"),
            ("list_resource_evaluations", "ResourceEvaluations"),
            # ("list_discovered_resources", "resourceIdentifiers") # https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/config/paginator/ListDiscoveredResources.html
        ],
        "backup": [
            ("list_backup_plans", "BackupPlansList"),
            ("list_backup_vaults", "BackupVaultList"),
            ("list_backup_jobs", "BackupJobs"),
        ],
        "cloudfront": [
            ("list_distributions", "DistributionList"),
            (
                "list_cloud_front_origin_access_identities",
                "CloudFrontOriginAccessIdentityList",
            ),
        ],
        "codedeploy": [
            ("list_applications", "Applications"),  # applications
            ("list_deployments", "Deployments"),  # deployments
        ],
        "ec2": [
            ("describe_instances", "Reservations"),
            ("describe_security_groups", "SecurityGroups"),
            ("describe_vpcs", "Vpcs"),
            ("describe_volumes", "Volumes"),
            ("describe_subnets", "Subnets"),
            ("describe_network_interfaces", "NetworkInterfaces"),
        ],
        "ecr": [
            ("describe_repositories", "Repositories"),  # repos
            # ("describe_images", "Images"),   # FIXME params needed
        ],
        "efs": [
            ("describe_file_systems", "FileSystems"),
        ],
        "eks": [
            ("list_clusters", "Clusters"),
        ],
        "elasticache": [
            ("describe_cache_clusters", "CacheClusters"),
        ],
        "elasticbeanstalk": [("describe_environments", "Environments")],
        "elb": [
            ("describe_load_balancers", "LoadBalancerDescriptions"),
        ],
        "es": [
            (
                "describe_reserved_elasticsearch_instances",
                "ReservedElasticsearchInstances",
            ),
        ],
        "lambda": [("list_functions", "Functions")],
        "rds": [
            ("describe_db_instances", "DBInstances"),
            ("describe_db_snapshots", "DBSnapshots"),
            ("describe_db_subnet_groups", "DBSubnetGroups"),
        ],
        "s3": [
            ("list_buckets", "Buckets"),
        ],
        "cloudformation": [("describe_stacks", "Stacks")],
        "cloudwatch": [("describe_alarms", "MetricAlarms")],
        "iam": [
            ("list_users", "Users"),
            ("list_roles", "Roles"),
            ("list_policies", "Policies"),  # lots
            # ("list_groups", "Groups"),
        ],
        "route53": [("list_hosted_zones", "HostedZones")],
        "dynamodb": [
            ("list_tables", "TableNames"),
            ("list_backups", "BackupSummaries"),
        ],
        "ecs": [
            ("list_clusters", "ClusterArns"),
            # ("list_services", "ServiceArns"),
            # ("list_tasks", "TaskArns"),
        ],
        "workspaces": [("describe_workspaces", "Workspaces")],
        "fsx": [("describe_file_systems", "FileSystems")],
        "glacier": [("list_vaults", "VaultList")],
        "guardduty": [
            ("list_detectors", "DetectorIds"),
        ],
    }

    non_paginated_services = {
        "apigatewayv2": ("get_apis", "Items"),
        "config": ("describe_configuration_recorders", "ConfigurationRecorders"),
        "ec2": ("describe_addresses", "Addresses"),
        "secretsmanager": ("list_secrets", "SecretList"),
        "ssm": ("get_parameters_by_path", "Parameters"),
        "kms": ("list_keys", "Keys"),
        "sns": ("list_topics", "Topics"),
        "cloudtrail": ("describe_trails", "trailList"),
        "codebuild": ("list_projects", "Projects"),
        "waf": ("list_web_acls", "WebACLs"),
        # "wafv2": ("list_ip_sets", "IPSets"), # Needs more data
    }

    def process_service_region(service, method, key, region):
        all_resources = []
        try:
            client = session.client(service, region_name=region, config=config)

            if service in non_paginated_services:
                resources = handle_non_paginated_service(client, method, key)
            else:
                resources = paginate_and_collect(client, method, key)

            for resource in resources:
                resource = enrich_with_metadata(client, resource, service)
            all_resources.extend(resources)
            # print(
            #     f"Collected {len(resources)} {service} resources in {region} using {method}"
            # )
            file_name = f"{AWS_ID}-{service}-{region}-{method}-{key}.json"
            write_to_file(all_resources, file_name)
        except botocore.exceptions.BotoCoreError as e:
            print(f"Error collecting {service} resources in {region}: {e}")
        return (service, all_resources)

    futures = []
    with ThreadPoolExecutor(max_workers=WORKERS) as executor:

        # paginated services
        for service, methods in services.items():
            for region in regions:
                for method, key in methods:
                    futures.append(
                        executor.submit(
                            process_service_region, service, method, key, region
                        )
                    )

        # non paginated services
        for service, (method, key) in non_paginated_services.items():
            for region in regions:
                futures.append(
                    executor.submit(
                        process_service_region, service, method, key, region
                    )
                )
        # resources that require inputs and custom funcs
        for service, (method, key) in non_paginated_services.items():
            for region in regions:
                # Other regional checks...
                futures.append(
                    executor.submit(
                        get_ec2_info,
                        session.client("ec2", region_name=region),
                        region,
                    )
                )
                futures.append(
                    executor.submit(
                        list_targets_for_target_groups,
                        session.client("elbv2", region_name=region),
                        region,
                    )
                )
                futures.append(
                    executor.submit(
                        get_guardduty_info,
                        session.client("guardduty", region_name=region),
                        region,
                    )
                )

    all_results = {}
    for future in as_completed(futures):
        result = future.result()
        if result:

            try:
                # service_name = result[0].get("Service", "unknown")
                service_name = result[0]
            except Exception as err:
                print(err)
                service_name = "unknown"

            if service_name not in all_results:
                all_results[service_name] = []
            all_results[service_name].extend(result[1])


def write_to_file(data, file_name):
    try:
        with open(f"{DATA_DIR}/{file_name}", "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, sort_keys=True, default=str)
    except Exception as err:
        print(err)
        with open(
            f"{DATA_DIR}/{file_name.replace('.json','.txt')}", "w", encoding="utf-8"
        ) as f:
            f.write(str(data))
    # print(f"Data written to {file_name}")


if __name__ == "__main__":
    collect_and_save_resources()
