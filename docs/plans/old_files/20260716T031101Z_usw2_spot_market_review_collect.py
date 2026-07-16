#!/usr/bin/env python3
"""Collect reproducible, read-only evidence for the us-west-2 NVMe Spot review."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import statistics
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Any

import yaml


REGION = "us-west-2"
PROFILE = "lsmc"
PARTITIONS = ("i96nvme", "i128nvme", "i192nvme", "i384nvme", "i192hugenvme")
TARGET_VCPU = {
    "i96nvme": 8 * 96,
    "i128nvme": 8 * 128,
    "i192nvme": 8 * 192,
    "i384nvme": 8 * 384,
    "i192hugenvme": 8 * 192,
}


def utc(value: dt.datetime) -> str:
    return value.astimezone(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def aws_json(*args: str) -> dict[str, Any]:
    command = [
        "aws",
        *args,
        "--region",
        REGION,
        "--profile",
        PROFILE,
        "--output",
        "json",
    ]
    env = dict(os.environ)
    env["AWS_PAGER"] = ""
    completed = subprocess.run(command, check=True, capture_output=True, text=True, env=env)
    return json.loads(completed.stdout)


def load_configured(
    repo: Path,
) -> tuple[
    dict[str, dict[str, list[str]]],
    dict[str, dict[str, list[dict[str, Any]]]],
    dict[str, str],
]:
    configured: dict[str, dict[str, list[str]]] = {}
    resources: dict[str, dict[str, list[dict[str, Any]]]] = {}
    templates: dict[str, str] = {}
    for suffix in "abcd":
        az = f"us-west-2{suffix}"
        path = repo / "config" / "day_cluster" / "intel" / REGION / az / f"prod_cluster_intel_spot_{az}.yaml"
        data = yaml.safe_load(path.read_text())
        queues = {queue["Name"]: queue for queue in data["Scheduling"]["SlurmQueues"]}
        configured[az] = {}
        resources[az] = {}
        templates[az] = str(path.relative_to(repo))
        for partition in PARTITIONS:
            queue = queues[partition]
            instance_types = {
                instance["InstanceType"]
                for resource in queue["ComputeResources"]
                for instance in resource["Instances"]
            }
            configured[az][partition] = sorted(instance_types)
            resources[az][partition] = [
                {
                    "name": resource["Name"],
                    "instance_types": sorted(
                        {instance["InstanceType"] for instance in resource["Instances"]}
                    ),
                }
                for resource in queue["ComputeResources"]
            ]
    return configured, resources, templates


def collect_cloudtrail(start: str, end: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    next_token: str | None = None
    while True:
        args = [
            "cloudtrail",
            "lookup-events",
            "--lookup-attributes",
            "AttributeKey=EventName,AttributeValue=RunInstances",
            "--start-time",
            start,
            "--end-time",
            end,
            "--max-results",
            "50",
        ]
        if next_token:
            args.extend(["--next-token", next_token])
        response = aws_json(*args)
        events.extend(response.get("Events", []))
        next_token = response.get("NextToken")
        if not next_token:
            return events


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--end-time", default="2026-07-16T03:11:01Z")
    args = parser.parse_args()

    repo = args.repo.resolve()
    end_dt = dt.datetime.fromisoformat(args.end_time.replace("Z", "+00:00"))
    start_dt = end_dt - dt.timedelta(hours=72)
    start, end = utc(start_dt), utc(end_dt)
    configured, resources, templates = load_configured(repo)
    all_types = sorted({item for by_partition in configured.values() for types in by_partition.values() for item in types})

    identity = aws_json("sts", "get-caller-identity")
    az_response = aws_json("ec2", "describe-availability-zones", "--zone-names", *sorted(configured))
    az_ids = {item["ZoneName"]: item["ZoneId"] for item in az_response["AvailabilityZones"]}

    offered: dict[str, list[str]] = {}
    for az in sorted(configured):
        response = aws_json(
            "ec2",
            "describe-instance-type-offerings",
            "--location-type",
            "availability-zone",
            "--filters",
            f"Name=location,Values={az}",
        )
        available = {item["InstanceType"] for item in response["InstanceTypeOfferings"]}
        offered[az] = sorted(available.intersection(all_types))

    price_response = aws_json(
        "ec2",
        "describe-spot-price-history",
        "--start-time",
        start,
        "--end-time",
        end,
        "--product-descriptions",
        "Linux/UNIX",
        "--instance-types",
        *all_types,
    )
    prices: dict[tuple[str, str], list[tuple[str, float]]] = defaultdict(list)
    for item in price_response["SpotPriceHistory"]:
        key = (item["AvailabilityZone"], item["InstanceType"])
        if key[0] in configured:
            prices[key].append((item["Timestamp"], float(item["SpotPrice"])))

    price_summary: dict[str, dict[str, dict[str, Any]]] = {az: {} for az in configured}
    for az in sorted(configured):
        for instance_type in all_types:
            observations = sorted(prices.get((az, instance_type), []), key=lambda item: item[0])
            if not observations:
                continue
            values = [value for _, value in observations]
            price_summary[az][instance_type] = {
                "observations": len(values),
                "current_usd_per_hour": observations[-1][1],
                "current_effective_at": observations[-1][0],
                "min_usd_per_hour": min(values),
                "median_usd_per_hour": statistics.median(values),
                "max_usd_per_hour": max(values),
                "range_usd_per_hour": max(values) - min(values),
            }

    resource_bid_summary: dict[str, dict[str, list[dict[str, Any]]]] = {
        az: {} for az in configured
    }
    type_bid_assessment: dict[str, dict[str, dict[str, dict[str, Any]]]] = {
        az: {} for az in configured
    }
    for az in sorted(configured):
        for partition in PARTITIONS:
            resource_bid_summary[az][partition] = []
            for resource in resources[az][partition]:
                current_prices = [
                    price_summary[az][instance_type]["current_usd_per_hour"]
                    for instance_type in resource["instance_types"]
                ]
                median_price = statistics.median(current_prices)
                uncapped_bid = round(median_price * 1.70, 4)
                final_bid = round(min(uncapped_bid, 9.99), 4)
                resource_bid_summary[az][partition].append(
                    {
                        **resource,
                        "current_median_spot_price": median_price,
                        "spot_cost_limit_pct": 1.70,
                        "uncapped_bid": uncapped_bid,
                        "global_spot_max_cost": 9.99,
                        "final_bid": final_bid,
                    }
                )
            type_bid_assessment[az][partition] = {}
            for instance_type in configured[az][partition]:
                containing = [
                    resource
                    for resource in resource_bid_summary[az][partition]
                    if instance_type in resource["instance_types"]
                ]
                current_price = price_summary[az][instance_type]["current_usd_per_hour"]
                highest_bid = max(resource["final_bid"] for resource in containing)
                type_bid_assessment[az][partition][instance_type] = {
                    "current_usd_per_hour": current_price,
                    "highest_containing_resource_bid": highest_bid,
                    "price_above_all_containing_resource_bids": current_price > highest_bid,
                    "containing_resources": [
                        {"name": resource["name"], "final_bid": resource["final_bid"]}
                        for resource in containing
                    ],
                }

    placement_scores: dict[str, dict[str, dict[str, Any]]] = {az: {} for az in configured}
    score_cache: dict[tuple[tuple[str, ...], int], dict[str, int]] = {}
    for az in sorted(configured):
        for partition in PARTITIONS:
            types = tuple(configured[az][partition])
            key = (types, TARGET_VCPU[partition])
            if key not in score_cache:
                response = aws_json(
                    "ec2",
                    "get-spot-placement-scores",
                    "--instance-types",
                    *types,
                    "--target-capacity",
                    str(TARGET_VCPU[partition]),
                    "--target-capacity-unit-type",
                    "vcpu",
                    "--single-availability-zone",
                    "--region-names",
                    REGION,
                )
                score_cache[key] = {
                    item["AvailabilityZoneId"]: item["Score"]
                    for item in response.get("SpotPlacementScores", [])
                }
            placement_scores[az][partition] = {
                "score": score_cache[key].get(az_ids[az]),
                "target_vcpu": TARGET_VCPU[partition],
                "target_node_equivalent": 8,
                "assumed_allocation_strategy": "capacity-optimized",
            }

    raw_cloudtrail = collect_cloudtrail(start, end)
    relevant = set(all_types)
    launch_events: list[dict[str, Any]] = []
    launch_summary: dict[str, dict[str, dict[str, Any]]] = {
        az: {instance_type: defaultdict(int) for instance_type in all_types} for az in configured
    }
    for event in raw_cloudtrail:
        detail = json.loads(event["CloudTrailEvent"])
        request = detail.get("requestParameters") or {}
        market = request.get("instanceMarketOptions") or {}
        instance_type = request.get("instanceType")
        az = request.get("availabilityZone")
        if market.get("marketType") != "spot" or instance_type not in relevant or az not in configured:
            continue
        error_code = detail.get("errorCode")
        response = detail.get("responseElements") or {}
        launched = len(((response.get("instancesSet") or {}).get("items") or []))
        outcome = "success" if not error_code else "error"
        if error_code in {"Server.InsufficientInstanceCapacity", "InsufficientInstanceCapacity"}:
            category = "insufficient_capacity"
        elif error_code == "Client.SpotMaxPriceTooLow":
            category = "spot_max_price_too_low"
        elif error_code:
            category = "other_error"
        else:
            category = "success"
        summary = launch_summary[az][instance_type]
        summary["events"] += 1
        summary[f"{category}_events"] += 1
        summary["launched_instances"] += launched
        launch_events.append(
            {
                "event_time": detail.get("eventTime") or str(event.get("EventTime")),
                "availability_zone": az,
                "instance_type": instance_type,
                "outcome": outcome,
                "category": category,
                "launched_instances": launched,
                "error_code": error_code,
                "error_message": detail.get("errorMessage"),
                "spot_max_price": ((market.get("spotOptions") or {}).get("maxPrice")),
                "client_token": request.get("clientToken"),
            }
        )

    normalized_launch_summary: dict[str, dict[str, dict[str, int]]] = {az: {} for az in configured}
    for az in sorted(configured):
        for instance_type in all_types:
            summary = launch_summary[az][instance_type]
            if summary:
                normalized_launch_summary[az][instance_type] = dict(sorted(summary.items()))

    partition_summary: dict[str, dict[str, dict[str, Any]]] = {az: {} for az in configured}
    for az in sorted(configured):
        offered_set = set(offered[az])
        for partition in PARTITIONS:
            types = configured[az][partition]
            partition_summary[az][partition] = {
                "configured_type_count": len(types),
                "offered_type_count": sum(instance_type in offered_set for instance_type in types),
                "types_not_offered": [instance_type for instance_type in types if instance_type not in offered_set],
                "types_without_price_history": [
                    instance_type for instance_type in types if instance_type not in price_summary[az]
                ],
                "placement_score": placement_scores[az][partition]["score"],
                "launch_success_instances": sum(
                    normalized_launch_summary[az].get(instance_type, {}).get("launched_instances", 0)
                    for instance_type in types
                ),
                "insufficient_capacity_events": sum(
                    normalized_launch_summary[az].get(instance_type, {}).get("insufficient_capacity_events", 0)
                    for instance_type in types
                ),
                "spot_max_price_too_low_events": sum(
                    normalized_launch_summary[az].get(instance_type, {}).get("spot_max_price_too_low_events", 0)
                    for instance_type in types
                ),
                "types_above_today_computed_bid": [
                    instance_type
                    for instance_type in types
                    if type_bid_assessment[az][partition][instance_type][
                        "price_above_all_containing_resource_bids"
                    ]
                ],
            }

    snapshot = {
        "metadata": {
            "schema_version": 1,
            "collected_at": utc(dt.datetime.now(dt.timezone.utc)),
            "window_start": start,
            "window_end": end,
            "window_hours": 72,
            "profile": PROFILE,
            "region": REGION,
            "account_id": identity["Account"],
            "arn": identity["Arn"],
            "read_only": True,
        },
        "templates": templates,
        "availability_zone_ids": az_ids,
        "partitions": list(PARTITIONS),
        "configured": configured,
        "compute_resources": resources,
        "offered": offered,
        "price_history_summary": price_summary,
        "resource_bid_summary": resource_bid_summary,
        "type_bid_assessment": type_bid_assessment,
        "placement_scores": placement_scores,
        "cloudtrail": {
            "runinstances_events_scanned": len(raw_cloudtrail),
            "relevant_spot_events": len(launch_events),
            "summary": normalized_launch_summary,
            "events": sorted(launch_events, key=lambda item: item["event_time"]),
        },
        "partition_summary": partition_summary,
        "interpretation": {
            "price_history": "Spot price history is market-price evidence, not proof of launch capacity.",
            "placement_score": "Partition-pool directional signal on a 1-10 scale. It is not a guarantee or a per-type score, and this collection uses AWS's capacity-optimized scoring assumption while the templates use price-capacity-optimized.",
            "cloudtrail": "Account-observed launch evidence is workload- and retry-correlated, not a controlled market sample.",
        },
        "sources": [
            {
                "id": "templates",
                "kind": "local configuration",
                "description": "Current working-tree Intel Spot ParallelCluster YAMLs",
            },
            {
                "id": "aws-offerings",
                "kind": "AWS EC2 API",
                "operation": "DescribeInstanceTypeOfferings",
            },
            {
                "id": "aws-price-history",
                "kind": "AWS EC2 API",
                "operation": "DescribeSpotPriceHistory",
            },
            {
                "id": "aws-placement-scores",
                "kind": "AWS EC2 API",
                "operation": "GetSpotPlacementScores",
            },
            {
                "id": "aws-cloudtrail",
                "kind": "AWS CloudTrail API",
                "operation": "LookupEvents for RunInstances",
            },
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "output": str(args.output),
        "configured_instance_types": len(all_types),
        "price_history_records": len(price_response["SpotPriceHistory"]),
        "cloudtrail_events_scanned": len(raw_cloudtrail),
        "relevant_spot_events": len(launch_events),
    }, indent=2))


if __name__ == "__main__":
    main()
