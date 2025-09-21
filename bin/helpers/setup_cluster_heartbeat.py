#!/usr/bin/env python3
"""Provision heartbeat notifications for a Daylily ephemeral cluster."""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import subprocess
import sys
import textwrap
import time
import zipfile
from dataclasses import dataclass
from typing import Iterable, Optional

import boto3
from botocore.exceptions import ClientError


@dataclass
class ResourceNames:
    """Convenience container for derived AWS resource names."""

    topic_name: str
    function_name: str
    schedule_name: str

    def topic_arn(self, account_id: str, region: str) -> str:
        return f"arn:aws:sns:{region}:{account_id}:{self.topic_name}"

    def schedule_arn(self, account_id: str, region: str, group: str = "default") -> str:
        return f"arn:aws:scheduler:{region}:{account_id}:schedule/{group}/{self.schedule_name}"


def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cluster-name", required=True, help="Name of the ParallelCluster cluster")
    parser.add_argument("--region", required=True, help="AWS region")
    parser.add_argument("--email", required=True, help="Email address for notifications")
    parser.add_argument(
        "--schedule",
        required=True,
        help="EventBridge Scheduler expression (e.g. rate(60 minutes) or cron(...))",
    )
    parser.add_argument(
        "--profile",
        help="AWS profile to use for the boto3 session (defaults to AWS_PROFILE environment variable).",
    )
    return parser.parse_args(argv)


def resolve_aws_profile(profile_argument: Optional[str]) -> str:
    """Validate and return the AWS profile to use."""

    profile = profile_argument or os.environ.get("AWS_PROFILE")
    if not profile:
        print(
            "Error: AWS_PROFILE is not set. Please export AWS_PROFILE or supply --profile.",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        result = subprocess.run(
            ["aws", "configure", "list-profiles"],
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        print("Error: AWS CLI is not installed or not found in PATH.", file=sys.stderr)
        sys.exit(1)
    except subprocess.CalledProcessError as exc:
        message = exc.stderr.strip() or exc.stdout.strip() or str(exc)
        print(f"Error listing AWS profiles: {message}", file=sys.stderr)
        sys.exit(1)

    available_profiles = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if profile not in available_profiles:
        print(
            f"Error: AWS profile '{profile}' not found. Please set AWS_PROFILE to a valid profile.",
            file=sys.stderr,
        )
        sys.exit(1)

    os.environ["AWS_PROFILE"] = profile

    if profile == "default":
        print("WARNING: AWS_PROFILE is set to 'default'. Sleeping for 1 second...")
        time.sleep(1)
    else:
        print(f"Using AWS profile: {profile}")

    return profile


def sanitize(value: str, *, max_length: int) -> str:
    """Convert an arbitrary string into an AWS-safe identifier."""

    cleaned = re.sub(r"[^A-Za-z0-9-]", "-", value)
    cleaned = re.sub(r"-+", "-", cleaned).strip("-")
    if not cleaned:
        cleaned = "cluster"
    if len(cleaned) > max_length:
        cleaned = cleaned[:max_length]
    return cleaned


def derive_names(cluster_name: str) -> ResourceNames:
    # SNS topics allow up to 256 characters, Lambda and Scheduler limit to 64.
    base = sanitize(cluster_name.lower(), max_length=200)
    topic = sanitize(f"daylily-{base}-heartbeat", max_length=256)
    function = sanitize(f"daylily-{base}-heartbeat", max_length=64)
    schedule = sanitize(f"daylily-{base}-heartbeat", max_length=64)
    return ResourceNames(topic, function, schedule)


def ensure_iam_role(iam_client, role_name: str) -> str:
    assume_role_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Service": "lambda.amazonaws.com"},
                "Action": "sts:AssumeRole",
            }
        ],
    }
    try:
        role = iam_client.get_role(RoleName=role_name)["Role"]
    except ClientError as error:  # pragma: no cover - exercised in production
        if error.response["Error"].get("Code") != "NoSuchEntity":
            raise
        role = iam_client.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps(assume_role_policy),
            Description="Allows Daylily heartbeat Lambda functions to access AWS APIs",
        )["Role"]
        # give IAM time to propagate
        time.sleep(5)

    # Ensure the basic execution policy is attached
    lambda_basic_policy = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
    attached = iam_client.list_attached_role_policies(RoleName=role_name)["AttachedPolicies"]
    if not any(p["PolicyArn"] == lambda_basic_policy for p in attached):
        iam_client.attach_role_policy(RoleName=role_name, PolicyArn=lambda_basic_policy)

    inline_policy_name = "daylily-heartbeat"
    policy_doc = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": [
                    "ec2:DescribeInstances",
                    "fsx:DescribeFileSystems",
                    "fsx:ListTagsForResource",
                    "sns:Publish",
                ],
                "Resource": "*",
            }
        ],
    }
    iam_client.put_role_policy(
        RoleName=role_name,
        PolicyName=inline_policy_name,
        PolicyDocument=json.dumps(policy_doc),
    )
    return role["Arn"]


def build_lambda_package() -> bytes:
    lambda_source = textwrap.dedent(
        """
        import json
        import os
        from datetime import datetime, timezone

        import boto3
        from botocore.exceptions import BotoCoreError, ClientError

        ec2 = boto3.client("ec2")
        fsx = boto3.client("fsx")
        sns = boto3.client("sns")

        TOPIC_ARN = os.environ["SNS_TOPIC_ARN"]
        CLUSTER_NAME = os.environ["CLUSTER_NAME"]
        SUBJECT_PREFIX = os.environ.get("SNS_SUBJECT_PREFIX", "Daylily Cluster Heartbeat")

        def _format_timestamp() -> str:
            return datetime.now(timezone.utc).isoformat()

        def _get_headnode_state(cluster_name: str):
            filters = [
                {"Name": "tag:parallelcluster:cluster-name", "Values": [cluster_name]},
                {"Name": "tag:parallelcluster:node-type", "Values": ["HeadNode"]},
            ]
            instances = []
            try:
                paginator = ec2.get_paginator("describe_instances")
                for page in paginator.paginate(Filters=filters):
                    for reservation in page.get("Reservations", []):
                        for instance in reservation.get("Instances", []):
                            instances.append(instance)
            except (BotoCoreError, ClientError):
                return "error", [], "Unable to query EC2 for head node status."

            if not instances:
                return "not-found", [], "No head node instances were located."

            states = sorted({inst.get("State", {}).get("Name", "unknown") for inst in instances})
            instance_ids = [inst.get("InstanceId", "unknown") for inst in instances]
            state_summary = ",".join(states)
            detail = f"Head node instances {instance_ids} are in state(s): {state_summary}."
            if all(state == "running" for state in states):
                detail += " Head node appears to be running."
            return state_summary, instance_ids, detail

        def _get_fsx_states(cluster_name: str):
            matches = []
            try:
                paginator = fsx.get_paginator("describe_file_systems")
                for page in paginator.paginate():
                    for filesystem in page.get("FileSystems", []):
                        tags = filesystem.get("Tags", []) or []
                        if not tags and filesystem.get("ResourceARN"):
                            try:
                                tag_resp = fsx.list_tags_for_resource(ResourceARN=filesystem["ResourceARN"])
                                tags = tag_resp.get("Tags", [])
                            except (BotoCoreError, ClientError):
                                tags = []
                        if any(
                            tag.get("Key") == "parallelcluster:cluster-name" and tag.get("Value") == cluster_name
                            for tag in tags
                        ):
                            matches.append(
                                {
                                    "id": filesystem.get("FileSystemId"),
                                    "status": filesystem.get("Lifecycle"),
                                    "capacity": filesystem.get("StorageCapacity"),
                                }
                            )
            except (BotoCoreError, ClientError):
                return [], ["Unable to query FSx for filesystem status."]

            if not matches:
                return [], ["No FSx filesystems tagged for this cluster were found."]

            details = []
            for item in matches:
                status = item.get("status", "unknown")
                highlight = ""
                if status == "AVAILABLE":
                    highlight = " (filesystem is AVAILABLE and accruing cost)"
                details.append(
                    f"FSx filesystem {item.get('id')} status: {status}{highlight}."
                )
            return matches, details

        def lambda_handler(event, _context):
            cluster_name = event.get("ClusterName", CLUSTER_NAME) if isinstance(event, dict) else CLUSTER_NAME
            region = event.get("Region") if isinstance(event, dict) else None

            head_state, head_instances, head_detail = _get_headnode_state(cluster_name)
            fsx_matches, fsx_details = _get_fsx_states(cluster_name)

            lines = [
                f"Heartbeat for cluster '{cluster_name}' at {_format_timestamp()}.",
            ]
            if region:
                lines.append(f"Region: {region}.")
            lines.append(head_detail)
            lines.extend(fsx_details)
            message = "\n".join(lines)

            sns.publish(
                TopicArn=TOPIC_ARN,
                Subject=f"{SUBJECT_PREFIX}: {cluster_name}",
                Message=message,
            )

            return {
                "cluster": cluster_name,
                "headNodeState": head_state,
                "headNodeInstances": head_instances,
                "fsxCount": len(fsx_matches),
            }
        """
    )

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("lambda_function.py", lambda_source)
    buffer.seek(0)
    return buffer.read()


def ensure_sns_subscription(sns_client, topic_arn: str, email: str) -> None:
    subs = sns_client.list_subscriptions_by_topic(TopicArn=topic_arn)
    if any(sub.get("Endpoint") == email and sub.get("Protocol") == "email" for sub in subs.get("Subscriptions", [])):
        return
    sns_client.subscribe(TopicArn=topic_arn, Protocol="email", Endpoint=email)


def create_or_update_lambda(
    lambda_client,
    function_name: str,
    role_arn: str,
    package_bytes: bytes,
    topic_arn: str,
    cluster_name: str,
) -> str:
    env = {
        "Variables": {
            "SNS_TOPIC_ARN": topic_arn,
            "CLUSTER_NAME": cluster_name,
            "SNS_SUBJECT_PREFIX": "Daylily cluster heartbeat",
        }
    }

    kwargs = dict(
        FunctionName=function_name,
        Runtime="python3.11",
        Role=role_arn,
        Handler="lambda_function.lambda_handler",
        Code={"ZipFile": package_bytes},
        Description="Publishes Daylily ParallelCluster heartbeat notifications",
        Timeout=60,
        MemorySize=256,
        Publish=True,
        Environment=env,
    )

    try:
        response = lambda_client.create_function(**kwargs)
    except ClientError as error:
        if error.response["Error"].get("Code") != "ResourceConflictException":
            raise
        lambda_client.update_function_code(FunctionName=function_name, ZipFile=package_bytes, Publish=True)
        lambda_client.update_function_configuration(
            FunctionName=function_name,
            Role=role_arn,
            Handler="lambda_function.lambda_handler",
            Runtime="python3.11",
            Timeout=60,
            MemorySize=256,
            Environment=env,
            Description="Publishes Daylily ParallelCluster heartbeat notifications",
        )
        waiter = lambda_client.get_waiter("function_active_v2")
        waiter.wait(FunctionName=function_name)
        response = lambda_client.get_function(FunctionName=function_name)
    else:
        waiter = lambda_client.get_waiter("function_active_v2")
        waiter.wait(FunctionName=function_name)

    configuration = response.get("Configuration") or response
    return configuration["FunctionArn"]


def add_scheduler_permission(lambda_client, function_name: str, schedule_arn: str, statement_id: str) -> None:
    try:
        lambda_client.add_permission(
            FunctionName=function_name,
            StatementId=statement_id,
            Action="lambda:InvokeFunction",
            Principal="scheduler.amazonaws.com",
            SourceArn=schedule_arn,
        )
    except ClientError as error:
        if error.response["Error"].get("Code") == "ResourceConflictException":
            return
        raise


def create_or_update_schedule(
    scheduler_client,
    schedule_name: str,
    schedule_expression: str,
    function_arn: str,
    cluster_name: str,
    region: str,
    timezone: Optional[str] = None,
) -> None:
    target = {
        "Arn": function_arn,
        "Input": json.dumps({"ClusterName": cluster_name, "Region": region}),
    }
    base_kwargs = dict(
        Name=schedule_name,
        GroupName="default",
        ScheduleExpression=schedule_expression,
        FlexibleTimeWindow={"Mode": "OFF"},
        Target=target,
        State="ENABLED",
    )
    if timezone:
        base_kwargs["ScheduleExpressionTimezone"] = timezone
    kwargs = base_kwargs

    try:
        scheduler_client.create_schedule(**kwargs)
    except ClientError as error:
        if error.response["Error"].get("Code") != "ConflictException":
            raise
        scheduler_client.update_schedule(**kwargs)


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = parse_args(argv)
    schedule_expression = args.schedule.strip()
    if not schedule_expression:
        raise SystemExit("Schedule expression may not be empty.")

    names = derive_names(args.cluster_name)

    profile = resolve_aws_profile(args.profile)

    session = boto3.Session(profile_name=profile, region_name=args.region)
    sns_client = session.client("sns")
    iam_client = session.client("iam")
    lambda_client = session.client("lambda")
    scheduler_client = session.client("scheduler")
    sts_client = session.client("sts")

    account_id = sts_client.get_caller_identity()["Account"]

    topic_response = sns_client.create_topic(Name=names.topic_name)
    topic_arn = topic_response["TopicArn"]
    ensure_sns_subscription(sns_client, topic_arn, args.email)

    role_arn = ensure_iam_role(iam_client, "daylily-ephemeral-heartbeat-role")
    package_bytes = build_lambda_package()
    function_arn = create_or_update_lambda(
        lambda_client,
        names.function_name,
        role_arn,
        package_bytes,
        topic_arn,
        args.cluster_name,
    )

    schedule_arn = names.schedule_arn(account_id, args.region)
    statement_id = sanitize(f"daylily-{names.schedule_name}-invoke", max_length=100)
    add_scheduler_permission(lambda_client, names.function_name, schedule_arn, statement_id)

    create_or_update_schedule(
        scheduler_client,
        names.schedule_name,
        schedule_expression,
        function_arn,
        args.cluster_name,
        args.region,
    )

    print("✅ Heartbeat notifications configured.")
    print(f"   SNS topic: {topic_arn}")
    print(f"   Lambda: {function_arn}")
    print(f"   Schedule: {schedule_arn} -> {schedule_expression}")
    print("   Reminder: confirm the email subscription from AWS SNS if you have not already done so.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
