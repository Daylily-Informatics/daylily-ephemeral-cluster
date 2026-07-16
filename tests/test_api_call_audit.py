"""Tests for cached and throttled AWS API call attribution."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from daylily_ec.aws.api_call_audit import (
    ApiCallAuditConfig,
    CacheEntryError,
    CacheMissError,
    CachedAwsReader,
    ExactRequestCache,
    PaidCallBudgetExceeded,
    ServiceRateLimiter,
    run_api_call_audit,
)


FIXED_NOW = datetime(2026, 7, 16, 1, 30, tzinfo=timezone.utc)


class FakeAws:
    def __init__(self, *, forbid_calls: bool = False) -> None:
        self.forbid_calls = forbid_calls
        self.calls: list[tuple[str, str, str, dict[str, Any]]] = []

    def session(self, *, profile_name: str):
        assert profile_name == "lsmc"
        parent = self

        class Session:
            def client(self, service: str, *, region_name: str, config: Any):
                assert config.retries["total_max_attempts"] == 1

                class Client:
                    def __getattr__(self, operation: str):
                        def invoke(**parameters: Any) -> dict[str, Any]:
                            if parent.forbid_calls:
                                raise AssertionError(
                                    f"unexpected live call {service}.{operation}"
                                )
                            parent.calls.append((service, region_name, operation, parameters))
                            return parent.response(service, operation, parameters)

                        return invoke

                return Client()

        return Session()

    def response(
        self,
        service: str,
        operation: str,
        parameters: dict[str, Any],
    ) -> dict[str, Any]:
        if (service, operation) == ("sts", "get_caller_identity"):
            return {
                "Account": "108782052779",
                "Arn": "arn:aws:iam::108782052779:root",
                "UserId": "root-id",
            }
        if (service, operation) == ("ce", "get_cost_and_usage"):
            return {
                "ResultsByTime": [
                    {
                        "TimePeriod": {"Start": "2026-07-01", "End": "2026-07-02"},
                        "Estimated": True,
                        "Groups": [
                            {
                                "Keys": ["GetCostAndUsage"],
                                "Metrics": {
                                    "UnblendedCost": {"Amount": "0.10", "Unit": "USD"},
                                    "UsageQuantity": {"Amount": "10", "Unit": "N/A"},
                                },
                            }
                        ],
                    }
                ]
            }
        if (service, operation) == ("cloudtrail", "lookup_events"):
            detail = {
                "eventTime": "2026-07-01T05:57:21Z",
                "eventName": "GetCostAndUsage",
                "userIdentity": {
                    "arn": "arn:aws:iam::108782052779:user/daylily-service",
                    "userName": "daylily-service",
                    "accessKeyId": "AKIARSU7KMWVZQF7TB64",
                },
                "sourceIPAddress": "52.89.110.76",
                "userAgent": "Boto3/1.43.15 Botocore/1.43.15",
                "requestParameters": {
                    "timePeriod": {"start": "2026-06-25", "end": "2026-07-02"},
                    "granularity": "MONTHLY",
                    "metrics": ["AmortizedCost"],
                    "groupBy": [
                        {"type": "TAG", "key": "aws-parallelcluster-clustername"},
                        {"type": "DIMENSION", "key": "SERVICE"},
                    ],
                },
            }
            return {
                "Events": [
                    {
                        "EventName": "GetCostAndUsage",
                        "EventTime": "2026-07-01T05:57:21Z",
                        "Username": "daylily-service",
                        "CloudTrailEvent": json.dumps(detail),
                    }
                ]
            }
        if (service, operation) == ("ec2", "describe_addresses"):
            return {
                "Addresses": [
                    {
                        "PublicIp": parameters["PublicIps"][0],
                        "PrivateIpAddress": "10.0.0.222",
                        "AllocationId": "eipalloc-04969423b36b3de9b",
                        "NetworkInterfaceId": "eni-00d0d767fe52379a8",
                        "InstanceId": "i-07df3a933e4839f52",
                    }
                ]
            }
        if (service, operation) == ("ec2", "describe_instances"):
            return {
                "Reservations": [
                    {
                        "Instances": [
                            {
                                "InstanceId": parameters["InstanceIds"][0],
                                "InstanceType": "t3.2xlarge",
                                "State": {"Name": "running"},
                                "Tags": [
                                    {"Key": "Name", "Value": "Dayhoff-day-Compute/Hostprimary"},
                                    {
                                        "Key": "aws:cloudformation:stack-name",
                                        "Value": "Dayhoff-day-Compute",
                                    },
                                    {"Key": "Environment", "Value": "day"},
                                    {"Key": "Project", "Value": "LSMC"},
                                    {"Key": "Roles", "Value": "ursa"},
                                ],
                            }
                        ]
                    }
                ]
            }
        if (service, operation) == ("iam", "get_user"):
            return {
                "User": {
                    "UserName": parameters["UserName"],
                    "CreateDate": "2025-02-19T05:20:27Z",
                }
            }
        if (service, operation) == ("iam", "list_access_keys"):
            return {
                "AccessKeyMetadata": [
                    {
                        "UserName": parameters["UserName"],
                        "AccessKeyId": "AKIARSU7KMWVZQF7TB64",
                        "Status": "Active",
                        "CreateDate": "2025-02-19T05:33:01Z",
                    }
                ]
            }
        if (service, operation) == ("iam", "get_access_key_last_used"):
            return {
                "AccessKeyLastUsed": {
                    "LastUsedDate": "2026-07-16T01:07:00Z",
                    "ServiceName": "ce",
                    "Region": "us-east-1",
                }
            }
        raise AssertionError(f"unexpected fake request {service}.{operation}")


def _reader(
    tmp_path: Path,
    fake: FakeAws,
    *,
    paid_call_budget: int = 1,
    cache_only: bool = False,
) -> CachedAwsReader:
    return CachedAwsReader(
        profile="lsmc",
        account_id="108782052779",
        cache=ExactRequestCache(
            tmp_path / "cache",
            max_age_seconds=3600,
            now=lambda: FIXED_NOW,
        ),
        limiter=ServiceRateLimiter({"*": 0}),
        paid_call_budget=paid_call_budget,
        cache_only=cache_only,
        session_factory=fake.session,
    )


def test_exact_request_cache_is_reused_by_a_new_reader(tmp_path: Path) -> None:
    first_fake = FakeAws()
    first = _reader(tmp_path, first_fake)
    parameters = {"TimePeriod": {"Start": "2026-07-01", "End": "2026-07-02"}}

    first_response = first.call(
        service="ce",
        region="us-east-1",
        operation="get_cost_and_usage",
        parameters=parameters,
        paid=True,
    )
    second_response = first.call(
        service="ce",
        region="us-east-1",
        operation="get_cost_and_usage",
        parameters=parameters,
        paid=True,
    )

    assert first_response == second_response
    assert len(first_fake.calls) == 1
    assert first.stats.live_calls == 1
    assert first.stats.cache_hits == 1

    second_fake = FakeAws(forbid_calls=True)
    second = _reader(tmp_path, second_fake)
    assert (
        second.call(
            service="ce",
            region="us-east-1",
            operation="get_cost_and_usage",
            parameters=parameters,
            paid=True,
        )
        == first_response
    )
    assert second.stats.live_calls == 0
    assert second.stats.paid_live_calls == 0
    assert second.stats.cache_hits == 1


def test_paid_call_budget_is_checked_before_second_live_call(tmp_path: Path) -> None:
    fake = FakeAws()
    reader = _reader(tmp_path, fake, paid_call_budget=1)
    reader.call(
        service="ce",
        region="us-east-1",
        operation="get_cost_and_usage",
        parameters={"query": "one"},
        paid=True,
    )

    with pytest.raises(PaidCallBudgetExceeded, match="budget 1"):
        reader.call(
            service="ce",
            region="us-east-1",
            operation="get_cost_and_usage",
            parameters={"query": "two"},
            paid=True,
        )

    assert len(fake.calls) == 1


def test_paid_call_budget_cannot_exceed_three_dollar_ceiling(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match=r"hard ceiling is \$3\.00"):
        _reader(tmp_path, FakeAws(), paid_call_budget=301)


def test_cache_only_miss_fails_without_live_call(tmp_path: Path) -> None:
    fake = FakeAws(forbid_calls=True)
    reader = _reader(tmp_path, fake, paid_call_budget=0, cache_only=True)

    with pytest.raises(CacheMissError, match="Cache-only request is missing"):
        reader.call(
            service="sts",
            region="us-east-1",
            operation="get_caller_identity",
        )

    assert reader.stats.live_calls == 0
    assert not fake.calls


def test_corrupt_cache_fails_hard_without_requery(tmp_path: Path) -> None:
    fake = FakeAws()
    reader = _reader(tmp_path, fake)
    reader.call(
        service="sts",
        region="us-east-1",
        operation="get_caller_identity",
    )
    cache_file = next((tmp_path / "cache").rglob("*.json"))
    payload = json.loads(cache_file.read_text(encoding="utf-8"))
    payload["response_sha256"] = "not-the-response-digest"
    cache_file.write_text(json.dumps(payload), encoding="utf-8")

    second = _reader(tmp_path, FakeAws(forbid_calls=True))
    with pytest.raises(CacheEntryError, match="digest mismatch"):
        second.call(
            service="sts",
            region="us-east-1",
            operation="get_caller_identity",
        )


def test_service_rate_limiter_spaces_live_calls() -> None:
    clock = {"value": 10.0}
    sleeps: list[float] = []

    def monotonic() -> float:
        return clock["value"]

    def sleep(seconds: float) -> None:
        sleeps.append(seconds)
        clock["value"] += seconds

    limiter = ServiceRateLimiter(
        {"cloudtrail": 0.5, "*": 0.2},
        monotonic=monotonic,
        sleep=sleep,
    )

    assert limiter.wait("cloudtrail") == 0
    assert limiter.wait("cloudtrail") == 0.5
    assert limiter.wait("iam") == 0
    assert limiter.wait("iam") == 0.2
    assert sleeps == [0.5, 0.2]
    assert limiter.total_sleep_seconds == 0.7


def _audit_config(tmp_path: Path, output_name: str) -> ApiCallAuditConfig:
    return ApiCallAuditConfig(
        profile="lsmc",
        account_id="108782052779",
        start_date=date(2026, 7, 1),
        end_date=date(2026, 7, 2),
        trail_region="us-east-1",
        resource_regions=("us-west-2",),
        output_dir=tmp_path / output_name,
        cache_dir=tmp_path / "cache",
        cache_max_age_seconds=3600,
        cloudtrail_slices_per_day=1,
        cloudtrail_events_per_slice=1,
        top_source_ips=1,
        top_principals=1,
        paid_call_budget=1,
        ce_min_interval_seconds=0,
        cloudtrail_min_interval_seconds=0,
        other_min_interval_seconds=0,
    )


def test_complete_second_run_uses_only_persistent_cache(tmp_path: Path) -> None:
    first_fake = FakeAws()
    first = run_api_call_audit(
        _audit_config(tmp_path, "first"),
        session_factory=first_fake.session,
        now=lambda: FIXED_NOW,
        sleep=lambda _seconds: None,
    )

    assert first["billed_api_requests"] == 10
    assert first["billed_api_cost_usd"] == 0.1
    assert first["request_reuse"]["live_calls"] == 8
    assert first["request_reuse"]["paid_live_calls"] == 1
    assert first["mapped_origins"][0]["instance_name"] == "Dayhoff-day-Compute/Hostprimary"
    assert first["top_principals"][0]["sample_share_pct"] == 100.0

    second_fake = FakeAws(forbid_calls=True)
    second = run_api_call_audit(
        _audit_config(tmp_path, "second"),
        session_factory=second_fake.session,
        now=lambda: FIXED_NOW,
        sleep=lambda _seconds: None,
    )

    assert second["request_reuse"]["live_calls"] == 0
    assert second["request_reuse"]["paid_live_calls"] == 0
    assert second["request_reuse"]["cache_hits"] == 8
    assert second["request_reuse"]["cache_hit_ratio"] == 1.0
    assert not second_fake.calls
    assert (tmp_path / "second" / "summary.json").is_file()
    request_shapes = (tmp_path / "second" / "request_shapes.csv").read_text(
        encoding="utf-8"
    )
    assert "aws-parallelcluster-clustername" in request_shapes
    assert "AmortizedCost" in request_shapes
