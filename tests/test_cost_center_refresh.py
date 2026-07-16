from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from daylily_ec.aws.cost_centers import (
    CostCenterError,
    CostCenterUsage,
    create_cost_center,
    ensure_cost_center_registry,
    get_cost_center_usage,
    put_cost_center_usage,
)
from daylily_ec.aws.cur import CurAthenaConfig, HourlyInstanceCost
from daylily_ec.cost_center_refresh import refresh_dedicated_cluster_usage
from tests.test_cost_centers import FakeDynamo


def _cost(start: str, end: str, amount: str) -> HourlyInstanceCost:
    return HourlyInstanceCost(
        instance_id="i-123",
        cluster_name="sent-hg003-5x-0712",
        region="us-west-2",
        hour_start=start,
        hour_end=end,
        amount_usd=Decimal(amount),
        currency="USD",
        usage_type="BoxUsage",
        operation="RunInstances",
        purchase_option="OnDemand",
        line_item_type="Usage",
    )


def _dynamo() -> FakeDynamo:
    dynamo = FakeDynamo()
    ensure_cost_center_registry(dynamo)
    create_cost_center(
        dynamo,
        "sent-hg003-5x-0712",
        monthly_cap_usd="750",
        allowed_users=["ubuntu"],
        now="2026-07-01T00:00:00Z",
    )
    return dynamo


def _config() -> CurAthenaConfig:
    return CurAthenaConfig(
        database="dayec_cur",
        table="cur2_hourly",
        output_s3_uri="s3://example/results/",
    )


def test_refresh_reproduces_authoritative_cluster_total(monkeypatch) -> None:
    dynamo = _dynamo()
    rows = [
        _cost("2026-07-09T06:00:00Z", "2026-07-09T07:00:00Z", "40.1"),
        _cost("2026-07-10T14:00:00Z", "2026-07-10T15:00:00Z", "45.6615186511"),
    ]
    monkeypatch.setattr(
        "daylily_ec.cost_center_refresh.query_hourly_ec2_instance_costs",
        lambda *_args, **_kwargs: rows,
    )

    result = refresh_dedicated_cluster_usage(
        athena_client=object(),
        dynamodb_client=dynamo,
        cost_center_name="sent-hg003-5x-0712",
        cluster_name="sent-hg003-5x-0712",
        month="2026-07",
        cur_config=_config(),
        now=datetime(2026, 7, 12, 12, 30, tzinfo=timezone.utc),
    )

    assert result.cur_row_count == 2
    assert str(result.usage.monthly_spend_usd) == "85.7615186511"
    assert result.usage.latest_processed_hour == "2026-07-10T15:00:00Z"
    assert get_cost_center_usage(dynamo, "sent-hg003-5x-0712", month="2026-07") == result.usage


def test_refresh_dry_run_does_not_write(monkeypatch) -> None:
    dynamo = _dynamo()
    before = get_cost_center_usage(dynamo, "sent-hg003-5x-0712", month="2026-07")
    monkeypatch.setattr(
        "daylily_ec.cost_center_refresh.query_hourly_ec2_instance_costs",
        lambda *_args, **_kwargs: [
            _cost("2026-07-11T00:00:00Z", "2026-07-11T01:00:00Z", "1.25")
        ],
    )

    result = refresh_dedicated_cluster_usage(
        athena_client=object(),
        dynamodb_client=dynamo,
        cost_center_name="sent-hg003-5x-0712",
        cluster_name="sent-hg003-5x-0712",
        month="2026-07",
        cur_config=_config(),
        dry_run=True,
        now=datetime(2026, 7, 12, 12, tzinfo=timezone.utc),
    )

    assert result.dry_run is True
    assert get_cost_center_usage(
        dynamo, "sent-hg003-5x-0712", month="2026-07"
    ) == before


def test_refresh_rejects_shared_cluster_assignment() -> None:
    with pytest.raises(CostCenterError, match="name to equal cluster name"):
        refresh_dedicated_cluster_usage(
            athena_client=object(),
            dynamodb_client=_dynamo(),
            cost_center_name="sent-hg003-5x-0712",
            cluster_name="shared-cluster",
            month="2026-07",
            cur_config=_config(),
        )


def test_refresh_rejects_empty_cur_result(monkeypatch) -> None:
    dynamo = _dynamo()
    monkeypatch.setattr(
        "daylily_ec.cost_center_refresh.query_hourly_ec2_instance_costs",
        lambda *_args, **_kwargs: [],
    )
    with pytest.raises(CostCenterError, match="no EC2 instance costs"):
        refresh_dedicated_cluster_usage(
            athena_client=object(),
            dynamodb_client=dynamo,
            cost_center_name="sent-hg003-5x-0712",
            cluster_name="sent-hg003-5x-0712",
            month="2026-07",
            cur_config=_config(),
            now=datetime(2026, 7, 12, 12, tzinfo=timezone.utc),
        )


def test_refresh_rejects_processed_hour_regression(monkeypatch) -> None:
    dynamo = _dynamo()
    put_cost_center_usage(
        dynamo,
        CostCenterUsage(
            name="sent-hg003-5x-0712",
            month="2026-07",
            monthly_spend_usd="10",
            latest_processed_hour="2026-07-11T02:00:00Z",
            updated_at="2026-07-11T03:00:00Z",
        ),
    )
    monkeypatch.setattr(
        "daylily_ec.cost_center_refresh.query_hourly_ec2_instance_costs",
        lambda *_args, **_kwargs: [
            _cost("2026-07-11T00:00:00Z", "2026-07-11T01:00:00Z", "9")
        ],
    )

    with pytest.raises(CostCenterError, match="regress"):
        refresh_dedicated_cluster_usage(
            athena_client=object(),
            dynamodb_client=dynamo,
            cost_center_name="sent-hg003-5x-0712",
            cluster_name="sent-hg003-5x-0712",
            month="2026-07",
            cur_config=_config(),
            now=datetime(2026, 7, 12, 12, tzinfo=timezone.utc),
        )
