from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from daylily_ec.aws.slurm_accounting import SlurmAccountingDb
from daylily_ec.workflow import attach_slurm_accounting as attach_module
from daylily_ec.workflow import recover_slurm_accounting as recovery_module
from daylily_ec.workflow.attach_slurm_accounting import PreparedSlurmAccountingUpdate
from daylily_ec.workflow.compute_fleet import ClusterIdleProof
from daylily_ec.workflow.recover_slurm_accounting import (
    RECOVERY_RECEIPT_FILENAME,
    SLURM_ACCOUNTING_RECOVERY_SCHEMA,
    UPDATE_CONFIGURATION_FILENAME,
    SlurmAccountingRecoveryError,
    recover_slurm_accounting,
)


def _source(path: Path) -> Path:
    path.write_text("Region: us-west-2\n", encoding="utf-8")
    return path


def _idle(*, jobs: int = 0) -> ClusterIdleProof:
    return ClusterIdleProof(
        authoritative=True,
        controller_count=0,
        slurm_job_count=jobs,
        observed_at="2026-08-20T18:00:00Z",
        instance_id="i-headnode",
        ssm_command_ids=("ssm-controller", "ssm-queue"),
    )


def _fleet_result(*, submitted: bool) -> SimpleNamespace:
    return SimpleNamespace(request_submitted=submitted)


def _prepared(destination: Path) -> PreparedSlurmAccountingUpdate:
    destination.write_text("accounting: rendered\n", encoding="utf-8")
    return PreparedSlurmAccountingUpdate(
        cluster_name="cluster-a",
        region="us-west-2",
        accounting_stack_name="dayec-slurm-accounting-us-west-2",
        provider_accounting_stack_name="dayec-slurm-accounting-us-west-2",
        privatelink_stack_name=None,
        consumer_vpc_id="vpc-exact",
        update_config_path=destination,
        service_created=False,
        database_name="dayec_slurm_acct",
        db_username="slurm_acct",
        provider_instance_type="t4g.micro",
    )


def _prepared_bridge(destination: Path) -> PreparedSlurmAccountingUpdate:
    return replace(
        _prepared(destination),
        accounting_stack_name="dayec-sacct-pl-vpc-exact",
        privatelink_stack_name="dayec-sacct-pl-vpc-exact",
    )


def _write_bound_receipt(tmp_path: Path, output_dir: Path) -> tuple[Path, Path, Path]:
    source = _source(tmp_path / "source.yaml").resolve()
    output_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    output_dir.chmod(0o700)
    update = output_dir / UPDATE_CONFIGURATION_FILENAME
    update.write_text("accounting: rendered\n", encoding="utf-8")
    update.chmod(0o600)
    receipt = output_dir / RECOVERY_RECEIPT_FILENAME
    receipt.write_text(
        json.dumps(
            {
                "schema_version": SLURM_ACCOUNTING_RECOVERY_SCHEMA,
                "ok": False,
                "terminal": False,
                "status": "in_progress",
                "phase": "update_submission",
                "cluster": "cluster-a",
                "region": "us-west-2",
                "region_az": "us-west-2d",
                "aws_profile": "lsmc",
                "aws_account_id": "123456789012",
                "accounting_stack_name": "dayec-slurm-accounting-us-west-2",
                "privatelink_stack_name": None,
                "consumer_vpc_id": "vpc-exact",
                "database_name": "dayec_slurm_acct",
                "db_username": "slurm_acct",
                "instance_type": "t4g.micro",
                "create_slurm_accounting_if_missing": False,
                "acknowledge_slurm_accounting_create_cost": False,
                "service_created": False,
                "cluster_configuration_path": str(source),
                "cluster_configuration_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                "update_configuration_path": str(update.resolve()),
                "update_configuration_sha256": hashlib.sha256(update.read_bytes()).hexdigest(),
                "phase_receipts": [
                    {
                        "phase": "update_submission",
                        "status": "complete",
                        "observed_at": "2026-08-20T18:00:00Z",
                    }
                ],
                "started_at": "2026-08-20T18:00:00Z",
                "updated_at": "2026-08-20T18:00:00Z",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    receipt.chmod(0o600)
    return source, update, receipt


def _write_render_intent(
    tmp_path: Path,
    output_dir: Path,
    *,
    preexisting_update: bool,
) -> tuple[Path, Path]:
    source = _source(tmp_path / "source.yaml").resolve()
    output_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    output_dir.chmod(0o700)
    update = output_dir / UPDATE_CONFIGURATION_FILENAME
    if preexisting_update:
        update.write_text("interrupted render\n", encoding="utf-8")
        update.chmod(0o600)
    phases = [
        {
            "phase": "render_intent",
            "status": "pending",
            "observed_at": "2026-08-20T18:00:00Z",
        }
    ]
    recovery_module._persist_progress_receipt(
        output_dir / RECOVERY_RECEIPT_FILENAME,
        phase="render_intent",
        cluster_name="cluster-a",
        region="us-west-2",
        region_az="us-west-2d",
        aws_profile="lsmc",
        aws_account_id="123456789012",
        stack_name="dayec-slurm-accounting-us-west-2",
        privatelink_stack_name=None,
        consumer_vpc_id="vpc-exact",
        database_name="dayec_slurm_acct",
        db_username="slurm_acct",
        instance_type="t4g.micro",
        create_if_missing=False,
        acknowledge_create_cost=False,
        service_created=False,
        source_config=source,
        source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        update_config=update,
        update_sha256=None,
        started_at="2026-08-20T18:00:00Z",
        phases=phases,
    )
    return source, update


def _recover(tmp_path: Path, **overrides):
    values = {
        "cluster_name": "cluster-a",
        "region": "us-west-2",
        "region_az": "us-west-2d",
        "profile": "lsmc",
        "pcluster_executable": "pcluster",
        "cluster_configuration": _source(tmp_path / "source.yaml"),
        "output_dir": tmp_path / "receipts",
        "stack_name": "dayec-slurm-accounting-us-west-2",
        "privatelink_stack_name": "",
        "database_name": "dayec_slurm_acct",
        "db_username": "slurm_acct",
        "instance_type": "t4g.micro",
        "create_slurm_accounting_if_missing": False,
        "acknowledge_slurm_accounting_create_cost": False,
        "timeout_seconds": 600,
        "poll_interval_seconds": 1,
        "account_id_resolver": lambda **_kwargs: "123456789012",
        "network_identity_resolver": lambda **_kwargs: SimpleNamespace(vpc_id="vpc-exact"),
    }
    values.update(overrides)
    output_dir = Path(values["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    output_dir.chmod(0o700)
    return recover_slurm_accounting(**values)


def test_create_complete_recovery_orders_idle_prepare_stop_update_start_verify(
    tmp_path, monkeypatch
) -> None:
    calls: list[str] = []
    cluster_states = iter(("CREATE_COMPLETE", "UPDATE_COMPLETE"))
    fleet_states = iter(("RUNNING", "RUNNING"))
    monkeypatch.setattr(
        recovery_module,
        "_describe_cluster_state",
        lambda *_args, **_kwargs: (next(cluster_states), {}),
    )
    monkeypatch.setattr(
        recovery_module,
        "_describe_fleet_state",
        lambda *_args, **_kwargs: next(fleet_states),
    )

    def idle_probe(**_kwargs) -> ClusterIdleProof:
        calls.append("idle")
        return _idle()

    def prepare(**kwargs) -> PreparedSlurmAccountingUpdate:
        calls.append(
            "prepare"
            if len([item for item in calls if item.startswith("prepare")]) == 0
            else "prepare:verify-exact"
        )
        assert kwargs["instance_type"] == "t4g.micro"
        assert kwargs["expected_region_az"] == "us-west-2d"
        assert kwargs["exact_target_only"] is True
        return _prepared(kwargs["destination_config"])

    def fleet_transition(**kwargs) -> SimpleNamespace:
        calls.append(f"fleet:{kwargs['request_status']}")
        progress = json.loads(
            (tmp_path / "receipts" / RECOVERY_RECEIPT_FILENAME).read_text(encoding="utf-8")
        )
        assert progress["status"] == "in_progress"
        assert progress["terminal"] is False
        assert progress["cluster_configuration_sha256"]
        assert progress["update_configuration_sha256"]
        return _fleet_result(submitted=True)

    def update_cluster(*_args, dry_run: bool, **_kwargs) -> SimpleNamespace:
        calls.append("update:dry" if dry_run else "update:submit")
        if not dry_run:
            intent = json.loads(
                (tmp_path / "receipts" / RECOVERY_RECEIPT_FILENAME).read_text(encoding="utf-8")
            )
            assert intent["phase"] == "update_submission_intent"
        return SimpleNamespace(success=True)

    def wait_update(*_args, **_kwargs) -> SimpleNamespace:
        calls.append("update:wait")
        return SimpleNamespace(success=True, final_status="UPDATE_COMPLETE")

    def verify(**_kwargs) -> str:
        calls.append("verify:sacct")
        return "i-headnode"

    monkeypatch.setattr(recovery_module, "prepare_slurm_accounting_update", prepare)
    monkeypatch.setattr(recovery_module, "run_compute_fleet_transition", fleet_transition)
    monkeypatch.setattr(recovery_module, "update_cluster", update_cluster)
    monkeypatch.setattr(recovery_module, "wait_for_cluster_update", wait_update)
    monkeypatch.setattr(recovery_module, "_verify_accounting", verify)
    output_dir = tmp_path / "receipts"
    output_dir.mkdir()
    unrelated = output_dir / "operator-note.txt"
    unrelated.write_text("preserve\n", encoding="utf-8")

    result = _recover(tmp_path, output_dir=output_dir, idle_probe_fn=idle_probe)

    assert calls == [
        "idle",
        "prepare",
        "idle",
        "fleet:STOP_REQUESTED",
        "update:dry",
        "update:submit",
        "update:wait",
        "prepare:verify-exact",
        "fleet:START_REQUESTED",
        "verify:sacct",
    ]
    assert unrelated.read_text(encoding="utf-8") == "preserve\n"
    assert result.accounting_verified is True
    assert result.update_submitted is True
    assert result.update_reclaimed is False
    assert result.final_cluster_state == "UPDATE_COMPLETE"
    assert result.final_fleet_state == "RUNNING"
    receipt_path = output_dir / RECOVERY_RECEIPT_FILENAME
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["schema_version"] == SLURM_ACCOUNTING_RECOVERY_SCHEMA
    assert receipt["status"] == "complete"
    assert receipt["terminal"] is True
    assert receipt["aws_profile"] == "lsmc"
    assert receipt["aws_account_id"] == "123456789012"
    assert receipt["accounting_verified"] is True
    assert receipt["update_configuration_path"] == str(output_dir / UPDATE_CONFIGURATION_FILENAME)
    assert result.recovery_receipt_sha256 == hashlib.sha256(receipt_path.read_bytes()).hexdigest()


def test_update_in_progress_reclaims_existing_update_without_duplicate(
    tmp_path, monkeypatch
) -> None:
    output_dir = tmp_path / "receipts"
    _write_bound_receipt(tmp_path, output_dir)
    cluster_states = iter(("UPDATE_IN_PROGRESS", "UPDATE_COMPLETE"))
    fleet_states = iter(("STOPPED", "RUNNING"))
    monkeypatch.setattr(
        recovery_module,
        "_describe_cluster_state",
        lambda *_args, **_kwargs: (next(cluster_states), {}),
    )
    monkeypatch.setattr(
        recovery_module,
        "_describe_fleet_state",
        lambda *_args, **_kwargs: next(fleet_states),
    )
    calls: list[str] = []

    def prepare(**kwargs) -> PreparedSlurmAccountingUpdate:
        calls.append("verify-exact")
        assert kwargs["create_if_missing"] is False
        assert kwargs["exact_target_only"] is True
        return _prepared(kwargs["destination_config"])

    monkeypatch.setattr(recovery_module, "prepare_slurm_accounting_update", prepare)
    monkeypatch.setattr(
        recovery_module,
        "update_cluster",
        lambda *_args, **_kwargs: pytest.fail("in-progress update must not be duplicated"),
    )
    monkeypatch.setattr(
        recovery_module,
        "wait_for_cluster_update",
        lambda *_args, **_kwargs: (
            calls.append("update:wait")
            or SimpleNamespace(success=True, final_status="UPDATE_COMPLETE")
        ),
    )
    transitions: list[str] = []

    def transition(**kwargs) -> SimpleNamespace:
        calls.append(f"fleet:{kwargs['request_status']}")
        transitions.append(kwargs["request_status"])
        return _fleet_result(submitted=True)

    monkeypatch.setattr(recovery_module, "run_compute_fleet_transition", transition)
    monkeypatch.setattr(recovery_module, "_verify_accounting", lambda **_kwargs: "i-headnode")

    result = _recover(tmp_path, output_dir=output_dir)

    assert transitions == ["START_REQUESTED"]
    assert calls == ["update:wait", "verify-exact", "fleet:START_REQUESTED"]
    assert result.update_submitted is False
    assert result.update_reclaimed is True
    assert result.update_configuration_sha256
    assert result.accounting_verified is True


def test_exact_privatelink_recovery_binds_bridge_and_consumer_in_terminal_receipt(
    tmp_path,
    monkeypatch,
) -> None:
    cluster_states = iter(("CREATE_COMPLETE", "UPDATE_COMPLETE"))
    fleet_states = iter(("STOPPED", "RUNNING"))
    monkeypatch.setattr(
        recovery_module,
        "_describe_cluster_state",
        lambda *_args, **_kwargs: (next(cluster_states), {}),
    )
    monkeypatch.setattr(
        recovery_module,
        "_describe_fleet_state",
        lambda *_args, **_kwargs: next(fleet_states),
    )
    prepare_calls: list[dict] = []

    def prepare(**kwargs) -> PreparedSlurmAccountingUpdate:
        prepare_calls.append(kwargs)
        return _prepared_bridge(kwargs["destination_config"])

    monkeypatch.setattr(recovery_module, "prepare_slurm_accounting_update", prepare)
    monkeypatch.setattr(
        recovery_module,
        "run_compute_fleet_transition",
        lambda **_kwargs: _fleet_result(submitted=False),
    )
    monkeypatch.setattr(
        recovery_module,
        "update_cluster",
        lambda *_args, **_kwargs: SimpleNamespace(success=True),
    )
    monkeypatch.setattr(
        recovery_module,
        "wait_for_cluster_update",
        lambda *_args, **_kwargs: SimpleNamespace(
            success=True,
            final_status="UPDATE_COMPLETE",
        ),
    )
    monkeypatch.setattr(recovery_module, "_verify_accounting", lambda **_kwargs: "i-headnode")

    result = _recover(
        tmp_path,
        privatelink_stack_name="dayec-sacct-pl-vpc-exact",
        idle_probe_fn=lambda **_kwargs: _idle(),
    )

    assert len(prepare_calls) == 2
    assert all(
        call["stack_name"] == "dayec-slurm-accounting-us-west-2"
        and call["privatelink_stack_name"] == "dayec-sacct-pl-vpc-exact"
        and call["exact_target_only"] is True
        and call["create_if_missing"] is False
        for call in prepare_calls
    )
    assert result.accounting_stack_name == "dayec-slurm-accounting-us-west-2"
    assert result.privatelink_stack_name == "dayec-sacct-pl-vpc-exact"
    assert result.consumer_vpc_id == "vpc-exact"
    receipt = json.loads(Path(result.recovery_receipt_path).read_text(encoding="utf-8"))
    assert receipt["accounting_stack_name"] == "dayec-slurm-accounting-us-west-2"
    assert receipt["privatelink_stack_name"] == "dayec-sacct-pl-vpc-exact"
    assert receipt["consumer_vpc_id"] == "vpc-exact"


def test_update_complete_only_restores_and_verifies(tmp_path, monkeypatch) -> None:
    output_dir = tmp_path / "receipts"
    _write_bound_receipt(tmp_path, output_dir)
    cluster_states = iter(("UPDATE_COMPLETE", "UPDATE_COMPLETE"))
    fleet_states = iter(("STOPPED", "RUNNING"))
    monkeypatch.setattr(
        recovery_module,
        "_describe_cluster_state",
        lambda *_args, **_kwargs: (next(cluster_states), {}),
    )
    monkeypatch.setattr(
        recovery_module,
        "_describe_fleet_state",
        lambda *_args, **_kwargs: next(fleet_states),
    )
    monkeypatch.setattr(
        recovery_module,
        "wait_for_cluster_update",
        lambda *_args, **_kwargs: pytest.fail("completed update must not be waited again"),
    )
    monkeypatch.setattr(
        recovery_module,
        "update_cluster",
        lambda *_args, **_kwargs: pytest.fail("completed update must not be resubmitted"),
    )
    monkeypatch.setattr(
        recovery_module,
        "run_compute_fleet_transition",
        lambda **_kwargs: order.append("start") or _fleet_result(submitted=True),
    )
    order: list[str] = []
    monkeypatch.setattr(
        recovery_module,
        "prepare_slurm_accounting_update",
        lambda **kwargs: order.append("verify-exact") or _prepared(kwargs["destination_config"]),
    )
    verified: list[bool] = []
    monkeypatch.setattr(
        recovery_module,
        "_verify_accounting",
        lambda **_kwargs: verified.append(True) or "i-headnode",
    )

    result = _recover(tmp_path, output_dir=output_dir)

    assert verified == [True]
    assert order == ["verify-exact", "start"]
    assert result.update_reclaimed is False
    assert result.fleet_start_submitted is True
    assert result.accounting_verified is True


def test_resumed_update_without_deterministic_config_fails_closed(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        recovery_module,
        "_describe_cluster_state",
        lambda *_args, **_kwargs: ("UPDATE_IN_PROGRESS", {}),
    )
    monkeypatch.setattr(
        recovery_module,
        "_describe_fleet_state",
        lambda *_args, **_kwargs: "STOPPED",
    )

    with pytest.raises(SlurmAccountingRecoveryError, match="identity receipt are required"):
        _recover(tmp_path)


def test_in_progress_update_with_running_fleet_fails_closed(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        recovery_module,
        "_describe_cluster_state",
        lambda *_args, **_kwargs: ("UPDATE_IN_PROGRESS", {}),
    )
    monkeypatch.setattr(
        recovery_module,
        "_describe_fleet_state",
        lambda *_args, **_kwargs: "RUNNING",
    )

    with pytest.raises(SlurmAccountingRecoveryError, match="stopped or stopping fleet"):
        _recover(tmp_path)


def test_active_work_blocks_before_service_or_fleet_mutation(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        recovery_module,
        "_describe_cluster_state",
        lambda *_args, **_kwargs: ("CREATE_COMPLETE", {}),
    )
    monkeypatch.setattr(
        recovery_module,
        "_describe_fleet_state",
        lambda *_args, **_kwargs: "RUNNING",
    )
    monkeypatch.setattr(
        recovery_module,
        "prepare_slurm_accounting_update",
        lambda **_kwargs: pytest.fail("active work must block service preparation"),
    )
    monkeypatch.setattr(
        recovery_module,
        "run_compute_fleet_transition",
        lambda **_kwargs: pytest.fail("active work must block fleet mutation"),
    )

    with pytest.raises(SlurmAccountingRecoveryError, match="jobs remain"):
        _recover(tmp_path, idle_probe_fn=lambda **_kwargs: _idle(jobs=1))


def test_paired_creation_and_cost_flags_fail_before_provider_calls(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        recovery_module,
        "_describe_cluster_state",
        lambda *_args, **_kwargs: pytest.fail("validation must precede provider calls"),
    )

    with pytest.raises(SlurmAccountingRecoveryError, match="must be supplied together"):
        _recover(
            tmp_path,
            create_slurm_accounting_if_missing=True,
            acknowledge_slurm_accounting_create_cost=False,
        )


def test_explicit_privatelink_rejects_provider_creation_flags_before_provider_calls(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        recovery_module,
        "_describe_cluster_state",
        lambda *_args, **_kwargs: pytest.fail("validation must precede provider calls"),
    )

    with pytest.raises(SlurmAccountingRecoveryError, match="cannot create"):
        _recover(
            tmp_path,
            privatelink_stack_name="dayec-sacct-pl-vpc-exact",
            create_slurm_accounting_if_missing=True,
            acknowledge_slurm_accounting_create_cost=True,
        )


@pytest.mark.parametrize("preexisting_update", [False, True])
def test_pre_render_write_ahead_receipt_resumes_interrupted_render(
    tmp_path, monkeypatch, preexisting_update
) -> None:
    output_dir = tmp_path / "receipts"
    _write_render_intent(
        tmp_path,
        output_dir,
        preexisting_update=preexisting_update,
    )
    cluster_states = iter(("CREATE_COMPLETE", "UPDATE_COMPLETE"))
    fleet_states = iter(("RUNNING", "RUNNING"))
    monkeypatch.setattr(
        recovery_module,
        "_describe_cluster_state",
        lambda *_args, **_kwargs: (next(cluster_states), {}),
    )
    monkeypatch.setattr(
        recovery_module,
        "_describe_fleet_state",
        lambda *_args, **_kwargs: next(fleet_states),
    )
    prepare_calls: list[Path] = []

    def prepare(**kwargs) -> PreparedSlurmAccountingUpdate:
        prepare_calls.append(kwargs["destination_config"])
        return _prepared(kwargs["destination_config"])

    monkeypatch.setattr(recovery_module, "prepare_slurm_accounting_update", prepare)
    monkeypatch.setattr(
        recovery_module,
        "run_compute_fleet_transition",
        lambda **_kwargs: _fleet_result(submitted=True),
    )
    monkeypatch.setattr(
        recovery_module,
        "update_cluster",
        lambda *_args, **_kwargs: SimpleNamespace(success=True),
    )
    monkeypatch.setattr(
        recovery_module,
        "wait_for_cluster_update",
        lambda *_args, **_kwargs: SimpleNamespace(
            success=True,
            final_status="UPDATE_COMPLETE",
        ),
    )
    monkeypatch.setattr(recovery_module, "_verify_accounting", lambda **_kwargs: "i-headnode")

    result = _recover(
        tmp_path,
        output_dir=output_dir,
        idle_probe_fn=lambda **_kwargs: _idle(),
    )

    assert prepare_calls[0] == output_dir / UPDATE_CONFIGURATION_FILENAME
    assert len(prepare_calls) == 2
    assert result.accounting_verified is True


@pytest.mark.parametrize(
    ("field", "wrong_value"),
    [
        ("accounting_stack_name", "wrong-stack"),
        ("provider_accounting_stack_name", "wrong-provider"),
        ("privatelink_stack_name", "unexpected-bridge"),
        ("consumer_vpc_id", "vpc-wrong"),
        ("database_name", "wrong_database"),
        ("db_username", "wrong_user"),
    ],
)
def test_prepared_exact_identity_mismatch_blocks_before_fleet(
    tmp_path, monkeypatch, field, wrong_value
) -> None:
    monkeypatch.setattr(
        recovery_module,
        "_describe_cluster_state",
        lambda *_args, **_kwargs: ("CREATE_COMPLETE", {}),
    )
    monkeypatch.setattr(
        recovery_module,
        "_describe_fleet_state",
        lambda *_args, **_kwargs: "RUNNING",
    )

    def prepare(**kwargs) -> PreparedSlurmAccountingUpdate:
        return replace(_prepared(kwargs["destination_config"]), **{field: wrong_value})

    monkeypatch.setattr(recovery_module, "prepare_slurm_accounting_update", prepare)
    monkeypatch.setattr(
        recovery_module,
        "run_compute_fleet_transition",
        lambda **_kwargs: pytest.fail("identity mismatch must precede fleet mutation"),
    )

    with pytest.raises(SlurmAccountingRecoveryError, match="does not match"):
        _recover(tmp_path, idle_probe_fn=lambda **_kwargs: _idle())


def test_preparation_failure_preserves_safe_stage_and_reason_without_provider_text(
    tmp_path,
    monkeypatch,
) -> None:
    output_dir = tmp_path / "receipts"
    monkeypatch.setattr(
        recovery_module,
        "_describe_cluster_state",
        lambda *_args, **_kwargs: ("CREATE_COMPLETE", {}),
    )
    monkeypatch.setattr(
        recovery_module,
        "_describe_fleet_state",
        lambda *_args, **_kwargs: "STOPPED",
    )

    def fail_preparation(**_kwargs):
        raise attach_module.SlurmAccountingPreparationError(
            "AccessDenied SDK detail password=do-not-expose",
            stage="service_resolution",
            reason_code="exact_database_discovery_failed",
        )

    monkeypatch.setattr(recovery_module, "prepare_slurm_accounting_update", fail_preparation)
    monkeypatch.setattr(
        recovery_module,
        "run_compute_fleet_transition",
        lambda **_kwargs: pytest.fail("preparation failure must precede fleet mutation"),
    )
    monkeypatch.setattr(
        recovery_module,
        "update_cluster",
        lambda *_args, **_kwargs: pytest.fail("preparation failure must precede update"),
    )

    with pytest.raises(SlurmAccountingRecoveryError) as caught:
        _recover(
            tmp_path,
            output_dir=output_dir,
            idle_probe_fn=lambda **_kwargs: _idle(),
        )

    assert str(caught.value) == (
        "The exact accounting service/update configuration was not prepared."
    )
    assert caught.value.stage == "service_resolution"
    assert caught.value.reason_code == "exact_database_discovery_failed"
    assert "AccessDenied" not in str(caught.value)
    assert "password" not in str(caught.value)
    receipt = json.loads((output_dir / RECOVERY_RECEIPT_FILENAME).read_text(encoding="utf-8"))
    assert receipt["status"] == "in_progress"
    assert receipt["phase"] == "render_intent"
    assert not (output_dir / UPDATE_CONFIGURATION_FILENAME).exists()


def test_exact_revalidation_preserves_safe_preparation_diagnostics(
    tmp_path,
    monkeypatch,
) -> None:
    source = _source(tmp_path / "source.yaml")
    update = tmp_path / UPDATE_CONFIGURATION_FILENAME
    update.write_text("accounting: rendered\n", encoding="utf-8")
    monkeypatch.setattr(
        recovery_module,
        "prepare_slurm_accounting_update",
        lambda **_kwargs: (_ for _ in ()).throw(
            attach_module.SlurmAccountingPreparationError(
                "AccessDenied SDK detail password=do-not-expose",
                stage="service_resolution",
                reason_code="exact_regional_stack_inventory_failed",
            )
        ),
    )

    with pytest.raises(SlurmAccountingRecoveryError) as caught:
        recovery_module._verify_exact_target_binding(
            cluster_name="cluster-a",
            region="us-west-2",
            region_az="us-west-2d",
            profile="lsmc",
            source_config=source,
            source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
            update_config=update,
            update_sha256=hashlib.sha256(update.read_bytes()).hexdigest(),
            stack_name="dayec-slurm-accounting-us-west-2",
            privatelink_stack_name=None,
            consumer_vpc_id="vpc-exact",
            database_name="dayec_slurm_acct",
            db_username="slurm_acct",
            instance_type="t4g.micro",
        )

    assert str(caught.value) == ("The exact accounting singleton could not be revalidated safely.")
    assert caught.value.stage == "service_resolution"
    assert caught.value.reason_code == "exact_regional_stack_inventory_failed"
    assert "AccessDenied" not in str(caught.value)
    assert "password" not in str(caught.value)


@pytest.mark.parametrize(
    ("stage", "reason_code"),
    [
        ("service resolution", "exact_database_discovery_failed"),
        ("service_resolution", "x" * 65),
        ("service_resolution", "sdk:error"),
    ],
)
def test_recovery_error_omits_unbounded_or_unstructured_diagnostics(
    stage,
    reason_code,
) -> None:
    error = SlurmAccountingRecoveryError(
        "Safe generic recovery failure.",
        stage=stage,
        reason_code=reason_code,
    )

    assert error.stage is None
    assert error.reason_code is None


def test_source_mutation_during_render_blocks_before_fleet(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        recovery_module,
        "_describe_cluster_state",
        lambda *_args, **_kwargs: ("CREATE_COMPLETE", {}),
    )
    monkeypatch.setattr(
        recovery_module,
        "_describe_fleet_state",
        lambda *_args, **_kwargs: "RUNNING",
    )

    def prepare(**kwargs) -> PreparedSlurmAccountingUpdate:
        prepared = _prepared(kwargs["destination_config"])
        kwargs["cluster_configuration"].write_text("mutated: true\n", encoding="utf-8")
        return prepared

    monkeypatch.setattr(recovery_module, "prepare_slurm_accounting_update", prepare)
    monkeypatch.setattr(
        recovery_module,
        "run_compute_fleet_transition",
        lambda **_kwargs: pytest.fail("source mutation must precede fleet mutation"),
    )

    with pytest.raises(SlurmAccountingRecoveryError, match="source cluster configuration changed"):
        _recover(tmp_path, idle_probe_fn=lambda **_kwargs: _idle())


@pytest.mark.parametrize("initial_fleet_state", ["RUNNING", "STOPPED"])
def test_work_appearing_during_preparation_blocks_before_stop_or_update(
    tmp_path, monkeypatch, initial_fleet_state
) -> None:
    monkeypatch.setattr(
        recovery_module,
        "_describe_cluster_state",
        lambda *_args, **_kwargs: ("CREATE_COMPLETE", {}),
    )
    monkeypatch.setattr(
        recovery_module,
        "_describe_fleet_state",
        lambda *_args, **_kwargs: initial_fleet_state,
    )
    proofs = iter((_idle(), _idle(jobs=1)))
    monkeypatch.setattr(
        recovery_module,
        "prepare_slurm_accounting_update",
        lambda **kwargs: _prepared(kwargs["destination_config"]),
    )
    monkeypatch.setattr(
        recovery_module,
        "run_compute_fleet_transition",
        lambda **_kwargs: pytest.fail("fresh active-work proof must block fleet handling"),
    )
    monkeypatch.setattr(
        recovery_module,
        "update_cluster",
        lambda *_args, **_kwargs: pytest.fail("fresh active-work proof must block update"),
    )

    with pytest.raises(SlurmAccountingRecoveryError, match="appeared during"):
        _recover(
            tmp_path,
            idle_probe_fn=lambda **_kwargs: next(proofs),
        )


@pytest.mark.parametrize(
    "corruption",
    [
        "source_hash",
        "update_file",
        "profile",
        "consumer_vpc",
        "bridge",
        "missing_bridge_field",
    ],
)
def test_resumed_recovery_rejects_identity_and_file_hash_mismatch(
    tmp_path, monkeypatch, corruption
) -> None:
    output_dir = tmp_path / "receipts"
    _source, update, receipt = _write_bound_receipt(tmp_path, output_dir)
    if corruption == "update_file":
        update.write_text("changed: true\n", encoding="utf-8")
    else:
        payload = json.loads(receipt.read_text(encoding="utf-8"))
        if corruption == "source_hash":
            payload["cluster_configuration_sha256"] = "0" * 64
        elif corruption == "profile":
            payload["aws_profile"] = "different-profile"
        elif corruption == "consumer_vpc":
            payload["consumer_vpc_id"] = "vpc-wrong"
        elif corruption == "bridge":
            payload["privatelink_stack_name"] = "unexpected-bridge"
        else:
            payload.pop("privatelink_stack_name")
        receipt.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    monkeypatch.setattr(
        recovery_module,
        "_describe_cluster_state",
        lambda *_args, **_kwargs: ("UPDATE_IN_PROGRESS", {}),
    )
    monkeypatch.setattr(
        recovery_module,
        "_describe_fleet_state",
        lambda *_args, **_kwargs: "STOPPED",
    )
    monkeypatch.setattr(
        recovery_module,
        "run_compute_fleet_transition",
        lambda **_kwargs: pytest.fail("binding mismatch must precede fleet mutation"),
    )

    with pytest.raises(SlurmAccountingRecoveryError, match="does not match|hash"):
        _recover(tmp_path, output_dir=output_dir)


def test_terminal_receipt_is_rejected_during_new_update(tmp_path, monkeypatch) -> None:
    output_dir = tmp_path / "receipts"
    _source, _update, receipt = _write_bound_receipt(tmp_path, output_dir)
    payload = json.loads(receipt.read_text(encoding="utf-8"))
    payload.update({"ok": True, "terminal": True, "status": "complete"})
    payload.pop("phase")
    receipt.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    monkeypatch.setattr(
        recovery_module,
        "_describe_cluster_state",
        lambda *_args, **_kwargs: ("UPDATE_IN_PROGRESS", {}),
    )
    monkeypatch.setattr(
        recovery_module,
        "_describe_fleet_state",
        lambda *_args, **_kwargs: "STOPPED",
    )

    with pytest.raises(SlurmAccountingRecoveryError, match="valid only"):
        _recover(tmp_path, output_dir=output_dir)


@pytest.mark.parametrize(
    ("provider_state", "receipt_phase"),
    [
        ("UPDATE_IN_PROGRESS", "service_ready"),
        ("UPDATE_COMPLETE_CLEANUP_IN_PROGRESS", "fleet_stopped"),
        ("UPDATE_COMPLETE", "pre_stop_exact_target_verified"),
        ("CREATE_COMPLETE", "update_complete"),
        ("CREATE_COMPLETE", "post_update_exact_target_verified"),
        ("CREATE_COMPLETE", "accounting_verified"),
        ("UPDATE_COMPLETE", "unknown_phase"),
    ],
)
def test_impossible_provider_state_and_receipt_phase_fails_before_mutation(
    tmp_path,
    monkeypatch,
    provider_state,
    receipt_phase,
) -> None:
    output_dir = tmp_path / "receipts"
    _source, _update, receipt = _write_bound_receipt(tmp_path, output_dir)
    payload = json.loads(receipt.read_text(encoding="utf-8"))
    payload["phase"] = receipt_phase
    payload["phase_receipts"][-1]["phase"] = receipt_phase
    receipt.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    monkeypatch.setattr(
        recovery_module,
        "_describe_cluster_state",
        lambda *_args, **_kwargs: (provider_state, {}),
    )
    monkeypatch.setattr(
        recovery_module,
        "_describe_fleet_state",
        lambda *_args, **_kwargs: "STOPPED",
    )
    monkeypatch.setattr(
        recovery_module,
        "run_compute_fleet_transition",
        lambda **_kwargs: pytest.fail("impossible phase must precede fleet mutation"),
    )
    monkeypatch.setattr(
        recovery_module,
        "update_cluster",
        lambda *_args, **_kwargs: pytest.fail("impossible phase must precede update"),
    )

    with pytest.raises(
        SlurmAccountingRecoveryError,
        match="unknown in-progress phase|invalid while",
    ):
        _recover(
            tmp_path,
            output_dir=output_dir,
            idle_probe_fn=lambda **_kwargs: pytest.fail(
                "impossible phase must precede idle probing"
            ),
        )


@pytest.mark.parametrize(
    "submission_phase",
    ["update_submission_intent", "update_submission"],
)
def test_reclaimed_submission_intent_reclaims_visible_update_without_resubmitting(
    tmp_path, monkeypatch, submission_phase
) -> None:
    output_dir = tmp_path / "receipts"
    _source, _update, receipt = _write_bound_receipt(tmp_path, output_dir)
    payload = json.loads(receipt.read_text(encoding="utf-8"))
    payload["phase"] = submission_phase
    payload["phase_receipts"][-1]["phase"] = submission_phase
    receipt.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    cluster_states = iter(("CREATE_COMPLETE", "UPDATE_IN_PROGRESS", "UPDATE_COMPLETE"))
    fleet_states = iter(("STOPPED", "RUNNING"))
    monkeypatch.setattr(
        recovery_module,
        "_describe_cluster_state",
        lambda *_args, **_kwargs: (next(cluster_states), {}),
    )
    monkeypatch.setattr(
        recovery_module,
        "_describe_fleet_state",
        lambda *_args, **_kwargs: next(fleet_states),
    )
    monkeypatch.setattr(
        recovery_module,
        "prepare_slurm_accounting_update",
        lambda **kwargs: _prepared(kwargs["destination_config"]),
    )
    monkeypatch.setattr(
        recovery_module,
        "update_cluster",
        lambda *_args, **_kwargs: pytest.fail("reclaimed intent must not resubmit"),
    )
    monkeypatch.setattr(
        recovery_module,
        "wait_for_cluster_update",
        lambda *_args, **_kwargs: SimpleNamespace(
            success=True,
            final_status="UPDATE_COMPLETE",
        ),
    )
    transitions: list[str] = []
    monkeypatch.setattr(
        recovery_module,
        "run_compute_fleet_transition",
        lambda **kwargs: (
            transitions.append(kwargs["request_status"]) or _fleet_result(submitted=True)
        ),
    )
    monkeypatch.setattr(recovery_module, "_verify_accounting", lambda **_kwargs: "i-headnode")

    result = _recover(
        tmp_path,
        output_dir=output_dir,
        idle_probe_fn=lambda **_kwargs: _idle(),
    )

    assert transitions == ["START_REQUESTED"]
    assert result.update_submitted is False
    assert result.update_reclaimed is True


@pytest.mark.parametrize(
    "submission_phase",
    ["update_submission_intent", "update_submission"],
)
def test_reclaimed_submission_intent_still_create_fails_without_resubmitting(
    tmp_path, monkeypatch, submission_phase
) -> None:
    output_dir = tmp_path / "receipts"
    _source, _update, receipt = _write_bound_receipt(tmp_path, output_dir)
    payload = json.loads(receipt.read_text(encoding="utf-8"))
    payload["phase"] = submission_phase
    payload["phase_receipts"][-1]["phase"] = submission_phase
    receipt.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    monkeypatch.setattr(
        recovery_module,
        "_describe_cluster_state",
        lambda *_args, **_kwargs: ("CREATE_COMPLETE", {}),
    )
    monkeypatch.setattr(
        recovery_module,
        "_describe_fleet_state",
        lambda *_args, **_kwargs: "STOPPED",
    )
    monkeypatch.setattr(
        recovery_module,
        "_resolve_delayed_update_submission",
        lambda **_kwargs: "CREATE_COMPLETE",
    )
    monkeypatch.setattr(
        recovery_module,
        "update_cluster",
        lambda *_args, **_kwargs: pytest.fail("ambiguous intent must never resubmit"),
    )

    with pytest.raises(SlurmAccountingRecoveryError, match="will not resubmit"):
        _recover(
            tmp_path,
            output_dir=output_dir,
            idle_probe_fn=lambda **_kwargs: _idle(),
        )


def _exact_db(**overrides) -> SlurmAccountingDb:
    values = {
        "stack_name": "dayec-slurm-accounting-us-west-2",
        "status": "CREATE_COMPLETE",
        "uri": "10.0.0.10:3306",
        "private_ip": "10.0.0.10",
        "database_name": "dayec_slurm_acct",
        "username": "slurm_acct",
        "password_secret_arn": "arn:aws:secretsmanager:us-west-2:123456789012:secret:test",
        "client_security_group_id": "sg-accounting",
        "client_secret_read_policy_arn": "arn:aws:iam::123456789012:policy/test",
        "instance_id": "i-accounting",
    }
    values.update(overrides)
    return SlurmAccountingDb(**values)


def _patch_exact_resolution(monkeypatch, db: SlurmAccountingDb) -> None:
    ec2 = SimpleNamespace(
        describe_subnets=lambda **_kwargs: {
            "Subnets": [{"VpcId": "vpc-exact", "AvailabilityZone": "us-west-2d"}]
        },
        describe_instances=lambda **_kwargs: {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "InstanceId": "i-accounting",
                            "InstanceType": "t4g.micro",
                        }
                    ]
                }
            ]
        },
    )
    context = SimpleNamespace(client=lambda service: ec2 if service == "ec2" else None)
    monkeypatch.setattr(
        attach_module.AWSContext,
        "build_region",
        staticmethod(lambda *_args, **_kwargs: context),
    )
    monkeypatch.setattr(
        attach_module,
        "discover_slurm_accounting_dbs",
        lambda *_args, **_kwargs: [db],
    )
    monkeypatch.setattr(
        attach_module,
        "list_regional_slurm_accounting_stacks",
        lambda *_args, **_kwargs: [
            {
                "StackName": "dayec-slurm-accounting-us-west-2",
                "Tags": [{"Key": "daylily-ec:vpc-id", "Value": "vpc-exact"}],
            }
        ],
    )
    monkeypatch.setattr(
        attach_module,
        "resolve_slurm_accounting_db",
        lambda *_args, **_kwargs: pytest.fail("exact mode must not auto-select a stack"),
    )
    monkeypatch.setattr(
        attach_module,
        "create_slurm_accounting_stack",
        lambda *_args, **_kwargs: pytest.fail("existing exact stack must not be recreated"),
    )


@pytest.mark.parametrize(
    ("scenario", "expected_reason", "create_if_missing"),
    [
        ("inventory_failure", "exact_regional_stack_inventory_failed", False),
        ("inventory_conflict", "exact_regional_stack_conflict", False),
        ("database_discovery_failure", "exact_database_discovery_failed", False),
        ("database_multiple", "exact_database_multiple", False),
        ("stack_missing", "exact_stack_missing", False),
        ("stack_create_failure", "exact_stack_create_failed", True),
    ],
)
def test_exact_preparation_reports_actionable_safe_reason_without_fallback(
    tmp_path,
    monkeypatch,
    scenario,
    expected_reason,
    create_if_missing,
) -> None:
    exact_db = _exact_db()
    _patch_exact_resolution(monkeypatch, exact_db)
    provider_detail = "AccessDenied SDK detail password=do-not-expose"

    if scenario == "inventory_failure":
        monkeypatch.setattr(
            attach_module,
            "list_regional_slurm_accounting_stacks",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError(provider_detail)),
        )
    elif scenario == "inventory_conflict":
        monkeypatch.setattr(
            attach_module,
            "list_regional_slurm_accounting_stacks",
            lambda *_args, **_kwargs: [{"StackName": "wrong-exact-stack"}],
        )
        monkeypatch.setattr(
            attach_module,
            "discover_slurm_accounting_dbs",
            lambda *_args, **_kwargs: pytest.fail(
                "inventory conflict must precede database discovery"
            ),
        )
    elif scenario == "database_discovery_failure":
        monkeypatch.setattr(
            attach_module,
            "discover_slurm_accounting_dbs",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError(provider_detail)),
        )
    elif scenario == "database_multiple":
        monkeypatch.setattr(
            attach_module,
            "discover_slurm_accounting_dbs",
            lambda *_args, **_kwargs: [exact_db, exact_db],
        )
    else:
        monkeypatch.setattr(
            attach_module,
            "list_regional_slurm_accounting_stacks",
            lambda *_args, **_kwargs: [],
        )
        monkeypatch.setattr(
            attach_module,
            "discover_slurm_accounting_dbs",
            lambda *_args, **_kwargs: [],
        )
        if scenario == "stack_create_failure":
            monkeypatch.setattr(
                attach_module,
                "create_slurm_accounting_stack",
                lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError(provider_detail)),
            )

    source = tmp_path / "source.yaml"
    source.write_text(
        "HeadNode:\n  Networking:\n    SubnetId: subnet-exact\n",
        encoding="utf-8",
    )
    with pytest.raises(attach_module.SlurmAccountingPreparationError) as caught:
        attach_module.prepare_slurm_accounting_update(
            cluster_name="cluster-a",
            region="us-west-2",
            profile="lsmc",
            cluster_configuration=source,
            stack_name="dayec-slurm-accounting-us-west-2",
            database_name="dayec_slurm_acct",
            db_username="slurm_acct",
            instance_type="t4g.micro",
            create_if_missing=create_if_missing,
            destination_config=tmp_path / "update.yaml",
            expected_region_az="us-west-2d",
            exact_target_only=True,
        )

    assert caught.value.stage == "service_resolution"
    assert caught.value.reason_code == expected_reason
    assert "AccessDenied" not in str(caught.value)
    assert "password" not in str(caught.value)


def test_exact_preparation_uses_only_supplied_stack_without_fallback(tmp_path, monkeypatch) -> None:
    _patch_exact_resolution(monkeypatch, _exact_db())
    source = tmp_path / "source.yaml"
    source.write_text(
        "HeadNode:\n  Networking:\n    SubnetId: subnet-exact\n",
        encoding="utf-8",
    )
    destination = tmp_path / "update.yaml"

    prepared = attach_module.prepare_slurm_accounting_update(
        cluster_name="cluster-a",
        region="us-west-2",
        profile="lsmc",
        cluster_configuration=source,
        stack_name="dayec-slurm-accounting-us-west-2",
        database_name="dayec_slurm_acct",
        db_username="slurm_acct",
        instance_type="t4g.micro",
        create_if_missing=False,
        destination_config=destination,
        expected_region_az="us-west-2d",
        exact_target_only=True,
    )

    assert prepared.accounting_stack_name == "dayec-slurm-accounting-us-west-2"
    assert prepared.database_name == "dayec_slurm_acct"
    assert prepared.db_username == "slurm_acct"
    assert destination.is_file()


@pytest.mark.parametrize(
    "db",
    [
        _exact_db(stack_name="wrong-stack"),
        _exact_db(database_name="wrong_database"),
        _exact_db(username="wrong_user"),
    ],
)
def test_exact_preparation_rejects_wrong_stack_database_or_user(tmp_path, monkeypatch, db) -> None:
    _patch_exact_resolution(monkeypatch, db)
    source = tmp_path / "source.yaml"
    source.write_text(
        "HeadNode:\n  Networking:\n    SubnetId: subnet-exact\n",
        encoding="utf-8",
    )

    with pytest.raises(attach_module.SlurmAccountingPreparationError) as caught:
        attach_module.prepare_slurm_accounting_update(
            cluster_name="cluster-a",
            region="us-west-2",
            profile="lsmc",
            cluster_configuration=source,
            stack_name="dayec-slurm-accounting-us-west-2",
            database_name="dayec_slurm_acct",
            db_username="slurm_acct",
            instance_type="t4g.micro",
            create_if_missing=False,
            destination_config=tmp_path / "update.yaml",
            expected_region_az="us-west-2d",
            exact_target_only=True,
        )

    assert caught.value.reason_code == "exact_service_identity_mismatch"
