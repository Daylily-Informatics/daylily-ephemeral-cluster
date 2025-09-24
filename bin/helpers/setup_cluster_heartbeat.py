#!/usr/bin/env python3
import argparse, os, sys, time, json, subprocess
import boto3
from botocore.exceptions import ClientError

def parse_args():
    p = argparse.ArgumentParser(description="Wire an SNS heartbeat via EventBridge Scheduler (no IAM writes).")
    p.add_argument("--cluster-name", required=True)
    p.add_argument("--region", required=True)
    p.add_argument("--email", required=True)
    p.add_argument("--schedule", required=True, help="rate(...) or cron(...) in UTC")
    p.add_argument("--profile", help="AWS profile (defaults to AWS_PROFILE)")
    p.add_argument("--scheduler-role-arn", required=True,
                   help="IAM role ARN that EventBridge Scheduler can assume to publish to SNS")
    return p.parse_args()

def resolve_profile(profile):
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

def ensure_topic_and_sub(sns, topic_name, email):
    topic_arn = sns.create_topic(Name=topic_name)["TopicArn"]
    # subscribe email if not already subscribed
    subs = sns.list_subscriptions_by_topic(TopicArn=topic_arn).get("Subscriptions", [])
    if not any(s.get("Protocol")=="email" and s.get("Endpoint")==email for s in subs):
        sns.subscribe(TopicArn=topic_arn, Protocol="email", Endpoint=email)
    return topic_arn

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
    resolve_profile(a.profile)

    sess = boto3.Session(profile_name=os.environ["AWS_PROFILE"], region_name=a.region)
    sns = sess.client("sns")
    sch = sess.client("scheduler")
    sts = sess.client("sts")

    acct = sts.get_caller_identity()["Account"]
    topic_name = f"daylily-{a.cluster_name}-heartbeat"
    topic_arn = ensure_topic_and_sub(sns, topic_name, a.email)

    message = f"Heartbeat for cluster '{a.cluster_name}' at {int(time.time())} (epoch). Region: {a.region}."
    schedule_name = f"daylily-{a.cluster_name}-heartbeat"[:64]  # Scheduler name limit

    create_or_update_schedule(
        sch, schedule_name, a.schedule, a.scheduler_role_arn, topic_arn, message
    )

    print("✅ Heartbeat schedule configured (direct to SNS).")
    print(f"   SNS topic: {topic_arn}")
    print(f"   Schedule: arn:aws:scheduler:{a.region}:{acct}:schedule/default/{schedule_name} -> {a.schedule}")
    print("   Reminder: confirm the SNS email subscription if you haven’t.")

if __name__ == "__main__":
    sys.exit(main())
