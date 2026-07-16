from __future__ import annotations

from decimal import Decimal

from daylily_ec.aws.cur import HourlyInstanceCost
from daylily_ec.cost_allocation import (
    AllocationJob,
    allocate_hourly_instance_costs,
    summarize_monthly_usage,
)


def _cost(amount="60"):
    return HourlyInstanceCost(
        instance_id="i-1",
        cluster_name="cluster-a",
        region="us-west-2",
        hour_start="2026-07-05T00:00:00Z",
        hour_end="2026-07-05T01:00:00Z",
        amount_usd=Decimal(amount),
        currency="USD",
        usage_type="BoxUsage",
        operation="RunInstances",
        purchase_option="OnDemand",
        line_item_type="Usage",
    )


def _allocs(rows):
    return {row.cost_center: row for row in rows}


def test_single_project_full_hour_gets_all_cost():
    rows = allocate_hourly_instance_costs(
        [_cost()],
        [
            AllocationJob(
                job_id="1",
                cost_center="a",
                start_at="2026-07-05T00:00:00Z",
                end_at="2026-07-05T01:00:00Z",
                node_names=("node-1",),
            )
        ],
        node_instance_map={"node-1": "i-1"},
    )

    assert _allocs(rows)["a"].allocated_seconds == Decimal("3600.0")
    assert _allocs(rows)["a"].allocated_cost_usd == Decimal("60")


def test_full_hour_plus_ten_minute_overlap_splits_only_overlap():
    rows = allocate_hourly_instance_costs(
        [_cost()],
        [
            AllocationJob(
                job_id="1",
                cost_center="a",
                start_at="2026-07-05T00:00:00Z",
                end_at="2026-07-05T01:00:00Z",
                node_names=("node-1",),
            ),
            AllocationJob(
                job_id="2",
                cost_center="b",
                start_at="2026-07-05T00:10:00Z",
                end_at="2026-07-05T00:20:00Z",
                node_names=("node-1",),
            ),
        ],
        node_instance_map={"node-1": "i-1"},
    )

    allocs = _allocs(rows)
    assert allocs["a"].allocated_seconds == Decimal("3300.0")
    assert allocs["b"].allocated_seconds == Decimal("300.0")
    assert allocs["a"].allocated_cost_usd.quantize(Decimal("0.01")) == Decimal("55.00")
    assert allocs["b"].allocated_cost_usd.quantize(Decimal("0.01")) == Decimal("5.00")


def test_same_cost_center_multiple_jobs_counts_once():
    rows = allocate_hourly_instance_costs(
        [_cost()],
        [
            AllocationJob(
                job_id="1",
                cost_center="a",
                start_at="2026-07-05T00:00:00Z",
                end_at="2026-07-05T00:30:00Z",
                node_names=("node-1",),
            ),
            AllocationJob(
                job_id="2",
                cost_center="a",
                start_at="2026-07-05T00:10:00Z",
                end_at="2026-07-05T00:20:00Z",
                node_names=("node-1",),
            ),
        ],
        node_instance_map={"node-1": "i-1"},
    )

    allocs = _allocs(rows)
    assert allocs["a"].allocated_seconds == Decimal("1800.0")
    assert allocs["idle"].allocated_seconds == Decimal("1800.0")


def test_no_jobs_allocates_to_idle():
    rows = allocate_hourly_instance_costs([_cost()], [], node_instance_map={})
    assert len(rows) == 1
    assert rows[0].cost_center == "idle"
    assert rows[0].allocated_cost_usd == Decimal("60")


def test_summarize_monthly_usage():
    rows = allocate_hourly_instance_costs(
        [_cost()],
        [
            AllocationJob(
                job_id="1",
                cost_center="a",
                start_at="2026-07-05T00:00:00Z",
                end_at="2026-07-05T01:00:00Z",
                node_names=("node-1",),
            )
        ],
        node_instance_map={"node-1": "i-1"},
    )

    usage = summarize_monthly_usage(
        rows,
        month="2026-07",
        latest_processed_hour="2026-07-05T01:00:00Z",
        updated_at="2026-07-05T01:05:00Z",
    )

    assert len(usage) == 1
    assert usage[0].name == "a"
    assert usage[0].monthly_spend_usd == Decimal("60")
