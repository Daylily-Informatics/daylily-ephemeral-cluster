"""Tests for the cache-first on-demand AWS cost/resource report."""

from __future__ import annotations

import csv
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from daylily_ec.aws.api_call_audit import ExactRequestCache, ServiceRateLimiter
from daylily_ec.aws.on_demand_cost_report import (
    CachedParallelClusterReader,
    OnDemandCostReportConfig,
    ResourceSet,
    _apply_history,
    _collect_parallelclusters,
    run_on_demand_cost_report,
)


FIXED_NOW = datetime(2026, 7, 16, 2, 30, tzinfo=timezone.utc)
ACCOUNT_ID = "108782052779"
INSTANCE_ARN = f"arn:aws:ec2:us-west-2:{ACCOUNT_ID}:instance/i-new"
WIDGET_ARN = f"arn:aws:quantum:us-west-2:{ACCOUNT_ID}:widget/w-new"


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
                "Account": ACCOUNT_ID,
                "Arn": f"arn:aws:iam::{ACCOUNT_ID}:root",
                "UserId": "root-id",
            }
        if (service, operation) == ("budgets", "describe_budgets"):
            return {
                "Budgets": [
                    {
                        "BudgetName": "Research",
                        "BudgetType": "COST",
                        "TimeUnit": "MONTHLY",
                        "BudgetLimit": {"Amount": "1000", "Unit": "USD"},
                        "CalculatedSpend": {
                            "ActualSpend": {"Amount": "125", "Unit": "USD"},
                            "ForecastedSpend": {"Amount": "300", "Unit": "USD"},
                        },
                        "FilterExpression": {
                            "Tags": {
                                "Key": "Project",
                                "Values": ["Alpha"],
                                "MatchOptions": ["EQUALS"],
                            }
                        },
                        "Metrics": ["UnblendedCost"],
                    }
                ]
            }
        if (service, operation) == ("budgets", "describe_notifications_for_budget"):
            return {"Notifications": []}
        if (service, operation) == ("budgets", "describe_budget_actions_for_budget"):
            return {"Actions": []}
        if (service, operation) == ("budgets", "list_tags_for_resource"):
            assert parameters["ResourceARN"].endswith("budget/Research")
            return {"ResourceTags": [{"Key": "Owner", "Value": "FinOps"}]}
        if (service, operation) == ("ce", "get_tags"):
            return {"Tags": ["Project", "Owner"], "ReturnSize": 2, "TotalSize": 2}
        if (service, operation) == ("ce", "get_cost_and_usage"):
            group_by = parameters["GroupBy"]
            first = group_by[0]
            if first == {"Type": "DIMENSION", "Key": "SERVICE"} and group_by[1]["Key"] == "REGION":
                if parameters.get("NextPageToken") == "service-2":
                    return self._cost_page(
                        ["Quantum Compute", "us-west-2"], "7.00"
                    )
                return {
                    **self._cost_page(
                        ["Amazon Elastic Compute Cloud - Compute", "us-west-2"],
                        "13.00",
                    ),
                    "NextPageToken": "service-2",
                }
            if first == {"Type": "DIMENSION", "Key": "SERVICE"} and group_by[1]["Key"] == "USAGE_TYPE":
                return self._cost_page(
                    ["Amazon Elastic Compute Cloud - Compute", "BoxUsage"], "13.00"
                )
            if first.get("Type") == "TAG":
                tag_key = first["Key"]
                tag_value = "Alpha" if tag_key == "Project" else "cluster-a"
                return self._cost_page(
                    [f"{tag_key}${tag_value}", "Quantum Compute"], "7.00"
                )
        if (service, operation) == ("ce", "get_cost_and_usage_with_resources"):
            assert set(parameters["Filter"]["Dimensions"]["Values"]) == {
                "Amazon Elastic Compute Cloud - Compute",
                "Quantum Compute",
            }
            return {
                "ResultsByTime": [
                    {
                        "TimePeriod": {"Start": "2026-07-01", "End": "2026-07-02"},
                        "Groups": [
                            {
                                "Keys": [
                                    "Amazon Elastic Compute Cloud - Compute",
                                    "i-new",
                                ],
                                "Metrics": {
                                    "UnblendedCost": {"Amount": "13", "Unit": "USD"}
                                },
                            },
                            {
                                "Keys": ["Quantum Compute", WIDGET_ARN],
                                "Metrics": {
                                    "UnblendedCost": {"Amount": "7", "Unit": "USD"}
                                },
                            },
                        ],
                    }
                ]
            }
        if (service, operation) == ("ec2", "describe_regions"):
            return {"Regions": [{"RegionName": "us-west-2", "OptInStatus": "opt-in-not-required"}]}
        if (service, operation) == ("resource-explorer-2", "list_indexes"):
            return {"Indexes": [{"Region": "us-west-2", "Type": "LOCAL"}]}
        if (service, operation) == ("resource-explorer-2", "list_resources"):
            filter_string = parameters["Filters"]["FilterString"]
            if filter_string == "tag:none":
                return {"Resources": [self._widget_resource()]}
            return {
                "Resources": [
                    self._widget_resource(),
                    {
                        "Arn": INSTANCE_ARN,
                        "OwningAccountId": ACCOUNT_ID,
                        "Region": "us-west-2",
                        "Service": "ec2",
                        "ResourceType": "ec2:instance",
                        "CfnResourceType": "AWS::EC2::Instance",
                        "Properties": [],
                    },
                ]
            }
        if (service, operation) == ("resourcegroupstaggingapi", "get_resources"):
            return {
                "ResourceTagMappingList": [
                    {
                        "ResourceARN": INSTANCE_ARN,
                        "Tags": [
                            {"Key": "Project", "Value": "Alpha"},
                            {"Key": "Cluster", "Value": "cluster-a"},
                        ],
                    }
                ]
            }
        if (service, operation) == ("cloudformation", "list_stacks"):
            return {
                "StackSummaries": [
                    {
                        "StackName": "cluster-a",
                        "StackId": f"arn:aws:cloudformation:us-west-2:{ACCOUNT_ID}:stack/cluster-a/id",
                        "StackStatus": "CREATE_COMPLETE",
                    }
                ]
            }
        if (service, operation) == ("cloudformation", "list_stack_resources"):
            return {
                "StackResourceSummaries": [
                    {
                        "LogicalResourceId": "HeadNode",
                        "PhysicalResourceId": "i-new",
                        "ResourceType": "AWS::EC2::Instance",
                        "ResourceStatus": "CREATE_COMPLETE",
                    }
                ]
            }
        if (service, operation) == ("ec2", "describe_instances"):
            return {
                "Reservations": [
                    {
                        "Instances": [
                            {
                                "InstanceId": "i-new",
                                "InstanceType": "m7i.large",
                                "State": {"Name": "running"},
                                "Tags": [
                                    {"Key": "Project", "Value": "Alpha"},
                                    {"Key": "Cluster", "Value": "cluster-a"},
                                ],
                            }
                        ]
                    }
                ]
            }
        if (service, operation) in {
            ("ec2", "describe_volumes"),
            ("ec2", "describe_snapshots"),
            ("ec2", "describe_nat_gateways"),
        }:
            key = {
                "describe_volumes": "Volumes",
                "describe_snapshots": "Snapshots",
                "describe_nat_gateways": "NatGateways",
            }[operation]
            return {key: []}
        if (service, operation) == ("ec2", "describe_addresses"):
            return {"Addresses": []}
        if (service, operation) == ("fsx", "describe_file_systems"):
            return {"FileSystems": []}
        if (service, operation) == ("rds", "describe_db_instances"):
            return {"DBInstances": []}
        if (service, operation) == ("rds", "describe_db_clusters"):
            return {"DBClusters": []}
        if (service, operation) == ("elbv2", "describe_load_balancers"):
            return {"LoadBalancers": []}
        if (service, operation) == ("s3", "list_buckets"):
            return {"Buckets": []}
        if (service, operation) == ("cloudwatch", "get_metric_data"):
            return {
                "MetricDataResults": [
                    {
                        "Id": parameters["MetricDataQueries"][0]["Id"],
                        "StatusCode": "Complete",
                        "Values": [10.0, 20.0],
                    }
                ]
            }
        raise AssertionError(f"unexpected fake request {service}.{operation} {parameters}")

    @staticmethod
    def _cost_page(keys: list[str], amount: str) -> dict[str, Any]:
        return {
            "ResultsByTime": [
                {
                    "TimePeriod": {"Start": "2026-07-01", "End": "2026-07-02"},
                    "Groups": [
                        {
                            "Keys": keys,
                            "Metrics": {
                                "UnblendedCost": {"Amount": amount, "Unit": "USD"}
                            },
                        }
                    ],
                }
            ]
        }

    @staticmethod
    def _widget_resource() -> dict[str, Any]:
        return {
            "Arn": WIDGET_ARN,
            "OwningAccountId": ACCOUNT_ID,
            "Region": "us-west-2",
            "Service": "quantum",
            "ResourceType": "quantum:widget",
            "CfnResourceType": "AWS::Quantum::Widget",
            "Properties": [],
        }


def _config(tmp_path: Path, output_name: str, **kwargs: Any) -> OnDemandCostReportConfig:
    values: dict[str, Any] = {
        "profile": "lsmc",
        "account_id": ACCOUNT_ID,
        "start_date": date(2026, 6, 1),
        "end_date": date(2026, 7, 15),
        "resource_start_date": date(2026, 7, 1),
        "control_region": "us-west-2",
        "output_dir": tmp_path / output_name,
        "cache_dir": tmp_path / "cache",
        "history_path": tmp_path / "history.json",
        "initialize_history": True,
        "cost_tag_keys": ("Project",),
        "cluster_tag_keys": ("Cluster",),
        "paid_call_budget": 10,
        "utilization_limit": 10,
        "cache_max_age_seconds": 3600,
        "ce_min_interval_seconds": 0,
        "other_min_interval_seconds": 0,
    }
    values.update(kwargs)
    return OnDemandCostReportConfig(**values)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_full_report_discovers_new_types_tags_budgets_and_reuses_cache(tmp_path: Path) -> None:
    first_fake = FakeAws()
    first = run_on_demand_cost_report(
        _config(tmp_path, "first"),
        session_factory=first_fake.session,
        now=lambda: FIXED_NOW,
        monotonic=lambda: 0.0,
        sleep=lambda _: None,
    )

    assert first["paid_call_guard"]["actual_paid_live_calls"] == 7
    assert first["paid_call_guard"]["actual_estimated_cost_usd_at_observed_rate"] == 0.07
    assert first["counts"]["budgets"] == 1
    assert first["tag_analysis"]["budget_selected_cost_tag_keys"] == ["Project"]
    assert first["tag_analysis"]["selected_cost_tag_keys"] == ["Cluster", "Project"]

    type_rows = _read_csv(tmp_path / "first" / "resource_types.csv")
    quantum = next(row for row in type_rows if row["resource_type"] == "AWS::Quantum::Widget")
    assert quantum["presence"] == "baseline"
    widget = next(
        row
        for row in _read_csv(tmp_path / "first" / "resources.csv")
        if row["arn"] == WIDGET_ARN
    )
    assert widget["tag_state"] == "untagged"
    assert widget["utilization_status"] == "not_supported"
    budget_associations = _read_csv(tmp_path / "first" / "budget_associations.csv")
    assert budget_associations[0]["key"] == "Project"
    assert budget_associations[0]["values"] == "Alpha"
    assert _read_csv(tmp_path / "first" / "budget_tags.csv")[0]["tag_value"] == "FinOps"
    service_tags = _read_csv(tmp_path / "first" / "service_tag_summary.csv")
    assert any(
        row["tag_key"] == "Project" and row["tag_value"] == "Alpha"
        for row in service_tags
    )
    assert _read_csv(tmp_path / "first" / "clusters.csv")[0]["cluster"] == "cluster-a"

    second_fake = FakeAws(forbid_calls=True)
    second = run_on_demand_cost_report(
        _config(
            tmp_path,
            "second",
            initialize_history=False,
            cache_only=True,
            paid_call_budget=0,
        ),
        session_factory=second_fake.session,
        now=lambda: FIXED_NOW,
        monotonic=lambda: 0.0,
        sleep=lambda _: None,
    )
    assert second["request_reuse"]["live_calls"] == 0
    assert second["request_reuse"]["paid_live_calls"] == 0
    assert second["request_reuse"]["cache_hit_ratio"] == 1.0
    assert not second_fake.calls


def test_type_history_retains_disappeared_class_without_claiming_deletion() -> None:
    resources = ResourceSet()
    resources.add(
        source="resource_explorer",
        arn=WIDGET_ARN,
        region="us-west-2",
        service="quantum",
        resource_type="quantum:widget",
        cfn_resource_type="AWS::Quantum::Widget",
    )
    prior = {
        "resource_types": {
            "AWS::Legacy::Gone": {
                "first_seen": "2026-07-01T00:00:00Z",
                "last_seen": "2026-07-15T00:00:00Z",
                "last_count": 1,
                "missing_runs": 0,
            }
        },
        "resources": {
            "arn:aws:legacy:us-west-2:108782052779:thing/old": {
                "resource_key": "arn:aws:legacy:us-west-2:108782052779:thing/old",
                "arn": "arn:aws:legacy:us-west-2:108782052779:thing/old",
                "region": "us-west-2",
                "service": "legacy",
                "resource_type": "AWS::Legacy::Gone",
                "resource_id": "old",
                "first_seen": "2026-07-01T00:00:00Z",
                "last_seen": "2026-07-15T00:00:00Z",
                "missing_runs": 0,
                "last_lifecycle_status": "active",
            }
        },
    }

    type_rows, _ = _apply_history(
        resources,
        prior=prior,
        generated_at="2026-07-16T02:30:00Z",
        account_id=ACCOUNT_ID,
        cost_services=[],
    )

    gone = next(row for row in type_rows if row["resource_type"] == "AWS::Legacy::Gone")
    assert gone["presence"] == "disappeared"
    old_resource = resources.records[
        "arn:aws:legacy:us-west-2:108782052779:thing/old"
    ]
    assert old_resource["presence"] == "disappeared"
    assert old_resource["lifecycle_status"] == "unresolved"
    assert "not proof of deletion" in old_resource["lifecycle_evidence"]


def test_parallelcluster_reader_caches_stopped_compute_fleet(tmp_path: Path) -> None:
    executable = tmp_path / "pcluster"
    executable.write_text("placeholder", encoding="utf-8")
    calls: list[list[str]] = []

    def command_runner(command, environment):
        calls.append(list(command))
        if "list-clusters" in command:
            stdout = json.dumps(
                {
                    "clusters": [
                        {"clusterName": "stopped-a", "clusterStatus": "CREATE_COMPLETE"}
                    ]
                }
            )
        else:
            stdout = json.dumps({"status": "STOPPED"})
        return type("Completed", (), {"returncode": 0, "stdout": stdout, "stderr": ""})()

    cache = ExactRequestCache(
        tmp_path / "cache", max_age_seconds=3600, now=lambda: FIXED_NOW
    )
    first = CachedParallelClusterReader(
        executable=executable,
        profile="lsmc",
        account_id=ACCOUNT_ID,
        cache=cache,
        limiter=ServiceRateLimiter({"*": 0}),
        cache_only=False,
        refresh=False,
        command_runner=command_runner,
    )
    rows = _collect_parallelclusters(first, ["us-west-2"])
    assert rows[0]["lifecycle_status"] == "stopped"
    assert len(calls) == 2

    def forbid(*_):
        raise AssertionError("unexpected pcluster command")

    second = CachedParallelClusterReader(
        executable=executable,
        profile="lsmc",
        account_id=ACCOUNT_ID,
        cache=cache,
        limiter=ServiceRateLimiter({"*": 0}),
        cache_only=True,
        refresh=False,
        command_runner=forbid,
    )
    second_rows = _collect_parallelclusters(second, ["us-west-2"])
    assert second_rows[0]["compute_fleet_status"] == "STOPPED"
    assert second.stats.live_calls == 0
    assert second.stats.cache_hits == 2


def test_report_config_rejects_more_than_three_dollars(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="may not exceed 300"):
        _config(tmp_path, "output", paid_call_budget=301).validate()
