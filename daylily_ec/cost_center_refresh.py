"""Authoritative CUR refresh for dedicated cluster cost centers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from daylily_ec.aws.cost_centers import (
    CostCenterError,
    CostCenterUsage,
    get_cost_center,
    get_cost_center_usage,
    put_cost_center_usage,
    utc_now_iso,
    validate_cost_center_name,
    validate_month,
)
from daylily_ec.aws.cur import CurAthenaConfig, query_hourly_ec2_instance_costs


@dataclass(frozen=True)
class DedicatedClusterUsageRefresh:
    usage: CostCenterUsage
    cluster_name: str
    query_start_hour: str
    query_end_hour: str
    cur_row_count: int
    first_cost_hour: str
    dry_run: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "usage": self.usage.to_dict(),
            "cluster_name": self.cluster_name,
            "query_start_hour": self.query_start_hour,
            "query_end_hour": self.query_end_hour,
            "cur_row_count": self.cur_row_count,
            "first_cost_hour": self.first_cost_hour,
            "dry_run": self.dry_run,
        }


def refresh_dedicated_cluster_usage(
    *,
    athena_client: Any,
    dynamodb_client: Any,
    cost_center_name: str,
    cluster_name: str,
    month: str,
    cur_config: CurAthenaConfig,
    registry_table_name: str = "dayec-cost-centers",
    usage_table_name: str = "dayec-cost-center-usage",
    dry_run: bool = False,
    now: datetime | None = None,
) -> DedicatedClusterUsageRefresh:
    """Recompute a dedicated cluster's monthly EC2 spend from CUR.

    This intentionally refuses shared-cluster allocation. A separate job-time
    allocator is required when a cluster hosts more than one cost center.
    """
    resolved_name = validate_cost_center_name(cost_center_name)
    resolved_cluster = validate_cost_center_name(cluster_name)
    resolved_month = validate_month(month)
    if resolved_name != resolved_cluster:
        raise CostCenterError(
            "Dedicated-cluster refresh requires cost-center name to equal cluster name; "
            "shared-cluster allocation must use Slurm job-time accounting."
        )

    cost_center = get_cost_center(
        dynamodb_client,
        resolved_name,
        table_name=registry_table_name,
    )
    if cost_center.status != "active":
        raise CostCenterError(f"Cost center '{resolved_name}' is not active.")

    current_time = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    current_hour = current_time.replace(minute=0, second=0, microsecond=0)
    start_hour, month_end = _month_bounds(resolved_month)
    end_hour = min(current_hour, month_end)
    if end_hour <= start_hour:
        raise CostCenterError(f"Month {resolved_month} has no completed UTC hour to refresh.")

    costs = query_hourly_ec2_instance_costs(
        athena_client,
        config=cur_config,
        cluster_name=resolved_cluster,
        start_hour=start_hour,
        end_hour=end_hour,
    )
    if not costs:
        raise CostCenterError(
            f"CUR returned no EC2 instance costs for cluster '{resolved_cluster}' "
            f"during {resolved_month}; refusing to write a zero snapshot."
        )

    amount = sum((row.amount_usd for row in costs), Decimal("0"))
    if amount < 0:
        raise CostCenterError("CUR monthly EC2 cost total is negative; refusing usage refresh.")
    latest_processed_hour = max(row.hour_end for row in costs)
    first_cost_hour = min(row.hour_start for row in costs)

    previous = get_cost_center_usage(
        dynamodb_client,
        resolved_name,
        month=resolved_month,
        usage_table_name=usage_table_name,
        allow_missing=True,
    )
    if previous and _parse_hour(latest_processed_hour) < _parse_hour(
        previous.latest_processed_hour
    ):
        raise CostCenterError(
            "CUR refresh would regress latest_processed_hour from "
            f"{previous.latest_processed_hour} to {latest_processed_hour}."
        )

    usage = CostCenterUsage(
        name=resolved_name,
        month=resolved_month,
        monthly_spend_usd=amount,
        latest_processed_hour=latest_processed_hour,
        updated_at=utc_now_iso(),
    )
    if not dry_run:
        usage = put_cost_center_usage(
            dynamodb_client,
            usage,
            usage_table_name=usage_table_name,
        )
    return DedicatedClusterUsageRefresh(
        usage=usage,
        cluster_name=resolved_cluster,
        query_start_hour=_format_hour(start_hour),
        query_end_hour=_format_hour(end_hour),
        cur_row_count=len(costs),
        first_cost_hour=first_cost_hour,
        dry_run=dry_run,
    )


def _month_bounds(month: str) -> tuple[datetime, datetime]:
    year, month_number = (int(part) for part in month.split("-", 1))
    start = datetime(year, month_number, 1, tzinfo=timezone.utc)
    if month_number == 12:
        end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        end = datetime(year, month_number + 1, 1, tzinfo=timezone.utc)
    return start, end


def _parse_hour(value: str) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise CostCenterError(f"CUR hour lacks timezone: {value}")
    return parsed.astimezone(timezone.utc)


def _format_hour(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
