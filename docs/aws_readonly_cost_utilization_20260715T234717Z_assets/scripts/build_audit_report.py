#!/usr/bin/env python3
"""Build the durable Markdown report and canonical MCP artifact payload."""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
REPO_DOCS = ROOT.parents[0]
REPORT = REPO_DOCS / "plans" / "20260715T234717Z_lsmc_aws_readonly_cost_utilization_report.md"
ARTIFACT = ROOT / "artifact.json"
SOURCE_NOTES = ROOT / "source_notes.md"


def read_csv(name: str) -> list[dict[str, str]]:
    with (DATA / name).open(newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(name: str, rows: list[dict[str, Any]]) -> None:
    path = DATA / name
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


def table(rows: list[dict[str, Any]], columns: list[tuple[str, str]], limit: int | None = None) -> str:
    selected = rows[:limit] if limit else rows
    lines = ["| " + " | ".join(label for label, _ in columns) + " |", "| " + " | ".join("---" for _ in columns) + " |"]
    for row in selected:
        values = []
        for _, field in columns:
            value = row.get(field, "")
            if isinstance(value, float):
                value = f"{value:,.2f}"
            values.append(str(value).replace("|", "\\|"))
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def source(source_id: str, label: str, path: str, description: str, filters: list[str], metrics: list[str]) -> dict[str, Any]:
    return {
        "id": source_id,
        "label": label,
        "path": path,
        "query": {
            "engine": "DuckDB",
            "language": "SQL",
            "sql": f"SELECT * FROM read_csv_auto('{path}')",
            "description": description,
            "executed_at": "2026-07-15T23:50:55Z",
            "tables_used": [path],
            "filters": filters,
            "metric_definitions": metrics,
        },
    }


service_rows = read_csv("service_monthly.csv")
services: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
for row in service_rows:
    period = "june" if row["start"] == "2026-06-01" else "july"
    services[row["service"]][period] += float(row["cost_usd"])
june_total = sum(x["june"] for x in services.values())
july_total = sum(x["july"] for x in services.values())
june_daily = june_total / 30
july_daily = july_total / 14
daily_change = july_daily / june_daily - 1
service_chart = []
for rank, (name, vals) in enumerate(sorted(services.items(), key=lambda x: x[1]["july"], reverse=True)[:10], 1):
    service_chart.append({
        "rank": rank, "service": name,
        "july_cost_usd": round(vals["july"], 2), "june_cost_usd": round(vals["june"], 2),
        "july_share_pct": round(vals["july"] / july_total * 100, 2),
        "july_daily_cost_usd": round(vals["july"] / 14, 2),
    })

resource_cost: dict[str, float] = defaultdict(float)
resource_service: dict[str, str] = {}
for row in read_csv("resource_daily.csv"):
    resource_cost[row["resource_id"]] += float(row["cost_usd"])
    resource_service[row["resource_id"]] = row["service"]

inventory = read_csv("inventory.csv")
inventory_by_id = {row["resource_id"]: row for row in inventory}
inventory_by_region_id = {(row["region"], row["resource_id"]): row for row in inventory}
inventory_by_arn = {row["arn"]: row for row in inventory if row["arn"]}

def live_row(resource_id: str, region: str | None = None) -> dict[str, str] | None:
    return (inventory_by_region_id.get((region, resource_id)) if region else None) or inventory_by_id.get(resource_id) or inventory_by_arn.get(resource_id)


ec2_clusters = []
cluster_cost_full: dict[str, float] = defaultdict(float)
for row in read_csv("ec2_cluster_mtd.csv"):
    cluster_cost_full[row["tag_cluster"] or "blank/unattributed"] += float(row["cost_usd"])
for row in read_csv("utilization_ec2_top_cost_clusters.csv"):
    cluster = row["cluster"]
    full = cluster_cost_full.get(cluster, 0.0)
    sampled = float(row["sampled_instance_cost_usd"])
    ec2_clusters.append({
        "cluster": cluster, "july_cluster_cost_usd": round(full, 2),
        "sampled_instance_cost_usd": round(sampled, 2),
        "sample_cost_coverage_pct": round(sampled / full * 100, 2) if full else None,
        "sampled_instances": int(row["sampled_instance_count"]),
        "instances_with_cpu": int(row["instances_with_cpu"]),
        "measured_vcpu_hours": round(float(row["measured_vcpu_hours"]), 2),
        "busy_vcpu_hours": round(float(row["busy_vcpu_hours"]), 2),
        "busy_share_pct": float(row["busy_share_pct"]) if row["busy_share_pct"] else None,
    })
ec2_clusters.sort(key=lambda x: x["july_cluster_cost_usd"], reverse=True)

high_cost_resources: list[dict[str, Any]] = []
for row in read_csv("utilization_s3_top_cost.csv"):
    inv = live_row(row["bucket"], row["region"])
    high_cost_resources.append({
        "category": "S3 bucket", "resource": row["bucket"], "region": row["region"],
        "july_cost_usd": float(row["july_cost_usd"]),
        "utilization": f"{float(row['latest_size_tib']):,.3f} TiB; {int(row['latest_object_count']):,} objects; request metrics not enabled",
        "tag_state": "untagged" if inv and inv["untagged"] == "True" else "tagged",
        "live_state": "live",
    })
for row in read_csv("utilization_fsx_top_cost.csv"):
    inv = live_row(row["resource_id"], row["region"])
    high_cost_resources.append({
        "category": "FSx file system", "resource": row["resource_id"], "region": row["region"],
        "july_cost_usd": float(row["july_cost_usd"]),
        "utilization": f"{float(row['read_tib']):,.3f} TiB read; {float(row['write_tib']):,.3f} TiB write; {int(row['metadata_ops']):,} metadata ops",
        "tag_state": "untagged" if inv and inv["untagged"] == "True" else ("tagged" if inv else "not observable after deletion"),
        "live_state": "live" if inv else "not live at scan time",
    })
rds_util = {(row["region"], row["resource_id"]): row for row in read_csv("utilization_rds.csv")}
for resource_id, cost in sorted(resource_cost.items(), key=lambda x: x[1], reverse=True):
    if ":rds:" not in resource_id or ":db:" not in resource_id or cost < 2:
        continue
    rid = resource_id.rsplit(":", 1)[-1]
    region = resource_id.split(":")[3]
    util = rds_util.get((region, rid))
    inv = live_row(rid, region)
    if util:
        utilization = f"CPU avg {float(util['cpu_avg_pct']):.2f}%, p95 {float(util['cpu_p95_pct']):.2f}%; connections avg {float(util['connections_avg']):.2f}"
    else:
        utilization = "no current CloudWatch row; instance not live at scan time"
    high_cost_resources.append({
        "category": "RDS instance", "resource": rid,
        "region": region, "july_cost_usd": round(cost, 2),
        "utilization": utilization,
        "tag_state": "untagged" if inv and inv["untagged"] == "True" else ("tagged" if inv else "not observable after deletion"),
        "live_state": "live" if inv else "not live at scan time",
    })
for resource_id, cost in sorted(resource_cost.items(), key=lambda x: x[1], reverse=True):
    if not resource_id.startswith("vol-") or cost < 4:
        continue
    inv = live_row(resource_id)
    high_cost_resources.append({
        "category": "EBS volume", "resource": resource_id,
        "region": inv["region"] if inv else "unknown", "july_cost_usd": round(cost, 2),
        "utilization": "live volume telemetry in utilization_ebs.csv" if inv else "not live at scan time; no current utilization",
        "tag_state": "untagged" if inv and inv["untagged"] == "True" else ("tagged" if inv else "not observable after deletion"),
        "live_state": "live" if inv else "not live at scan time",
    })
for row in read_csv("utilization_nat.csv"):
    arn = f"arn:aws:ec2:{row['region']}:108782052779:natgateway/{row['resource_id']}"
    cost = resource_cost.get(arn, 0.0)
    if cost < 5:
        continue
    high_cost_resources.append({
        "category": "NAT gateway", "resource": row["resource_id"], "region": row["region"],
        "july_cost_usd": round(cost, 2),
        "utilization": f"{float(row['total_traffic_gib']):,.3f} GiB across four CloudWatch byte counters",
        "tag_state": "untagged" if row["untagged"] == "True" else "tagged",
        "live_state": "live",
    })
high_cost_resources.sort(key=lambda x: x["july_cost_usd"], reverse=True)

ebs_util = {row["resource_id"]: row for row in read_csv("utilization_ebs.csv")}
nat_util = {row["resource_id"]: row for row in read_csv("utilization_nat.csv")}
rds_util = {(row["region"], row["resource_id"]): row for row in read_csv("utilization_rds.csv")}
s3_util = {row["bucket"]: row for row in read_csv("utilization_s3_top_cost.csv")}
untagged_rows = []
for row in read_csv("direct_untagged.csv"):
    cost = max(resource_cost.get(row["resource_id"], 0.0), resource_cost.get(row["arn"], 0.0))
    utilization = "not collected for this resource type"
    if row["kind"] == "db_instance" and (row["region"], row["resource_id"]) in rds_util:
        util = rds_util[(row["region"], row["resource_id"])]
        utilization = f"CPU avg {float(util['cpu_avg_pct']):.2f}%; connections avg {float(util['connections_avg']):.2f}"
    elif row["kind"] == "nat_gateway" and row["resource_id"] in nat_util:
        utilization = f"{float(nat_util[row['resource_id']]['total_traffic_gib']):,.3f} GiB across four byte counters"
    elif row["kind"] == "volume" and row["resource_id"] in ebs_util:
        util = ebs_util[row["resource_id"]]
        points = int(util["datapoints"])
        observed_idle = None
        if util["idle_pct_of_window"] and points:
            observed_idle = min(100.0, float(util["idle_pct_of_window"]) * 336 / points)
        utilization = f"{points} observed hours; idle {observed_idle:.1f}% of observed hours" if observed_idle is not None else "no CloudWatch datapoints in window"
    elif row["kind"] == "bucket" and row["resource_id"] in s3_util:
        util = s3_util[row["resource_id"]]
        utilization = f"{float(util['latest_size_tib']):,.3f} TiB; request metrics not enabled"
    elif row["kind"] == "elastic_ip":
        utilization = "associated" if row.get("associated") == "True" else "unassociated"
    untagged_rows.append({
        "category": row["kind"], "resource": row["resource_id"], "region": row["region"],
        "july_resource_cost_usd": round(cost, 2), "utilization": utilization,
        "state": row.get("state") or ("live" if row["kind"] == "bucket" else ""),
        "size_gib": int(float(row.get("size_gib") or row.get("volume_size_gib") or 0)),
    })
untagged_rows.sort(key=lambda x: (x["july_resource_cost_usd"], x["size_gib"]), reverse=True)
untagged_positive = [row for row in untagged_rows if row["july_resource_cost_usd"] > 0]
untagged_cost = sum(row["july_resource_cost_usd"] for row in untagged_positive)

lifecycle_summary = json.loads((DATA / "lifecycle_summary.json").read_text())
lifecycle_resources = read_csv("lifecycle_resources.csv")
lifecycle_clusters = read_csv("lifecycle_clusters.csv")
lifecycle_stacks = read_csv("lifecycle_cloudformation_stacks.csv")
jemx3_related = read_csv("jemx3_related_resources.csv")
current_lifecycle_resources = [row for row in lifecycle_resources if row["record_scope"].startswith("current")]
current_lifecycle_counts = {
    status: sum(1 for row in current_lifecycle_resources if row["lifecycle_status"] == status)
    for status in sorted({row["lifecycle_status"] for row in current_lifecycle_resources})
}
stopped_resources = [row for row in current_lifecycle_resources if row["lifecycle_status"] == "stopped"]
transitioning_resources = [row for row in current_lifecycle_resources if row["lifecycle_status"] == "deleting"]
attention_stacks = [row for row in lifecycle_stacks if row["lifecycle_status"] in {"exception", "exception_recovered", "provisioning_or_updating"}]
failed_stacks = [row for row in lifecycle_stacks if row["lifecycle_status"] == "exception"]
active_clusters = [row for row in lifecycle_clusters if row["lifecycle_status"] == "active"]
deleted_clusters = [row for row in lifecycle_clusters if row["lifecycle_status"] == "deleted"]
jemx3_orphans = [row for row in jemx3_related if row["lifecycle_status"] == "orphaned"]
for row in lifecycle_clusters:
    row["july_cost_usd"] = float(row["july_cost_usd"])
for row in lifecycle_resources:
    row["july_cost_usd"] = float(row["july_cost_usd"])

overview = [{
    "july_mtd_cost_usd": round(july_total, 2), "june_cost_usd": round(june_total, 2),
    "july_daily_cost_usd": round(july_daily, 2), "june_daily_cost_usd": round(june_daily, 2),
    "daily_rate_change": daily_change, "direct_resource_count": 194,
    "direct_untagged_count": len(untagged_rows), "untagged_positive_cost_count": len(untagged_positive),
    "untagged_identified_cost_usd": round(untagged_cost, 2),
    "cost_explorer_api_cost_usd": 630.60, "cost_explorer_api_requests": 63060,
    "ec2_sample_cost_coverage": 0.4018, "ec2_sample_ids_with_cpu": 99,
    "active_cluster_count": len(active_clusters), "deleted_cluster_count": len(deleted_clusters),
    "stopped_resource_count": len(stopped_resources), "failed_stack_count": len(failed_stacks),
}]

write_csv("derived_service_costs.csv", service_chart)
write_csv("derived_high_cost_resources.csv", high_cost_resources)
write_csv("derived_ec2_clusters.csv", ec2_clusters)
write_csv("derived_untagged_resources.csv", untagged_rows)

service_source = source(
    "src_cost", "AWS Cost Explorer service and resource cost snapshot",
    "docs/aws_readonly_cost_utilization_20260715T234717Z_assets/data/service_monthly.csv",
    "UnblendedCost grouped by service for June and July MTD, reconciled to direct Cost Explorer totals.",
    ["Account 108782052779", "June 1 through July 14, 2026", "Cost Explorer End=2026-07-15 exclusive"],
    ["July MTD cost is UnblendedCost for 14 complete billing days", "Daily cost is period cost divided by observed calendar days"],
)
derived_source = source(
    "src_derived", "Joined high-cost resource evidence",
    "docs/aws_readonly_cost_utilization_20260715T234717Z_assets/data/derived_high_cost_resources.csv",
    "Cost Explorer resource IDs joined to current inventory and retained CloudWatch metrics.",
    ["Top billed resources in July MTD", "No deletion or rightsizing inference from missing telemetry"],
    ["Resource cost is the sum of daily UnblendedCost rows for the exact resource ID", "Utilization is descriptive over July 1-14"],
)
ec2_source = source(
    "src_ec2", "EC2 top-cost instance CPU sample",
    "docs/aws_readonly_cost_utilization_20260715T234717Z_assets/data/derived_ec2_clusters.csv",
    "Top 100 billed EC2 instance IDs joined to CloudTrail launch metadata and 5-minute CloudWatch CPUUtilization, then aggregated by cluster.",
    ["Top 100 EC2 resource IDs by July MTD cost", "99 IDs with exact metadata and CPU", "40.18% of EC2 service spend represented"],
    ["Busy vCPU-hours = vCPUs x 5/60 hours x CPUUtilization fraction", "Busy share = busy vCPU-hours / measured vCPU-hours"],
)
untagged_source = source(
    "src_untagged", "Current zero-user-tag resource inventory",
    "docs/aws_readonly_cost_utilization_20260715T234717Z_assets/data/derived_untagged_resources.csv",
    "Direct service inventory of current cost-bearing resource families across all enabled regions, filtered to zero non-AWS tags and joined to cost/utilization where available.",
    ["21 enabled regions", "AWS-managed tags excluded from user tag count", "Current direct inventory only"],
    ["Untagged means zero non-AWS tags", "Identified cost includes only resource-level billing IDs that could be joined exactly"],
)
lifecycle_source = source(
    "src_lifecycle", "Current and billed AWS resource lifecycle classification",
    "docs/aws_readonly_cost_utilization_20260715T234717Z_assets/data/lifecycle_resources.csv",
    "Current direct resource inventory joined to July billed identifiers, live ParallelCluster, and CloudFormation lifecycle evidence.",
    ["21 enabled regions", "Snapshot 2026-07-16T00:45:33Z", "No mutation APIs"],
    ["Deleted requires terminal provider deletion or absence from refreshed direct inventory", "Orphaned requires a live resource with an absent explicit owner"],
)
sources = [service_source, derived_source, ec2_source, untagged_source, lifecycle_source]

manifest = {
    "version": 1, "surface": "report",
    "title": "LSMC AWS Cost, Untagged Resource, And Utilization Audit",
    "description": "Read-only AWS account audit for profile lsmc, June and July 2026.",
    "generatedAt": lifecycle_summary["generated_at"],
    "sources": sources,
    "cards": [
        {"id": "card_cost", "description": "Fourteen complete billing days.", "dataset": "overview", "sourceId": "src_cost", "metrics": [
            {"label": "July MTD", "field": "july_mtd_cost_usd", "format": "currency"},
            {"label": "Daily vs June", "field": "daily_rate_change", "format": "percent", "signed": True},
        ]},
        {"id": "card_untagged", "description": "Zero non-AWS tags in direct inventory.", "dataset": "overview", "sourceId": "src_untagged", "metrics": [
            {"label": "Resources", "field": "direct_untagged_count", "format": "number"},
            {"label": "Joined July cost", "field": "untagged_identified_cost_usd", "format": "currency"},
        ]},
        {"id": "card_ce_api", "description": "A high-cost non-resource activity driver.", "dataset": "overview", "sourceId": "src_cost", "metrics": [
            {"label": "July API cost", "field": "cost_explorer_api_cost_usd", "format": "currency"},
            {"label": "Requests", "field": "cost_explorer_api_requests", "format": "number"},
        ]},
        {"id": "card_ec2_coverage", "description": "Top 100 instance IDs; 99 resolved.", "dataset": "overview", "sourceId": "src_ec2", "metrics": [
            {"label": "Spend coverage", "field": "ec2_sample_cost_coverage", "format": "percent"},
            {"label": "IDs with CPU", "field": "ec2_sample_ids_with_cpu", "format": "number"},
        ]},
        {"id": "card_lifecycle", "description": "Live lifecycle snapshot across all audited resource families.", "dataset": "overview", "sourceId": "src_lifecycle", "metrics": [
            {"label": "Active clusters", "field": "active_cluster_count", "format": "number"},
            {"label": "Stopped resources", "field": "stopped_resource_count", "format": "number"},
            {"label": "Failed stacks", "field": "failed_stack_count", "format": "number"},
        ]},
    ],
    "charts": [
        {"id": "chart_service_cost", "title": "July month-to-date cost by service", "description": "Top ten services account for nearly all spend in the first 14 complete billing days.",
         "dataset": "service_costs", "type": "bar", "sourceId": "src_cost",
         "encodings": {"x": {"field": "service"}, "y": {"field": "july_cost_usd"}},
         "options": {"orientation": "horizontal", "grouping": "grouped", "showLegend": False}},
    ],
    "tables": [
        {"id": "table_high_cost", "title": "High-cost resource evidence", "description": "Exact July resource IDs with available utilization; missing rows are labeled, not treated as zero.",
         "dataset": "high_cost_resources", "sourceId": "src_derived", "defaultSort": {"field": "july_cost_usd", "direction": "desc"},
         "columns": [
             {"field": "category", "label": "Category", "type": "text"}, {"field": "resource", "label": "Resource", "type": "text"},
             {"field": "region", "label": "Region", "type": "text"}, {"field": "july_cost_usd", "label": "July cost", "type": "currency", "format": "currency"},
             {"field": "utilization", "label": "Utilization", "type": "text"}, {"field": "tag_state", "label": "Tag state", "type": "text"},
             {"field": "live_state", "label": "Live state", "type": "text"},
         ]},
        {"id": "table_ec2", "title": "EC2 cluster CPU sample", "description": "Five-minute CPU benchmark for the top-100 billed instance sample; cluster cost is the full Cost Explorer tag total.",
         "dataset": "ec2_clusters", "sourceId": "src_ec2", "defaultSort": {"field": "july_cluster_cost_usd", "direction": "desc"},
         "columns": [
             {"field": "cluster", "label": "Cluster", "type": "text"}, {"field": "july_cluster_cost_usd", "label": "Full July cost", "type": "currency", "format": "currency"},
             {"field": "sample_cost_coverage_pct", "label": "Sample coverage %", "type": "number", "format": "number"},
             {"field": "measured_vcpu_hours", "label": "Measured vCPU-h", "type": "number", "format": "number"},
             {"field": "busy_share_pct", "label": "CPU busy %", "type": "number", "format": "number"},
         ]},
        {"id": "table_untagged", "title": "Current resources with zero user tags", "description": "Direct current inventory across 21 enabled regions; sorted by identified July resource cost.",
         "dataset": "untagged_resources", "sourceId": "src_untagged", "defaultSort": {"field": "july_resource_cost_usd", "direction": "desc"},
         "columns": [
             {"field": "category", "label": "Category", "type": "text"}, {"field": "resource", "label": "Resource", "type": "text"},
             {"field": "region", "label": "Region", "type": "text"}, {"field": "july_resource_cost_usd", "label": "Identified July cost", "type": "currency", "format": "currency"},
             {"field": "utilization", "label": "Utilization", "type": "text"}, {"field": "state", "label": "State", "type": "text"},
         ]},
        {"id": "table_cluster_lifecycle", "title": "ParallelCluster lifecycle", "description": "Every July-billed or currently tagged ParallelCluster identity, including live compute-fleet state and terminal deletion evidence.",
         "dataset": "lifecycle_clusters", "sourceId": "src_lifecycle", "defaultSort": {"field": "july_cost_usd", "direction": "desc"},
         "columns": [
             {"field": "cluster", "label": "Cluster", "type": "text"}, {"field": "region", "label": "Region", "type": "text"},
             {"field": "july_cost_usd", "label": "July cost", "type": "currency", "format": "currency"},
             {"field": "lifecycle_status", "label": "Lifecycle", "type": "text"},
             {"field": "cluster_provider_status", "label": "Cluster state", "type": "text"},
             {"field": "compute_fleet_status", "label": "Compute fleet", "type": "text"},
             {"field": "cloudformation_status", "label": "Stack state", "type": "text"},
         ]},
        {"id": "table_all_lifecycle", "title": f"Lifecycle resource preview (500 of {len(lifecycle_resources):,} rows)", "description": "Bounded interactive preview; the durable lifecycle_resources.csv contains every current direct-inventory resource and unique July billed identifier.",
         "dataset": "lifecycle_resources", "sourceId": "src_lifecycle", "defaultSort": {"field": "july_cost_usd", "direction": "desc"},
         "columns": [
             {"field": "service", "label": "Service", "type": "text"}, {"field": "kind", "label": "Kind", "type": "text"},
             {"field": "region", "label": "Region", "type": "text"}, {"field": "resource_id", "label": "Resource", "type": "text"},
             {"field": "july_cost_usd", "label": "July cost", "type": "currency", "format": "currency"},
             {"field": "lifecycle_status", "label": "Lifecycle", "type": "text"},
             {"field": "provider_state", "label": "Provider state", "type": "text"},
             {"field": "owner_stack", "label": "Owner stack", "type": "text"},
             {"field": "owner_cluster", "label": "Owner cluster", "type": "text"},
         ]},
        {"id": "table_stopped", "title": "Stopped current resources", "description": "Resources for which AWS explicitly reports stopped state.",
         "dataset": "stopped_resources", "sourceId": "src_lifecycle", "columns": [
             {"field": "resource_id", "label": "Resource", "type": "text"}, {"field": "name", "label": "Name", "type": "text"},
             {"field": "region", "label": "Region", "type": "text"}, {"field": "july_cost_usd", "label": "July cost", "type": "currency", "format": "currency"},
             {"field": "owner_stack", "label": "Owner stack", "type": "text"},
         ]},
        {"id": "table_stack_attention", "title": "Failed, recovered, and in-progress stacks", "description": "Unresolved failures are distinct from completed rollback histories and active provisioning.",
         "dataset": "attention_stacks", "sourceId": "src_lifecycle", "columns": [
             {"field": "stack_name", "label": "Stack", "type": "text"}, {"field": "region", "label": "Region", "type": "text"},
             {"field": "lifecycle_status", "label": "Classification", "type": "text"}, {"field": "stack_status", "label": "AWS status", "type": "text"},
             {"field": "status_reason", "label": "Reason", "type": "text"},
         ]},
        {"id": "table_jemx3", "title": "jemx3 tagged residual verification", "description": "Service-specific existence checks distinguish stale tag-index entries from live orphaned log groups.",
         "dataset": "jemx3_related", "sourceId": "src_lifecycle", "columns": [
             {"field": "resource_arn", "label": "Resource ARN", "type": "text"}, {"field": "exists", "label": "Exists", "type": "text"},
             {"field": "lifecycle_status", "label": "Lifecycle", "type": "text"}, {"field": "classification_evidence", "label": "Evidence", "type": "text"},
         ]},
    ],
    "blocks": [
        {"id": "title", "type": "markdown", "body": "# LSMC AWS Cost, Untagged Resource, And Utilization Audit"},
        {"id": "summary", "type": "markdown", "body": "## Technical summary\n\nJuly 1-14 spend is **$20,620.26**; the daily rate is **10.9% below June**, but EC2, S3, RDS, and FSx still account for **88.1%** of spend. The sharpest near-term findings are 63,060 Cost Explorer API requests costing **$630.60**, three `dayhoff-lsmcq7` RDS instances costing **$413.56** with 1.8-2.9% CPU and zero connections, four untagged NAT gateways costing **$36.30** with zero traffic, and **66** current resources with zero user tags. No AWS mutations were performed."},
        {"id": "metrics", "type": "metric-strip", "cardIds": ["card_cost", "card_untagged", "card_ce_api", "card_ec2_coverage", "card_lifecycle"]},
        {"id": "lifecycle_heading", "type": "markdown", "body": "## Current lifecycle state\n\n`jemx3` is deleted: ParallelCluster and the live stack are absent, CloudFormation records `DELETE_COMPLETE` at 2026-07-05T09:22:22Z, and its head node and managed FSx are absent. Two clusters currently exist: `ifx-p2-1000-120-0715` is active with fleet `RUNNING`; `tst-10315g` was `CREATE_IN_PROGRESS` at the snapshot. Ten EC2 resources are explicitly stopped. Two stacks remain in unresolved failure states, while five other stacks completed rollback."},
        {"id": "cluster_lifecycle_table", "type": "table", "tableId": "table_cluster_lifecycle"},
        {"id": "stopped_table", "type": "table", "tableId": "table_stopped"},
        {"id": "stack_attention_table", "type": "table", "tableId": "table_stack_attention"},
        {"id": "jemx3_table", "type": "table", "tableId": "table_jemx3"},
        {"id": "all_lifecycle_heading", "type": "markdown", "body": f"## Full resource lifecycle inventory\n\nThe full table contains {len(lifecycle_resources):,} rows: all 196 current direct-inventory resources, every unique July billed identifier, and verified live tagged residuals, deduplicated when a current resource matches billing. Billing identifiers that do not map to a directly enumerable resource type remain `unresolved` rather than being guessed."},
        {"id": "all_lifecycle_table", "type": "table", "tableId": "table_all_lifecycle"},
        {"id": "cost_heading", "type": "markdown", "body": "## EC2 and storage dominate the July bill\n\nThe chart ranks the top ten services for July 1-14. EC2 compute is 55.1% of spend, S3 is 18.0%, RDS is 7.9%, and FSx is 7.1%."},
        {"id": "service_chart", "type": "chart", "chartId": "chart_service_cost"},
        {"id": "resource_heading", "type": "markdown", "body": "## The strongest resource-level candidates combine cost with low observed activity\n\nThe table joins exact billed resource IDs to retained or current CloudWatch evidence. It also flags resources that were already deleted by scan time so missing telemetry is not misread as idle."},
        {"id": "resource_table", "type": "table", "tableId": "table_high_cost"},
        {"id": "ec2_heading", "type": "markdown", "body": "## EC2 CPU is low in the measured top-cost sample\n\nThe top-100 instance sample represents 40.18% of July EC2 service spend. CPU busy share ranges from 3.0% for sampled `jemx3` vCPU-hours to 20.3% for `illumina-94-c02`; this is a CPU-only signal and must be paired with Slurm/job benchmarks before rightsizing."},
        {"id": "ec2_table", "type": "table", "tableId": "table_ec2"},
        {"id": "untagged_heading", "type": "markdown", "body": "## Sixty-six current resources have zero user tags\n\nThe direct current inventory found 26 buckets, 14 volumes, 13 Elastic IPs, 6 NAT gateways, 3 snapshots, 2 RDS instances, and 2 load balancers with no non-AWS tags. Resource Explorer found 1,612 broader indexed entries, but that count is dominated by ephemeral fleets, spot requests, and security-group rules and is not a cleanup count."},
        {"id": "untagged_table", "type": "table", "tableId": "table_untagged"},
        {"id": "scope", "type": "markdown", "body": "## Scope, data, and metric definitions\n\n**Cost:** Cost Explorer `UnblendedCost`; June 1-30 is final and July 1-14 is estimated. **Untagged:** zero non-AWS tags in direct service inventory. **EC2 busy share:** vCPU-weighted 5-minute `CPUUtilization` over observed points. **S3 utilization:** latest daily stored bytes and object count; request metrics were not enabled for the top buckets. **NAT traffic:** sum of four directional CloudWatch byte counters, not billable-byte equivalence."},
        {"id": "method", "type": "markdown", "body": "## Methodology\n\nThe scan enumerated 21 enabled regions with direct read APIs for EC2/EBS/EIP/NAT, FSx, RDS/Aurora, ELBv2, and S3; supplemented three indexed regions with Resource Explorer `tag:none`; grouped Cost Explorer by service, region, usage type, cluster tag, and resource ID; and joined exact IDs to CloudTrail launch metadata and CloudWatch. Grouped service totals reconcile exactly to direct Cost Explorer totals."},
        {"id": "limits", "type": "markdown", "body": "## Limitations, uncertainty, and robustness checks\n\nResource-level Cost Explorer IDs cover 71.06% of July EC2 spend; the top-100 CPU sample covers 40.18%, with 99 of 100 IDs resolved. Resource Explorer exists only in `us-west-2`, `us-east-1`, and `us-east-2`. S3 request metrics are absent, so storage size is measured but access activity is not. Several billed FSx/RDS/EBS IDs were not live at scan time; retained metrics are shown when available. CPU, connections, and byte counters do not prove safe deletion or rightsizing. The profile resolves to the account root principal, which is a credential-scope risk even though this run made read-only calls."},
        {"id": "next", "type": "markdown", "body": "## Recommended next steps\n\n1. Identify and throttle the automation responsible for 63,060 Cost Explorer API requests ($630.60) in 14 days.\n2. Review the three `dayhoff-lsmcq7` RDS instances ($413.56 combined; 1.8-2.9% CPU; zero average connections) and untagged `labcore-dev-instance-1` ($46.08; 2.75% CPU; zero connections) with their owners before any change.\n3. Validate ownership of the four zero-traffic untagged NAT gateways in `ap-south-1` and `eu-central-1` ($36.30 combined); separately tag the active untagged `nat-00f3c26e43ede9b10` ($33.00; ~1,992 GiB across four counters).\n4. Add ownership/cost-center/lifecycle tags to the 66 direct untagged resources, starting with `lsmc-public-ont-data` (5.604 TiB; $25.38), the two untagged RDS instances, and cost-bearing NAT/EBS resources.\n5. Review lifecycle/storage-class policy for `lsmc-ssf-sequencing-data` (218.046 TiB; $953.69) and `lsmc-dayoa-omics-analysis-us-west-2` (61.428 TiB; $278.01).\n6. Replace root-profile scanning with an explicitly read-only assumed role."},
        {"id": "questions", "type": "markdown", "body": "## Further questions\n\n- Which automation is issuing Cost Explorer API calls, and is its polling frequency intentional?\n- Are the `dayhoff-lsmcq7` readers/writer required for standby or recovery objectives despite zero observed connections?\n- Are the zero-traffic NAT gateways retained for disaster recovery, or are they orphaned?\n- Which S3 buckets are authoritative archives versus working copies eligible for colder lifecycle tiers?"},
    ],
}

snapshot = {
    "version": 1, "status": "ready", "generatedAt": lifecycle_summary["generated_at"],
    "datasets": {
        "overview": overview,
        "service_costs": service_chart,
        "high_cost_resources": high_cost_resources,
        "ec2_clusters": ec2_clusters,
        "untagged_resources": untagged_rows,
        "lifecycle_clusters": lifecycle_clusters,
        "lifecycle_resources": lifecycle_resources[:500],
        "stopped_resources": stopped_resources,
        "attention_stacks": attention_stacks,
        "jemx3_related": jemx3_related,
    },
}
artifact = {"surface": "report", "manifest": manifest, "snapshot": snapshot, "sources": sources, "package_info": {"snapshot_label": "2026-07-15 read-only AWS audit"}}
ARTIFACT.write_text(json.dumps(artifact, indent=2, sort_keys=False) + "\n")

report = f"""# LSMC AWS Cost, Untagged Resource, And Utilization Audit

Generated: {lifecycle_summary['generated_at']}  
AWS profile/account: `lsmc` / `108782052779`  
Safety: read-only; no AWS mutations performed.

## Technical Summary

July 1-14 spend is **${july_total:,.2f}**. The daily rate is **{abs(daily_change)*100:.1f}% below June**, but EC2, S3, RDS, and FSx still account for **88.1%** of July spend.

The clearest findings are:

- **63,060 Cost Explorer API requests cost $630.60** in 14 days.
- The three `dayhoff-lsmcq7` RDS instances cost **$413.56** combined while averaging **1.81%-2.88% CPU** and **zero database connections**.
- Four untagged NAT gateways in `ap-south-1` and `eu-central-1` cost **$36.30** combined and reported **zero traffic**.
- **66 current resources have zero user tags**: 26 S3 buckets, 14 EBS volumes, 13 Elastic IPs, 6 NAT gateways, 3 snapshots, 2 RDS instances, and 2 load balancers.
- The `lsmc` profile resolves to `arn:aws:iam::108782052779:root`; the scan was read-only, but the credential scope is materially broader than needed.

## Resource And Cluster Lifecycle Snapshot

Lifecycle evidence was refreshed at **{lifecycle_summary['generated_at']}** across all 21 enabled regions. ParallelCluster explicitly does not support `ap-northeast-3` or `ap-south-2`; direct AWS inventory and CloudFormation coverage still succeeded in both regions.

### ParallelCluster

{table(lifecycle_clusters, [("Cluster", "cluster"), ("Region", "region"), ("July $", "july_cost_usd"), ("Lifecycle", "lifecycle_status"), ("Cluster state", "cluster_provider_status"), ("Compute fleet", "compute_fleet_status"), ("Stack", "cloudformation_status")])}

`jemx3` is **deleted**, not running. ParallelCluster reports it absent, the live CloudFormation stack is absent, and CloudFormation history records `DELETE_COMPLETE` at **2026-07-05T09:22:22.181Z**. No `jemx3` EC2 instances or managed FSx `fs-07fb3448c1cb30c1c` exist.

The tag index retained eight old `jemx3` references. Service-specific checks show four EBS volumes and one DRA are deleted stale-index entries. Three CloudWatch log groups still exist after the owner stack was deleted, so those are classified **orphaned**:

{table(jemx3_related, [("Resource", "resource_arn"), ("Exists", "exists"), ("Lifecycle", "lifecycle_status"), ("Evidence", "classification_evidence")])}

At the snapshot, two clusters existed:

- `ifx-p2-1000-120-0715`: **active**, `UPDATE_COMPLETE`, compute fleet `RUNNING`.
- `tst-10315g`: **provisioning**, `CREATE_IN_PROGRESS`; compute-fleet state was intentionally not queried until cluster creation completes.

All other 44 named cluster rows are deleted. The `blank/unattributed` $445.03 billing row is unresolved because it is not a cluster identity.

### Current stopped and transitioning resources

The refreshed direct inventory contains **{len(stopped_resources)} stopped resources** and **{len(transitioning_resources)} deleting resource**. Stopped is based only on explicit AWS provider state.

{table(stopped_resources, [("Resource", "resource_id"), ("Name", "name"), ("Region", "region"), ("July $", "july_cost_usd"), ("Owner stack", "owner_stack")])}

{table(transitioning_resources, [("Resource", "resource_id"), ("Name", "name"), ("Region", "region"), ("Provider state", "provider_state"), ("Owner cluster", "owner_cluster")])}

### CloudFormation exceptions

Two stacks remain in unresolved failure states; five other stacks record completed rollback states and are reported separately as `exception_recovered`.

{table(attention_stacks, [("Stack", "stack_name"), ("Region", "region"), ("Classification", "lifecycle_status"), ("AWS state", "stack_status"), ("Reason", "status_reason")])}

The unresolved failures are:

- `Dayhoff-staging-Network` (`us-east-1`): `DELETE_FAILED`; two private subnets failed deletion.
- `marvain-cleanroom-20260712T103857Z` (`us-west-1`): `ROLLBACK_FAILED`; `AgentWorkerSecurityGroup` failed deletion.

### Full lifecycle inventory

The canonical lifecycle table contains **{len(lifecycle_resources):,} rows** covering all **{lifecycle_summary['current_inventory_rows']} current direct-inventory resources** plus all **{lifecycle_summary['billed_unique_identifiers']:,} unique July billed identifiers**, with matching live/billed rows deduplicated. Overall classifications are {json.dumps(lifecycle_summary['lifecycle_counts'], sort_keys=True)}. The 77 `unresolved` rows are billing identifiers that do not represent a directly enumerable resource type; they are not guessed as deleted.

Full table: `docs/aws_readonly_cost_utilization_20260715T234717Z_assets/data/lifecycle_resources.csv`

## Cost Concentration

June total: **${june_total:,.2f}** (final). July 1-14 total: **${july_total:,.2f}** (estimated). Daily cost fell from **${june_daily:,.2f}** to **${july_daily:,.2f}**.

{table(service_chart, [("Service", "service"), ("July MTD $", "july_cost_usd"), ("Share %", "july_share_pct"), ("June $", "june_cost_usd")])}

Non-resource platform activity also matters: Cost Explorer API calls are the fifth-largest July service cost at **$632.11** total, including **$630.60 / 63,060 requests** under `USE1-APIRequest`; AWS Config recorded **71,399 configuration items** for **$214.20**.

## High-Cost Resources And Utilization

{table(high_cost_resources, [("Category", "category"), ("Resource", "resource"), ("Region", "region"), ("July $", "july_cost_usd"), ("Utilization", "utilization"), ("Tags", "tag_state"), ("Live", "live_state")], 30)}

The largest S3 buckets are `lsmc-ssf-sequencing-data` at **218.046 TiB / $953.69** and `lsmc-dayoa-omics-analysis-us-west-2` at **61.428 TiB / $278.01**. None of the top-cost buckets had S3 request metrics enabled, so this scan can measure stored capacity but not request activity.

The highest resource-ID FSx cost was `fs-07fb3448c1cb30c1c` at **$190.43**, with **50.112 TiB read**, **12.908 TiB written**, and **419,915,451 metadata operations**. By contrast, `fs-0b57687e1517a9181` cost **$151.45** with essentially no data I/O (0 read, 0.001 TiB written), though it still had 7.4M metadata operations. These file systems were no longer live at scan time; CloudWatch history supplied the measurements.

## EC2 CPU Sample

Resource-level IDs cover **71.06%** of July EC2 cost. The top-100 instance sample covers **40.18%** of total EC2 service spend; 99 IDs resolved to exact metadata and 5-minute CPU, while `i-01db42c813d037c0e` ($27.96) remained unresolved.

{table(ec2_clusters, [("Cluster", "cluster"), ("Full July $", "july_cluster_cost_usd"), ("Sample $", "sampled_instance_cost_usd"), ("Coverage %", "sample_cost_coverage_pct"), ("Measured vCPU-h", "measured_vcpu_hours"), ("CPU busy %", "busy_share_pct")], 12)}

This is CPU utilization, not workflow efficiency. High-I/O jobs, scheduler gaps, node startup, and deliberately oversized memory instances can all produce low CPU. Pair these results with Slurm/job benchmark data before rightsizing.

## Untagged Resources

Direct service APIs found **{len(untagged_rows)} current resources with zero non-AWS tags**. Exact resource-level billing IDs join **${untagged_cost:,.2f}** of July cost to {len(untagged_positive)} of them; this is a lower bound because resource-level Cost Explorer coverage is incomplete.

{table(untagged_rows, [("Category", "category"), ("Resource", "resource"), ("Region", "region"), ("July $", "july_resource_cost_usd"), ("Utilization", "utilization"), ("State", "state")], 30)}

Resource Explorer separately returned **1,612 untagged indexed entries** in its three indexed regions. That population is dominated by 510 EC2 fleets, 232 security-group rules, 222 spot requests, 137 ECR repositories, and 79 RDS cluster snapshots; it is useful for ownership cleanup but is not a deletion or savings list.

## Method And Definitions

- **Cost:** Cost Explorer `UnblendedCost`; June 1-30 is final and July 1-14 is estimated. Grouped service totals reconcile exactly to direct totals.
- **Untagged:** zero non-AWS tags in current direct service inventory.
- **Coverage:** 21 enabled regions for EC2/EBS/EIP/NAT, FSx, RDS/Aurora, ELBv2, and S3; Resource Explorer supplementation only in `us-west-2`, `us-east-1`, and `us-east-2`.
- **EC2 busy share:** `vCPUs x 5/60 x CPUUtilization%`, summed over 5-minute points, divided by measured vCPU-hours.
- **NAT traffic:** sum of four directional byte counters; this is not equivalent to billable bytes and can double-count a flow.
- **S3 utilization:** latest daily bucket size/object count. Request metrics were not enabled for the top buckets.

## Recommendations

1. Identify and throttle the automation responsible for the 63,060 Cost Explorer API requests.
2. Review the three `dayhoff-lsmcq7` instances and untagged `labcore-dev-instance-1` with service owners before any resize/stop decision.
3. Confirm whether the four zero-traffic NAT gateways are required for DR; if not, prepare a separate destructive-change proposal. Tag the active untagged NATs now only through an approved tagging change.
4. Apply ownership, cost-center, and lifecycle tags to the 66 direct untagged resources, starting with `lsmc-public-ont-data`, the two RDS instances, and the cost-bearing NAT/EBS resources.
5. Review S3 lifecycle/storage-class policy for the 218 TiB sequencing bucket and 61 TiB analysis bucket.
6. Use an explicitly read-only assumed role for future audits instead of root-profile credentials.

## Limitations And Open Questions

- Missing metrics are labeled missing, never interpreted as idle.
- Several billed resources were already deleted, so only retained historical metrics are available.
- CPU, connection, and byte counters do not establish safe deletion or rightsizing.
- Which automation is issuing the Cost Explorer calls?
- Are the zero-connection RDS instances retained for standby/recovery objectives?
- Are the zero-traffic NAT gateways intentional DR capacity?
- Which S3 buckets are authoritative archives versus working copies eligible for colder lifecycle tiers?

## Evidence

- Canonical MCP payload: `docs/aws_readonly_cost_utilization_20260715T234717Z_assets/artifact.json`
- Direct inventory: `docs/aws_readonly_cost_utilization_20260715T234717Z_assets/data/inventory.csv`
- Untagged current resources: `docs/aws_readonly_cost_utilization_20260715T234717Z_assets/data/derived_untagged_resources.csv`
- Cost/resource evidence: `docs/aws_readonly_cost_utilization_20260715T234717Z_assets/data/derived_high_cost_resources.csv`
- EC2 cluster sample: `docs/aws_readonly_cost_utilization_20260715T234717Z_assets/data/derived_ec2_clusters.csv`
- Command audit records: `docs/aws_readonly_cost_utilization_20260715T234717Z_assets/data/command_records.json`
- Full resource lifecycle: `docs/aws_readonly_cost_utilization_20260715T234717Z_assets/data/lifecycle_resources.csv`
- Cluster lifecycle: `docs/aws_readonly_cost_utilization_20260715T234717Z_assets/data/lifecycle_clusters.csv`
- CloudFormation lifecycle: `docs/aws_readonly_cost_utilization_20260715T234717Z_assets/data/lifecycle_cloudformation_stacks.csv`
- Lifecycle command audit: `docs/aws_readonly_cost_utilization_20260715T234717Z_assets/data/lifecycle_command_records.json`
- jemx3 exact evidence: `docs/aws_readonly_cost_utilization_20260715T234717Z_assets/data/jemx3_lifecycle_evidence.json`
"""
REPORT.write_text(report)

SOURCE_NOTES.write_text("""# Source Notes And Chart Map

- Delivery mode: MCP app report; audience: technical.
- Chart: `July month-to-date cost by service`; question: where July cost is concentrated; family: comparison/ranking; type: horizontal bar; fields: service and July UnblendedCost; source: `service_monthly.csv`; supported claim: EC2 and storage dominate spend.
- The chart dataset retains June cost, July share, July daily cost, and rank for auditability beyond the plotted fields.
- Tables are used for exact resource IDs, utilization measurements, tag state, and missing-data labels.
- Resource-level cost coverage is partial and is disclosed adjacent to the affected findings.
- Required technical-report sections are present. Implications are integrated into recommendations. No additional visible methods appendix is needed beyond the durable evidence list in the Markdown companion.
- Lifecycle tables distinguish live provider state, stack state, and owner state. `DELETE_COMPLETE` history is never treated as a live cluster, and stale Resource Groups Tagging API rows are verified against service-specific reads before orphan classification.
""")

print(json.dumps({
    "june_total": round(june_total, 2), "july_total": round(july_total, 2),
    "july_daily_change_pct": round(daily_change * 100, 2),
    "untagged_count": len(untagged_rows), "untagged_joined_cost_usd": round(untagged_cost, 2),
    "high_cost_resource_rows": len(high_cost_resources), "artifact": str(ARTIFACT), "report": str(REPORT),
}, indent=2))
