#!/usr/bin/env python3
import argparse
import sys
import time

import boto3


DAYLILY_PREFIXES = [
    "daylily-files",
    "daylily-filesets",
    "daylily-file-workset-usage",
    "daylily-linked-buckets",
    "daylily-customers",
    # add any other daylily-* tables here if needed
]


def should_delete(table_name: str) -> bool:
    if table_name.startswith("daylily-"):
        return True
    return False


def main():
    parser = argparse.ArgumentParser(
        description="Delete Daylily DynamoDB tables (daylily-*)"
    )
    parser.add_argument(
        "--region",
        default="us-west-2",
        help="AWS region (default: us-west-2)",
    )
    parser.add_argument(
        "--profile",
        default=None,
        help="AWS profile name (optional; omit for default credentials)",
    )
    parser.add_argument(
        "--endpoint-url",
        default=None,
        help="DynamoDB endpoint (e.g. http://localhost:8001 for DynamoDB Local)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Actually delete tables (without this, script is dry-run)",
    )
    args = parser.parse_args()

    session_kwargs = {"region_name": args.region}
    if args.profile:
        session_kwargs["profile_name"] = args.profile
    session = boto3.Session(**session_kwargs)

    client_kwargs = {}
    if args.endpoint_url:
        client_kwargs["endpoint_url"] = args.endpoint_url

    dynamodb = session.client("dynamodb", **client_kwargs)

    # List all tables
    print("Listing DynamoDB tables...")
    tables = []
    paginator = dynamodb.get_paginator("list_tables")
    for page in paginator.paginate():
        tables.extend(page.get("TableNames", []))

    if not tables:
        print("No tables found.")
        return

    candidates = [t for t in tables if should_delete(t)]
    if not candidates:
        print("No tables matching daylily-* found.")
        return

    print("Tables matching daylily-* that would be deleted:")
    for t in candidates:
        print(f"  - {t}")

    if not args.force:
        print("\nDry run only. Re-run with --force to actually delete these tables.")
        return

    # Confirm one more time on stdout
    print("\n*** WARNING ***")
    print("You are about to DELETE the tables listed above.")
    resp = input("Type 'DELETE' to confirm: ")
    if resp.strip().upper() != "DELETE":
        print("Aborted.")
        sys.exit(1)

    for table_name in candidates:
        print(f"Deleting table {table_name} ...")
        dynamodb.delete_table(TableName=table_name)

        # Wait for table to be deleted
        while True:
            try:
                desc = dynamodb.describe_table(TableName=table_name)
                status = desc["Table"]["TableStatus"]
                print(f"  still {status} ...")
                time.sleep(2)
            except dynamodb.exceptions.ResourceNotFoundException:
                print(f"  {table_name} deleted.")
                break

    print("Done.")


if __name__ == "__main__":
    main()
