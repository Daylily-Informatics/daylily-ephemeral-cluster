#!/usr/bin/env python3
import argparse
import io
import json
import os
import subprocess
import sys
import textwrap
import time
import zipfile
from dataclasses import dataclass
from typing import Dict, Optional

import boto3
from botocore.exceptions import ClientError

def parse_args():
    p = argparse.ArgumentParser(description="Wire an SNS heartbeat via EventBridge Scheduler (no IAM writes).")
    p.add_argument("--cluster-name", required=True)
    p.add_argument("--region", required=True)
    p.add_argument("--email", required=True)
    p.add_argument("--schedule", required=True, help="rate(...) or cron(...) in UTC")
    p.add_argument("--profile", help="AWS profile (defaults to AWS_PROFILE)")
    p.add_argument(
        "--scheduler-role-arn",
        help="IAM role ARN that EventBridge Scheduler can assume to publish to SNS",
    )
    p.add_argument(
        "--lambda-role-arn",
        help="IAM role ARN for the heartbeat Lambda function (requires SNS/Budgets permissions)",
    )
    return p.parse_args()

def resolve_aws_profile(profile: Optional[str]) -> str:
    prof = profile or os.environ.get("AWS_PROFILE")
    if not prof:
        print("Error: set AWS_PROFILE or pass --profile", file=sys.stderr); sys.exit(1)
    # sanity: ensure profile exists
    try:
        out = subprocess.run(["aws","configure","list-profiles"], check=True, capture_output=True, text=True).stdout
        if prof not in [x.strip() for x in out.splitlines() if x.strip()]:
            print(f"Error: profile {prof} not found.", file=sys.stderr); sys.exit(1)
    except Exception as e:
        print(f"Error listing profiles: {e}", file=sys.stderr); sys.exit(1)
    os.environ["AWS_PROFILE"] = prof
    return prof

resolve_profile = resolve_aws_profile  # Backwards compatibility for importers.


@dataclass(frozen=True)
class HeartbeatNames:
    cluster_name: str

    @property
    def topic_name(self) -> str:
        return f"daylily-{self.cluster_name}-heartbeat"

    @property
    def schedule_name(self) -> str:
        # Scheduler names are limited to 64 characters.
        return f"daylily-{self.cluster_name}-heartbeat"[:64]

    @property
    def function_name(self) -> str:
        # Legacy lambda wiring used this naming pattern; retained for teardown compatibility.
        return f"daylily-{self.cluster_name}-heartbeat"

    def topic_arn(self, account_id: str, region: str) -> str:
        return f"arn:aws:sns:{region}:{account_id}:{self.topic_name}"


def derive_names(cluster_name: str) -> HeartbeatNames:
    return HeartbeatNames(cluster_name=cluster_name)


def ensure_topic_and_sub(sns, topic_name, email, region, account_id):
    try:
        topic_arn = sns.create_topic(Name=topic_name)["TopicArn"]
    except ClientError as error:
        err_code = error.response.get("Error", {}).get("Code", "")
        if err_code != "AuthorizationError":
            raise

        # Fall back to an existing topic when creation is forbidden.  This
        # happens in least-privilege environments where the topic is created
        # out-of-band (for example via Terraform) and the operator is only
        # allowed to publish/subscribe.
        topic_arn = f"arn:aws:sns:{region}:{account_id}:{topic_name}"
        try:
            sns.get_topic_attributes(TopicArn=topic_arn)
        except ClientError:
            raise RuntimeError(
                "SNS topic creation is forbidden and an existing topic "
                f"named '{topic_name}' was not found. Create the topic "
                "manually or grant SNS:CreateTopic permissions."
            ) from error

        print(
            "⚠️ SNS:CreateTopic not permitted; using existing topic "
            f"{topic_arn}.",
            file=sys.stderr,
        )

    # subscribe email if not already subscribed
    subs = sns.list_subscriptions_by_topic(TopicArn=topic_arn).get("Subscriptions", [])
    if not any(s.get("Protocol") == "email" and s.get("Endpoint") == email for s in subs):
        try:
            sns.subscribe(TopicArn=topic_arn, Protocol="email", Endpoint=email)
        except ClientError as error:
            err_code = error.response.get("Error", {}).get("Code", "")
            if err_code == "AuthorizationError":
                raise RuntimeError(
                    "SNS subscription permissions are insufficient. "
                    "Confirm the topic has an email subscription for "
                    f"{email} or grant SNS:Subscribe."
                ) from error
            raise
    return topic_arn


ROLE_ENV_VARS = (
    "DAY_HEARTBEAT_SCHEDULER_ROLE_ARN",
    "DAYLILY_HEARTBEAT_SCHEDULER_ROLE_ARN",
    "DAY_HEARTBEAT_ROLE_ARN",
    "DAYLILY_SCHEDULER_ROLE_ARN",
)

DEFAULT_ROLE_NAMES = (
    "eventbridge-scheduler-to-sns",
    "daylily-eventbridge-scheduler",
)

LAMBDA_ROLE_ENV_VARS = (
    "DAY_HEARTBEAT_LAMBDA_ROLE_ARN",
    "DAYLILY_HEARTBEAT_LAMBDA_ROLE_ARN",
)

LAMBDA_SOURCE = textwrap.dedent(
    """
    import json
    import os
    from collections import Counter
    from datetime import datetime, timezone
    from decimal import Decimal, InvalidOperation

    import boto3
    from botocore.exceptions import ClientError


    def _fmt_duration(delta):
        total_seconds = int(delta.total_seconds())
        if total_seconds < 0:
            total_seconds = 0
        days, remainder = divmod(total_seconds, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, seconds = divmod(remainder, 60)
        parts = []
        if days:
            parts.append(f"{days}d")
        if hours:
            parts.append(f"{hours}h")
        if minutes:
            parts.append(f"{minutes}m")
        if not parts:
            parts.append(f"{seconds}s")
        return " ".join(parts)


    def _safe_decimal(value):
        if value is None:
            return None
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError):
            return None


    def _gather_tagged_resources(tag_client, cluster_name):
        resources = []
        paginator = tag_client.get_paginator("get_resources")
        for page in paginator.paginate(
            TagFilters=[{"Key": "parallelcluster:cluster-name", "Values": [cluster_name]}]
        ):
            resources.extend(page.get("ResourceTagMappingList", []))
        return resources


    def _extract_tag(resources, key):
        for resource in resources:
            for tag in resource.get("Tags", []):
                if tag.get("Key") == key:
                    return tag.get("Value")
        return None


    def _summarize_resources(resources):
        counts = Counter()
        for resource in resources:
            rtype = resource.get("ResourceType", "unknown")
            counts[rtype] += 1
        return counts


    def handler(event, _context):
        region = os.environ["CLUSTER_REGION"]
        cluster_name = os.environ["CLUSTER_NAME"]
        topic_arn = os.environ["TOPIC_ARN"]
        budget_region = os.environ.get("BUDGET_REGION", region)

        session = boto3.Session(region_name=region)
        tag_client = session.client("resourcegroupstaggingapi")
        cloudformation = session.client("cloudformation")
        sns = session.client("sns")
        sts = session.client("sts")

        resources = _gather_tagged_resources(tag_client, cluster_name)
        owner = _extract_tag(resources, "aws-parallelcluster-username") or "unknown"
        project = _extract_tag(resources, "aws-parallelcluster-project")

        stack_name = f"parallelcluster-{cluster_name}"
        stack_status = "UNKNOWN"
        created = None
        try:
            stack = cloudformation.describe_stacks(StackName=stack_name)["Stacks"][0]
        except ClientError:
            stack = None
        if stack:
            stack_status = stack.get("StackStatus", "UNKNOWN")
            created = stack.get("CreationTime")

        uptime_line = "Uptime: unavailable"
        if created:
            now = datetime.now(timezone.utc)
            uptime_line = f"Uptime: {_fmt_duration(now - created)} (since {created.isoformat()})"

        counts = _summarize_resources(resources)
        resource_lines = []
        if resources:
            resource_lines.append("Tagged resources still present (parallelcluster:cluster-name):")
            for resource in resources[:10]:
                rtype = resource.get("ResourceType", "unknown")
                arn = resource.get("ResourceARN", "")
                resource_lines.append(f"  - {rtype}: {arn}")
            remaining = len(resources) - min(len(resources), 10)
            if remaining:
                resource_lines.append(f"  ... plus {remaining} more resource(s).")
        else:
            resource_lines.append("No tagged resources found. Cluster appears fully torn down.")

        budget_lines = ["Budget: unavailable"]
        if project:
            account_id = sts.get_caller_identity()["Account"]
            budgets = boto3.client("budgets", region_name=budget_region)
            try:
                budget_resp = budgets.describe_budget(AccountId=account_id, BudgetName=project)
            except budgets.exceptions.NotFoundException:  # type: ignore[attr-defined]
                budget_resp = None
            except ClientError:
                budget_resp = None
            if budget_resp:
                budget = budget_resp.get("Budget", {})
                limit = _safe_decimal(budget.get("BudgetLimit", {}).get("Amount"))
                actual = _safe_decimal(
                    budget.get("CalculatedSpend", {}).get("ActualSpend", {}).get("Amount")
                )
                forecast = _safe_decimal(
                    budget.get("CalculatedSpend", {}).get("ForecastedSpend", {}).get("Amount")
                )
                percent = None
                if limit and limit > 0 and actual is not None:
                    percent = (actual / limit) * 100
                parts = [f"Budget '{project}':"]
                if limit is not None:
                    parts.append(f"  Limit: ${limit:.2f}")
                if actual is not None:
                    parts.append(f"  Actual spend: ${actual:.2f}")
                if forecast is not None:
                    parts.append(f"  Forecast: ${forecast:.2f}")
                if percent is not None:
                    parts.append(f"  Usage: {percent:.1f}% of limit")
                budget_lines = parts

        summary_lines = [
            f"Cluster: {cluster_name} ({region})",
            f"Stack status: {stack_status}",
            uptime_line,
            f"Owner: {owner}",
            f"Tagged resource count: {sum(counts.values())} across {len(counts)} service(s)",
        ]

        message_lines = summary_lines + [""] + budget_lines + [""] + resource_lines

        sns.publish(
            TopicArn=topic_arn,
            Subject=f"Daylily heartbeat for {cluster_name}",
            Message="\n".join(message_lines),
        )

        return {"status": "ok", "resources": len(resources), "stack_status": stack_status}
    """
)


def resolve_scheduler_role_arn(session: boto3.Session, explicit: Optional[str], account_id: str) -> str:
    if explicit:
        return explicit

    for env_var in ROLE_ENV_VARS:
        value = os.environ.get(env_var)
        if value:
            print(f"ℹ️ Using scheduler role ARN from ${env_var}.")
            return value

    iam = session.client("iam")
    for role_name in DEFAULT_ROLE_NAMES:
        arn = f"arn:aws:iam::{account_id}:role/{role_name}"
        try:
            iam.get_role(RoleName=role_name)
        except ClientError as error:
            code = error.response.get("Error", {}).get("Code", "")
            if code == "NoSuchEntity":
                continue
            if code == "AccessDenied":
                print(
                    "⚠️ Access denied when checking IAM role '" + role_name + "'.",
                    "Provide --scheduler-role-arn explicitly or set one of the DAY_HEARTBEAT_* environment variables.",
                    file=sys.stderr,
                )
                break
            raise
        else:
            print(f"ℹ️ Using IAM role {arn} (auto-detected).")
            return arn

    print(
        "Error: Unable to determine EventBridge Scheduler role ARN. "
        "Pass --scheduler-role-arn or set DAY_HEARTBEAT_SCHEDULER_ROLE_ARN.",
        file=sys.stderr,
    )
    sys.exit(2)


def resolve_lambda_role_arn(explicit: Optional[str]) -> str:
    if explicit:
        return explicit

    for env_var in LAMBDA_ROLE_ENV_VARS:
        value = os.environ.get(env_var)
        if value:
            print(f"ℹ️ Using heartbeat Lambda role ARN from ${env_var}.")
            return value

    print(
        "Error: Unable to determine heartbeat Lambda execution role ARN. "
        "Pass --lambda-role-arn or set DAY_HEARTBEAT_LAMBDA_ROLE_ARN.",
        file=sys.stderr,
    )
    sys.exit(2)


def build_lambda_package() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr("lambda_function.py", LAMBDA_SOURCE)
    return buffer.getvalue()


def ensure_lambda_function(lambda_client, function_name: str, role_arn: str, env: Dict[str, str]):
    package = build_lambda_package()
    try:
        resp = lambda_client.get_function(FunctionName=function_name)
    except ClientError as error:
        if error.response["Error"].get("Code") != "ResourceNotFoundException":
            raise
        print(f"ℹ️ Creating heartbeat Lambda function {function_name}.")
        created = lambda_client.create_function(
            FunctionName=function_name,
            Runtime="python3.11",
            Role=role_arn,
            Handler="lambda_function.handler",
            Code={"ZipFile": package},
            Description="Publishes detailed Daylily heartbeat data to SNS.",
            Timeout=60,
            MemorySize=256,
            Publish=True,
            Environment={"Variables": env},
            Architectures=["x86_64"],
        )
        return created["FunctionArn"]

    print(f"ℹ️ Updating heartbeat Lambda function {function_name}.")
    lambda_client.update_function_code(FunctionName=function_name, ZipFile=package, Publish=True)
    lambda_client.update_function_configuration(
        FunctionName=function_name,
        Role=role_arn,
        Environment={"Variables": env},
        Timeout=60,
        MemorySize=256,
    )
    return resp["Configuration"]["FunctionArn"]


def create_or_update_schedule(scheduler, name, expr, role_arn, target_arn, target_input, timezone=None):
    target = {
        "Arn": target_arn,
        "RoleArn": role_arn,
        "Input": json.dumps(target_input),
    }
    kwargs = dict(
        Name=name,
        GroupName="default",
        ScheduleExpression=expr,
        FlexibleTimeWindow={"Mode": "OFF"},
        Target=target,
        State="ENABLED",
    )
    if timezone:
        kwargs["ScheduleExpressionTimezone"] = timezone
    try:
        scheduler.create_schedule(**kwargs)
    except ClientError as e:
        if e.response["Error"].get("Code") != "ConflictException":
            raise
        scheduler.update_schedule(**kwargs)

def main():
    a = parse_args()
    profile = resolve_aws_profile(a.profile)

    sess = boto3.Session(profile_name=profile, region_name=a.region)
    sns = sess.client("sns")
    sch = sess.client("scheduler")
    sts = sess.client("sts")
    lambda_client = sess.client("lambda")

    names = derive_names(a.cluster_name)
    acct = sts.get_caller_identity()["Account"]
    role_arn = resolve_scheduler_role_arn(sess, a.scheduler_role_arn, acct)
    lambda_role_arn = resolve_lambda_role_arn(a.lambda_role_arn)

    topic_arn = ensure_topic_and_sub(sns, names.topic_name, a.email, a.region, acct)
    lambda_env = {
        "CLUSTER_NAME": a.cluster_name,
        "CLUSTER_REGION": a.region,
        "TOPIC_ARN": topic_arn,
        "BUDGET_REGION": a.region,
    }
    function_arn = ensure_lambda_function(
        lambda_client, names.function_name, lambda_role_arn, lambda_env
    )

    schedule_name = names.schedule_name
    schedule_input = {
        "cluster": a.cluster_name,
        "invoked_at": int(time.time()),
    }

    create_or_update_schedule(
        sch, schedule_name, a.schedule, role_arn, function_arn, schedule_input
    )

    print("✅ Heartbeat schedule configured (via Lambda to SNS).")
    print(f"   SNS topic: {topic_arn}")
    print(f"   Lambda: {function_arn}")
    print(f"   Schedule: arn:aws:scheduler:{a.region}:{acct}:schedule/default/{schedule_name} -> {a.schedule}")
    print("   Reminder: confirm the SNS email subscription if you haven’t.")

if __name__ == "__main__":
    sys.exit(main())
