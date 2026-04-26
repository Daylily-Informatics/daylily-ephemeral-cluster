from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from daylily_ec.aws.validation import (
    AwsValidationOptions,
    check_pcluster_omics_policy_exists,
    check_ssm_session_document,
    extract_cluster_shape,
    simulate_required_permissions,
    write_gap_analysis,
)
from daylily_ec.aws.validation import AwsValidationReport
from daylily_ec.state.models import CheckResult, CheckStatus


class _Paginator:
    def __init__(self, pages):
        self.pages = pages

    def paginate(self, **_kwargs):
        return list(self.pages)


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
