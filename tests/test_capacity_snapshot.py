from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from daylily_ec.aws.capacity_snapshot import (
    CAPACITY_SNAPSHOT_SCHEMA,
    build_capacity_snapshot,
)

CAPTURED_AT = datetime(2026, 8, 20, 18, 5, tzinfo=timezone.utc)


class _EmptyInventory:
    def get_paginator(self, _operation: str):
        raise RuntimeError("no paginator")

    def describe_instances(self, **_kwargs):
        return {"Reservations": []}

    def describe_spot_instance_requests(self, **_kwargs):
        return {"SpotInstanceRequests": []}

    def describe_fleets(self, **_kwargs):
        return {"Fleets": []}

    def describe_spot_fleet_requests(self, **_kwargs):
        return {"SpotFleetRequestConfigs": []}

    def describe_instance_types(self, **_kwargs):
        return {"InstanceTypes": []}


class _EmptyAutoScaling:
    def get_paginator(self, _operation: str):
        raise RuntimeError("no paginator")

    def describe_auto_scaling_groups(self, **_kwargs):
        return {"AutoScalingGroups": []}


class _Quotas:
    def __init__(self, *, include_usage_metric: bool = True) -> None:
        self.include_usage_metric = include_usage_metric

    def get_service_quota(self, *, ServiceCode: str, QuotaCode: str):
        assert ServiceCode == "ec2"
        quota = {
            "QuotaCode": QuotaCode,
            "Value": 256.0,
            "Unit": "None",
        }
        if self.include_usage_metric:
            quota["UsageMetric"] = {
                "MetricNamespace": "AWS/Usage",
                "MetricName": "ResourceCount",
                "MetricDimensions": {
                    "Class": "Standard/OnDemand" if QuotaCode == "L-1216C47A" else "Standard/Spot",
                    "Resource": "vCPU",
                    "Service": "EC2",
                    "Type": "Resource",
                },
                "MetricStatisticRecommendation": "Maximum",
            }
        return {"Quota": quota}


class _CloudWatch:
    def __init__(self, *, observed_at: datetime = CAPTURED_AT, fail: bool = False) -> None:
        self.observed_at = observed_at
        self.fail = fail
        self.calls: list[dict[str, object]] = []

    def get_metric_statistics(self, **kwargs):
        self.calls.append(kwargs)
        if self.fail:
            raise RuntimeError("provider credential detail")
        metric_class = next(
            dimension["Value"] for dimension in kwargs["Dimensions"] if dimension["Name"] == "Class"
        )
        value = 32.0 if metric_class.endswith("OnDemand") else 64.0
        return {
            "Datapoints": [
                {
                    "Timestamp": self.observed_at,
                    "Maximum": value,
                }
            ]
        }


def _snapshot(*, quotas=None, cloudwatch=None, ec2=None):
    return build_capacity_snapshot(
        ec2_client=ec2 or _EmptyInventory(),
        autoscaling_client=_EmptyAutoScaling(),
        service_quotas_client=quotas or _Quotas(),
        cloudwatch_client=cloudwatch or _CloudWatch(),
        profile="lsmc",
        account_id="123456789012",
        region="us-west-2",
        quota_families=["standard"],
        now=CAPTURED_AT,
    )


def test_capacity_snapshot_uses_each_quota_usage_metric_as_authority() -> None:
    cloudwatch = _CloudWatch(observed_at=CAPTURED_AT - timedelta(seconds=60))

    payload = _snapshot(cloudwatch=cloudwatch)

    assert payload["schema_version"] == CAPACITY_SNAPSHOT_SCHEMA
    assert payload["status"] == "complete"
    assert payload["complete"] is True
    assert payload["reason_codes"] == []
    assert len(cloudwatch.calls) == 2
    assert [
        (row["capacity_type"], row["used_vcpus"], row["headroom_vcpus"])
        for row in payload["quotas"]
    ] == [
        ("ONDEMAND", 32.0, 224.0),
        ("SPOT", 64.0, 192.0),
    ]
    for call in cloudwatch.calls:
        assert call["Namespace"] == "AWS/Usage"
        assert call["MetricName"] == "ResourceCount"
        assert call["Period"] == 60
        assert call["Statistics"] == ["Maximum"]
    assert payload["inventory_context"]["authoritative"] is False


def test_stale_quota_usage_fails_closed_and_nulls_all_totals() -> None:
    cloudwatch = _CloudWatch(observed_at=CAPTURED_AT - timedelta(seconds=601))

    payload = _snapshot(cloudwatch=cloudwatch)

    assert payload["status"] == "incomplete"
    assert payload["complete"] is False
    assert payload["reason_codes"] == ["quota_usage_metric_timestamp_stale"]
    assert all(row["used_vcpus"] is None for row in payload["quotas"])
    assert all(row["headroom_vcpus"] is None for row in payload["quotas"])


def test_missing_usage_metric_fails_closed_without_guessing_from_instances() -> None:
    ec2 = _EmptyInventory()
    ec2.describe_instances = lambda **_kwargs: {
        "Reservations": [
            {"Instances": [{"InstanceType": "r7i.2xlarge", "State": {"Name": "running"}}]}
        ]
    }
    ec2.describe_instance_types = lambda **_kwargs: {
        "InstanceTypes": [
            {
                "InstanceType": "r7i.2xlarge",
                "VCpuInfo": {"DefaultVCpus": 8},
            }
        ]
    }

    payload = _snapshot(quotas=_Quotas(include_usage_metric=False), ec2=ec2)

    assert payload["complete"] is False
    assert payload["reason_codes"] == ["quota_usage_metric_missing"]
    assert payload["quotas"][0]["context_observed_used_vcpus"] == 8
    assert payload["quotas"][0]["used_vcpus"] is None


def test_cloudwatch_failure_returns_only_bounded_reason_code() -> None:
    payload = _snapshot(cloudwatch=_CloudWatch(fail=True))

    assert payload["complete"] is False
    assert payload["reason_codes"] == ["quota_usage_metric_query_failed"]
    assert "credential" not in str(payload)


def test_optional_inventory_failure_does_not_override_fresh_quota_metric() -> None:
    failing_inventory = SimpleNamespace(
        get_paginator=lambda _operation: (_ for _ in ()).throw(RuntimeError("denied")),
        describe_instances=lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("denied")),
        describe_spot_instance_requests=lambda **_kwargs: (_ for _ in ()).throw(
            RuntimeError("denied")
        ),
        describe_fleets=lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("denied")),
        describe_spot_fleet_requests=lambda **_kwargs: (_ for _ in ()).throw(
            RuntimeError("denied")
        ),
    )

    payload = _snapshot(ec2=failing_inventory)

    assert payload["complete"] is True
    assert payload["inventory_context"]["complete"] is False
    assert payload["inventory_context"]["reason_codes"]
