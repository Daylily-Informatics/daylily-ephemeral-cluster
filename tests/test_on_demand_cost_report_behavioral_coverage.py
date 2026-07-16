"""Behavioral coverage for cost-report validation and provider classification."""

from __future__ import annotations

import json
import subprocess
from dataclasses import replace
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

import daylily_ec.aws.on_demand_cost_report as c
from daylily_ec.aws.api_call_audit import ExactRequestCache, ServiceRateLimiter

ACCOUNT = "108782052779"


def _config(tmp_path: Path, **overrides) -> c.OnDemandCostReportConfig:
    values = dict(
        profile="lsmc",
        account_id=ACCOUNT,
        start_date=date(2026, 7, 1),
        end_date=date(2026, 7, 15),
        resource_start_date=date(2026, 7, 2),
        control_region="us-west-2",
        output_dir=tmp_path / "out",
        cache_dir=tmp_path / "cache",
        history_path=tmp_path / "history.json",
        initialize_history=True,
        cost_tag_keys=("Project",),
        cluster_tag_keys=("Cluster",),
        paid_call_budget=1,
        utilization_limit=10,
        cache_max_age_seconds=3600,
        ce_min_interval_seconds=0,
        other_min_interval_seconds=0,
    )
    values.update(overrides)
    return c.OnDemandCostReportConfig(**values)


@pytest.mark.parametrize(
    "changes",
    [
        {"profile": ""},
        {"account_id": "bad"},
        {"start_date": date(2026, 7, 15)},
        {"resource_start_date": date(2026, 6, 30)},
        {"resource_start_date": date(2026, 6, 1)},
        {
            "start_date": date(2026, 6, 1),
            "resource_start_date": date(2026, 6, 20),
            "end_date": date(2026, 7, 15),
        },
        {"control_region": ""},
        {"paid_call_budget": -1},
        {"cache_only": True, "refresh": True},
        {"cache_max_age_seconds": -1},
        {"utilization_limit": -1},
        {"utilization_period_seconds": 0},
        {"ce_min_interval_seconds": -1},
        {"cost_tag_keys": ("Project", "")},
        {"cluster_tag_keys": ("Cluster", "Cluster")},
        {"parallelcluster_regions": ("",), "parallelcluster_executable": Path("pcluster")},
        {"parallelcluster_regions": ("us-west-2",)},
        {"parallelcluster_executable": Path("pcluster")},
    ],
)
def test_config_validation_rejects_each_invalid_contract(tmp_path, changes):
    with pytest.raises(ValueError):
        replace(_config(tmp_path), **changes).validate()


def test_jsonable_lifecycle_tag_and_resource_helpers(tmp_path):
    now = c._utc_now()
    assert now.tzinfo == timezone.utc
    assert c._jsonable(datetime(2026, 1, 1, tzinfo=timezone.utc)).startswith("2026-01-01")
    assert c._jsonable(tmp_path) == str(tmp_path)
    assert c._jsonable(object()).startswith("<object object")
    assert c._arn_parts("not-an-arn") == ("", "", "", "")
    assert c._resource_key(arn="", region="west", type_key="type", resource_id="id").startswith(
        "aws-resource://"
    )
    assert c._resource_explorer_tags(
        [{"Name": "tags", "Data": {"Tags": [{"Key": "A", "Value": "B"}]}}]
    ) == {"A": "B"}
    assert c._resource_explorer_tags([{"Name": "tags", "Data": {"A": "B"}}]) == {"A": "B"}
    assert c._resource_explorer_tags([{"Name": "tags", "Data": [{"key": "A", "value": "B"}]}]) == {
        "A": "B"
    }
    assert c._tags_map(["bad", {"Key": "A", "Value": "B"}]) == {"A": "B"}

    stack_states = {
        "DELETE_COMPLETE": "deleted",
        "DELETE_IN_PROGRESS": "deleting",
        "CREATE_FAILED": "exception",
        "ROLLBACK_COMPLETE": "exception_recovered",
        "UPDATE_IN_PROGRESS": "provisioning_or_updating",
        "CREATE_COMPLETE": "active",
    }
    for state, expected in stack_states.items():
        assert c._stack_lifecycle(state) == expected
    provider_states = {
        (False, "running"): "unresolved",
        (True, "stopped"): "stopped",
        (True, "terminated"): "deleted",
        (True, "deleting"): "deleting",
        (True, "failed"): "exception",
        (True, "pending"): "provisioning_or_updating",
        (True, "running"): "active",
    }
    for (exists, state), expected in provider_states.items():
        assert c._provider_lifecycle(state, exists=exists) == expected


def test_pagination_detects_token_cycles_and_flatten_skips_malformed_rows():
    class Reader:
        def call(self, **kwargs):
            return {"rows": [], "Next": "same"}

    with pytest.raises(c.OnDemandCostReportError, match="pagination token cycle"):
        list(
            c._paginate(
                Reader(),
                service="svc",
                region="r",
                operation="op",
                parameters={},
                request_token="Token",
                response_token="Next",
            )
        )
    rows = c._flatten_cost_pages(
        [
            {
                "ResultsByTime": [
                    "bad",
                    {
                        "TimePeriod": {"Start": "s", "End": "e"},
                        "Groups": [
                            "bad",
                            {
                                "Keys": ["service", "resource"],
                                "Metrics": {"UnblendedCost": {"Amount": "2", "Unit": "USD"}},
                            },
                        ],
                    },
                ]
            }
        ],
        ("service", "resource_id"),
    )
    assert rows[0]["cost_usd"] == 2.0


def test_budget_expression_and_legacy_association_parsing():
    expression = {
        "And": [
            {"Tags": {"Key": "Project", "Values": "Alpha", "MatchOptions": ["EQUALS"]}},
            {"Not": {"Dimensions": {"Key": "SERVICE", "Values": ["EC2"]}}},
        ]
    }
    rows = c._budget_expression_associations(expression, budget_name="Budget")
    assert {row["expression_path"] for row in rows} == {
        "filter_expression.and[0]",
        "filter_expression.and[1].not",
    }
    assert c._budget_expression_associations("bad", budget_name="Budget") == []
    legacy = c._legacy_budget_associations({"TagKeyValue": "Project$Alpha"}, budget_name="Budget")
    assert legacy[0]["values"] == "Project$Alpha"
    assert c._budget_cost_tag_keys(rows + legacy) == {"Project"}
    assert c._spend_fields(None, "actual") == {"actual_amount": None, "actual_unit": ""}


def test_parallelcluster_reader_validation_and_response_failures(tmp_path):
    with pytest.raises(c.OnDemandCostReportError, match="does not exist"):
        c.CachedParallelClusterReader(
            executable=tmp_path / "missing",
            profile="lsmc",
            account_id=ACCOUNT,
            cache=ExactRequestCache(tmp_path / "cache", max_age_seconds=0),
            limiter=ServiceRateLimiter({"*": 0}),
            cache_only=False,
            refresh=False,
        )

    executable = tmp_path / "pcluster"
    executable.write_text("x", encoding="utf-8")

    def make_runner(returncode=0, stdout="{}", stderr=""):
        return lambda command, environment: subprocess.CompletedProcess(
            command, returncode, stdout, stderr
        )

    reader = c.CachedParallelClusterReader(
        executable=executable,
        profile="lsmc",
        account_id=ACCOUNT,
        cache=ExactRequestCache(tmp_path / "cache-a", max_age_seconds=0),
        limiter=ServiceRateLimiter({"*": 0}),
        cache_only=False,
        refresh=True,
        command_runner=make_runner(),
    )
    with pytest.raises(c.OnDemandCostReportError, match="requires cluster_name"):
        reader.call(region="us-west-2", operation="describe_compute_fleet")
    with pytest.raises(c.OnDemandCostReportError, match="unsupported"):
        reader.call(region="us-west-2", operation="delete_cluster")

    for name, runner, message in (
        ("failed", make_runner(2, stderr="denied"), "failed"),
        ("bad-json", make_runner(stdout="not-json"), "non-JSON"),
        ("array", make_runner(stdout="[]"), "non-object"),
    ):
        broken = c.CachedParallelClusterReader(
            executable=executable,
            profile="lsmc",
            account_id=ACCOUNT,
            cache=ExactRequestCache(tmp_path / name, max_age_seconds=0),
            limiter=ServiceRateLimiter({"*": 0}),
            cache_only=False,
            refresh=True,
            command_runner=runner,
        )
        with pytest.raises(c.OnDemandCostReportError, match=message):
            broken.call(region="us-west-2", operation="list_clusters")


class _InventoryReader:
    def call(self, *, service, region, operation, parameters=None, **_kwargs):
        payloads = {
            "describe_instances": {
                "Reservations": [
                    {
                        "Instances": [
                            "bad",
                            {
                                "InstanceId": "i-1",
                                "State": {"Name": "running"},
                                "Tags": [{"Key": "Cluster", "Value": "c"}],
                            },
                        ]
                    }
                ]
            },
            "describe_volumes": {"Volumes": ["bad", {"VolumeId": "vol-1", "State": "available"}]},
            "describe_snapshots": {
                "Snapshots": ["bad", {"SnapshotId": "snap-1", "State": "completed"}]
            },
            "describe_addresses": {"Addresses": ["bad", {}, {"PublicIp": "1.2.3.4"}]},
            "describe_nat_gateways": {
                "NatGateways": ["bad", {"NatGatewayId": "nat-1", "State": "available"}]
            },
            "describe_file_systems": {
                "FileSystems": ["bad", {"FileSystemId": "fs-1", "Lifecycle": "AVAILABLE"}]
            },
            "describe_db_instances": {
                "DBInstances": [
                    "bad",
                    {"DBInstanceIdentifier": "db-1", "DBInstanceStatus": "available"},
                ]
            },
            "describe_db_clusters": {
                "DBClusters": ["bad", {"DBClusterIdentifier": "dbc-1", "Status": "available"}]
            },
            "describe_load_balancers": {
                "LoadBalancers": [
                    "bad",
                    {
                        "LoadBalancerArn": f"arn:aws:elasticloadbalancing:us-west-2:{ACCOUNT}:loadbalancer/app/lb/id",
                        "LoadBalancerName": "lb",
                        "State": {"Code": "active"},
                    },
                ]
            },
            "list_buckets": {"Buckets": ["bad", {}, {"Name": "bucket"}]},
        }
        return payloads[operation]


def test_direct_provider_inventory_classifies_every_supported_provider():
    resources = c.ResourceSet()
    c._direct_provider_inventory(
        _InventoryReader(),
        account_id=ACCOUNT,
        regions=["us-west-2"],
        control_region="us-west-2",
        resources=resources,
    )
    types = {row["cfn_resource_type"] for row in resources.records.values()}
    assert {
        "AWS::EC2::Instance",
        "AWS::EC2::Volume",
        "AWS::EC2::Snapshot",
        "AWS::EC2::EIP",
        "AWS::EC2::NatGateway",
        "AWS::FSx::FileSystem",
        "AWS::RDS::DBInstance",
        "AWS::RDS::DBCluster",
        "AWS::ElasticLoadBalancingV2::LoadBalancer",
        "AWS::S3::Bucket",
    } <= types


def test_cost_attachment_history_validation_and_all_cluster_classifications(tmp_path):
    resources = c.ResourceSet()
    current = resources.add(
        source="provider",
        arn=f"arn:aws:ec2:us-west-2:{ACCOUNT}:instance/i-1",
        region="us-west-2",
        service="ec2",
        resource_type="ec2:instance",
        cfn_resource_type="AWS::EC2::Instance",
        resource_id="i-1",
        tags={"Cluster": "resource-only"},
    )
    c._attach_resource_costs(
        resources,
        [
            {"service": "EC2", "resource_id": "", "cost_usd": 10},
            {"service": "EC2", "resource_id": "i-1", "cost_usd": 2},
            {"service": "Mystery", "resource_id": "unknown", "cost_usd": 3},
        ],
    )
    assert current["cost_usd"] == 2
    assert any(row.get("presence") == "cost_history_only" for row in resources.records.values())

    config = _config(tmp_path)
    config.history_path.write_text("{}", encoding="utf-8")
    with pytest.raises(c.HistoryContractError, match="already exists"):
        c._read_history(config)
    config.history_path.write_text("not-json", encoding="utf-8")
    with pytest.raises(c.HistoryContractError, match="unable to read"):
        c._read_history(replace(config, initialize_history=False))
    for payload, message in (
        ([], "JSON object"),
        ({"schema_version": -1}, "unsupported history schema"),
        ({"schema_version": c.HISTORY_SCHEMA_VERSION, "account_id": "other"}, "does not match"),
        (
            {"schema_version": c.HISTORY_SCHEMA_VERSION, "account_id": ACCOUNT},
            "catalogs are malformed",
        ),
    ):
        config.history_path.write_text(json.dumps(payload), encoding="utf-8")
        with pytest.raises(c.HistoryContractError, match=message):
            c._read_history(replace(config, initialize_history=False))

    rows = c._cluster_rows(
        resources=resources,
        parallelclusters=[
            {"cluster": "pcluster", "region": "us-west-2", "lifecycle_status": "active"}
        ],
        stacks=[
            {"stack_name": "stack-only", "region": "us-west-2", "lifecycle_status": "active"},
            {
                "stack_name": "deleted",
                "region": "us-east-1",
                "lifecycle_status": "deleted",
                "deletion_time": "now",
            },
        ],
        cost_by_tag_rows=[
            {"tag_key": "Cluster", "tag_value": "unresolved", "cost_usd": 4},
            {"tag_key": "Other", "tag_value": "ignored", "cost_usd": 9},
            {"tag_key": "Cluster", "tag_value": "NoTagValue", "cost_usd": 9},
        ],
        cluster_tag_keys=["Cluster"],
    )
    by_name = {row["cluster"]: row for row in rows}
    assert by_name["pcluster"]["lifecycle_status"] == "active"
    assert by_name["stack-only"]["classification_evidence"].startswith("same-name live")
    assert by_name["resource-only"]["lifecycle_status"] == "orphaned"
    assert by_name["deleted"]["lifecycle_status"] == "deleted"
    assert by_name["unresolved"]["lifecycle_status"] == "unresolved"
    assert c._empty_budget_data()["budgets"] == []


def test_budget_collection_captures_notifications_subscribers_actions_and_tags():
    class Reader:
        def call(self, *, operation, **_kwargs):
            return {
                "describe_budgets": {
                    "Budgets": [
                        {
                            "BudgetName": "Research",
                            "BudgetLimit": {"Amount": "10", "Unit": "USD"},
                            "CostFilters": {"TagKeyValue": ["Project$Alpha"]},
                        }
                    ]
                },
                "describe_notifications_for_budget": {
                    "Notifications": [
                        {"NotificationType": "ACTUAL", "Threshold": 80},
                    ]
                },
                "describe_subscribers_for_notification": {
                    "Subscribers": ["bad", {"SubscriptionType": "EMAIL", "Address": "a@b"}]
                },
                "describe_budget_actions_for_budget": {
                    "Actions": ["bad", {"ActionId": "a", "Definition": {"x": 1}}]
                },
                "list_tags_for_resource": {
                    "ResourceTags": ["bad", {"Key": "Owner", "Value": "FinOps"}]
                },
            }[operation]

    result = c._collect_budgets(Reader(), account_id=ACCOUNT, region="us-east-1")
    assert result["budgets"][0]["notification_count"] == 1
    assert result["subscribers"][0]["Address"] == "a@b"
    assert result["actions"][0]["Definition"] == '{"x": 1}'
    assert result["budget_tags"][0]["tag_value"] == "FinOps"


def test_region_utilization_and_output_preconditions(tmp_path):
    class EmptyRegions:
        def call(self, **_kwargs):
            return {"Regions": []}

    with pytest.raises(c.OnDemandCostReportError, match="no enabled regions"):
        c._enabled_regions(EmptyRegions(), "us-west-2")

    resources = c.ResourceSet()
    selected = resources.add(
        source="provider",
        arn=f"arn:aws:ec2:us-west-2:{ACCOUNT}:instance/i-1",
        region="us-west-2",
        service="ec2",
        resource_type="ec2:instance",
        cfn_resource_type="AWS::EC2::Instance",
        resource_id="i-1",
    )
    selected["cost_usd"] = 10
    unselected = resources.add(
        source="provider",
        arn=f"arn:aws:ec2:us-west-2:{ACCOUNT}:instance/i-2",
        region="us-west-2",
        service="ec2",
        resource_type="ec2:instance",
        cfn_resource_type="AWS::EC2::Instance",
        resource_id="i-2",
    )
    unselected["cost_usd"] = 1

    class Metrics:
        def call(self, **_kwargs):
            return {"MetricDataResults": ["bad"]}

    rows = c._collect_utilization(
        Metrics(), replace(_config(tmp_path), utilization_limit=1), resources
    )
    assert selected["utilization_status"] == "no_datapoints"
    assert unselected["utilization_status"] == "not_selected"
    assert rows[0]["status"] == "no_datapoints"

    output = tmp_path / "occupied"
    output.mkdir()
    (output / "file").write_text("x", encoding="utf-8")
    with pytest.raises(c.OnDemandCostReportError, match="refusing to overwrite"):
        c.run_on_demand_cost_report(_config(tmp_path, output_dir=output))
