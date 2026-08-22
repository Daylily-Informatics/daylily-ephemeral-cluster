"""Bounded, fail-closed regional EC2 vCPU quota and usage snapshots."""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Iterable
from datetime import datetime, timedelta, timezone
from typing import Any

from daylily_ec.aws.validation import EC2_VCPU_QUOTA_CODES

CAPACITY_SNAPSHOT_SCHEMA = "dyec.aws_capacity_snapshot.v1"
CAPACITY_TYPES = ("ONDEMAND", "SPOT")
MAX_QUOTA_FAMILIES = 16
CAPACITY_USAGE_WINDOW_SECONDS = 900
CAPACITY_USAGE_PERIOD_SECONDS = 60
MAX_CAPACITY_USAGE_AGE_SECONDS = 600
MAX_CAPACITY_USAGE_FUTURE_SKEW_SECONDS = 300
_SAFE_METRIC_TOKEN_RE = re.compile(r"^[A-Za-z0-9_./:+,() -]{1,256}$")


class CapacitySnapshotError(RuntimeError):
    """Raised when the requested snapshot contract itself is invalid."""


class _UsageMetricError(RuntimeError):
    def __init__(self, reason_code: str):
        super().__init__(reason_code)
        self.reason_code = reason_code


def _pages(client: Any, operation: str, **kwargs: Any) -> Iterable[dict[str, Any]]:
    try:
        paginator = client.get_paginator(operation)
    except Exception:  # noqa: BLE001 - SDK capability probe, never surfaced
        paginator = None
    if paginator is not None:
        yield from paginator.paginate(**kwargs)
        return
    yield getattr(client, operation)(**kwargs)


def _quota_group(instance_type: str) -> str:
    value = str(instance_type or "").strip().lower()
    if value.startswith("hpc"):
        return "hpc"
    if value.startswith("inf"):
        return "inf"
    if value.startswith("trn"):
        return "trn"
    if value.startswith("dl"):
        return "dl"
    if value.startswith(("vt", "g")):
        return "g_vt"
    if value.startswith("x"):
        return "x"
    if value.startswith("f"):
        return "f"
    if value.startswith("p"):
        return "p"
    if value.startswith("u-"):
        return "high_memory"
    if value[:1] in {"a", "c", "d", "h", "i", "m", "r", "t", "z"}:
        return "standard"
    return ""


def _normalize_families(values: Iterable[str]) -> tuple[str, ...]:
    families = tuple(sorted({str(value or "").strip().lower() for value in values}))
    if not families or len(families) > MAX_QUOTA_FAMILIES or any(not value for value in families):
        raise CapacitySnapshotError("At least one bounded --quota-family is required")
    supported = {family for family, _capacity_type in EC2_VCPU_QUOTA_CODES}
    unsupported = sorted(set(families) - supported)
    if unsupported:
        raise CapacitySnapshotError("Unsupported EC2 vCPU quota family: " + ", ".join(unsupported))
    return families


def _safe_metric_token(value: Any, *, reason_code: str) -> str:
    text = str(value or "").strip()
    if not _SAFE_METRIC_TOKEN_RE.fullmatch(text):
        raise _UsageMetricError(reason_code)
    return text


def _quota_usage_observation(
    *,
    cloudwatch_client: Any,
    usage_metric: Any,
    captured_at: datetime,
) -> dict[str, Any]:
    if not isinstance(usage_metric, dict):
        raise _UsageMetricError("quota_usage_metric_missing")
    namespace = _safe_metric_token(
        usage_metric.get("MetricNamespace"),
        reason_code="quota_usage_metric_invalid",
    )
    metric_name = _safe_metric_token(
        usage_metric.get("MetricName"),
        reason_code="quota_usage_metric_invalid",
    )
    statistic = _safe_metric_token(
        usage_metric.get("MetricStatisticRecommendation"),
        reason_code="quota_usage_metric_statistic_invalid",
    )
    if statistic not in {"Average", "Maximum", "Minimum", "SampleCount", "Sum"}:
        raise _UsageMetricError("quota_usage_metric_statistic_invalid")
    raw_dimensions = usage_metric.get("MetricDimensions")
    if not isinstance(raw_dimensions, dict) or not raw_dimensions or len(raw_dimensions) > 16:
        raise _UsageMetricError("quota_usage_metric_dimensions_invalid")
    dimensions: list[dict[str, str]] = []
    public_dimensions: dict[str, str] = {}
    for raw_name, raw_value in sorted(raw_dimensions.items()):
        name = _safe_metric_token(
            raw_name,
            reason_code="quota_usage_metric_dimensions_invalid",
        )
        value = _safe_metric_token(
            raw_value,
            reason_code="quota_usage_metric_dimensions_invalid",
        )
        dimensions.append({"Name": name, "Value": value})
        public_dimensions[name] = value
    try:
        response = cloudwatch_client.get_metric_statistics(
            Namespace=namespace,
            MetricName=metric_name,
            Dimensions=dimensions,
            StartTime=captured_at - timedelta(seconds=CAPACITY_USAGE_WINDOW_SECONDS),
            EndTime=captured_at,
            Period=CAPACITY_USAGE_PERIOD_SECONDS,
            Statistics=[statistic],
        )
    except Exception as exc:
        raise _UsageMetricError("quota_usage_metric_query_failed") from exc
    datapoints = response.get("Datapoints")
    if not isinstance(datapoints, list) or not datapoints:
        raise _UsageMetricError("quota_usage_metric_datapoint_missing")
    normalized: list[tuple[datetime, float]] = []
    for datapoint in datapoints:
        if not isinstance(datapoint, dict):
            raise _UsageMetricError("quota_usage_metric_datapoint_invalid")
        observed_at = datapoint.get("Timestamp")
        if isinstance(observed_at, str):
            try:
                observed_at = datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
            except ValueError as exc:
                raise _UsageMetricError("quota_usage_metric_timestamp_invalid") from exc
        if not isinstance(observed_at, datetime) or observed_at.tzinfo is None:
            raise _UsageMetricError("quota_usage_metric_timestamp_invalid")
        try:
            value = float(datapoint[statistic])
        except (KeyError, TypeError, ValueError) as exc:
            raise _UsageMetricError("quota_usage_metric_value_invalid") from exc
        if not math.isfinite(value) or value < 0:
            raise _UsageMetricError("quota_usage_metric_value_invalid")
        normalized.append((observed_at.astimezone(timezone.utc), value))
    observed_at, value = max(normalized, key=lambda item: item[0])
    age_seconds = (captured_at - observed_at).total_seconds()
    if age_seconds < -MAX_CAPACITY_USAGE_FUTURE_SKEW_SECONDS:
        raise _UsageMetricError("quota_usage_metric_timestamp_future")
    if age_seconds > MAX_CAPACITY_USAGE_AGE_SECONDS:
        raise _UsageMetricError("quota_usage_metric_timestamp_stale")
    return {
        "namespace": namespace,
        "metric_name": metric_name,
        "dimensions": public_dimensions,
        "statistic": statistic,
        "period_seconds": CAPACITY_USAGE_PERIOD_SECONDS,
        "window_seconds": CAPACITY_USAGE_WINDOW_SECONDS,
        "observed_at": observed_at.isoformat().replace("+00:00", "Z"),
        "age_seconds": round(age_seconds, 3),
        "value": value,
    }


def _instance_vcpus(ec2_client: Any, instance_types: set[str]) -> dict[str, int]:
    if not instance_types:
        return {}
    result: dict[str, int] = {}
    ordered = sorted(instance_types)
    for offset in range(0, len(ordered), 100):
        batch = ordered[offset : offset + 100]
        response = ec2_client.describe_instance_types(InstanceTypes=batch)
        for row in response.get("InstanceTypes", []):
            instance_type = str(row.get("InstanceType") or "")
            try:
                vcpus = int((row.get("VCpuInfo") or {})["DefaultVCpus"])
            except (KeyError, TypeError, ValueError) as exc:
                raise CapacitySnapshotError(
                    "EC2 instance-type inventory returned invalid vCPU data"
                ) from exc
            if not instance_type or vcpus <= 0:
                raise CapacitySnapshotError(
                    "EC2 instance-type inventory returned invalid vCPU data"
                )
            result[instance_type] = vcpus
    if set(result) != instance_types:
        raise CapacitySnapshotError("EC2 instance-type inventory was incomplete")
    return result


def _current_instances(ec2_client: Any) -> list[dict[str, Any]]:
    instances: list[dict[str, Any]] = []
    for page in _pages(
        ec2_client,
        "describe_instances",
        Filters=[{"Name": "instance-state-name", "Values": ["pending", "running"]}],
    ):
        for reservation in page.get("Reservations", []):
            instances.extend(reservation.get("Instances", []))
    return instances


def _open_spot_requests(ec2_client: Any) -> list[dict[str, Any]]:
    requests: list[dict[str, Any]] = []
    for page in _pages(
        ec2_client,
        "describe_spot_instance_requests",
        Filters=[{"Name": "state", "Values": ["open"]}],
    ):
        requests.extend(page.get("SpotInstanceRequests", []))
    return requests


def _detect_unresolved_ec2_fleet_demand(ec2_client: Any) -> int:
    unresolved = 0
    for page in _pages(ec2_client, "describe_fleets"):
        for fleet in page.get("Fleets", []):
            if str(fleet.get("FleetState") or "") in {"deleted", "deleted_running"}:
                continue
            target = fleet.get("TargetCapacitySpecification") or {}
            try:
                total_target = float(target.get("TotalTargetCapacity") or 0)
                fulfilled = float(fleet.get("FulfilledCapacity") or 0)
            except (TypeError, ValueError) as exc:
                raise CapacitySnapshotError("EC2 Fleet capacity inventory was invalid") from exc
            if total_target - fulfilled > 1e-9:
                unresolved += 1
    return unresolved


def _detect_unresolved_spot_fleet_demand(ec2_client: Any) -> int:
    unresolved = 0
    for page in _pages(ec2_client, "describe_spot_fleet_requests"):
        for request in page.get("SpotFleetRequestConfigs", []):
            state = str(request.get("SpotFleetRequestState") or "")
            if state in {"cancelled", "cancelled_running", "cancelled_terminating"}:
                continue
            config = request.get("SpotFleetRequestConfig") or {}
            try:
                target = float(config.get("TargetCapacity") or 0)
                fulfilled = float(request.get("FulfilledCapacity") or 0)
            except (TypeError, ValueError) as exc:
                raise CapacitySnapshotError("Spot Fleet capacity inventory was invalid") from exc
            if target - fulfilled > 1e-9:
                unresolved += 1
    return unresolved


def _detect_unresolved_asg_demand(autoscaling_client: Any) -> int:
    unresolved = 0
    for page in _pages(autoscaling_client, "describe_auto_scaling_groups"):
        for group in page.get("AutoScalingGroups", []):
            try:
                desired = int(group.get("DesiredCapacity") or 0)
            except (TypeError, ValueError) as exc:
                raise CapacitySnapshotError("Auto Scaling capacity inventory was invalid") from exc
            instances = group.get("Instances") or []
            if not isinstance(instances, list):
                raise CapacitySnapshotError("Auto Scaling capacity inventory was invalid")
            if desired > len(instances):
                unresolved += 1
    return unresolved


def build_capacity_snapshot(
    *,
    ec2_client: Any,
    autoscaling_client: Any,
    service_quotas_client: Any,
    cloudwatch_client: Any,
    profile: str,
    account_id: str,
    region: str,
    quota_families: Iterable[str],
    now: datetime | None = None,
) -> dict[str, Any]:
    """Return quota-native vCPU use, or an explicit incomplete/null snapshot.

    Service Quotas ``UsageMetric`` is the authority because it accounts for
    every quota-consuming EC2 request mechanism.  EC2/Fleet/ASG inventory is
    included only as non-authoritative diagnostic context.
    """

    resolved_profile = str(profile or "").strip()
    resolved_account = str(account_id or "").strip()
    resolved_region = str(region or "").strip()
    if not resolved_profile or not resolved_account or not resolved_region:
        raise CapacitySnapshotError("Exact profile, account, and region are required")
    families = _normalize_families(quota_families)
    captured = now or datetime.now(timezone.utc)
    if captured.tzinfo is None:
        raise CapacitySnapshotError("Capacity snapshot time must include a timezone")
    captured = captured.astimezone(timezone.utc)
    captured_at = captured.replace(microsecond=0).isoformat().replace("+00:00", "Z")
    authoritative_reason_codes: set[str] = set()
    context_reason_codes: set[str] = set()
    contextual_usage: Counter[tuple[str, str]] = Counter()
    instance_counts: Counter[tuple[str, str]] = Counter()
    open_request_counts: Counter[tuple[str, str]] = Counter()

    try:
        instances = _current_instances(ec2_client)
    except Exception:  # noqa: BLE001 - bounded reason code only
        instances = []
        context_reason_codes.add("instance_inventory_unavailable")
    try:
        open_requests = _open_spot_requests(ec2_client)
    except Exception:  # noqa: BLE001 - bounded reason code only
        open_requests = []
        context_reason_codes.add("spot_request_inventory_unavailable")

    typed_rows: list[tuple[str, str, str]] = []
    instance_types: set[str] = set()
    if not context_reason_codes:
        for instance in instances:
            instance_type = str(instance.get("InstanceType") or "").strip()
            group = _quota_group(instance_type)
            if not instance_type or not group:
                context_reason_codes.add("instance_family_unmapped")
                continue
            capacity_type = "SPOT" if instance.get("InstanceLifecycle") == "spot" else "ONDEMAND"
            typed_rows.append((instance_type, group, capacity_type))
            instance_types.add(instance_type)
        for request in open_requests:
            launch = request.get("LaunchSpecification") or {}
            instance_type = (
                str(launch.get("InstanceType") or "").strip() if isinstance(launch, dict) else ""
            )
            group = _quota_group(instance_type)
            if not instance_type or not group:
                context_reason_codes.add("open_spot_request_type_unavailable")
                continue
            typed_rows.append((instance_type, group, "SPOT_OPEN_REQUEST"))
            instance_types.add(instance_type)

    try:
        vcpus = _instance_vcpus(ec2_client, instance_types)
    except Exception:  # noqa: BLE001 - bounded reason code only
        vcpus = {}
        context_reason_codes.add("instance_type_inventory_unavailable")
    if vcpus:
        for instance_type, group, capacity_type in typed_rows:
            key = (group, "SPOT" if capacity_type == "SPOT_OPEN_REQUEST" else capacity_type)
            contextual_usage[key] += vcpus[instance_type]
            if capacity_type == "SPOT_OPEN_REQUEST":
                open_request_counts[key] += 1
            else:
                instance_counts[key] += 1

    pending_mechanisms = {
        "ec2_fleets": None,
        "spot_fleets": None,
        "auto_scaling_groups": None,
    }
    for key, callback in (
        ("ec2_fleets", lambda: _detect_unresolved_ec2_fleet_demand(ec2_client)),
        ("spot_fleets", lambda: _detect_unresolved_spot_fleet_demand(ec2_client)),
        (
            "auto_scaling_groups",
            lambda: _detect_unresolved_asg_demand(autoscaling_client),
        ),
    ):
        try:
            pending_mechanisms[key] = callback()
        except Exception:  # noqa: BLE001 - bounded reason code only
            context_reason_codes.add(f"{key}_inventory_unavailable")
    if any(value for value in pending_mechanisms.values() if value is not None):
        context_reason_codes.add("unresolved_pending_capacity")

    rows: list[dict[str, Any]] = []
    for family in families:
        for capacity_type in CAPACITY_TYPES:
            definition = EC2_VCPU_QUOTA_CODES.get((family, capacity_type))
            if definition is None:
                continue
            quota_code, quota_name = definition
            limit_vcpus: float | None = None
            unit: str | None = None
            observation: dict[str, Any] | None = None
            row_reason_codes: list[str] = []
            try:
                quota = service_quotas_client.get_service_quota(
                    ServiceCode="ec2",
                    QuotaCode=quota_code,
                )["Quota"]
                limit_vcpus = float(quota["Value"])
                if not math.isfinite(limit_vcpus) or limit_vcpus < 0:
                    raise ValueError("invalid quota value")
                unit = str(quota.get("Unit") or "None")
                observation = _quota_usage_observation(
                    cloudwatch_client=cloudwatch_client,
                    usage_metric=quota.get("UsageMetric"),
                    captured_at=captured,
                )
            except _UsageMetricError as exc:
                row_reason_codes.append(exc.reason_code)
                authoritative_reason_codes.add(exc.reason_code)
            except Exception:  # noqa: BLE001 - bounded reason code only
                row_reason_codes.append("service_quota_inventory_unavailable")
                authoritative_reason_codes.add("service_quota_inventory_unavailable")
            key = (family, capacity_type)
            rows.append(
                {
                    "quota_family": family,
                    "capacity_type": capacity_type,
                    "service_code": "ec2",
                    "quota_code": quota_code,
                    "quota_name": quota_name,
                    "limit_vcpus": limit_vcpus,
                    "unit": unit,
                    "usage_metric": (
                        {name: value for name, value in observation.items() if name != "value"}
                        if observation is not None
                        else None
                    ),
                    "usage_metric_value_vcpus": (
                        observation["value"] if observation is not None else None
                    ),
                    "reason_codes": row_reason_codes,
                    "context_observed_instance_count": instance_counts[key],
                    "context_observed_open_spot_request_count": open_request_counts[key],
                    "context_observed_used_vcpus": contextual_usage[key],
                }
            )

    if not rows:
        authoritative_reason_codes.add("supported_quota_rows_missing")
    complete = not authoritative_reason_codes
    for row in rows:
        if complete:
            row["used_vcpus"] = row["usage_metric_value_vcpus"]
            row["headroom_vcpus"] = row["limit_vcpus"] - row["used_vcpus"]
        else:
            row["used_vcpus"] = None
            row["headroom_vcpus"] = None
    return {
        "schema_version": CAPACITY_SNAPSHOT_SCHEMA,
        "ok": True,
        "status": "complete" if complete else "incomplete",
        "complete": complete,
        "captured_at": captured_at,
        "profile": resolved_profile,
        "account_id": resolved_account,
        "region": resolved_region,
        "quota_families": list(families),
        "reason_codes": sorted(authoritative_reason_codes),
        "usage_source": {
            "service": "cloudwatch",
            "source_contract": "ServiceQuotas.Quota.UsageMetric",
            "window_seconds": CAPACITY_USAGE_WINDOW_SECONDS,
            "period_seconds": CAPACITY_USAGE_PERIOD_SECONDS,
            "maximum_age_seconds": MAX_CAPACITY_USAGE_AGE_SECONDS,
            "maximum_future_skew_seconds": MAX_CAPACITY_USAGE_FUTURE_SKEW_SECONDS,
        },
        "inventory_context": {
            "authoritative": False,
            "complete": not context_reason_codes,
            "reason_codes": sorted(context_reason_codes),
            "pending_capacity_mechanisms": pending_mechanisms,
        },
        "quotas": rows,
    }
