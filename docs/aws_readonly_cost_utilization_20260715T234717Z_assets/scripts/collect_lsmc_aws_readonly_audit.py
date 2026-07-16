#!/usr/bin/env python3
"""Collect a bounded, read-only AWS cost, tag, and utilization audit."""

from __future__ import annotations

import csv
import datetime as dt
import json
import math
import os
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any


PROFILE = "lsmc"
ACCOUNT_ID = "108782052779"
HOME_REGION = "us-west-2"
START = "2026-06-01"
MTD_START = "2026-07-01"
END = "2026-07-15"  # Cost Explorer end is exclusive.
CW_START = "2026-07-01T00:00:00Z"
CW_END = "2026-07-15T00:00:00Z"
GENERATED_AT = dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")
ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "raw"
DATA = ROOT / "data"

TOP_RESOURCE_SERVICES = [
    "Amazon Elastic Compute Cloud - Compute",
    "EC2 - Other",
    "Amazon FSx",
    "Amazon Relational Database Service",
    "Amazon Simple Storage Service",
    "Amazon Virtual Private Cloud",
    "Amazon Elastic Load Balancing",
]

RESOURCE_EXPLORER_SERVICES = [
    "ec2", "fsx", "rds", "s3", "elasticloadbalancing", "ecs", "ecr",
    "lambda", "dynamodb", "logs", "cloudformation",
]

command_records: list[dict[str, Any]] = []


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
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


def run_aws(
    args: list[str], *, region: str = HOME_REGION, required: bool = True,
    record: bool = True,
) -> Any | None:
    env = os.environ.copy()
    env["AWS_PROFILE"] = PROFILE
    env["AWS_DEFAULT_REGION"] = region
    cmd = ["aws", *args, "--profile", PROFILE, "--region", region, "--output", "json"]
    proc = subprocess.run(cmd, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    rec = {
        "command": " ".join(cmd), "region": region,
        "returncode": proc.returncode, "stderr": proc.stderr.strip(),
    }
    if record:
        command_records.append(rec)
    if proc.returncode != 0:
        if required:
            print(json.dumps(rec, indent=2), file=sys.stderr)
            raise SystemExit(proc.returncode)
        return None
    return json.loads(proc.stdout) if proc.stdout.strip() else {}


def tags_dict(tags: Any) -> dict[str, str]:
    result: dict[str, str] = {}
    for tag in tags or []:
        key = tag.get("Key") or tag.get("key")
        if key:
            result[str(key)] = str(tag.get("Value") or tag.get("value") or "")
    return result


def user_tags(tags: dict[str, str]) -> dict[str, str]:
    return {k: v for k, v in tags.items() if not k.lower().startswith("aws:")}


def tag_text(tags: dict[str, str]) -> str:
    return ";".join(f"{k}={v}" for k, v in sorted(tags.items()))


def add_resource(
    rows: list[dict[str, Any]], *, service: str, kind: str, region: str,
    resource_id: str, arn: str = "", name: str = "", tags: dict[str, str] | None = None,
    **attrs: Any,
) -> None:
    all_tags = tags or {}
    utags = user_tags(all_tags)
    row = {
        "service": service, "kind": kind, "region": region,
        "resource_id": resource_id, "arn": arn, "name": name,
        "user_tag_count": len(utags), "untagged": len(utags) == 0,
        "user_tags": tag_text(utags), "all_tags": tag_text(all_tags),
    }
    row.update(attrs)
    rows.append(row)


def ce_query(name: str, args: list[str]) -> Any:
    payload = run_aws(args, region="us-east-1")
    write_json(RAW / f"{name}.json", payload)
    return payload


def flatten_cost(payload: dict[str, Any], fields: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for period in payload.get("ResultsByTime", []):
        for group in period.get("Groups", []):
            row: dict[str, Any] = {
                "start": period["TimePeriod"]["Start"],
                "end": period["TimePeriod"]["End"],
                "estimated": bool(period.get("Estimated")),
                "cost_usd": float(group["Metrics"]["UnblendedCost"]["Amount"]),
            }
            for idx, field in enumerate(fields):
                value = group.get("Keys", [])[idx] if idx < len(group.get("Keys", [])) else ""
                row[field] = value.split("$", 1)[1] if field.startswith("tag_") and "$" in value else value
            rows.append(row)
    return rows


def percentile(values: list[float], quantile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, math.ceil(quantile * len(ordered)) - 1))
    return ordered[idx]


def metric_stats(
    namespace: str, metric: str, dimensions: list[dict[str, str]], region: str,
    statistic: str = "Average", period: int = 3600,
) -> list[dict[str, Any]]:
    payload = run_aws([
        "cloudwatch", "get-metric-statistics", "--namespace", namespace,
        "--metric-name", metric, "--dimensions", json.dumps(dimensions),
        "--start-time", CW_START, "--end-time", CW_END,
        "--period", str(period), "--statistics", statistic,
    ], region=region, required=False)
    return (payload or {}).get("Datapoints", [])


def inventory_region(region: str, rows: list[dict[str, Any]]) -> None:
    payload = run_aws(["ec2", "describe-instances"], region=region)
    for reservation in payload.get("Reservations", []):
        for item in reservation.get("Instances", []):
            tags = tags_dict(item.get("Tags"))
            add_resource(
                rows, service="EC2", kind="instance", region=region,
                resource_id=item["InstanceId"],
                arn=f"arn:aws:ec2:{region}:{ACCOUNT_ID}:instance/{item['InstanceId']}",
                name=tags.get("Name", ""), tags=tags,
                state=item.get("State", {}).get("Name", ""),
                instance_type=item.get("InstanceType", ""),
                launch_time=item.get("LaunchTime", ""),
            )

    payload = run_aws(["ec2", "describe-volumes"], region=region)
    for item in payload.get("Volumes", []):
        tags = tags_dict(item.get("Tags"))
        add_resource(
            rows, service="EBS", kind="volume", region=region,
            resource_id=item["VolumeId"],
            arn=f"arn:aws:ec2:{region}:{ACCOUNT_ID}:volume/{item['VolumeId']}",
            name=tags.get("Name", ""), tags=tags, state=item.get("State", ""),
            size_gib=item.get("Size", 0), volume_type=item.get("VolumeType", ""),
            attached_instance_ids=";".join(a.get("InstanceId", "") for a in item.get("Attachments", [])),
        )

    payload = run_aws(["ec2", "describe-snapshots", "--owner-ids", "self"], region=region)
    for item in payload.get("Snapshots", []):
        tags = tags_dict(item.get("Tags"))
        add_resource(
            rows, service="EBS", kind="snapshot", region=region,
            resource_id=item["SnapshotId"],
            arn=f"arn:aws:ec2:{region}:{ACCOUNT_ID}:snapshot/{item['SnapshotId']}",
            name=tags.get("Name", ""), tags=tags, state=item.get("State", ""),
            volume_size_gib=item.get("VolumeSize", 0), start_time=item.get("StartTime", ""),
        )

    payload = run_aws(["ec2", "describe-addresses"], region=region)
    for item in payload.get("Addresses", []):
        tags = tags_dict(item.get("Tags"))
        rid = item.get("AllocationId") or item.get("PublicIp", "")
        add_resource(
            rows, service="EC2", kind="elastic_ip", region=region, resource_id=rid,
            arn=f"arn:aws:ec2:{region}:{ACCOUNT_ID}:elastic-ip/{rid}",
            name=tags.get("Name", ""), tags=tags,
            associated=bool(item.get("AssociationId")), public_ip=item.get("PublicIp", ""),
        )

    payload = run_aws(["ec2", "describe-nat-gateways"], region=region)
    for item in payload.get("NatGateways", []):
        tags = tags_dict(item.get("Tags"))
        add_resource(
            rows, service="VPC", kind="nat_gateway", region=region,
            resource_id=item["NatGatewayId"],
            arn=f"arn:aws:ec2:{region}:{ACCOUNT_ID}:natgateway/{item['NatGatewayId']}",
            name=tags.get("Name", ""), tags=tags, state=item.get("State", ""),
        )

    payload = run_aws(["fsx", "describe-file-systems"], region=region)
    for item in payload.get("FileSystems", []):
        tags = tags_dict(item.get("Tags"))
        add_resource(
            rows, service="FSx", kind="file_system", region=region,
            resource_id=item["FileSystemId"], arn=item.get("ResourceARN", ""),
            name=tags.get("Name", ""), tags=tags, state=item.get("Lifecycle", ""),
            fsx_type=item.get("FileSystemType", ""), storage_capacity_gib=item.get("StorageCapacity", 0),
            storage_type=item.get("StorageType", ""),
        )

    payload = run_aws(["rds", "describe-db-instances"], region=region)
    for item in payload.get("DBInstances", []):
        arn = item.get("DBInstanceArn", "")
        tag_payload = run_aws(["rds", "list-tags-for-resource", "--resource-name", arn], region=region)
        tags = tags_dict(tag_payload.get("TagList"))
        add_resource(
            rows, service="RDS", kind="db_instance", region=region,
            resource_id=item["DBInstanceIdentifier"], arn=arn,
            name=tags.get("Name", item["DBInstanceIdentifier"]), tags=tags,
            state=item.get("DBInstanceStatus", ""), db_class=item.get("DBInstanceClass", ""),
            engine=item.get("Engine", ""), allocated_storage_gib=item.get("AllocatedStorage", 0),
            cluster_id=item.get("DBClusterIdentifier", ""),
        )

    payload = run_aws(["rds", "describe-db-clusters"], region=region)
    for item in payload.get("DBClusters", []):
        arn = item.get("DBClusterArn", "")
        tag_payload = run_aws(["rds", "list-tags-for-resource", "--resource-name", arn], region=region)
        tags = tags_dict(tag_payload.get("TagList"))
        add_resource(
            rows, service="RDS", kind="db_cluster", region=region,
            resource_id=item["DBClusterIdentifier"], arn=arn,
            name=tags.get("Name", item["DBClusterIdentifier"]), tags=tags,
            state=item.get("Status", ""), engine=item.get("Engine", ""),
            serverless_v2_min_acu=(item.get("ServerlessV2ScalingConfiguration") or {}).get("MinCapacity", ""),
            serverless_v2_max_acu=(item.get("ServerlessV2ScalingConfiguration") or {}).get("MaxCapacity", ""),
        )

    payload = run_aws(["elbv2", "describe-load-balancers"], region=region)
    for item in payload.get("LoadBalancers", []):
        arn = item.get("LoadBalancerArn", "")
        tag_payload = run_aws(["elbv2", "describe-tags", "--resource-arns", arn], region=region)
        descriptions = tag_payload.get("TagDescriptions", [])
        tags = tags_dict(descriptions[0].get("Tags") if descriptions else [])
        add_resource(
            rows, service="ELBv2", kind="load_balancer", region=region,
            resource_id=item.get("LoadBalancerName", ""), arn=arn,
            name=item.get("LoadBalancerName", ""), tags=tags,
            state=(item.get("State") or {}).get("Code", ""), lb_type=item.get("Type", ""),
        )


def inventory_s3(rows: list[dict[str, Any]]) -> None:
    payload = run_aws(["s3api", "list-buckets"])
    for item in payload.get("Buckets", []):
        name = item["Name"]
        location = run_aws(["s3api", "get-bucket-location", "--bucket", name], required=False)
        region = (location or {}).get("LocationConstraint") or "us-east-1"
        tag_payload = run_aws(["s3api", "get-bucket-tagging", "--bucket", name], region=region, required=False)
        tags = tags_dict((tag_payload or {}).get("TagSet"))
        lifecycle = run_aws(["s3api", "get-bucket-lifecycle-configuration", "--bucket", name], region=region, required=False)
        add_resource(
            rows, service="S3", kind="bucket", region=region,
            resource_id=name, arn=f"arn:aws:s3:::{name}", name=name, tags=tags,
            creation_date=item.get("CreationDate", ""), has_lifecycle=bool((lifecycle or {}).get("Rules")),
        )


def resource_explorer_untagged(index_regions: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for region in index_regions:
        for service in RESOURCE_EXPLORER_SERVICES:
            token: str | None = None
            while True:
                args = ["resource-explorer-2", "search", "--query-string", f"service:{service} tag:none", "--max-results", "1000"]
                if token:
                    args.extend(["--next-token", token])
                payload = run_aws(args, region=region)
                for item in payload.get("Resources", []):
                    arn = item.get("Arn", "")
                    if arn in seen:
                        continue
                    seen.add(arn)
                    rows.append({
                        "service": item.get("Service", ""), "resource_type": item.get("ResourceType", ""),
                        "region": item.get("Region", ""), "arn": arn,
                        "last_reported_at": item.get("LastReportedAt", ""), "source_index_region": region,
                    })
                token = payload.get("NextToken")
                if not token:
                    break
    return rows


def cloudwatch_utilization(resources: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in resources:
        region = row["region"]
        rid = row["resource_id"]
        if row["kind"] == "db_instance" and row.get("state") == "available":
            dims = [{"Name": "DBInstanceIdentifier", "Value": rid}]
            cpu = [float(x["Average"]) for x in metric_stats("AWS/RDS", "CPUUtilization", dims, region)]
            conns = [float(x["Average"]) for x in metric_stats("AWS/RDS", "DatabaseConnections", dims, region)]
            free_mem = [float(x["Average"]) for x in metric_stats("AWS/RDS", "FreeableMemory", dims, region)]
            result["rds"].append({
                "region": region, "resource_id": rid, "db_class": row.get("db_class", ""),
                "engine": row.get("engine", ""), "untagged": row["untagged"],
                "cpu_avg_pct": round(sum(cpu) / len(cpu), 2) if cpu else None,
                "cpu_p95_pct": round(percentile(cpu, .95), 2) if cpu else None,
                "cpu_max_pct": round(max(cpu), 2) if cpu else None,
                "connections_avg": round(sum(conns) / len(conns), 2) if conns else None,
                "connections_max": round(max(conns), 2) if conns else None,
                "freeable_memory_avg_gib": round(sum(free_mem) / len(free_mem) / 2**30, 2) if free_mem else None,
                "datapoints": len(cpu),
            })
        elif row["kind"] == "file_system" and row.get("state") == "AVAILABLE":
            dims = [{"Name": "FileSystemId", "Value": rid}]
            read = [float(x["Sum"]) for x in metric_stats("AWS/FSx", "DataReadBytes", dims, region, "Sum")]
            write = [float(x["Sum"]) for x in metric_stats("AWS/FSx", "DataWriteBytes", dims, region, "Sum")]
            meta = [float(x["Sum"]) for x in metric_stats("AWS/FSx", "MetadataOperations", dims, region, "Sum")]
            free = sorted(metric_stats("AWS/FSx", "FreeDataStorageCapacity", dims, region), key=lambda x: x.get("Timestamp", ""))
            result["fsx"].append({
                "region": region, "resource_id": rid, "name": row.get("name", ""),
                "fsx_type": row.get("fsx_type", ""), "storage_capacity_gib": row.get("storage_capacity_gib", 0),
                "untagged": row["untagged"], "read_tib": round(sum(read) / 2**40, 3),
                "write_tib": round(sum(write) / 2**40, 3), "metadata_ops": int(sum(meta)),
                "latest_free_tib": round(float(free[-1]["Average"]) / 2**40, 3) if free else None,
                "datapoints": max(len(read), len(write), len(meta)),
            })
        elif row["kind"] == "volume" and (row.get("untagged") or int(row.get("size_gib", 0)) >= 200):
            dims = [{"Name": "VolumeId", "Value": rid}]
            idle = [float(x["Sum"]) for x in metric_stats("AWS/EBS", "VolumeIdleTime", dims, region, "Sum")]
            reads = [float(x["Sum"]) for x in metric_stats("AWS/EBS", "VolumeReadOps", dims, region, "Sum")]
            writes = [float(x["Sum"]) for x in metric_stats("AWS/EBS", "VolumeWriteOps", dims, region, "Sum")]
            result["ebs"].append({
                "region": region, "resource_id": rid, "name": row.get("name", ""),
                "size_gib": row.get("size_gib", 0), "state": row.get("state", ""),
                "attached_instance_ids": row.get("attached_instance_ids", ""), "untagged": row["untagged"],
                "idle_pct_of_window": round(min(100.0, sum(idle) / (14 * 86400) * 100), 2) if idle else None,
                "read_ops": int(sum(reads)), "write_ops": int(sum(writes)), "datapoints": len(idle),
            })
        elif row["kind"] == "nat_gateway" and row.get("state") == "available":
            dims = [{"Name": "NatGatewayId", "Value": rid}]
            total = 0.0
            points = 0
            for metric in ("BytesInFromDestination", "BytesInFromSource", "BytesOutToDestination", "BytesOutToSource"):
                vals = [float(x["Sum"]) for x in metric_stats("AWS/NATGateway", metric, dims, region, "Sum")]
                total += sum(vals)
                points = max(points, len(vals))
            result["nat"].append({
                "region": region, "resource_id": rid, "name": row.get("name", ""),
                "untagged": row["untagged"], "total_traffic_gib": round(total / 2**30, 3),
                "datapoints": points,
            })
    return result


def s3_storage_metrics(regions: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for region in regions:
        queries = [
            {"Id": "bytes", "Expression": "SEARCH('{AWS/S3,BucketName,StorageType} MetricName=\"BucketSizeBytes\"', 'Average', 86400)", "ReturnData": True},
            {"Id": "objects", "Expression": "SEARCH('{AWS/S3,BucketName,StorageType} MetricName=\"NumberOfObjects\"', 'Average', 86400)", "ReturnData": True},
        ]
        payload = run_aws([
            "cloudwatch", "get-metric-data", "--metric-data-queries", json.dumps(queries),
            "--start-time", "2026-07-13T00:00:00Z", "--end-time", CW_END,
            "--scan-by", "TimestampDescending", "--max-datapoints", "100800",
        ], region=region, required=False)
        for series in (payload or {}).get("MetricDataResults", []):
            label = series.get("Label", "")
            values = series.get("Values", [])
            match = re.search(r"BucketName[ =:]+'?([^,}' ]+)", label)
            bucket = match.group(1) if match else label
            rows.append({
                "region": region, "metric": series.get("Id", ""), "label": label,
                "bucket": bucket, "latest_value": float(values[0]) if values else None,
                "datapoints": len(values),
            })
    return rows


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    DATA.mkdir(parents=True, exist_ok=True)

    identity = run_aws(["sts", "get-caller-identity"])
    if identity.get("Account") != ACCOUNT_ID:
        raise SystemExit(f"refusing unexpected account {identity.get('Account')}")
    write_json(RAW / "caller_identity.json", identity)

    region_payload = run_aws(["ec2", "describe-regions", "--all-regions"])
    regions = sorted(r["RegionName"] for r in region_payload.get("Regions", []) if r.get("OptInStatus") != "not-opted-in")
    write_json(DATA / "enabled_regions.json", regions)

    indexes = run_aws(["resource-explorer-2", "list-indexes"])
    index_regions = sorted({x["Region"] for x in indexes.get("Indexes", [])})
    write_json(RAW / "resource_explorer_indexes.json", indexes)

    common = ["--time-period", f"Start={START},End={END}", "--granularity", "MONTHLY", "--metrics", "UnblendedCost"]
    service = ce_query("ce_service_monthly", ["ce", "get-cost-and-usage", *common, "--group-by", "Type=DIMENSION,Key=SERVICE"])
    service_usage = ce_query("ce_service_usage_monthly", ["ce", "get-cost-and-usage", *common, "--group-by", "Type=DIMENSION,Key=SERVICE", "Type=DIMENSION,Key=USAGE_TYPE"])
    service_region = ce_query("ce_service_region_monthly", ["ce", "get-cost-and-usage", *common, "--group-by", "Type=DIMENSION,Key=SERVICE", "Type=DIMENSION,Key=REGION"])
    cluster_filter = json.dumps({"Dimensions": {"Key": "SERVICE", "Values": ["Amazon Elastic Compute Cloud - Compute"]}}, separators=(",", ":"))
    cluster = ce_query("ce_ec2_cluster_mtd", [
        "ce", "get-cost-and-usage", "--time-period", f"Start={MTD_START},End={END}",
        "--granularity", "MONTHLY", "--metrics", "UnblendedCost", "--filter", cluster_filter,
        "--group-by", "Type=TAG,Key=parallelcluster:cluster-name", "Type=DIMENSION,Key=PURCHASE_TYPE",
    ])
    resource_filter = json.dumps({"Dimensions": {"Key": "SERVICE", "Values": TOP_RESOURCE_SERVICES}}, separators=(",", ":"))
    resources_cost = ce_query("ce_resource_daily", [
        "ce", "get-cost-and-usage-with-resources", "--time-period", f"Start={MTD_START},End={END}",
        "--granularity", "DAILY", "--metrics", "UnblendedCost", "--filter", resource_filter,
        "--group-by", "Type=DIMENSION,Key=SERVICE", "Type=DIMENSION,Key=RESOURCE_ID",
    ])

    cost_tables = {
        "service_monthly": flatten_cost(service, ["service"]),
        "service_usage_monthly": flatten_cost(service_usage, ["service", "usage_type"]),
        "service_region_monthly": flatten_cost(service_region, ["service", "region"]),
        "ec2_cluster_mtd": flatten_cost(cluster, ["tag_cluster", "purchase_type"]),
        "resource_daily": flatten_cost(resources_cost, ["service", "resource_id"]),
    }
    for name, rows in cost_tables.items():
        write_csv(DATA / f"{name}.csv", rows)

    inventory: list[dict[str, Any]] = []
    for idx, region in enumerate(regions, 1):
        print(f"inventory {idx}/{len(regions)} {region}", flush=True)
        inventory_region(region, inventory)
    inventory_s3(inventory)
    write_json(DATA / "inventory.json", inventory)
    write_csv(DATA / "inventory.csv", inventory)
    direct_untagged = [row for row in inventory if row["untagged"]]
    write_csv(DATA / "direct_untagged.csv", direct_untagged)

    explorer_untagged = resource_explorer_untagged(index_regions)
    write_csv(DATA / "resource_explorer_untagged.csv", explorer_untagged)

    util = cloudwatch_utilization(inventory)
    for name, rows in util.items():
        write_csv(DATA / f"utilization_{name}.csv", rows)
    s3_metrics = s3_storage_metrics(regions)
    write_csv(DATA / "utilization_s3_storage_raw.csv", s3_metrics)

    summary = {
        "generated_at": GENERATED_AT, "account_id": ACCOUNT_ID, "profile": PROFILE,
        "billing_window": {"start": START, "end_exclusive": END},
        "utilization_window": {"start": CW_START, "end_exclusive": CW_END},
        "enabled_region_count": len(regions), "resource_explorer_index_regions": index_regions,
        "inventory_resource_count": len(inventory), "direct_untagged_count": len(direct_untagged),
        "resource_explorer_untagged_count": len(explorer_untagged),
        "inventory_counts_by_kind": dict(sorted(defaultdict(int, {k: sum(1 for r in inventory if r["kind"] == k) for k in {r["kind"] for r in inventory}}).items())),
        "untagged_counts_by_kind": dict(sorted(defaultdict(int, {k: sum(1 for r in direct_untagged if r["kind"] == k) for k in {r["kind"] for r in direct_untagged}}).items())),
        "command_count": len(command_records),
        "command_error_count": sum(1 for x in command_records if x["returncode"] != 0),
    }
    write_json(DATA / "summary.json", summary)
    write_json(DATA / "command_records.json", command_records)
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
