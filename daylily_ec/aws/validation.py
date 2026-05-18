"""Read-only AWS readiness validation for Daylily ephemeral clusters."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Callable, Iterable, Literal, Optional

from pydantic import Field
import yaml

from daylily_ec.aws.cloudformation import derive_stack_name, describe_stack_status
from daylily_ec.aws.context import AWSContext, parse_region_az
from daylily_ec.aws.iam import (
    PCLUSTER_OMICS_POLICY_NAME,
    check_daylily_policies,
)
from daylily_ec.aws.quotas import (
    QUOTA_DEFS,
    _fetch_quota_value,
    check_all_quotas,
)
from daylily_ec.config.triplets import get_effective_default, load_config, resolve_value
from daylily_ec.render.renderer import ALL_SUBSTITUTION_KEYS, render_template
from daylily_ec.resources import resource_path
from daylily_ec.state.models import CheckResult, CheckStatus, PreflightReport
from daylily_ec.workflow.create_cluster import (
    EXIT_SUCCESS,
    EXIT_VALIDATION_FAILURE,
)

ValidationMode = Literal["permissions", "quotas", "all"]
SUPPORTED_MODES: tuple[str, ...] = ("permissions", "quotas", "all")
DEFAULT_CONFIG_PATH = "config/daylily_ephemeral_cluster_template.yaml"
DEFAULT_CLUSTER_TEMPLATE_PATH = "config/day_cluster/prod_cluster.yaml"
SSM_SESSION_DOCUMENT = "SSM-SessionManagerRunShell"


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
    fsx_storage_gib: int
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
            "fsx_storage_gib": self.fsx_storage_gib,
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
    cfg = None
    config_path = ""
    cluster_name = ""
    if options.config_path is not None:
        config_path = str(_resolve_config_path(options.config_path))
    if options.mode in ("quotas", "all"):
        if not config_path:
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
        report.checks.extend(run_permission_checks(aws_ctx))
    if options.mode in ("quotas", "all"):
        if cfg is None:
            raise AwsValidationError("Internal error: quota validation missing config.")
        report.checks.extend(run_quota_checks(aws_ctx, cfg, config_path=config_path))

    _finalize_summary(report)
    if options.gap_analysis_path is not None:
        write_gap_analysis(report, options.gap_analysis_path)

    return (
        EXIT_SUCCESS if report.ready else EXIT_VALIDATION_FAILURE,
        report,
    )


def run_permission_checks(aws_ctx: AWSContext) -> list[CheckResult]:
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
    checks.extend(simulate_required_permissions(aws_ctx, iam_client))
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
                "The document must run shell sessions as ubuntu in a login shell."
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
                "preferences that run as ubuntu."
            ),
        )

    inputs = payload.get("inputs", {}) if isinstance(payload, dict) else {}
    shell_profile = inputs.get("shellProfile", {}) if isinstance(inputs, dict) else {}
    linux_shell_profile = ""
    if isinstance(shell_profile, dict):
        linux_shell_profile = str(shell_profile.get("linux") or "")
    run_as_enabled = inputs.get("runAsEnabled") is True if isinstance(inputs, dict) else False
    run_as_user = str(inputs.get("runAsDefaultUser") or "") if isinstance(inputs, dict) else ""
    login_shell_ok = any(
        marker in linux_shell_profile
        for marker in ("bash -l", ".bash_profile", "daylily-headnode-bootstrap.sh")
    )

    details = {
        "document": SSM_SESSION_DOCUMENT,
        "runAsEnabled": run_as_enabled,
        "runAsDefaultUser": run_as_user,
        "shellProfileLinux": linux_shell_profile,
    }
    if run_as_enabled and run_as_user == "ubuntu" and login_shell_ok:
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
            "runAsDefaultUser is ubuntu, and shellProfile.linux enters a bash "
            "login shell."
        ),
    )


def simulate_required_permissions(
    aws_ctx: AWSContext,
    iam_client: Any,
) -> list[CheckResult]:
    """Use IAM policy simulation to validate Daylily and ParallelCluster actions."""

    if aws_ctx.iam_username == "root":
        return [
            CheckResult(
                id="iam.simulation.root",
                status=CheckStatus.PASS,
                details={"note": "root account has implicit full access"},
            )
        ]

    checks: list[CheckResult] = []
    principal_arn = _simulation_source_arn(aws_ctx.caller_arn, aws_ctx.account_id)
    for group in _permission_groups(aws_ctx):
        try:
            results = _simulate_group(iam_client, principal_arn, group)
        except Exception as exc:
            checks.append(
                CheckResult(
                    id="iam.simulation",
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
            return checks

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
    max_128i = _int_config_value(cfg, "max_count_128I", 1)
    max_192i = _int_config_value(cfg, "max_count_192I", 1)
    checks = check_all_quotas(
        aws_ctx,
        max_count_8i=max_8i,
        max_count_128i=max_128i,
        max_count_192i=max_192i,
        non_interactive=True,
    )
    checks.append(_check_baseline_stack_presence(aws_ctx))

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
    checks.extend(_check_rendered_vcpu_quotas(aws_ctx, shape))
    checks.append(_check_instance_type_offerings(aws_ctx, shape))
    checks.append(_check_spot_market_signal(aws_ctx, shape))
    checks.extend(_check_storage_quotas(aws_ctx, shape))
    return checks


def render_effective_cluster_yaml(cfg: Any, aws_ctx: AWSContext) -> tuple[str, Path, str]:
    """Render the configured ParallelCluster template without writing files."""

    cluster_name = _effective_config_value(cfg, "cluster_name", "prod") or "prod"
    template_value = (
        _effective_config_value(
            cfg,
            "cluster_template_yaml",
            DEFAULT_CLUSTER_TEMPLATE_PATH,
        )
        or DEFAULT_CLUSTER_TEMPLATE_PATH
    )
    template_path = _resolve_data_path(template_value)
    substitutions = _validation_substitutions(cfg, aws_ctx, cluster_name)
    template_text = template_path.read_text(encoding="utf-8")
    return (
        render_template(
            template_text,
            substitutions,
            required_keys=ALL_SUBSTITUTION_KEYS,
        ),
        template_path,
        cluster_name,
    )


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
    if isinstance(shared_storage, list):
        for storage in shared_storage:
            if not isinstance(storage, dict):
                continue
            if str(storage.get("StorageType") or "") != "FsxLustre":
                continue
            fsx_settings = storage.get("FsxLustreSettings") or {}
            if not isinstance(fsx_settings, dict):
                continue
            fsx_storage_gib = _coerce_positive_int(
                fsx_settings.get("StorageCapacity", 0),
                "SharedStorage.FsxLustreSettings.StorageCapacity",
            )
            fsx_deployment_type = str(fsx_settings.get("DeploymentType") or "").strip()
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
        fsx_storage_gib=fsx_storage_gib,
        compute_resources=tuple(compute_demands),
        vcpus_by_instance_type=vcpus_by_type,
    )


def write_gap_analysis(report: AwsValidationReport, path: Path) -> None:
    """Write an AWS-admin oriented Markdown gap analysis report."""

    path = Path(path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    gaps = [check for check in report.checks if check.status != CheckStatus.PASS]
    passing = [check for check in report.checks if check.status == CheckStatus.PASS]
    lines = [
        "# Daylily AWS Validation Gap Analysis",
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
        ]
    )
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
                    json.dumps(check.details, indent=2, sort_keys=True),
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
                    json.dumps(check.details, indent=2, sort_keys=True),
                    "```",
                    "",
                ]
            )
    path.write_text("\n".join(lines), encoding="utf-8")


def _permission_groups(aws_ctx: AWSContext) -> tuple[PermissionGroup, ...]:
    account = aws_ctx.account_id
    region = aws_ctx.region
    service_linked_services = (
        "spot.amazonaws.com",
        "fsx.amazonaws.com",
        "s3.data-source.lustre.fsx.amazonaws.com",
        "imagebuilder.amazonaws.com",
        "ec2.amazonaws.com",
        "lambda.amazonaws.com",
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
                "ec2:DescribeSubnets",
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
            ),
        ),
        PermissionGroup(
            "sns",
            "SNS topic integration",
            (
                "sns:CreateTopic",
                "sns:GetTopicAttributes",
                "sns:SetTopicAttributes",
                "sns:Subscribe",
                "sns:Unsubscribe",
                "sns:Publish",
                "sns:DeleteTopic",
            ),
            (f"arn:aws:sns:{region}:{account}:daylily-validation-topic",),
        ),
        PermissionGroup(
            "scheduler",
            "EventBridge Scheduler integration",
            (
                "scheduler:CreateSchedule",
                "scheduler:GetSchedule",
                "scheduler:ListSchedules",
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
                "secretsmanager:GetSecretValue",
                "secretsmanager:DeleteSecret",
                "ecr:GetAuthorizationToken",
                "ecr:DescribeRepositories",
                "ecr:CreateRepository",
                "ecr:DeleteRepository",
                "cognito-idp:ListUserPools",
                "elasticfilesystem:DescribeFileSystems",
            ),
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


def _check_baseline_stack_presence(aws_ctx: AWSContext) -> CheckResult:
    stack_name = derive_stack_name(aws_ctx.region_az)
    status = describe_stack_status(aws_ctx.client("cloudformation"), stack_name)
    if status:
        return CheckResult(
            id="quota.network.baseline_stack",
            status=CheckStatus.PASS,
            details={"stack_name": stack_name, "stack_status": status},
        )
    return CheckResult(
        id="quota.network.baseline_stack",
        status=CheckStatus.WARN,
        details={
            "stack_name": stack_name,
            "stack_status": None,
            "network_quota_checks": [q.check_id for q in QUOTA_DEFS if q.service_code == "vpc"],
        },
        remediation=(
            "Baseline network stack is absent or unreadable. Ensure VPC, NAT "
            "Gateway, Elastic IP, and Internet Gateway quotas can support the "
            "first Daylily stack in this AZ."
        ),
    )


def _check_rendered_vcpu_quotas(
    aws_ctx: AWSContext,
    shape: ClusterShape,
) -> list[CheckResult]:
    service_quotas = aws_ctx.client("service-quotas")
    checks: list[CheckResult] = []
    for check_id, label, quota_code, demand in (
        (
            "quota.rendered_ondemand_vcpu",
            "On-Demand vCPU Max",
            "L-1216C47A",
            shape.rendered_ondemand_vcpus,
        ),
        (
            "quota.rendered_spot_vcpu",
            "Spot vCPU Max",
            "L-34B43A08",
            shape.rendered_spot_vcpus,
        ),
    ):
        quota_value = _fetch_quota_value(service_quotas, "ec2", quota_code)
        details = {
            "quota_code": quota_code,
            "service_code": "ec2",
            "quota_name": label,
            "rendered_demand_vcpus": demand,
            "current_value": quota_value,
            "cluster_shape": shape.to_details(),
        }
        if quota_value is None:
            checks.append(
                CheckResult(
                    id=check_id,
                    status=CheckStatus.WARN,
                    details=details,
                    remediation=(
                        f"Unable to read EC2 quota {quota_code} for {label}. "
                        "Grant servicequotas:GetServiceQuota or check the quota manually."
                    ),
                )
            )
            continue
        if demand >= quota_value:
            checks.append(
                CheckResult(
                    id=check_id,
                    status=CheckStatus.FAIL,
                    details=details,
                    remediation=(
                        f"Rendered cluster demand requires {demand} {label} vCPUs, "
                        f"but quota {quota_code} is {int(quota_value)}. Request an "
                        "increase or reduce the configured queue MaxCount values."
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
) -> list[CheckResult]:
    checks: list[CheckResult] = []
    if shape.headnode_root_volume_type == "gp3":
        checks.append(
            _check_named_service_quota(
                aws_ctx,
                check_id="quota.ebs.gp3_storage",
                service_code="ebs",
                quota_name_fragments=("Storage for General Purpose SSD (gp3) volumes",),
                required_value=shape.headnode_root_volume_gib / 1024,
                required_unit="TiB",
                remediation_subject="EBS gp3 regional storage",
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
                    "note": "cluster template does not request gp3 root volume",
                },
            )
        )

    if shape.fsx_deployment_type.startswith("SCRATCH"):
        checks.append(
            _check_named_service_quota(
                aws_ctx,
                check_id="quota.fsx.lustre_scratch_filesystems",
                service_code="fsx",
                quota_name_fragments=("Lustre Scratch file systems",),
                required_value=1,
                required_unit="file system",
                remediation_subject="FSx for Lustre Scratch file system count",
            )
        )
        checks.append(
            _check_named_service_quota(
                aws_ctx,
                check_id="quota.fsx.lustre_scratch_storage",
                service_code="fsx",
                quota_name_fragments=("Lustre Scratch storage capacity",),
                required_value=shape.fsx_storage_gib,
                required_unit="GiB",
                remediation_subject="FSx for Lustre Scratch storage capacity",
            )
        )
    elif shape.fsx_storage_gib > 0:
        checks.append(
            _check_named_service_quota(
                aws_ctx,
                check_id="quota.fsx.lustre_storage",
                service_code="fsx",
                quota_name_fragments=("Lustre", "storage capacity"),
                required_value=shape.fsx_storage_gib,
                required_unit="GiB",
                remediation_subject="FSx for Lustre storage capacity",
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
    bucket = _effective_config_value(cfg, "s3_bucket_name", "daylily-validation-bucket")
    bucket_url = f"s3://{bucket}" if bucket else "s3://daylily-validation-bucket"
    substitutions = {
        "REGSUB_REGION": aws_ctx.region,
        "REGSUB_PUB_SUBNET": _effective_config_value(
            cfg,
            "public_subnet_id",
            "subnet-validation-public",
        ),
        "REGSUB_KEYNAME": "daylily-validation",
        "REGSUB_S3_BUCKET_INIT": bucket_url,
        "REGSUB_S3_BUCKET_NAME": bucket or "daylily-validation-bucket",
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
        "REGSUB_S3_BUCKET_REF": bucket_url,
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
        "REGSUB_SAVE_FSX": _effective_config_value(cfg, "auto_delete_fsx", "Delete"),
        "REGSUB_ENFORCE_BUDGET": _effective_config_value(cfg, "enforce_budget", "skip"),
        "REGSUB_AWS_ACCOUNT_ID": aws_ctx.account_id,
        "REGSUB_ALLOCATION_STRATEGY": _effective_config_value(
            cfg,
            "spot_instance_allocation_strategy",
            "price-capacity-optimized",
        ),
        "REGSUB_DAYLILY_GIT_DEETS": "aws-validate",
        "REGSUB_MAX_COUNT_8I": _effective_config_value(cfg, "max_count_8I", "1"),
        "REGSUB_MAX_COUNT_128I": _effective_config_value(cfg, "max_count_128I", "1"),
        "REGSUB_MAX_COUNT_192I": _effective_config_value(cfg, "max_count_192I", "1"),
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


def _finalize_summary(report: AwsValidationReport) -> None:
    counts = Counter(check.status.value for check in report.checks)
    report.summary = {
        "PASS": counts.get("PASS", 0),
        "WARN": counts.get("WARN", 0),
        "FAIL": counts.get("FAIL", 0),
    }
