#!/usr/bin/env python3
"""Read-only lifecycle and ownership classification for the LSMC AWS audit."""

from __future__ import annotations

import csv
import datetime as dt
import importlib.util
import json
import os
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any


PROFILE = "lsmc"
ACCOUNT_ID = "108782052779"
ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RAW = ROOT / "raw"
PCLUSTER = Path("/Users/jmajor/miniconda3/envs/DAY-EC/bin/pcluster")
GENERATED_AT = dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")
FAILURE_STATES = {
    "CREATE_FAILED", "DELETE_FAILED", "IMPORT_ROLLBACK_FAILED", "ROLLBACK_FAILED",
    "UPDATE_FAILED", "UPDATE_ROLLBACK_FAILED",
}
RECOVERED_FAILURE_STATES = {"ROLLBACK_COMPLETE", "UPDATE_ROLLBACK_COMPLETE"}

command_records: list[dict[str, Any]] = []


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: list[str] = []
    for row in rows:
        for field in row:
            if field not in fields:
                fields.append(field)
    with path.open("w", newline="") as handle:
        if not fields:
            return
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def run(command: list[str], *, region: str, required: bool = True) -> tuple[Any | None, dict[str, Any]]:
    env = os.environ.copy()
    env["AWS_PROFILE"] = PROFILE
    env["AWS_DEFAULT_REGION"] = region
    proc = subprocess.run(command, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    record = {
        "command": " ".join(command), "region": region, "returncode": proc.returncode,
        "stderr": proc.stderr.strip(), "stdout": proc.stdout.strip(), "recorded_at": GENERATED_AT,
    }
    command_records.append(record)
    if proc.returncode != 0:
        if required:
            print(json.dumps(record, indent=2), file=sys.stderr)
            raise SystemExit(proc.returncode)
        return None, record
    try:
        return json.loads(proc.stdout) if proc.stdout.strip() else {}, record
    except json.JSONDecodeError:
        record["stderr"] = f"non-JSON output: {proc.stdout[:500]}"
        if required:
            raise
        return None, record


def aws(args: list[str], region: str, required: bool = True) -> tuple[Any | None, dict[str, Any]]:
    return run(["aws", *args, "--profile", PROFILE, "--region", region, "--output", "json"], region=region, required=required)


def pcluster(args: list[str], region: str, required: bool = True) -> tuple[Any | None, dict[str, Any]]:
    return run([str(PCLUSTER), *args, "--region", region], region=region, required=required)


def parse_tags(text: str) -> dict[str, str]:
    tags: dict[str, str] = {}
    for item in (text or "").split(";"):
        if "=" in item:
            key, value = item.split("=", 1)
            tags[key] = value
    return tags


def stack_lifecycle(status: str) -> str:
    if status == "DELETE_COMPLETE":
        return "deleted"
    if status == "DELETE_IN_PROGRESS":
        return "deleting"
    if status in FAILURE_STATES or status.endswith("_FAILED"):
        return "exception"
    if status in RECOVERED_FAILURE_STATES:
        return "exception_recovered"
    if status.endswith("_IN_PROGRESS"):
        return "provisioning_or_updating"
    return "active"


def current_resource_lifecycle(row: dict[str, str], stack: dict[str, Any] | None) -> tuple[str, str]:
    provider = row.get("state", "")
    kind = row["kind"]
    if provider in {"terminated", "deleted", "DELETED"}:
        return "deleted", f"AWS provider state is {provider}"
    if stack:
        owner_state = stack_lifecycle(stack.get("stack_status", ""))
        if owner_state == "exception":
            return "exception", f"owning stack is {stack.get('stack_status', '')}"
        if owner_state == "deleting":
            return "deleting", f"owning stack is {stack.get('stack_status', '')}"
    tags = parse_tags(row.get("all_tags", ""))
    if tags.get("aws:cloudformation:stack-name") and not stack:
        return "orphaned", "resource exists but its explicit CloudFormation owner does not"
    if provider.lower() in {"stopped", "stopping"}:
        return "stopped", f"AWS provider state is {provider}"
    if provider.lower() in {"shutting-down", "deleting"}:
        return "deleting", f"AWS provider state is {provider}"
    if kind == "instance" and provider not in {"running", "pending"}:
        return "unresolved", f"unexpected EC2 state {provider!r}"
    return "active", f"resource exists; AWS provider state is {provider or 'exists'}"


def canonical_resource(raw: str) -> str:
    if raw.startswith("arn:"):
        if "/" in raw:
            return raw.rsplit("/", 1)[1]
        return raw.rsplit(":", 1)[1]
    return raw


def billed_kind(service: str, raw: str) -> str | None:
    rid = canonical_resource(raw)
    if service == "Amazon Elastic Compute Cloud - Compute" and re.fullmatch(r"i-[0-9a-f]+", rid):
        return "instance"
    if service == "Amazon FSx" and re.fullmatch(r"fs-[0-9a-f]+", rid):
        return "file_system"
    if service == "Amazon Relational Database Service" and (":db:" in raw or ":cluster:" in raw):
        return "db_instance" if ":db:" in raw else "db_cluster"
    if service == "Amazon Simple Storage Service" and raw and not raw.startswith("arn:"):
        return "bucket"
    if service == "Amazon Elastic Load Balancing" and raw.startswith("arn:aws:elasticloadbalancing:"):
        return "load_balancer"
    if service in {"EC2 - Other", "Amazon Virtual Private Cloud"}:
        if re.fullmatch(r"vol-[0-9a-f]+", rid):
            return "volume"
        if re.fullmatch(r"snap-[0-9a-f]+", rid):
            return "snapshot"
        if re.fullmatch(r"eipalloc-[0-9a-f]+", rid):
            return "elastic_ip"
        if re.fullmatch(r"nat-[0-9a-f]+", rid):
            return "nat_gateway"
        if re.fullmatch(r"i-[0-9a-f]+", rid):
            return "instance"
    return None


def refresh_inventory(regions: list[str]) -> list[dict[str, Any]]:
    spec = importlib.util.spec_from_file_location("audit_collector", ROOT / "scripts" / "collect_lsmc_aws_readonly_audit.py")
    if spec is None or spec.loader is None:
        raise SystemExit("cannot load the existing read-only inventory collector")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    inventory: list[dict[str, Any]] = []
    for index, region in enumerate(regions, 1):
        print(f"refresh inventory {index}/{len(regions)} {region}", flush=True)
        module.inventory_region(region, inventory)
    module.inventory_s3(inventory)
    command_records.extend(module.command_records)
    return inventory


def main() -> None:
    regions = json.loads((DATA / "enabled_regions.json").read_text())
    identity, _ = aws(["sts", "get-caller-identity"], "us-west-2")
    if (identity or {}).get("Account") != ACCOUNT_ID:
        raise SystemExit(f"refusing unexpected AWS account {(identity or {}).get('Account')}")

    current_inventory = refresh_inventory(regions)
    write_csv(DATA / "lifecycle_current_inventory.csv", current_inventory)
    write_json(RAW / "lifecycle_current_inventory.json", current_inventory)

    stack_rows: list[dict[str, Any]] = []
    stack_summaries: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for index, region in enumerate(regions, 1):
        print(f"cloudformation {index}/{len(regions)} {region}", flush=True)
        payload, _ = aws(["cloudformation", "list-stacks"], region)
        for item in (payload or {}).get("StackSummaries", []):
            row = {
                "region": region, "stack_name": item.get("StackName", ""),
                "stack_id": item.get("StackId", ""), "stack_status": item.get("StackStatus", ""),
                "lifecycle_status": stack_lifecycle(item.get("StackStatus", "")),
                "creation_time": item.get("CreationTime", ""), "deletion_time": item.get("DeletionTime", ""),
                "last_updated_time": item.get("LastUpdatedTime", ""),
                "status_reason": item.get("StackStatusReason", ""),
            }
            stack_rows.append(row)
            stack_summaries[(region, row["stack_name"])].append(row)
    write_csv(DATA / "lifecycle_cloudformation_stacks.csv", stack_rows)

    def owner_stack(region: str, name: str) -> dict[str, Any] | None:
        candidates = stack_summaries.get((region, name), [])
        live = [x for x in candidates if x["stack_status"] != "DELETE_COMPLETE"]
        if live:
            return sorted(live, key=lambda x: x.get("last_updated_time") or x.get("creation_time") or "", reverse=True)[0]
        return None

    live_clusters: dict[tuple[str, str], dict[str, Any]] = {}
    unsupported_pcluster_regions: list[str] = []
    for index, region in enumerate(regions, 1):
        print(f"parallelcluster {index}/{len(regions)} {region}", flush=True)
        next_token = ""
        while True:
            args = ["list-clusters"]
            if next_token:
                args.extend(["--next-token", next_token])
            payload, record = pcluster(args, region, required=False)
            if payload is None:
                if "invalid or unsupported region" in record.get("stdout", ""):
                    unsupported_pcluster_regions.append(region)
                    break
                print(json.dumps(record, indent=2), file=sys.stderr)
                raise SystemExit(record["returncode"])
            for cluster in (payload or {}).get("clusters", []):
                live_clusters[(region, cluster["clusterName"])] = cluster
            next_token = (payload or {}).get("nextToken", "")
            if not next_token:
                break

    for (region, name), cluster in live_clusters.items():
        if cluster.get("clusterStatus") in {"CREATE_COMPLETE", "UPDATE_COMPLETE"}:
            fleet, record = pcluster(["describe-compute-fleet", "--cluster-name", name], region, required=False)
            cluster["computeFleetStatus"] = (fleet or {}).get("status", "")
            cluster["computeFleetError"] = record.get("stderr", "") if fleet is None else ""
        else:
            cluster["computeFleetStatus"] = "not queried while cluster is " + cluster.get("clusterStatus", "")

    inventory_by_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
    inventory_by_arn: dict[str, dict[str, Any]] = {}
    resource_rows: list[dict[str, Any]] = []
    for row in current_inventory:
        inventory_by_id[row["resource_id"]].append(row)
        if row.get("arn"):
            inventory_by_arn[row["arn"]] = row
        tags = parse_tags(row.get("all_tags", ""))
        stack_name = tags.get("aws:cloudformation:stack-name", "")
        stack = owner_stack(row["region"], stack_name) if stack_name else None
        status, evidence = current_resource_lifecycle(row, stack)
        cluster_name = tags.get("parallelcluster:cluster-name") or tags.get("aws-parallelcluster-clustername", "")
        resource_rows.append({
            "record_scope": "current_inventory", "service": row["service"], "kind": row["kind"],
            "region": row["region"], "resource_id": row["resource_id"], "arn": row.get("arn", ""),
            "name": row.get("name", ""), "july_cost_usd": 0.0, "lifecycle_status": status,
            "provider_state": row.get("state", "") or "exists", "owner_stack": stack_name,
            "owner_stack_status": stack.get("stack_status", "") if stack else ("absent" if stack_name else ""),
            "owner_cluster": cluster_name, "classification_evidence": evidence,
            "classification_confidence": "high",
        })

    billed_cost: dict[tuple[str, str], float] = defaultdict(float)
    for row in read_csv(DATA / "resource_daily.csv"):
        billed_cost[(row["service"], row["resource_id"])] += float(row["cost_usd"])

    current_keys: dict[tuple[str, str], dict[str, Any]] = {}
    for row in resource_rows:
        current_keys[(row["service"], row["resource_id"])] = row
        if row["arn"]:
            current_keys[(row["service"], row["arn"])] = row

    for (service, raw_id), cost in billed_cost.items():
        rid = canonical_resource(raw_id)
        inv = inventory_by_arn.get(raw_id)
        if inv is None:
            matches = inventory_by_id.get(rid, [])
            inv = matches[0] if len(matches) == 1 else None
        if inv is not None:
            target = next(x for x in resource_rows if x["region"] == inv["region"] and x["resource_id"] == inv["resource_id"] and x["kind"] == inv["kind"])
            target["record_scope"] = "current_inventory_and_billed"
            target["july_cost_usd"] += cost
            continue
        kind = billed_kind(service, raw_id)
        if kind:
            lifecycle = "deleted"
            evidence = "billed in July but absent from the refreshed all-region direct inventory"
            confidence = "high"
        else:
            lifecycle = "unresolved"
            evidence = "Cost Explorer identifier is not a directly enumerable resource type in this audit"
            confidence = "low"
        region = ""
        if raw_id.startswith("arn:"):
            parts = raw_id.split(":")
            region = parts[3] if len(parts) > 3 else ""
        resource_rows.append({
            "record_scope": "billed_history", "service": service, "kind": kind or "billing_identifier",
            "region": region or "unknown", "resource_id": rid, "arn": raw_id if raw_id.startswith("arn:") else "",
            "name": "", "july_cost_usd": round(cost, 8), "lifecycle_status": lifecycle,
            "provider_state": "absent" if lifecycle == "deleted" else "not directly enumerable",
            "owner_stack": "", "owner_stack_status": "", "owner_cluster": "",
            "classification_evidence": evidence, "classification_confidence": confidence,
        })

    resource_rows.sort(key=lambda x: (x["lifecycle_status"], -float(x["july_cost_usd"]), x["service"], x["resource_id"]))
    write_csv(DATA / "lifecycle_resources.csv", resource_rows)

    cost_clusters: dict[str, float] = defaultdict(float)
    for row in read_csv(DATA / "ec2_cluster_mtd.csv"):
        cost_clusters[row["tag_cluster"] or "blank/unattributed"] += float(row["cost_usd"])
    current_tagged_clusters: set[tuple[str, str]] = set()
    for row in current_inventory:
        tags = parse_tags(row.get("all_tags", ""))
        name = tags.get("parallelcluster:cluster-name") or tags.get("aws-parallelcluster-clustername")
        if name:
            current_tagged_clusters.add((row["region"], name))

    cluster_names = set(cost_clusters)
    cluster_names.update(name for _, name in live_clusters)
    cluster_names.update(name for _, name in current_tagged_clusters)
    cluster_rows: list[dict[str, Any]] = []
    for name in sorted(cluster_names):
        if name == "blank/unattributed":
            cluster_rows.append({
                "cluster": name, "region": "unknown", "july_cost_usd": round(cost_clusters[name], 2),
                "lifecycle_status": "unresolved", "cluster_provider_status": "not a cluster identity",
                "compute_fleet_status": "", "cloudformation_status": "", "cluster_exists": False,
                "current_tagged_resource_count": 0, "classification_evidence": "blank cost-allocation tag",
            })
            continue
        matches = [(region, cluster) for (region, cluster_name), cluster in live_clusters.items() if cluster_name == name]
        tagged = [(region, cluster_name) for region, cluster_name in current_tagged_clusters if cluster_name == name]
        stack_history = [x for x in stack_rows if x["stack_name"] == name]
        if matches:
            for region, cluster in matches:
                provider = cluster.get("clusterStatus", "")
                fleet = cluster.get("computeFleetStatus", "")
                if provider == "DELETE_IN_PROGRESS":
                    lifecycle = "deleting"
                elif provider in FAILURE_STATES or provider.endswith("_FAILED"):
                    lifecycle = "exception"
                elif provider.endswith("_IN_PROGRESS"):
                    lifecycle = "provisioning_or_updating"
                elif fleet in {"STOPPED", "STOPPING"}:
                    lifecycle = "stopped"
                else:
                    lifecycle = "active"
                cluster_rows.append({
                    "cluster": name, "region": region, "july_cost_usd": round(cost_clusters.get(name, 0.0), 2),
                    "lifecycle_status": lifecycle, "cluster_provider_status": provider,
                    "compute_fleet_status": fleet, "cloudformation_status": cluster.get("cloudformationStackStatus", ""),
                    "cluster_exists": True,
                    "current_tagged_resource_count": sum(1 for x in current_inventory if x["region"] == region and name in parse_tags(x.get("all_tags", "")).values()),
                    "classification_evidence": "live ParallelCluster list-clusters result",
                })
        else:
            deleted = sorted([x for x in stack_history if x["stack_status"] == "DELETE_COMPLETE"], key=lambda x: x.get("deletion_time") or "", reverse=True)
            failed = [x for x in stack_history if stack_lifecycle(x["stack_status"]) == "exception"]
            if failed:
                item = failed[0]
                lifecycle, provider, region = "exception", item["stack_status"], item["region"]
                evidence = "ParallelCluster absent; same-name CloudFormation stack has failure status"
            elif deleted:
                item = deleted[0]
                lifecycle, provider, region = "deleted", "absent", item["region"]
                evidence = f"ParallelCluster absent; CloudFormation {item['stack_status']} at {item['deletion_time']}"
            elif tagged:
                region = tagged[0][0]
                lifecycle, provider = "deleted", "absent"
                evidence = "ParallelCluster and same-name live stack absent; tagged residual resources remain"
            else:
                region = "unknown"
                lifecycle, provider = "deleted", "absent"
                evidence = "July-billed cluster is absent from all live ParallelCluster and CloudFormation inventories"
            cluster_rows.append({
                "cluster": name, "region": region, "july_cost_usd": round(cost_clusters.get(name, 0.0), 2),
                "lifecycle_status": lifecycle, "cluster_provider_status": provider,
                "compute_fleet_status": "", "cloudformation_status": provider if provider not in {"absent"} else (deleted[0]["stack_status"] if deleted else "absent"),
                "cluster_exists": False, "current_tagged_resource_count": len(tagged),
                "classification_evidence": evidence,
            })
    cluster_rows.sort(key=lambda x: (-float(x["july_cost_usd"]), x["cluster"]))
    write_csv(DATA / "lifecycle_clusters.csv", cluster_rows)

    exception_rows: list[dict[str, Any]] = []
    for row in stack_rows:
        if row["lifecycle_status"] == "exception":
            exception_rows.append({"type": "cloudformation_stack", **row})
    for row in resource_rows:
        if row["lifecycle_status"] in {"exception", "exception_recovered", "orphaned"}:
            exception_rows.append({"type": "resource", **row})
    write_csv(DATA / "lifecycle_exceptions_and_orphans.csv", exception_rows)

    jemx3_tagged, _ = aws([
        "resourcegroupstaggingapi", "get-resources", "--tag-filters",
        "Key=parallelcluster:cluster-name,Values=jemx3",
    ], "us-west-2")
    jemx3_pcluster, jemx3_pcluster_record = pcluster(["describe-cluster", "--cluster-name", "jemx3"], "us-west-2", required=False)
    jemx3_stack, jemx3_stack_record = aws(["cloudformation", "describe-stacks", "--stack-name", "jemx3"], "us-west-2", required=False)
    jemx3_rows = [x for x in cluster_rows if x["cluster"] == "jemx3"]
    jemx3_history = [x for x in stack_rows if x["stack_name"] == "jemx3"]
    jemx3_related: list[dict[str, Any]] = []
    for item in (jemx3_tagged or {}).get("ResourceTagMappingList", []):
        arn = item.get("ResourceARN", "")
        rid = canonical_resource(arn)
        if ":volume/" in arn:
            exists = bool(inventory_by_id.get(rid))
            lifecycle = "orphaned" if exists else "deleted"
            evidence = "refreshed EBS inventory contains the volume after owner deletion" if exists else "absent from refreshed all-region EBS inventory; tag index entry is stale"
        elif ":association/" in arn and ":fsx:" in arn:
            association_id = rid
            association_payload, _ = aws([
                "fsx", "describe-data-repository-associations", "--association-ids", association_id,
            ], "us-west-2")
            exists = bool((association_payload or {}).get("Associations"))
            lifecycle = "orphaned" if exists else "deleted"
            evidence = "FSx association exists after owner deletion" if exists else "FSx returned no current association; tag index entry is stale"
        elif ":logs:" in arn and ":log-group:" in arn:
            log_name = arn.split(":log-group:", 1)[1].removesuffix(":*")
            log_payload, _ = aws([
                "logs", "describe-log-groups", "--log-group-name-prefix", log_name,
            ], "us-west-2")
            exact = [x for x in (log_payload or {}).get("logGroups", []) if x.get("logGroupName") == log_name]
            exists = bool(exact)
            lifecycle = "orphaned" if exists else "deleted"
            evidence = "log group exists after owning cluster stack DELETE_COMPLETE" if exists else "log group absent; tag index entry is stale"
        else:
            exists = False
            lifecycle = "unresolved"
            evidence = "resource type is not directly resolved by the lifecycle collector"
        jemx3_related.append({
            "resource_arn": arn, "resource_id": rid, "exists": exists,
            "lifecycle_status": lifecycle, "classification_evidence": evidence,
        })
    write_csv(DATA / "jemx3_related_resources.csv", jemx3_related)
    for item in jemx3_related:
        if item["lifecycle_status"] != "orphaned":
            continue
        orphan = {
            "record_scope": "tagged_residual", "service": "CloudWatch Logs", "kind": "log_group",
            "region": "us-west-2", "resource_id": item["resource_id"], "arn": item["resource_arn"],
            "name": item["resource_id"], "july_cost_usd": 0.0, "lifecycle_status": "orphaned",
            "provider_state": "exists", "owner_stack": "jemx3", "owner_stack_status": "DELETE_COMPLETE",
            "owner_cluster": "jemx3", "classification_evidence": item["classification_evidence"],
            "classification_confidence": "high",
        }
        resource_rows.append(orphan)
        exception_rows.append({"type": "resource", **orphan})
    resource_rows.sort(key=lambda x: (x["lifecycle_status"], -float(x["july_cost_usd"]), x["service"], x["resource_id"]))
    write_csv(DATA / "lifecycle_resources.csv", resource_rows)
    write_csv(DATA / "lifecycle_exceptions_and_orphans.csv", exception_rows)
    write_json(DATA / "jemx3_lifecycle_evidence.json", {
        "generated_at": GENERATED_AT,
        "classification": jemx3_rows,
        "parallelcluster_describe": jemx3_pcluster,
        "parallelcluster_error": jemx3_pcluster_record.get("stderr", ""),
        "current_cloudformation_stack": jemx3_stack,
        "current_cloudformation_error": jemx3_stack_record.get("stderr", ""),
        "cloudformation_history": jemx3_history,
        "current_direct_inventory_resources": [x for x in resource_rows if x.get("owner_cluster") == "jemx3"],
        "tag_index_entries": (jemx3_tagged or {}).get("ResourceTagMappingList", []),
        "resolved_tag_index_entries": jemx3_related,
        "explicit_managed_fsx": {"id": "fs-07fb3448c1cb30c1c", "current_state": "absent"},
        "note": "Every tag-index entry is resolved by a current service-specific read where supported; tag-index presence alone is not treated as proof of existence.",
    })

    read_prefixes = ("describe", "get", "list", "lookup", "search")
    suspicious: list[dict[str, Any]] = []
    for record in command_records:
        parts = record["command"].split()
        executable = Path(parts[0]).name if parts else ""
        if executable == "aws":
            operation = parts[2] if len(parts) > 2 else ""
        elif executable == "pcluster":
            operation = parts[1] if len(parts) > 1 else ""
        else:
            operation = ""
        if not operation.startswith(read_prefixes):
            suspicious.append({**record, "parsed_operation": operation})
    if suspicious:
        write_json(DATA / "lifecycle_suspicious_commands.json", suspicious)
        raise SystemExit("read-only command verification failed")
    write_json(DATA / "lifecycle_command_records.json", command_records)
    summary = {
        "generated_at": GENERATED_AT, "profile": PROFILE, "account_id": ACCOUNT_ID,
        "enabled_regions": len(regions), "current_inventory_rows": len(current_inventory),
        "billed_unique_identifiers": len(billed_cost), "lifecycle_resource_rows": len(resource_rows),
        "cluster_rows": len(cluster_rows), "cloudformation_stack_rows": len(stack_rows),
        "parallelcluster_unsupported_regions": unsupported_pcluster_regions,
        "lifecycle_counts": dict(sorted({s: sum(1 for x in resource_rows if x["lifecycle_status"] == s) for s in {x["lifecycle_status"] for x in resource_rows}}.items())),
        "cluster_lifecycle_counts": dict(sorted({s: sum(1 for x in cluster_rows if x["lifecycle_status"] == s) for s in {x["lifecycle_status"] for x in cluster_rows}}.items())),
        "cloudformation_lifecycle_counts": dict(sorted({s: sum(1 for x in stack_rows if x["lifecycle_status"] == s) for s in {x["lifecycle_status"] for x in stack_rows}}.items())),
        "exception_orphan_rows": len(exception_rows), "command_count": len(command_records),
        "command_error_count": sum(1 for x in command_records if x["returncode"] != 0),
        "read_only_command_verification": "passed",
    }
    write_json(DATA / "lifecycle_summary.json", summary)
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
