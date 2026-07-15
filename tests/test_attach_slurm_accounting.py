from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from daylily_ec.aws.slurm_accounting import SlurmAccountingDb
from daylily_ec.pcluster.runner import PclusterResult
from daylily_ec.workflow import attach_slurm_accounting as attach_module
from daylily_ec.workflow.attach_slurm_accounting import (
    SlurmAccountingAttachError,
    attach_slurm_accounting,
    render_slurm_accounting_update_config,
)


def _db() -> SlurmAccountingDb:
    return SlurmAccountingDb(
        stack_name="dayec-slurm-accounting-us-west-2",
        status="CREATE_COMPLETE",
        uri="10.0.1.237:3306",
        private_ip="10.0.1.237",
        database_name="dayec_slurm_acct",
        username="slurm_acct",
        password_secret_arn="arn:aws:secretsmanager:us-west-2:123:secret:acct",
        client_security_group_id="sg-accounting-client",
        instance_id="i-accounting",
    )


def _config(path: Path) -> Path:
    path.write_text(
        yaml.safe_dump(
            {
                "Region": "us-west-2",
                "HeadNode": {
                    "InstanceType": "r7i.2xlarge",
                    "Networking": {
                        "SubnetId": "subnet-head",
                        "AdditionalSecurityGroups": ["sg-existing"],
                    },
                },
                "Scheduling": {
                    "Scheduler": "slurm",
                    "SlurmSettings": {"EnableMemoryBasedScheduling": False},
                    "SlurmQueues": [],
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return path


def _result(body: dict, *, success: bool = True) -> PclusterResult:
    return PclusterResult(
        command="pcluster",
        returncode=0 if success else 1,
        json_body=body,
        success=success,
    )


class _Ec2:
    def describe_subnets(self, *, SubnetIds):
        assert SubnetIds == ["subnet-head"]
        return {
            "Subnets": [
                {
                    "SubnetId": "subnet-head",
                    "VpcId": "vpc-cluster",
                    "AvailabilityZone": "us-west-2d",
                }
            ]
        }


class _AwsContext:
    def client(self, service: str):
        assert service == "ec2"
        return _Ec2()


def _patch_ready_cluster(monkeypatch, update_calls: list[bool]) -> None:
    monkeypatch.setattr(
        attach_module.pcluster_runner,
        "describe_cluster",
        lambda *_args, **_kwargs: _result({"clusterStatus": "CREATE_COMPLETE"}),
    )
    monkeypatch.setattr(
        attach_module.pcluster_runner,
        "describe_compute_fleet",
        lambda *_args, **_kwargs: _result({"status": "STOPPED"}),
    )
    monkeypatch.setattr(
        attach_module.AWSContext,
        "build_region",
        classmethod(lambda _cls, _region, profile=None: _AwsContext()),
    )
    monkeypatch.setattr(
        attach_module,
        "ensure_slurm_accounting_db",
        lambda *_args, **_kwargs: _db(),
    )

    def fake_update(*_args, dry_run: bool, **_kwargs):
        update_calls.append(dry_run)
        return _result({"message": "ok"})

    monkeypatch.setattr(attach_module.pcluster_runner, "update_cluster", fake_update)


def test_default_templates_disable_slurm_accounting() -> None:
    root = Path(__file__).resolve().parents[1]
    for relative in (
        "config/daylily_ephemeral_cluster_template.yaml",
        "daylily_ec/resources/payload/config/daylily_ephemeral_cluster_template.yaml",
    ):
        payload = yaml.safe_load((root / relative).read_text(encoding="utf-8"))
        assert payload["ephemeral_cluster"]["config"]["slurm_accounting_enabled"] == [
            "PROMPTUSER",
            "false",
            "",
        ]
        assert (
            payload["ephemeral_cluster"]["template_defaults"]["slurm_accounting_enabled"] == "false"
        )


def test_default_templates_use_explicit_persistent2_storage() -> None:
    root = Path(__file__).resolve().parents[1]
    expected = {
        "fsx_fs_size": ["USESETVALUE", "", "4800"],
        "fsx_deployment_type": ["USESETVALUE", "", "PERSISTENT_2"],
        "fsx_throughput_mbps_per_tib": ["USESETVALUE", "", "250"],
        "fsx_lustre_version": ["USESETVALUE", "", "2.15"],
        "fsx_metadata_mode": ["USESETVALUE", "", "AUTOMATIC"],
        "fsx_encryption_mode": ["USESETVALUE", "", "AWS_MANAGED_FSX"],
        "fsx_owner": ["USESETVALUE", "", "DYEC"],
        "fsx_lifecycle": ["USESETVALUE", "", "CLUSTER_BOUND"],
        "sweep_protection_tag": ["USESETVALUE", "", "ursa-preserve=true"],
    }
    for relative in (
        "config/daylily_ephemeral_cluster_template.yaml",
        "daylily_ec/resources/payload/config/daylily_ephemeral_cluster_template.yaml",
    ):
        payload = yaml.safe_load((root / relative).read_text(encoding="utf-8"))
        config = payload["ephemeral_cluster"]["config"]
        assert {key: config[key] for key in expected} == expected


def test_render_update_config_adds_database_and_preserves_existing_group(tmp_path) -> None:
    source = _config(tmp_path / "source.yaml")
    destination = tmp_path / "update.yaml"

    render_slurm_accounting_update_config(source, destination, _db())

    original = yaml.safe_load(source.read_text(encoding="utf-8"))
    updated = yaml.safe_load(destination.read_text(encoding="utf-8"))
    assert "Database" not in original["Scheduling"]["SlurmSettings"]
    assert updated["HeadNode"]["Networking"]["AdditionalSecurityGroups"] == [
        "sg-existing",
        "sg-accounting-client",
    ]
    assert updated["Scheduling"]["SlurmSettings"]["Database"] == {
        "Uri": "10.0.1.237:3306",
        "UserName": "slurm_acct",
        "PasswordSecretArn": "arn:aws:secretsmanager:us-west-2:123:secret:acct",
        "DatabaseName": "dayec_slurm_acct",
    }


def test_attach_rejects_running_compute_fleet_before_accounting_resolution(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(
        attach_module.pcluster_runner,
        "describe_cluster",
        lambda *_args, **_kwargs: _result({"clusterStatus": "CREATE_COMPLETE"}),
    )
    monkeypatch.setattr(
        attach_module.pcluster_runner,
        "describe_compute_fleet",
        lambda *_args, **_kwargs: _result({"status": "RUNNING"}),
    )
    monkeypatch.setattr(
        attach_module,
        "ensure_slurm_accounting_db",
        lambda *_args, **_kwargs: pytest.fail("accounting must not resolve"),
    )

    with pytest.raises(SlurmAccountingAttachError, match="STOPPED"):
        attach_slurm_accounting(
            cluster_name="cluster-a",
            region="us-west-2",
            profile="lsmc",
            cluster_configuration=_config(tmp_path / "source.yaml"),
            output_dir=tmp_path,
        )


def test_attach_dry_run_never_submits_real_update(tmp_path, monkeypatch) -> None:
    update_calls: list[bool] = []
    _patch_ready_cluster(monkeypatch, update_calls)

    result = attach_slurm_accounting(
        cluster_name="cluster-a",
        region="us-west-2",
        profile="lsmc",
        cluster_configuration=_config(tmp_path / "source.yaml"),
        output_dir=tmp_path,
        dry_run_only=True,
    )

    assert update_calls == [True]
    assert result.update_submitted is False
    assert result.dry_run_only is True
    assert Path(result.update_config_path).is_file()


def test_attach_submits_only_after_successful_dry_run(tmp_path, monkeypatch) -> None:
    update_calls: list[bool] = []
    _patch_ready_cluster(monkeypatch, update_calls)

    result = attach_slurm_accounting(
        cluster_name="cluster-a",
        region="us-west-2",
        profile="lsmc",
        cluster_configuration=_config(tmp_path / "source.yaml"),
        output_dir=tmp_path,
    )

    assert update_calls == [True, False]
    assert result.update_submitted is True


def test_attach_dry_run_failure_does_not_submit(tmp_path, monkeypatch) -> None:
    update_calls: list[bool] = []
    _patch_ready_cluster(monkeypatch, update_calls)
    monkeypatch.setattr(
        attach_module.pcluster_runner,
        "update_cluster",
        lambda *_args, dry_run, **_kwargs: (
            update_calls.append(dry_run) or _result({}, success=False)
        ),
    )

    with pytest.raises(SlurmAccountingAttachError, match="dry-run rejected"):
        attach_slurm_accounting(
            cluster_name="cluster-a",
            region="us-west-2",
            profile="lsmc",
            cluster_configuration=_config(tmp_path / "source.yaml"),
            output_dir=tmp_path,
        )

    assert update_calls == [True]
