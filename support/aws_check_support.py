import boto3


def get_support_severity_levels():
    client = boto3.client(service_name="support", region_name="us-east-1")

    try:
        response = client.describe_severity_levels(language="en")

        severity_levels = []
        for severity_level in response["severityLevels"]:
            severity_levels.append(severity_level["code"])
    except client.exceptions.ClientError as err:
        if err.response["Error"]["Code"] == "SubscriptionRequiredException":
            return []
        raise err

    return severity_levels


__SUPPORT_LEVELS__ = {
    "critical": "ENTERPRISE",
    "urgent": "BUSINESS",
    "high": "BUSINESS",
    "normal": "DEVELOPER",
    "low": "DEVELOPER",
}

support_levels = get_support_severity_levels()

found = False
for level, support_level in __SUPPORT_LEVELS__.items():
    if level in support_levels:
        found = True
        print(f"Your AWS support level is: {support_level}")
        break

if not found:
    print("Your AWS support level is: BASIC")
