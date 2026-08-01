"""Read-only AWS readiness validation for Daylily ephemeral clusters."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from fnmatch import fnmatchcase
import json
from pathlib import Path
from typing import Any, Callable, Iterable, Literal, Optional
from urllib.parse import unquote

from pydantic import Field
import yaml

from daylily_ec.aws.budgets import (
    CLUSTER_THRESHOLDS,
    GLOBAL_BUDGET_NAME,
    GLOBAL_THRESHOLDS,
    cluster_budget_name,
    make_budget_preflight_step,
)
from daylily_ec.aws.cloudformation import (
    derive_stack_name,
    describe_stack_status,
    get_stack_outputs,
)
from daylily_ec.aws.context import AWSContext, parse_region_az
from daylily_ec.aws.cost_centers import (
    DEFAULT_COST_CENTER_HOME_REGION,
    DEFAULT_COST_CENTER_TABLE,
    DEFAULT_COST_CENTER_USAGE_TABLE,
    RESERVED_IDLE_COST_CENTER,
    cost_center_is_expired,
    list_cost_center_usage,
    list_cost_centers,
)
from daylily_ec.aws.cur_export import (
    CUR_EXPORT_COLUMNS,
    DATA_EXPORTS_TABLE,
    DEFAULT_BILLING_REGION,
    DEFAULT_DATABASE as DEFAULT_CUR_DATABASE,
    DEFAULT_EXPORT_NAME as DEFAULT_CUR_EXPORT_NAME,
    DEFAULT_EXPORT_PREFIX as DEFAULT_CUR_EXPORT_PREFIX,
    DEFAULT_TABLE as DEFAULT_CUR_TABLE,
    CurExportConfig,
    _export_for_compare,
    billing_period_data_location,
    build_cur2_export_definition,
    data_exports_bucket_policy_statement,
    default_cur_export_bucket,
    get_cur2_schema,
    glue_table_input,
)
from daylily_ec.aws.dragen_license import make_dragen_license_preflight_step
from daylily_ec.aws.iam import (
    PCLUSTER_OMICS_POLICY_NAME,
    check_daylily_policies,
)
from daylily_ec.aws.quotas import (
    QUOTA_DEFS,
    _fetch_quota_value,
    check_all_quotas,
)
from daylily_ec.aws.s3 import normalize_role_s3_uri
from daylily_ec.aws.slurm_accounting import (
    SlurmAccountingError,
    derive_slurm_accounting_stack_name,
    discover_slurm_accounting_dbs,
    list_regional_slurm_accounting_stacks,
)
from daylily_ec.config.triplets import (
    get_effective_default,
    load_config,
    resolve_derived_max_count,
    resolve_value,
)
from daylily_ec.render.renderer import ALL_SUBSTITUTION_KEYS, REQUIRED_KEYS, render_template
from daylily_ec.resources import resource_path
from daylily_ec.state.models import CheckResult, CheckStatus, PreflightReport
from daylily_ec.workflow.create_cluster import (
    DEFAULT_CREATE_CLUSTER_TYPE,
    EXIT_SUCCESS,
    EXIT_VALIDATION_FAILURE,
    az_cluster_template_relative_path,
    normalize_enforce_budget,
)

ValidationMode = Literal["permissions", "quotas", "all"]
SUPPORTED_MODES: tuple[str, ...] = ("permissions", "quotas", "all")
DEFAULT_CONFIG_PATH = "config/daylily_ephemeral_cluster_template.yaml"
SSM_SESSION_DOCUMENT = "SSM-SessionManagerRunShell"
COST_CENTER_MAX_USAGE_AGE_HOURS = 64
BUDGET_COUNT_QUOTA = 20_000
CUR_EXPORT_COUNT_QUOTA = 5
DYNAMODB_TABLE_QUOTA_CODE = "L-F98FE922"
S3_GENERAL_PURPOSE_BUCKET_QUOTA_CODE = "L-DC2B2D3D"
ATHENA_ACTIVE_DML_QUOTA_CODE = "L-FC5F6546"
CLOUDFORMATION_STACK_QUOTA_CODE = "L-0485CB21"
VPC_SECURITY_GROUP_QUOTA_CODE = "L-E79EC296"
VPC_NETWORK_INTERFACE_QUOTA_CODE = "L-DF5E4CA3"
SECRETS_MANAGER_SECRET_QUOTA_CODE = "L-2F66C23C"
EC2_VCPU_QUOTA_CODES: dict[tuple[str, str], tuple[str, str]] = {
    ("standard", "ONDEMAND"): (
        "L-1216C47A",
        "Running On-Demand Standard (A, C, D, H, I, M, R, T, Z) instances",
    ),
    ("standard", "SPOT"): (
        "L-34B43A08",
        "All Standard (A, C, D, H, I, M, R, T, Z) Spot Instance Requests",
    ),
    ("x", "ONDEMAND"): ("L-7295265B", "Running On-Demand X instances"),
    ("x", "SPOT"): ("L-E3A00192", "All X Spot Instance Requests"),
    ("f", "ONDEMAND"): ("L-74FC7D96", "Running On-Demand F instances"),
    ("f", "SPOT"): ("L-88CF9481", "All F Spot Instance Requests"),
    ("g_vt", "ONDEMAND"): (
        "L-DB2E81BA",
        "Running On-Demand G and VT instances",
    ),
    ("g_vt", "SPOT"): ("L-3819A6DF", "All G and VT Spot Instance Requests"),
    ("p", "ONDEMAND"): ("L-417A185B", "Running On-Demand P instances"),
    ("p", "SPOT"): ("L-7212CCBC", "All P Spot Instance Requests"),
    ("inf", "ONDEMAND"): ("L-1945791B", "Running On-Demand Inf instances"),
    ("inf", "SPOT"): ("L-B5D1601B", "All Inf Spot Instance Requests"),
    ("trn", "ONDEMAND"): ("L-2C3B7624", "Running On-Demand Trn instances"),
    ("trn", "SPOT"): ("L-6B0D517C", "All Trn Spot Instance Requests"),
    ("dl", "ONDEMAND"): ("L-6E869C2A", "Running On-Demand DL instances"),
    ("dl", "SPOT"): ("L-85EED4F7", "All DL Spot Instance Requests"),
    ("hpc", "ONDEMAND"): ("L-F7808C92", "Running On-Demand HPC instances"),
    ("high_memory", "ONDEMAND"): (
        "L-43DA4232",
        "Running On-Demand High Memory instances",
    ),
}
BUDGET_QUOTA_SOURCE = (
    "https://docs.aws.amazon.com/cost-management/latest/userguide/management-limits.html"
)
CUR_EXPORT_QUOTA_SOURCE = "https://docs.aws.amazon.com/cur/latest/userguide/dataexports-quotas.html"


class AwsValidationError(RuntimeError):
    """Raised when validation cannot be constructed from explicit inputs."""


@dataclass(frozen=True)
class AwsValidationOptions:
    """Options for the read-only AWS validator."""

    mode: ValidationMode
    profile: str
    region_az: str
    config_path: Optional[str] = None
    gap_analysis_path: Optional[Path] = None

    def __post_init__(self) -> None:
        mode = str(self.mode or "").strip()
        profile = str(self.profile or "").strip()
        region_az = str(self.region_az or "").strip()
        if mode not in SUPPORTED_MODES:
            raise AwsValidationError(
                f"Unsupported AWS validation mode '{mode}'. Expected one of: "
                f"{', '.join(SUPPORTED_MODES)}."
            )
        if not profile:
            raise AwsValidationError("--profile is required for aws validate.")
        if profile == "default":
            raise AwsValidationError(
                "The implicit 'default' AWS profile is not accepted. Use an explicit named profile."
            )
        if not region_az:
            raise AwsValidationError("--region-az is required for aws validate.")
        try:
            parse_region_az(region_az)
        except ValueError as exc:
            raise AwsValidationError(str(exc)) from exc
        object.__setattr__(self, "mode", mode)
        object.__setattr__(self, "profile", profile)
        object.__setattr__(self, "region_az", region_az)


class AwsValidationReport(PreflightReport):
    """Full read-only validation report for CLI JSON output and gap reports."""

    mode: str = ""
    config_path: str = ""
    summary: dict[str, int] = Field(default_factory=dict)

    @property
    def ready(self) -> bool:
        """True when every check passed."""
        return not self.failed_checks and not self.warned_checks

    def to_sorted_json(self, indent: int = 2) -> str:
        return json.dumps(
            self.model_dump(mode="json"),
            indent=indent,
            sort_keys=True,
        )


@dataclass(frozen=True)
class PermissionGroup:
    """One IAM simulation group."""

    check_id: str
    label: str
    actions: tuple[str, ...]
    resources: tuple[str, ...] = ("*",)
    context: tuple[tuple[str, tuple[str, ...]], ...] = ()


@dataclass(frozen=True)
class ComputeResourceDemand:
    """Rendered ParallelCluster compute demand for one compute resource."""

    queue: str
    capacity_type: str
    name: str
    max_count: int
    instance_types: tuple[str, ...]
    max_vcpus_per_instance: int
    demand_vcpus: int


@dataclass(frozen=True)
class ClusterShape:
    """Demand extracted from a rendered ParallelCluster YAML."""

    cluster_name: str
    template_path: str
    headnode_instance_type: str
    headnode_vcpus: int
    headnode_root_volume_type: str
    headnode_root_volume_gib: int
    fsx_deployment_type: str
    fsx_storage_type: str
    fsx_storage_gib: int
    fsx_read_cache_gib: int
    fsx_throughput_capacity: int
    compute_resources: tuple[ComputeResourceDemand, ...]
    vcpus_by_instance_type: dict[str, int]

    @property
    def all_instance_types(self) -> tuple[str, ...]:
        values = {self.headnode_instance_type}
        for resource in self.compute_resources:
            values.update(resource.instance_types)
        return tuple(sorted(v for v in values if v))

    @property
    def spot_instance_types(self) -> tuple[str, ...]:
        values: set[str] = set()
        for resource in self.compute_resources:
            if resource.capacity_type == "SPOT":
                values.update(resource.instance_types)
        return tuple(sorted(values))

    @property
    def rendered_spot_vcpus(self) -> int:
        return sum(
            resource.demand_vcpus
            for resource in self.compute_resources
            if resource.capacity_type == "SPOT"
        )

    @property
    def rendered_ondemand_vcpus(self) -> int:
        return self.headnode_vcpus + sum(
            resource.demand_vcpus
            for resource in self.compute_resources
            if resource.capacity_type == "ONDEMAND"
        )

    def to_details(self) -> dict[str, Any]:
        return {
            "cluster_name": self.cluster_name,
            "template_path": self.template_path,
            "headnode_instance_type": self.headnode_instance_type,
            "headnode_vcpus": self.headnode_vcpus,
            "headnode_root_volume_type": self.headnode_root_volume_type,
            "headnode_root_volume_gib": self.headnode_root_volume_gib,
            "fsx_deployment_type": self.fsx_deployment_type,
            "fsx_storage_type": self.fsx_storage_type,
            "fsx_storage_gib": self.fsx_storage_gib,
            "fsx_read_cache_gib": self.fsx_read_cache_gib,
            "fsx_throughput_capacity": self.fsx_throughput_capacity,
            "rendered_spot_vcpus": self.rendered_spot_vcpus,
            "rendered_ondemand_vcpus": self.rendered_ondemand_vcpus,
            "instance_types": list(self.all_instance_types),
            "compute_resources": [
                {
                    "queue": resource.queue,
                    "capacity_type": resource.capacity_type,
                    "name": resource.name,
                    "max_count": resource.max_count,
                    "instance_types": list(resource.instance_types),
                    "max_vcpus_per_instance": resource.max_vcpus_per_instance,
                    "demand_vcpus": resource.demand_vcpus,
                }
                for resource in self.compute_resources
            ],
        }


def run_aws_validation(
    options: AwsValidationOptions,
    *,
    context_builder: Callable[[str, Optional[str]], AWSContext] = AWSContext.build,
) -> tuple[int, AwsValidationReport]:
    """Run read-only AWS validation and return ``(exit_code, report)``."""

    aws_ctx = context_builder(options.region_az, options.profile)
    config_path = str(_resolve_config_path(options.config_path))
    cfg = load_config(config_path)
    cluster_name = _effective_config_value(cfg, "cluster_name", "prod") or "prod"

    report = AwsValidationReport(
        run_id=datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S"),
        cluster_name=cluster_name or None,
        region=aws_ctx.region,
        region_az=aws_ctx.region_az,
        aws_profile=aws_ctx.profile,
        account_id=aws_ctx.account_id,
        caller_arn=aws_ctx.caller_arn,
        mode=options.mode,
        config_path=config_path,
    )
    report.checks.append(
        CheckResult(
            id="aws.identity",
            status=CheckStatus.PASS,
            details={
                "account_id": aws_ctx.account_id,
                "caller_arn": aws_ctx.caller_arn,
                "profile": aws_ctx.profile,
                "region": aws_ctx.region,
                "region_az": aws_ctx.region_az,
            },
        )
    )

    if options.mode in ("permissions", "all"):
        report.checks.extend(run_permission_checks(aws_ctx, cfg=cfg))
    if options.mode in ("quotas", "all"):
        report.checks.extend(run_quota_checks(aws_ctx, cfg, config_path=config_path))

    _finalize_summary(report)
    if options.gap_analysis_path is not None:
        write_gap_analysis(report, options.gap_analysis_path)

    return (
        EXIT_SUCCESS if report.ready else EXIT_VALIDATION_FAILURE,
        report,
    )


def run_permission_checks(aws_ctx: AWSContext, *, cfg: Any | None = None) -> list[CheckResult]:
    """Run all read-only permission validation checks."""

    iam_client = aws_ctx.client("iam")
    checks: list[CheckResult] = []
    checks.extend(
        check_daylily_policies(
            iam_client,
            aws_ctx.iam_username,
            aws_ctx.region,
            interactive=False,
        )
    )
    checks.append(check_pcluster_omics_policy_exists(iam_client))
    checks.append(check_ssm_session_document(aws_ctx.client("ssm")))
    checks.extend(simulate_required_permissions(aws_ctx, iam_client, cfg=cfg))
    if cfg is not None:
        checks.append(check_runtime_cost_policy(aws_ctx, iam_client, cfg))
        checks.append(check_dragen_license_configuration(aws_ctx, iam_client, cfg))
        checks.extend(check_cost_control_readiness(aws_ctx, cfg))
        checks.append(check_slurm_accounting_readiness(aws_ctx, cfg))
    return checks


def check_pcluster_omics_policy_exists(iam_client: Any) -> CheckResult:
    """Check for ``pcluster-omics-analysis`` without creating it."""

    try:
        paginator = iam_client.get_paginator("list_policies")
        for page in paginator.paginate(Scope="Local"):
            for policy in page.get("Policies", []):
                if policy.get("PolicyName") == PCLUSTER_OMICS_POLICY_NAME:
                    return CheckResult(
                        id="iam.pcluster_omics_policy",
                        status=CheckStatus.PASS,
                        details={
                            "policy": PCLUSTER_OMICS_POLICY_NAME,
                            "arn": policy.get("Arn", ""),
                            "read_only": True,
                        },
                    )
    except Exception as exc:
        return CheckResult(
            id="iam.pcluster_omics_policy",
            status=CheckStatus.FAIL,
            details={"policy": PCLUSTER_OMICS_POLICY_NAME, "error": str(exc)},
            remediation=(
                "Unable to list local IAM policies. Grant iam:ListPolicies so "
                "Daylily can verify the pcluster-omics-analysis policy."
            ),
        )

    return CheckResult(
        id="iam.pcluster_omics_policy",
        status=CheckStatus.FAIL,
        details={"policy": PCLUSTER_OMICS_POLICY_NAME, "found": False},
        remediation=(
            f"Create the IAM policy '{PCLUSTER_OMICS_POLICY_NAME}' with the "
            "Spot service-linked-role permission, or run the Daylily global "
            "admin bootstrap helper with an admin profile."
        ),
    )


def check_ssm_session_document(ssm_client: Any) -> CheckResult:
    """Verify the supported Session Manager shell document is readable and correct."""

    try:
        response = ssm_client.get_document(
            Name=SSM_SESSION_DOCUMENT,
            DocumentFormat="JSON",
        )
    except Exception as exc:
        return CheckResult(
            id="ssm.session_document",
            status=CheckStatus.FAIL,
            details={"document": SSM_SESSION_DOCUMENT, "error": str(exc)},
            remediation=(
                f"Create or grant ssm:GetDocument access to {SSM_SESSION_DOCUMENT}. "
                "The document must run shell sessions as the cluster-appropriate remote user "
                "in a bash login/interactive shell that sources ~/.bashrc."
            ),
        )

    try:
        payload = _decode_ssm_document(response.get("Content", "{}"))
    except ValueError as exc:
        return CheckResult(
            id="ssm.session_document",
            status=CheckStatus.FAIL,
            details={"document": SSM_SESSION_DOCUMENT, "error": str(exc)},
            remediation=(
                f"Replace {SSM_SESSION_DOCUMENT} with valid JSON Session Manager "
                "preferences that use the cluster-appropriate remote user."
            ),
        )

    inputs = payload.get("inputs", {}) if isinstance(payload, dict) else {}
    shell_profile = inputs.get("shellProfile", {}) if isinstance(inputs, dict) else {}
    linux_shell_profile = ""
    if isinstance(shell_profile, dict):
        linux_shell_profile = str(shell_profile.get("linux") or "")
    run_as_enabled = inputs.get("runAsEnabled") is True if isinstance(inputs, dict) else False
    run_as_user = str(inputs.get("runAsDefaultUser") or "") if isinstance(inputs, dict) else ""
    login_shell_ok = (
        "bash -il" in linux_shell_profile
        or "bash -li" in linux_shell_profile
        or ("--login" in linux_shell_profile and "--interactive" in linux_shell_profile)
    )
    bashrc_ok = ".bashrc" in linux_shell_profile

    details = {
        "document": SSM_SESSION_DOCUMENT,
        "runAsEnabled": run_as_enabled,
        "runAsDefaultUser": run_as_user,
        "shellProfileLinux": linux_shell_profile,
    }
    if run_as_enabled and run_as_user in {"ubuntu", "ec2-user"} and login_shell_ok and bashrc_ok:
        return CheckResult(
            id="ssm.session_document",
            status=CheckStatus.PASS,
            details=details,
        )
    return CheckResult(
        id="ssm.session_document",
        status=CheckStatus.FAIL,
        details=details,
        remediation=(
            f"Update {SSM_SESSION_DOCUMENT} so runAsEnabled is true, "
            "runAsDefaultUser is the resolved cluster user (ubuntu for Ubuntu/Intel "
            "DayOA headnodes, ec2-user for DRAGEN/RHEL-style headnodes), and "
            "shellProfile.linux enters a bash login/interactive shell that sources ~/.bashrc."
        ),
    )


def check_runtime_cost_policy(
    aws_ctx: AWSContext,
    iam_client: Any,
    cfg: Any,
) -> CheckResult:
    """Validate the selected headnode policy, not merely a same-name policy."""

    partition = _aws_partition(aws_ctx.caller_arn)
    policy_arn = _effective_config_value(
        cfg,
        "iam_policy_arn",
        f"arn:{partition}:iam::{aws_ctx.account_id}:policy/pclusterTagsAndBudget",
    )
    if not policy_arn:
        return CheckResult(
            id="iam.runtime_cost_policy",
            status=CheckStatus.FAIL,
            details={"actor": "headnode", "policy_arn": ""},
            remediation=(
                "Set iam_policy_arn to the managed headnode policy used by the rendered "
                "ParallelCluster configuration."
            ),
        )

    try:
        policy = iam_client.get_policy(PolicyArn=policy_arn).get("Policy") or {}
        version_id = str(policy.get("DefaultVersionId") or "")
        if not version_id:
            raise ValueError("managed policy has no default version")
        version = (
            iam_client.get_policy_version(
                PolicyArn=policy_arn,
                VersionId=version_id,
            ).get("PolicyVersion")
            or {}
        )
        document = _decode_policy_document(version.get("Document"))
    except Exception as exc:
        return CheckResult(
            id="iam.runtime_cost_policy",
            status=CheckStatus.FAIL,
            details={
                "actor": "headnode",
                "policy_arn": policy_arn,
                "error": str(exc),
            },
            remediation=(
                "Grant iam:GetPolicy and iam:GetPolicyVersion, and ensure the selected "
                "pclusterTagsAndBudget managed policy exists."
            ),
        )

    budget_resource = f"arn:{partition}:budgets::{aws_ctx.account_id}:budget/*"
    registry_table_arn = (
        f"arn:{partition}:dynamodb:{DEFAULT_COST_CENTER_HOME_REGION}:"
        f"{aws_ctx.account_id}:table/{DEFAULT_COST_CENTER_TABLE}"
    )
    requirements = [
        ("budgets:ViewBudget", budget_resource),
        ("billing:GetBillingViewData", "*"),
        ("dynamodb:GetItem", registry_table_arn),
    ]
    missing = [
        {"action": action, "resource": resource}
        for action, resource in requirements
        if not _policy_allows(document, action=action, resource=resource)
    ]
    details = {
        "actor": "headnode",
        "policy_arn": policy_arn,
        "default_version_id": version_id,
        "required_permissions": [
            {"action": action, "resource": resource} for action, resource in requirements
        ],
        "missing_permissions": missing,
    }
    if missing:
        return CheckResult(
            id="iam.runtime_cost_policy",
            status=CheckStatus.FAIL,
            details=details,
            remediation=(
                "Update the selected headnode managed policy with the missing budget "
                "and cost-center registry read. Monthly usage is reporting telemetry "
                "and is not part of Slurm admission."
            ),
        )
    return CheckResult(
        id="iam.runtime_cost_policy",
        status=CheckStatus.PASS,
        details=details,
    )


def check_dragen_license_configuration(
    aws_ctx: AWSContext,
    iam_client: Any,
    cfg: Any,
) -> CheckResult:
    """Validate optional DRAGEN secret metadata and its least-privilege policy."""

    secret_arn = _effective_config_value(cfg, "dragen_license_secret_arn", "")
    policy_arn = _effective_config_value(cfg, "dragen_license_policy_arn", "")
    if not secret_arn and not policy_arn:
        return CheckResult(
            id="iam.dragen_license_secret_policy",
            status=CheckStatus.PASS,
            details={"configured": False, "secret_value_read": False},
        )
    if not secret_arn or not policy_arn:
        return CheckResult(
            id="iam.dragen_license_secret_policy",
            status=CheckStatus.FAIL,
            details={
                "configured": True,
                "secret_arn": secret_arn,
                "policy_arn": policy_arn,
                "secret_value_read": False,
            },
            remediation=(
                "Set both dragen_license_secret_arn and dragen_license_policy_arn, "
                "or leave both empty."
            ),
        )

    probe = PreflightReport()
    make_dragen_license_preflight_step(
        secretsmanager_client=aws_ctx.client("secretsmanager"),
        iam_client=iam_client,
        secret_arn=secret_arn,
        policy_arn=policy_arn,
    )(probe)
    return probe.checks[-1]


def check_cost_control_readiness(
    aws_ctx: AWSContext,
    cfg: Any,
) -> list[CheckResult]:
    """Inspect the live budget, cost-center, and CUR resources without mutation."""

    cluster_name = _effective_config_value(cfg, "cluster_name", "prod") or "prod"
    budgets_client = aws_ctx.client("budgets")
    budget_check = make_budget_preflight_step(
        budgets_client,
        aws_ctx.account_id,
        global_budget_name=GLOBAL_BUDGET_NAME,
        cluster_name=cluster_name,
        region_az=aws_ctx.region_az,
    )
    budget_check.details["enforcement"] = normalize_enforce_budget(
        _effective_config_value(cfg, "enforce_budget", "true")
    )
    budget_check.details["actor"] = "operator"
    _enrich_budget_readiness(
        budget_check,
        budgets_client=budgets_client,
        account_id=aws_ctx.account_id,
        cluster_name=cluster_name,
        global_budget_amount=_effective_config_value(
            cfg,
            "global_budget_amount",
            "200",
        ),
        cluster_budget_amount=_effective_config_value(cfg, "budget_amount", "200"),
        notification_email=_effective_config_value(cfg, "budget_email", ""),
    )
    return [
        budget_check,
        _check_cost_center_registry_readiness(aws_ctx),
        _check_cur_export_readiness(aws_ctx),
        _check_cur_catalog_readiness(aws_ctx),
        _check_athena_readiness(aws_ctx),
    ]


def _enrich_budget_readiness(
    check: CheckResult,
    *,
    budgets_client: Any,
    account_id: str,
    cluster_name: str,
    global_budget_amount: str,
    cluster_budget_amount: str,
    notification_email: str,
) -> None:
    """Add limits, spend, filters, and notifications to budget readiness."""

    requested = (
        (
            GLOBAL_BUDGET_NAME,
            global_budget_amount,
            GLOBAL_THRESHOLDS,
            bool(check.details.get("global_exists")),
            f"user:aws-parallelcluster-clustername${cluster_name}",
        ),
        (
            cluster_name,
            cluster_budget_amount,
            CLUSTER_THRESHOLDS,
            bool(check.details.get("cluster_exists")),
            f"user:aws-parallelcluster-clustername${cluster_name}",
        ),
    )
    snapshots: dict[str, Any] = {}
    budget_gaps: list[dict[str, Any]] = []
    try:
        for (
            name,
            configured_amount,
            expected_thresholds,
            exists,
            expected_tag_filter,
        ) in requested:
            snapshot: dict[str, Any] = {
                "exists": exists,
                "configured_limit_usd": configured_amount,
                "expected_notification_thresholds_percent": list(expected_thresholds),
                "expected_cost_filter": {"TagKeyValue": [expected_tag_filter]},
            }
            snapshots[name] = snapshot
            if not exists:
                budget_gaps.append({"budget": name, "reason": "budget is missing"})
                continue
            budget = (
                budgets_client.describe_budget(
                    AccountId=account_id,
                    BudgetName=name,
                ).get("Budget")
                or {}
            )
            limit = budget.get("BudgetLimit") or {}
            calculated = budget.get("CalculatedSpend") or {}
            actual = calculated.get("ActualSpend") or {}
            forecast = calculated.get("ForecastedSpend") or {}
            limit_amount = str(limit.get("Amount") or "")
            actual_amount = str(actual.get("Amount") or "")
            forecast_amount = str(forecast.get("Amount") or "")
            snapshot.update(
                {
                    "budget_type": budget.get("BudgetType", ""),
                    "time_unit": budget.get("TimeUnit", ""),
                    "limit_amount": limit_amount,
                    "limit_unit": limit.get("Unit", ""),
                    "actual_spend_amount": actual_amount,
                    "actual_spend_unit": actual.get("Unit", ""),
                    "forecast_spend_amount": forecast_amount,
                    "forecast_spend_unit": forecast.get("Unit", ""),
                    "cost_filters": _json_safe(budget.get("CostFilters") or {}),
                    "last_updated_time": _json_safe(budget.get("LastUpdatedTime")),
                }
            )
            configured_decimal = _optional_decimal(configured_amount)
            limit_decimal = _optional_decimal(limit_amount)
            actual_decimal = _optional_decimal(actual_amount)
            expected_filter = {"TagKeyValue": [expected_tag_filter]}
            snapshot["limit_matches_config"] = (
                configured_decimal is not None
                and limit_decimal is not None
                and configured_decimal == limit_decimal
            )
            snapshot["actual_spend_below_limit"] = (
                actual_decimal is not None
                and limit_decimal is not None
                and actual_decimal >= 0
                and limit_decimal > 0
                and actual_decimal < limit_decimal
            )
            snapshot["budget_type_valid"] = budget.get("BudgetType") == "COST"
            snapshot["time_unit_valid"] = budget.get("TimeUnit") == "MONTHLY"
            snapshot["currency_valid"] = limit.get("Unit") == "USD" and actual.get("Unit") == "USD"
            snapshot["cost_filter_matches_config"] = (
                budget.get("CostFilters") or {}
            ) == expected_filter
            notifications = _describe_budget_notifications(
                budgets_client,
                account_id=account_id,
                budget_name=name,
            )
            snapshot["notifications"] = notifications
            valid_notifications = [
                item
                for item in notifications
                if item.get("threshold") is not None
                and item.get("notification_type") == "ACTUAL"
                and item.get("comparison_operator") == "GREATER_THAN"
                and item.get("threshold_type") in {"", "PERCENTAGE"}
            ]
            thresholds = {float(item["threshold"]) for item in valid_notifications}
            missing_thresholds = [
                threshold for threshold in expected_thresholds if float(threshold) not in thresholds
            ]
            snapshot["missing_notification_thresholds_percent"] = missing_thresholds
            if notification_email:
                snapshot["configured_notification_email"] = notification_email
                snapshot["configured_email_subscribed"] = (
                    all(
                        notification_email in item.get("subscriber_addresses", [])
                        for item in valid_notifications
                        if float(item.get("threshold") or -1)
                        in {float(value) for value in expected_thresholds}
                    )
                    and not missing_thresholds
                )

            if not snapshot["actual_spend_below_limit"]:
                budget_gaps.append(
                    {
                        "budget": name,
                        "reason": "actual spend is at or above the budget limit",
                    }
                )
            if not snapshot["limit_matches_config"]:
                budget_gaps.append(
                    {
                        "budget": name,
                        "reason": "live limit differs from configured limit",
                    }
                )
            for valid_key, reason in (
                ("budget_type_valid", "budget type is not COST"),
                ("time_unit_valid", "budget time unit is not MONTHLY"),
                ("currency_valid", "budget limit or actual spend is not USD"),
                (
                    "cost_filter_matches_config",
                    "live cost filters differ from the configured cluster-tag filter",
                ),
            ):
                if not snapshot[valid_key]:
                    budget_gaps.append({"budget": name, "reason": reason})
            if missing_thresholds:
                budget_gaps.append(
                    {
                        "budget": name,
                        "reason": "expected notification thresholds are missing",
                    }
                )
            if notification_email and not snapshot["configured_email_subscribed"]:
                budget_gaps.append(
                    {
                        "budget": name,
                        "reason": "configured email is not subscribed to every expected threshold",
                    }
                )
    except Exception as exc:
        check.status = CheckStatus.FAIL
        check.details["inspection_error"] = str(exc)
        check.remediation = (
            "Grant AWS Budgets read access for budget details, notifications, and "
            "subscribers, then rerun validation."
        )
    check.details["budget_snapshots"] = snapshots
    check.details["budget_configuration_gaps"] = budget_gaps
    if budget_gaps and check.status != CheckStatus.FAIL:
        check.status = CheckStatus.FAIL
        existing_remediation = str(check.remediation or "").strip()
        reconciliation = (
            "Reconcile the live budget limits, current spend, and notification "
            "subscriptions with the explicit DayEC configuration."
        )
        if existing_remediation.startswith("Budgets will be created:"):
            existing_remediation = "Create the missing budgets explicitly: " + (
                existing_remediation.removeprefix("Budgets will be created:").strip()
            )
        check.remediation = " ".join(
            part for part in (existing_remediation, reconciliation) if part
        )


def _describe_budget_notifications(
    client: Any,
    *,
    account_id: str,
    budget_name: str,
) -> list[dict[str, Any]]:
    notifications: list[dict[str, Any]] = []
    token = ""
    while True:
        request: dict[str, Any] = {
            "AccountId": account_id,
            "BudgetName": budget_name,
            "MaxResults": 100,
        }
        if token:
            request["NextToken"] = token
        response = client.describe_notifications_for_budget(**request)
        for notification in response.get("Notifications", []):
            subscribers = client.describe_subscribers_for_notification(
                AccountId=account_id,
                BudgetName=budget_name,
                Notification=notification,
                MaxResults=100,
            ).get("Subscribers", [])
            notifications.append(
                {
                    "notification_type": notification.get("NotificationType", ""),
                    "comparison_operator": notification.get("ComparisonOperator", ""),
                    "threshold": notification.get("Threshold"),
                    "threshold_type": notification.get("ThresholdType", ""),
                    "subscriber_addresses": sorted(
                        str(item.get("Address") or "") for item in subscribers
                    ),
                }
            )
        token = str(response.get("NextToken") or "")
        if not token:
            return notifications


def _optional_decimal(value: Any) -> Decimal | None:
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _check_cost_center_registry_readiness(aws_ctx: AWSContext) -> CheckResult:
    dynamodb = _regional_client(
        aws_ctx,
        "dynamodb",
        DEFAULT_COST_CENTER_HOME_REGION,
    )
    expected_schemas = {
        DEFAULT_COST_CENTER_TABLE: [
            {"AttributeName": "cost_center", "KeyType": "HASH"},
        ],
        DEFAULT_COST_CENTER_USAGE_TABLE: [
            {"AttributeName": "cost_center", "KeyType": "HASH"},
            {"AttributeName": "month", "KeyType": "RANGE"},
        ],
    }
    tables: dict[str, Any] = {}
    missing_tables: list[str] = []
    invalid_tables: dict[str, Any] = {}
    table_errors: dict[str, str] = {}
    for table_name, expected_schema in expected_schemas.items():
        try:
            table = dynamodb.describe_table(TableName=table_name).get("Table") or {}
        except Exception as exc:
            if _is_not_found_error(exc):
                missing_tables.append(table_name)
            else:
                table_errors[table_name] = str(exc)
            continue
        actual_schema = table.get("KeySchema") or []
        tables[table_name] = {
            "status": table.get("TableStatus", ""),
            "key_schema": actual_schema,
            "item_count": table.get("ItemCount"),
        }
        if table.get("TableStatus") != "ACTIVE" or actual_schema != expected_schema:
            invalid_tables[table_name] = tables[table_name]

    if DEFAULT_COST_CENTER_TABLE in table_errors:
        return CheckResult(
            id="cost_centers.registry_readiness",
            status=CheckStatus.FAIL,
            details={
                "home_region": DEFAULT_COST_CENTER_HOME_REGION,
                "tables": tables,
                "table_errors": table_errors,
            },
            remediation=("Grant DynamoDB DescribeTable access to the cost-center registry."),
        )

    details: dict[str, Any] = {
        "home_region": DEFAULT_COST_CENTER_HOME_REGION,
        "tables": tables,
        "missing_tables": missing_tables,
        "invalid_tables": invalid_tables,
        "table_errors": table_errors,
        "reserved_idle_present": False,
        "active_cost_centers": [],
        "eligible_active_cost_centers": [],
        "expired_active_cost_centers": [],
        "current_month": datetime.now(timezone.utc).strftime("%Y-%m"),
        "missing_usage": [],
        "stale_usage": [],
        "exhausted_usage": [],
        "usage_snapshots": {},
        "max_usage_age_hours": COST_CENTER_MAX_USAGE_AGE_HOURS,
    }
    if DEFAULT_COST_CENTER_TABLE in missing_tables:
        return CheckResult(
            id="cost_centers.registry_readiness",
            status=CheckStatus.FAIL,
            details=details,
            remediation=(
                "Create the missing global registry table with "
                "dyec cost-centers ensure-registry using an approved admin profile."
            ),
        )
    if DEFAULT_COST_CENTER_TABLE in invalid_tables:
        return CheckResult(
            id="cost_centers.registry_readiness",
            status=CheckStatus.FAIL,
            details=details,
            remediation=(
                "Repair the DayEC cost-center registry status or key schema; do not "
                "substitute alternate tables."
            ),
        )

    try:
        centers = list_cost_centers(
            dynamodb,
            table_name=DEFAULT_COST_CENTER_TABLE,
            status="all",
        )
    except Exception as exc:
        return CheckResult(
            id="cost_centers.registry_readiness",
            status=CheckStatus.FAIL,
            details={**details, "error": str(exc)},
            remediation=("Grant DynamoDB Scan access to the DayEC cost-center registry."),
        )

    center_by_name = {center.name: center for center in centers}
    details["reserved_idle_present"] = (
        center_by_name.get(RESERVED_IDLE_COST_CENTER) is not None
        and center_by_name[RESERVED_IDLE_COST_CENTER].status == "system"
    )
    active_names = sorted(center.name for center in centers if center.status == "active")
    details["active_cost_centers"] = active_names
    now = datetime.now(timezone.utc)
    eligible_active_names: list[str] = []
    for name in active_names:
        center = center_by_name[name]
        if cost_center_is_expired(center, now=now):
            details["expired_active_cost_centers"].append(
                {"cost_center": name, "active_until": center.active_until}
            )
        else:
            eligible_active_names.append(name)
    details["eligible_active_cost_centers"] = eligible_active_names

    if not details["reserved_idle_present"]:
        return CheckResult(
            id="cost_centers.registry_readiness",
            status=CheckStatus.FAIL,
            details=details,
            remediation=("Repair the reserved idle registry row so it exists with status system."),
        )
    telemetry_table_issue = ""
    if DEFAULT_COST_CENTER_USAGE_TABLE in missing_tables:
        telemetry_table_issue = "monthly usage telemetry table is missing"
    elif DEFAULT_COST_CENTER_USAGE_TABLE in invalid_tables:
        telemetry_table_issue = (
            "monthly usage telemetry table is not active or has an invalid schema"
        )
    elif DEFAULT_COST_CENTER_USAGE_TABLE in table_errors:
        telemetry_table_issue = table_errors[DEFAULT_COST_CENTER_USAGE_TABLE]
    if telemetry_table_issue:
        details["telemetry_error"] = telemetry_table_issue
        details["missing_usage"] = eligible_active_names
        return CheckResult(
            id="cost_centers.registry_readiness",
            status=CheckStatus.WARN,
            details=details,
            remediation=(
                "Restore the monthly usage telemetry table. This does not block Slurm admission."
            ),
        )

    try:
        usage_rows = list_cost_center_usage(
            dynamodb,
            month=details["current_month"],
            usage_table_name=DEFAULT_COST_CENTER_USAGE_TABLE,
        )
    except Exception as exc:
        details["telemetry_error"] = str(exc)
        return CheckResult(
            id="cost_centers.registry_readiness",
            status=CheckStatus.WARN,
            details=details,
            remediation=(
                "Restore DynamoDB Scan access to monthly cost-center usage telemetry. "
                "This does not block Slurm admission."
            ),
        )

    usage_by_name = {row.name: row for row in usage_rows}
    for name in eligible_active_names:
        usage = usage_by_name.get(name)
        if usage is None:
            details["missing_usage"].append(name)
            continue
        center = center_by_name[name]
        cap = center.monthly_cap_usd
        spend = usage.monthly_spend_usd
        snapshot = {
            "monthly_cap_usd": str(cap),
            "monthly_spend_usd": str(spend),
            "latest_processed_hour": usage.latest_processed_hour,
            "spend_below_cap": spend < cap,
        }
        max_age_hours = center.max_usage_age_hours or COST_CENTER_MAX_USAGE_AGE_HOURS
        snapshot["max_usage_age_hours"] = max_age_hours
        details["usage_snapshots"][name] = snapshot
        if spend >= cap:
            details["exhausted_usage"].append(
                {
                    "cost_center": name,
                    "monthly_spend_usd": str(spend),
                    "monthly_cap_usd": str(cap),
                }
            )
        try:
            latest = datetime.fromisoformat(
                usage.latest_processed_hour.replace("Z", "+00:00")
            ).astimezone(timezone.utc)
        except ValueError:
            details["stale_usage"].append(
                {"cost_center": name, "latest_processed_hour": usage.latest_processed_hour}
            )
            continue
        age_hours = (now - latest).total_seconds() / 3600.0
        snapshot["age_hours"] = round(age_hours, 2)
        if age_hours > max_age_hours:
            details["stale_usage"].append(
                {
                    "cost_center": name,
                    "latest_processed_hour": usage.latest_processed_hour,
                    "age_hours": round(age_hours, 2),
                    "max_usage_age_hours": max_age_hours,
                }
            )

    if details["missing_usage"] or details["stale_usage"] or details["exhausted_usage"]:
        return CheckResult(
            id="cost_centers.registry_readiness",
            status=CheckStatus.WARN,
            details=details,
            remediation=(
                "Refresh current-month usage telemetry or reconcile reported cap status. "
                "These telemetry conditions do not block Slurm admission."
            ),
        )
    if details["expired_active_cost_centers"]:
        details["lifecycle_notice"] = (
            "Expired active_until rows are normal lifecycle telemetry and do not block "
            "other cost centers. Extend active_until only when that cost center should "
            "accept submissions again."
        )
        return CheckResult(
            id="cost_centers.registry_readiness",
            status=CheckStatus.PASS,
            details=details,
        )
    return CheckResult(
        id="cost_centers.registry_readiness",
        status=CheckStatus.PASS,
        details=details,
    )


def _default_cur_config(aws_ctx: AWSContext) -> CurExportConfig:
    bucket = default_cur_export_bucket(aws_ctx.account_id)
    return CurExportConfig(
        account_id=aws_ctx.account_id,
        bucket=bucket,
        bucket_region=DEFAULT_BILLING_REGION,
        billing_region=DEFAULT_BILLING_REGION,
        athena_region=DEFAULT_BILLING_REGION,
        export_name=DEFAULT_CUR_EXPORT_NAME,
        s3_prefix=DEFAULT_CUR_EXPORT_PREFIX,
        database=DEFAULT_CUR_DATABASE,
        table=DEFAULT_CUR_TABLE,
        athena_output_s3_uri=(f"s3://{bucket}/{DEFAULT_CUR_EXPORT_PREFIX}/athena-results/"),
        cluster_tag_key="user_parallelcluster_cluster_name",
    ).normalized()


def _check_cur_export_readiness(aws_ctx: AWSContext) -> CheckResult:
    config = _default_cur_config(aws_ctx)
    s3 = _regional_client(aws_ctx, "s3", config.bucket_region)
    bcm = _regional_client(aws_ctx, "bcm-data-exports", config.billing_region)
    details: dict[str, Any] = {
        "billing_region": config.billing_region,
        "bucket": config.bucket,
        "bucket_region": None,
        "bucket_policy_valid": False,
        "export_name": config.export_name,
        "export_arn": "",
        "export_status": {},
        "export_definition_matches": False,
        "latest_execution": None,
        "schema_columns": [],
        "cluster_tag_key": config.cluster_tag_key,
    }
    missing: list[str] = []
    invalid: list[str] = []
    try:
        try:
            s3.head_bucket(Bucket=config.bucket)
            location = s3.get_bucket_location(Bucket=config.bucket).get("LocationConstraint")
            details["bucket_region"] = location or "us-east-1"
            policy = json.loads(s3.get_bucket_policy(Bucket=config.bucket).get("Policy") or "{}")
            expected = data_exports_bucket_policy_statement(config)
            details["bucket_policy_valid"] = any(
                _policy_statement_contains(statement, expected)
                for statement in policy.get("Statement", [])
                if isinstance(statement, dict)
            )
            if details["bucket_region"] != config.bucket_region:
                invalid.append("bucket_region")
            if not details["bucket_policy_valid"]:
                invalid.append("bucket_policy")
        except Exception as exc:
            if _is_not_found_error(exc):
                missing.append("s3_bucket_or_policy")
            else:
                raise

        export = _find_data_export_by_name(bcm, config.export_name)
        if export is None:
            missing.append("cur2_export")
        else:
            export_arn = str(export.get("ExportArn") or "")
            details["export_arn"] = export_arn
            details["export_status"] = _json_safe(export.get("ExportStatus") or {})
            if str((export.get("ExportStatus") or {}).get("StatusCode") or "") != "HEALTHY":
                invalid.append("export_status")
            current = bcm.get_export(ExportArn=export_arn).get("Export") or {}
            expected_definition = build_cur2_export_definition(config)
            details["export_definition"] = _json_safe(current)
            details["expected_export_definition"] = expected_definition
            details["export_definition_matches"] = _export_for_compare(
                current
            ) == _export_for_compare(expected_definition)
            if not details["export_definition_matches"]:
                invalid.append("export_definition")
            query = str((current.get("DataQuery") or {}).get("QueryStatement") or "")
            missing_columns = [column for column in CUR_EXPORT_COLUMNS if column not in query]
            details["missing_query_columns"] = missing_columns
            if DATA_EXPORTS_TABLE not in query or missing_columns:
                invalid.append("export_query")
            executions = _list_data_export_executions(bcm, export_arn)
            if executions:
                executions.sort(
                    key=lambda item: str(
                        (item.get("ExecutionStatus") or {}).get("CreatedAt") or ""
                    ),
                    reverse=True,
                )
                details["latest_execution"] = _json_safe(executions[0])
                latest_status = str(
                    (executions[0].get("ExecutionStatus") or {}).get("StatusCode") or ""
                )
                if latest_status != "DELIVERY_SUCCESS":
                    invalid.append("latest_export_execution")
            else:
                missing.append("export_execution")

        schema = get_cur2_schema(bcm)
        details["schema_columns"] = sorted(str(column.get("Name") or "") for column in schema)
    except Exception as exc:
        return CheckResult(
            id="cost_control.cur_export_readiness",
            status=CheckStatus.FAIL,
            details={**details, "missing": missing, "invalid": invalid, "error": str(exc)},
            remediation=(
                "Grant read access to the CUR S3 bucket and BCM Data Exports, then "
                "rerun validation. The validator does not create or update these resources."
            ),
        )

    details["missing"] = missing
    details["invalid"] = invalid
    if invalid:
        return CheckResult(
            id="cost_control.cur_export_readiness",
            status=CheckStatus.FAIL,
            details=details,
            remediation=(
                "Repair the existing CUR 2.0 bucket policy/export definition explicitly; "
                "do not silently adopt a different export."
            ),
        )
    if missing:
        return CheckResult(
            id="cost_control.cur_export_readiness",
            status=CheckStatus.FAIL,
            details=details,
            remediation=(
                "Provision the missing CUR 2.0 resources with "
                "dyec cost-centers ensure-cur-export using an approved admin profile."
            ),
        )
    return CheckResult(
        id="cost_control.cur_export_readiness",
        status=CheckStatus.PASS,
        details=details,
    )


def _check_cur_catalog_readiness(aws_ctx: AWSContext) -> CheckResult:
    config = _default_cur_config(aws_ctx)
    glue = _regional_client(aws_ctx, "glue", config.athena_region)
    bcm = _regional_client(aws_ctx, "bcm-data-exports", config.billing_region)
    billing_period = datetime.now(timezone.utc).strftime("%Y-%m")
    details: dict[str, Any] = {
        "region": config.athena_region,
        "database": config.database,
        "table": config.table,
        "billing_period": billing_period,
        "database_exists": False,
        "table_exists": False,
        "partition_exists": False,
        "managed": False,
        "schema_columns": [],
        "table_contract_matches": False,
        "partition_contract_matches": False,
    }
    missing: list[str] = []
    invalid: list[str] = []
    try:
        expected_schema = get_cur2_schema(bcm)
        expected_table = glue_table_input(config, schema=expected_schema)
        try:
            glue.get_database(Name=config.database)
            details["database_exists"] = True
        except Exception as exc:
            if _is_not_found_error(exc):
                missing.append("database")
            else:
                raise
        if details["database_exists"]:
            try:
                table = (
                    glue.get_table(
                        DatabaseName=config.database,
                        Name=config.table,
                    ).get("Table")
                    or {}
                )
                details["table_exists"] = True
                details["managed"] = (table.get("Parameters") or {}).get("dayec:managed") == "true"
                details["schema_columns"] = sorted(
                    str(column.get("Name") or "")
                    for column in (table.get("StorageDescriptor") or {}).get("Columns", [])
                )
                details["table_location"] = (table.get("StorageDescriptor") or {}).get(
                    "Location", ""
                )
                details["expected_table_location"] = (
                    expected_table.get("StorageDescriptor") or {}
                ).get("Location", "")
                details["table_contract_matches"] = _glue_table_contract_matches(
                    table,
                    expected_table,
                )
                if not details["table_contract_matches"]:
                    invalid.append("table_contract")
            except Exception as exc:
                if _is_not_found_error(exc):
                    missing.append("table")
                else:
                    raise
        if details["table_exists"]:
            try:
                partition = (
                    glue.get_partition(
                        DatabaseName=config.database,
                        TableName=config.table,
                        PartitionValues=[billing_period],
                    ).get("Partition")
                    or {}
                )
                details["partition_exists"] = True
                expected_partition_location = billing_period_data_location(
                    config,
                    billing_period,
                )
                actual_partition_location = (partition.get("StorageDescriptor") or {}).get(
                    "Location", ""
                )
                details["partition_location"] = actual_partition_location
                details["expected_partition_location"] = expected_partition_location
                details["partition_contract_matches"] = (
                    partition.get("Values") == [billing_period]
                    and (partition.get("Parameters") or {}).get("dayec:managed") == "true"
                    and actual_partition_location == expected_partition_location
                    and _glue_storage_descriptor_matches(
                        partition.get("StorageDescriptor") or {},
                        expected_table.get("StorageDescriptor") or {},
                        compare_location=False,
                    )
                )
                if not details["partition_contract_matches"]:
                    invalid.append("partition_contract")
            except Exception as exc:
                if _is_not_found_error(exc):
                    missing.append("current_month_partition")
                else:
                    raise
    except Exception as exc:
        return CheckResult(
            id="cost_control.cur_catalog_readiness",
            status=CheckStatus.FAIL,
            details={
                **details,
                "missing": missing,
                "invalid": invalid,
                "error": str(exc),
            },
            remediation=(
                "Grant Glue GetDatabase, GetTable, and GetPartition for the DayEC CUR catalog."
            ),
        )

    details["missing"] = missing
    details["invalid"] = invalid
    if invalid:
        return CheckResult(
            id="cost_control.cur_catalog_readiness",
            status=CheckStatus.FAIL,
            details=details,
            remediation=(
                "The CUR Glue table or current-month partition differs from the exact "
                "managed DayEC schema and S3-location contract; repair it explicitly."
            ),
        )
    if missing:
        return CheckResult(
            id="cost_control.cur_catalog_readiness",
            status=CheckStatus.FAIL,
            details=details,
            remediation=(
                "Create the missing Glue database, table, or current-month partition with "
                "dyec cost-centers ensure-cur-export."
            ),
        )
    return CheckResult(
        id="cost_control.cur_catalog_readiness",
        status=CheckStatus.PASS,
        details=details,
    )


def _glue_table_contract_matches(
    actual: dict[str, Any],
    expected: dict[str, Any],
) -> bool:
    expected_parameters = expected.get("Parameters") or {}
    actual_parameters = actual.get("Parameters") or {}
    return (
        actual.get("Name") == expected.get("Name")
        and actual.get("TableType") == expected.get("TableType")
        and all(actual_parameters.get(key) == value for key, value in expected_parameters.items())
        and actual.get("PartitionKeys") == expected.get("PartitionKeys")
        and _glue_storage_descriptor_matches(
            actual.get("StorageDescriptor") or {},
            expected.get("StorageDescriptor") or {},
        )
    )


def _glue_storage_descriptor_matches(
    actual: dict[str, Any],
    expected: dict[str, Any],
    *,
    compare_location: bool = True,
) -> bool:
    keys = (
        "Columns",
        "InputFormat",
        "OutputFormat",
        "SerdeInfo",
        "StoredAsSubDirectories",
    )
    if compare_location and actual.get("Location") != expected.get("Location"):
        return False
    return all(actual.get(key) == expected.get(key) for key in keys)


def _check_athena_readiness(aws_ctx: AWSContext) -> CheckResult:
    athena = _regional_client(aws_ctx, "athena", DEFAULT_BILLING_REGION)
    try:
        workgroup = athena.get_work_group(WorkGroup="primary").get("WorkGroup") or {}
    except Exception as exc:
        return CheckResult(
            id="cost_control.athena_readiness",
            status=CheckStatus.FAIL,
            details={
                "region": DEFAULT_BILLING_REGION,
                "workgroup": "primary",
                "query_started": False,
                "error": str(exc),
            },
            remediation=(
                "Grant athena:GetWorkGroup on the primary workgroup. No query was started."
            ),
        )
    details = {
        "region": DEFAULT_BILLING_REGION,
        "workgroup": "primary",
        "state": workgroup.get("State", ""),
        "query_started": False,
    }
    if workgroup.get("State") != "ENABLED":
        return CheckResult(
            id="cost_control.athena_readiness",
            status=CheckStatus.FAIL,
            details=details,
            remediation="Enable the explicit Athena primary workgroup used by CUR allocation.",
        )
    return CheckResult(
        id="cost_control.athena_readiness",
        status=CheckStatus.PASS,
        details=details,
    )


def check_slurm_accounting_readiness(
    aws_ctx: AWSContext,
    cfg: Any,
) -> CheckResult:
    enabled = _strict_bool_config(cfg, "slurm_accounting_enabled", False)
    create_if_missing = _strict_bool_config(cfg, "slurm_accounting_create_db", False)
    details: dict[str, Any] = {
        "configured": enabled,
        "create_if_missing": create_if_missing,
        "stack_name": "",
        "status": "",
    }
    if not enabled:
        return CheckResult(
            id="slurm_accounting.readiness",
            status=CheckStatus.PASS,
            details=details,
        )

    baseline_name = derive_stack_name(aws_ctx.region_az)
    outputs = get_stack_outputs(aws_ctx.client("cloudformation"), baseline_name)
    if not outputs.vpc_id:
        return CheckResult(
            id="slurm_accounting.readiness",
            status=CheckStatus.FAIL,
            details={**details, "baseline_stack": baseline_name},
            remediation=(
                "The enabled Slurm-accounting configuration requires a readable baseline "
                "stack with a VPC output."
            ),
        )

    stack_name = _effective_config_value(cfg, "slurm_accounting_stack_name", "")
    details["stack_name"] = stack_name or derive_slurm_accounting_stack_name(aws_ctx.region_az)
    try:
        matches = discover_slurm_accounting_dbs(
            aws_ctx,
            region_az=aws_ctx.region_az,
            vpc_id=outputs.vpc_id,
            stack_name=stack_name,
        )
    except SlurmAccountingError as exc:
        return CheckResult(
            id="slurm_accounting.readiness",
            status=CheckStatus.FAIL,
            details={**details, "vpc_id": outputs.vpc_id, "error": str(exc)},
            remediation="Repair the explicit DayEC Slurm-accounting stack contract.",
        )
    if not matches:
        status = CheckStatus.WARN if create_if_missing else CheckStatus.FAIL
        return CheckResult(
            id="slurm_accounting.readiness",
            status=status,
            details={**details, "vpc_id": outputs.vpc_id, "found": False},
            remediation=(
                "No matching accounting stack exists. Create it explicitly with "
                "dyec slurm-accounting ensure before a create flow that does not allow creation."
            ),
        )
    db = matches[0]
    details.update(
        {
            "found": True,
            "stack_name": db.stack_name,
            "status": db.status,
            "instance_id": db.instance_id,
            "client_security_group_id": db.client_security_group_id,
            "password_secret_arn": db.password_secret_arn,
        }
    )
    try:
        if not db.instance_id:
            raise SlurmAccountingError(
                "healthy accounting stack has no AccountingInstanceId output"
            )
        reservations = (
            aws_ctx.client("ec2")
            .describe_instances(InstanceIds=[db.instance_id])
            .get("Reservations", [])
        )
        instances = [
            instance
            for reservation in reservations
            for instance in reservation.get("Instances", [])
        ]
        if len(instances) != 1:
            raise SlurmAccountingError(
                f"expected one accounting EC2 instance, found {len(instances)}"
            )
        details["instance_state"] = (instances[0].get("State") or {}).get("Name", "")
        security_groups = (
            aws_ctx.client("ec2")
            .describe_security_groups(GroupIds=[db.client_security_group_id])
            .get("SecurityGroups", [])
        )
        details["client_security_group_exists"] = len(security_groups) == 1
        secret = aws_ctx.client("secretsmanager").describe_secret(SecretId=db.password_secret_arn)
        details["password_secret_exists"] = bool(secret.get("ARN") or secret.get("Name"))
    except Exception as exc:
        return CheckResult(
            id="slurm_accounting.readiness",
            status=CheckStatus.FAIL,
            details={**details, "error": str(exc), "secret_value_read": False},
            remediation=(
                "Grant read access to the accounting EC2 instance, client security "
                "group, and secret metadata, and repair any missing stack resource."
            ),
        )
    if (
        details["instance_state"] != "running"
        or not details["client_security_group_exists"]
        or not details["password_secret_exists"]
    ):
        return CheckResult(
            id="slurm_accounting.readiness",
            status=CheckStatus.FAIL,
            details={**details, "secret_value_read": False},
            remediation=(
                "Restore the accounting EC2 instance to running and ensure its client "
                "security group and password secret still exist."
            ),
        )
    details["secret_value_read"] = False
    return CheckResult(
        id="slurm_accounting.readiness",
        status=CheckStatus.PASS,
        details=details,
    )


def simulate_required_permissions(
    aws_ctx: AWSContext,
    iam_client: Any,
    *,
    cfg: Any | None = None,
) -> list[CheckResult]:
    """Use IAM policy simulation to validate Daylily and ParallelCluster actions."""

    groups = _permission_groups(aws_ctx, cfg=cfg)
    if aws_ctx.iam_username == "root":
        return [
            CheckResult(
                id=f"iam.simulation.{group.check_id}",
                status=CheckStatus.WARN,
                details={
                    "principal_arn": aws_ctx.caller_arn,
                    "actions": list(group.actions),
                    "resources": list(group.resources),
                    "denied_actions": None,
                    "implicit_root_access": True,
                    "simulation_performed": False,
                    "unverified_boundaries": [
                        "AWS Organizations service control policies",
                        "AWS Organizations resource control policies",
                        "resource-based explicit denies",
                    ],
                },
                remediation=(
                    "IAM does not accept an account-root ARN as a policy-simulation source. "
                    "Run this validator with the actual non-root operator role/user to prove "
                    "these actions, or have an AWS administrator verify the listed SCP, RCP, "
                    "and resource-policy boundaries."
                ),
            )
            for group in groups
        ]

    checks: list[CheckResult] = []
    principal_arn = _simulation_source_arn(aws_ctx.caller_arn, aws_ctx.account_id)
    for group in groups:
        try:
            results = _simulate_group(iam_client, principal_arn, group)
        except Exception as exc:
            checks.append(
                CheckResult(
                    id=f"iam.simulation.{group.check_id}",
                    status=CheckStatus.FAIL,
                    details={
                        "principal_arn": principal_arn,
                        "group": group.check_id,
                        "error": str(exc),
                    },
                    remediation=(
                        "Grant iam:SimulatePrincipalPolicy to this profile, or "
                        "ask an AWS admin to run the gap analysis with a profile "
                        "that can simulate the operator principal."
                    ),
                )
            )
            continue

        denied = [
            result for result in results if str(result.get("EvalDecision", "")).lower() != "allowed"
        ]
        details = {
            "principal_arn": principal_arn,
            "actions": list(group.actions),
            "resources": list(group.resources),
            "denied_actions": sorted({str(result.get("EvalActionName", "")) for result in denied}),
            "decisions": [
                {
                    "action": result.get("EvalActionName"),
                    "resource": result.get("EvalResourceName", "*"),
                    "decision": result.get("EvalDecision"),
                }
                for result in results
            ],
        }
        if denied:
            checks.append(
                CheckResult(
                    id=f"iam.simulation.{group.check_id}",
                    status=CheckStatus.FAIL,
                    details=details,
                    remediation=(
                        "Attach or update Daylily AWS policies so the principal "
                        f"can perform {group.label}. Denied actions: "
                        + ", ".join(details["denied_actions"])
                    ),
                )
            )
        else:
            checks.append(
                CheckResult(
                    id=f"iam.simulation.{group.check_id}",
                    status=CheckStatus.PASS,
                    details=details,
                )
            )
    return checks


def run_quota_checks(
    aws_ctx: AWSContext,
    cfg: Any,
    *,
    config_path: str,
) -> list[CheckResult]:
    """Run quota checks, including rendered ParallelCluster demand."""

    max_8i = _int_config_value(cfg, "max_count_8I", 1)
    max_96i_nvme = _required_int_config_value(cfg, "max_count_96I_NVME")
    max_128i = _int_config_value(cfg, "max_count_128I", 1)
    max_192i = _int_config_value(cfg, "max_count_192I", 1)
    max_384i = _int_config_value(cfg, "max_count_384I", 1)
    checks = [
        check
        for check in check_all_quotas(
            aws_ctx,
            max_count_8i=max_8i,
            max_count_96i_nvme=max_96i_nvme,
            max_count_128i=max_128i,
            max_count_192i=max_192i,
            max_count_384i=max_384i,
            non_interactive=True,
        )
        if check.id not in {"quota.ondemand_vcpu", "quota.spot_vcpu"}
    ]
    baseline_check = _check_baseline_stack_presence(aws_ctx)
    checks.append(baseline_check)
    _enrich_network_quota_headroom(
        checks,
        aws_ctx,
        baseline_ready=baseline_check.status == CheckStatus.PASS,
    )
    accounting_shape, accounting_vcpus, accounting_gp3_gib = _check_slurm_accounting_shape(
        aws_ctx, cfg
    )
    checks.append(accounting_shape)
    checks.extend(_check_cost_control_quotas(aws_ctx, cfg))

    try:
        rendered_yaml, template_path, cluster_name = render_effective_cluster_yaml(
            cfg,
            aws_ctx,
        )
        shape = extract_cluster_shape(
            rendered_yaml,
            aws_ctx,
            cluster_name=cluster_name,
            template_path=str(template_path),
        )
    except Exception as exc:
        checks.append(
            CheckResult(
                id="quota.cluster_shape",
                status=CheckStatus.FAIL,
                details={"config_path": config_path, "error": str(exc)},
                remediation=(
                    "Fix the selected Daylily config and ParallelCluster template "
                    "so the validator can render and parse the effective cluster shape."
                ),
            )
        )
        return checks

    checks.append(
        CheckResult(
            id="quota.cluster_shape",
            status=CheckStatus.PASS,
            details=shape.to_details(),
        )
    )
    checks.extend(
        _check_rendered_vcpu_quotas(
            aws_ctx,
            shape,
            additional_ondemand_vcpus=accounting_vcpus,
            additional_ondemand_instance_type=(
                _effective_config_value(
                    cfg,
                    "slurm_accounting_instance_type",
                    "t4g.micro",
                )
                if accounting_vcpus
                else ""
            ),
        )
    )
    checks.append(_check_instance_type_offerings(aws_ctx, shape))
    checks.append(_check_spot_market_signal(aws_ctx, shape))
    checks.extend(
        _check_storage_quotas(
            aws_ctx,
            shape,
            additional_gp3_gib=accounting_gp3_gib,
        )
    )
    return checks


def render_effective_cluster_yaml(cfg: Any, aws_ctx: AWSContext) -> tuple[str, Path, str]:
    """Render the configured ParallelCluster template without writing files."""

    cluster_name = _effective_config_value(cfg, "cluster_name", "prod") or "prod"
    template_value = _explicit_cluster_template_yaml(cfg)
    if not template_value:
        template_value = str(
            az_cluster_template_relative_path(
                DEFAULT_CREATE_CLUSTER_TYPE,
                aws_ctx.region_az,
            )
        )
    template_path = _resolve_data_path(template_value)
    substitutions = _validation_substitutions(cfg, aws_ctx, cluster_name)
    template_text = template_path.read_text(encoding="utf-8")
    return (
        render_template(
            template_text,
            substitutions,
            required_keys=REQUIRED_KEYS,
        ),
        template_path,
        cluster_name,
    )


def _explicit_cluster_template_yaml(cfg: Any) -> str:
    triplet = cfg.ephemeral_cluster.config.get("cluster_template_yaml")
    if triplet is None:
        return ""
    return str(resolve_value(triplet) or "").strip()


def extract_cluster_shape(
    rendered_yaml: str,
    aws_ctx: AWSContext,
    *,
    cluster_name: str,
    template_path: str,
) -> ClusterShape:
    """Parse rendered ParallelCluster YAML and compute demand."""

    payload = yaml.safe_load(rendered_yaml) or {}
    if not isinstance(payload, dict):
        raise ValueError("Rendered cluster template is not a YAML mapping.")

    headnode = payload.get("HeadNode", {}) or {}
    if not isinstance(headnode, dict):
        raise ValueError("Rendered cluster template missing HeadNode mapping.")
    headnode_instance_type = str(headnode.get("InstanceType") or "").strip()
    if not headnode_instance_type:
        raise ValueError("Rendered cluster template missing HeadNode.InstanceType.")
    root_volume = (
        ((headnode.get("LocalStorage") or {}).get("RootVolume") or {})
        if isinstance(headnode.get("LocalStorage") or {}, dict)
        else {}
    )
    headnode_root_volume_type = str(root_volume.get("VolumeType") or "").strip()
    headnode_root_volume_gib = _coerce_positive_int(
        root_volume.get("Size", 0),
        "HeadNode.LocalStorage.RootVolume.Size",
    )

    shared_storage = payload.get("SharedStorage") or []
    fsx_storage_gib = 0
    fsx_deployment_type = ""
    fsx_storage_type = ""
    fsx_read_cache_gib = 0
    fsx_throughput_capacity = 0
    if isinstance(shared_storage, list):
        for storage in shared_storage:
            if not isinstance(storage, dict):
                continue
            if str(storage.get("StorageType") or "") != "FsxLustre":
                continue
            fsx_settings = storage.get("FsxLustreSettings") or {}
            if not isinstance(fsx_settings, dict):
                continue
            fsx_deployment_type = str(fsx_settings.get("DeploymentType") or "").strip()
            fsx_storage_type = str(fsx_settings.get("StorageType") or "SSD").strip().upper()
            storage_capacity = fsx_settings.get("StorageCapacity", 0)
            if fsx_storage_type == "INTELLIGENT_TIERING":
                fsx_storage_gib = _coerce_nonnegative_int(
                    storage_capacity,
                    "SharedStorage.FsxLustreSettings.StorageCapacity",
                )
            else:
                fsx_storage_gib = _coerce_positive_int(
                    storage_capacity,
                    "SharedStorage.FsxLustreSettings.StorageCapacity",
                )
            read_cache = fsx_settings.get("DataReadCacheConfiguration") or {}
            if not isinstance(read_cache, dict):
                raise ValueError(
                    "SharedStorage.FsxLustreSettings.DataReadCacheConfiguration must be a mapping."
                )
            fsx_read_cache_gib = _coerce_nonnegative_int(
                read_cache.get("SizeGiB", 0),
                "SharedStorage.FsxLustreSettings.DataReadCacheConfiguration.SizeGiB",
            )
            fsx_throughput_capacity = _coerce_nonnegative_int(
                fsx_settings.get("ThroughputCapacity", 0),
                "SharedStorage.FsxLustreSettings.ThroughputCapacity",
            )
            break

    queues = ((payload.get("Scheduling") or {}).get("SlurmQueues")) or []
    if not isinstance(queues, list):
        raise ValueError("Rendered cluster template Scheduling.SlurmQueues is not a list.")

    instance_types = {headnode_instance_type}
    raw_resources: list[tuple[str, str, str, int, tuple[str, ...]]] = []
    for queue in queues:
        if not isinstance(queue, dict):
            continue
        queue_name = str(queue.get("Name") or "").strip()
        capacity_type = str(queue.get("CapacityType") or "ONDEMAND").strip().upper()
        compute_resources = queue.get("ComputeResources") or []
        if not isinstance(compute_resources, list):
            continue
        for resource in compute_resources:
            if not isinstance(resource, dict):
                continue
            resource_name = str(resource.get("Name") or "").strip()
            max_count = _coerce_nonnegative_int(
                resource.get("MaxCount", 0),
                f"Scheduling.SlurmQueues.{queue_name}.{resource_name}.MaxCount",
            )
            instances = resource.get("Instances") or []
            resource_instance_types: list[str] = []
            if isinstance(instances, list):
                for item in instances:
                    if isinstance(item, dict):
                        instance_type = str(item.get("InstanceType") or "").strip()
                        if instance_type:
                            resource_instance_types.append(instance_type)
                            instance_types.add(instance_type)
            raw_resources.append(
                (
                    queue_name,
                    capacity_type,
                    resource_name,
                    max_count,
                    tuple(resource_instance_types),
                )
            )

    vcpus_by_type = _describe_instance_vcpus(aws_ctx.client("ec2"), instance_types)
    compute_demands: list[ComputeResourceDemand] = []
    for queue_name, capacity_type, resource_name, max_count, resource_types in raw_resources:
        if not resource_types:
            max_vcpus = 0
        else:
            max_vcpus = max(vcpus_by_type.get(instance_type, 0) for instance_type in resource_types)
        compute_demands.append(
            ComputeResourceDemand(
                queue=queue_name,
                capacity_type=capacity_type,
                name=resource_name,
                max_count=max_count,
                instance_types=resource_types,
                max_vcpus_per_instance=max_vcpus,
                demand_vcpus=max_count * max_vcpus,
            )
        )

    return ClusterShape(
        cluster_name=cluster_name,
        template_path=template_path,
        headnode_instance_type=headnode_instance_type,
        headnode_vcpus=vcpus_by_type[headnode_instance_type],
        headnode_root_volume_type=headnode_root_volume_type,
        headnode_root_volume_gib=headnode_root_volume_gib,
        fsx_deployment_type=fsx_deployment_type,
        fsx_storage_type=fsx_storage_type,
        fsx_storage_gib=fsx_storage_gib,
        fsx_read_cache_gib=fsx_read_cache_gib,
        fsx_throughput_capacity=fsx_throughput_capacity,
        compute_resources=tuple(compute_demands),
        vcpus_by_instance_type=vcpus_by_type,
    )


def write_gap_analysis(report: AwsValidationReport, path: Path) -> None:
    """Write an answer-first permissions, readiness, and quota report."""

    path = Path(path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    gaps = [check for check in report.checks if check.status != CheckStatus.PASS]
    passing = [check for check in report.checks if check.status == CheckStatus.PASS]
    overall = "SATISFIED" if report.ready else "NOT SATISFIED"
    area_counts: dict[str, Counter[str]] = {}
    for check in report.checks:
        area_counts.setdefault(_report_area(check.id), Counter())[check.status.value] += 1
    lines = [
        "# Daylily AWS Permissions And Quotas Validation Report",
        "",
        "## Outcome",
        "",
        f"- Overall: **{overall}**",
        f"- Satisfied checks: {len(passing)} / {len(report.checks)}",
        f"- Unsatisfied or unknown checks: {len(gaps)} / {len(report.checks)}",
        "",
        "## Context",
        "",
        f"- Mode: `{report.mode}`",
        f"- AWS profile: `{report.aws_profile}`",
        f"- Account: `{report.account_id}`",
        f"- Principal: `{report.caller_arn}`",
        f"- Region: `{report.region}`",
        f"- Region AZ: `{report.region_az}`",
    ]
    if report.config_path:
        lines.append(f"- Config: `{report.config_path}`")
    lines.extend(
        [
            "",
            "## Summary",
            "",
            f"- PASS: {report.summary.get('PASS', 0)}",
            f"- WARN: {report.summary.get('WARN', 0)}",
            f"- FAIL: {report.summary.get('FAIL', 0)}",
            "",
            "## Area Summary",
            "",
            "| Area | Satisfied | Unknown | Not satisfied | Total | Outcome |",
            "|---|---:|---:|---:|---:|---|",
        ]
    )
    for area, counts in area_counts.items():
        total = sum(counts.values())
        if counts[CheckStatus.FAIL.value]:
            area_outcome = "NOT SATISFIED"
        elif counts[CheckStatus.WARN.value]:
            area_outcome = "UNKNOWN"
        else:
            area_outcome = "SATISFIED"
        lines.append(
            f"| {area} | {counts[CheckStatus.PASS.value]} | "
            f"{counts[CheckStatus.WARN.value]} | {counts[CheckStatus.FAIL.value]} | "
            f"{total} | {area_outcome} |"
        )
    lines.extend(
        [
            "",
            "## Results Matrix",
            "",
            "| Area | Check | Result | Status |",
            "|---|---|---|---|",
        ]
    )
    for check in report.checks:
        result = {
            CheckStatus.PASS: "SATISFIED",
            CheckStatus.WARN: "UNKNOWN",
            CheckStatus.FAIL: "NOT SATISFIED",
        }[check.status]
        lines.append(
            f"| {_report_area(check.id)} | `{check.id}` | {result} | {check.status.value} |"
        )
    lines.append("")
    if not gaps:
        lines.extend(["No permission or quota gaps were detected.", ""])
    else:
        lines.extend(["## Required Admin Follow-Up", ""])
        for check in gaps:
            lines.extend(
                [
                    f"### {check.id} - {check.status.value}",
                    "",
                    check.remediation
                    or "Review this validation result and correct the account setup.",
                    "",
                    "```json",
                    json.dumps(_json_safe(check.details), indent=2, sort_keys=True),
                    "```",
                    "",
                ]
            )
    lines.extend(["## Passing Validation Checks", ""])
    if not passing:
        lines.extend(["No passing validation checks were recorded.", ""])
    else:
        for check in passing:
            lines.extend(
                [
                    f"### {check.id} - {check.status.value}",
                    "",
                    "```json",
                    json.dumps(_json_safe(check.details), indent=2, sort_keys=True),
                    "```",
                    "",
                ]
            )
    path.write_text("\n".join(lines), encoding="utf-8")


def _permission_groups(
    aws_ctx: AWSContext,
    *,
    cfg: Any | None = None,
) -> tuple[PermissionGroup, ...]:
    account = aws_ctx.account_id
    region = aws_ctx.region
    partition = _aws_partition(aws_ctx.caller_arn)
    cluster_name = (
        _effective_config_value(cfg, "cluster_name", "prod") if cfg is not None else "prod"
    ) or "prod"
    cur_bucket = default_cur_export_bucket(account)
    service_linked_services = (
        "spot.amazonaws.com",
        "fsx.amazonaws.com",
        "s3.data-source.lustre.fsx.amazonaws.com",
        "imagebuilder.amazonaws.com",
        "ec2.amazonaws.com",
        "lambda.amazonaws.com",
        "budgets.amazonaws.com",
    )
    groups: list[PermissionGroup] = [
        PermissionGroup(
            "iam_core",
            "IAM inspection and role/profile management",
            (
                "iam:ListPolicies",
                "iam:GetPolicy",
                "iam:GetPolicyVersion",
                "iam:ListAttachedUserPolicies",
                "iam:ListGroupsForUser",
                "iam:ListAttachedGroupPolicies",
                "iam:ListRoles",
                "iam:ListInstanceProfiles",
                "iam:GetAccountSummary",
                "iam:GetRole",
                "iam:CreateRole",
                "iam:DeleteRole",
                "iam:CreateInstanceProfile",
                "iam:DeleteInstanceProfile",
                "iam:AddRoleToInstanceProfile",
                "iam:RemoveRoleFromInstanceProfile",
                "iam:AttachRolePolicy",
                "iam:DetachRolePolicy",
                "iam:PutRolePolicy",
                "iam:DeleteRolePolicy",
                "iam:TagRole",
                "iam:UntagRole",
                "iam:SimulatePrincipalPolicy",
            ),
        ),
        PermissionGroup(
            "iam_pass_role",
            "IAM PassRole for ParallelCluster and scheduler roles",
            ("iam:PassRole",),
            (f"arn:aws:iam::{account}:role/daylily-validation-role",),
        ),
        PermissionGroup(
            "cloudformation",
            "CloudFormation stack lifecycle",
            (
                "cloudformation:DescribeStacks",
                "cloudformation:ListStacks",
                "cloudformation:CreateStack",
                "cloudformation:UpdateStack",
                "cloudformation:DeleteStack",
                "cloudformation:DescribeStackEvents",
            ),
        ),
        PermissionGroup(
            "ec2_network_compute",
            "EC2, VPC, security-group, and instance lifecycle",
            (
                "ec2:DescribeAvailabilityZones",
                "ec2:DescribeInstanceTypes",
                "ec2:DescribeInstanceTypeOfferings",
                "ec2:DescribeSpotPriceHistory",
                "ec2:DescribeSpotInstanceRequests",
                "ec2:DescribeSubnets",
                "ec2:DescribeVpcs",
                "ec2:DescribeInstances",
                "ec2:DescribeImages",
                "ec2:DescribeSecurityGroups",
                "ec2:DescribeNetworkInterfaces",
                "ec2:DescribeRouteTables",
                "ec2:DescribeVolumes",
                "ec2:DescribeAddresses",
                "ec2:DescribeInternetGateways",
                "ec2:DescribeNatGateways",
                "ec2:CreateVpc",
                "ec2:DeleteVpc",
                "ec2:CreateSubnet",
                "ec2:DeleteSubnet",
                "ec2:CreateInternetGateway",
                "ec2:AttachInternetGateway",
                "ec2:DetachInternetGateway",
                "ec2:CreateNatGateway",
                "ec2:DeleteNatGateway",
                "ec2:AllocateAddress",
                "ec2:ReleaseAddress",
                "ec2:CreateSecurityGroup",
                "ec2:AuthorizeSecurityGroupIngress",
                "ec2:AuthorizeSecurityGroupEgress",
                "ec2:RunInstances",
                "ec2:TerminateInstances",
                "ec2:CreateTags",
                "ec2:DeleteTags",
            ),
        ),
        PermissionGroup(
            "autoscaling_elb",
            "Auto Scaling and load-balancer resources used by ParallelCluster",
            (
                "autoscaling:DescribeAutoScalingGroups",
                "autoscaling:CreateAutoScalingGroup",
                "autoscaling:DeleteAutoScalingGroup",
                "elasticloadbalancing:DescribeLoadBalancers",
                "elasticloadbalancing:CreateLoadBalancer",
                "elasticloadbalancing:DeleteLoadBalancer",
            ),
        ),
        PermissionGroup(
            "fsx",
            "FSx for Lustre lifecycle and repository tasks",
            (
                "fsx:DescribeFileSystems",
                "fsx:CreateFileSystem",
                "fsx:DeleteFileSystem",
                "fsx:CreateDataRepositoryAssociation",
                "fsx:DescribeDataRepositoryAssociations",
                "fsx:DeleteDataRepositoryAssociation",
                "fsx:CreateDataRepositoryTask",
                "fsx:DescribeDataRepositoryTasks",
                "fsx:TagResource",
            ),
        ),
        PermissionGroup(
            "s3",
            "S3 bucket and object access for the FSx data repository",
            (
                "s3:ListAllMyBuckets",
                "s3:GetBucketLocation",
                "s3:CreateBucket",
                "s3:GetBucketPolicy",
                "s3:PutBucketPolicy",
                "s3:ListBucket",
                "s3:GetObject",
                "s3:PutObject",
                "s3:DeleteObject",
            ),
        ),
        PermissionGroup(
            "ssm",
            "Systems Manager document, command, and Session Manager access",
            (
                "ssm:GetDocument",
                "ssm:GetParameter",
                "ssm:GetParameters",
                "ssm:DescribeInstanceInformation",
                "ssm:StartSession",
                "ssm:TerminateSession",
                "ssm:DescribeSessions",
                "ssm:SendCommand",
                "ssm:GetCommandInvocation",
            ),
        ),
        PermissionGroup(
            "service_quotas",
            "Service Quotas reads used by validation",
            (
                "servicequotas:GetServiceQuota",
                "servicequotas:ListServiceQuotas",
                "servicequotas:ListAWSDefaultServiceQuotas",
            ),
        ),
        PermissionGroup(
            "budgets",
            "Budgets and cost-tag enforcement",
            (
                "budgets:ViewBudget",
                "budgets:ModifyBudget",
                "billing:GetBillingViewData",
            ),
        ),
        PermissionGroup(
            "cost_explorer_reports",
            "Cost Explorer and allocation-tag reporting",
            (
                "ce:GetCostAndUsage",
                "ce:GetCostAndUsageWithResources",
                "ce:GetDimensionValues",
                "ce:GetTags",
                "ce:ListCostAllocationTags",
                "ce:DescribeCostCategoryDefinition",
                "ce:ListCostCategoryDefinitions",
                "tag:GetResources",
                "tag:GetTagKeys",
                "tag:GetTagValues",
            ),
        ),
        PermissionGroup(
            "dynamodb_cost_center_list",
            "global cost-center table discovery",
            ("dynamodb:ListTables",),
        ),
        PermissionGroup(
            "dynamodb_cost_centers",
            "global cost-center registry and monthly usage snapshots",
            (
                "dynamodb:DescribeTable",
                "dynamodb:CreateTable",
                "dynamodb:GetItem",
                "dynamodb:PutItem",
                "dynamodb:Scan",
            ),
            (
                f"arn:{partition}:dynamodb:{DEFAULT_COST_CENTER_HOME_REGION}:"
                f"{account}:table/{DEFAULT_COST_CENTER_TABLE}",
                f"arn:{partition}:dynamodb:{DEFAULT_COST_CENTER_HOME_REGION}:"
                f"{account}:table/{DEFAULT_COST_CENTER_USAGE_TABLE}",
            ),
        ),
        PermissionGroup(
            "cur_data_exports_list",
            "CUR 2.0 Data Exports discovery",
            (
                "bcm-data-exports:ListExports",
                "bcm-data-exports:ListTables",
            ),
        ),
        PermissionGroup(
            "cur_data_exports_table",
            "CUR 2.0 table schema inspection",
            ("bcm-data-exports:GetTable",),
            (
                f"arn:{partition}:bcm-data-exports:{DEFAULT_BILLING_REGION}:"
                f"{account}:table/{DATA_EXPORTS_TABLE}",
            ),
        ),
        PermissionGroup(
            "cur_data_exports_create",
            "CUR 2.0 creation across the export and source table",
            ("bcm-data-exports:CreateExport",),
            (
                f"arn:{partition}:bcm-data-exports:{DEFAULT_BILLING_REGION}:{account}:export/*",
                f"arn:{partition}:bcm-data-exports:{DEFAULT_BILLING_REGION}:"
                f"{account}:table/{DATA_EXPORTS_TABLE}",
            ),
        ),
        PermissionGroup(
            "cur_data_exports_resource",
            "CUR 2.0 export inspection and tagging",
            (
                "bcm-data-exports:GetExport",
                "bcm-data-exports:ListExecutions",
                "bcm-data-exports:ListTagsForResource",
                "bcm-data-exports:TagResource",
            ),
            (f"arn:{partition}:bcm-data-exports:{DEFAULT_BILLING_REGION}:{account}:export/*",),
        ),
        PermissionGroup(
            "cur_data_exports_update",
            "CUR 2.0 updates across the export and source table",
            ("bcm-data-exports:UpdateExport",),
            (
                f"arn:{partition}:bcm-data-exports:{DEFAULT_BILLING_REGION}:{account}:export/*",
                f"arn:{partition}:bcm-data-exports:{DEFAULT_BILLING_REGION}:"
                f"{account}:table/{DATA_EXPORTS_TABLE}",
            ),
        ),
        PermissionGroup(
            "cur_legacy_dependency",
            "legacy CUR authorization required to create CUR 2.0 exports",
            ("cur:PutReportDefinition",),
        ),
        PermissionGroup(
            "glue_cur_catalog",
            "Glue catalog used by hourly cost-center allocation",
            (
                "glue:GetDatabase",
                "glue:CreateDatabase",
                "glue:GetTable",
                "glue:CreateTable",
                "glue:UpdateTable",
                "glue:GetPartition",
                "glue:CreatePartition",
            ),
        ),
        PermissionGroup(
            "athena_workgroup_list",
            "Athena workgroup discovery for regional DML headroom",
            ("athena:ListWorkGroups",),
        ),
        PermissionGroup(
            "athena_cur_queries",
            "Athena queries used by hourly cost-center allocation",
            (
                "athena:GetWorkGroup",
                "athena:StartQueryExecution",
                "athena:GetQueryExecution",
                "athena:GetQueryResults",
                "athena:ListQueryExecutions",
                "athena:BatchGetQueryExecution",
            ),
            (f"arn:{partition}:athena:{DEFAULT_BILLING_REGION}:{account}:workgroup/*",),
        ),
        PermissionGroup(
            "sns_list",
            "SNS account-level topic and subscription discovery",
            (
                "sns:ListTopics",
                "sns:ListSubscriptions",
            ),
        ),
        PermissionGroup(
            "sns_topic",
            "SNS topic integration",
            (
                "sns:CreateTopic",
                "sns:ListSubscriptionsByTopic",
                "sns:GetTopicAttributes",
                "sns:SetTopicAttributes",
                "sns:Subscribe",
                "sns:Unsubscribe",
                "sns:Publish",
                "sns:DeleteTopic",
            ),
            (f"arn:{partition}:sns:{region}:{account}:daylily-{cluster_name}-heartbeat",),
        ),
        PermissionGroup(
            "scheduler",
            "EventBridge Scheduler integration",
            (
                "scheduler:CreateSchedule",
                "scheduler:GetSchedule",
                "scheduler:ListSchedules",
                "scheduler:UpdateSchedule",
                "scheduler:DeleteSchedule",
            ),
        ),
        PermissionGroup(
            "lambda_imagebuilder",
            "Lambda and Image Builder backing services used by ParallelCluster",
            (
                "lambda:CreateFunction",
                "lambda:GetFunction",
                "lambda:ListFunctions",
                "lambda:DeleteFunction",
                "lambda:AddPermission",
                "lambda:RemovePermission",
                "imagebuilder:ListImages",
                "imagebuilder:GetImage",
                "imagebuilder:CreateImage",
                "imagebuilder:DeleteImage",
            ),
        ),
        PermissionGroup(
            "cloudwatch_logs",
            "CloudWatch metrics, alarms, and logs",
            (
                "cloudwatch:PutMetricData",
                "cloudwatch:DescribeAlarms",
                "cloudwatch:PutMetricAlarm",
                "cloudwatch:DeleteAlarms",
                "logs:CreateLogGroup",
                "logs:CreateLogStream",
                "logs:DescribeLogGroups",
                "logs:PutLogEvents",
                "logs:DeleteLogGroup",
            ),
        ),
        PermissionGroup(
            "dynamodb_parallelcluster",
            "ParallelCluster DynamoDB tables",
            (
                "dynamodb:CreateTable",
                "dynamodb:DescribeTable",
                "dynamodb:UpdateTable",
                "dynamodb:DeleteTable",
                "dynamodb:TagResource",
            ),
            (f"arn:aws:dynamodb:{region}:{account}:table/parallelcluster-validation",),
        ),
        PermissionGroup(
            "parallelcluster_backing_services",
            "ParallelCluster backing services",
            (
                "tag:GetResources",
                "tag:TagResources",
                "tag:UntagResources",
                "route53:ListHostedZones",
                "route53:ChangeResourceRecordSets",
                "apigateway:GET",
                "apigateway:POST",
                "apigateway:DELETE",
                "secretsmanager:CreateSecret",
                "secretsmanager:DescribeSecret",
                "secretsmanager:ListSecrets",
                "secretsmanager:GetSecretValue",
                "secretsmanager:GetRandomPassword",
                "secretsmanager:PutSecretValue",
                "secretsmanager:UpdateSecret",
                "secretsmanager:TagResource",
                "secretsmanager:DeleteSecret",
                "ecr:GetAuthorizationToken",
                "ecr:DescribeRepositories",
                "ecr:CreateRepository",
                "ecr:DeleteRepository",
                "cognito-idp:ListUserPools",
                "elasticfilesystem:DescribeFileSystems",
            ),
        ),
        PermissionGroup(
            "cur_s3_bucket",
            "CUR 2.0 delivery bucket and bucket policy",
            (
                "s3:ListBucket",
                "s3:GetBucketLocation",
                "s3:CreateBucket",
                "s3:GetBucketPolicy",
                "s3:PutBucketPolicy",
            ),
            (f"arn:{partition}:s3:::{cur_bucket}",),
        ),
        PermissionGroup(
            "cur_s3_objects",
            "CUR 2.0 delivered objects and Athena results",
            (
                "s3:GetObject",
                "s3:PutObject",
            ),
            (f"arn:{partition}:s3:::{cur_bucket}/{DEFAULT_CUR_EXPORT_PREFIX}/*",),
        ),
    ]
    groups.extend(
        PermissionGroup(
            f"service_linked_role_{service_name.split('.')[0].replace('-', '_')}",
            f"service-linked role creation for {service_name}",
            ("iam:CreateServiceLinkedRole",),
            ("*",),
            (("iam:AWSServiceName", (service_name,)),),
        )
        for service_name in service_linked_services
    )
    return tuple(groups)


def _simulate_group(
    iam_client: Any,
    principal_arn: str,
    group: PermissionGroup,
) -> list[dict[str, Any]]:
    kwargs: dict[str, Any] = {
        "PolicySourceArn": principal_arn,
        "ActionNames": list(group.actions),
        "ResourceArns": list(group.resources),
    }
    if group.context:
        kwargs["ContextEntries"] = [
            {
                "ContextKeyName": key,
                "ContextKeyValues": list(values),
                "ContextKeyType": "string",
            }
            for key, values in group.context
        ]
    results: list[dict[str, Any]] = []
    marker = ""
    while True:
        request = dict(kwargs)
        if marker:
            request["Marker"] = marker
        response = iam_client.simulate_principal_policy(**request)
        results.extend(response.get("EvaluationResults", []))
        if not response.get("IsTruncated"):
            return results
        marker = str(response.get("Marker") or "")
        if not marker:
            return results


def _simulation_source_arn(caller_arn: str, account_id: str) -> str:
    if ":assumed-role/" not in caller_arn:
        return caller_arn
    prefix, resource = caller_arn.split(":assumed-role/", maxsplit=1)
    role_name = resource.split("/", maxsplit=1)[0]
    partition = caller_arn.split(":", maxsplit=2)[1]
    return f"arn:{partition}:iam::{account_id}:role/{role_name}"


def _decode_ssm_document(content: Any) -> dict[str, Any]:
    if isinstance(content, dict):
        return content
    if not isinstance(content, str):
        raise ValueError("SSM document Content is not JSON text.")
    try:
        payload = json.loads(content or "{}")
    except json.JSONDecodeError as exc:
        raise ValueError("SSM document Content is not valid JSON.") from exc
    if not isinstance(payload, dict):
        raise ValueError("SSM document Content is not a JSON object.")
    return payload


def _aws_partition(caller_arn: str) -> str:
    parts = str(caller_arn or "").split(":", maxsplit=2)
    if len(parts) < 2 or not parts[1]:
        raise AwsValidationError(f"Cannot derive AWS partition from caller ARN: {caller_arn}")
    return parts[1]


def _decode_policy_document(content: Any) -> dict[str, Any]:
    if isinstance(content, dict):
        return content
    if not isinstance(content, str) or not content.strip():
        raise ValueError("managed policy version has no policy document")
    payload = json.loads(unquote(content))
    if not isinstance(payload, dict):
        raise ValueError("managed policy document is not a JSON object")
    return payload


def _policy_allows(document: dict[str, Any], *, action: str, resource: str) -> bool:
    statements = document.get("Statement") or []
    if isinstance(statements, dict):
        statements = [statements]
    matching_allows = False
    for statement in statements:
        if not isinstance(statement, dict):
            continue
        actions = statement.get("Action") or []
        resources = statement.get("Resource") or []
        if isinstance(actions, str):
            actions = [actions]
        if isinstance(resources, str):
            resources = [resources]
        action_matches = any(
            fnmatchcase(action.lower(), str(pattern).lower()) for pattern in actions
        )
        resource_matches = any(fnmatchcase(resource, str(pattern)) for pattern in resources)
        if not action_matches or not resource_matches:
            continue
        if statement.get("Effect") == "Deny":
            return False
        if statement.get("Effect") == "Allow" and not statement.get("Condition"):
            matching_allows = True
    return matching_allows


def _policy_statement_contains(actual: dict[str, Any], expected: dict[str, Any]) -> bool:
    actions = actual.get("Action") or []
    if isinstance(actions, str):
        actions = [actions]
    resources = actual.get("Resource") or []
    if isinstance(resources, str):
        resources = [resources]
    services = (actual.get("Principal") or {}).get("Service") or []
    if isinstance(services, str):
        services = [services]
    expected_services = (expected.get("Principal") or {}).get("Service") or []
    if isinstance(expected_services, str):
        expected_services = [expected_services]
    expected_actions = expected.get("Action") or []
    if isinstance(expected_actions, str):
        expected_actions = [expected_actions]
    expected_resources = expected.get("Resource") or []
    if isinstance(expected_resources, str):
        expected_resources = [expected_resources]
    return (
        actual.get("Effect") == expected.get("Effect")
        and set(map(str, expected_services)).issubset(set(map(str, services)))
        and set(map(str, expected_actions)).issubset(set(map(str, actions)))
        and set(map(str, expected_resources)).issubset(set(map(str, resources)))
        and actual.get("Condition") == expected.get("Condition")
    )


def _regional_client(aws_ctx: AWSContext, service: str, region: str) -> Any:
    if region == aws_ctx.region:
        return aws_ctx.client(service)
    return aws_ctx.session.client(service, region_name=region)


def _error_code(exc: Exception) -> str:
    response = getattr(exc, "response", None)
    if isinstance(response, dict):
        return str((response.get("Error") or {}).get("Code") or "")
    return ""


def _is_not_found_error(exc: Exception) -> bool:
    code = _error_code(exc)
    if code in {
        "404",
        "NoSuchBucket",
        "NoSuchBucketPolicy",
        "NotFoundException",
        "ResourceNotFoundException",
        "TableNotFoundException",
        "EntityNotFoundException",
    }:
        return True
    text = str(exc).lower()
    return "not found" in text or "notfound" in text or "does not exist" in text


def _list_budgets(client: Any, account_id: str) -> list[dict[str, Any]]:
    budgets: list[dict[str, Any]] = []
    token = ""
    while True:
        request: dict[str, Any] = {"AccountId": account_id, "MaxResults": 100}
        if token:
            request["NextToken"] = token
        response = client.describe_budgets(**request)
        budgets.extend(response.get("Budgets", []))
        token = str(response.get("NextToken") or "")
        if not token:
            return budgets


def _list_dynamodb_tables(client: Any) -> list[str]:
    try:
        paginator = client.get_paginator("list_tables")
    except Exception:
        paginator = None
    if paginator is not None:
        return [str(name) for page in paginator.paginate() for name in page.get("TableNames", [])]
    names: list[str] = []
    token = ""
    while True:
        request = {"ExclusiveStartTableName": token} if token else {}
        response = client.list_tables(**request)
        names.extend(str(name) for name in response.get("TableNames", []))
        token = str(response.get("LastEvaluatedTableName") or "")
        if not token:
            return names


def _list_data_exports(client: Any) -> list[dict[str, Any]]:
    exports: list[dict[str, Any]] = []
    token = ""
    while True:
        request = {"NextToken": token} if token else {}
        response = client.list_exports(**request)
        exports.extend(response.get("Exports", []))
        token = str(response.get("NextToken") or "")
        if not token:
            return exports


def _find_data_export_by_name(client: Any, export_name: str) -> dict[str, Any] | None:
    for export in _list_data_exports(client):
        if export.get("ExportName") == export_name:
            return export
    return None


def _list_data_export_executions(
    client: Any,
    export_arn: str,
) -> list[dict[str, Any]]:
    executions: list[dict[str, Any]] = []
    token = ""
    while True:
        request: dict[str, Any] = {"ExportArn": export_arn}
        if token:
            request["NextToken"] = token
        response = client.list_executions(**request)
        executions.extend(response.get("Executions", []))
        token = str(response.get("NextToken") or "")
        if not token:
            return executions


def _list_cloudformation_stacks(client: Any) -> list[dict[str, Any]]:
    try:
        paginator = client.get_paginator("describe_stacks")
    except Exception:
        paginator = None
    if paginator is not None:
        return [stack for page in paginator.paginate() for stack in page.get("Stacks", [])]
    stacks: list[dict[str, Any]] = []
    token = ""
    while True:
        request = {"NextToken": token} if token else {}
        response = client.describe_stacks(**request)
        stacks.extend(response.get("Stacks", []))
        token = str(response.get("NextToken") or "")
        if not token:
            return stacks


def _strict_bool_config(cfg: Any, key: str, fallback: bool) -> bool:
    raw = _effective_config_value(cfg, key, "true" if fallback else "false")
    value = raw.strip().lower()
    if value in {"true", "1", "yes"}:
        return True
    if value in {"false", "0", "no"}:
        return False
    raise AwsValidationError(f"{key} must be true or false; got {raw!r}")


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(value, Decimal):
        return str(value)
    return value


def _check_baseline_stack_presence(aws_ctx: AWSContext) -> CheckResult:
    stack_name = derive_stack_name(aws_ctx.region_az)
    status = describe_stack_status(aws_ctx.client("cloudformation"), stack_name)
    if status in {
        "CREATE_COMPLETE",
        "UPDATE_COMPLETE",
        "UPDATE_ROLLBACK_COMPLETE",
        "IMPORT_COMPLETE",
    }:
        return CheckResult(
            id="quota.network.baseline_stack",
            status=CheckStatus.PASS,
            details={"stack_name": stack_name, "stack_status": status},
        )
    known_broken = bool(status) and (
        "FAILED" in status or "ROLLBACK" in status or status == "DELETE_COMPLETE"
    )
    return CheckResult(
        id="quota.network.baseline_stack",
        status=CheckStatus.FAIL if known_broken else CheckStatus.WARN,
        details={
            "stack_name": stack_name,
            "stack_status": status or None,
            "network_quota_checks": [q.check_id for q in QUOTA_DEFS if q.service_code == "vpc"],
        },
        remediation=(
            "Baseline network stack is absent or unreadable. Ensure VPC, NAT "
            "Gateway, Elastic IP, and Internet Gateway quotas can support the "
            "first Daylily stack in this AZ."
        ),
    )


def _enrich_network_quota_headroom(
    checks: list[CheckResult],
    aws_ctx: AWSContext,
    *,
    baseline_ready: bool,
) -> None:
    """Replace ceiling-only network results with current-use-plus-demand math."""

    specs: dict[str, tuple[str, str, dict[str, Any]]] = {
        "quota.vpcs": ("describe_vpcs", "Vpcs", {}),
        "quota.elastic_ips": ("describe_addresses", "Addresses", {}),
        "quota.nat_gateways": (
            "describe_nat_gateways",
            "NatGateways",
            {
                "Filter": [
                    {
                        "Name": "state",
                        "Values": ["pending", "available", "deleting"],
                    },
                ]
            },
        ),
        "quota.internet_gateways": (
            "describe_internet_gateways",
            "InternetGateways",
            {},
        ),
    }
    if not any(check.id in specs for check in checks):
        return
    ec2 = aws_ctx.client("ec2")
    for check in checks:
        spec = specs.get(check.id)
        if spec is None:
            continue
        operation, result_key, request = spec
        check.details["scope"] = (
            aws_ctx.region_az if check.id == "quota.nat_gateways" else aws_ctx.region
        )
        check.details["required_new"] = 0 if baseline_ready else 1
        try:
            if check.id == "quota.nat_gateways":
                current_used = _count_nat_gateways_in_az(
                    ec2,
                    region_az=aws_ctx.region_az,
                    request=request,
                )
            elif check.id == "quota.elastic_ips":
                current_used = _count_customer_managed_amazon_eips(ec2)
            else:
                current_used = _count_paginated_items(
                    ec2,
                    operation=operation,
                    result_key=result_key,
                    request=request,
                )
        except Exception as exc:
            check.status = CheckStatus.WARN
            check.details["current_used"] = None
            check.details["error"] = str(exc)
            check.remediation = (
                f"Grant ec2:{operation.removeprefix('describe_').replace('_', ' ').title().replace(' ', '')} "
                "so current network quota use can be measured."
            )
            continue
        quota = check.details.get("current_value")
        check.details["current_used"] = current_used
        if quota is None:
            continue
        projected = current_used + int(check.details["required_new"])
        check.details["projected_used"] = projected
        check.details["remaining_after_required"] = int(float(quota)) - projected
        if projected > float(quota):
            check.status = CheckStatus.FAIL
            check.remediation = (
                f"Current use plus baseline demand requires {projected}, above quota "
                f"{check.details.get('quota_code')}={int(float(quota))}."
            )
        elif check.status != CheckStatus.WARN:
            check.status = CheckStatus.PASS
            check.remediation = ""


def _count_nat_gateways_in_az(
    ec2_client: Any,
    *,
    region_az: str,
    request: dict[str, Any],
) -> int:
    paginator = ec2_client.get_paginator("describe_nat_gateways")
    nat_gateways = [
        gateway for page in paginator.paginate(**request) for gateway in page.get("NatGateways", [])
    ]
    subnet_ids = sorted(
        {str(gateway.get("SubnetId") or "") for gateway in nat_gateways if gateway.get("SubnetId")}
    )
    subnets: list[dict[str, Any]] = []
    for batch in _chunks(subnet_ids, 200):
        subnets.extend(ec2_client.describe_subnets(SubnetIds=list(batch)).get("Subnets", []))
    target_subnets = {
        str(subnet.get("SubnetId") or "")
        for subnet in subnets
        if subnet.get("AvailabilityZone") == region_az
    }
    return sum(
        1 for gateway in nat_gateways if str(gateway.get("SubnetId") or "") in target_subnets
    )


def _count_customer_managed_amazon_eips(ec2_client: Any) -> int:
    addresses = ec2_client.describe_addresses().get("Addresses", [])
    return sum(
        1
        for address in addresses
        if not address.get("ServiceManaged")
        and str(address.get("PublicIpv4Pool") or "amazon") == "amazon"
    )


def _check_slurm_accounting_shape(
    aws_ctx: AWSContext,
    cfg: Any,
) -> tuple[CheckResult, int, int]:
    """Return optional accounting-host demand for vCPU and gp3 quota math."""

    enabled = _strict_bool_config(cfg, "slurm_accounting_enabled", False)
    instance_type = _effective_config_value(
        cfg,
        "slurm_accounting_instance_type",
        "t4g.micro",
    )
    if not enabled:
        return (
            CheckResult(
                id="quota.slurm_accounting_shape",
                status=CheckStatus.PASS,
                details={
                    "configured": False,
                    "additional_ondemand_vcpus": 0,
                    "additional_gp3_gib": 0,
                },
            ),
            0,
            0,
        )
    try:
        vcpus = _describe_instance_vcpus(
            aws_ctx.client("ec2"),
            [instance_type],
        )[instance_type]
    except Exception as exc:
        return (
            CheckResult(
                id="quota.slurm_accounting_shape",
                status=CheckStatus.FAIL,
                details={
                    "configured": True,
                    "instance_type": instance_type,
                    "error": str(exc),
                },
                remediation=(
                    "Grant ec2:DescribeInstanceTypes and select a valid explicit "
                    "Slurm-accounting instance type."
                ),
            ),
            0,
            0,
        )
    details = {
        "configured": True,
        "instance_type": instance_type,
        "additional_ondemand_vcpus": vcpus,
        "additional_gp3_gib": 20,
        "additional_security_groups": 2,
        "additional_network_interfaces": 1,
        "additional_secrets": 1,
        "additional_cloudformation_stacks": 1,
    }
    return (
        CheckResult(
            id="quota.slurm_accounting_shape",
            status=CheckStatus.PASS,
            details=details,
        ),
        vcpus,
        20,
    )


def _check_cost_control_quotas(
    aws_ctx: AWSContext,
    cfg: Any,
) -> list[CheckResult]:
    """Check count/headroom limits introduced by cost-control infrastructure."""

    checks = [
        _check_budget_count_quota(aws_ctx, cfg),
        _check_dynamodb_table_count_quota(aws_ctx),
        _check_s3_bucket_count_quota(aws_ctx),
        _check_cur_export_count_quota(aws_ctx),
        _check_athena_active_dml_quota(aws_ctx),
        _check_cloudformation_stack_quota(aws_ctx, cfg),
    ]
    checks.extend(_check_slurm_accounting_resource_quotas(aws_ctx, cfg))
    return checks


def _check_budget_count_quota(aws_ctx: AWSContext, cfg: Any) -> CheckResult:
    cluster_name = _effective_config_value(cfg, "cluster_name", "prod") or "prod"
    required_names = {
        GLOBAL_BUDGET_NAME,
        cluster_budget_name(aws_ctx.region_az, cluster_name),
    }
    try:
        budgets = _list_budgets(aws_ctx.client("budgets"), aws_ctx.account_id)
    except Exception as exc:
        return CheckResult(
            id="quota.budget_count",
            status=CheckStatus.WARN,
            details={
                "quota": BUDGET_COUNT_QUOTA,
                "required_budget_names": sorted(required_names),
                "source": BUDGET_QUOTA_SOURCE,
                "error": str(exc),
            },
            remediation="Grant budgets:ViewBudget so budget-count headroom can be verified.",
        )
    existing_names = {str(item.get("BudgetName") or "") for item in budgets}
    missing = sorted(required_names - existing_names)
    used = len(budgets)
    projected = used + len(missing)
    details = {
        "quota": BUDGET_COUNT_QUOTA,
        "current_used": used,
        "required_new": len(missing),
        "projected_used": projected,
        "remaining_after_required": BUDGET_COUNT_QUOTA - projected,
        "required_budget_names": sorted(required_names),
        "missing_budget_names": missing,
        "source": BUDGET_QUOTA_SOURCE,
    }
    if projected > BUDGET_COUNT_QUOTA:
        return CheckResult(
            id="quota.budget_count",
            status=CheckStatus.FAIL,
            details=details,
            remediation="Remove unused budgets or reduce required budget creation.",
        )
    return CheckResult(
        id="quota.budget_count",
        status=CheckStatus.PASS,
        details=details,
    )


def _check_dynamodb_table_count_quota(aws_ctx: AWSContext) -> CheckResult:
    dynamodb = _regional_client(
        aws_ctx,
        "dynamodb",
        DEFAULT_COST_CENTER_HOME_REGION,
    )
    table_names: set[str] = set()
    try:
        table_names = set(_list_dynamodb_tables(dynamodb))
        quota = _fetch_quota_value(
            _regional_client(
                aws_ctx,
                "service-quotas",
                DEFAULT_COST_CENTER_HOME_REGION,
            ),
            "dynamodb",
            DYNAMODB_TABLE_QUOTA_CODE,
        )
    except Exception as exc:
        quota = None
        error = str(exc)
    else:
        error = ""
    required_names = {DEFAULT_COST_CENTER_TABLE, DEFAULT_COST_CENTER_USAGE_TABLE}
    missing = sorted(required_names - table_names)
    details = {
        "region": DEFAULT_COST_CENTER_HOME_REGION,
        "quota_code": DYNAMODB_TABLE_QUOTA_CODE,
        "current_value": quota,
        "current_used": len(table_names) if not error else None,
        "required_new": len(missing),
        "missing_table_names": missing,
        "error": error,
    }
    if quota is None or details["current_used"] is None:
        return CheckResult(
            id="quota.dynamodb_table_count",
            status=CheckStatus.WARN,
            details=details,
            remediation=("Grant DynamoDB ListTables and Service Quotas GetServiceQuota access."),
        )
    projected = int(details["current_used"]) + len(missing)
    details["projected_used"] = projected
    details["remaining_after_required"] = int(quota) - projected
    if projected > quota:
        return CheckResult(
            id="quota.dynamodb_table_count",
            status=CheckStatus.FAIL,
            details=details,
            remediation="Request a DynamoDB table quota increase before registry creation.",
        )
    return CheckResult(
        id="quota.dynamodb_table_count",
        status=CheckStatus.PASS,
        details=details,
    )


def _check_s3_bucket_count_quota(aws_ctx: AWSContext) -> CheckResult:
    s3 = _regional_client(aws_ctx, "s3", DEFAULT_BILLING_REGION)
    desired_bucket = default_cur_export_bucket(aws_ctx.account_id)
    try:
        names = {str(item.get("Name") or "") for item in s3.list_buckets().get("Buckets", [])}
        quota = _fetch_quota_value(
            _regional_client(
                aws_ctx,
                "service-quotas",
                DEFAULT_BILLING_REGION,
            ),
            "s3",
            S3_GENERAL_PURPOSE_BUCKET_QUOTA_CODE,
        )
    except Exception as exc:
        return CheckResult(
            id="quota.s3_bucket_count",
            status=CheckStatus.WARN,
            details={
                "region": DEFAULT_BILLING_REGION,
                "quota_code": S3_GENERAL_PURPOSE_BUCKET_QUOTA_CODE,
                "desired_bucket": desired_bucket,
                "error": str(exc),
            },
            remediation="Grant S3 ListAllMyBuckets and Service Quotas read access.",
        )
    required_new = 0 if desired_bucket in names else 1
    projected = len(names) + required_new
    details = {
        "quota_code": S3_GENERAL_PURPOSE_BUCKET_QUOTA_CODE,
        "current_value": quota,
        "current_used": len(names),
        "required_new": required_new,
        "projected_used": projected,
        "desired_bucket": desired_bucket,
        "remaining_after_required": None if quota is None else int(quota) - projected,
    }
    if quota is None:
        return CheckResult(
            id="quota.s3_bucket_count",
            status=CheckStatus.WARN,
            details=details,
            remediation="Unable to read the S3 general-purpose bucket quota.",
        )
    if projected > quota:
        return CheckResult(
            id="quota.s3_bucket_count",
            status=CheckStatus.FAIL,
            details=details,
            remediation="Request S3 bucket quota headroom before CUR bucket creation.",
        )
    return CheckResult(
        id="quota.s3_bucket_count",
        status=CheckStatus.PASS,
        details=details,
    )


def _check_cur_export_count_quota(aws_ctx: AWSContext) -> CheckResult:
    bcm = _regional_client(
        aws_ctx,
        "bcm-data-exports",
        DEFAULT_BILLING_REGION,
    )
    try:
        exports = _list_data_exports(bcm)
        cur_exports: list[dict[str, Any]] = []
        desired_exists = False
        for summary in exports:
            export_arn = str(summary.get("ExportArn") or "")
            current = bcm.get_export(ExportArn=export_arn).get("Export") or {}
            query = str((current.get("DataQuery") or {}).get("QueryStatement") or "")
            if DATA_EXPORTS_TABLE not in query:
                continue
            cur_exports.append(current)
            if (
                str(current.get("Name") or summary.get("ExportName") or "")
                == DEFAULT_CUR_EXPORT_NAME
            ):
                desired_exists = True
    except Exception as exc:
        return CheckResult(
            id="quota.cur2_export_count",
            status=CheckStatus.WARN,
            details={
                "region": DEFAULT_BILLING_REGION,
                "quota": CUR_EXPORT_COUNT_QUOTA,
                "source": CUR_EXPORT_QUOTA_SOURCE,
                "error": str(exc),
            },
            remediation="Grant BCM Data Exports ListExports and GetExport access.",
        )
    required_new = 0 if desired_exists else 1
    projected = len(cur_exports) + required_new
    details = {
        "region": DEFAULT_BILLING_REGION,
        "quota": CUR_EXPORT_COUNT_QUOTA,
        "current_used": len(cur_exports),
        "required_new": required_new,
        "projected_used": projected,
        "remaining_after_required": CUR_EXPORT_COUNT_QUOTA - projected,
        "desired_export": DEFAULT_CUR_EXPORT_NAME,
        "desired_export_exists": desired_exists,
        "source": CUR_EXPORT_QUOTA_SOURCE,
    }
    if projected > CUR_EXPORT_COUNT_QUOTA:
        return CheckResult(
            id="quota.cur2_export_count",
            status=CheckStatus.FAIL,
            details=details,
            remediation="Remove an unused CUR 2.0 export before creating the DayEC export.",
        )
    return CheckResult(
        id="quota.cur2_export_count",
        status=CheckStatus.PASS,
        details=details,
    )


def _check_athena_active_dml_quota(aws_ctx: AWSContext) -> CheckResult:
    athena = _regional_client(aws_ctx, "athena", DEFAULT_BILLING_REGION)
    quota = _fetch_quota_value(
        _regional_client(
            aws_ctx,
            "service-quotas",
            DEFAULT_BILLING_REGION,
        ),
        "athena",
        ATHENA_ACTIVE_DML_QUOTA_CODE,
    )
    details: dict[str, Any] = {
        "region": DEFAULT_BILLING_REGION,
        "service_code": "athena",
        "quota_code": ATHENA_ACTIVE_DML_QUOTA_CODE,
        "current_value": quota,
        "current_used": None,
        "required_new": 1,
        "workgroups_inspected": [],
    }
    if quota is None:
        return CheckResult(
            id="quota.athena_active_dml",
            status=CheckStatus.WARN,
            details=details,
            remediation=(
                f"Unable to read Athena quota {ATHENA_ACTIVE_DML_QUOTA_CODE} in "
                f"{DEFAULT_BILLING_REGION}."
            ),
        )
    try:
        workgroups = _list_athena_workgroups(athena)
        details["workgroups_inspected"] = workgroups
        execution_ids = [
            execution_id
            for workgroup in workgroups
            for execution_id in _list_athena_query_execution_ids(
                athena,
                workgroup=workgroup,
            )
        ]
        active_ids: list[str] = []
        for batch in _chunks(execution_ids, 50):
            response = athena.batch_get_query_execution(QueryExecutionIds=list(batch))
            for execution in response.get("QueryExecutions", []):
                state = str((execution.get("Status") or {}).get("State") or "")
                statement_type = str(execution.get("StatementType") or "")
                if statement_type == "DML" and state in {"QUEUED", "RUNNING"}:
                    active_ids.append(str(execution.get("QueryExecutionId") or ""))
    except Exception as exc:
        details["error"] = str(exc)
        return CheckResult(
            id="quota.athena_active_dml",
            status=CheckStatus.WARN,
            details=details,
            remediation=(
                "Grant athena:ListWorkGroups, athena:ListQueryExecutions, and "
                "athena:BatchGetQueryExecution across regional workgroups so active "
                "DML headroom can be measured."
            ),
        )
    current_used = len(active_ids)
    projected = current_used + 1
    details.update(
        {
            "current_used": current_used,
            "active_query_execution_ids": sorted(active_ids),
            "projected_used": projected,
            "remaining_after_required": int(quota) - projected,
        }
    )
    if projected > quota:
        return CheckResult(
            id="quota.athena_active_dml",
            status=CheckStatus.FAIL,
            details=details,
            remediation=(
                "Wait for an active Athena DML query to finish or request additional "
                "active-query quota before the hourly allocation query runs."
            ),
        )
    return CheckResult(
        id="quota.athena_active_dml",
        status=CheckStatus.PASS,
        details=details,
    )


def _list_athena_query_execution_ids(
    client: Any,
    *,
    workgroup: str,
) -> list[str]:
    execution_ids: list[str] = []
    token = ""
    while True:
        request: dict[str, Any] = {"WorkGroup": workgroup, "MaxResults": 50}
        if token:
            request["NextToken"] = token
        response = client.list_query_executions(**request)
        execution_ids.extend(str(value) for value in response.get("QueryExecutionIds", []) if value)
        token = str(response.get("NextToken") or "")
        if not token:
            return execution_ids


def _list_athena_workgroups(client: Any) -> list[str]:
    workgroups: list[str] = []
    token = ""
    while True:
        request: dict[str, Any] = {"MaxResults": 50}
        if token:
            request["NextToken"] = token
        response = client.list_work_groups(**request)
        workgroups.extend(
            str(item.get("Name") or "")
            for item in response.get("WorkGroups", [])
            if item.get("Name")
        )
        token = str(response.get("NextToken") or "")
        if not token:
            return sorted(set(workgroups))


def _check_fixed_service_quota(
    aws_ctx: AWSContext,
    *,
    check_id: str,
    service_code: str,
    quota_code: str,
    required_value: float,
    required_unit: str,
    region: str,
) -> CheckResult:
    quota = _fetch_quota_value(
        _regional_client(aws_ctx, "service-quotas", region),
        service_code,
        quota_code,
    )
    details = {
        "region": region,
        "service_code": service_code,
        "quota_code": quota_code,
        "current_value": quota,
        "required_value": required_value,
        "required_unit": required_unit,
    }
    if quota is None:
        return CheckResult(
            id=check_id,
            status=CheckStatus.WARN,
            details=details,
            remediation=f"Unable to read quota {quota_code} in {region}.",
        )
    if required_value > quota:
        return CheckResult(
            id=check_id,
            status=CheckStatus.FAIL,
            details=details,
            remediation=f"Request quota {quota_code} >= {required_value:g} {required_unit}.",
        )
    return CheckResult(id=check_id, status=CheckStatus.PASS, details=details)


def _check_cloudformation_stack_quota(aws_ctx: AWSContext, cfg: Any) -> CheckResult:
    enabled = _strict_bool_config(cfg, "slurm_accounting_enabled", False)
    if not enabled:
        return CheckResult(
            id="quota.cloudformation_stack_count",
            status=CheckStatus.PASS,
            details={"required_new": 0, "slurm_accounting_enabled": False},
        )
    cfn = aws_ctx.client("cloudformation")
    desired = _effective_config_value(cfg, "slurm_accounting_stack_name", "") or (
        derive_slurm_accounting_stack_name(aws_ctx.region_az)
    )
    try:
        summaries = [
            stack
            for stack in _list_cloudformation_stacks(cfn)
            if str(stack.get("StackStatus") or "") != "DELETE_COMPLETE"
        ]
        regional_accounting_stacks = list_regional_slurm_accounting_stacks(
            aws_ctx,
            region_az=aws_ctx.region_az,
        )
    except Exception as exc:
        return CheckResult(
            id="quota.cloudformation_stack_count",
            status=CheckStatus.WARN,
            details={"required_stack": desired, "error": str(exc)},
            remediation="Grant cloudformation:ListStacks for stack-count headroom.",
        )
    required_new = 0 if regional_accounting_stacks else 1
    quota_check = _check_fixed_service_quota(
        aws_ctx,
        check_id="quota.cloudformation_stack_count",
        service_code="cloudformation",
        quota_code=CLOUDFORMATION_STACK_QUOTA_CODE,
        required_value=len(summaries) + required_new,
        required_unit="stacks",
        region=aws_ctx.region,
    )
    quota_check.details.update(
        {
            "current_used": len(summaries),
            "required_new": required_new,
            "required_stack": desired,
            "regional_accounting_stacks": [
                str(stack.get("StackName") or "") for stack in regional_accounting_stacks
            ],
        }
    )
    return quota_check


def _check_slurm_accounting_resource_quotas(
    aws_ctx: AWSContext,
    cfg: Any,
) -> list[CheckResult]:
    enabled = _strict_bool_config(cfg, "slurm_accounting_enabled", False)
    specs = (
        (
            "quota.slurm_accounting.security_groups",
            "vpc",
            VPC_SECURITY_GROUP_QUOTA_CODE,
            aws_ctx.region,
            "describe_security_groups",
            "SecurityGroups",
            2,
            "ec2",
        ),
        (
            "quota.slurm_accounting.network_interfaces",
            "vpc",
            VPC_NETWORK_INTERFACE_QUOTA_CODE,
            aws_ctx.region,
            "describe_network_interfaces",
            "NetworkInterfaces",
            1,
            "ec2",
        ),
        (
            "quota.slurm_accounting.secrets",
            "secretsmanager",
            SECRETS_MANAGER_SECRET_QUOTA_CODE,
            aws_ctx.region,
            "list_secrets",
            "SecretList",
            1,
            "secretsmanager",
        ),
        (
            "quota.slurm_accounting.iam_roles",
            "iam",
            "RolesQuota",
            DEFAULT_BILLING_REGION,
            "list_roles",
            "Roles",
            1,
            "iam",
        ),
        (
            "quota.slurm_accounting.iam_instance_profiles",
            "iam",
            "InstanceProfilesQuota",
            DEFAULT_BILLING_REGION,
            "list_instance_profiles",
            "InstanceProfiles",
            1,
            "iam",
        ),
    )
    if not enabled:
        return [
            CheckResult(
                id=check_id,
                status=CheckStatus.PASS,
                details={
                    "configured": False,
                    "required_new": 0,
                    "quota_code": quota_code,
                },
            )
            for (
                check_id,
                _service_code,
                quota_code,
                _region,
                _operation,
                _result_key,
                _demand,
                _client_service,
            ) in specs
        ]

    desired_stack = _effective_config_value(cfg, "slurm_accounting_stack_name", "") or (
        derive_slurm_accounting_stack_name(aws_ctx.region_az)
    )
    try:
        regional_accounting_stacks = list_regional_slurm_accounting_stacks(
            aws_ctx,
            region_az=aws_ctx.region_az,
        )
        stack_inventory_error = ""
    except Exception as exc:
        regional_accounting_stacks = []
        stack_inventory_error = str(exc)
    stack_exists = bool(regional_accounting_stacks)
    stack_status = ",".join(
        sorted(str(stack.get("StackStatus") or "") for stack in regional_accounting_stacks)
    )
    try:
        iam_summary = aws_ctx.client("iam").get_account_summary().get("SummaryMap") or {}
        iam_summary_error = ""
    except Exception as exc:
        iam_summary = {}
        iam_summary_error = str(exc)
    checks: list[CheckResult] = []
    for (
        check_id,
        service_code,
        quota_code,
        region,
        operation,
        result_key,
        missing_stack_demand,
        client_service,
    ) in specs:
        client = aws_ctx.client(client_service)
        required_new = 0 if stack_exists else missing_stack_demand
        if service_code == "iam":
            quota = float(iam_summary[quota_code]) if quota_code in iam_summary else None
        else:
            quota = _fetch_quota_value(
                _regional_client(aws_ctx, "service-quotas", region),
                service_code,
                quota_code,
            )
        details: dict[str, Any] = {
            "configured": True,
            "region": region,
            "service_code": service_code,
            "quota_code": quota_code,
            "current_value": quota,
            "required_new": required_new,
            "accounting_stack": desired_stack,
            "accounting_stack_status": stack_status,
            "regional_accounting_stacks": [
                str(stack.get("StackName") or "") for stack in regional_accounting_stacks
            ],
            "quota_source": (
                "iam:GetAccountSummary"
                if service_code == "iam"
                else "servicequotas:GetServiceQuota"
            ),
        }
        try:
            if stack_inventory_error:
                raise RuntimeError(stack_inventory_error)
            if service_code == "iam":
                if iam_summary_error:
                    raise RuntimeError(iam_summary_error)
                current_used = int(iam_summary[result_key])
            else:
                current_used = _count_paginated_items(
                    client,
                    operation=operation,
                    result_key=result_key,
                )
        except Exception as exc:
            details["current_used"] = None
            details["error"] = str(exc)
            checks.append(
                CheckResult(
                    id=check_id,
                    status=CheckStatus.WARN,
                    details=details,
                    remediation=(
                        f"Grant read access for {operation} so current accounting-resource "
                        "headroom can be measured."
                    ),
                )
            )
            continue
        details["current_used"] = current_used
        if quota is None:
            quota_remediation = (
                f"IAM account summary did not include {quota_code}."
                if service_code == "iam"
                else f"Unable to read service quota {quota_code} in {region}."
            )
            checks.append(
                CheckResult(
                    id=check_id,
                    status=CheckStatus.WARN,
                    details=details,
                    remediation=quota_remediation,
                )
            )
            continue
        projected = current_used + required_new
        details["projected_used"] = projected
        details["remaining_after_required"] = int(quota) - projected
        if projected > quota:
            checks.append(
                CheckResult(
                    id=check_id,
                    status=CheckStatus.FAIL,
                    details=details,
                    remediation=(
                        f"Request quota {quota_code} above {projected} or release unused "
                        "resources before creating the accounting stack."
                    ),
                )
            )
        else:
            checks.append(
                CheckResult(
                    id=check_id,
                    status=CheckStatus.PASS,
                    details=details,
                )
            )
    return checks


def _count_paginated_items(
    client: Any,
    *,
    operation: str,
    result_key: str,
    request: dict[str, Any] | None = None,
) -> int:
    kwargs = dict(request or {})
    try:
        paginator = client.get_paginator(operation)
    except Exception:
        paginator = None
    if paginator is not None:
        return sum(len(page.get(result_key, [])) for page in paginator.paginate(**kwargs))
    response = getattr(client, operation)(**kwargs)
    return len(response.get(result_key, []))


def _check_rendered_vcpu_quotas(
    aws_ctx: AWSContext,
    shape: ClusterShape,
    *,
    additional_ondemand_vcpus: int = 0,
    additional_ondemand_instance_type: str = "",
) -> list[CheckResult]:
    """Check current-use plus rendered demand against each EC2 vCPU family quota."""

    service_quotas = aws_ctx.client("service-quotas")
    demands, covered_types = _rendered_vcpu_demands_by_group(shape)
    additional_group = ""
    if additional_ondemand_vcpus:
        additional_group = _ec2_vcpu_quota_group(additional_ondemand_instance_type)
        demands[(additional_group, "ONDEMAND")] += additional_ondemand_vcpus
        covered_types.setdefault((additional_group, "ONDEMAND"), set()).add(
            additional_ondemand_instance_type
        )
    try:
        (
            current_usage,
            current_instance_counts,
            current_open_spot_request_counts,
            open_spot_request_error,
        ) = _current_ec2_vcpu_usage(aws_ctx)
        usage_error = ""
    except Exception as exc:
        current_usage = Counter()
        current_instance_counts = Counter()
        current_open_spot_request_counts = Counter()
        open_spot_request_error = ""
        usage_error = str(exc)

    checks: list[CheckResult] = []
    for (quota_group, capacity_type), demand in sorted(demands.items()):
        suffix = "" if quota_group == "standard" else f".{quota_group}"
        check_id = (
            "quota.rendered_ondemand_vcpu"
            if capacity_type == "ONDEMAND"
            else "quota.rendered_spot_vcpu"
        ) + suffix
        quota_definition = EC2_VCPU_QUOTA_CODES.get((quota_group, capacity_type))
        details: dict[str, Any] = {
            "service_code": "ec2",
            "quota_group": quota_group,
            "capacity_type": capacity_type,
            "covered_instance_types": sorted(
                covered_types.get((quota_group, capacity_type), set())
            ),
            "current_used_vcpus": current_usage[(quota_group, capacity_type)],
            "current_instance_count": current_instance_counts[(quota_group, capacity_type)],
            "current_open_spot_request_count": current_open_spot_request_counts[
                (quota_group, capacity_type)
            ],
            "rendered_demand_vcpus": demand,
            "additional_slurm_accounting_vcpus": (
                additional_ondemand_vcpus
                if quota_group == additional_group and capacity_type == "ONDEMAND"
                else 0
            ),
        }
        if usage_error:
            details["current_used_vcpus"] = None
            details["current_instance_count"] = None
            details["current_open_spot_request_count"] = None
            details["usage_error"] = usage_error
            checks.append(
                CheckResult(
                    id=check_id,
                    status=CheckStatus.WARN,
                    details=details,
                    remediation=(
                        "Grant ec2:DescribeInstances, ec2:DescribeSpotInstanceRequests, "
                        "and ec2:DescribeInstanceTypes so current regional vCPU use can "
                        "be included in quota headroom."
                    ),
                )
            )
            continue
        if quota_definition is None:
            checks.append(
                CheckResult(
                    id=check_id,
                    status=CheckStatus.WARN,
                    details=details,
                    remediation=(
                        f"No explicit {capacity_type} vCPU quota mapping is registered "
                        f"for EC2 family group {quota_group}. Add the exact AWS quota "
                        "before treating this instance family as launch-ready."
                    ),
                )
            )
            continue
        quota_code, quota_name = quota_definition
        quota_value = _fetch_quota_value(service_quotas, "ec2", quota_code)
        details["quota_code"] = quota_code
        details["quota_name"] = quota_name
        details["current_value"] = quota_value
        if quota_value is None:
            checks.append(
                CheckResult(
                    id=check_id,
                    status=CheckStatus.WARN,
                    details=details,
                    remediation=(
                        f"Unable to read EC2 quota {quota_code} for {quota_name}. "
                        "Grant servicequotas:GetServiceQuota or check the quota manually."
                    ),
                )
            )
            continue
        projected = current_usage[(quota_group, capacity_type)] + demand
        details["projected_used_vcpus"] = projected
        details["remaining_after_required_vcpus"] = int(quota_value) - projected
        if projected > quota_value:
            checks.append(
                CheckResult(
                    id=check_id,
                    status=CheckStatus.FAIL,
                    details=details,
                    remediation=(
                        f"Current use plus rendered demand requires {projected} vCPUs "
                        f"from {quota_name}, but quota {quota_code} is "
                        f"{int(quota_value)}. Request an increase or reduce the "
                        "configured queue MaxCount/instance-family choices."
                    ),
                )
            )
            continue
        if capacity_type == "SPOT" and open_spot_request_error:
            details["open_spot_request_usage_error"] = open_spot_request_error
            checks.append(
                CheckResult(
                    id=check_id,
                    status=CheckStatus.WARN,
                    details=details,
                    remediation=(
                        "Grant ec2:DescribeSpotInstanceRequests so open, unfulfilled "
                        "Spot request vCPUs can be included without double-counting "
                        "fulfilled running instances."
                    ),
                )
            )
            continue
        checks.append(
            CheckResult(
                id=check_id,
                status=CheckStatus.PASS,
                details=details,
            )
        )
    return checks


def _rendered_vcpu_demands_by_group(
    shape: ClusterShape,
) -> tuple[Counter[tuple[str, str]], dict[tuple[str, str], set[str]]]:
    demands: Counter[tuple[str, str]] = Counter()
    covered_types: dict[tuple[str, str], set[str]] = {}
    head_group = _ec2_vcpu_quota_group(shape.headnode_instance_type)
    demands[(head_group, "ONDEMAND")] += shape.headnode_vcpus
    covered_types.setdefault((head_group, "ONDEMAND"), set()).add(shape.headnode_instance_type)
    for resource in shape.compute_resources:
        types_by_group: dict[str, list[str]] = {}
        for instance_type in resource.instance_types:
            group = _ec2_vcpu_quota_group(instance_type)
            types_by_group.setdefault(group, []).append(instance_type)
        for group, instance_types in types_by_group.items():
            key = (group, resource.capacity_type)
            max_vcpus = max(
                shape.vcpus_by_instance_type[instance_type] for instance_type in instance_types
            )
            demands[key] += resource.max_count * max_vcpus
            covered_types.setdefault(key, set()).update(instance_types)
    return demands, covered_types


def _ec2_vcpu_quota_group(instance_type: str) -> str:
    value = str(instance_type or "").strip().lower()
    if value.startswith("hpc"):
        return "hpc"
    if value.startswith("inf"):
        return "inf"
    if value.startswith("trn"):
        return "trn"
    if value.startswith("dl"):
        return "dl"
    if value.startswith("vt") or value.startswith("g"):
        return "g_vt"
    if value.startswith("x"):
        return "x"
    if value.startswith("f"):
        return "f"
    if value.startswith("p"):
        return "p"
    if value.startswith("u-"):
        return "high_memory"
    if value[:1] in {"a", "c", "d", "h", "i", "m", "r", "t", "z"}:
        return "standard"
    return f"unmapped_{value.split('.', maxsplit=1)[0] or 'unknown'}"


def _current_ec2_vcpu_usage(
    aws_ctx: AWSContext,
) -> tuple[
    Counter[tuple[str, str]],
    Counter[tuple[str, str]],
    Counter[tuple[str, str]],
    str,
]:
    ec2 = aws_ctx.client("ec2")
    instances: list[dict[str, Any]] = []
    paginator = ec2.get_paginator("describe_instances")
    for page in paginator.paginate(
        Filters=[
            {
                "Name": "instance-state-name",
                "Values": ["pending", "running"],
            }
        ]
    ):
        for reservation in page.get("Reservations", []):
            instances.extend(reservation.get("Instances", []))
    open_spot_requests: list[dict[str, Any]] = []
    open_spot_request_error = ""
    try:
        spot_paginator = ec2.get_paginator("describe_spot_instance_requests")
        for page in spot_paginator.paginate(Filters=[{"Name": "state", "Values": ["open"]}]):
            open_spot_requests.extend(page.get("SpotInstanceRequests", []))
    except Exception as exc:
        open_spot_request_error = str(exc)

    instance_types = {
        str(instance.get("InstanceType") or "")
        for instance in instances
        if instance.get("InstanceType")
    }
    open_request_types: list[str] = []
    missing_request_types: list[str] = []
    for request in open_spot_requests:
        launch_specification = request.get("LaunchSpecification") or {}
        instance_type = (
            str(launch_specification.get("InstanceType") or "").strip()
            if isinstance(launch_specification, dict)
            else ""
        )
        if not instance_type:
            missing_request_types.append(str(request.get("SpotInstanceRequestId") or "unknown"))
            continue
        open_request_types.append(instance_type)
        instance_types.add(instance_type)
    if missing_request_types:
        raise ValueError(
            "Open Spot request(s) did not expose LaunchSpecification.InstanceType: "
            + ", ".join(sorted(missing_request_types))
        )
    vcpus_by_type = _describe_instance_vcpus(ec2, instance_types)
    usage: Counter[tuple[str, str]] = Counter()
    counts: Counter[tuple[str, str]] = Counter()
    open_request_counts: Counter[tuple[str, str]] = Counter()
    for instance in instances:
        instance_type = str(instance.get("InstanceType") or "")
        quota_group = _ec2_vcpu_quota_group(instance_type)
        capacity_type = "SPOT" if instance.get("InstanceLifecycle") == "spot" else "ONDEMAND"
        key = (quota_group, capacity_type)
        usage[key] += vcpus_by_type[instance_type]
        counts[key] += 1
    for instance_type in open_request_types:
        key = (_ec2_vcpu_quota_group(instance_type), "SPOT")
        usage[key] += vcpus_by_type[instance_type]
        open_request_counts[key] += 1
    return usage, counts, open_request_counts, open_spot_request_error


def _check_instance_type_offerings(
    aws_ctx: AWSContext,
    shape: ClusterShape,
) -> CheckResult:
    instance_types = shape.all_instance_types
    ec2 = aws_ctx.client("ec2")
    try:
        offered: set[str] = set()
        paginator = ec2.get_paginator("describe_instance_type_offerings")
        for batch in _chunks(instance_types, 100):
            for page in paginator.paginate(
                LocationType="availability-zone",
                Filters=[
                    {"Name": "location", "Values": [aws_ctx.region_az]},
                    {"Name": "instance-type", "Values": list(batch)},
                ],
            ):
                for offering in page.get("InstanceTypeOfferings", []):
                    instance_type = str(offering.get("InstanceType") or "")
                    if instance_type:
                        offered.add(instance_type)
    except Exception as exc:
        return CheckResult(
            id="quota.instance_type_offerings",
            status=CheckStatus.FAIL,
            details={
                "region_az": aws_ctx.region_az,
                "instance_types": list(instance_types),
                "error": str(exc),
            },
            remediation=(
                "Grant ec2:DescribeInstanceTypeOfferings and verify the requested "
                "instance types are offered in the selected AZ."
            ),
        )
    missing = sorted(set(instance_types) - offered)
    details = {
        "region_az": aws_ctx.region_az,
        "instance_types": list(instance_types),
        "offered_instance_types": sorted(offered),
        "missing_instance_types": missing,
    }
    if missing:
        return CheckResult(
            id="quota.instance_type_offerings",
            status=CheckStatus.FAIL,
            details=details,
            remediation=(
                f"The selected AZ does not offer all requested instance types: "
                f"{', '.join(missing)}. Pick another --region-az or edit the "
                "cluster template queues."
            ),
        )
    return CheckResult(
        id="quota.instance_type_offerings",
        status=CheckStatus.PASS,
        details=details,
    )


def _check_spot_market_signal(aws_ctx: AWSContext, shape: ClusterShape) -> CheckResult:
    instance_types = shape.spot_instance_types
    if not instance_types:
        return CheckResult(
            id="quota.spot_market_signal",
            status=CheckStatus.PASS,
            details={"spot_instance_types": []},
        )
    ec2 = aws_ctx.client("ec2")
    missing: list[str] = []
    errors: dict[str, str] = {}
    for instance_type in instance_types:
        try:
            response = ec2.describe_spot_price_history(
                InstanceTypes=[instance_type],
                ProductDescriptions=["Linux/UNIX"],
                AvailabilityZone=aws_ctx.region_az,
                MaxResults=1,
            )
        except Exception as exc:
            errors[instance_type] = str(exc)
            continue
        if not response.get("SpotPriceHistory"):
            missing.append(instance_type)
    details = {
        "region_az": aws_ctx.region_az,
        "spot_instance_types": list(instance_types),
        "missing_price_history": sorted(missing),
        "errors": errors,
    }
    if missing or errors:
        return CheckResult(
            id="quota.spot_market_signal",
            status=CheckStatus.WARN,
            details=details,
            remediation=(
                "Some requested Spot instance types have no visible Linux/UNIX "
                "price signal in the selected AZ. Grant ec2:DescribeSpotPriceHistory "
                "or choose instance types/AZs with active Spot capacity."
            ),
        )
    return CheckResult(
        id="quota.spot_market_signal",
        status=CheckStatus.PASS,
        details=details,
    )


def _check_storage_quotas(
    aws_ctx: AWSContext,
    shape: ClusterShape,
    *,
    additional_gp3_gib: int = 0,
) -> list[CheckResult]:
    checks: list[CheckResult] = []
    if shape.headnode_root_volume_type == "gp3" or additional_gp3_gib > 0:
        cluster_gp3_gib = (
            shape.headnode_root_volume_gib if shape.headnode_root_volume_type == "gp3" else 0
        )
        checks.append(
            _check_ebs_gp3_headroom(
                aws_ctx,
                required_new_gib=cluster_gp3_gib + additional_gp3_gib,
                additional_slurm_accounting_gp3_gib=additional_gp3_gib,
            )
        )
    else:
        checks.append(
            CheckResult(
                id="quota.ebs.gp3_storage",
                status=CheckStatus.PASS,
                details={
                    "volume_type": shape.headnode_root_volume_type,
                    "headnode_root_volume_gib": shape.headnode_root_volume_gib,
                    "additional_slurm_accounting_gp3_gib": additional_gp3_gib,
                    "note": "cluster template does not request gp3 root volume",
                },
            )
        )

    deployment_type = shape.fsx_deployment_type.upper()
    if deployment_type.startswith("SCRATCH"):
        checks.extend(
            _check_fsx_lustre_headroom(
                aws_ctx,
                deployment_kind="scratch",
                required_new_storage_gib=shape.fsx_storage_gib,
            )
        )
    elif deployment_type == "PERSISTENT_1":
        checks.extend(
            _check_fsx_lustre_headroom(
                aws_ctx,
                deployment_kind="persistent_1",
                required_new_storage_gib=shape.fsx_storage_gib,
            )
        )
    elif deployment_type == "PERSISTENT_2" and shape.fsx_storage_type != "INTELLIGENT_TIERING":
        checks.extend(
            _check_fsx_lustre_headroom(
                aws_ctx,
                deployment_kind="persistent_2",
                required_new_storage_gib=shape.fsx_storage_gib,
            )
        )
    elif deployment_type == "PERSISTENT_2":
        checks.extend(
            _check_fsx_lustre_headroom(
                aws_ctx,
                deployment_kind="persistent_intelligent_tiering",
                required_new_storage_gib=0,
                required_new_read_cache_gib=shape.fsx_read_cache_gib,
                required_new_throughput_capacity=shape.fsx_throughput_capacity,
            )
        )
    elif (
        deployment_type
        or shape.fsx_storage_gib > 0
        or shape.fsx_read_cache_gib > 0
        or shape.fsx_throughput_capacity > 0
    ):
        checks.append(
            CheckResult(
                id="quota.fsx.lustre_deployment_type",
                status=CheckStatus.FAIL,
                details={
                    "deployment_type": shape.fsx_deployment_type,
                    "storage_type": shape.fsx_storage_type,
                },
                remediation=(
                    "Add exact FSx Service Quota mappings for this rendered Lustre "
                    "deployment and storage type before treating it as launch-ready."
                ),
            )
        )
    else:
        checks.append(
            CheckResult(
                id="quota.fsx.lustre_storage",
                status=CheckStatus.PASS,
                details={"fsx_storage_gib": 0, "note": "no FSx Lustre storage requested"},
            )
        )
    return checks


def _check_ebs_gp3_headroom(
    aws_ctx: AWSContext,
    *,
    required_new_gib: int,
    additional_slurm_accounting_gp3_gib: int,
) -> CheckResult:
    check = _check_named_service_quota(
        aws_ctx,
        check_id="quota.ebs.gp3_storage",
        service_code="ebs",
        quota_name_fragments=("Storage for General Purpose SSD (gp3) volumes",),
        required_value=required_new_gib / 1024,
        required_unit="TiB",
        remediation_subject="EBS gp3 regional storage",
    )
    check.details["required_new_gib"] = required_new_gib
    check.details["additional_slurm_accounting_gp3_gib"] = additional_slurm_accounting_gp3_gib
    try:
        ec2 = aws_ctx.client("ec2")
        paginator = ec2.get_paginator("describe_volumes")
        current_used_gib = sum(
            int(volume.get("Size") or 0)
            for page in paginator.paginate(Filters=[{"Name": "volume-type", "Values": ["gp3"]}])
            for volume in page.get("Volumes", [])
        )
    except Exception as exc:
        check.details["current_used_gib"] = None
        check.details["usage_error"] = str(exc)
        if check.status != CheckStatus.FAIL:
            check.status = CheckStatus.WARN
            check.remediation = (
                "Grant ec2:DescribeVolumes so current gp3 storage consumption can be "
                "included in quota headroom."
            )
        return check
    check.details["current_used_gib"] = current_used_gib
    quota_tib = check.details.get("current_value")
    if quota_tib is None:
        return check
    projected_gib = current_used_gib + required_new_gib
    quota_gib = float(quota_tib) * 1024
    check.details["projected_used_gib"] = projected_gib
    check.details["remaining_after_required_gib"] = int(quota_gib - projected_gib)
    if projected_gib > quota_gib:
        check.status = CheckStatus.FAIL
        check.remediation = (
            f"Current gp3 use plus demand is {projected_gib} GiB, above the "
            f"{int(quota_gib)} GiB applied quota."
        )
    elif check.status != CheckStatus.WARN:
        check.status = CheckStatus.PASS
        check.remediation = ""
    return check


def _check_fsx_lustre_headroom(
    aws_ctx: AWSContext,
    *,
    deployment_kind: str,
    required_new_storage_gib: int,
    required_new_read_cache_gib: int = 0,
    required_new_throughput_capacity: int = 0,
) -> list[CheckResult]:
    quota_names = {
        "scratch": (
            "quota.fsx.lustre_scratch",
            "Lustre Scratch file systems",
            "Lustre Scratch storage capacity",
        ),
        "persistent_1": (
            "quota.fsx.lustre_persistent_1",
            "Lustre Persistent_1 file systems",
            "Lustre Persistent_1 storage capacity",
        ),
        "persistent_2": (
            "quota.fsx.lustre_persistent_2",
            "Lustre Persistent_2 file systems",
            "Lustre Persistent_2 storage capacity",
        ),
        "persistent_intelligent_tiering": (
            "quota.fsx.lustre_persistent_intelligent_tiering",
            "Lustre Persistent_2 file systems",
            "Lustre Persistent Intelligent-Tiering SSD read cache storage capacity",
        ),
    }
    if deployment_kind not in quota_names:
        raise ValueError(f"Unsupported FSx Lustre deployment kind: {deployment_kind}")
    prefix, count_quota_name, storage_quota_name = quota_names[deployment_kind]
    intelligent_tiering = deployment_kind == "persistent_intelligent_tiering"
    count_check = _check_named_service_quota(
        aws_ctx,
        check_id=f"{prefix}_filesystems",
        service_code="fsx",
        quota_name_fragments=(count_quota_name,),
        required_value=1,
        required_unit="file system",
        remediation_subject="FSx for Lustre file system count",
    )
    storage_check = _check_named_service_quota(
        aws_ctx,
        check_id=f"{prefix}_{'read_cache_storage' if intelligent_tiering else 'storage'}",
        service_code="fsx",
        quota_name_fragments=(storage_quota_name,),
        required_value=(
            required_new_read_cache_gib if intelligent_tiering else required_new_storage_gib
        ),
        required_unit="GiB",
        remediation_subject=(
            "FSx for Lustre Intelligent-Tiering SSD read cache storage capacity"
            if intelligent_tiering
            else "FSx for Lustre storage capacity"
        ),
    )
    quota_checks = [count_check, storage_check]
    throughput_check: CheckResult | None = None
    if intelligent_tiering:
        throughput_check = _check_named_service_quota(
            aws_ctx,
            check_id=f"{prefix}_throughput_capacity",
            service_code="fsx",
            quota_name_fragments=("Lustre Persistent Intelligent-Tiering throughput capacity",),
            required_value=required_new_throughput_capacity,
            required_unit="MB/s",
            remediation_subject="FSx for Lustre Intelligent-Tiering throughput capacity",
        )
        quota_checks.append(throughput_check)
    try:
        fsx = aws_ctx.client("fsx")
        paginator = fsx.get_paginator("describe_file_systems")
        all_file_systems = [
            item
            for page in paginator.paginate()
            for item in page.get("FileSystems", [])
            if item.get("FileSystemType") == "LUSTRE"
            and str(item.get("Lifecycle") or "") not in {"DELETED", "FAILED"}
        ]
    except Exception as exc:
        for check in quota_checks:
            check.details["current_used"] = None
            check.details["usage_error"] = str(exc)
            if check.status != CheckStatus.FAIL:
                check.status = CheckStatus.WARN
                check.remediation = (
                    "Grant fsx:DescribeFileSystems so current Lustre consumption can "
                    "be included in quota headroom."
                )
        return quota_checks

    usage_file_systems = [
        item for item in all_file_systems if _fsx_lustre_matches_deployment(item, deployment_kind)
    ]
    if deployment_kind in {"persistent_2", "persistent_intelligent_tiering"}:
        count_file_systems = [
            item
            for item in all_file_systems
            if str(((item.get("LustreConfiguration") or {}).get("DeploymentType") or "")).upper()
            == "PERSISTENT_2"
        ]
    else:
        count_file_systems = usage_file_systems
    current_count = len(count_file_systems)
    _apply_count_headroom(
        count_check,
        current_used=current_count,
        required_new=1,
    )
    if intelligent_tiering:
        current_storage_gib = sum(
            int(
                (
                    (item.get("LustreConfiguration") or {}).get("DataReadCacheConfiguration") or {}
                ).get("SizeGiB")
                or 0
            )
            for item in usage_file_systems
        )
    else:
        current_storage_gib = sum(
            int(item.get("StorageCapacity") or 0) for item in usage_file_systems
        )
    _apply_count_headroom(
        storage_check,
        current_used=current_storage_gib,
        required_new=(
            required_new_read_cache_gib if intelligent_tiering else required_new_storage_gib
        ),
    )
    if throughput_check is not None:
        current_throughput_capacity = sum(
            int((item.get("LustreConfiguration") or {}).get("ThroughputCapacity") or 0)
            for item in usage_file_systems
        )
        _apply_count_headroom(
            throughput_check,
            current_used=current_throughput_capacity,
            required_new=required_new_throughput_capacity,
        )
    return quota_checks


def _fsx_lustre_matches_deployment(item: dict[str, Any], deployment_kind: str) -> bool:
    configuration = item.get("LustreConfiguration") or {}
    deployment_type = str(configuration.get("DeploymentType") or "").upper()
    storage_type = str(item.get("StorageType") or "").upper()
    if deployment_kind == "scratch":
        return deployment_type.startswith("SCRATCH")
    if deployment_kind == "persistent_1":
        return deployment_type == "PERSISTENT_1"
    if deployment_kind == "persistent_2":
        return deployment_type == "PERSISTENT_2" and storage_type != "INTELLIGENT_TIERING"
    if deployment_kind == "persistent_intelligent_tiering":
        return deployment_type == "PERSISTENT_2" and storage_type == "INTELLIGENT_TIERING"
    return False


def _apply_count_headroom(
    check: CheckResult,
    *,
    current_used: int,
    required_new: int,
) -> None:
    check.details["current_used"] = current_used
    check.details["required_new"] = required_new
    quota = check.details.get("current_value")
    if quota is None:
        return
    projected = current_used + required_new
    check.details["projected_used"] = projected
    check.details["remaining_after_required"] = int(float(quota)) - projected
    if projected > float(quota):
        check.status = CheckStatus.FAIL
        check.remediation = (
            f"Current use plus demand is {projected}, above the applied quota "
            f"{check.details.get('quota_code')}={int(float(quota))}."
        )
    elif check.status != CheckStatus.WARN:
        check.status = CheckStatus.PASS
        check.remediation = ""


def _check_named_service_quota(
    aws_ctx: AWSContext,
    *,
    check_id: str,
    service_code: str,
    quota_name_fragments: tuple[str, ...],
    required_value: float,
    required_unit: str,
    remediation_subject: str,
) -> CheckResult:
    service_quotas = aws_ctx.client("service-quotas")
    try:
        quota = _find_quota_by_name(
            service_quotas,
            service_code=service_code,
            fragments=quota_name_fragments,
        )
    except Exception as exc:
        return CheckResult(
            id=check_id,
            status=CheckStatus.WARN,
            details={
                "service_code": service_code,
                "quota_name_fragments": list(quota_name_fragments),
                "required_value": required_value,
                "required_unit": required_unit,
                "error": str(exc),
            },
            remediation=(
                f"Unable to list Service Quotas for {service_code}. Grant "
                "servicequotas:ListServiceQuotas and "
                "servicequotas:ListAWSDefaultServiceQuotas, then verify "
                f"{remediation_subject} manually."
            ),
        )
    if quota is None:
        return CheckResult(
            id=check_id,
            status=CheckStatus.WARN,
            details={
                "service_code": service_code,
                "quota_name_fragments": list(quota_name_fragments),
                "required_value": required_value,
                "required_unit": required_unit,
                "found": False,
            },
            remediation=(
                f"Service Quotas did not expose a matching quota for "
                f"{remediation_subject}. Verify the required {required_value:g} "
                f"{required_unit} manually."
            ),
        )
    quota_value = float(quota.get("Value", 0))
    details = {
        "service_code": service_code,
        "quota_code": quota.get("QuotaCode", ""),
        "quota_name": quota.get("QuotaName", ""),
        "current_value": quota_value,
        "required_value": required_value,
        "required_unit": required_unit,
    }
    if required_value > quota_value:
        return CheckResult(
            id=check_id,
            status=CheckStatus.FAIL,
            details=details,
            remediation=(
                f"Request an increase for {remediation_subject}: required "
                f"{required_value:g} {required_unit}, current quota "
                f"{quota_value:g}."
            ),
        )
    return CheckResult(id=check_id, status=CheckStatus.PASS, details=details)


def _find_quota_by_name(
    service_quotas: Any,
    *,
    service_code: str,
    fragments: tuple[str, ...],
) -> Optional[dict[str, Any]]:
    lowered = tuple(fragment.lower() for fragment in fragments)
    for operation in ("list_service_quotas", "list_aws_default_service_quotas"):
        if hasattr(service_quotas, "get_paginator"):
            try:
                paginator = service_quotas.get_paginator(operation)
            except Exception:
                paginator = None
            if paginator is not None:
                for page in paginator.paginate(ServiceCode=service_code):
                    for quota in page.get("Quotas", []):
                        name = str(quota.get("QuotaName") or "").lower()
                        if all(fragment in name for fragment in lowered):
                            return quota
                continue
        response = getattr(service_quotas, operation)(ServiceCode=service_code)
        for quota in response.get("Quotas", []):
            name = str(quota.get("QuotaName") or "").lower()
            if all(fragment in name for fragment in lowered):
                return quota
    return None


def _describe_instance_vcpus(
    ec2_client: Any,
    instance_types: Iterable[str],
) -> dict[str, int]:
    unique_types = tuple(sorted({item for item in instance_types if item}))
    vcpus: dict[str, int] = {}
    for batch in _chunks(unique_types, 100):
        response = ec2_client.describe_instance_types(InstanceTypes=list(batch))
        for item in response.get("InstanceTypes", []):
            instance_type = str(item.get("InstanceType") or "")
            default_vcpus = item.get("VCpuInfo", {}).get("DefaultVCpus")
            if instance_type and default_vcpus is not None:
                vcpus[instance_type] = int(default_vcpus)
    missing = sorted(set(unique_types) - set(vcpus))
    if missing:
        raise ValueError(
            "Unable to resolve vCPU counts for instance type(s): " + ", ".join(missing)
        )
    return vcpus


def _validation_substitutions(
    cfg: Any,
    aws_ctx: AWSContext,
    cluster_name: str,
) -> dict[str, str]:
    max_8i = _int_config_value(cfg, "max_count_8I", 1)
    max_96i_nvme = _required_int_config_value(cfg, "max_count_96I_NVME")
    max_128i = _int_config_value(cfg, "max_count_128I", 1)
    max_192i = _int_config_value(cfg, "max_count_192I", 1)
    max_384i = _int_config_value(cfg, "max_count_384I", 1)
    max_count_values = {
        "max_count_8I": str(max_8i),
        "max_count_96I_NVME": str(max_96i_nvme),
        "max_count_128I": str(max_128i),
        "max_count_192I": str(max_192i),
        "max_count_384I": str(max_384i),
        "max_count_128I_C": resolve_derived_max_count(cfg, "max_count_128I_C", max_128i),
        "max_count_128I_M": resolve_derived_max_count(cfg, "max_count_128I_M", max_128i),
        "max_count_128I_R": resolve_derived_max_count(cfg, "max_count_128I_R", max_128i),
        "max_count_128I_NVME": resolve_derived_max_count(cfg, "max_count_128I_NVME", max_128i),
        "max_count_192I_C": resolve_derived_max_count(cfg, "max_count_192I_C", max_192i),
        "max_count_192I_M": resolve_derived_max_count(cfg, "max_count_192I_M", max_192i),
        "max_count_192I_R": resolve_derived_max_count(cfg, "max_count_192I_R", max_192i),
        "max_count_192I_NVME_C": resolve_derived_max_count(cfg, "max_count_192I_NVME_C", max_192i),
        "max_count_192I_NVME_M": resolve_derived_max_count(cfg, "max_count_192I_NVME_M", max_192i),
        "max_count_192I_NVME_R": resolve_derived_max_count(cfg, "max_count_192I_NVME_R", max_192i),
        "max_count_192I_HUGENVME": resolve_derived_max_count(
            cfg, "max_count_192I_HUGENVME", max_192i
        ),
        "max_count_384I_NVME_C": resolve_derived_max_count(cfg, "max_count_384I_NVME_C", max_384i),
        "max_count_384I_NVME_M": resolve_derived_max_count(cfg, "max_count_384I_NVME_M", max_384i),
        "max_count_384I_NVME_R": resolve_derived_max_count(cfg, "max_count_384I_NVME_R", max_384i),
    }
    reference = normalize_role_s3_uri(
        _effective_config_value(cfg, "reference_s3_uri", "daylily-validation-references"),
        role="reference",
    )
    control_data = normalize_role_s3_uri(
        _effective_config_value(cfg, "control_data_s3_uri", "daylily-validation-control-data"),
        role="control_data",
    )
    staging = normalize_role_s3_uri(
        _effective_config_value(cfg, "stage_s3_uri", "daylily-validation-staging"),
        role="staging",
    )
    export_destination = normalize_role_s3_uri(
        _effective_config_value(
            cfg,
            "export_destination_s3_uri",
            "daylily-validation-export",
        ),
        role="export_destination",
    )
    cluster_boot_s3_uri = f"{reference.uri.rstrip('/')}/runtime_assets/cluster_boot_config"
    substitutions = {
        "REGSUB_REGION": aws_ctx.region,
        "REGSUB_PUB_SUBNET": _effective_config_value(
            cfg,
            "public_subnet_id",
            "subnet-validation-public",
        ),
        "REGSUB_KEYNAME": "daylily-validation",
        "REGSUB_S3_BUCKET_INIT": cluster_boot_s3_uri,
        "REGSUB_S3_IAM_POLICY": _effective_config_value(
            cfg,
            "iam_policy_arn",
            f"arn:aws:iam::{aws_ctx.account_id}:policy/pclusterTagsAndBudget",
        ),
        "REGSUB_PRIVATE_SUBNET": _effective_config_value(
            cfg,
            "private_subnet_id",
            "subnet-validation-private",
        ),
        "REGSUB_S3_REFERENCE_BUCKET": reference.bucket,
        "REGSUB_S3_CONTROL_DATA_BUCKET": control_data.bucket,
        "REGSUB_S3_STAGE_BUCKET": staging.bucket,
        "REGSUB_S3_EXPORT_BUCKET": export_destination.bucket,
        "REGSUB_S3_REFERENCE_URI": reference.uri.rstrip("/"),
        "REGSUB_S3_CONTROL_DATA_URI": control_data.uri.rstrip("/"),
        "REGSUB_S3_STAGE_URI": staging.uri.rstrip("/"),
        "REGSUB_FSX_SIZE": _effective_config_value(cfg, "fsx_fs_size", "4800"),
        "REGSUB_DETAILED_MONITORING": _effective_config_value(
            cfg,
            "enable_detailed_monitoring",
            "false",
        ),
        "REGSUB_CLUSTER_NAME": cluster_name,
        "REGSUB_USERNAME": "daylily-validation",
        "REGSUB_PROJECT": cluster_name,
        "REGSUB_DELETE_LOCAL_ROOT": _effective_config_value(
            cfg,
            "delete_local_root",
            "true",
        ),
        "REGSUB_DRAGEN_PCLUSTER_AMI": _effective_config_value(
            cfg,
            "dragen_pcluster_ami",
            "",
        ),
        "REGSUB_SAVE_FSX": _effective_config_value(cfg, "auto_delete_fsx", "Delete"),
        "REGSUB_ENFORCE_BUDGET": normalize_enforce_budget(
            _effective_config_value(cfg, "enforce_budget", "true")
        ),
        "REGSUB_COST_CENTER_REGION": "us-west-2",
        "REGSUB_COST_CENTER_TABLE": "dayec-cost-centers",
        "REGSUB_COST_CENTER_USAGE_TABLE": "dayec-cost-center-usage",
        "REGSUB_AWS_ACCOUNT_ID": aws_ctx.account_id,
        "REGSUB_ALLOCATION_STRATEGY": _effective_config_value(
            cfg,
            "spot_instance_allocation_strategy",
            "price-capacity-optimized",
        ),
        "REGSUB_DAYLILY_GIT_DEETS": "aws-validate",
        "REGSUB_MAX_COUNT_8I": max_count_values["max_count_8I"],
        "REGSUB_MAX_COUNT_96I_NVME": max_count_values["max_count_96I_NVME"],
        "REGSUB_MAX_COUNT_128I": max_count_values["max_count_128I"],
        "REGSUB_MAX_COUNT_192I": max_count_values["max_count_192I"],
        "REGSUB_MAX_COUNT_384I": max_count_values["max_count_384I"],
        "REGSUB_MAX_COUNT_128I_C": max_count_values["max_count_128I_C"],
        "REGSUB_MAX_COUNT_128I_M": max_count_values["max_count_128I_M"],
        "REGSUB_MAX_COUNT_128I_R": max_count_values["max_count_128I_R"],
        "REGSUB_MAX_COUNT_128I_NVME": max_count_values["max_count_128I_NVME"],
        "REGSUB_MAX_COUNT_192I_C": max_count_values["max_count_192I_C"],
        "REGSUB_MAX_COUNT_192I_M": max_count_values["max_count_192I_M"],
        "REGSUB_MAX_COUNT_192I_R": max_count_values["max_count_192I_R"],
        "REGSUB_MAX_COUNT_192I_NVME_C": max_count_values["max_count_192I_NVME_C"],
        "REGSUB_MAX_COUNT_192I_NVME_M": max_count_values["max_count_192I_NVME_M"],
        "REGSUB_MAX_COUNT_192I_NVME_R": max_count_values["max_count_192I_NVME_R"],
        "REGSUB_MAX_COUNT_192I_HUGENVME": max_count_values["max_count_192I_HUGENVME"],
        "REGSUB_MAX_COUNT_384I_NVME_C": max_count_values["max_count_384I_NVME_C"],
        "REGSUB_MAX_COUNT_384I_NVME_M": max_count_values["max_count_384I_NVME_M"],
        "REGSUB_MAX_COUNT_384I_NVME_R": max_count_values["max_count_384I_NVME_R"],
        "REGSUB_HEADNODE_INSTANCE_TYPE": _effective_config_value(
            cfg,
            "headnode_instance_type",
            "r7i.2xlarge",
        ),
        "REGSUB_HEARTBEAT_EMAIL": _effective_config_value(
            cfg,
            "heartbeat_email",
            "daylily-validation@example.invalid",
        ),
        "REGSUB_HEARTBEAT_SCHEDULE": _effective_config_value(
            cfg,
            "heartbeat_schedule",
            "rate(60 minutes)",
        ),
        "REGSUB_HEARTBEAT_SCHEDULER_ROLE_ARN": _effective_config_value(
            cfg,
            "heartbeat_scheduler_role_arn",
            f"arn:aws:iam::{aws_ctx.account_id}:role/daylily-validation-scheduler",
        ),
    }
    return {key: str(substitutions.get(key, "")) for key in ALL_SUBSTITUTION_KEYS}


def _effective_config_value(cfg: Any, key: str, fallback: str = "") -> str:
    triplet = cfg.ephemeral_cluster.config.get(key)
    resolved = resolve_value(triplet) if triplet is not None else ""
    if resolved:
        return resolved
    return get_effective_default(cfg, key, fallback) or fallback


def _int_config_value(cfg: Any, key: str, fallback: int) -> int:
    value = _effective_config_value(cfg, key, str(fallback))
    return _coerce_nonnegative_int(value, key)


def _required_int_config_value(cfg: Any, key: str) -> int:
    value = _effective_config_value(cfg, key, "")
    if not value:
        raise ValueError(f"Missing required configuration value: {key}")
    return _coerce_nonnegative_int(value, key)


def _resolve_config_path(config_path: Optional[str]) -> Path:
    return _resolve_data_path(config_path or DEFAULT_CONFIG_PATH)


def _resolve_data_path(path: str) -> Path:
    candidate = Path(path).expanduser()
    if candidate.is_file():
        return candidate
    if not candidate.is_absolute():
        try:
            return resource_path(path)
        except FileNotFoundError:
            pass
    raise FileNotFoundError(f"File not found: {path}")


def _coerce_positive_int(value: Any, label: str) -> int:
    result = _coerce_nonnegative_int(value, label)
    if result <= 0:
        raise ValueError(f"{label} must be greater than zero.")
    return result


def _coerce_nonnegative_int(value: Any, label: str) -> int:
    try:
        result = int(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be an integer, got {value!r}.") from exc
    if result < 0:
        raise ValueError(f"{label} must not be negative.")
    return result


def _chunks(values: Iterable[str], size: int) -> Iterable[tuple[str, ...]]:
    batch: list[str] = []
    for value in values:
        batch.append(value)
        if len(batch) >= size:
            yield tuple(batch)
            batch = []
    if batch:
        yield tuple(batch)


def _report_area(check_id: str) -> str:
    prefix = check_id.split(".", maxsplit=1)[0]
    return {
        "aws": "Identity",
        "iam": "Permissions",
        "ssm": "Permissions",
        "budget": "Budget readiness",
        "cost_centers": "Cost-center readiness",
        "cost_control": "CUR and cost readiness",
        "slurm_accounting": "Slurm accounting",
        "quota": "Quotas and headroom",
    }.get(prefix, "Readiness")


def _finalize_summary(report: AwsValidationReport) -> None:
    counts = Counter(check.status.value for check in report.checks)
    report.summary = {
        "PASS": counts.get("PASS", 0),
        "WARN": counts.get("WARN", 0),
        "FAIL": counts.get("FAIL", 0),
    }
