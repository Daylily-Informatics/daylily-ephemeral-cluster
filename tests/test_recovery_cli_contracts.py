from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from daylily_ec.cli import app
from daylily_ec.workflow.compute_fleet import (
    ClusterIdleProof,
    ComputeFleetOperationResult,
)
from daylily_ec.workflow.recover_slurm_accounting import (
    SlurmAccountingRecoveryError,
    SlurmAccountingRecoveryResult,
)

runner = CliRunner()


def _activate(monkeypatch) -> None:
    monkeypatch.setenv("CONDA_PREFIX", "/tmp/dayec")
    monkeypatch.setenv("CONDA_DEFAULT_ENV", "DAY-EC")


def test_cluster_compute_fleet_cli_passes_exact_public_contract(monkeypatch) -> None:
    import daylily_ec.workflow.compute_fleet as fleet_module

    _activate(monkeypatch)
    calls: dict[str, object] = {}

    def fake_transition(**kwargs) -> ComputeFleetOperationResult:
        calls.update(kwargs)
        return ComputeFleetOperationResult(
            cluster="cluster-a",
            region="us-west-2",
            request_status="STOP_REQUESTED",
            wait_for_status="STOPPED",
            drain_requested=True,
            initial_status="RUNNING",
            final_status="STOPPED",
            request_submitted=True,
            resumed_existing_request=False,
            idle_proof=ClusterIdleProof(
                authoritative=True,
                controller_count=0,
                slurm_job_count=0,
                observed_at="2026-08-20T18:00:00Z",
                instance_id="i-headnode",
                ssm_command_ids=("ssm-controller", "ssm-queue"),
            ),
            started_at="2026-08-20T18:00:00Z",
            completed_at="2026-08-20T18:01:00Z",
            elapsed_seconds=60.0,
        )

    monkeypatch.setattr(fleet_module, "run_compute_fleet_transition", fake_transition)

    result = runner.invoke(
        app,
        [
            "--json",
            "cluster",
            "compute-fleet",
            "--cluster",
            "cluster-a",
            "--region",
            "us-west-2",
            "--profile",
            "lsmc",
            "--status",
            "STOP_REQUESTED",
            "--wait-for",
            "STOPPED",
            "--drain",
            "--timeout-seconds",
            "900",
            "--poll-interval-seconds",
            "15",
        ],
    )

    assert result.exit_code == 0, result.output
    assert calls == {
        "cluster_name": "cluster-a",
        "region": "us-west-2",
        "profile": "lsmc",
        "request_status": "STOP_REQUESTED",
        "wait_for_status": "STOPPED",
        "drain": True,
        "timeout_seconds": 900,
        "poll_interval_seconds": 15,
    }
    payload = json.loads(result.stdout)
    assert payload["schema_version"] == "dyec.cluster_compute_fleet.v1"
    assert payload["request_status"] == "STOP_REQUESTED"
    assert payload["final_status"] == "STOPPED"
    assert payload["idle_proof"]["slurm_job_count"] == 0


def test_cluster_compute_fleet_cli_rejects_non_exact_state_spelling(monkeypatch) -> None:
    _activate(monkeypatch)

    result = runner.invoke(
        app,
        [
            "cluster",
            "compute-fleet",
            "--cluster",
            "cluster-a",
            "--region",
            "us-west-2",
            "--profile",
            "lsmc",
            "--status",
            "stop_requested",
            "--wait-for",
            "STOPPED",
        ],
    )

    assert result.exit_code == 2
    assert "Invalid value" in result.stderr


def test_cluster_compute_fleet_cli_emits_versioned_json_failure(monkeypatch) -> None:
    _activate(monkeypatch)

    result = runner.invoke(
        app,
        [
            "--json",
            "cluster",
            "compute-fleet",
            "--cluster",
            "cluster-a",
            "--region",
            "us-west-2",
            "--profile",
            "lsmc",
            "--status",
            "STOP_REQUESTED",
            "--wait-for",
            "RUNNING",
        ],
    )

    assert result.exit_code == 1
    assert json.loads(result.stdout) == {
        "schema_version": "dyec.cluster_compute_fleet.v1",
        "ok": False,
        "error_code": "compute_fleet_operation_failed",
        "error": "STOP_REQUESTED must pair with wait target STOPPED.",
    }


def test_slurm_accounting_recover_cli_passes_exact_public_contract(
    tmp_path: Path, monkeypatch
) -> None:
    import daylily_ec.workflow.recover_slurm_accounting as recovery_module

    _activate(monkeypatch)
    calls: dict[str, object] = {}
    source = tmp_path / "cluster.yaml"
    source.write_text("Region: us-west-2\n", encoding="utf-8")
    output_dir = tmp_path / "receipts"

    def fake_recover(**kwargs) -> SlurmAccountingRecoveryResult:
        calls.update(kwargs)
        return SlurmAccountingRecoveryResult(
            cluster="cluster-a",
            region="us-west-2",
            region_az="us-west-2d",
            aws_profile="lsmc",
            aws_account_id="123456789012",
            accounting_stack_name="dayec-slurm-accounting-us-west-2",
            database_name="dayec_slurm_acct",
            db_username="slurm_acct",
            instance_type="t4g.micro",
            create_slurm_accounting_if_missing=True,
            acknowledge_slurm_accounting_create_cost=True,
            service_created=False,
            cluster_configuration_path=str(source),
            cluster_configuration_sha256="a" * 64,
            update_configuration_path=str(output_dir / "slurm-accounting-update.yaml"),
            update_configuration_sha256="b" * 64,
            initial_cluster_state="CREATE_COMPLETE",
            initial_fleet_state="RUNNING",
            final_cluster_state="UPDATE_COMPLETE",
            final_fleet_state="RUNNING",
            update_submitted=True,
            update_reclaimed=False,
            fleet_stop_submitted=True,
            fleet_start_submitted=True,
            accounting_verified=True,
            phase_receipts=(
                {
                    "phase": "accounting_verified",
                    "status": "complete",
                    "observed_at": "2026-08-20T18:10:00Z",
                },
            ),
            started_at="2026-08-20T18:00:00Z",
            completed_at="2026-08-20T18:10:00Z",
            elapsed_seconds=600.0,
            recovery_receipt_path=str(output_dir / "slurm-accounting-recovery.json"),
            recovery_receipt_sha256="c" * 64,
        )

    monkeypatch.setattr(recovery_module, "recover_slurm_accounting", fake_recover)

    result = runner.invoke(
        app,
        [
            "--json",
            "slurm-accounting",
            "recover",
            "--cluster",
            "cluster-a",
            "--region",
            "us-west-2",
            "--region-az",
            "us-west-2d",
            "--profile",
            "lsmc",
            "--cluster-configuration",
            str(source),
            "--output-dir",
            str(output_dir),
            "--stack-name",
            "dayec-slurm-accounting-us-west-2",
            "--database-name",
            "dayec_slurm_acct",
            "--db-username",
            "slurm_acct",
            "--instance-type",
            "t4g.micro",
            "--create-slurm-accounting-if-missing",
            "--acknowledge-slurm-accounting-create-cost",
            "--timeout-seconds",
            "5400",
            "--poll-interval-seconds",
            "30",
        ],
    )

    assert result.exit_code == 0, result.output
    assert calls == {
        "cluster_name": "cluster-a",
        "region": "us-west-2",
        "region_az": "us-west-2d",
        "profile": "lsmc",
        "cluster_configuration": source,
        "output_dir": output_dir,
        "stack_name": "dayec-slurm-accounting-us-west-2",
        "database_name": "dayec_slurm_acct",
        "db_username": "slurm_acct",
        "instance_type": "t4g.micro",
        "create_slurm_accounting_if_missing": True,
        "acknowledge_slurm_accounting_create_cost": True,
        "timeout_seconds": 5400,
        "poll_interval_seconds": 30,
    }
    payload = json.loads(result.stdout)
    assert payload["schema_version"] == "dyec.slurm_accounting_recovery.v1"
    assert payload["terminal"] is True
    assert payload["status"] == "complete"
    assert payload["aws_profile"] == "lsmc"
    assert payload["aws_account_id"] == "123456789012"
    assert payload["database_name"] == "dayec_slurm_acct"
    assert payload["db_username"] == "slurm_acct"
    assert payload["accounting_verified"] is True
    assert payload["final_cluster_state"] == "UPDATE_COMPLETE"
    assert payload["final_fleet_state"] == "RUNNING"
    assert payload["recovery_receipt_sha256"] == "c" * 64


def test_slurm_accounting_recover_cli_emits_versioned_json_failure(
    tmp_path: Path, monkeypatch
) -> None:
    _activate(monkeypatch)
    source = tmp_path / "cluster.yaml"
    source.write_text("Region: us-west-2\n", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "--json",
            "slurm-accounting",
            "recover",
            "--cluster",
            "cluster-a",
            "--region",
            "us-west-2",
            "--region-az",
            "us-west-2d",
            "--profile",
            "lsmc",
            "--cluster-configuration",
            str(source),
            "--output-dir",
            str(tmp_path / "receipts"),
            "--stack-name",
            "dayec-slurm-accounting-us-west-2",
            "--database-name",
            "dayec_slurm_acct",
            "--db-username",
            "slurm_acct",
            "--instance-type",
            "t4g.micro",
            "--create-slurm-accounting-if-missing",
        ],
    )

    assert result.exit_code == 1
    assert json.loads(result.stdout) == {
        "schema_version": "dyec.slurm_accounting_recovery.v1",
        "ok": False,
        "error_code": "slurm_accounting_recovery_failed",
        "error": (
            "--create-slurm-accounting-if-missing and "
            "--acknowledge-slurm-accounting-create-cost must be supplied together."
        ),
    }


def test_slurm_accounting_recover_cli_emits_safe_preparation_diagnostics(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import daylily_ec.workflow.recover_slurm_accounting as recovery_module

    _activate(monkeypatch)
    source = tmp_path / "cluster.yaml"
    source.write_text("Region: us-west-2\n", encoding="utf-8")

    def fail_recovery(**_kwargs):
        try:
            raise RuntimeError("AccessDenied SDK detail password=do-not-expose")
        except RuntimeError as provider_error:
            raise SlurmAccountingRecoveryError(
                "The exact accounting service/update configuration was not prepared.",
                stage="service_resolution",
                reason_code="exact_database_discovery_failed",
            ) from provider_error

    monkeypatch.setattr(recovery_module, "recover_slurm_accounting", fail_recovery)
    result = runner.invoke(
        app,
        [
            "--json",
            "slurm-accounting",
            "recover",
            "--cluster",
            "cluster-a",
            "--region",
            "us-west-2",
            "--region-az",
            "us-west-2d",
            "--profile",
            "lsmc",
            "--cluster-configuration",
            str(source),
            "--output-dir",
            str(tmp_path / "receipts"),
            "--stack-name",
            "dayec-slurm-accounting-us-west-2",
            "--database-name",
            "dayec_slurm_acct",
            "--db-username",
            "slurm_acct",
            "--instance-type",
            "t4g.micro",
        ],
    )

    assert result.exit_code == 1
    assert json.loads(result.stdout) == {
        "schema_version": "dyec.slurm_accounting_recovery.v1",
        "ok": False,
        "error_code": "slurm_accounting_recovery_failed",
        "error": "The exact accounting service/update configuration was not prepared.",
        "stage": "service_resolution",
        "reason_code": "exact_database_discovery_failed",
    }
    assert "AccessDenied" not in result.stdout
    assert "password" not in result.stdout
