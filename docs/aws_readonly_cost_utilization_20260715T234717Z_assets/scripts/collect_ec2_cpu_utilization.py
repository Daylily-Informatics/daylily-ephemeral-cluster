#!/usr/bin/env python3
"""Collect 5-minute CPU utilization for the highest-cost July EC2 instance IDs."""

from __future__ import annotations

import csv
import json
import math
import os
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any


PROFILE = "lsmc"
START = "2026-07-01T00:00:00Z"
END = "2026-07-15T00:00:00Z"
TRAIL_LOOKBACK_START = "2026-04-16T00:00:00Z"
ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RAW = ROOT / "raw"
TOP_N = 100
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


def percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    values = sorted(values)
    return values[min(len(values) - 1, math.ceil(q * len(values)) - 1)]


def cost_inputs() -> tuple[dict[str, float], dict[str, float]]:
    instance_cost: dict[str, float] = defaultdict(float)
    regional_cost: dict[str, float] = defaultdict(float)
    with (DATA / "resource_daily.csv").open(newline="") as handle:
        for row in csv.DictReader(handle):
            if row["service"] == "Amazon Elastic Compute Cloud - Compute" and row["resource_id"].startswith("i-"):
                instance_cost[row["resource_id"]] += float(row["cost_usd"])
    with (DATA / "service_region_monthly.csv").open(newline="") as handle:
        for row in csv.DictReader(handle):
            if row["start"] == "2026-07-01" and row["service"] == "Amazon Elastic Compute Cloud - Compute":
                regional_cost[row["region"] or "global"] += float(row["cost_usd"])
    return instance_cost, regional_cost


def add_trail_payload(result: dict[str, dict[str, Any]], payload: dict[str, Any], region: str) -> None:
    for event in payload.get("Events", []):
        detail = json.loads(event.get("CloudTrailEvent") or "{}")
        if detail.get("eventName") != "RunInstances":
            continue
        for item in (((detail.get("responseElements") or {}).get("instancesSet") or {}).get("items") or []):
            iid = item.get("instanceId")
            if not iid:
                continue
            tags = {str(t.get("key")): str(t.get("value") or "") for t in ((item.get("tagSet") or {}).get("items") or []) if t.get("key")}
            cpu = item.get("cpuOptions") or {}
            vcpus = int(cpu.get("coreCount") or 0) * int(cpu.get("threadsPerCore") or 0)
            result[iid] = {
                "region": region,
                "launch_time": detail.get("eventTime", ""),
                "instance_type": item.get("instanceType") or (detail.get("requestParameters") or {}).get("instanceType", ""),
                "vcpus": vcpus,
                "cluster": tags.get("parallelcluster:cluster-name") or tags.get("aws-parallelcluster-clustername") or "untagged/unattributed",
                "queue": tags.get("parallelcluster:queue-name", ""),
                "compute_resource": tags.get("parallelcluster:compute-resource-name", ""),
                "market": item.get("instanceLifecycle", "on-demand"),
            }


def trail_instances(regions: list[str], wanted_ids: list[str]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for region in regions:
        payload = run_aws([
            "cloudtrail", "lookup-events", "--lookup-attributes",
            "AttributeKey=EventName,AttributeValue=RunInstances",
            "--start-time", START, "--end-time", END,
        ], region)
        write_json(RAW / f"cloudtrail_runinstances_{region}.json", payload)
        add_trail_payload(result, payload, region)
    for iid in (x for x in wanted_ids if x not in result):
        for region in regions:
            payload = run_aws([
                "cloudtrail", "lookup-events", "--lookup-attributes",
                f"AttributeKey=ResourceName,AttributeValue={iid}",
                "--start-time", TRAIL_LOOKBACK_START, "--end-time", END,
            ], region)
            add_trail_payload(result, payload, region)
            if iid in result:
                break
    return result


def current_instances(regions: list[str]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for region in regions:
        payload = run_aws(["ec2", "describe-instances"], region)
        for reservation in payload.get("Reservations", []):
            for item in reservation.get("Instances", []):
                tags = {str(t.get("Key")): str(t.get("Value") or "") for t in item.get("Tags", []) if t.get("Key")}
                cpu = item.get("CpuOptions") or {}
                result[item["InstanceId"]] = {
                    "region": region, "launch_time": str(item.get("LaunchTime", "")),
                    "instance_type": item.get("InstanceType", ""),
                    "vcpus": int(cpu.get("CoreCount") or 0) * int(cpu.get("ThreadsPerCore") or 0),
                    "cluster": tags.get("parallelcluster:cluster-name") or tags.get("aws-parallelcluster-clustername") or "untagged/unattributed",
                    "queue": tags.get("parallelcluster:queue-name", ""),
                    "compute_resource": tags.get("parallelcluster:compute-resource-name", ""),
                    "market": "spot" if item.get("InstanceLifecycle") == "spot" else "on-demand",
                }
    return result


def cpu_metrics(instance_ids: list[str], metadata: dict[str, dict[str, Any]]) -> dict[str, list[float]]:
    output: dict[str, list[float]] = defaultdict(list)
    by_region: dict[str, list[str]] = defaultdict(list)
    for iid in instance_ids:
        if iid in metadata:
            by_region[metadata[iid]["region"]].append(iid)
    for region, ids in by_region.items():
        for offset in range(0, len(ids), 20):
            batch = ids[offset:offset + 20]
            queries = []
            query_to_id: dict[str, str] = {}
            for idx, iid in enumerate(batch):
                query_id = f"m{idx}"
                query_to_id[query_id] = iid
                queries.append({
                    "Id": query_id,
                    "MetricStat": {
                        "Metric": {"Namespace": "AWS/EC2", "MetricName": "CPUUtilization", "Dimensions": [{"Name": "InstanceId", "Value": iid}]},
                        "Period": 300, "Stat": "Average",
                    },
                    "ReturnData": True,
                })
            payload = run_aws([
                "cloudwatch", "get-metric-data", "--metric-data-queries", json.dumps(queries),
                "--start-time", START, "--end-time", END, "--scan-by", "TimestampAscending",
                "--max-datapoints", "100800",
            ], region)
            for series in payload.get("MetricDataResults", []):
                iid = query_to_id.get(series.get("Id", ""))
                if iid:
                    output[iid].extend(float(x) for x in series.get("Values", []))
    return output


def main() -> None:
    instance_cost, regional_cost = cost_inputs()
    regions = sorted(r for r, cost in regional_cost.items() if r != "global" and cost > 1)
    ranked = sorted(instance_cost, key=instance_cost.get, reverse=True)[:TOP_N]
    metadata = trail_instances(regions, ranked)
    metadata.update(current_instances(regions))
    metrics = cpu_metrics(ranked, metadata)

    rows: list[dict[str, Any]] = []
    for rank, iid in enumerate(ranked, 1):
        meta = metadata.get(iid, {})
        values = metrics.get(iid, [])
        vcpus = int(meta.get("vcpus") or 0)
        measured_hours = len(values) * 5 / 60
        measured_vcpu_hours = measured_hours * vcpus
        busy_vcpu_hours = sum(v / 100 * vcpus * 5 / 60 for v in values)
        rows.append({
            "rank": rank, "instance_id": iid, "july_cost_usd": round(instance_cost[iid], 4),
            "region": meta.get("region", "unknown"), "cluster": meta.get("cluster", "unknown"),
            "instance_type": meta.get("instance_type", ""), "vcpus": vcpus,
            "market": meta.get("market", ""), "queue": meta.get("queue", ""),
            "compute_resource": meta.get("compute_resource", ""), "launch_time": meta.get("launch_time", ""),
            "cpu_avg_pct": round(sum(values) / len(values), 2) if values else None,
            "cpu_p95_pct": round(percentile(values, .95), 2) if values else None,
            "cpu_max_pct": round(max(values), 2) if values else None,
            "metric_datapoints": len(values), "measured_hours": round(measured_hours, 3),
            "measured_vcpu_hours": round(measured_vcpu_hours, 3),
            "busy_vcpu_hours": round(busy_vcpu_hours, 3),
            "idle_vcpu_hours": round(measured_vcpu_hours - busy_vcpu_hours, 3),
            "busy_share_pct": round(busy_vcpu_hours / measured_vcpu_hours * 100, 2) if measured_vcpu_hours else None,
        })
    write_csv(DATA / "utilization_ec2_top_cost_instances.csv", rows)

    clusters: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for row in rows:
        cluster = str(row["cluster"])
        clusters[cluster]["july_cost_usd"] += float(row["july_cost_usd"])
        clusters[cluster]["measured_vcpu_hours"] += float(row["measured_vcpu_hours"])
        clusters[cluster]["busy_vcpu_hours"] += float(row["busy_vcpu_hours"])
        counts[cluster]["instances"] += 1
        if row["metric_datapoints"]:
            counts[cluster]["instances_with_cpu"] += 1
    cluster_rows = []
    for cluster, vals in sorted(clusters.items(), key=lambda x: x[1]["july_cost_usd"], reverse=True):
        measured = vals["measured_vcpu_hours"]
        busy = vals["busy_vcpu_hours"]
        cluster_rows.append({
            "cluster": cluster, "sampled_instance_count": counts[cluster]["instances"],
            "instances_with_cpu": counts[cluster]["instances_with_cpu"],
            "sampled_instance_cost_usd": round(vals["july_cost_usd"], 2),
            "measured_vcpu_hours": round(measured, 2), "busy_vcpu_hours": round(busy, 2),
            "idle_vcpu_hours": round(measured - busy, 2),
            "busy_share_pct": round(busy / measured * 100, 2) if measured else None,
        })
    write_csv(DATA / "utilization_ec2_top_cost_clusters.csv", cluster_rows)

    total_service_cost = sum(regional_cost.values())
    resource_id_cost = sum(instance_cost.values())
    sampled_cost = sum(instance_cost[i] for i in ranked)
    summary = {
        "top_n": TOP_N, "regions": regions,
        "ec2_service_mtd_cost_usd": total_service_cost,
        "ec2_resource_id_cost_usd": resource_id_cost,
        "resource_id_coverage_pct": round(resource_id_cost / total_service_cost * 100, 2) if total_service_cost else None,
        "sampled_instance_cost_usd": sampled_cost,
        "sampled_service_cost_coverage_pct": round(sampled_cost / total_service_cost * 100, 2) if total_service_cost else None,
        "sampled_ids_with_metadata": sum(1 for i in ranked if i in metadata),
        "sampled_ids_with_cpu": sum(1 for i in ranked if metrics.get(i)),
        "command_count": len(records), "command_error_count": sum(1 for r in records if r["returncode"]),
    }
    write_json(DATA / "utilization_ec2_summary.json", summary)
    write_json(DATA / "utilization_ec2_command_records.json", records)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
