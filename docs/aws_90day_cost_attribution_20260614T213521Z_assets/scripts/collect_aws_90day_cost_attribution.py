#!/usr/bin/env python3
"""Collect read-only AWS cost and inventory data for the 2026-06-14 report."""

from __future__ import annotations

import csv
import datetime as dt
import json
import os
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape


PROFILE = "lsmc"
DEFAULT_REGION = "us-west-2"
ACCOUNT_ID = "108782052779"
START = "2026-03-16"
END = "2026-06-14"
RECENT_START = "2026-06-01"
RECENT_END = END
GENERATED_AT = dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "raw"
DATA = ROOT / "data"
IMAGES = ROOT / "images"
REPORT = ROOT.parents[0] / "AWS_90day_cost_attribution_20260614.md"
LEDGER = ROOT.parents[0] / "plans" / "20260614T213521Z_aws_90day_cost_attribution_ledger.md"

REGIONS = [
    "ap-south-2",
    "ap-south-1",
    "ca-central-1",
    "eu-central-1",
    "us-west-1",
    "us-west-2",
    "af-south-1",
    "eu-north-1",
    "eu-west-3",
    "eu-west-2",
    "eu-west-1",
    "ap-northeast-3",
    "ap-northeast-2",
    "ap-northeast-1",
    "sa-east-1",
    "ap-east-1",
    "ap-southeast-1",
    "ap-southeast-2",
    "ap-southeast-3",
    "us-east-1",
    "us-east-2",
]

TAG_KEYS = [
    "lsmc-project",
    "project",
    "parallelcluster:cluster-name",
    "aws-parallelcluster-clustername",
    "aws-parallelcluster-project",
    "aws-parallelcluster-username",
]

RESOURCE_COST_SERVICES = [
    "Amazon Elastic Compute Cloud - Compute",
    "EC2 - Other",
    "Amazon Relational Database Service",
    "Amazon Elastic Load Balancing",
    "Amazon Virtual Private Cloud",
    "Amazon Elastic Container Service",
]

COMPUTE_SERVICES = {
    "Amazon Elastic Compute Cloud - Compute",
    "EC2 - Other",
    "Amazon Relational Database Service",
    "Amazon Elastic Load Balancing",
    "Amazon Virtual Private Cloud",
    "Amazon Elastic Container Service",
}

APP_PATTERNS = {
    "terrarium": re.compile(r"terrarium", re.I),
    "aquarium": re.compile(r"aquarium", re.I),
    "dayhoff": re.compile(r"dayhoff|tapdb|lsmcq|lsmcok|jemdev|ddev", re.I),
}

DYEC_TAG_KEYS = {
    "parallelcluster:cluster-name",
    "aws-parallelcluster-clustername",
}


def run_aws(args: list[str], *, region: str | None = None, allow_error: bool = False) -> tuple[Any | None, dict[str, Any]]:
    env = os.environ.copy()
    env["AWS_PROFILE"] = PROFILE
    env["AWS_DEFAULT_REGION"] = region or DEFAULT_REGION
    cmd = ["aws", *args, "--output", "json"]
    proc = subprocess.run(cmd, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    record = {
        "cmd": " ".join(cmd),
        "region": region or DEFAULT_REGION,
        "returncode": proc.returncode,
        "stderr": proc.stderr.strip(),
    }
    if proc.returncode != 0:
        if allow_error:
            return None, record
        print(json.dumps(record, indent=2), file=sys.stderr)
        raise SystemExit(proc.returncode)
    if not proc.stdout.strip():
        return {}, record
    return json.loads(proc.stdout), record


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def amount(group: dict[str, Any]) -> float:
    return float(group["Metrics"]["UnblendedCost"]["Amount"])


def group_key_value(key: str) -> str:
    if "$" in key:
        return key.split("$", 1)[1]
    return key


def ce_query(name: str, granularity: str, group_by: list[tuple[str, str]] | None = None, filter_obj: dict[str, Any] | None = None) -> dict[str, Any]:
    args = [
        "ce",
        "get-cost-and-usage",
        "--time-period",
        f"Start={START},End={END}",
        "--granularity",
        granularity,
        "--metrics",
        "UnblendedCost",
    ]
    if group_by:
        args.append("--group-by")
        for type_, key in group_by:
            args.extend([f"Type={type_},Key={key}"])
    if filter_obj:
        args.extend(["--filter", json.dumps(filter_obj, separators=(",", ":"))])
    data, record = run_aws(args)
    write_json(RAW / f"{name}.json", data)
    command_records.append({**record, "artifact": str(RAW / f"{name}.json")})
    return data


def flatten_ce(name: str, payload: dict[str, Any], group_fields: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for period in payload.get("ResultsByTime", []):
        start = period["TimePeriod"]["Start"]
        end = period["TimePeriod"]["End"]
        if period.get("Groups"):
            for group in period["Groups"]:
                row = {
                    "time_start": start,
                    "time_end": end,
                    "estimated": period.get("Estimated", False),
                    "amount_usd": amount(group),
                }
                for idx, field in enumerate(group_fields):
                    row[field] = group["Keys"][idx] if idx < len(group["Keys"]) else ""
                    if field.startswith("tag_"):
                        row[f"{field}_value"] = group_key_value(row[field])
                rows.append(row)
        else:
            total = period.get("Total", {}).get("UnblendedCost", {}).get("Amount", "0")
            rows.append(
                {
                    "time_start": start,
                    "time_end": end,
                    "estimated": period.get("Estimated", False),
                    "amount_usd": float(total),
                }
            )
    write_csv(DATA / f"{name}.csv", rows)
    return rows


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("")
        return
    keys: list[str] = []
    for row in rows:
        for key in row.keys():
            if key not in keys:
                keys.append(key)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)


def tags_to_dict(tags: Any) -> dict[str, str]:
    out: dict[str, str] = {}
    for tag in tags or []:
        key = tag.get("Key") or tag.get("key")
        val = tag.get("Value") or tag.get("value") or ""
        if key:
            out[key] = val
    return out


def tags_text(tags: dict[str, str]) -> str:
    return " ".join(f"{k}={v}" for k, v in sorted(tags.items()))


def resource_text(resource: dict[str, Any]) -> str:
    parts = [
        resource.get("service", ""),
        resource.get("kind", ""),
        resource.get("region", ""),
        resource.get("id", ""),
        resource.get("arn", ""),
        resource.get("name", ""),
        tags_text(resource.get("tags", {})),
    ]
    return " ".join(str(part) for part in parts if part)


def classify_text(text: str, tags: dict[str, str] | None = None) -> str:
    tags = tags or {}
    for key in DYEC_TAG_KEYS:
        if tags.get(key):
            return "dyec_cluster"
    lower = text.lower()
    if any(k in lower for k in ["parallelcluster", "aws-parallelcluster-clustername", "aws-parallelcluster-project"]):
        if any(v for k, v in tags.items() if k.startswith("aws-parallelcluster") or k == "parallelcluster:cluster-name"):
            return "dyec_cluster"
    for app, pattern in APP_PATTERNS.items():
        if pattern.search(text):
            return app
    return "unallocated"


def add_resource(resources: list[dict[str, Any]], service: str, kind: str, region: str, resource_id: str, arn: str = "", name: str = "", tags: dict[str, str] | None = None, raw: dict[str, Any] | None = None) -> None:
    tags = tags or {}
    resource = {
        "service": service,
        "kind": kind,
        "region": region,
        "id": resource_id,
        "arn": arn,
        "name": name,
        "tags": tags,
    }
    if raw:
        for key in ("State", "Size", "VolumeType", "InstanceType", "DBInstanceClass", "Engine", "StorageCapacity", "LifeCycle", "Status"):
            if key in raw:
                resource[key] = raw[key]
    resource["classification"] = classify_text(resource_text(resource), tags)
    resources.append(resource)


def inventory_region(region: str, resources: list[dict[str, Any]]) -> None:
    data, rec = run_aws(["ec2", "describe-instances"], region=region, allow_error=True)
    command_records.append(rec)
    if data:
        for reservation in data.get("Reservations", []):
            for inst in reservation.get("Instances", []):
                tags = tags_to_dict(inst.get("Tags"))
                add_resource(
                    resources,
                    "EC2",
                    "ec2_instance",
                    region,
                    inst["InstanceId"],
                    arn=f"arn:aws:ec2:{region}:{ACCOUNT_ID}:instance/{inst['InstanceId']}",
                    name=tags.get("Name", ""),
                    tags=tags,
                    raw={"State": inst.get("State", {}).get("Name", ""), "InstanceType": inst.get("InstanceType", "")},
                )

    data, rec = run_aws(["ec2", "describe-volumes"], region=region, allow_error=True)
    command_records.append(rec)
    if data:
        for vol in data.get("Volumes", []):
            tags = tags_to_dict(vol.get("Tags"))
            add_resource(
                resources,
                "EBS",
                "ebs_volume",
                region,
                vol["VolumeId"],
                arn=f"arn:aws:ec2:{region}:{ACCOUNT_ID}:volume/{vol['VolumeId']}",
                name=tags.get("Name", ""),
                tags=tags,
                raw={"State": vol.get("State", ""), "Size": vol.get("Size", ""), "VolumeType": vol.get("VolumeType", "")},
            )

    data, rec = run_aws(["ec2", "describe-addresses"], region=region, allow_error=True)
    command_records.append(rec)
    if data:
        for addr in data.get("Addresses", []):
            tags = tags_to_dict(addr.get("Tags"))
            rid = addr.get("AllocationId") or addr.get("PublicIp", "")
            add_resource(resources, "EC2", "eip", region, rid, name=tags.get("Name", ""), tags=tags)

    data, rec = run_aws(["ec2", "describe-nat-gateways"], region=region, allow_error=True)
    command_records.append(rec)
    if data:
        for nat in data.get("NatGateways", []):
            tags = tags_to_dict(nat.get("Tags"))
            add_resource(
                resources,
                "VPC",
                "nat_gateway",
                region,
                nat["NatGatewayId"],
                arn=f"arn:aws:ec2:{region}:{ACCOUNT_ID}:natgateway/{nat['NatGatewayId']}",
                name=tags.get("Name", ""),
                tags=tags,
                raw={"State": nat.get("State", "")},
            )

    data, rec = run_aws(["fsx", "describe-file-systems"], region=region, allow_error=True)
    command_records.append(rec)
    if data:
        for fs in data.get("FileSystems", []):
            tags = tags_to_dict(fs.get("Tags"))
            add_resource(
                resources,
                "FSx",
                "fsx_file_system",
                region,
                fs["FileSystemId"],
                arn=fs.get("ResourceARN", ""),
                name=tags.get("Name", ""),
                tags=tags,
                raw={"LifeCycle": fs.get("Lifecycle", ""), "StorageCapacity": fs.get("StorageCapacity", "")},
            )

    data, rec = run_aws(["fsx", "describe-data-repository-associations"], region=region, allow_error=True)
    command_records.append(rec)
    if data:
        for dra in data.get("Associations", []):
            tags = tags_to_dict(dra.get("Tags"))
            add_resource(
                resources,
                "FSx",
                "fsx_dra",
                region,
                dra["AssociationId"],
                arn=dra.get("ResourceARN", ""),
                name=tags.get("Name", ""),
                tags=tags,
                raw={"LifeCycle": dra.get("Lifecycle", "")},
            )

    data, rec = run_aws(["rds", "describe-db-instances"], region=region, allow_error=True)
    command_records.append(rec)
    if data:
        for db in data.get("DBInstances", []):
            arn = db.get("DBInstanceArn", "")
            tag_data, tag_rec = run_aws(["rds", "list-tags-for-resource", "--resource-name", arn], region=region, allow_error=True)
            command_records.append(tag_rec)
            tags = tags_to_dict((tag_data or {}).get("TagList"))
            add_resource(
                resources,
                "RDS",
                "rds_instance",
                region,
                db["DBInstanceIdentifier"],
                arn=arn,
                name=tags.get("Name", db["DBInstanceIdentifier"]),
                tags=tags,
                raw={"Status": db.get("DBInstanceStatus", ""), "DBInstanceClass": db.get("DBInstanceClass", ""), "Engine": db.get("Engine", "")},
            )

    data, rec = run_aws(["rds", "describe-db-clusters"], region=region, allow_error=True)
    command_records.append(rec)
    if data:
        for dbc in data.get("DBClusters", []):
            arn = dbc.get("DBClusterArn", "")
            tag_data, tag_rec = run_aws(["rds", "list-tags-for-resource", "--resource-name", arn], region=region, allow_error=True)
            command_records.append(tag_rec)
            tags = tags_to_dict((tag_data or {}).get("TagList"))
            add_resource(
                resources,
                "RDS",
                "rds_cluster",
                region,
                dbc["DBClusterIdentifier"],
                arn=arn,
                name=tags.get("Name", dbc["DBClusterIdentifier"]),
                tags=tags,
                raw={"Status": dbc.get("Status", ""), "Engine": dbc.get("Engine", "")},
            )

    data, rec = run_aws(["elbv2", "describe-load-balancers"], region=region, allow_error=True)
    command_records.append(rec)
    lbs = (data or {}).get("LoadBalancers", []) if data else []
    for lb in lbs:
        arn = lb.get("LoadBalancerArn", "")
        tag_data, tag_rec = run_aws(["elbv2", "describe-tags", "--resource-arns", arn], region=region, allow_error=True)
        command_records.append(tag_rec)
        tag_descs = (tag_data or {}).get("TagDescriptions", [])
        tags = tags_to_dict(tag_descs[0].get("Tags") if tag_descs else [])
        add_resource(resources, "ELBv2", "load_balancer", region, lb.get("LoadBalancerName", ""), arn=arn, name=lb.get("LoadBalancerName", ""), tags=tags)

    data, rec = run_aws(["ecs", "list-clusters"], region=region, allow_error=True)
    command_records.append(rec)
    cluster_arns = (data or {}).get("clusterArns", []) if data else []
    if cluster_arns:
        data, rec = run_aws(["ecs", "describe-clusters", "--clusters", *cluster_arns, "--include", "TAGS"], region=region, allow_error=True)
        command_records.append(rec)
        for cluster in (data or {}).get("clusters", []):
            tags = tags_to_dict(cluster.get("tags"))
            name = cluster.get("clusterName", "")
            add_resource(resources, "ECS", "ecs_cluster", region, name, arn=cluster.get("clusterArn", ""), name=name, tags=tags)
            svc_data, svc_rec = run_aws(["ecs", "list-services", "--cluster", cluster.get("clusterArn", "")], region=region, allow_error=True)
            command_records.append(svc_rec)
            service_arns = (svc_data or {}).get("serviceArns", []) if svc_data else []
            for idx in range(0, len(service_arns), 10):
                chunk = service_arns[idx : idx + 10]
                desc, desc_rec = run_aws(["ecs", "describe-services", "--cluster", cluster.get("clusterArn", ""), "--services", *chunk, "--include", "TAGS"], region=region, allow_error=True)
                command_records.append(desc_rec)
                for svc in (desc or {}).get("services", []):
                    tags = tags_to_dict(svc.get("tags"))
                    name = svc.get("serviceName", "")
                    add_resource(resources, "ECS", "ecs_service", region, name, arn=svc.get("serviceArn", ""), name=name, tags=tags)


def inventory_s3(resources: list[dict[str, Any]]) -> None:
    data, rec = run_aws(["s3api", "list-buckets"], allow_error=True)
    command_records.append(rec)
    for bucket in (data or {}).get("Buckets", []) if data else []:
        name = bucket["Name"]
        tag_data, tag_rec = run_aws(["s3api", "get-bucket-tagging", "--bucket", name], allow_error=True)
        command_records.append(tag_rec)
        tags = tags_to_dict((tag_data or {}).get("TagSet")) if tag_data else {}
        lifecycle_data, life_rec = run_aws(["s3api", "get-bucket-lifecycle-configuration", "--bucket", name], allow_error=True)
        command_records.append(life_rec)
        resource = {
            "service": "S3",
            "kind": "s3_bucket",
            "region": "",
            "id": name,
            "arn": f"arn:aws:s3:::{name}",
            "name": name,
            "tags": tags,
            "has_lifecycle": bool(lifecycle_data and lifecycle_data.get("Rules")),
        }
        resource["classification"] = classify_text(resource_text(resource), tags)
        resources.append(resource)


def sum_rows(rows: list[dict[str, Any]], **filters: Any) -> float:
    total = 0.0
    for row in rows:
        ok = True
        for key, value in filters.items():
            if callable(value):
                ok = bool(value(row.get(key, "")))
            elif row.get(key) != value:
                ok = False
            if not ok:
                break
        if ok:
            total += float(row.get("amount_usd", 0) or 0)
    return total


def by_field(rows: list[dict[str, Any]], field: str, n: int = 10) -> list[dict[str, Any]]:
    agg: dict[str, float] = defaultdict(float)
    for row in rows:
        agg[str(row.get(field, ""))] += float(row.get("amount_usd", 0) or 0)
    return [{"name": key or "blank", "amount_usd": round(val, 2)} for key, val in sorted(agg.items(), key=lambda kv: kv[1], reverse=True)[:n]]


def make_bar_svg(path: Path, title: str, rows: list[dict[str, Any]], name_field: str = "name", value_field: str = "amount_usd") -> None:
    rows = rows[:12]
    width = 980
    left = 260
    bar_max = 620
    row_h = 34
    height = 80 + row_h * max(len(rows), 1)
    max_val = max([float(r[value_field]) for r in rows] + [1.0])
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        f'<text x="24" y="36" font-family="Arial, sans-serif" font-size="22" font-weight="700" fill="#17212b">{escape(title)}</text>',
    ]
    for idx, row in enumerate(rows):
        y = 64 + idx * row_h
        val = float(row[value_field])
        label = str(row[name_field])
        bar_w = max(1, int(bar_max * val / max_val))
        parts.append(f'<text x="24" y="{y+18}" font-family="Arial, sans-serif" font-size="14" fill="#17212b">{escape(label[:42])}</text>')
        parts.append(f'<rect x="{left}" y="{y}" width="{bar_w}" height="20" rx="3" fill="#1f5f99"/>')
        parts.append(f'<text x="{left + bar_w + 8}" y="{y+16}" font-family="Arial, sans-serif" font-size="13" fill="#334155">${val:,.2f}</text>')
    parts.append("</svg>")
    path.write_text("\n".join(parts) + "\n")


def make_line_svg(path: Path, title: str, rows: list[dict[str, Any]]) -> None:
    width = 980
    height = 300
    pad_l = 70
    pad_r = 30
    pad_t = 60
    pad_b = 45
    vals = [float(r["amount_usd"]) for r in rows]
    max_val = max(vals + [1.0])
    min_val = min(vals + [0.0])
    span = max_val - min_val or 1.0
    points = []
    for idx, row in enumerate(rows):
        x = pad_l + idx * ((width - pad_l - pad_r) / max(len(rows) - 1, 1))
        y = pad_t + (max_val - float(row["amount_usd"])) * ((height - pad_t - pad_b) / span)
        points.append((x, y))
    poly = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        f'<text x="24" y="36" font-family="Arial, sans-serif" font-size="22" font-weight="700" fill="#17212b">{escape(title)}</text>',
        f'<line x1="{pad_l}" y1="{height-pad_b}" x2="{width-pad_r}" y2="{height-pad_b}" stroke="#cbd5e1"/>',
        f'<line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{height-pad_b}" stroke="#cbd5e1"/>',
        f'<polyline fill="none" stroke="#1c7f72" stroke-width="3" points="{poly}"/>',
        f'<text x="24" y="{pad_t+8}" font-family="Arial, sans-serif" font-size="12" fill="#475569">${max_val:,.0f}</text>',
        f'<text x="24" y="{height-pad_b}" font-family="Arial, sans-serif" font-size="12" fill="#475569">${min_val:,.0f}</text>',
    ]
    if rows:
        parts.append(f'<text x="{pad_l}" y="{height-18}" font-family="Arial, sans-serif" font-size="12" fill="#475569">{escape(rows[0]["time_start"])}</text>')
        parts.append(f'<text x="{width-160}" y="{height-18}" font-family="Arial, sans-serif" font-size="12" fill="#475569">{escape(rows[-1]["time_start"])}</text>')
    parts.append("</svg>")
    path.write_text("\n".join(parts) + "\n")


def table(rows: list[dict[str, Any]], columns: list[tuple[str, str]], max_rows: int | None = None) -> str:
    selected = rows[:max_rows] if max_rows else rows
    lines = ["| " + " | ".join(label for label, _ in columns) + " |", "| " + " | ".join("---" for _ in columns) + " |"]
    for row in selected:
        vals = []
        for _, key in columns:
            val = row.get(key, "")
            if isinstance(val, float):
                vals.append(f"${val:,.2f}")
            else:
                vals.append(str(val))
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines)


def fmt_usd(value: float) -> str:
    return f"${value:,.2f}"


def write_report(summary: dict[str, Any]) -> None:
    total = summary["total_cost"]
    top_services = summary["top_services"]
    top_regions = summary["top_regions"]
    monthly = summary["monthly_totals"]
    category = summary["category_surfaces"]
    recent = summary["recent_resource_costs_by_class"]
    recent_by_service = summary["recent_resource_costs_by_class_service"]
    live_counts = summary["live_resource_counts_by_class"]
    rds_usage = summary["rds_usage_type_breakdown"]
    pc_services = summary["dyec_cluster_service_breakdown"]
    dayhoff_services = summary["dayhoff_lsmc_project_service_breakdown"]
    unallocated_note = summary["attribution_limits"]

    report = f"""# AWS 90-Day Cost Attribution Report

Generated: {GENERATED_AT}
AWS profile: `{PROFILE}`
Account: `{ACCOUNT_ID}`
Window: {START} through 2026-06-13 inclusive (`Cost Explorer End={END}`)
Metric: `UnblendedCost`

No AWS mutations were performed. Tagging, stopping, deleting, lifecycle changes, rightsizing, and cleanup actions below are findings or recommendations only.

## Executive Summary

The account spent **{fmt_usd(total)}** in the last complete 90 billing days. The top services remain concentrated in EC2 compute, FSx, S3, EC2-Other, and RDS/Aurora.

{table(top_services, [("Service", "name"), ("90-day spend", "amount_usd")], 8)}

{table(top_regions, [("Region", "name"), ("90-day spend", "amount_usd")], 8)}

## Overview Plots

![Daily spend](aws_90day_cost_attribution_20260614T213521Z_assets/images/daily_spend.svg)

![Top services](aws_90day_cost_attribution_20260614T213521Z_assets/images/top_services.svg)

![Top regions](aws_90day_cost_attribution_20260614T213521Z_assets/images/top_regions.svg)

![Attribution surfaces](aws_90day_cost_attribution_20260614T213521Z_assets/images/attribution_surfaces.svg)

## Time Trend

{table(monthly, [("Period", "name"), ("Spend", "amount_usd")])}

## Attribution Surfaces

These surfaces are not all mutually exclusive. They are separated by evidence type because the historical billing tags do not cover every app stack.

{table(category, [("Surface", "surface"), ("Evidence", "evidence"), ("90-day spend", "amount_usd"), ("Confidence", "confidence")])}

### DYEC / ParallelCluster

The strongest DYEC historical view is the nonblank `parallelcluster:cluster-name` Cost Explorer tag. It attributes **{fmt_usd(summary["dyec_cluster_tagged_total"])}** over the window. The service mix under that tag is:

{table(pc_services, [("Service", "name"), ("DYEC cluster-tagged spend", "amount_usd")], 12)}

Top cluster-name values:

{table(summary["top_dyec_clusters"], [("Cluster tag value", "name"), ("90-day spend", "amount_usd")], 15)}

### Dayhoff / TapDB

The strongest historical Dayhoff view is the nonblank `lsmc-project` values beginning with `dayhoff` plus `tapdb` values. That tag surface attributes **{fmt_usd(summary["dayhoff_lsmc_project_total"])}**. The generic `project=dayhoff-all` tag separately attributes **{fmt_usd(summary["dayhoff_project_total"])}** and may overlap with the `lsmc-project` view, so it is not added to it.

{table(dayhoff_services, [("Service", "name"), ("Dayhoff/TapDB lsmc-project spend", "amount_usd")], 12)}

Top `lsmc-project` values in the Dayhoff/TapDB family:

{table(summary["top_dayhoff_lsmc_projects"], [("lsmc-project value", "name"), ("90-day spend", "amount_usd")], 15)}

### Aurora / RDS

The full RDS/Aurora service cost is **{fmt_usd(summary["rds_total"])}**. The apparent instance-class compute subset from RDS usage types is **{fmt_usd(summary["rds_compute_subset"])}**; storage, I/O, backup, and other RDS/Aurora usage remain outside that subset.

{table(rds_usage, [("RDS usage type", "name"), ("90-day spend", "amount_usd")], 15)}

Live Aurora/RDS resources by classification:

{table(summary["live_rds_by_class"], [("Class", "name"), ("Live RDS/Aurora resources", "count")])}

### Terrarium And Aquarium

Terrarium and Aquarium do not appear in the active Cost Explorer tag keys for this window. Their exact 90-day historical spend cannot be separated from Cost Explorer tags without adding/activating billing tags before the spend occurs.

Recent resource-level Cost Explorer data for {RECENT_START} through 2026-06-13 provides a partial actual-spend signal:

{table(recent, [("Class", "name"), ("Recent resource-level spend", "amount_usd"), ("30.4-day run-rate", "monthly_run_rate_usd")])}

Recent resource-level split by class and service:

{table(recent_by_service, [("Class", "classification"), ("Service", "service"), ("Recent spend", "amount_usd"), ("30.4-day run-rate", "monthly_run_rate_usd")], 20)}

Live resource counts by classification:

{table(live_counts, [("Class", "name"), ("Live resources", "count")])}

## Attribution Limits

{unallocated_note}

## Evidence And Artifacts

Raw Cost Explorer JSON:

- `docs/aws_90day_cost_attribution_20260614T213521Z_assets/raw/ce_total_daily.json`
- `docs/aws_90day_cost_attribution_20260614T213521Z_assets/raw/ce_service_daily.json`
- `docs/aws_90day_cost_attribution_20260614T213521Z_assets/raw/ce_service_monthly.json`
- `docs/aws_90day_cost_attribution_20260614T213521Z_assets/raw/ce_region_monthly.json`
- `docs/aws_90day_cost_attribution_20260614T213521Z_assets/raw/ce_usage_type_monthly.json`
- `docs/aws_90day_cost_attribution_20260614T213521Z_assets/raw/ce_service_usage_monthly.json`
- `docs/aws_90day_cost_attribution_20260614T213521Z_assets/raw/ce_service_tag_*.json`
- `docs/aws_90day_cost_attribution_20260614T213521Z_assets/raw/ce_resource_*.json`

Derived data:

- `docs/aws_90day_cost_attribution_20260614T213521Z_assets/data/summary.json`
- `docs/aws_90day_cost_attribution_20260614T213521Z_assets/data/live_resources.json`
- `docs/aws_90day_cost_attribution_20260614T213521Z_assets/data/live_resources.csv`
- `docs/aws_90day_cost_attribution_20260614T213521Z_assets/data/recent_resource_costs.csv`
- `docs/aws_90day_cost_attribution_20260614T213521Z_assets/data/command_records.json`

Collector command status:

- Total AWS command records: {summary["command_count"]}
- Nonzero command records: {summary["command_error_count"]}
- Expected S3 metadata misses: {summary["expected_s3_no_lifecycle_count"]} `NoSuchLifecycleConfiguration`, {summary["expected_s3_no_tag_set_count"]} `NoSuchTagSet`
- Unexpected command errors after filtering expected S3 metadata misses: {summary["unexpected_command_error_count"]}

## Reproducibility

The collector is preserved at `docs/aws_90day_cost_attribution_20260614T213521Z_assets/scripts/collect_aws_90day_cost_attribution.py`. Rerun from the repo root with:

```bash
AWS_PROFILE=lsmc AWS_DEFAULT_REGION=us-west-2 python3 docs/aws_90day_cost_attribution_20260614T213521Z_assets/scripts/collect_aws_90day_cost_attribution.py
```
"""
    REPORT.write_text(report)


command_records: list[dict[str, Any]] = []


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    DATA.mkdir(parents=True, exist_ok=True)
    IMAGES.mkdir(parents=True, exist_ok=True)

    total_daily = flatten_ce("ce_total_daily", ce_query("ce_total_daily", "DAILY"), [])
    service_daily = flatten_ce("ce_service_daily", ce_query("ce_service_daily", "DAILY", [("DIMENSION", "SERVICE")]), ["service"])
    service_monthly = flatten_ce("ce_service_monthly", ce_query("ce_service_monthly", "MONTHLY", [("DIMENSION", "SERVICE")]), ["service"])
    region_monthly = flatten_ce("ce_region_monthly", ce_query("ce_region_monthly", "MONTHLY", [("DIMENSION", "REGION")]), ["region"])
    usage_type_monthly = flatten_ce("ce_usage_type_monthly", ce_query("ce_usage_type_monthly", "MONTHLY", [("DIMENSION", "USAGE_TYPE")]), ["usage_type"])
    operation_monthly = flatten_ce("ce_operation_monthly", ce_query("ce_operation_monthly", "MONTHLY", [("DIMENSION", "OPERATION")]), ["operation"])
    service_usage_monthly = flatten_ce("ce_service_usage_monthly", ce_query("ce_service_usage_monthly", "MONTHLY", [("DIMENSION", "SERVICE"), ("DIMENSION", "USAGE_TYPE")]), ["service", "usage_type"])
    service_operation_monthly = flatten_ce("ce_service_operation_monthly", ce_query("ce_service_operation_monthly", "MONTHLY", [("DIMENSION", "SERVICE"), ("DIMENSION", "OPERATION")]), ["service", "operation"])

    tag_rows: dict[str, list[dict[str, Any]]] = {}
    service_tag_rows: dict[str, list[dict[str, Any]]] = {}
    tag_values: dict[str, Any] = {}
    for tag in TAG_KEYS:
        safe = tag.replace(":", "_").replace("-", "_")
        vals, rec = run_aws(["ce", "get-tags", "--time-period", f"Start={START},End={END}", "--tag-key", tag])
        command_records.append(rec)
        tag_values[tag] = vals
        write_json(RAW / f"ce_get_tags_{safe}.json", vals)
        tag_rows[tag] = flatten_ce(f"ce_tag_{safe}_monthly", ce_query(f"ce_tag_{safe}_monthly", "MONTHLY", [("TAG", tag)]), [f"tag_{safe}"])
        service_tag_rows[tag] = flatten_ce(f"ce_service_tag_{safe}_monthly", ce_query(f"ce_service_tag_{safe}_monthly", "MONTHLY", [("DIMENSION", "SERVICE"), ("TAG", tag)]), ["service", f"tag_{safe}"])

    resource_cost_rows: list[dict[str, Any]] = []
    resource_cost_errors: list[dict[str, Any]] = []
    for service in RESOURCE_COST_SERVICES:
        safe = re.sub(r"[^A-Za-z0-9]+", "_", service).strip("_").lower()
        payload, rec = run_aws(
            [
                "ce",
                "get-cost-and-usage-with-resources",
                "--time-period",
                f"Start={RECENT_START},End={RECENT_END}",
                "--granularity",
                "DAILY",
                "--metrics",
                "UnblendedCost",
                "--filter",
                json.dumps({"Dimensions": {"Key": "SERVICE", "Values": [service]}}, separators=(",", ":")),
                "--group-by",
                "Type=DIMENSION,Key=RESOURCE_ID",
            ],
            allow_error=True,
        )
        command_records.append({**rec, "artifact": str(RAW / f"ce_resource_{safe}.json")})
        if payload:
            write_json(RAW / f"ce_resource_{safe}.json", payload)
            rows = flatten_ce(f"ce_resource_{safe}", payload, ["resource_id"])
            for row in rows:
                row["service"] = service
                row["classification"] = classify_text(str(row.get("resource_id", "")))
                resource_cost_rows.append(row)
        else:
            resource_cost_errors.append({**rec, "service": service})
    write_csv(DATA / "recent_resource_costs.csv", resource_cost_rows)
    write_json(DATA / "resource_cost_errors.json", resource_cost_errors)

    resources: list[dict[str, Any]] = []
    for region in REGIONS:
        inventory_region(region, resources)
    inventory_s3(resources)
    write_json(DATA / "live_resources.json", resources)
    flat_resources = []
    for resource in resources:
        flat_resources.append(
            {
                "service": resource.get("service", ""),
                "kind": resource.get("kind", ""),
                "region": resource.get("region", ""),
                "id": resource.get("id", ""),
                "arn": resource.get("arn", ""),
                "name": resource.get("name", ""),
                "classification": resource.get("classification", ""),
                "tags": tags_text(resource.get("tags", {})),
                "state": resource.get("State", resource.get("Status", resource.get("LifeCycle", ""))),
                "size": resource.get("Size", resource.get("StorageCapacity", "")),
                "type": resource.get("InstanceType", resource.get("DBInstanceClass", resource.get("VolumeType", ""))),
                "engine": resource.get("Engine", ""),
                "has_lifecycle": resource.get("has_lifecycle", ""),
            }
        )
    write_csv(DATA / "live_resources.csv", flat_resources)
    write_json(DATA / "command_records.json", command_records)

    live_index_text = defaultdict(list)
    for resource in resources:
        live_index_text[resource["classification"]].append(resource_text(resource))

    # Reclassify recent resource costs using live inventory text when possible.
    for row in resource_cost_rows:
        rid = str(row.get("resource_id", ""))
        text = rid
        for resource in resources:
            if resource.get("id") and resource["id"] in rid:
                text += " " + resource_text(resource)
            elif resource.get("arn") and resource["arn"] in rid:
                text += " " + resource_text(resource)
        row["classification"] = classify_text(text)
    write_csv(DATA / "recent_resource_costs.csv", resource_cost_rows)

    total_cost = round(sum(float(r["amount_usd"]) for r in total_daily), 2)
    top_services = by_field(service_monthly, "service", 15)
    top_regions = by_field(region_monthly, "region", 12)
    monthly_total_rows = flatten_ce("ce_total_monthly", ce_query("ce_total_monthly", "MONTHLY"), [])
    monthly_totals = [
        {"name": row["time_start"], "amount_usd": round(float(row["amount_usd"]), 2)}
        for row in sorted(monthly_total_rows, key=lambda r: r["time_start"])
    ]

    pc_tag = "parallelcluster:cluster-name"
    pc_safe = pc_tag.replace(":", "_").replace("-", "_")
    pc_value_field = f"tag_{pc_safe}_value"
    dyec_cluster_tagged_total = round(sum_rows(tag_rows[pc_tag], **{pc_value_field: lambda v: bool(v)}), 2)
    dyec_cluster_service_rows = service_tag_rows[pc_tag]
    dyec_cluster_service_breakdown = by_field(
        [r for r in dyec_cluster_service_rows if r.get(pc_value_field)],
        "service",
        15,
    )
    top_dyec_clusters = by_field([r for r in tag_rows[pc_tag] if r.get(pc_value_field)], pc_value_field, 20)
    dyec_ec2_compute = round(sum_rows(dyec_cluster_service_rows, service="Amazon Elastic Compute Cloud - Compute", **{pc_value_field: lambda v: bool(v)}), 2)
    dyec_fsx = round(sum_rows(dyec_cluster_service_rows, service="Amazon FSx", **{pc_value_field: lambda v: bool(v)}), 2)

    lsmc_tag = "lsmc-project"
    lsmc_safe = lsmc_tag.replace(":", "_").replace("-", "_")
    lsmc_value_field = f"tag_{lsmc_safe}_value"
    dayhoff_pred = lambda v: bool(re.search(r"^(dayhoff|tapdb)", str(v), re.I))
    dayhoff_lsmc_project_total = round(sum_rows(tag_rows[lsmc_tag], **{lsmc_value_field: dayhoff_pred}), 2)
    dayhoff_lsmc_project_service_breakdown = by_field([r for r in service_tag_rows[lsmc_tag] if dayhoff_pred(r.get(lsmc_value_field, ""))], "service", 15)
    top_dayhoff_lsmc_projects = by_field([r for r in tag_rows[lsmc_tag] if dayhoff_pred(r.get(lsmc_value_field, ""))], lsmc_value_field, 20)

    project_tag = "project"
    project_safe = project_tag.replace(":", "_").replace("-", "_")
    project_value_field = f"tag_{project_safe}_value"
    dayhoff_project_total = round(sum_rows(tag_rows[project_tag], **{project_value_field: lambda v: v == "dayhoff-all"}), 2)

    rds_total = round(sum_rows(service_monthly, service="Amazon Relational Database Service"), 2)
    rds_usage_rows = [r for r in service_usage_monthly if r.get("service") == "Amazon Relational Database Service"]
    rds_usage_type_breakdown = by_field(rds_usage_rows, "usage_type", 20)
    rds_compute_subset = round(
        sum(
            float(r["amount_usd"])
            for r in rds_usage_rows
            if re.search(r"InstanceUsage|BoxUsage|Multi-AZUsage|CPUCredits", r.get("usage_type", ""), re.I)
        ),
        2,
    )

    recent_by_class: dict[str, dict[str, float]] = defaultdict(lambda: {"amount_usd": 0.0})
    recent_by_class_service: dict[tuple[str, str], float] = defaultdict(float)
    for row in resource_cost_rows:
        cls = row.get("classification", "unallocated")
        if row.get("service") in COMPUTE_SERVICES:
            recent_by_class[cls]["amount_usd"] += float(row.get("amount_usd", 0) or 0)
            recent_by_class_service[(cls, row.get("service", ""))] += float(row.get("amount_usd", 0) or 0)
    days = (dt.date.fromisoformat(RECENT_END) - dt.date.fromisoformat(RECENT_START)).days
    recent_resource_costs_by_class = []
    for cls, values in sorted(recent_by_class.items(), key=lambda kv: kv[1]["amount_usd"], reverse=True):
        amt = round(values["amount_usd"], 2)
        recent_resource_costs_by_class.append({"name": cls, "amount_usd": amt, "monthly_run_rate_usd": round(amt / max(days, 1) * 30.4375, 2)})
    recent_resource_costs_by_class_service = []
    for (cls, service), amt_raw in sorted(recent_by_class_service.items(), key=lambda kv: kv[1], reverse=True):
        amt = round(amt_raw, 2)
        if amt <= 0:
            continue
        recent_resource_costs_by_class_service.append(
            {
                "classification": cls,
                "service": service,
                "amount_usd": amt,
                "monthly_run_rate_usd": round(amt / max(days, 1) * 30.4375, 2),
            }
        )

    live_counts_by_class_agg: dict[str, int] = defaultdict(int)
    for resource in resources:
        live_counts_by_class_agg[resource["classification"]] += 1
    live_resource_counts_by_class = [{"name": cls, "count": count} for cls, count in sorted(live_counts_by_class_agg.items(), key=lambda kv: kv[1], reverse=True)]

    live_rds_by_class_agg: dict[str, int] = defaultdict(int)
    for resource in resources:
        if resource.get("service") == "RDS":
            live_rds_by_class_agg[resource["classification"]] += 1
    live_rds_by_class = [{"name": cls, "count": count} for cls, count in sorted(live_rds_by_class_agg.items(), key=lambda kv: kv[1], reverse=True)]

    category_surfaces = [
        {
            "surface": "DYEC cluster-name tagged",
            "evidence": "`parallelcluster:cluster-name` nonblank",
            "amount_usd": dyec_cluster_tagged_total,
            "confidence": "high for tagged cluster resources",
        },
        {
            "surface": "DYEC EC2 compute subset",
            "evidence": "service=EC2 Compute + nonblank cluster-name tag",
            "amount_usd": dyec_ec2_compute,
            "confidence": "high for tagged EC2 compute",
        },
        {
            "surface": "DYEC FSx subset",
            "evidence": "service=Amazon FSx + nonblank cluster-name tag",
            "amount_usd": dyec_fsx,
            "confidence": "high for tagged FSx",
        },
        {
            "surface": "Dayhoff/TapDB lsmc-project tagged",
            "evidence": "`lsmc-project` starts dayhoff/tapdb",
            "amount_usd": dayhoff_lsmc_project_total,
            "confidence": "high for resources carrying lsmc-project",
        },
        {
            "surface": "Dayhoff project tag",
            "evidence": "`project=dayhoff-all`",
            "amount_usd": dayhoff_project_total,
            "confidence": "separate tag surface; may overlap",
        },
        {
            "surface": "Aurora/RDS service total",
            "evidence": "service=Amazon Relational Database Service",
            "amount_usd": rds_total,
            "confidence": "high service total, not app-specific",
        },
        {
            "surface": "Aurora/RDS instance compute subset",
            "evidence": "RDS usage types matching instance/box/multi-AZ/CPU credit",
            "amount_usd": rds_compute_subset,
            "confidence": "usage-type heuristic",
        },
    ]

    attribution_limits = (
        "Cost Explorer active tag keys for this window were limited to ParallelCluster/project tags. "
        "`Name`, CloudFormation stack-name, ECS service, and RDS identifier were not active historical cost allocation tags. "
        "Therefore DYEC and Dayhoff/TapDB are separated with historical tag evidence where tags exist, while Terrarium and Aquarium are separated only in live inventory and recent resource-level Cost Explorer data. "
        "Unclassified or blank-tag spend remains unallocated rather than inferred."
    )

    expected_s3_no_lifecycle_count = 0
    expected_s3_no_tag_set_count = 0
    unexpected_command_errors = []
    for record in command_records:
        if not record.get("returncode"):
            continue
        stderr = record.get("stderr", "")
        if "NoSuchLifecycleConfiguration" in stderr:
            expected_s3_no_lifecycle_count += 1
        elif "NoSuchTagSet" in stderr:
            expected_s3_no_tag_set_count += 1
        else:
            unexpected_command_errors.append(record)

    summary = {
        "generated_at": GENERATED_AT,
        "profile": PROFILE,
        "account_id": ACCOUNT_ID,
        "window": {"start": START, "end_exclusive": END, "last_inclusive_day": "2026-06-13"},
        "recent_resource_window": {"start": RECENT_START, "end_exclusive": RECENT_END, "days": days},
        "total_cost": total_cost,
        "top_services": top_services,
        "top_regions": top_regions,
        "monthly_totals": monthly_totals,
        "category_surfaces": category_surfaces,
        "dyec_cluster_tagged_total": dyec_cluster_tagged_total,
        "dyec_cluster_service_breakdown": dyec_cluster_service_breakdown,
        "top_dyec_clusters": top_dyec_clusters,
        "dyec_ec2_compute": dyec_ec2_compute,
        "dyec_fsx": dyec_fsx,
        "dayhoff_lsmc_project_total": dayhoff_lsmc_project_total,
        "dayhoff_project_total": dayhoff_project_total,
        "dayhoff_lsmc_project_service_breakdown": dayhoff_lsmc_project_service_breakdown,
        "top_dayhoff_lsmc_projects": top_dayhoff_lsmc_projects,
        "rds_total": rds_total,
        "rds_compute_subset": rds_compute_subset,
        "rds_usage_type_breakdown": rds_usage_type_breakdown,
        "recent_resource_costs_by_class": recent_resource_costs_by_class,
        "recent_resource_costs_by_class_service": recent_resource_costs_by_class_service,
        "live_resource_counts_by_class": live_resource_counts_by_class,
        "live_rds_by_class": live_rds_by_class,
        "resource_count": len(resources),
        "command_count": len(command_records),
        "command_error_count": sum(1 for r in command_records if r.get("returncode")),
        "expected_s3_no_lifecycle_count": expected_s3_no_lifecycle_count,
        "expected_s3_no_tag_set_count": expected_s3_no_tag_set_count,
        "unexpected_command_error_count": len(unexpected_command_errors),
        "unexpected_command_errors": unexpected_command_errors,
        "resource_cost_error_count": len(resource_cost_errors),
        "attribution_limits": attribution_limits,
    }
    write_json(DATA / "summary.json", summary)

    make_line_svg(IMAGES / "daily_spend.svg", "Daily AWS Spend", total_daily)
    make_bar_svg(IMAGES / "top_services.svg", "Top Services", top_services)
    make_bar_svg(IMAGES / "top_regions.svg", "Top Regions", top_regions)
    make_bar_svg(IMAGES / "attribution_surfaces.svg", "Attribution Surfaces", category_surfaces, "surface", "amount_usd")

    write_report(summary)


if __name__ == "__main__":
    main()
