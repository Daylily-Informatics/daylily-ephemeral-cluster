from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import daylily_ec.aws.validation as validation_module
from daylily_ec.aws.cur_export import (
    CUR_EXPORT_COLUMNS,
    DATA_EXPORTS_TABLE,
    billing_period_data_location,
    build_cur2_export_definition,
    data_exports_bucket_policy_statement,
    glue_table_input,
)
from daylily_ec.aws.validation import (
    AwsValidationReport,
    _check_budget_count_quota,
    _check_athena_active_dml_quota,
    _check_cost_center_registry_readiness,
    _check_cur_catalog_readiness,
    _check_cur_export_count_quota,
    _check_cur_export_readiness,
    _check_dynamodb_table_count_quota,
    _check_slurm_accounting_resource_quotas,
    _enrich_network_quota_headroom,
    _enrich_budget_readiness,
    _permission_groups,
    _policy_allows,
    check_runtime_cost_policy,
    write_gap_analysis,
)
from daylily_ec.config.models import ConfigFile, Triplet
from daylily_ec.state.models import CheckResult, CheckStatus


ACCOUNT_ID = "123456789012"


def _context(**clients):
    client_map = dict(clients)
    session = SimpleNamespace(client=lambda service, region_name=None: client_map[service])
    return SimpleNamespace(
        account_id=ACCOUNT_ID,
        caller_arn=f"arn:aws:iam::{ACCOUNT_ID}:user/alice",
        iam_username="alice",
        profile="dev",
        region="us-west-2",
        region_az="us-west-2b",
        session=session,
        client=lambda service: client_map[service],
    )


def _cfg() -> ConfigFile:
    return ConfigFile()


def test_permission_catalog_covers_recent_cost_control_surfaces() -> None:
    groups = _permission_groups(_context())
    actions = {action for group in groups for action in group.actions}
    resources = {resource for group in groups for resource in group.resources}

    assert {
        "budgets:ViewBudget",
        "budgets:ModifyBudget",
        "billing:GetBillingViewData",
        "dynamodb:GetItem",
        "dynamodb:Scan",
        "bcm-data-exports:ListExports",
        "bcm-data-exports:GetTable",
        "bcm-data-exports:CreateExport",
        "bcm-data-exports:UpdateExport",
        "bcm-data-exports:ListExecutions",
        "cur:PutReportDefinition",
        "glue:GetPartition",
        "glue:CreatePartition",
        "athena:StartQueryExecution",
        "athena:GetQueryResults",
        "cloudformation:ListStacks",
        "ec2:DescribeRouteTables",
        "ec2:DescribeSpotInstanceRequests",
        "scheduler:UpdateSchedule",
        "sns:ListSubscriptionsByTopic",
        "secretsmanager:DescribeSecret",
    } <= actions
    assert f"arn:aws:dynamodb:us-west-2:{ACCOUNT_ID}:table/dayec-cost-centers" in resources
    assert f"arn:aws:dynamodb:us-west-2:{ACCOUNT_ID}:table/dayec-cost-center-usage" in resources
    assert any(
        group.check_id == "service_linked_role_budgets"
        and group.context == (("iam:AWSServiceName", ("budgets.amazonaws.com",)),)
        for group in groups
    )


def test_cost_center_freshness_limit_is_48_hours() -> None:
    assert validation_module.COST_CENTER_MAX_USAGE_AGE_HOURS == 48


def test_permission_catalog_scopes_sns_to_configured_cluster_topic() -> None:
    groups = _permission_groups(
        _context(),
        cfg=SimpleNamespace(
            ephemeral_cluster=SimpleNamespace(
                config={
                    "cluster_name": Triplet(
                        action="USESETVALUE",
                        set_value="majors-cluster",
                    )
                }
            )
        ),
    )

    sns_group = next(group for group in groups if group.check_id == "sns_topic")
    assert sns_group.resources == (
        f"arn:aws:sns:us-west-2:{ACCOUNT_ID}:daylily-majors-cluster-heartbeat",
    )


def test_runtime_cost_policy_inspects_default_version_and_exact_tables() -> None:
    policy_arn = f"arn:aws:iam::{ACCOUNT_ID}:policy/pclusterTagsAndBudget"
    iam = MagicMock()
    iam.get_policy.return_value = {"Policy": {"Arn": policy_arn, "DefaultVersionId": "v7"}}
    iam.get_policy_version.return_value = {
        "PolicyVersion": {
            "Document": {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": ["budgets:ViewBudget", "billing:GetBillingViewData"],
                        "Resource": "*",
                    },
                    {
                        "Effect": "Allow",
                        "Action": "dynamodb:GetItem",
                        "Resource": [
                            f"arn:aws:dynamodb:us-west-2:{ACCOUNT_ID}:table/dayec-cost-centers",
                            f"arn:aws:dynamodb:us-west-2:{ACCOUNT_ID}:table/dayec-cost-center-usage",
                        ],
                    },
                ],
            }
        }
    }

    result = check_runtime_cost_policy(_context(), iam, _cfg())

    assert result.status == CheckStatus.PASS
    assert result.details["default_version_id"] == "v7"
    assert result.details["missing_permissions"] == []
    iam.get_policy.assert_called_once_with(PolicyArn=policy_arn)
    iam.get_policy_version.assert_called_once_with(
        PolicyArn=policy_arn,
        VersionId="v7",
    )

    iam.get_policy_version.return_value["PolicyVersion"]["Document"]["Statement"][0]["Action"] = [
        "budgets:ViewBudget"
    ]
    result = check_runtime_cost_policy(_context(), iam, _cfg())
    assert result.status == CheckStatus.FAIL
    assert result.details["missing_permissions"] == [
        {"action": "billing:GetBillingViewData", "resource": "*"}
    ]


def test_runtime_policy_check_does_not_treat_conditional_allow_as_unconditional() -> None:
    document = {
        "Statement": [
            {
                "Effect": "Allow",
                "Action": "dynamodb:GetItem",
                "Resource": "*",
                "Condition": {"StringEquals": {"aws:PrincipalTag/team": "a"}},
            }
        ]
    }

    assert not _policy_allows(
        document,
        action="dynamodb:GetItem",
        resource=f"arn:aws:dynamodb:us-west-2:{ACCOUNT_ID}:table/dayec-cost-centers",
    )


class _BudgetsClient:
    def __init__(self, *, live_limit: str = "200", actual_spend: str = "25") -> None:
        self.live_limit = live_limit
        self.actual_spend = actual_spend

    def describe_budget(self, *, AccountId, BudgetName):
        assert AccountId == ACCOUNT_ID
        return {
            "Budget": {
                "BudgetName": BudgetName,
                "BudgetType": "COST",
                "TimeUnit": "MONTHLY",
                "BudgetLimit": {"Amount": self.live_limit, "Unit": "USD"},
                "CalculatedSpend": {
                    "ActualSpend": {"Amount": self.actual_spend, "Unit": "USD"},
                    "ForecastedSpend": {"Amount": "50", "Unit": "USD"},
                },
                "CostFilters": {"TagKeyValue": ["user:aws-parallelcluster-clustername$cluster-a"]},
                "LastUpdatedTime": datetime(2026, 7, 10, tzinfo=timezone.utc),
            }
        }

    def describe_notifications_for_budget(self, *, BudgetName, **_kwargs):
        thresholds = [25, 50, 75, 99] if BudgetName == "daylily-global" else [75]
        return {
            "Notifications": [
                {
                    "NotificationType": "ACTUAL",
                    "ComparisonOperator": "GREATER_THAN",
                    "Threshold": float(value),
                    "ThresholdType": "PERCENTAGE",
                }
                for value in thresholds
            ]
        }

    def describe_subscribers_for_notification(self, **_kwargs):
        return {"Subscribers": [{"SubscriptionType": "EMAIL", "Address": "alerts@example.org"}]}


def test_budget_readiness_reports_limits_spend_and_notifications() -> None:
    check = CheckResult(
        id="budget.readiness",
        status=CheckStatus.PASS,
        details={"global_exists": True, "cluster_exists": True},
    )

    _enrich_budget_readiness(
        check,
        budgets_client=_BudgetsClient(),
        account_id=ACCOUNT_ID,
        cluster_name="cluster-a",
        global_budget_amount="200",
        cluster_budget_amount="200",
        notification_email="alerts@example.org",
    )

    assert check.status == CheckStatus.PASS
    assert check.details["budget_configuration_gaps"] == []
    cluster = check.details["budget_snapshots"]["cluster-a"]
    assert cluster["actual_spend_amount"] == "25"
    assert cluster["actual_spend_below_limit"] is True
    assert cluster["limit_matches_config"] is True
    assert cluster["configured_email_subscribed"] is True


def test_budget_readiness_warns_on_live_limit_or_spend_mismatch() -> None:
    check = CheckResult(
        id="budget.readiness",
        status=CheckStatus.PASS,
        details={"global_exists": True, "cluster_exists": True},
    )

    _enrich_budget_readiness(
        check,
        budgets_client=_BudgetsClient(live_limit="100", actual_spend="100"),
        account_id=ACCOUNT_ID,
        cluster_name="cluster-a",
        global_budget_amount="200",
        cluster_budget_amount="200",
        notification_email="alerts@example.org",
    )

    assert check.status == CheckStatus.FAIL
    reasons = {item["reason"] for item in check.details["budget_configuration_gaps"]}
    assert "actual spend is at or above the budget limit" in reasons
    assert "live limit differs from configured limit" in reasons


def test_cost_center_registry_checks_schema_idle_and_fresh_usage(monkeypatch) -> None:
    dynamodb = MagicMock()

    def describe_table(*, TableName):
        schemas = {
            "dayec-cost-centers": [{"AttributeName": "cost_center", "KeyType": "HASH"}],
            "dayec-cost-center-usage": [
                {"AttributeName": "cost_center", "KeyType": "HASH"},
                {"AttributeName": "month", "KeyType": "RANGE"},
            ],
        }
        return {
            "Table": {
                "TableStatus": "ACTIVE",
                "KeySchema": schemas[TableName],
                "ItemCount": 2,
            }
        }

    dynamodb.describe_table.side_effect = describe_table
    monkeypatch.setattr(validation_module, "_regional_client", lambda *_args: dynamodb)
    monkeypatch.setattr(
        validation_module,
        "list_cost_centers",
        lambda *_args, **_kwargs: [
            SimpleNamespace(name="idle", status="system", monthly_cap_usd=Decimal("0")),
            SimpleNamespace(
                name="team-a",
                status="active",
                monthly_cap_usd=Decimal("100"),
            ),
        ],
    )
    monkeypatch.setattr(
        validation_module,
        "list_cost_center_usage",
        lambda *_args, **_kwargs: [
            SimpleNamespace(
                name="team-a",
                monthly_spend_usd=Decimal("25"),
                latest_processed_hour=datetime.now(timezone.utc)
                .replace(microsecond=0)
                .isoformat()
                .replace("+00:00", "Z"),
            )
        ],
    )

    result = _check_cost_center_registry_readiness(_context())

    assert result.status == CheckStatus.PASS
    assert result.details["reserved_idle_present"] is True
    assert result.details["missing_usage"] == []
    assert result.details["stale_usage"] == []
    assert dynamodb.method_calls == [
        (("describe_table"), (), {"TableName": "dayec-cost-centers"}),
        (("describe_table"), (), {"TableName": "dayec-cost-center-usage"}),
    ]

    monkeypatch.setattr(
        validation_module,
        "list_cost_center_usage",
        lambda *_args, **_kwargs: [
            SimpleNamespace(
                name="team-a",
                monthly_spend_usd=Decimal("100"),
                latest_processed_hour=datetime.now(timezone.utc)
                .replace(microsecond=0)
                .isoformat()
                .replace("+00:00", "Z"),
            )
        ],
    )
    result = _check_cost_center_registry_readiness(_context())
    assert result.status == CheckStatus.FAIL
    assert result.details["exhausted_usage"][0]["cost_center"] == "team-a"


def test_cur_readiness_uses_only_read_apis(monkeypatch) -> None:
    context = _context()
    config = validation_module._default_cur_config(context)
    s3 = MagicMock()
    s3.get_bucket_location.return_value = {"LocationConstraint": None}
    s3.get_bucket_policy.return_value = {
        "Policy": validation_module.json.dumps(
            {
                "Version": "2012-10-17",
                "Statement": [data_exports_bucket_policy_statement(config)],
            }
        )
    }
    bcm = MagicMock()
    bcm.list_exports.return_value = {
        "Exports": [
            {
                "ExportName": config.export_name,
                "ExportArn": "arn:aws:bcm-data-exports:us-east-1:123456789012:export/x",
                "ExportStatus": {"StatusCode": "HEALTHY"},
            }
        ]
    }
    bcm.get_export.return_value = {"Export": build_cur2_export_definition(config)}
    bcm.list_executions.return_value = {
        "Executions": [
            {
                "ExecutionStatus": {
                    "StatusCode": "DELIVERY_SUCCESS",
                    "CreatedAt": datetime(2026, 7, 10, tzinfo=timezone.utc),
                }
            }
        ]
    }
    bcm.get_table.return_value = {
        "Schema": [{"Name": name, "Type": "STRING"} for name in CUR_EXPORT_COLUMNS]
    }
    monkeypatch.setattr(
        validation_module,
        "_regional_client",
        lambda _ctx, service, _region: {"s3": s3, "bcm-data-exports": bcm}[service],
    )

    result = _check_cur_export_readiness(context)

    assert result.status == CheckStatus.PASS
    assert result.details["latest_execution"]["ExecutionStatus"]["StatusCode"] == "DELIVERY_SUCCESS"
    assert not s3.create_bucket.called
    assert not s3.put_bucket_policy.called
    assert not bcm.create_export.called
    assert not bcm.update_export.called

    drifted = build_cur2_export_definition(config)
    drifted["RefreshCadence"] = {"Frequency": "MANUAL"}
    bcm.get_export.return_value = {"Export": drifted}
    result = _check_cur_export_readiness(context)
    assert result.status == CheckStatus.FAIL
    assert "export_definition" in result.details["invalid"]


def test_cur_catalog_readiness_does_not_create_or_update(monkeypatch) -> None:
    context = _context()
    config = validation_module._default_cur_config(context)
    schema = [{"Name": name, "Type": "STRING"} for name in CUR_EXPORT_COLUMNS]
    expected_table = glue_table_input(config, schema=schema)
    glue = MagicMock()
    glue.get_database.return_value = {"Database": {"Name": "dayec_cur"}}
    glue.get_table.return_value = {"Table": expected_table}
    billing_period = datetime.now(timezone.utc).strftime("%Y-%m")
    partition_storage = deepcopy(expected_table["StorageDescriptor"])
    partition_storage["Location"] = billing_period_data_location(config, billing_period)
    glue.get_partition.return_value = {
        "Partition": {
            "Values": [billing_period],
            "Parameters": {"dayec:managed": "true"},
            "StorageDescriptor": partition_storage,
        }
    }
    bcm = MagicMock()
    bcm.get_table.return_value = {"Schema": schema}
    monkeypatch.setattr(
        validation_module,
        "_regional_client",
        lambda _ctx, service, _region: {
            "glue": glue,
            "bcm-data-exports": bcm,
        }[service],
    )

    result = _check_cur_catalog_readiness(context)

    assert result.status == CheckStatus.PASS
    assert not glue.create_database.called
    assert not glue.create_table.called
    assert not glue.update_table.called
    assert not glue.create_partition.called

    glue.get_partition.return_value["Partition"]["StorageDescriptor"]["Location"] = (
        "s3://wrong/location/"
    )
    result = _check_cur_catalog_readiness(context)
    assert result.status == CheckStatus.FAIL
    assert "partition_contract" in result.details["invalid"]


def test_new_count_quotas_report_current_use_demand_and_headroom(monkeypatch) -> None:
    budgets = MagicMock()
    monkeypatch.setattr(
        validation_module,
        "_list_budgets",
        lambda *_args: [{"BudgetName": "daylily-global"}],
    )
    budget_result = _check_budget_count_quota(
        _context(budgets=budgets),
        _cfg(),
    )
    assert budget_result.status == CheckStatus.PASS
    assert budget_result.details["current_used"] == 1
    assert budget_result.details["required_new"] == 1

    dynamodb = MagicMock()
    service_quotas = MagicMock()
    monkeypatch.setattr(
        validation_module,
        "_regional_client",
        lambda _c, service, _r: {
            "dynamodb": dynamodb,
            "service-quotas": service_quotas,
        }[service],
    )
    monkeypatch.setattr(validation_module, "_list_dynamodb_tables", lambda _client: ["other"])
    monkeypatch.setattr(validation_module, "_fetch_quota_value", lambda *_args: 2)
    table_result = _check_dynamodb_table_count_quota(_context())
    assert table_result.status == CheckStatus.FAIL
    assert table_result.details["current_used"] == 1
    assert table_result.details["required_new"] == 2
    assert table_result.details["projected_used"] == 3


def test_cur_export_count_quota_counts_only_cur2_exports(monkeypatch) -> None:
    bcm = MagicMock()
    monkeypatch.setattr(validation_module, "_regional_client", lambda *_args: bcm)
    monkeypatch.setattr(
        validation_module,
        "_list_data_exports",
        lambda _client: [
            {"ExportArn": f"arn:{index}", "ExportName": f"cur-{index}"} for index in range(5)
        ],
    )
    bcm.get_export.side_effect = [
        {
            "Export": {
                "Name": f"cur-{index}",
                "DataQuery": {"QueryStatement": f"SELECT * FROM {DATA_EXPORTS_TABLE}"},
            }
        }
        for index in range(5)
    ]

    result = _check_cur_export_count_quota(_context())

    assert result.status == CheckStatus.FAIL
    assert result.details["current_used"] == 5
    assert result.details["required_new"] == 1
    assert result.details["projected_used"] == 6


def test_athena_active_dml_quota_uses_current_running_queries(monkeypatch) -> None:
    athena = MagicMock()
    service_quotas = MagicMock()
    athena.list_work_groups.return_value = {
        "WorkGroups": [{"Name": "primary"}, {"Name": "secondary"}]
    }
    athena.list_query_executions.side_effect = lambda WorkGroup, **_kwargs: {
        "QueryExecutionIds": (["q-running", "q-done"] if WorkGroup == "primary" else ["q-ddl"])
    }
    athena.batch_get_query_execution.return_value = {
        "QueryExecutions": [
            {
                "QueryExecutionId": "q-running",
                "StatementType": "DML",
                "Status": {"State": "RUNNING"},
            },
            {
                "QueryExecutionId": "q-done",
                "StatementType": "DML",
                "Status": {"State": "SUCCEEDED"},
            },
            {
                "QueryExecutionId": "q-ddl",
                "StatementType": "DDL",
                "Status": {"State": "RUNNING"},
            },
        ]
    }
    monkeypatch.setattr(
        validation_module,
        "_regional_client",
        lambda _ctx, service, _region: {
            "athena": athena,
            "service-quotas": service_quotas,
        }[service],
    )
    monkeypatch.setattr(validation_module, "_fetch_quota_value", lambda *_args: 2)

    result = _check_athena_active_dml_quota(_context())

    assert result.status == CheckStatus.PASS
    assert result.details["current_used"] == 1
    assert result.details["projected_used"] == 2

    monkeypatch.setattr(validation_module, "_fetch_quota_value", lambda *_args: 1)
    result = _check_athena_active_dml_quota(_context())
    assert result.status == CheckStatus.FAIL


def test_disabled_slurm_accounting_has_zero_incremental_resource_demand() -> None:
    results = _check_slurm_accounting_resource_quotas(_context(), _cfg())

    assert len(results) == 5
    assert {result.status for result in results} == {CheckStatus.PASS}
    assert all(result.details["required_new"] == 0 for result in results)


def test_enabled_slurm_accounting_uses_iam_account_summary_quotas(monkeypatch) -> None:
    cfg = _cfg()
    cfg.ephemeral_cluster.config["slurm_accounting_enabled"] = Triplet(
        action="USESETVALUE",
        default_value="",
        set_value="true",
    )
    iam = MagicMock()
    iam.get_account_summary.return_value = {
        "SummaryMap": {
            "Roles": 10,
            "RolesQuota": 1000,
            "InstanceProfiles": 7,
            "InstanceProfilesQuota": 1000,
        }
    }
    ctx = _context(
        cloudformation=MagicMock(),
        ec2=MagicMock(),
        secretsmanager=MagicMock(),
        iam=iam,
    )
    monkeypatch.setattr(validation_module, "describe_stack_status", lambda *_args: None)
    monkeypatch.setattr(validation_module, "_regional_client", lambda *_args: MagicMock())
    monkeypatch.setattr(validation_module, "_fetch_quota_value", lambda *_args: 1000)
    monkeypatch.setattr(
        validation_module,
        "_count_paginated_items",
        lambda _client, *, operation, **_kwargs: {
            "describe_security_groups": 10,
            "describe_network_interfaces": 20,
            "list_secrets": 30,
        }[operation],
    )

    results = _check_slurm_accounting_resource_quotas(ctx, cfg)
    by_id = {result.id: result for result in results}

    assert by_id["quota.slurm_accounting.iam_roles"].status == CheckStatus.PASS
    assert by_id["quota.slurm_accounting.iam_roles"].details["current_used"] == 10
    assert by_id["quota.slurm_accounting.iam_roles"].details["current_value"] == 1000
    assert by_id["quota.slurm_accounting.iam_instance_profiles"].details["current_used"] == 7
    iam.get_account_summary.assert_called_once_with()


def test_network_quota_headroom_uses_current_usage_plus_baseline_demand(monkeypatch) -> None:
    checks = [
        CheckResult(
            id=check_id,
            status=CheckStatus.PASS,
            details={"current_value": 10, "quota_code": f"quota-{index}"},
        )
        for index, check_id in enumerate(
            (
                "quota.vpcs",
                "quota.elastic_ips",
                "quota.nat_gateways",
                "quota.internet_gateways",
            )
        )
    ]
    monkeypatch.setattr(
        validation_module,
        "_count_paginated_items",
        lambda _client, *, operation, **_kwargs: {
            "describe_vpcs": 6,
            "describe_internet_gateways": 6,
        }[operation],
    )
    monkeypatch.setattr(
        validation_module,
        "_count_customer_managed_amazon_eips",
        lambda _client: 10,
    )
    monkeypatch.setattr(
        validation_module,
        "_count_nat_gateways_in_az",
        lambda *_args, **_kwargs: 2,
    )

    _enrich_network_quota_headroom(
        checks,
        _context(ec2=MagicMock()),
        baseline_ready=False,
    )

    by_id = {check.id: check for check in checks}
    assert by_id["quota.vpcs"].details["projected_used"] == 7
    assert by_id["quota.elastic_ips"].status == CheckStatus.FAIL
    assert by_id["quota.elastic_ips"].details["projected_used"] == 11


def test_markdown_report_serializes_aws_datetimes_and_outcome(tmp_path) -> None:
    report = AwsValidationReport(
        mode="all",
        region="us-west-2",
        region_az="us-west-2b",
        aws_profile="dev",
        account_id=ACCOUNT_ID,
        caller_arn=f"arn:aws:iam::{ACCOUNT_ID}:user/alice",
        checks=[
            CheckResult(
                id="quota.budget_count",
                status=CheckStatus.PASS,
                details={"observed_at": datetime(2026, 7, 10, tzinfo=timezone.utc)},
            ),
            CheckResult(
                id="budget.readiness",
                status=CheckStatus.WARN,
                details={"cluster_exists": False},
                remediation="Create the configured cluster budget.",
            ),
        ],
        summary={"PASS": 1, "WARN": 1, "FAIL": 0},
    )
    path = tmp_path / "report.md"

    write_gap_analysis(report, path)

    text = path.read_text(encoding="utf-8")
    assert "Overall: **NOT SATISFIED**" in text
    assert "| Quotas and headroom | `quota.budget_count` | SATISFIED | PASS |" in text
    assert "| Budget readiness | `budget.readiness` | UNKNOWN | WARN |" in text
    assert "## Area Summary" in text
    assert "| Budget readiness | 0 | 1 | 0 | 1 | UNKNOWN |" in text
    assert '"observed_at": "2026-07-10T00:00:00Z"' in text
