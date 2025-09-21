#!/usr/bin/env python3
"""Remove heartbeat notification resources for a Daylily ephemeral cluster."""
from __future__ import annotations

import argparse
import sys
from typing import Iterable, Optional

import boto3
from botocore.exceptions import ClientError

from setup_cluster_heartbeat import derive_names  # type: ignore


def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cluster-name", required=True)
    parser.add_argument("--region", required=True)
    parser.add_argument("--profile")
    return parser.parse_args(argv)


def delete_schedule(scheduler_client, schedule_name: str) -> None:
    try:
        scheduler_client.delete_schedule(Name=schedule_name, GroupName="default")
        print(f"Deleted schedule {schedule_name}.")
    except ClientError as error:
        if error.response["Error"].get("Code") in {"ResourceNotFoundException", "ValidationException"}:
            print(f"Schedule {schedule_name} did not exist.")
        else:
            raise


def delete_lambda(lambda_client, function_name: str) -> None:
    try:
        lambda_client.delete_function(FunctionName=function_name)
        print(f"Deleted Lambda function {function_name}.")
    except ClientError as error:
        if error.response["Error"].get("Code") == "ResourceNotFoundException":
            print(f"Lambda function {function_name} did not exist.")
        else:
            raise


def delete_topic(sns_client, topic_arn: str) -> None:
    try:
        sns_client.delete_topic(TopicArn=topic_arn)
        print(f"Deleted SNS topic {topic_arn}.")
    except ClientError as error:
        if error.response["Error"].get("Code") == "NotFound":
            print(f"SNS topic {topic_arn} did not exist.")
        else:
            raise


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = parse_args(argv)

    names = derive_names(args.cluster_name)

    session = boto3.Session(profile_name=args.profile, region_name=args.region) if args.profile else boto3.Session(
        region_name=args.region
    )
    scheduler_client = session.client("scheduler")
    lambda_client = session.client("lambda")
    sns_client = session.client("sns")
    sts_client = session.client("sts")

    account_id = sts_client.get_caller_identity()["Account"]
    topic_arn = names.topic_arn(account_id, args.region)

    delete_schedule(scheduler_client, names.schedule_name)
    delete_lambda(lambda_client, names.function_name)
    delete_topic(sns_client, topic_arn)

    print("✅ Heartbeat notification resources removed (if they existed).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
