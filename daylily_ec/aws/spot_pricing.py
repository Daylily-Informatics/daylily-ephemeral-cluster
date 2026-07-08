"""Spot-price bid generation for ParallelCluster compute resources."""

from __future__ import annotations

import json
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap

SPOT_PRICE_SUMMARY_SCHEMA_VERSION = "dyec.spot_price_summary.v1"

DEFAULT_GLOBAL_SPOT_MAX_COST: float = 7.50
MAX_GLOBAL_SPOT_MAX_COST: float = 10.00
DEFAULT_SPOT_COST_LIMIT_PCT: float = 1.2
MIN_SPOT_COST_LIMIT_PCT: float = 1.0
MAX_SPOT_COST_LIMIT_PCT: float = 1.4
DEFAULT_WRITE_SPOT_PRICING_WARN_THRESHOLD: float = 6.00


def validate_spot_pricing_limits(
    *,
    global_spot_max_cost: float = DEFAULT_GLOBAL_SPOT_MAX_COST,
    spot_cost_limit_pct: float = DEFAULT_SPOT_COST_LIMIT_PCT,
    write_spot_pricing_warn_threshold: float = DEFAULT_WRITE_SPOT_PRICING_WARN_THRESHOLD,
) -> tuple[float, float, float]:
    """Validate and normalize DYEC create spot pricing limits."""

    try:
        global_max = float(global_spot_max_cost)
        pct = float(spot_cost_limit_pct)
        warn_threshold = float(write_spot_pricing_warn_threshold)
    except (TypeError, ValueError) as exc:
        raise ValueError("Spot pricing limits must be numeric.") from exc

    if global_max <= 0 or global_max > MAX_GLOBAL_SPOT_MAX_COST:
        raise ValueError(
            "--global-spot-max-cost must be > 0 and <= "
            f"{MAX_GLOBAL_SPOT_MAX_COST:.2f}; got {global_max:.4f}."
        )
    if pct < MIN_SPOT_COST_LIMIT_PCT or pct > MAX_SPOT_COST_LIMIT_PCT:
        raise ValueError(
            "--spot-cost-limit-pct must be between "
            f"{MIN_SPOT_COST_LIMIT_PCT:.1f} and {MAX_SPOT_COST_LIMIT_PCT:.1f}; "
            f"got {pct:.4f}."
        )
    if warn_threshold <= 0:
        raise ValueError(
            "--write-spot-pricing-warn-threshold must be > 0; "
            f"got {warn_threshold:.4f}."
        )
    return global_max, pct, warn_threshold


def get_spot_price(ec2_client: Any, instance_type: str, az: str) -> float:
    """Return the latest Linux/UNIX spot price for one instance type and AZ."""

    try:
        resp = ec2_client.describe_spot_price_history(
            InstanceTypes=[instance_type],
            AvailabilityZone=az,
            ProductDescriptions=["Linux/UNIX"],
            MaxResults=1,
        )
    except Exception as exc:
        raise RuntimeError(
            f"Spot price lookup failed for {instance_type} in {az}. "
            "Confirm the instance type is valid and ec2:DescribeSpotPriceHistory is allowed. "
            f"Detail: {exc}"
        ) from exc

    prices = resp.get("SpotPriceHistory", [])
    if not prices:
        raise RuntimeError(
            f"Spot price lookup returned no price history for {instance_type} in {az}."
        )

    try:
        return float(prices[0]["SpotPrice"])
    except (KeyError, ValueError, TypeError) as exc:
        raise RuntimeError(
            "Spot price lookup returned a non-numeric SpotPrice for "
            f"{instance_type} in {az}: {prices[0]!r}"
        ) from exc


def get_instance_vcpu_counts(ec2_client: Any, instance_types: Iterable[str]) -> dict[str, int]:
    """Return EC2 default vCPU counts for each instance type."""

    unique_instance_types = list(dict.fromkeys(instance_types))
    if not unique_instance_types:
        return {}

    try:
        resp = ec2_client.describe_instance_types(InstanceTypes=unique_instance_types)
    except Exception as exc:
        joined = ", ".join(unique_instance_types)
        raise RuntimeError(
            "Instance type vCPU lookup failed for "
            f"{joined}. Confirm ec2:DescribeInstanceTypes is allowed. Detail: {exc}"
        ) from exc

    counts: dict[str, int] = {}
    for item in resp.get("InstanceTypes", []) or []:
        instance_type = str(item.get("InstanceType") or "")
        vcpu_info = item.get("VCpuInfo") or {}
        try:
            vcpus = int(vcpu_info["DefaultVCpus"])
        except (KeyError, TypeError, ValueError) as exc:
            raise RuntimeError(
                f"Instance type vCPU lookup returned invalid VCpuInfo for {instance_type}: "
                f"{item!r}"
            ) from exc
        if vcpus <= 0:
            raise RuntimeError(
                f"Instance type vCPU lookup returned non-positive DefaultVCpus for "
                f"{instance_type}: {vcpus}"
            )
        counts[instance_type] = vcpus

    missing = sorted(set(unique_instance_types) - set(counts))
    if missing:
        raise RuntimeError(
            "Instance type vCPU lookup returned no details for: " + ", ".join(missing)
        )
    return counts


def calculate_compute_resource_spot_price(
    ec2_client: Any,
    resource_config: Dict[str, Any],
    az: str,
    *,
    global_spot_max_cost: float = DEFAULT_GLOBAL_SPOT_MAX_COST,
    spot_cost_limit_pct: float = DEFAULT_SPOT_COST_LIMIT_PCT,
    write_spot_pricing_warn_threshold: float = DEFAULT_WRITE_SPOT_PRICING_WARN_THRESHOLD,
) -> Optional[float]:
    """Return the capped spot bid for one compute resource using its own median."""

    global_max, pct, _warn_threshold = validate_spot_pricing_limits(
        global_spot_max_cost=global_spot_max_cost,
        spot_cost_limit_pct=spot_cost_limit_pct,
        write_spot_pricing_warn_threshold=write_spot_pricing_warn_threshold,
    )
    stats = _collect_resource_price_stats(ec2_client, resource_config, az)
    if stats is None:
        return None
    return _final_bid(
        reference_median=float(stats["raw_median_spot_price"]),
        spot_cost_limit_pct=pct,
        global_spot_max_cost=global_max,
    )


def apply_spot_to_queue(
    ec2_client: Any,
    queue_config: Dict[str, Any],
    az: str,
    *,
    global_spot_max_cost: float = DEFAULT_GLOBAL_SPOT_MAX_COST,
    spot_cost_limit_pct: float = DEFAULT_SPOT_COST_LIMIT_PCT,
    write_spot_pricing_warn_threshold: float = DEFAULT_WRITE_SPOT_PRICING_WARN_THRESHOLD,
) -> dict[str, Any]:
    """Set resource-specific ``SpotPrice`` values in one queue in place."""

    summary = _build_spot_price_summary(
        {"Scheduling": {"SlurmQueues": [queue_config]}},
        az,
        ec2_client,
        global_spot_max_cost=global_spot_max_cost,
        spot_cost_limit_pct=spot_cost_limit_pct,
        write_spot_pricing_warn_threshold=write_spot_pricing_warn_threshold,
    )
    return summary


def process_slurm_queues(
    config: Dict[str, Any],
    az: str,
    ec2_client: Any,
    *,
    global_spot_max_cost: float = DEFAULT_GLOBAL_SPOT_MAX_COST,
    spot_cost_limit_pct: float = DEFAULT_SPOT_COST_LIMIT_PCT,
    write_spot_pricing_warn_threshold: float = DEFAULT_WRITE_SPOT_PRICING_WARN_THRESHOLD,
) -> dict[str, Any]:
    """Process all Slurm queues in *config* and return a structured summary."""

    return _build_spot_price_summary(
        config,
        az,
        ec2_client,
        global_spot_max_cost=global_spot_max_cost,
        spot_cost_limit_pct=spot_cost_limit_pct,
        write_spot_pricing_warn_threshold=write_spot_pricing_warn_threshold,
    )


def apply_spot_prices(
    input_path: str,
    output_path: str,
    az: str,
    *,
    ec2_client: Any = None,
    profile: Optional[str] = None,
    global_spot_max_cost: float = DEFAULT_GLOBAL_SPOT_MAX_COST,
    spot_cost_limit_pct: float = DEFAULT_SPOT_COST_LIMIT_PCT,
    write_spot_pricing_warn_threshold: float = DEFAULT_WRITE_SPOT_PRICING_WARN_THRESHOLD,
    summary_output_path: str | Path | None = None,
) -> dict[str, Any]:
    """Read init-template YAML, set ``SpotPrice`` values, and write outputs."""

    global_max, pct, warn_threshold = validate_spot_pricing_limits(
        global_spot_max_cost=global_spot_max_cost,
        spot_cost_limit_pct=spot_cost_limit_pct,
        write_spot_pricing_warn_threshold=write_spot_pricing_warn_threshold,
    )
    if ec2_client is None:
        import boto3

        session_kw: Dict[str, str] = {}
        if profile:
            session_kw["profile_name"] = profile
        region = az[:-1]
        session_kw["region_name"] = region
        ec2_client = boto3.Session(**session_kw).client("ec2")

    yaml = YAML()
    yaml.preserve_quotes = True
    config = yaml.load(Path(input_path))

    summary = process_slurm_queues(
        config,
        az,
        ec2_client,
        global_spot_max_cost=global_max,
        spot_cost_limit_pct=pct,
        write_spot_pricing_warn_threshold=warn_threshold,
    )

    out_yaml = YAML()
    out_yaml.explicit_start = True
    out_yaml.explicit_end = True
    with open(output_path, "w", encoding="utf-8") as fh:
        out_yaml.dump(config, fh)

    if summary_output_path is not None:
        Path(summary_output_path).write_text(
            json.dumps(summary, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return summary


def _build_spot_price_summary(
    config: Dict[str, Any],
    az: str,
    ec2_client: Any,
    *,
    global_spot_max_cost: float,
    spot_cost_limit_pct: float,
    write_spot_pricing_warn_threshold: float,
) -> dict[str, Any]:
    queues = config.get("Scheduling", {}).get("SlurmQueues", []) or []
    resource_stats: dict[tuple[str, str], dict[str, Any]] = {}
    resource_refs: dict[tuple[str, str], Any] = {}

    for queue_index, queue in enumerate(queues):
        queue_name = str(queue.get("Name") or f"queue_{queue_index}")
        for resource_index, resource in enumerate(queue.get("ComputeResources", []) or []):
            resource_name = str(resource.get("Name") or f"resource_{resource_index}")
            stats = _collect_resource_price_stats(ec2_client, resource, az)
            if stats is None:
                raise RuntimeError(
                    f"Compute resource {queue_name}/{resource_name} has no Instances[].InstanceType."
                )
            resource_key = (queue_name, resource_name)
            resource_stats[resource_key] = stats
            resource_refs[resource_key] = resource

    resource_rows: list[dict[str, Any]] = []
    partition_accumulators: dict[str, dict[str, Any]] = {}

    for queue_index, queue in enumerate(queues):
        queue_name = str(queue.get("Name") or f"queue_{queue_index}")
        queue_rows: list[dict[str, Any]] = []
        for resource_index, resource in enumerate(queue.get("ComputeResources", []) or []):
            resource_name = str(resource.get("Name") or f"resource_{resource_index}")
            resource_key = (queue_name, resource_name)
            stats = resource_stats[resource_key]
            ref_key = _reference_key_for_resource(queue_name, resource_name)
            if ref_key not in resource_stats:
                raise RuntimeError(
                    "i384 reference spot data missing for "
                    f"{queue_name}/{resource_name}: expected {ref_key[0]}/{ref_key[1]}."
                )
            ref_stats = resource_stats[ref_key]
            reference_source = "self" if ref_key == resource_key else "i192_reference"
            reference_median = float(ref_stats["raw_median_spot_price"])
            uncapped_bid = _round_price(reference_median * spot_cost_limit_pct)
            final_bid = min(uncapped_bid, _round_price(global_spot_max_cost))
            final_bid = _round_price(final_bid)
            global_limiter_applied = uncapped_bid > final_bid
            warn_threshold_exceeded = final_bid > write_spot_pricing_warn_threshold

            resource["SpotPrice"] = final_bid
            if isinstance(resource, CommentedMap):
                resource.yaml_add_eol_comment(
                    "Calculated from reference median spot price with DYEC create cap.",
                    key="SpotPrice",
                    column=0,
                )

            min_count = _parse_int(resource.get("MinCount", 0))
            max_count = _parse_int(resource.get("MaxCount", 0))
            row = {
                "queue": queue_name,
                "resource": resource_name,
                "instance_types": list(stats["instance_types"]),
                "instance_vcpus": dict(stats["instance_vcpus"]),
                "min_instance_vcpus": int(stats["min_instance_vcpus"]),
                "max_instance_vcpus": int(stats["max_instance_vcpus"]),
                "raw_min_spot_price": _round_price(float(stats["raw_min_spot_price"])),
                "raw_max_spot_price": _round_price(float(stats["raw_max_spot_price"])),
                "raw_median_spot_price": _round_price(float(stats["raw_median_spot_price"])),
                "reference_queue": ref_key[0],
                "reference_resource": ref_key[1],
                "reference_median_spot_price": _round_price(reference_median),
                "reference_source": reference_source,
                "uncapped_pct_bid": uncapped_bid,
                "final_bid": final_bid,
                "max_final_bid_usd_per_vcpu_hour": _round_price(
                    final_bid / int(stats["min_instance_vcpus"])
                ),
                "spot_cost_limit_pct": spot_cost_limit_pct,
                "global_spot_max_cost": global_spot_max_cost,
                "global_limiter_applied": global_limiter_applied,
                "write_spot_pricing_warn_threshold": write_spot_pricing_warn_threshold,
                "warn_threshold_exceeded": warn_threshold_exceeded,
                "min_count": min_count,
                "max_count": max_count,
            }
            resource_rows.append(row)
            queue_rows.append(row)

        partition_accumulators[queue_name] = _partition_summary_row(
            queue_name,
            queue_rows,
            global_spot_max_cost=global_spot_max_cost,
            spot_cost_limit_pct=spot_cost_limit_pct,
            write_spot_pricing_warn_threshold=write_spot_pricing_warn_threshold,
        )

    return {
        "schema_version": SPOT_PRICE_SUMMARY_SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "availability_zone": az,
        "global_spot_max_cost": _round_price(global_spot_max_cost),
        "spot_cost_limit_pct": spot_cost_limit_pct,
        "write_spot_pricing_warn_threshold": _round_price(
            write_spot_pricing_warn_threshold
        ),
        "resources": resource_rows,
        "partitions": list(partition_accumulators.values()),
    }


def _collect_resource_price_stats(
    ec2_client: Any,
    resource_config: Dict[str, Any],
    az: str,
) -> dict[str, Any] | None:
    instance_types = [
        str(inst.get("InstanceType"))
        for inst in resource_config.get("Instances", []) or []
        if inst.get("InstanceType")
    ]
    if not instance_types:
        return None

    prices = [get_spot_price(ec2_client, instance_type, az) for instance_type in instance_types]
    instance_vcpus = get_instance_vcpu_counts(ec2_client, instance_types)
    return {
        "instance_types": instance_types,
        "instance_vcpus": instance_vcpus,
        "min_instance_vcpus": min(instance_vcpus.values()),
        "max_instance_vcpus": max(instance_vcpus.values()),
        "raw_min_spot_price": min(prices),
        "raw_max_spot_price": max(prices),
        "raw_median_spot_price": statistics.median(prices),
    }


def _reference_key_for_resource(queue_name: str, resource_name: str) -> tuple[str, str]:
    if queue_name.startswith("i384") or "384" in resource_name:
        return (queue_name.replace("384", "192", 1), resource_name.replace("384", "192", 1))
    return (queue_name, resource_name)


def _partition_summary_row(
    queue_name: str,
    rows: Iterable[dict[str, Any]],
    *,
    global_spot_max_cost: float,
    spot_cost_limit_pct: float,
    write_spot_pricing_warn_threshold: float,
) -> dict[str, Any]:
    row_list = list(rows)
    if not row_list:
        return {
            "queue": queue_name,
            "resource_count": 0,
            "min_instances": 0,
            "max_instances": 0,
            "raw_min_hourly_cost_without_limiter": 0.0,
            "raw_max_hourly_cost_without_limiter": 0.0,
            "max_reference_median_spot_price": 0.0,
            "max_final_bid_usd_per_vcpu_hour": 0.0,
            "max_uncapped_pct_bid": 0.0,
            "max_final_bid": 0.0,
            "global_spot_max_cost": _round_price(global_spot_max_cost),
            "spot_cost_limit_pct": spot_cost_limit_pct,
            "write_spot_pricing_warn_threshold": _round_price(
                write_spot_pricing_warn_threshold
            ),
            "global_limiter_applied": False,
            "warn_threshold_exceeded": False,
            "reference_partitions": "",
        }

    min_instances = sum(int(row["min_count"]) for row in row_list)
    max_instances = sum(int(row["max_count"]) for row in row_list)
    raw_min_cost = sum(
        int(row["min_count"]) * float(row["raw_median_spot_price"]) for row in row_list
    )
    raw_max_cost = sum(
        int(row["max_count"]) * float(row["raw_median_spot_price"]) for row in row_list
    )
    reference_partitions = sorted(
        {str(row["reference_queue"]) for row in row_list if row["reference_queue"] != queue_name}
    )
    if not reference_partitions:
        reference_partitions = [queue_name]

    return {
        "queue": queue_name,
        "resource_count": len(row_list),
        "min_instances": min_instances,
        "max_instances": max_instances,
        "raw_min_hourly_cost_without_limiter": _round_price(raw_min_cost),
        "raw_max_hourly_cost_without_limiter": _round_price(raw_max_cost),
        "max_reference_median_spot_price": _round_price(
            max(float(row["reference_median_spot_price"]) for row in row_list)
        ),
        "max_final_bid_usd_per_vcpu_hour": _round_price(
            max(float(row["max_final_bid_usd_per_vcpu_hour"]) for row in row_list)
        ),
        "max_uncapped_pct_bid": _round_price(
            max(float(row["uncapped_pct_bid"]) for row in row_list)
        ),
        "max_final_bid": _round_price(max(float(row["final_bid"]) for row in row_list)),
        "global_spot_max_cost": _round_price(global_spot_max_cost),
        "spot_cost_limit_pct": spot_cost_limit_pct,
        "write_spot_pricing_warn_threshold": _round_price(
            write_spot_pricing_warn_threshold
        ),
        "global_limiter_applied": any(bool(row["global_limiter_applied"]) for row in row_list),
        "warn_threshold_exceeded": any(bool(row["warn_threshold_exceeded"]) for row in row_list),
        "reference_partitions": ",".join(reference_partitions),
    }


def _final_bid(
    *,
    reference_median: float,
    spot_cost_limit_pct: float,
    global_spot_max_cost: float,
) -> float:
    return _round_price(min(reference_median * spot_cost_limit_pct, global_spot_max_cost))


def _round_price(value: float) -> float:
    return round(float(value), 4)


def _parse_int(value: Any) -> int:
    if value in (None, ""):
        return 0
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"Expected integer MinCount/MaxCount value, got {value!r}.") from exc
