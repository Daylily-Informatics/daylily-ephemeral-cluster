"""Additional behavioral coverage for the read-only AWS validator."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import quote

import pytest

import daylily_ec.aws.validation as validation
from daylily_ec.aws.validation import (
    AwsValidationError,
    AwsValidationOptions,
    AwsValidationReport,
    _aws_partition,
    _check_athena_readiness,
    _check_cloudformation_stack_quota,
    _check_fixed_service_quota,
    _check_slurm_accounting_resource_quotas,
    _check_slurm_accounting_shape,
    _count_paginated_items,
    _decode_policy_document,
    _describe_budget_notifications,
    _error_code,
    _find_data_export_by_name,
    _fsx_lustre_matches_deployment,
    _glue_storage_descriptor_matches,
    _glue_table_contract_matches,
    _is_not_found_error,
    _json_safe,
    _list_athena_query_execution_ids,
    _list_athena_workgroups,
    _list_budgets,
    _list_cloudformation_stacks,
    _list_data_export_executions,
    _list_dynamodb_tables,
    _policy_allows,
    _policy_statement_contains,
    _regional_client,
    _strict_bool_config,
    check_cost_control_readiness,
    check_dragen_license_configuration,
    check_runtime_cost_policy,
    check_slurm_accounting_readiness,
    extract_cluster_shape,
    run_aws_validation,
    run_permission_checks,
)
from daylily_ec.config.models import ConfigFile, Triplet
from daylily_ec.state.models import CheckResult, CheckStatus


class _Paginator:
    def __init__(self, pages: list[dict]) -> None:
        self.pages = pages

    def paginate(self, **_kwargs):
        return self.pages


class _Context:
    def __init__(self, **clients: object) -> None:
        self.region = "us-west-2"
        self.region_az = "us-west-2d"
        self.profile = "coverage"
        self.account_id = "123456789012"
        self.caller_arn = "arn:aws:iam::123456789012:user/coverage"
        self.iam_username = "coverage"
        self.session = SimpleNamespace(
            client=lambda service, region_name: ("regional", service, region_name)
        )
        self._clients = clients

    def client(self, service: str):
        return self._clients[service]


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        (
            {"mode": "unknown", "profile": "coverage", "region_az": "us-west-2d"},
            "Unsupported AWS validation mode",
        ),
        (
            {"mode": "all", "profile": "", "region_az": "us-west-2d"},
            "--profile is required",
        ),
        (
            {"mode": "all", "profile": "coverage", "region_az": ""},
            "--region-az is required",
        ),
        (
            {"mode": "all", "profile": "coverage", "region_az": "us-west-2"},
            "expected a letter",
        ),
    ],
)
def test_validation_options_reject_invalid_public_contracts(
    kwargs: dict[str, str], message: str
) -> None:
    with pytest.raises(AwsValidationError, match=message):
        AwsValidationOptions(**kwargs)


def test_validation_options_normalize_and_report_serializes_deterministically() -> None:
    options = AwsValidationOptions(
        mode=" permissions ",
        profile=" coverage ",
        region_az=" us-west-2d ",
    )
    assert (options.mode, options.profile, options.region_az) == (
        "permissions",
        "coverage",
        "us-west-2d",
    )

    report = AwsValidationReport(
        run_id="20260716032804",
        checks=[CheckResult(id="aws.identity", status=CheckStatus.PASS)],
        summary={"PASS": 1, "WARN": 0, "FAIL": 0},
    )
    payload = report.to_sorted_json(indent=0)
    assert json.loads(payload)["summary"] == {"PASS": 1, "WARN": 0, "FAIL": 0}
    assert payload.index('"checks"') < payload.index('"summary"')


@pytest.mark.parametrize(
    ("mode", "permission_status", "expected_calls", "expected_exit"),
    [
        ("permissions", CheckStatus.PASS, ["permissions"], 0),
        ("quotas", CheckStatus.PASS, ["quotas"], 0),
        ("all", CheckStatus.WARN, ["permissions", "quotas"], 1),
    ],
)
def test_run_aws_validation_routes_modes_finalizes_and_writes_gap_report(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
    permission_status: CheckStatus,
    expected_calls: list[str],
    expected_exit: int,
) -> None:
    cfg = ConfigFile()
    cfg.ephemeral_cluster.config["cluster_name"] = Triplet(
        action="USESETVALUE", set_value="coverage-cluster"
    )
    config_path = tmp_path / "daylily.yaml"
    config_path.write_text("unused: true\n", encoding="utf-8")
    gap_path = tmp_path / "gap.md"
    calls: list[str] = []
    ctx = _Context()

    monkeypatch.setattr(validation, "_resolve_config_path", lambda _path: config_path)
    monkeypatch.setattr(validation, "load_config", lambda _path: cfg)
    monkeypatch.setattr(
        validation,
        "run_permission_checks",
        lambda _ctx, cfg: calls.append("permissions")
        or [CheckResult(id="iam.test", status=permission_status)],
    )
    monkeypatch.setattr(
        validation,
        "run_quota_checks",
        lambda _ctx, _cfg, config_path: calls.append("quotas")
        or [CheckResult(id="quota.test", status=CheckStatus.PASS)],
    )
    monkeypatch.setattr(
        validation,
        "write_gap_analysis",
        lambda report, path: calls.append(f"gap:{path.name}:{report.mode}"),
    )

    exit_code, report = run_aws_validation(
        AwsValidationOptions(
            mode=mode,
            profile="coverage",
            region_az="us-west-2d",
            config_path=str(config_path),
            gap_analysis_path=gap_path,
        ),
        context_builder=lambda region_az, profile: ctx,
    )

    assert exit_code == expected_exit
    assert calls[:-1] == expected_calls
    assert calls[-1] == f"gap:gap.md:{mode}"
    assert report.cluster_name == "coverage-cluster"
    assert report.summary["PASS"] >= 1
    assert report.summary["WARN"] == (1 if permission_status is CheckStatus.WARN else 0)
    assert report.checks[0].id == "aws.identity"


def test_permission_check_orchestrator_includes_config_dependent_readiness(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def check(check_id: str) -> CheckResult:
        return CheckResult(id=check_id, status=CheckStatus.PASS)

    monkeypatch.setattr(
        validation, "check_daylily_policies", lambda *_args, **_kwargs: [check("daylily")]
    )
    monkeypatch.setattr(
        validation, "check_pcluster_omics_policy_exists", lambda _iam: check("omics")
    )
    monkeypatch.setattr(validation, "check_ssm_session_document", lambda _ssm: check("ssm"))
    monkeypatch.setattr(
        validation, "simulate_required_permissions", lambda *_args, **_kwargs: [check("simulation")]
    )
    monkeypatch.setattr(validation, "check_runtime_cost_policy", lambda *_args: check("runtime"))
    monkeypatch.setattr(
        validation, "check_dragen_license_configuration", lambda *_args: check("dragen")
    )
    monkeypatch.setattr(validation, "check_cost_control_readiness", lambda *_args: [check("cost")])
    monkeypatch.setattr(
        validation, "check_slurm_accounting_readiness", lambda *_args: check("accounting")
    )

    checks = run_permission_checks(_Context(iam=object(), ssm=object()), cfg=ConfigFile())
    assert [item.id for item in checks] == [
        "daylily",
        "omics",
        "ssm",
        "simulation",
        "runtime",
        "dragen",
        "cost",
        "accounting",
    ]


def test_runtime_cost_policy_rejects_missing_policy_and_unreadable_default_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(validation, "_effective_config_value", lambda *_args: "")
    missing = check_runtime_cost_policy(_Context(), object(), ConfigFile())
    assert missing.status is CheckStatus.FAIL
    assert missing.details["policy_arn"] == ""

    monkeypatch.setattr(
        validation,
        "_effective_config_value",
        lambda *_args: "arn:aws:iam::123456789012:policy/runtime",
    )
    iam = SimpleNamespace(get_policy=lambda **_kwargs: {"Policy": {}})
    unreadable = check_runtime_cost_policy(_Context(), iam, ConfigFile())
    assert unreadable.status is CheckStatus.FAIL
    assert "no default version" in unreadable.details["error"]


def test_dragen_license_configuration_handles_absent_partial_and_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    values = {"dragen_license_secret_arn": "", "dragen_license_policy_arn": ""}
    monkeypatch.setattr(
        validation,
        "_effective_config_value",
        lambda _cfg, key, _fallback: values[key],
    )
    assert (
        check_dragen_license_configuration(_Context(), object(), ConfigFile()).status
        is CheckStatus.PASS
    )

    values["dragen_license_secret_arn"] = "arn:secret"
    assert (
        check_dragen_license_configuration(_Context(), object(), ConfigFile()).status
        is CheckStatus.FAIL
    )

    values["dragen_license_policy_arn"] = "arn:policy"

    def fake_step(**_kwargs):
        def apply(report):
            report.checks.append(CheckResult(id="iam.dragen", status=CheckStatus.PASS))

        return apply

    monkeypatch.setattr(validation, "make_dragen_license_preflight_step", fake_step)
    result = check_dragen_license_configuration(
        _Context(secretsmanager=object()), object(), ConfigFile()
    )
    assert result.id == "iam.dragen"


def test_cost_control_readiness_assembles_budget_and_read_only_dependency_checks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    budget = CheckResult(id="budget", status=CheckStatus.PASS, details={})
    monkeypatch.setattr(validation, "make_budget_preflight_step", lambda *_args, **_kwargs: budget)
    monkeypatch.setattr(
        validation,
        "_enrich_budget_readiness",
        lambda check, **_kwargs: check.details.update({"enriched": True}),
    )
    monkeypatch.setattr(
        validation,
        "_check_cost_center_registry_readiness",
        lambda _ctx: CheckResult(id="registry", status=CheckStatus.PASS),
    )
    monkeypatch.setattr(
        validation,
        "_check_cur_export_readiness",
        lambda _ctx: CheckResult(id="export", status=CheckStatus.PASS),
    )
    monkeypatch.setattr(
        validation,
        "_check_cur_catalog_readiness",
        lambda _ctx: CheckResult(id="catalog", status=CheckStatus.PASS),
    )
    monkeypatch.setattr(
        validation,
        "_check_athena_readiness",
        lambda _ctx: CheckResult(id="athena", status=CheckStatus.PASS),
    )

    checks = check_cost_control_readiness(_Context(budgets=object()), ConfigFile())
    assert [check.id for check in checks] == [
        "budget",
        "registry",
        "export",
        "catalog",
        "athena",
    ]
    assert budget.details["actor"] == "operator"
    assert budget.details["enriched"] is True


def test_policy_document_decoding_and_authorization_semantics() -> None:
    allow = {
        "Effect": "Allow",
        "Action": "dynamodb:Get*",
        "Resource": "arn:aws:dynamodb:*:123456789012:table/dayec-*",
    }
    document = {"Statement": ["ignored", allow]}
    encoded = quote(json.dumps(document))

    assert _decode_policy_document(document) is document
    assert _decode_policy_document(encoded) == document
    assert _policy_allows(
        document,
        action="dynamodb:GetItem",
        resource="arn:aws:dynamodb:us-west-2:123456789012:table/dayec-cost-centers",
    )
    assert not _policy_allows(
        {"Statement": {**allow, "Condition": {"StringEquals": {"aws:x": "y"}}}},
        action="dynamodb:GetItem",
        resource="arn:aws:dynamodb:us-west-2:123456789012:table/dayec-cost-centers",
    )
    assert not _policy_allows(
        {"Statement": [allow, {**allow, "Effect": "Deny"}]},
        action="dynamodb:GetItem",
        resource="arn:aws:dynamodb:us-west-2:123456789012:table/dayec-cost-centers",
    )

    with pytest.raises(ValueError, match="no policy document"):
        _decode_policy_document("")
    with pytest.raises(ValueError, match="not a JSON object"):
        _decode_policy_document("%5B%5D")


def test_policy_statement_subset_partition_and_error_helpers() -> None:
    expected = {
        "Effect": "Allow",
        "Principal": {"Service": "scheduler.amazonaws.com"},
        "Action": "sts:AssumeRole",
        "Resource": "*",
        "Condition": None,
    }
    actual = {
        "Effect": "Allow",
        "Principal": {"Service": ["scheduler.amazonaws.com", "events.amazonaws.com"]},
        "Action": ["sts:AssumeRole", "sts:TagSession"],
        "Resource": ["*"],
        "Condition": None,
    }
    assert _policy_statement_contains(actual, expected)
    assert not _policy_statement_contains({**actual, "Effect": "Deny"}, expected)
    assert _aws_partition("arn:aws-us-gov:iam::123456789012:user/a") == "aws-us-gov"
    with pytest.raises(AwsValidationError, match="Cannot derive AWS partition"):
        _aws_partition("not-an-arn")

    coded = RuntimeError("denied")
    coded.response = {"Error": {"Code": "ResourceNotFoundException"}}  # type: ignore[attr-defined]
    assert _error_code(coded) == "ResourceNotFoundException"
    assert _is_not_found_error(coded)
    assert _is_not_found_error(RuntimeError("object does not exist"))
    assert not _is_not_found_error(RuntimeError("access denied"))


def test_regional_client_strict_boole_and_json_safe(monkeypatch: pytest.MonkeyPatch) -> None:
    ctx = _Context(dynamodb="local-client")
    assert _regional_client(ctx, "dynamodb", "us-west-2") == "local-client"
    assert _regional_client(ctx, "dynamodb", "us-east-1") == (
        "regional",
        "dynamodb",
        "us-east-1",
    )

    values = iter(["YES", "0", "sometimes"])
    monkeypatch.setattr(validation, "_effective_config_value", lambda *_args: next(values))
    assert _strict_bool_config(object(), "enabled", False) is True
    assert _strict_bool_config(object(), "enabled", True) is False
    with pytest.raises(AwsValidationError, match="must be true or false"):
        _strict_bool_config(object(), "enabled", False)

    converted = _json_safe(
        {
            1: (
                datetime(2026, 7, 16, 3, 28, 4, tzinfo=timezone.utc),
                Decimal("12.30"),
            )
        }
    )
    assert converted == {"1": ["2026-07-16T03:28:04Z", "12.30"]}


def test_read_only_list_helpers_follow_service_pagination_contracts() -> None:
    class Client:
        def __init__(self) -> None:
            self.budget_requests: list[dict] = []
            self.export_requests: list[dict] = []
            self.execution_requests: list[dict] = []
            self.stack_requests: list[dict] = []

        def describe_budgets(self, **request):
            self.budget_requests.append(request)
            return (
                {"Budgets": [{"BudgetName": "a"}], "NextToken": "next"}
                if len(self.budget_requests) == 1
                else {"Budgets": [{"BudgetName": "b"}]}
            )

        def list_exports(self, **request):
            self.export_requests.append(request)
            return (
                {"Exports": [{"ExportName": "other"}], "NextToken": "next"}
                if len(self.export_requests) == 1
                else {"Exports": [{"ExportName": "target", "ExportArn": "arn:target"}]}
            )

        def list_executions(self, **request):
            self.execution_requests.append(request)
            return (
                {"Executions": [{"Status": "RUNNING"}], "NextToken": "next"}
                if len(self.execution_requests) == 1
                else {"Executions": [{"Status": "SUCCEEDED"}]}
            )

        def describe_stacks(self, **request):
            self.stack_requests.append(request)
            return (
                {"Stacks": [{"StackName": "a"}], "NextToken": "next"}
                if len(self.stack_requests) == 1
                else {"Stacks": [{"StackName": "b"}]}
            )

        def get_paginator(self, _operation):
            raise RuntimeError("pagination unsupported")

    client = Client()
    assert [item["BudgetName"] for item in _list_budgets(client, "123")] == ["a", "b"]
    assert client.budget_requests[1]["NextToken"] == "next"
    assert _find_data_export_by_name(client, "target")["ExportArn"] == "arn:target"
    assert _find_data_export_by_name(Client(), "absent") is None
    assert len(_list_data_export_executions(client, "arn:target")) == 2
    assert client.execution_requests[1]["NextToken"] == "next"
    assert [item["StackName"] for item in _list_cloudformation_stacks(client)] == ["a", "b"]
    assert client.stack_requests[1]["NextToken"] == "next"


def test_dynamodb_and_cloudformation_helpers_use_paginators_when_available() -> None:
    class Client:
        def get_paginator(self, operation: str):
            pages = {
                "list_tables": [{"TableNames": ["a"]}, {"TableNames": ["b"]}],
                "describe_stacks": [{"Stacks": [{"StackName": "a"}]}],
            }
            return _Paginator(pages[operation])

    client = Client()
    assert _list_dynamodb_tables(client) == ["a", "b"]
    assert _list_cloudformation_stacks(client) == [{"StackName": "a"}]


def test_count_paginated_items_uses_paginator_and_direct_fallback() -> None:
    paginated = SimpleNamespace(
        get_paginator=lambda _operation: _Paginator([{"Items": [{}, {}]}, {"Items": [{}]}])
    )
    assert (
        _count_paginated_items(
            paginated,
            operation="list_items",
            result_key="Items",
            request={"Scope": "all"},
        )
        == 3
    )

    class Direct:
        def get_paginator(self, _operation):
            raise RuntimeError("unsupported")

        def list_items(self, **request):
            assert request == {"Scope": "all"}
            return {"Items": [{}, {}]}

    assert (
        _count_paginated_items(
            Direct(),
            operation="list_items",
            result_key="Items",
            request={"Scope": "all"},
        )
        == 2
    )


@pytest.mark.parametrize(
    ("quota", "expected"),
    [(None, CheckStatus.WARN), (4.0, CheckStatus.FAIL), (10.0, CheckStatus.PASS)],
)
def test_fixed_service_quota_reports_unreadable_insufficient_and_sufficient(
    monkeypatch: pytest.MonkeyPatch,
    quota: float | None,
    expected: CheckStatus,
) -> None:
    monkeypatch.setattr(validation, "_fetch_quota_value", lambda *_args: quota)
    result = _check_fixed_service_quota(
        _Context(**{"service-quotas": object()}),
        check_id="quota.test",
        service_code="test",
        quota_code="L-TEST",
        required_value=5,
        required_unit="items",
        region="us-west-2",
    )
    assert result.status is expected
    assert result.details["current_value"] == quota


def test_cloudformation_stack_quota_disabled_inventory_error_and_existing_stack(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_accounting_flags(monkeypatch, enabled=False)
    disabled = _check_cloudformation_stack_quota(_Context(), ConfigFile())
    assert disabled.status is CheckStatus.PASS
    assert disabled.details["required_new"] == 0

    _patch_accounting_flags(monkeypatch, enabled=True)
    monkeypatch.setattr(
        validation,
        "_list_cloudformation_stacks",
        lambda _client: (_ for _ in ()).throw(RuntimeError("denied")),
    )
    failed = _check_cloudformation_stack_quota(_Context(cloudformation=object()), ConfigFile())
    assert failed.status is CheckStatus.WARN

    monkeypatch.setattr(
        validation,
        "_list_cloudformation_stacks",
        lambda _client: [
            {"StackName": "active", "StackStatus": "CREATE_COMPLETE"},
            {"StackName": "deleted", "StackStatus": "DELETE_COMPLETE"},
        ],
    )
    monkeypatch.setattr(
        validation,
        "list_regional_slurm_accounting_stacks",
        lambda *_args, **_kwargs: [{"StackName": "accounting", "StackStatus": "CREATE_COMPLETE"}],
    )
    monkeypatch.setattr(
        validation,
        "_check_fixed_service_quota",
        lambda *_args, **_kwargs: CheckResult(
            id="quota.cloudformation_stack_count",
            status=CheckStatus.PASS,
            details={},
        ),
    )
    existing = _check_cloudformation_stack_quota(_Context(cloudformation=object()), ConfigFile())
    assert existing.status is CheckStatus.PASS
    assert existing.details["current_used"] == 1
    assert existing.details["required_new"] == 0


def test_accounting_resource_quotas_disabled_and_enabled_inventory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_accounting_flags(monkeypatch, enabled=False)
    disabled = _check_slurm_accounting_resource_quotas(_Context(), ConfigFile())
    assert len(disabled) == 5
    assert {check.status for check in disabled} == {CheckStatus.PASS}
    assert {check.details["required_new"] for check in disabled} == {0}

    _patch_accounting_flags(monkeypatch, enabled=True)
    monkeypatch.setattr(
        validation,
        "list_regional_slurm_accounting_stacks",
        lambda *_args, **_kwargs: [],
    )
    monkeypatch.setattr(validation, "_fetch_quota_value", lambda *_args: 100.0)

    class CountClient:
        def get_paginator(self, _operation):
            return _Paginator([{}])

    iam = CountClient()
    iam.get_account_summary = lambda: {
        "SummaryMap": {
            "RolesQuota": 100,
            "Roles": 10,
            "InstanceProfilesQuota": 100,
            "InstanceProfiles": 10,
        }
    }
    clients = {
        "iam": iam,
        "ec2": CountClient(),
        "secretsmanager": CountClient(),
        "service-quotas": object(),
    }
    enabled = _check_slurm_accounting_resource_quotas(_Context(**clients), ConfigFile())
    assert len(enabled) == 5
    assert {check.status for check in enabled} == {CheckStatus.PASS}
    assert sorted(check.details["required_new"] for check in enabled) == [1, 1, 1, 1, 2]


def test_accounting_resource_quota_inventory_failure_is_bounded_warning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_accounting_flags(monkeypatch, enabled=True)
    monkeypatch.setattr(
        validation,
        "list_regional_slurm_accounting_stacks",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("inventory denied")),
    )
    monkeypatch.setattr(validation, "_fetch_quota_value", lambda *_args: None)
    failed = SimpleNamespace(
        get_account_summary=lambda: (_ for _ in ()).throw(RuntimeError("summary denied")),
        get_paginator=lambda _operation: _Paginator([{}]),
    )
    results = _check_slurm_accounting_resource_quotas(
        _Context(
            iam=failed,
            ec2=failed,
            secretsmanager=failed,
            **{"service-quotas": object()},
        ),
        ConfigFile(),
    )
    assert len(results) == 5
    assert {check.status for check in results} == {CheckStatus.WARN}
    assert all("inventory denied" in check.details["error"] for check in results)


def test_dynamodb_list_fallback_and_budget_notification_pagination() -> None:
    class Dynamo:
        def __init__(self) -> None:
            self.calls = 0

        def get_paginator(self, _operation):
            raise RuntimeError("no paginator")

        def list_tables(self, **request):
            self.calls += 1
            if self.calls == 1:
                assert request == {}
                return {"TableNames": ["a"], "LastEvaluatedTableName": "a"}
            assert request == {"ExclusiveStartTableName": "a"}
            return {"TableNames": ["b"]}

    class Budgets:
        def __init__(self) -> None:
            self.calls = 0

        def describe_notifications_for_budget(self, **request):
            self.calls += 1
            notification = {
                "NotificationType": "ACTUAL",
                "ComparisonOperator": "GREATER_THAN",
                "Threshold": self.calls * 50,
                "ThresholdType": "PERCENTAGE",
            }
            return (
                {"Notifications": [notification], "NextToken": "next"}
                if self.calls == 1
                else {"Notifications": [notification]}
            )

        def describe_subscribers_for_notification(self, **_request):
            return {"Subscribers": [{"Address": "b@example.org"}, {"Address": "a@example.org"}]}

    assert _list_dynamodb_tables(Dynamo()) == ["a", "b"]
    notifications = _describe_budget_notifications(
        Budgets(), account_id="123", budget_name="cluster"
    )
    assert [item["threshold"] for item in notifications] == [50, 100]
    assert notifications[0]["subscriber_addresses"] == ["a@example.org", "b@example.org"]


def test_athena_list_helpers_paginate_filter_and_deduplicate() -> None:
    class Athena:
        def __init__(self) -> None:
            self.query_calls = 0
            self.workgroup_calls = 0

        def list_query_executions(self, **request):
            self.query_calls += 1
            return (
                {"QueryExecutionIds": ["q1", ""], "NextToken": "next"}
                if self.query_calls == 1
                else {"QueryExecutionIds": ["q2"]}
            )

        def list_work_groups(self, **request):
            self.workgroup_calls += 1
            return (
                {"WorkGroups": [{"Name": "primary"}], "NextToken": "next"}
                if self.workgroup_calls == 1
                else {"WorkGroups": [{"Name": "primary"}, {"Name": "analytics"}, {}]}
            )

    client = Athena()
    assert _list_athena_query_execution_ids(client, workgroup="primary") == ["q1", "q2"]
    assert _list_athena_workgroups(client) == ["analytics", "primary"]


@pytest.mark.parametrize(
    ("client", "expected"),
    [
        (
            SimpleNamespace(
                get_work_group=lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("denied"))
            ),
            CheckStatus.FAIL,
        ),
        (
            SimpleNamespace(get_work_group=lambda **_kwargs: {"WorkGroup": {"State": "DISABLED"}}),
            CheckStatus.FAIL,
        ),
        (
            SimpleNamespace(get_work_group=lambda **_kwargs: {"WorkGroup": {"State": "ENABLED"}}),
            CheckStatus.PASS,
        ),
    ],
)
def test_athena_readiness_is_read_only_and_requires_enabled_workgroup(
    monkeypatch: pytest.MonkeyPatch,
    client: object,
    expected: CheckStatus,
) -> None:
    monkeypatch.setattr(validation, "_regional_client", lambda *_args: client)
    result = _check_athena_readiness(_Context())
    assert result.status is expected
    assert result.details["query_started"] is False


def _patch_accounting_flags(
    monkeypatch: pytest.MonkeyPatch, *, enabled: bool, create_if_missing: bool = False
) -> None:
    monkeypatch.setattr(
        validation,
        "_strict_bool_config",
        lambda _cfg, key, _fallback: (
            enabled if key == "slurm_accounting_enabled" else create_if_missing
        ),
    )


def test_slurm_accounting_readiness_disabled_and_missing_baseline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_accounting_flags(monkeypatch, enabled=False)
    assert check_slurm_accounting_readiness(_Context(), ConfigFile()).status is CheckStatus.PASS

    _patch_accounting_flags(monkeypatch, enabled=True)
    monkeypatch.setattr(validation, "get_stack_outputs", lambda *_args: SimpleNamespace(vpc_id=""))
    assert (
        check_slurm_accounting_readiness(_Context(cloudformation=object()), ConfigFile()).status
        is CheckStatus.FAIL
    )


@pytest.mark.parametrize(
    ("create_if_missing", "expected"),
    [(False, CheckStatus.FAIL), (True, CheckStatus.WARN)],
)
def test_slurm_accounting_readiness_missing_service_respects_creation_policy(
    monkeypatch: pytest.MonkeyPatch,
    create_if_missing: bool,
    expected: CheckStatus,
) -> None:
    _patch_accounting_flags(monkeypatch, enabled=True, create_if_missing=create_if_missing)
    monkeypatch.setattr(
        validation, "get_stack_outputs", lambda *_args: SimpleNamespace(vpc_id="vpc-1")
    )
    monkeypatch.setattr(validation, "discover_slurm_accounting_dbs", lambda *_args, **_kwargs: [])
    result = check_slurm_accounting_readiness(_Context(cloudformation=object()), ConfigFile())
    assert result.status is expected
    assert result.details["found"] is False


def test_slurm_accounting_readiness_discovery_and_metadata_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_accounting_flags(monkeypatch, enabled=True)
    monkeypatch.setattr(
        validation, "get_stack_outputs", lambda *_args: SimpleNamespace(vpc_id="vpc-1")
    )
    monkeypatch.setattr(
        validation,
        "discover_slurm_accounting_dbs",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            validation.SlurmAccountingError("incompatible")
        ),
    )
    assert (
        check_slurm_accounting_readiness(_Context(cloudformation=object()), ConfigFile()).status
        is CheckStatus.FAIL
    )

    db = SimpleNamespace(
        stack_name="accounting",
        status="CREATE_COMPLETE",
        instance_id="",
        client_security_group_id="sg-client",
        password_secret_arn="arn:secret",
    )
    monkeypatch.setattr(validation, "discover_slurm_accounting_dbs", lambda *_args, **_kwargs: [db])
    result = check_slurm_accounting_readiness(_Context(cloudformation=object()), ConfigFile())
    assert result.status is CheckStatus.FAIL
    assert result.details["secret_value_read"] is False


@pytest.mark.parametrize(
    ("instance_state", "security_groups", "secret", "expected"),
    [
        ("stopped", [{}], {"ARN": "arn:secret"}, CheckStatus.FAIL),
        ("running", [], {"ARN": "arn:secret"}, CheckStatus.FAIL),
        ("running", [{}], {}, CheckStatus.FAIL),
        ("running", [{}], {"ARN": "arn:secret"}, CheckStatus.PASS),
    ],
)
def test_slurm_accounting_readiness_validates_live_metadata_without_secret_value_read(
    monkeypatch: pytest.MonkeyPatch,
    instance_state: str,
    security_groups: list[dict],
    secret: dict,
    expected: CheckStatus,
) -> None:
    _patch_accounting_flags(monkeypatch, enabled=True)
    monkeypatch.setattr(
        validation, "get_stack_outputs", lambda *_args: SimpleNamespace(vpc_id="vpc-1")
    )
    db = SimpleNamespace(
        stack_name="accounting",
        status="CREATE_COMPLETE",
        instance_id="i-accounting",
        client_security_group_id="sg-client",
        password_secret_arn="arn:secret",
    )
    monkeypatch.setattr(validation, "discover_slurm_accounting_dbs", lambda *_args, **_kwargs: [db])
    ec2 = SimpleNamespace(
        describe_instances=lambda **_kwargs: {
            "Reservations": [{"Instances": [{"State": {"Name": instance_state}}]}]
        },
        describe_security_groups=lambda **_kwargs: {"SecurityGroups": security_groups},
    )
    secrets = SimpleNamespace(describe_secret=lambda **_kwargs: secret)
    result = check_slurm_accounting_readiness(
        _Context(cloudformation=object(), ec2=ec2, secretsmanager=secrets),
        ConfigFile(),
    )
    assert result.status is expected
    assert result.details["secret_value_read"] is False


def test_accounting_shape_disabled_invalid_instance_and_valid_demand(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_accounting_flags(monkeypatch, enabled=False)
    check, vcpus, gp3 = _check_slurm_accounting_shape(_Context(), ConfigFile())
    assert (check.status, vcpus, gp3) == (CheckStatus.PASS, 0, 0)

    _patch_accounting_flags(monkeypatch, enabled=True)
    monkeypatch.setattr(validation, "_effective_config_value", lambda *_args: "t4g.micro")
    monkeypatch.setattr(
        validation,
        "_describe_instance_vcpus",
        lambda *_args: (_ for _ in ()).throw(RuntimeError("unknown type")),
    )
    check, vcpus, gp3 = _check_slurm_accounting_shape(_Context(ec2=object()), ConfigFile())
    assert (check.status, vcpus, gp3) == (CheckStatus.FAIL, 0, 0)

    monkeypatch.setattr(validation, "_describe_instance_vcpus", lambda *_args: {"t4g.micro": 2})
    check, vcpus, gp3 = _check_slurm_accounting_shape(_Context(ec2=object()), ConfigFile())
    assert (check.status, vcpus, gp3) == (CheckStatus.PASS, 2, 20)


@pytest.mark.parametrize(
    ("deployment", "item", "expected"),
    [
        ("scratch", {"LustreConfiguration": {"DeploymentType": "SCRATCH_2"}}, True),
        ("persistent_1", {"LustreConfiguration": {"DeploymentType": "PERSISTENT_1"}}, True),
        (
            "persistent_2",
            {"LustreConfiguration": {"DeploymentType": "PERSISTENT_2"}, "StorageType": "SSD"},
            True,
        ),
        (
            "persistent_intelligent_tiering",
            {
                "LustreConfiguration": {"DeploymentType": "PERSISTENT_2"},
                "StorageType": "INTELLIGENT_TIERING",
            },
            True,
        ),
        ("unknown", {}, False),
    ],
)
def test_fsx_deployment_matching(deployment: str, item: dict, expected: bool) -> None:
    assert _fsx_lustre_matches_deployment(item, deployment) is expected


def test_glue_contract_helpers_compare_location_parameters_and_nested_schema() -> None:
    descriptor = {
        "Location": "s3://cur/table/",
        "Columns": [{"Name": "identity_line_item_id", "Type": "string"}],
        "InputFormat": "input",
        "OutputFormat": "output",
        "SerdeInfo": {"SerializationLibrary": "serde"},
        "StoredAsSubDirectories": False,
    }
    expected = {
        "Name": "cur_table",
        "TableType": "EXTERNAL_TABLE",
        "Parameters": {"classification": "parquet"},
        "PartitionKeys": [{"Name": "billing_period", "Type": "string"}],
        "StorageDescriptor": descriptor,
    }
    actual = {**expected, "Parameters": {"classification": "parquet", "extra": "ok"}}
    assert _glue_table_contract_matches(actual, expected)
    assert not _glue_table_contract_matches(
        {**actual, "Parameters": {"classification": "csv"}}, expected
    )
    assert not _glue_storage_descriptor_matches(
        {**descriptor, "Location": "s3://wrong/"}, descriptor
    )
    assert _glue_storage_descriptor_matches(
        {**descriptor, "Location": "s3://different/"},
        descriptor,
        compare_location=False,
    )


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ("[1]", "not a YAML mapping"),
        ("HeadNode: [1]", "missing HeadNode mapping"),
        ("HeadNode: {}", "missing HeadNode.InstanceType"),
        (
            "HeadNode:\n  InstanceType: r7i.2xlarge\n  LocalStorage:\n    RootVolume:\n      Size: 0",
            "must be greater than zero",
        ),
        (
            "HeadNode:\n  InstanceType: r7i.2xlarge\n  LocalStorage:\n    RootVolume:\n      Size: 20\nScheduling:\n  SlurmQueues:\n    wrong: value",
            "SlurmQueues is not a list",
        ),
    ],
)
def test_extract_cluster_shape_rejects_invalid_rendered_contracts(
    payload: str, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        extract_cluster_shape(
            payload,
            _Context(ec2=object()),
            cluster_name="coverage",
            template_path="cluster.yaml",
        )
