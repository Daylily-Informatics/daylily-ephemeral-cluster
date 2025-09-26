#!/usr/bin/env python3
import argparse, os, sys, time, json, subprocess
from dataclasses import dataclass
from typing import Optional

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


def ensure_topic_and_sub(sns, topic_name, email):
    topic_arn = sns.create_topic(Name=topic_name)["TopicArn"]
    # subscribe email if not already subscribed
    subs = sns.list_subscriptions_by_topic(TopicArn=topic_arn).get("Subscriptions", [])
    if not any(s.get("Protocol")=="email" and s.get("Endpoint")==email for s in subs):
        sns.subscribe(TopicArn=topic_arn, Protocol="email", Endpoint=email)
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


def create_or_update_schedule(scheduler, name, expr, role_arn, topic_arn, message, timezone=None):
    target = {
        "Arn": topic_arn,
        "RoleArn": role_arn,
        # EventBridge Scheduler delivers this to SNS as the message
        "Input": json.dumps({"default": message}),  # SNS will use 'default' field as message if no structure
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

    names = derive_names(a.cluster_name)
    acct = sts.get_caller_identity()["Account"]
    role_arn = resolve_scheduler_role_arn(sess, a.scheduler_role_arn, acct)

    topic_arn = ensure_topic_and_sub(sns, names.topic_name, a.email)

    message = f"Heartbeat for cluster '{a.cluster_name}' at {int(time.time())} (epoch). Region: {a.region}."
    schedule_name = names.schedule_name

    create_or_update_schedule(
        sch, schedule_name, a.schedule, role_arn, topic_arn, message
    )

    print("✅ Heartbeat schedule configured (direct to SNS).")
    print(f"   SNS topic: {topic_arn}")
    print(f"   Schedule: arn:aws:scheduler:{a.region}:{acct}:schedule/default/{schedule_name} -> {a.schedule}")
    print("   Reminder: confirm the SNS email subscription if you haven’t.")

if __name__ == "__main__":
    sys.exit(main())
