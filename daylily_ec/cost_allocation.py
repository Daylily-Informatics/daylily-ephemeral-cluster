"""Time-weighted hourly cost-center allocation."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Iterable, Mapping

from daylily_ec.aws.cost_centers import RESERVED_IDLE_COST_CENTER
from daylily_ec.aws.cost_centers import CostCenterUsage
from daylily_ec.aws.cur import HourlyInstanceCost


class CostAllocationError(RuntimeError):
    """Raised when cost allocation inputs are malformed."""


@dataclass(frozen=True)
class AllocationJob:
    job_id: str
    cost_center: str
    start_at: str
    end_at: str
    node_names: tuple[str, ...]


@dataclass(frozen=True)
class AllocationRow:
    instance_id: str
    cluster_name: str
    hour_start: str
    hour_end: str
    cost_center: str
    allocated_seconds: Decimal
    allocated_cost_usd: Decimal

    def to_dict(self) -> dict[str, str]:
        return {
            "instance_id": self.instance_id,
            "cluster_name": self.cluster_name,
            "hour_start": self.hour_start,
            "hour_end": self.hour_end,
            "cost_center": self.cost_center,
            "allocated_seconds": str(self.allocated_seconds),
            "allocated_cost_usd": str(self.allocated_cost_usd),
        }


def allocate_hourly_instance_costs(
    costs: Iterable[HourlyInstanceCost],
    jobs: Iterable[AllocationJob | Any],
    *,
    node_instance_map: Mapping[str, str],
) -> list[AllocationRow]:
    """Allocate hourly instance costs across active cost centers and idle time."""
    normalized_jobs = [_normalize_job(job) for job in jobs]
    rows: list[AllocationRow] = []
    for cost in costs:
        hour_start = _parse_time(cost.hour_start)
        hour_end = _parse_time(cost.hour_end)
        if hour_start >= hour_end:
            raise CostAllocationError("cost hour_start must be before hour_end.")
        total_seconds = Decimal(str((hour_end - hour_start).total_seconds()))
        if total_seconds <= 0:
            raise CostAllocationError("cost hour duration must be positive.")

        relevant: list[tuple[datetime, datetime, str]] = []
        for job in normalized_jobs:
            if cost.instance_id not in _job_instance_ids(job, node_instance_map):
                continue
            start = max(_parse_time(job.start_at), hour_start)
            end = min(_parse_time(job.end_at), hour_end)
            if start < end:
                relevant.append((start, end, job.cost_center))

        allocations = _split_instance_hour(hour_start, hour_end, relevant)
        for cost_center, seconds in sorted(allocations.items()):
            share = seconds / total_seconds
            rows.append(
                AllocationRow(
                    instance_id=cost.instance_id,
                    cluster_name=cost.cluster_name,
                    hour_start=_format_time(hour_start),
                    hour_end=_format_time(hour_end),
                    cost_center=cost_center,
                    allocated_seconds=seconds,
                    allocated_cost_usd=(cost.amount_usd * share),
                )
            )
    return rows


def summarize_monthly_usage(
    rows: Iterable[AllocationRow],
    *,
    month: str,
    latest_processed_hour: str,
    updated_at: str,
) -> list[CostCenterUsage]:
    """Summarize allocation rows into monthly DynamoDB usage records."""
    totals: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    for row in rows:
        if not row.hour_start.startswith(month):
            continue
        totals[row.cost_center] += row.allocated_cost_usd
    return [
        CostCenterUsage(
            name=cost_center,
            month=month,
            monthly_spend_usd=total,
            latest_processed_hour=latest_processed_hour,
            updated_at=updated_at,
        )
        for cost_center, total in sorted(totals.items())
    ]


def _split_instance_hour(
    hour_start: datetime,
    hour_end: datetime,
    intervals: list[tuple[datetime, datetime, str]],
) -> dict[str, Decimal]:
    boundaries = {hour_start, hour_end}
    for start, end, _center in intervals:
        boundaries.add(start)
        boundaries.add(end)
    ordered = sorted(boundaries)
    allocations: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    for index in range(len(ordered) - 1):
        start = ordered[index]
        end = ordered[index + 1]
        seconds = Decimal(str((end - start).total_seconds()))
        if seconds <= 0:
            continue
        active = {
            center
            for interval_start, interval_end, center in intervals
            if interval_start < end and interval_end > start
        }
        if not active:
            allocations[RESERVED_IDLE_COST_CENTER] += seconds
            continue
        share = seconds / Decimal(len(active))
        for center in active:
            allocations[center] += share
    return dict(allocations)


def _normalize_job(job: AllocationJob | Any) -> AllocationJob:
    if isinstance(job, AllocationJob):
        return job
    job_id = _attr(job, "job_id", _attr(job, "job_id_raw", ""))
    cost_center = _attr(job, "cost_center", "")
    start_at = _attr(job, "start_at", "")
    end_at = _attr(job, "end_at", "")
    node_names = tuple(_attr(job, "node_names", ()) or ())
    if not job_id:
        raise CostAllocationError("Job is missing job_id.")
    if not cost_center:
        raise CostAllocationError(f"Job {job_id} is missing cost_center.")
    if cost_center == RESERVED_IDLE_COST_CENTER:
        raise CostAllocationError("Jobs cannot use reserved cost center 'idle'.")
    if not start_at or not end_at:
        raise CostAllocationError(f"Job {job_id} must have start_at and end_at.")
    if not node_names:
        raise CostAllocationError(f"Job {job_id} is missing node_names.")
    return AllocationJob(
        job_id=str(job_id),
        cost_center=str(cost_center),
        start_at=str(start_at),
        end_at=str(end_at),
        node_names=tuple(str(node) for node in node_names),
    )


def _job_instance_ids(job: AllocationJob, node_instance_map: Mapping[str, str]) -> set[str]:
    instance_ids: set[str] = set()
    for node in job.node_names:
        instance_id = node_instance_map.get(node)
        if not instance_id:
            raise CostAllocationError(f"Node '{node}' is missing from node_instance_map.")
        instance_ids.add(instance_id)
    return instance_ids


def _attr(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _parse_time(value: str) -> datetime:
    text = str(value or "").strip()
    if not text:
        raise CostAllocationError("timestamp must be non-empty.")
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CostAllocationError(f"Invalid timestamp '{value}'.") from exc
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _format_time(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
