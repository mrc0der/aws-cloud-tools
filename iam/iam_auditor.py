import boto3
import os
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main(region_name="us-east-1"):
    # Default: us-east-1
    # For GovCloud: 'us-gov-west-1' or 'us-gov-east-1'
    # For AWS China: 'cn-north-1' or 'cn-northwest-1'

    # Optionally specify a profile if configured
    # session = boto3.Session(profile_name='your-profile', region_name=region_name)
    session = boto3.Session(region_name=region_name)

    iam = session.client("iam")
    sts = session.client("sts")
    account_id = sts.get_caller_identity()["Account"]

    if not os.path.isdir("./roles"):
        os.makedirs(os.path.join(".", "roles"))

    if not os.path.isdir("./policies"):
        os.makedirs(os.path.join(".", "policies"))

    # Process Roles
    process_roles(iam, account_id, "./roles")

    # Process Policies
    process_policies(iam, account_id, "./policies")


def process_roles(iam, account_id, base_dir):
    paginator = iam.get_paginator("list_roles")
    page_iterator = paginator.paginate()

    for page in page_iterator:
        roles = page["Roles"]
        for role in roles:
            role_name = role["RoleName"]

            # Process Inline Policies
            inline_policies = iam.list_role_policies(RoleName=role_name)["PolicyNames"]
            for policy_name in inline_policies:
                filename = f"{account_id}-{role_name}-{policy_name}.json"
                meta_filename = (
                    f"./roles/{account_id}-{role_name}-{policy_name}_metadata.json"
                )
                file_path = os.path.join(base_dir, filename)
                if not os.path.exists(file_path):
                    # logger.info("Saving %s", filename)
                    logger.info("Saving role %s", role_name)
                    policy = iam.get_role_policy(
                        RoleName=role_name, PolicyName=policy_name
                    )
                    policy_document = policy["PolicyDocument"]
                    with open(file_path, "w") as f:
                        json.dump(policy_document, f, indent=2, default=str)
                    with open(file_path, "w") as f:
                        json.dump(policy_document, f, indent=2, default=str)

            # Process Attached Policies
            attached_policies = iam.list_attached_role_policies(RoleName=role_name)[
                "AttachedPolicies"
            ]
            for attached_policy in attached_policies:
                policy_arn = attached_policy["PolicyArn"]
                policy_name = attached_policy["PolicyName"]
                filename = f"{account_id}-{role_name}-{policy_name}.json"
                meta_filename = (
                    f"./roles/{account_id}-{role_name}-{policy_name}_metadata.json"
                )
                file_path = os.path.join(base_dir, filename)
                if not os.path.exists(file_path):
                    # Get the default version of the policy
                    policy = iam.get_policy(PolicyArn=policy_arn)
                    default_version_id = policy["Policy"]["DefaultVersionId"]
                    policy_version = iam.get_policy_version(
                        PolicyArn=policy_arn, VersionId=default_version_id
                    )
                    policy_document = policy_version["PolicyVersion"]["Document"]
                    with open(file_path, "w") as f:
                        json.dump(policy_document, f, indent=2, default=str)
                    with open(meta_filename, "w") as meta_file:
                        json.dump(policy, meta_file, indent=2, default=str)


def process_policies(iam, account_id, base_dir):
    paginator = iam.get_paginator("list_policies")
    page_iterator = paginator.paginate(
        Scope="All"
    )  # Include AWS and customer managed policies

    for page in page_iterator:
        policies = page["Policies"]
        for policy in policies:
            policy_name = policy["PolicyName"]
            policy_arn = policy["Arn"]
            filename = f"{account_id}-{policy_name}.json"
            meta_filename = f"./policies/{account_id}-{policy_name}_metadata.json"
            file_path = os.path.join(base_dir, filename)
            if not os.path.exists(file_path):
                logger.info("Processing policy %s", policy_name)
                # Get the default version of the policy
                policy_version = iam.get_policy_version(
                    PolicyArn=policy_arn, VersionId=policy["DefaultVersionId"]
                )
                policy_document = policy_version["PolicyVersion"]["Document"]
                with open(file_path, "w") as f:
                    json.dump(policy_document, f, indent=2, default=str)
                with open(meta_filename, "w") as meta_file:
                    json.dump(policy, meta_file, indent=2, default=str)


if __name__ == "__main__":
    main()
