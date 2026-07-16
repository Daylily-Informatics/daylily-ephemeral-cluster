#!/usr/bin/env python3
"""Collect read-only utilization for top July FSx and S3 resource IDs."""

from __future__ import annotations

import csv
import json
import os
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any


PROFILE = "lsmc"
START = "2026-07-01T00:00:00Z"
END = "2026-07-15T00:00:00Z"
ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
records: list[dict[str, Any]] = []


def run_aws(args: list[str], region: str) -> dict[str, Any]:
    env = os.environ.copy()
    env["AWS_PROFILE"] = PROFILE
    env["AWS_DEFAULT_REGION"] = region
    cmd = ["aws", *args, "--profile", PROFILE, "--region", region, "--output", "json"]
    proc = subprocess.run(cmd, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    records.append({"command": " ".join(cmd), "returncode": proc.returncode, "stderr": proc.stderr.strip()})
    if proc.returncode:
        print(json.dumps(records[-1], indent=2), file=sys.stderr)
        raise SystemExit(proc.returncode)
    return json.loads(proc.stdout) if proc.stdout.strip() else {}


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("")
        return
    fields: list[str] = []
    for row in rows:
        for field in row:
            if field not in fields:
                fields.append(field)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def costs(service: str, limit: int) -> list[tuple[str, float]]:
    amounts: dict[str, float] = defaultdict(float)
    with (DATA / "resource_daily.csv").open(newline="") as handle:
        for row in csv.DictReader(handle):
            if row["service"] == service and row["resource_id"] not in ("", "NoResourceId"):
                amounts[row["resource_id"]] += float(row["cost_usd"])
    return sorted(amounts.items(), key=lambda x: x[1], reverse=True)[:limit]


def stats(namespace: str, metric: str, dimensions: list[dict[str, str]], region: str, statistic: str, period: int) -> list[dict[str, Any]]:
    payload = run_aws([
        "cloudwatch", "get-metric-statistics", "--namespace", namespace,
        "--metric-name", metric, "--dimensions", json.dumps(dimensions),
        "--start-time", START, "--end-time", END, "--period", str(period),
        "--statistics", statistic,
    ], region)
    return payload.get("Datapoints", [])


def fsx() -> list[dict[str, Any]]:
    rows = []
    for arn, cost in costs("Amazon FSx", 15):
        match = re.match(r"arn:aws:fsx:([^:]+):[^:]+:file-system/(fs-[a-z0-9]+)", arn)
        if not match:
            continue
        region, fsid = match.groups()
        dims = [{"Name": "FileSystemId", "Value": fsid}]
        read = [float(x["Sum"]) for x in stats("AWS/FSx", "DataReadBytes", dims, region, "Sum", 3600)]
        write = [float(x["Sum"]) for x in stats("AWS/FSx", "DataWriteBytes", dims, region, "Sum", 3600)]
        meta = [float(x["Sum"]) for x in stats("AWS/FSx", "MetadataOperations", dims, region, "Sum", 3600)]
        free = sorted(stats("AWS/FSx", "FreeDataStorageCapacity", dims, region, "Average", 3600), key=lambda x: x.get("Timestamp", ""))
        rows.append({
            "region": region, "resource_id": fsid, "july_cost_usd": round(cost, 2),
            "read_tib": round(sum(read) / 2**40, 3), "write_tib": round(sum(write) / 2**40, 3),
            "metadata_ops": int(sum(meta)),
            "latest_free_tib": round(float(free[-1]["Average"]) / 2**40, 3) if free else None,
            "metric_datapoints": max(len(read), len(write), len(meta)),
        })
    return rows


def inventory_bucket_regions() -> dict[str, str]:
    result = {}
    with (DATA / "inventory.csv").open(newline="") as handle:
        for row in csv.DictReader(handle):
            if row["kind"] == "bucket":
                result[row["resource_id"]] = row["region"]
    return result


def s3() -> list[dict[str, Any]]:
    regions = inventory_bucket_regions()
    rows = []
    for bucket, cost in costs("Amazon Simple Storage Service", 15):
        region = regions.get(bucket)
        if not region:
            continue
        listed = run_aws([
            "cloudwatch", "list-metrics", "--namespace", "AWS/S3", "--metric-name", "BucketSizeBytes",
            "--dimensions", f"Name=BucketName,Value={bucket}",
        ], region)
        total_bytes = 0.0
        storage_types = []
        for metric in listed.get("Metrics", []):
            dims = metric.get("Dimensions", [])
            points = sorted(stats("AWS/S3", "BucketSizeBytes", dims, region, "Average", 86400), key=lambda x: x.get("Timestamp", ""))
            if points:
                total_bytes += float(points[-1]["Average"])
                storage_types.extend(d.get("Value", "") for d in dims if d.get("Name") == "StorageType")
        object_points = stats(
            "AWS/S3", "NumberOfObjects",
            [{"Name": "BucketName", "Value": bucket}, {"Name": "StorageType", "Value": "AllStorageTypes"}],
            region, "Average", 86400,
        )
        object_points = sorted(object_points, key=lambda x: x.get("Timestamp", ""))
        req = run_aws([
            "cloudwatch", "list-metrics", "--namespace", "AWS/S3", "--metric-name", "AllRequests",
            "--dimensions", f"Name=BucketName,Value={bucket}",
        ], region)
        request_total = 0.0
        for metric in req.get("Metrics", []):
            request_total += sum(float(x["Sum"]) for x in stats("AWS/S3", "AllRequests", metric.get("Dimensions", []), region, "Sum", 3600))
        rows.append({
            "region": region, "bucket": bucket, "july_cost_usd": round(cost, 2),
            "latest_size_tib": round(total_bytes / 2**40, 3),
            "latest_object_count": int(float(object_points[-1]["Average"])) if object_points else None,
            "storage_types": ";".join(sorted(set(storage_types))),
            "request_metrics_enabled": bool(req.get("Metrics")),
            "all_requests": int(request_total) if request_total else None,
        })
    return rows


def main() -> None:
    fsx_rows = fsx()
    s3_rows = s3()
    write_csv(DATA / "utilization_fsx_top_cost.csv", fsx_rows)
    write_csv(DATA / "utilization_s3_top_cost.csv", s3_rows)
    write_json(DATA / "utilization_storage_command_records.json", records)
    print(json.dumps({
        "fsx_rows": len(fsx_rows), "fsx_rows_with_metrics": sum(1 for x in fsx_rows if x["metric_datapoints"]),
        "s3_rows": len(s3_rows), "s3_request_metrics_enabled": sum(1 for x in s3_rows if x["request_metrics_enabled"]),
        "command_count": len(records), "command_errors": sum(1 for x in records if x["returncode"]),
    }, indent=2))


if __name__ == "__main__":
    main()
