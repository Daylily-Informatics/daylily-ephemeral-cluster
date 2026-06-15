#!/usr/bin/env python3
"""Sync current Sentieon GitHub model bundles into the active LSMC runtime prefix."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import urllib.request
from typing import Any

import boto3
import yaml
from botocore.exceptions import ClientError


MODELS_URL = "https://raw.githubusercontent.com/Sentieon/sentieon-models/main/sentieon_models.yaml"
SOURCE_BUCKET = "sentieon-release"
SOURCE_PREFIX = "other/"
DEST_BUCKET = "lsmc-dayoa-references-usw2"
DEST_PREFIX = "runtime_assets/cached_envs/sentieon-genomics-202503.03/bundles/"
BACKUP_PREFIX_TEMPLATE = (
    "runtime_assets/backups/sentieon-genomics-202503.03/"
    "{stamp}/bundles/"
)


def fetch_models() -> dict[str, Any]:
    with urllib.request.urlopen(MODELS_URL, timeout=30) as response:
        return yaml.safe_load(response.read().decode("utf-8"))


def collect_bundle_names(node: Any) -> list[str]:
    names: list[str] = []

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            for child in value.values():
                walk(child)
            return
        if isinstance(value, list):
            for child in value:
                walk(child)
            return
        if isinstance(value, str) and value.startswith(
            "https://s3.amazonaws.com/sentieon-release/other/"
        ):
            name = value.rsplit("/", 1)[-1]
            if name not in names:
                names.append(name)

    walk(node)
    return names


def head_or_none(client: Any, *, bucket: str, key: str) -> dict[str, Any] | None:
    try:
        return client.head_object(Bucket=bucket, Key=key)
    except ClientError as exc:
        code = str(exc.response.get("Error", {}).get("Code", ""))
        if code in {"404", "NoSuchKey", "NotFound"}:
            return None
        raise


def slim_head(head: dict[str, Any] | None) -> dict[str, Any] | None:
    if head is None:
        return None
    return {
        "ContentLength": head.get("ContentLength"),
        "ETag": head.get("ETag"),
        "LastModified": head.get("LastModified").isoformat()
        if head.get("LastModified")
        else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", default=os.environ.get("AWS_PROFILE", "lsmc"))
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--stamp", default=dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    args = parser.parse_args()

    session = boto3.Session(profile_name=args.profile)
    s3 = session.client("s3")
    models = fetch_models()
    bundle_names = collect_bundle_names(models)
    backup_prefix = BACKUP_PREFIX_TEMPLATE.format(stamp=args.stamp)

    rows: list[dict[str, Any]] = []
    for name in bundle_names:
        source_key = f"{SOURCE_PREFIX}{name}"
        dest_key = f"{DEST_PREFIX}{name}"
        backup_key = f"{backup_prefix}{name}"
        source_head = s3.head_object(Bucket=SOURCE_BUCKET, Key=source_key)
        dest_head = head_or_none(s3, bucket=DEST_BUCKET, key=dest_key)
        source_size = int(source_head["ContentLength"])
        dest_size = int(dest_head["ContentLength"]) if dest_head else None
        action = "match"
        if dest_head is None:
            action = "copy_missing"
        elif dest_size != source_size:
            action = "backup_and_replace"
        row: dict[str, Any] = {
            "bundle": name,
            "source_key": f"s3://{SOURCE_BUCKET}/{source_key}",
            "dest_key": f"s3://{DEST_BUCKET}/{dest_key}",
            "backup_key": f"s3://{DEST_BUCKET}/{backup_key}" if dest_head else None,
            "source": slim_head(source_head),
            "before": slim_head(dest_head),
            "action": action,
        }

        if args.execute and action == "backup_and_replace":
            s3.copy_object(
                Bucket=DEST_BUCKET,
                Key=backup_key,
                CopySource={"Bucket": DEST_BUCKET, "Key": dest_key},
                CopySourceIfMatch=dest_head["ETag"],
                MetadataDirective="COPY",
            )
            row["backup"] = slim_head(s3.head_object(Bucket=DEST_BUCKET, Key=backup_key))

        if args.execute and action in {"backup_and_replace", "copy_missing"}:
            s3.copy_object(
                Bucket=DEST_BUCKET,
                Key=dest_key,
                CopySource={"Bucket": SOURCE_BUCKET, "Key": source_key},
                CopySourceIfMatch=source_head["ETag"],
                MetadataDirective="COPY",
            )
            after = s3.head_object(Bucket=DEST_BUCKET, Key=dest_key)
            row["after"] = slim_head(after)
            row["verified"] = int(after["ContentLength"]) == source_size
        rows.append(row)

    summary = {
        "execute": args.execute,
        "profile": args.profile,
        "models_url": MODELS_URL,
        "models_updated_on": models.get("Updated on"),
        "destination_prefix": f"s3://{DEST_BUCKET}/{DEST_PREFIX}",
        "backup_prefix": f"s3://{DEST_BUCKET}/{backup_prefix}",
        "counts": {
            "total": len(rows),
            "match": sum(row["action"] == "match" for row in rows),
            "copy_missing": sum(row["action"] == "copy_missing" for row in rows),
            "backup_and_replace": sum(row["action"] == "backup_and_replace" for row in rows),
        },
        "rows": rows,
    }
    json.dump(summary, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    if args.execute:
        failed = [row for row in rows if row["action"] != "match" and not row.get("verified")]
        return 1 if failed else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
