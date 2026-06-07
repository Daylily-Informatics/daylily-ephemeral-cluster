from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from daylily_ec.aws.validation import (
    AwsValidationOptions,
    ClusterShape,
    ComputeResourceDemand,
    PermissionGroup,
    _check_baseline_stack_presence,
    _check_instance_type_offerings,
    _check_named_service_quota,
    _check_rendered_vcpu_quotas,
    _check_spot_market_signal,
    _check_storage_quotas,
    _chunks,
    _coerce_nonnegative_int,
    _coerce_positive_int,
    _decode_ssm_document,
    _describe_instance_vcpus,
    _find_quota_by_name,
    _finalize_summary,
    _simulate_group,
    _simulation_source_arn,
    check_pcluster_omics_policy_exists,
    check_ssm_session_document,
    extract_cluster_shape,
    run_permission_checks,
    run_quota_checks,
    simulate_required_permissions,
    write_gap_analysis,
)
import daylily_ec.aws.validation as validation_module
from daylily_ec.aws.validation import AwsValidationReport
from daylily_ec.state.models import CheckResult, CheckStatus


class _Paginator:
    def __init__(self, pages):
        self.pages = pages

    def paginate(self, **_kwargs):
        return list(self.pages)


class _Clients(SimpleNamespace):
    def client(self, service):
        return getattr(self, service.replace("-", "_"))


def _shape(
    *,
    headnode_root_volume_type: str = "gp3",
    fsx_deployment_type: str = "SCRATCH_2",
    fsx_storage_gib: int = 4800,
    spot_count: int = 2,
) -> ClusterShape:
    return ClusterShape(
        cluster_name="validation",
        template_path="cluster.yaml",
        headnode_instance_type="r7i.2xlarge",
        headnode_vcpus=8,
        headnode_root_volume_type=headnode_root_volume_type,
        headnode_root_volume_gib=512,
        fsx_deployment_type=fsx_deployment_type,
        fsx_storage_gib=fsx_storage_gib,
        compute_resources=(
            ComputeResourceDemand(
                queue="spot",
                capacity_type="SPOT",
                name="r7",
                max_count=spot_count,
                instance_types=("r7i.2xlarge",),
                max_vcpus_per_instance=8,
                demand_vcpus=spot_count * 8,
            ),
            ComputeResourceDemand(
                queue="on",
                capacity_type="ONDEMAND",
                name="c7",
                max_count=1,
                instance_types=("c7i.48xlarge",),
                max_vcpus_per_instance=192,
                demand_vcpus=192,
            ),
        ),
        vcpus_by_instance_type={"r7i.2xlarge": 8, "c7i.48xlarge": 192},
    )


def test_options_reject_default_profile() -> None:
    with pytest.raises(RuntimeError, match="default"):
        AwsValidationOptions(
            mode="permissions",
            profile="default",
            region_az="us-west-2b",
        )


def test_pcluster_omics_policy_check_is_read_only() -> None:
    iam = MagicMock()
    iam.get_paginator.return_value = _Paginator([{"Policies": []}])

    result = check_pcluster_omics_policy_exists(iam)

    assert result.status == CheckStatus.FAIL
    iam.get_paginator.assert_called_once_with("list_policies")
    assert not iam.create_policy.called
    assert not iam.create_policy_version.called


def test_ssm_session_document_detects_wrong_run_as_user() -> None:
    ssm = MagicMock()
    ssm.get_document.return_value = {
        "Content": json.dumps(
            {
                "inputs": {
                    "runAsEnabled": True,
                    "runAsDefaultUser": "root",
                    "shellProfile": {"linux": "bash -l"},
                }
            }
        )
    }

    result = check_ssm_session_document(ssm)

    assert result.status == CheckStatus.FAIL
    assert result.details["runAsDefaultUser"] == "root"
    assert "ubuntu" in result.remediation


def test_ssm_session_document_accepts_supported_login_shell() -> None:
    ssm = MagicMock()
    ssm.get_document.return_value = {
        "Content": {
            "inputs": {
                "runAsEnabled": True,
                "runAsDefaultUser": "ubuntu",
                "shellProfile": {"linux": "cd ~ && exec bash -l"},
            }
        }
    }

    result = check_ssm_session_document(ssm)

    assert result.status == CheckStatus.PASS
    assert result.details["runAsDefaultUser"] == "ubuntu"


def test_ssm_session_document_reports_read_and_decode_errors() -> None:
    missing = MagicMock()
    missing.get_document.side_effect = RuntimeError("denied")
    assert check_ssm_session_document(missing).status == CheckStatus.FAIL

    invalid = MagicMock()
    invalid.get_document.return_value = {"Content": "[not-json"}
    result = check_ssm_session_document(invalid)
    assert result.status == CheckStatus.FAIL
    assert "valid JSON" in result.remediation


def test_pcluster_omics_policy_check_passes_and_reports_api_error() -> None:
    found = MagicMock()
    found.get_paginator.return_value = _Paginator(
        [{"Policies": [{"PolicyName": "pcluster-omics-analysis", "Arn": "arn:policy"}]}]
    )
    assert check_pcluster_omics_policy_exists(found).status == CheckStatus.PASS

    broken = MagicMock()
    broken.get_paginator.side_effect = RuntimeError("list failed")
    result = check_pcluster_omics_policy_exists(broken)
    assert result.status == CheckStatus.FAIL
    assert "list failed" in result.details["error"]


def test_simulation_reports_denied_action() -> None:
    class FakeIam:
        def simulate_principal_policy(self, **kwargs):
            return {
                "EvaluationResults": [
                    {
                        "EvalActionName": action,
                        "EvalResourceName": kwargs["ResourceArns"][0],
                        "EvalDecision": (
                            "explicitDeny" if action == "ec2:RunInstances" else "allowed"
                        ),
                    }
                    for action in kwargs["ActionNames"]
                ],
                "IsTruncated": False,
            }

    ctx = SimpleNamespace(
        account_id="123456789012",
        region="us-west-2",
        caller_arn="arn:aws:iam::123456789012:user/alice",
        iam_username="alice",
    )

    results = simulate_required_permissions(ctx, FakeIam())

    failed = [result for result in results if result.status == CheckStatus.FAIL]
    assert any(result.id == "iam.simulation.ec2_network_compute" for result in failed)
    assert "ec2:RunInstances" in failed[0].details["denied_actions"]


def test_simulation_root_allowed_and_api_error_short_circuits() -> None:
    root_ctx = SimpleNamespace(
        account_id="123456789012",
        region="us-west-2",
        caller_arn="arn:aws:iam::123456789012:root",
        iam_username="root",
    )
    assert simulate_required_permissions(root_ctx, MagicMock())[0].status == CheckStatus.PASS

    class BrokenIam:
        def simulate_principal_policy(self, **_kwargs):
            raise RuntimeError("cannot simulate")

    user_ctx = SimpleNamespace(
        account_id="123456789012",
        region="us-west-2",
        caller_arn="arn:aws:iam::123456789012:user/alice",
        iam_username="alice",
    )
    result = simulate_required_permissions(user_ctx, BrokenIam())[0]
    assert result.status == CheckStatus.FAIL
    assert result.details["error"] == "cannot simulate"


def test_simulate_group_paginates_and_context_entries() -> None:
    calls = []

    class PaginatingIam:
        def simulate_principal_policy(self, **kwargs):
            calls.append(kwargs)
            if "Marker" not in kwargs:
                return {
                    "EvaluationResults": [{"EvalActionName": "iam:CreateServiceLinkedRole"}],
                    "IsTruncated": True,
                    "Marker": "next",
                }
            return {
                "EvaluationResults": [{"EvalActionName": "iam:PassRole"}],
                "IsTruncated": False,
            }

    group = PermissionGroup(
        "ctx",
        "context group",
        ("iam:CreateServiceLinkedRole", "iam:PassRole"),
        ("*",),
        (("iam:AWSServiceName", ("spot.amazonaws.com",)),),
    )

    results = _simulate_group(PaginatingIam(), "arn:aws:iam::123456789012:user/alice", group)

    assert [result["EvalActionName"] for result in results] == [
        "iam:CreateServiceLinkedRole",
        "iam:PassRole",
    ]
    assert calls[0]["ContextEntries"][0]["ContextKeyValues"] == ["spot.amazonaws.com"]
    assert calls[1]["Marker"] == "next"


def test_simulation_source_arn_converts_assumed_role() -> None:
    assert _simulation_source_arn(
        "arn:aws:sts::123456789012:assumed-role/DayRole/session",
        "123456789012",
    ) == "arn:aws:iam::123456789012:role/DayRole"
    assert _simulation_source_arn(
        "arn:aws:iam::123456789012:user/alice",
        "123456789012",
    ) == "arn:aws:iam::123456789012:user/alice"


def test_decode_ssm_document_rejects_non_objects() -> None:
    assert _decode_ssm_document({"inputs": {}}) == {"inputs": {}}
    with pytest.raises(ValueError, match="not JSON text"):
        _decode_ssm_document(42)
    with pytest.raises(ValueError, match="JSON object"):
        _decode_ssm_document("[]")


def test_extract_cluster_shape_uses_rendered_queue_demand() -> None:
    rendered_yaml = """
Region: us-west-2
HeadNode:
  InstanceType: r7i.2xlarge
  LocalStorage:
    RootVolume:
      Size: 421
      VolumeType: gp3
Scheduling:
  Scheduler: slurm
  SlurmQueues:
    - Name: i8
      CapacityType: SPOT
      ComputeResources:
        - Name: r7
          Instances:
            - InstanceType: r7i.2xlarge
          MaxCount: 2
    - Name: on
      CapacityType: ONDEMAND
      ComputeResources:
        - Name: c7
          Instances:
            - InstanceType: c7i.48xlarge
          MaxCount: 1
SharedStorage:
  - Name: fsx-test
    StorageType: FsxLustre
    FsxLustreSettings:
      StorageCapacity: 4800
      DeploymentType: SCRATCH_2
"""

    class FakeEc2:
        def describe_instance_types(self, InstanceTypes):
            values = {"r7i.2xlarge": 8, "c7i.48xlarge": 192}
            return {
                "InstanceTypes": [
                    {
                        "InstanceType": instance_type,
                        "VCpuInfo": {"DefaultVCpus": values[instance_type]},
                    }
                    for instance_type in InstanceTypes
                ]
            }

    ctx = SimpleNamespace(client=lambda service: FakeEc2())

    shape = extract_cluster_shape(
        rendered_yaml,
        ctx,
        cluster_name="validation",
        template_path="cluster.yaml",
    )

    assert shape.rendered_spot_vcpus == 16
    assert shape.rendered_ondemand_vcpus == 200
    assert shape.fsx_storage_gib == 4800
    assert shape.headnode_root_volume_type == "gp3"


def test_run_permission_checks_uses_only_read_only_checks(monkeypatch) -> None:
    iam = MagicMock()
    ssm = MagicMock()
    ctx = _Clients(
        iam=iam,
        ssm=ssm,
        iam_username="alice",
        region="us-west-2",
        account_id="123456789012",
        caller_arn="arn:aws:iam::123456789012:user/alice",
    )
    monkeypatch.setattr(
        validation_module,
        "check_daylily_policies",
        lambda *_args, **_kwargs: [
            CheckResult(id="iam.daylily", status=CheckStatus.PASS, details={})
        ],
    )
    monkeypatch.setattr(
        validation_module,
        "check_pcluster_omics_policy_exists",
        lambda _client: CheckResult(id="iam.pcluster", status=CheckStatus.PASS, details={}),
    )
    monkeypatch.setattr(
        validation_module,
        "check_ssm_session_document",
        lambda _client: CheckResult(id="ssm.document", status=CheckStatus.PASS, details={}),
    )
    monkeypatch.setattr(
        validation_module,
        "simulate_required_permissions",
        lambda *_args: [CheckResult(id="iam.sim", status=CheckStatus.PASS, details={})],
    )

    checks = run_permission_checks(ctx)

    assert [check.id for check in checks] == [
        "iam.daylily",
        "iam.pcluster",
        "ssm.document",
        "iam.sim",
    ]
    assert not iam.create_policy.called


def test_run_quota_checks_covers_success_and_render_error(monkeypatch) -> None:
    cfg = SimpleNamespace(ephemeral_cluster=SimpleNamespace(config={}, template_defaults={}))
    ctx = _Clients(region_az="us-west-2d")
    shape = _shape()
    monkeypatch.setattr(
        validation_module,
        "check_all_quotas",
        lambda *_args, **_kwargs: [
            CheckResult(id="quota.base", status=CheckStatus.PASS, details={})
        ],
    )
    monkeypatch.setattr(
        validation_module,
        "_check_baseline_stack_presence",
        lambda _ctx: CheckResult(id="quota.stack", status=CheckStatus.PASS, details={}),
    )
    monkeypatch.setattr(
        validation_module,
        "render_effective_cluster_yaml",
        lambda *_args: ("yaml", "cluster.yaml", "validation"),
    )
    monkeypatch.setattr(validation_module, "extract_cluster_shape", lambda *_args, **_kwargs: shape)
    monkeypatch.setattr(
        validation_module,
        "_check_rendered_vcpu_quotas",
        lambda *_args: [CheckResult(id="quota.vcpu", status=CheckStatus.PASS, details={})],
    )
    monkeypatch.setattr(
        validation_module,
        "_check_instance_type_offerings",
        lambda *_args: CheckResult(id="quota.offerings", status=CheckStatus.PASS, details={}),
    )
    monkeypatch.setattr(
        validation_module,
        "_check_spot_market_signal",
        lambda *_args: CheckResult(id="quota.spot", status=CheckStatus.PASS, details={}),
    )
    monkeypatch.setattr(
        validation_module,
        "_check_storage_quotas",
        lambda *_args: [CheckResult(id="quota.storage", status=CheckStatus.PASS, details={})],
    )

    checks = run_quota_checks(ctx, cfg, config_path="config.yaml")

    assert [check.id for check in checks] == [
        "quota.base",
        "quota.stack",
        "quota.cluster_shape",
        "quota.vcpu",
        "quota.offerings",
        "quota.spot",
        "quota.storage",
    ]

    monkeypatch.setattr(
        validation_module,
        "render_effective_cluster_yaml",
        lambda *_args: (_ for _ in ()).throw(ValueError("bad template")),
    )
    checks = run_quota_checks(ctx, cfg, config_path="config.yaml")
    assert checks[-1].id == "quota.cluster_shape"
    assert checks[-1].status == CheckStatus.FAIL
    assert "bad template" in checks[-1].details["error"]


def test_baseline_stack_presence_pass_and_warn(monkeypatch) -> None:
    ctx = _Clients(region_az="us-west-2d", cloudformation=MagicMock())
    monkeypatch.setattr(validation_module, "describe_stack_status", lambda *_args: "CREATE_COMPLETE")
    assert _check_baseline_stack_presence(ctx).status == CheckStatus.PASS

    monkeypatch.setattr(validation_module, "describe_stack_status", lambda *_args: None)
    result = _check_baseline_stack_presence(ctx)
    assert result.status == CheckStatus.WARN
    assert result.details["stack_name"] == "pcluster-vpc-stack-2d"


def test_rendered_vcpu_quotas_cover_pass_fail_and_warn(monkeypatch) -> None:
    ctx = _Clients(service_quotas=MagicMock())
    values = {"L-1216C47A": 500, "L-34B43A08": 10}
    monkeypatch.setattr(
        validation_module,
        "_fetch_quota_value",
        lambda _client, _service, quota_code: values[quota_code],
    )
    checks = _check_rendered_vcpu_quotas(ctx, _shape(spot_count=2))
    assert checks[0].status == CheckStatus.PASS
    assert checks[1].status == CheckStatus.FAIL

    monkeypatch.setattr(validation_module, "_fetch_quota_value", lambda *_args: None)
    checks = _check_rendered_vcpu_quotas(ctx, _shape())
    assert {check.status for check in checks} == {CheckStatus.WARN}


def test_instance_type_offerings_cover_pass_missing_and_error() -> None:
    class OfferingEc2:
        def __init__(self, offered):
            self.offered = offered

        def get_paginator(self, _name):
            return _Paginator(
                [
                    {
                        "InstanceTypeOfferings": [
                            {"InstanceType": instance_type} for instance_type in self.offered
                        ]
                    }
                ]
            )

    ctx = _Clients(region_az="us-west-2d", ec2=OfferingEc2(["c7i.48xlarge", "r7i.2xlarge"]))
    assert _check_instance_type_offerings(ctx, _shape()).status == CheckStatus.PASS

    ctx.ec2 = OfferingEc2(["r7i.2xlarge"])
    result = _check_instance_type_offerings(ctx, _shape())
    assert result.status == CheckStatus.FAIL
    assert result.details["missing_instance_types"] == ["c7i.48xlarge"]

    broken = MagicMock()
    broken.get_paginator.side_effect = RuntimeError("no offerings")
    ctx.ec2 = broken
    result = _check_instance_type_offerings(ctx, _shape())
    assert result.status == CheckStatus.FAIL
    assert result.details["error"] == "no offerings"


def test_spot_market_signal_cover_empty_pass_and_warn() -> None:
    ctx = _Clients(region_az="us-west-2d", ec2=MagicMock())
    assert _check_spot_market_signal(ctx, _shape(spot_count=0)).status == CheckStatus.PASS

    ctx.ec2.describe_spot_price_history.return_value = {
        "SpotPriceHistory": [{"SpotPrice": "0.20"}]
    }
    assert _check_spot_market_signal(ctx, _shape()).status == CheckStatus.PASS

    ctx.ec2.describe_spot_price_history.return_value = {"SpotPriceHistory": []}
    result = _check_spot_market_signal(ctx, _shape())
    assert result.status == CheckStatus.WARN
    assert result.details["missing_price_history"] == ["r7i.2xlarge"]

    ctx.ec2.describe_spot_price_history.side_effect = RuntimeError("spot denied")
    result = _check_spot_market_signal(ctx, _shape())
    assert result.status == CheckStatus.WARN
    assert result.details["errors"] == {"r7i.2xlarge": "spot denied"}


def test_storage_quotas_cover_gp3_scratch_non_gp3_and_no_fsx(monkeypatch) -> None:
    ctx = _Clients(service_quotas=MagicMock())
    calls = []

    def fake_named(_ctx, **kwargs):
        calls.append(kwargs["check_id"])
        return CheckResult(id=kwargs["check_id"], status=CheckStatus.PASS, details=kwargs)

    monkeypatch.setattr(validation_module, "_check_named_service_quota", fake_named)

    checks = _check_storage_quotas(ctx, _shape())
    assert [check.id for check in checks] == [
        "quota.ebs.gp3_storage",
        "quota.fsx.lustre_scratch_filesystems",
        "quota.fsx.lustre_scratch_storage",
    ]
    assert calls == [check.id for check in checks]

    checks = _check_storage_quotas(
        ctx,
        _shape(headnode_root_volume_type="gp2", fsx_deployment_type="", fsx_storage_gib=0),
    )
    assert checks[0].status == CheckStatus.PASS
    assert checks[1].id == "quota.fsx.lustre_storage"
    assert checks[1].status == CheckStatus.PASS


def test_named_service_quota_cover_exception_not_found_fail_and_pass(monkeypatch) -> None:
    ctx = _Clients(service_quotas=MagicMock())

    monkeypatch.setattr(
        validation_module,
        "_find_quota_by_name",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("list denied")),
    )
    assert _check_named_service_quota(
        ctx,
        check_id="quota.x",
        service_code="fsx",
        quota_name_fragments=("lustre",),
        required_value=1,
        required_unit="GiB",
        remediation_subject="FSx",
    ).status == CheckStatus.WARN

    monkeypatch.setattr(validation_module, "_find_quota_by_name", lambda *_args, **_kwargs: None)
    assert _check_named_service_quota(
        ctx,
        check_id="quota.x",
        service_code="fsx",
        quota_name_fragments=("lustre",),
        required_value=1,
        required_unit="GiB",
        remediation_subject="FSx",
    ).status == CheckStatus.WARN

    monkeypatch.setattr(
        validation_module,
        "_find_quota_by_name",
        lambda *_args, **_kwargs: {"QuotaCode": "L-1", "QuotaName": "Lustre", "Value": 1},
    )
    assert _check_named_service_quota(
        ctx,
        check_id="quota.x",
        service_code="fsx",
        quota_name_fragments=("lustre",),
        required_value=2,
        required_unit="GiB",
        remediation_subject="FSx",
    ).status == CheckStatus.FAIL
    assert _check_named_service_quota(
        ctx,
        check_id="quota.x",
        service_code="fsx",
        quota_name_fragments=("lustre",),
        required_value=1,
        required_unit="GiB",
        remediation_subject="FSx",
    ).status == CheckStatus.PASS


def test_find_quota_by_name_uses_paginator_and_fallback_methods() -> None:
    paged = MagicMock()
    paged.get_paginator.return_value = _Paginator(
        [{"Quotas": [{"QuotaName": "Lustre Scratch storage capacity", "Value": 1000}]}]
    )
    assert _find_quota_by_name(
        paged,
        service_code="fsx",
        fragments=("Lustre", "storage"),
    )["Value"] == 1000

    class NoPaginator:
        def list_service_quotas(self, **_kwargs):
            return {"Quotas": []}

        def list_aws_default_service_quotas(self, **_kwargs):
            return {"Quotas": [{"QuotaName": "Storage for General Purpose SSD", "Value": 20}]}

    assert _find_quota_by_name(
        NoPaginator(),
        service_code="ebs",
        fragments=("general purpose",),
    )["Value"] == 20


def test_describe_instance_vcpus_and_coercion_helpers() -> None:
    class Ec2:
        def describe_instance_types(self, InstanceTypes):
            return {
                "InstanceTypes": [
                    {"InstanceType": item, "VCpuInfo": {"DefaultVCpus": 8}}
                    for item in InstanceTypes
                    if item != "missing.type"
                ]
            }

    assert _describe_instance_vcpus(Ec2(), ["r7i.2xlarge", "r7i.2xlarge"]) == {
        "r7i.2xlarge": 8
    }
    with pytest.raises(ValueError, match="missing.type"):
        _describe_instance_vcpus(Ec2(), ["missing.type"])
    assert _coerce_nonnegative_int("0", "count") == 0
    assert _coerce_positive_int("5", "size") == 5
    with pytest.raises(ValueError, match="integer"):
        _coerce_nonnegative_int("not-int", "count")
    with pytest.raises(ValueError, match="not be negative"):
        _coerce_nonnegative_int("-1", "count")
    with pytest.raises(ValueError, match="greater than zero"):
        _coerce_positive_int("0", "size")
    assert list(_chunks(["a", "b", "c"], 2)) == [("a", "b"), ("c",)]


def test_finalize_summary_counts_terminal_statuses() -> None:
    report = AwsValidationReport(
        checks=[
            CheckResult(id="pass", status=CheckStatus.PASS, details={}),
            CheckResult(id="warn", status=CheckStatus.WARN, details={}),
            CheckResult(id="fail", status=CheckStatus.FAIL, details={}),
        ]
    )

    _finalize_summary(report)

    assert report.summary == {"PASS": 1, "WARN": 1, "FAIL": 1}


def test_gap_analysis_lists_remediation(tmp_path) -> None:
    report = AwsValidationReport(
        mode="permissions",
        region="us-west-2",
        region_az="us-west-2b",
        aws_profile="dev",
        account_id="123456789012",
        caller_arn="arn:aws:iam::123456789012:user/alice",
        checks=[
            CheckResult(
                id="iam.policy.global",
                status=CheckStatus.FAIL,
                details={"policy": "missing"},
                remediation="Attach the Daylily global policy.",
            ),
            CheckResult(
                id="iam.simulation.s3_data",
                status=CheckStatus.PASS,
                details={
                    "actions": ["s3:GetObject", "s3:ListBucket"],
                    "denied_actions": [],
                },
            ),
        ],
        summary={"PASS": 1, "WARN": 0, "FAIL": 1},
    )
    report_path = tmp_path / "gap.md"

    write_gap_analysis(report, report_path)

    text = report_path.read_text(encoding="utf-8")
    assert "- PASS: 1" in text
    assert "- WARN: 0" in text
    assert "- FAIL: 1" in text
    assert "iam.policy.global - FAIL" in text
    assert "Attach the Daylily global policy." in text
    assert "## Passing Validation Checks" in text
    assert "iam.simulation.s3_data - PASS" in text
    assert '"actions": [' in text
    assert '"s3:GetObject"' in text
    assert '"denied_actions": []' in text


def test_gap_analysis_no_gaps_still_lists_passing_checks(tmp_path) -> None:
    report = AwsValidationReport(
        mode="quotas",
        region="us-east-1",
        region_az="us-east-1a",
        aws_profile="prod",
        account_id="123456789012",
        caller_arn="arn:aws:iam::123456789012:user/alice",
        checks=[
            CheckResult(
                id="quota.spot_vcpu",
                status=CheckStatus.PASS,
                details={
                    "quota_code": "L-34B43A08",
                    "current_value": 512,
                    "tot_vcpu_demand": 328,
                },
            )
        ],
        summary={"PASS": 1, "WARN": 0, "FAIL": 0},
    )
    report_path = tmp_path / "no_gap.md"

    write_gap_analysis(report, report_path)

    text = report_path.read_text(encoding="utf-8")
    assert "No permission or quota gaps were detected." in text
    assert "## Passing Validation Checks" in text
    assert "quota.spot_vcpu - PASS" in text
    assert '"quota_code": "L-34B43A08"' in text
    assert '"tot_vcpu_demand": 328' in text


def test_gap_analysis_warn_only_report_records_no_passing_checks(tmp_path) -> None:
    report = AwsValidationReport(
        mode="all",
        region="eu-central-1",
        region_az="eu-central-1a",
        aws_profile="prod",
        account_id="123456789012",
        caller_arn="arn:aws:iam::123456789012:user/alice",
        checks=[
            CheckResult(
                id="quota.spot_market_signal",
                status=CheckStatus.WARN,
                details={"spot_instance_types": ["r7i.2xlarge"]},
                remediation="Confirm Spot market capacity before launching.",
            )
        ],
        summary={"PASS": 0, "WARN": 1, "FAIL": 0},
    )
    report_path = tmp_path / "nested" / "gap.md"

    write_gap_analysis(report, report_path)

    text = report_path.read_text(encoding="utf-8")
    assert "## Required Admin Follow-Up" in text
    assert "quota.spot_market_signal - WARN" in text
    assert "Confirm Spot market capacity before launching." in text
    assert "## Passing Validation Checks" in text
    assert "No passing validation checks were recorded." in text
