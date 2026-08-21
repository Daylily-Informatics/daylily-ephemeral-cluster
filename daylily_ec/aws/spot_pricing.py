"""Spot-price bid generation for ParallelCluster compute resources."""

from __future__ import annotations

import json
import math
import statistics
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap

SPOT_PRICE_SUMMARY_SCHEMA_VERSION = "dyec.spot_price_summary.v1"

DEFAULT_SPOT_PRODUCT_DESCRIPTION = "Linux/UNIX"
F2_PARTITION_MAX_INSTANCE_THRESHOLD = 3
F2_LOW_DIVERSITY_SPOT_COST_LIMIT_PCT = 1.20

DEFAULT_GLOBAL_SPOT_MAX_COST: float = 9.99
MAX_GLOBAL_SPOT_MAX_COST: float = 9.99
DEFAULT_SPOT_COST_LIMIT_PCT: float = 1.70
MIN_SPOT_COST_LIMIT_PCT: float = 1.0
MAX_SPOT_COST_LIMIT_PCT: float = 2.20
DEFAULT_WRITE_SPOT_PRICING_WARN_THRESHOLD: float = 8.00
MAX_SPOT_OBSERVATION_AGE_SECONDS = 3600
MAX_SPOT_OBSERVATION_FUTURE_SKEW_SECONDS = 300


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
            f"--write-spot-pricing-warn-threshold must be > 0; got {warn_threshold:.4f}."
        )
    return global_max, pct, warn_threshold


def get_spot_price(
    ec2_client: Any,
    instance_type: str,
    az: str,
    *,
    product_description: str = DEFAULT_SPOT_PRODUCT_DESCRIPTION,
) -> float:
    """Return the latest spot price for one product, instance type, and AZ."""

    try:
        resp = ec2_client.describe_spot_price_history(
            InstanceTypes=[instance_type],
            AvailabilityZone=az,
            ProductDescriptions=[product_description],
            MaxResults=1,
        )
    except Exception as exc:
        raise RuntimeError(
            f"Spot price lookup failed for {product_description} {instance_type} in {az}. "
            "Confirm the instance type is valid and ec2:DescribeSpotPriceHistory is allowed."
        ) from exc

    prices = resp.get("SpotPriceHistory", [])
    if not prices:
        raise RuntimeError(
            "Spot price lookup returned no price history for "
            f"{product_description} {instance_type} in {az}."
        )

    try:
        return float(prices[0]["SpotPrice"])
    except (KeyError, ValueError, TypeError) as exc:
        raise RuntimeError(
            "Spot price lookup returned a non-numeric SpotPrice for "
            f"{product_description} {instance_type} in {az}."
        ) from exc


def get_fresh_spot_price_observation(
    ec2_client: Any,
    instance_type: str,
    az: str,
    *,
    product_description: str = DEFAULT_SPOT_PRODUCT_DESCRIPTION,
    captured_at: datetime | None = None,
) -> dict[str, Any]:
    """Return one bounded, timestamped, fresh Spot market observation."""

    now = captured_at or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise RuntimeError("Spot price capture time must include a timezone.")
    try:
        response = ec2_client.describe_spot_price_history(
            InstanceTypes=[instance_type],
            AvailabilityZone=az,
            ProductDescriptions=[product_description],
            MaxResults=1,
        )
    except Exception as exc:
        raise RuntimeError(
            f"Spot price lookup failed for {product_description} {instance_type} in {az}."
        ) from exc
    rows = response.get("SpotPriceHistory", [])
    if len(rows) != 1 or not isinstance(rows[0], dict):
        raise RuntimeError(
            f"Spot price lookup returned no exact observation for {instance_type} in {az}."
        )
    row = rows[0]
    try:
        price = float(row["SpotPrice"])
    except (KeyError, TypeError, ValueError) as exc:
        raise RuntimeError(
            f"Spot price lookup returned an invalid numeric observation for {instance_type}."
        ) from exc
    if not math.isfinite(price) or price <= 0:
        raise RuntimeError(
            f"Spot price lookup returned an invalid numeric observation for {instance_type}."
        )
    observed = row.get("Timestamp")
    if isinstance(observed, str):
        try:
            observed = datetime.fromisoformat(observed.replace("Z", "+00:00"))
        except ValueError as exc:
            raise RuntimeError("Spot price observation timestamp is invalid.") from exc
    if not isinstance(observed, datetime) or observed.tzinfo is None:
        raise RuntimeError("Spot price observation is missing a timezone-aware timestamp.")
    observed_utc = observed.astimezone(timezone.utc)
    captured_utc = now.astimezone(timezone.utc)
    age_seconds = (captured_utc - observed_utc).total_seconds()
    if age_seconds < -MAX_SPOT_OBSERVATION_FUTURE_SKEW_SECONDS:
        raise RuntimeError("Spot price observation timestamp is too far in the future.")
    if age_seconds > MAX_SPOT_OBSERVATION_AGE_SECONDS:
        raise RuntimeError("Spot price observation is older than the approved freshness bound.")
    return {
        "instance_type": instance_type,
        "product_description": product_description,
        "price": price,
        "observed_at": observed_utc.isoformat().replace("+00:00", "Z"),
        "age_seconds": round(age_seconds, 3),
    }


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
            f"{joined}. Confirm ec2:DescribeInstanceTypes is allowed."
        ) from exc

    counts: dict[str, int] = {}
    for item in resp.get("InstanceTypes", []) or []:
        instance_type = str(item.get("InstanceType") or "")
        vcpu_info = item.get("VCpuInfo") or {}
        try:
            vcpus = int(vcpu_info["DefaultVCpus"])
        except (KeyError, TypeError, ValueError) as exc:
            raise RuntimeError(
                f"Instance type vCPU lookup returned invalid VCpuInfo for {instance_type}."
            ) from exc
        if vcpus <= 0:
            raise RuntimeError(
                f"Instance type vCPU lookup returned non-positive DefaultVCpus for {instance_type}."
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
    resource_config: dict[str, Any],
    az: str,
    *,
    global_spot_max_cost: float = DEFAULT_GLOBAL_SPOT_MAX_COST,
    spot_cost_limit_pct: float = DEFAULT_SPOT_COST_LIMIT_PCT,
    write_spot_pricing_warn_threshold: float = DEFAULT_WRITE_SPOT_PRICING_WARN_THRESHOLD,
) -> float | None:
    """Return the capped spot bid for one compute resource using its own median."""

    global_max, pct, _warn_threshold = validate_spot_pricing_limits(
        global_spot_max_cost=global_spot_max_cost,
        spot_cost_limit_pct=spot_cost_limit_pct,
        write_spot_pricing_warn_threshold=write_spot_pricing_warn_threshold,
    )
    stats = _collect_resource_price_stats(
        ec2_client,
        resource_config,
        az,
        captured_at=datetime.now(timezone.utc),
    )
    if stats is None:
        return None
    return _final_bid(
        reference_median=float(stats["raw_median_spot_price"]),
        spot_cost_limit_pct=pct,
        global_spot_max_cost=global_max,
    )


def apply_spot_to_queue(
    ec2_client: Any,
    queue_config: dict[str, Any],
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
    config: dict[str, Any],
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
    profile: str | None = None,
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

        session_kw: dict[str, str] = {}
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
    config: dict[str, Any],
    az: str,
    ec2_client: Any,
    *,
    global_spot_max_cost: float,
    spot_cost_limit_pct: float,
    write_spot_pricing_warn_threshold: float,
) -> dict[str, Any]:
    captured_at = datetime.now(timezone.utc)
    queues = config.get("Scheduling", {}).get("SlurmQueues", []) or []
    spot_queues = [
        queue
        for queue in queues
        if str(queue.get("CapacityType") or "ONDEMAND").strip().upper() == "SPOT"
    ]
    resource_stats: dict[tuple[str, str], dict[str, Any]] = {}

    for queue_index, queue in enumerate(spot_queues):
        queue_name = str(queue.get("Name") or f"queue_{queue_index}")
        for resource_index, resource in enumerate(_queue_resources(queue)):
            resource_name = _resource_name(resource, resource_index)
            stats = _collect_resource_price_stats(
                ec2_client,
                resource,
                az,
                captured_at=captured_at,
            )
            if stats is None:
                raise RuntimeError(
                    f"Compute resource {queue_name}/{resource_name} has no Instances[].InstanceType."
                )
            resource_key = (queue_name, resource_name)
            resource_stats[resource_key] = stats

    resource_rows: list[dict[str, Any]] = []
    partition_accumulators: dict[str, dict[str, Any]] = {}

    for queue_index, queue in enumerate(spot_queues):
        queue_name = str(queue.get("Name") or f"queue_{queue_index}")
        resources = _queue_resources(queue)
        queue_max_instances = _queue_max_instances(resources)
        queue_partition_max_price = _queue_partition_max_spot_price(
            queue_name,
            resources,
            resource_stats,
        )
        queue_rows: list[dict[str, Any]] = []
        for resource_index, resource in enumerate(resources):
            resource_name = _resource_name(resource, resource_index)
            resource_key = (queue_name, resource_name)
            stats = resource_stats[resource_key]
            ref_key = resource_key
            use_f2_partition_max = _uses_f2_partition_max(
                stats,
                queue_max_instances=queue_max_instances,
            )
            if use_f2_partition_max:
                reference_queue = queue_name
                reference_resource = "partition_max"
                reference_source = "f2_partition_max"
                reference_median = queue_partition_max_price
                effective_spot_cost_limit_pct = F2_LOW_DIVERSITY_SPOT_COST_LIMIT_PCT
            else:
                ref_stats = resource_stats[ref_key]
                reference_queue = queue_name
                reference_resource = resource_name
                reference_source = "self"
                reference_median = float(ref_stats["raw_median_spot_price"])
                effective_spot_cost_limit_pct = spot_cost_limit_pct
            uncapped_bid = _round_price(reference_median * effective_spot_cost_limit_pct)
            final_bid = min(uncapped_bid, _round_price(global_spot_max_cost))
            final_bid = _round_price(final_bid)
            global_limiter_applied = uncapped_bid > final_bid
            warn_threshold_exceeded = final_bid > write_spot_pricing_warn_threshold

            resource["SpotPrice"] = final_bid
            if isinstance(resource, CommentedMap):
                comment_source = (
                    "f2 partition max spot price"
                    if use_f2_partition_max
                    else "reference median spot price"
                )
                resource.yaml_add_eol_comment(
                    f"Calculated from {comment_source} with DYEC create cap.",
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
                "spot_price_observations": list(stats["spot_price_observations"]),
                "min_instance_vcpus": int(stats["min_instance_vcpus"]),
                "max_instance_vcpus": int(stats["max_instance_vcpus"]),
                "raw_min_spot_price": _round_price(float(stats["raw_min_spot_price"])),
                "raw_max_spot_price": _round_price(float(stats["raw_max_spot_price"])),
                "raw_median_spot_price": _round_price(float(stats["raw_median_spot_price"])),
                "reference_queue": reference_queue,
                "reference_resource": reference_resource,
                "reference_median_spot_price": _round_price(reference_median),
                "reference_source": reference_source,
                "uncapped_pct_bid": uncapped_bid,
                "final_bid": final_bid,
                "max_final_bid_usd_per_vcpu_hour": _round_price(
                    final_bid / int(stats["min_instance_vcpus"])
                ),
                "spot_cost_limit_pct": effective_spot_cost_limit_pct,
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
        "generated_at": captured_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "observation_policy": {
            "maximum_age_seconds": MAX_SPOT_OBSERVATION_AGE_SECONDS,
            "maximum_future_skew_seconds": MAX_SPOT_OBSERVATION_FUTURE_SKEW_SECONDS,
        },
        "availability_zone": az,
        "global_spot_max_cost": _round_price(global_spot_max_cost),
        "spot_cost_limit_pct": spot_cost_limit_pct,
        "write_spot_pricing_warn_threshold": _round_price(write_spot_pricing_warn_threshold),
        "resources": resource_rows,
        "partitions": list(partition_accumulators.values()),
    }


def _collect_resource_price_stats(
    ec2_client: Any,
    resource_config: dict[str, Any],
    az: str,
    *,
    captured_at: datetime,
) -> dict[str, Any] | None:
    instance_types = [
        str(inst.get("InstanceType"))
        for inst in resource_config.get("Instances", []) or []
        if inst.get("InstanceType")
    ]
    if not instance_types:
        return None

    observations = [
        _effective_spot_price_observation(
            ec2_client,
            instance_type,
            az,
            captured_at=captured_at,
        )
        for instance_type in instance_types
    ]
    prices = [float(observation["price"]) for observation in observations]
    instance_vcpus = get_instance_vcpu_counts(ec2_client, instance_types)
    return {
        "instance_types": instance_types,
        "instance_vcpus": instance_vcpus,
        "spot_price_observations": observations,
        "min_instance_vcpus": min(instance_vcpus.values()),
        "max_instance_vcpus": max(instance_vcpus.values()),
        "raw_min_spot_price": min(prices),
        "raw_max_spot_price": max(prices),
        "raw_median_spot_price": statistics.median(prices),
    }


def _queue_resources(queue: dict[str, Any]) -> list[dict[str, Any]]:
    return list(queue.get("ComputeResources", []) or [])


def _resource_name(resource: dict[str, Any], index: int) -> str:
    return str(resource.get("Name") or f"resource_{index}")


def _queue_max_instances(resources: Iterable[dict[str, Any]]) -> int:
    return sum(_parse_int(resource.get("MaxCount", 0)) for resource in resources)


def _queue_partition_max_spot_price(
    queue_name: str,
    resources: Iterable[dict[str, Any]],
    resource_stats: dict[tuple[str, str], dict[str, Any]],
) -> float:
    prices = []
    for resource_index, resource in enumerate(resources):
        resource_name = _resource_name(resource, resource_index)
        stats = resource_stats[(queue_name, resource_name)]
        prices.append(float(stats["raw_max_spot_price"]))
    return max(prices) if prices else 0.0


def _uses_f2_partition_max(
    stats: dict[str, Any],
    *,
    queue_max_instances: int,
) -> bool:
    return queue_max_instances < F2_PARTITION_MAX_INSTANCE_THRESHOLD and any(
        _is_f2_instance_type(instance_type) for instance_type in stats["instance_types"]
    )


def _effective_spot_price_observation(
    ec2_client: Any,
    instance_type: str,
    az: str,
    *,
    captured_at: datetime,
) -> dict[str, Any]:
    observations = [
        get_fresh_spot_price_observation(
            ec2_client,
            instance_type,
            az,
            product_description=product_description,
            captured_at=captured_at,
        )
        for product_description in _spot_product_descriptions(instance_type)
    ]
    return max(observations, key=lambda item: float(item["price"]))


def _spot_product_descriptions(instance_type: str) -> tuple[str, ...]:
    return (DEFAULT_SPOT_PRODUCT_DESCRIPTION,)


def _is_f2_instance_type(instance_type: str) -> bool:
    return instance_type.startswith("f2.")


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
            "write_spot_pricing_warn_threshold": _round_price(write_spot_pricing_warn_threshold),
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
        "spot_cost_limit_pct": max(float(row["spot_cost_limit_pct"]) for row in row_list),
        "write_spot_pricing_warn_threshold": _round_price(write_spot_pricing_warn_threshold),
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
