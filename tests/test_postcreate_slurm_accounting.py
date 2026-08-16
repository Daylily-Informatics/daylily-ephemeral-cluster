import json
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace

import pytest

from daylily_ec.workflow.attach_slurm_accounting import (
    PreparedSlurmAccountingUpdate,
    SlurmAccountingPreparationError,
)
from daylily_ec.workflow.postcreate_slurm_accounting import (
    ACCOUNTING_OUTCOME_ENABLED,
    ACCOUNTING_OUTCOME_OFF,
    ACCOUNTING_OUTCOME_RECOVERY_REQUIRED,
    ACCOUNTING_OUTCOME_WARNING,
    run_postcreate_slurm_accounting,
    validate_postcreate_slurm_accounting_options,
)
from daylily_ec.state.slurm_accounting import warning_message


def _result(*, success=True, body=None):
    return SimpleNamespace(success=success, json_body=body or {})


def _kwargs(tmp_path: Path) -> dict:
    return {
        "cluster_name": "proof-cluster",
        "region": "us-west-2",
        "region_az": "us-west-2c",
        "profile": "test",
        "cluster_configuration": tmp_path / "base.yaml",
        "initial_headnode_instance_id": "i-head",
        "slurm_accounting": "on",
        "non_interactive": True,
        "create_slurm_accounting_if_missing": False,
        "acknowledge_slurm_accounting_create_cost": False,
        "pcluster_executable": "/opt/pcluster",
    }


SENSITIVE_FAILURE_DETAIL = (
    "mysql://slurm_acct:password@db.internal.example:3306/dayec "
    "10.91.82.73 "
    "arn:aws:secretsmanager:us-west-2:123456789012:secret:sacct-password"
)


def _install_lifecycle_scenario(
    monkeypatch,
    tmp_path: Path,
    *,
    failure: str = "",
    initial_fleet_state: str = "RUNNING",
    replacement_headnode_id: str = "i-head",
):
    """Install one deterministic lifecycle with optional stage failure."""
    calls: list[object] = []
    fleet_requests: list[str] = []

    def prepare(**kwargs):
        calls.append(("prepare", kwargs["create_if_missing"]))
        if failure in {"discovery", "stack_creation", "render"}:
            reason_code = {
                "discovery": "service_discovery_failed",
                "stack_creation": "service_missing",
                "render": "update_config_render_failed",
            }[failure]
            raise SlurmAccountingPreparationError(
                SENSITIVE_FAILURE_DETAIL,
                stage="service_resolution",
                reason_code=reason_code,
                regional_stack_count=0,
            )
        return PreparedSlurmAccountingUpdate(
            cluster_name="proof-cluster",
            region="us-west-2",
            accounting_stack_name="dayec-slurm-accounting-us-west-2",
            update_config_path=tmp_path / "accounting-update.yaml",
            service_created=kwargs["create_if_missing"],
        )

    fleet_describe_calls = 0

    def describe_fleet(*_args, **kwargs):
        nonlocal fleet_describe_calls
        calls.append(("describe_fleet", kwargs["executable"]))
        fleet_describe_calls += 1
        if failure == "fleet_describe":
            raise RuntimeError(SENSITIVE_FAILURE_DETAIL)
        if failure == "stop" and fleet_describe_calls > 1:
            return _result(body={"status": "RUNNING"})
        if failure == "submit" and fleet_describe_calls > 1:
            return _result(body={"status": "STOPPED"})
        return _result(body={"status": initial_fleet_state})

    def update_fleet(_cluster, status, _region, **kwargs):
        calls.append((status, kwargs["executable"]))
        fleet_requests.append(status)
        if failure == "stop" and status == "STOP_REQUESTED":
            raise RuntimeError(SENSITIVE_FAILURE_DETAIL)
        if failure == "restart" and status == "START_REQUESTED":
            raise RuntimeError(SENSITIVE_FAILURE_DETAIL)
        return _result()

    def wait_fleet(_cluster, _region, target, **kwargs):
        calls.append((f"wait_{target}", kwargs["executable"]))
        if failure == "stop_timeout" and target == "STOPPED":
            return SimpleNamespace(success=False, final_status="STOP_REQUESTED")
        if failure == "restart_timeout" and target == "RUNNING":
            return SimpleNamespace(success=False, final_status="START_REQUESTED")
        return SimpleNamespace(success=True, final_status=target)

    def update(_cluster, _config, _region, *, dry_run, **kwargs):
        calls.append(("dry_run" if dry_run else "submit", kwargs["executable"]))
        if failure == "dry_run" and dry_run:
            raise RuntimeError(SENSITIVE_FAILURE_DETAIL)
        if failure == "submit" and not dry_run:
            raise RuntimeError(SENSITIVE_FAILURE_DETAIL)
        return _result()

    def wait_update(*_args, **kwargs):
        calls.append(("wait_update", kwargs["executable"]))
        if failure == "rollback":
            return SimpleNamespace(
                success=False,
                final_status="UPDATE_ROLLBACK_COMPLETE",
                safe_to_restore_fleet=True,
            )
        if failure == "indeterminate":
            return SimpleNamespace(
                success=False,
                final_status="UPDATE_ROLLBACK_FAILED",
                safe_to_restore_fleet=False,
            )
        if failure == "update_timeout":
            raise TimeoutError(SENSITIVE_FAILURE_DETAIL)
        return SimpleNamespace(
            success=True,
            final_status="UPDATE_COMPLETE",
            safe_to_restore_fleet=True,
        )

    def describe_cluster(*_args, **kwargs):
        calls.append(("describe_cluster", kwargs["executable"]))
        if failure == "headnode_describe":
            raise RuntimeError(SENSITIVE_FAILURE_DETAIL)
        if failure == "submit":
            return _result(body={"clusterStatus": "CREATE_COMPLETE"})
        return _result(
            body={
                "clusterStatus": "UPDATE_COMPLETE",
                "headNode": {"instanceId": replacement_headnode_id},
            }
        )

    def readiness(*_args, **kwargs):
        calls.append(("readiness", kwargs["remote_user"]))
        if failure == "readiness":
            raise RuntimeError(SENSITIVE_FAILURE_DETAIL)

    def wait_for_ssm(instance_id, *_args, **_kwargs):
        calls.append(("wait_for_ssm", instance_id))

    def verify(_instance_id, _region, command, **kwargs):
        calls.append(("verify", kwargs["as_user"], command))
        if failure == "verification":
            raise RuntimeError(SENSITIVE_FAILURE_DETAIL)

    monkeypatch.setattr(
        "daylily_ec.workflow.attach_slurm_accounting.prepare_slurm_accounting_update",
        prepare,
    )
    monkeypatch.setattr(
        "daylily_ec.workflow.postcreate_slurm_accounting.describe_compute_fleet",
        describe_fleet,
    )
    monkeypatch.setattr(
        "daylily_ec.workflow.postcreate_slurm_accounting.update_compute_fleet",
        update_fleet,
    )
    monkeypatch.setattr(
        "daylily_ec.workflow.postcreate_slurm_accounting.wait_for_compute_fleet",
        wait_fleet,
    )
    monkeypatch.setattr(
        "daylily_ec.workflow.postcreate_slurm_accounting.update_cluster",
        update,
    )
    monkeypatch.setattr(
        "daylily_ec.workflow.postcreate_slurm_accounting.wait_for_cluster_update",
        wait_update,
    )
    monkeypatch.setattr(
        "daylily_ec.workflow.postcreate_slurm_accounting.describe_cluster",
        describe_cluster,
    )
    monkeypatch.setattr(
        "daylily_ec.workflow.postcreate_slurm_accounting.validate_headnode_readiness",
        readiness,
    )
    monkeypatch.setattr(
        "daylily_ec.workflow.postcreate_slurm_accounting.wait_for_ssm_online",
        wait_for_ssm,
    )
    monkeypatch.setattr(
        "daylily_ec.workflow.postcreate_slurm_accounting.run_shell",
        verify,
    )
    return calls, fleet_requests


def test_direct_validation_rejects_invalid_mode_and_unpaired_approvals():
    with pytest.raises(ValueError, match="exactly lowercase"):
        validate_postcreate_slurm_accounting_options(
            slurm_accounting="ON",
            create_slurm_accounting_if_missing=False,
            acknowledge_slurm_accounting_create_cost=False,
        )
    with pytest.raises(ValueError, match="supplied together"):
        validate_postcreate_slurm_accounting_options(
            slurm_accounting="on",
            create_slurm_accounting_if_missing=True,
            acknowledge_slurm_accounting_create_cost=False,
        )


def test_off_never_discovers_or_mutates(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "daylily_ec.workflow.postcreate_slurm_accounting.describe_compute_fleet",
        lambda *args, **kwargs: pytest.fail("fleet must not be described"),
    )
    outcome = run_postcreate_slurm_accounting(**{**_kwargs(tmp_path), "slurm_accounting": "off"})
    assert outcome.outcome == ACCOUNTING_OUTCOME_OFF
    assert outcome.stage_reached == "off"


def test_noninteractive_missing_service_warns_without_fleet_mutation(monkeypatch, tmp_path):
    def missing(**kwargs):
        raise SlurmAccountingPreparationError(
            "safe",
            stage="service_resolution",
            reason_code="service_missing",
            regional_stack_count=0,
        )

    monkeypatch.setattr(
        "daylily_ec.workflow.attach_slurm_accounting.prepare_slurm_accounting_update",
        missing,
    )
    monkeypatch.setattr(
        "daylily_ec.workflow.postcreate_slurm_accounting.describe_compute_fleet",
        lambda *args, **kwargs: pytest.fail("fleet must not be described"),
    )
    outcome = run_postcreate_slurm_accounting(**_kwargs(tmp_path))
    assert outcome.outcome == ACCOUNTING_OUTCOME_WARNING
    assert outcome.error_stage == "service_preparation"
    assert outcome.update_config_path == ""


def test_interactive_first_singleton_requires_two_default_no_confirmations(monkeypatch, tmp_path):
    calls = []

    def prepare(**kwargs):
        calls.append(("prepare", kwargs["create_if_missing"]))
        if not kwargs["create_if_missing"]:
            raise SlurmAccountingPreparationError(
                "safe",
                stage="service_resolution",
                reason_code="service_missing",
                regional_stack_count=0,
            )
        raise AssertionError("second declined approval must not create")

    def confirm(message, *, default):
        calls.append(("confirm", default))
        return len([call for call in calls if call[0] == "confirm"]) == 1

    monkeypatch.setattr(
        "daylily_ec.workflow.attach_slurm_accounting.prepare_slurm_accounting_update",
        prepare,
    )
    monkeypatch.setattr(
        "daylily_ec.workflow.postcreate_slurm_accounting._interactive_terminal",
        lambda non_interactive: True,
    )
    outcome = run_postcreate_slurm_accounting(
        **{**_kwargs(tmp_path), "non_interactive": False, "confirm_fn": confirm}
    )
    assert outcome.outcome == ACCOUNTING_OUTCOME_WARNING
    assert outcome.create_approval_flag is True
    assert outcome.cost_acknowledgement_flag is False
    assert calls == [("prepare", False), ("confirm", False), ("confirm", False)]


def test_running_fleet_success_order_and_alternate_executable(monkeypatch, tmp_path):
    calls = []
    update_path = tmp_path / "accounting.yaml"

    def prepared(**kwargs):
        calls.append("prepare")
        return PreparedSlurmAccountingUpdate(
            cluster_name="proof-cluster",
            region="us-west-2",
            accounting_stack_name="dayec-slurm-accounting-us-west-2",
            update_config_path=update_path,
            service_created=False,
        )

    def describe_fleet(*args, **kwargs):
        calls.append(("describe_fleet", kwargs["executable"]))
        return _result(body={"status": "RUNNING"})

    def update_fleet(_cluster, status, _region, **kwargs):
        calls.append((status, kwargs["executable"]))
        return _result()

    def wait_fleet(_cluster, _region, target, **kwargs):
        calls.append((f"wait_{target}", kwargs["executable"]))
        return SimpleNamespace(success=True, final_status=target)

    def update(_cluster, _config, _region, *, dry_run, **kwargs):
        calls.append(("dry_run" if dry_run else "submit", kwargs["executable"]))
        return _result()

    def wait_update(*_args, **kwargs):
        calls.append(("wait_update", kwargs["executable"]))
        return SimpleNamespace(
            success=True,
            final_status="UPDATE_COMPLETE",
            safe_to_restore_fleet=True,
        )

    def describe_cluster(*_args, **kwargs):
        calls.append(("describe_cluster", kwargs["executable"]))
        return _result(
            body={"clusterStatus": "UPDATE_COMPLETE", "headNode": {"instanceId": "i-head"}}
        )

    monkeypatch.setattr(
        "daylily_ec.workflow.attach_slurm_accounting.prepare_slurm_accounting_update",
        prepared,
    )
    monkeypatch.setattr(
        "daylily_ec.workflow.postcreate_slurm_accounting.describe_compute_fleet",
        describe_fleet,
    )
    monkeypatch.setattr(
        "daylily_ec.workflow.postcreate_slurm_accounting.update_compute_fleet",
        update_fleet,
    )
    monkeypatch.setattr(
        "daylily_ec.workflow.postcreate_slurm_accounting.wait_for_compute_fleet",
        wait_fleet,
    )
    monkeypatch.setattr("daylily_ec.workflow.postcreate_slurm_accounting.update_cluster", update)
    monkeypatch.setattr(
        "daylily_ec.workflow.postcreate_slurm_accounting.wait_for_cluster_update",
        wait_update,
    )
    monkeypatch.setattr(
        "daylily_ec.workflow.postcreate_slurm_accounting.describe_cluster",
        describe_cluster,
    )
    monkeypatch.setattr(
        "daylily_ec.workflow.postcreate_slurm_accounting.validate_headnode_readiness",
        lambda *args, **kwargs: calls.append("readiness"),
    )
    monkeypatch.setattr(
        "daylily_ec.workflow.postcreate_slurm_accounting.run_shell",
        lambda *args, **kwargs: calls.append(("verify", kwargs["as_user"])),
    )

    outcome = run_postcreate_slurm_accounting(**_kwargs(tmp_path))
    assert outcome.outcome == ACCOUNTING_OUTCOME_ENABLED
    assert outcome.fleet_restored is True
    assert calls == [
        "prepare",
        ("describe_fleet", "/opt/pcluster"),
        ("STOP_REQUESTED", "/opt/pcluster"),
        ("wait_STOPPED", "/opt/pcluster"),
        ("dry_run", "/opt/pcluster"),
        ("submit", "/opt/pcluster"),
        ("wait_update", "/opt/pcluster"),
        ("describe_cluster", "/opt/pcluster"),
        "readiness",
        ("START_REQUESTED", "/opt/pcluster"),
        ("wait_RUNNING", "/opt/pcluster"),
        ("verify", "ubuntu"),
    ]


def test_indeterminate_update_never_restarts(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "daylily_ec.workflow.attach_slurm_accounting.prepare_slurm_accounting_update",
        lambda **kwargs: PreparedSlurmAccountingUpdate(
            cluster_name="proof-cluster",
            region="us-west-2",
            accounting_stack_name="dayec-slurm-accounting-us-west-2",
            update_config_path=tmp_path / "accounting.yaml",
            service_created=False,
        ),
    )
    monkeypatch.setattr(
        "daylily_ec.workflow.postcreate_slurm_accounting.describe_compute_fleet",
        lambda *args, **kwargs: _result(body={"status": "RUNNING"}),
    )
    requests = []
    monkeypatch.setattr(
        "daylily_ec.workflow.postcreate_slurm_accounting.update_compute_fleet",
        lambda _cluster, status, _region, **kwargs: requests.append(status) or _result(),
    )
    monkeypatch.setattr(
        "daylily_ec.workflow.postcreate_slurm_accounting.wait_for_compute_fleet",
        lambda *args, **kwargs: SimpleNamespace(success=True, final_status="STOPPED"),
    )
    monkeypatch.setattr(
        "daylily_ec.workflow.postcreate_slurm_accounting.update_cluster",
        lambda *args, **kwargs: _result(),
    )
    monkeypatch.setattr(
        "daylily_ec.workflow.postcreate_slurm_accounting.wait_for_cluster_update",
        lambda *args, **kwargs: SimpleNamespace(
            success=False,
            final_status="UPDATE_ROLLBACK_FAILED",
            safe_to_restore_fleet=False,
        ),
    )
    outcome = run_postcreate_slurm_accounting(**_kwargs(tmp_path))
    assert outcome.outcome == ACCOUNTING_OUTCOME_RECOVERY_REQUIRED
    assert outcome.recovery_required is True
    assert requests == ["STOP_REQUESTED"]


def test_dry_run_failure_restores_initially_running_fleet(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "daylily_ec.workflow.attach_slurm_accounting.prepare_slurm_accounting_update",
        lambda **kwargs: PreparedSlurmAccountingUpdate(
            cluster_name="proof-cluster",
            region="us-west-2",
            accounting_stack_name="dayec-slurm-accounting-us-west-2",
            update_config_path=tmp_path / "accounting.yaml",
            service_created=False,
        ),
    )
    monkeypatch.setattr(
        "daylily_ec.workflow.postcreate_slurm_accounting.describe_compute_fleet",
        lambda *args, **kwargs: _result(body={"status": "RUNNING"}),
    )
    requests = []
    monkeypatch.setattr(
        "daylily_ec.workflow.postcreate_slurm_accounting.update_compute_fleet",
        lambda _cluster, status, _region, **kwargs: requests.append(status) or _result(),
    )
    monkeypatch.setattr(
        "daylily_ec.workflow.postcreate_slurm_accounting.wait_for_compute_fleet",
        lambda _cluster, _region, target, **kwargs: SimpleNamespace(
            success=True, final_status=target
        ),
    )
    monkeypatch.setattr(
        "daylily_ec.workflow.postcreate_slurm_accounting.update_cluster",
        lambda *args, **kwargs: _result(success=False),
    )
    outcome = run_postcreate_slurm_accounting(**_kwargs(tmp_path))
    assert outcome.outcome == ACCOUNTING_OUTCOME_WARNING
    assert outcome.error_stage == "update_dry_run"
    assert outcome.fleet_restored is True
    assert requests == ["STOP_REQUESTED", "START_REQUESTED"]


def test_paired_noninteractive_approvals_create_first_singleton_before_fleet_stop(
    monkeypatch, tmp_path
):
    calls, requests = _install_lifecycle_scenario(monkeypatch, tmp_path)

    outcome = run_postcreate_slurm_accounting(
        **{
            **_kwargs(tmp_path),
            "create_slurm_accounting_if_missing": True,
            "acknowledge_slurm_accounting_create_cost": True,
        }
    )

    assert outcome.outcome == ACCOUNTING_OUTCOME_ENABLED
    assert outcome.service_created is True
    assert calls[0] == ("prepare", True)
    assert calls.index(("prepare", True)) < calls.index(("STOP_REQUESTED", "/opt/pcluster"))
    assert requests == ["STOP_REQUESTED", "START_REQUESTED"]


@pytest.mark.parametrize(
    "reason_code,regional_stack_count",
    [
        ("service_incompatible", 1),
        ("service_incompatible", 3),
    ],
)
def test_existing_incompatible_regional_service_never_creates_or_stops_fleet(
    monkeypatch, tmp_path, reason_code, regional_stack_count
):
    preparation_calls = []

    def incompatible(**kwargs):
        preparation_calls.append(kwargs["create_if_missing"])
        raise SlurmAccountingPreparationError(
            SENSITIVE_FAILURE_DETAIL,
            stage="service_resolution",
            reason_code=reason_code,
            regional_stack_count=regional_stack_count,
        )

    monkeypatch.setattr(
        "daylily_ec.workflow.attach_slurm_accounting.prepare_slurm_accounting_update",
        incompatible,
    )
    monkeypatch.setattr(
        "daylily_ec.workflow.postcreate_slurm_accounting.describe_compute_fleet",
        lambda *_args, **_kwargs: pytest.fail("fleet must not be described"),
    )

    outcome = run_postcreate_slurm_accounting(**_kwargs(tmp_path))

    assert outcome.outcome == ACCOUNTING_OUTCOME_WARNING
    assert outcome.error_stage == "service_preparation"
    assert outcome.service_created is False
    assert preparation_calls == [False]


def test_initially_stopped_fleet_remains_stopped(monkeypatch, tmp_path):
    calls, requests = _install_lifecycle_scenario(
        monkeypatch,
        tmp_path,
        initial_fleet_state="STOPPED",
    )

    outcome = run_postcreate_slurm_accounting(**_kwargs(tmp_path))

    assert outcome.outcome == ACCOUNTING_OUTCOME_ENABLED
    assert outcome.terminal_fleet_state == "STOPPED"
    assert outcome.fleet_restored is None
    assert requests == []
    assert not any(
        isinstance(call, tuple) and call[0] in {"wait_STOPPED", "wait_RUNNING"} for call in calls
    )


@pytest.mark.parametrize("initial_state", ["STOP_REQUESTED", "START_REQUESTED"])
def test_concurrent_fleet_transition_is_recovery_required_without_request(
    monkeypatch, tmp_path, initial_state
):
    _calls, requests = _install_lifecycle_scenario(
        monkeypatch,
        tmp_path,
        initial_fleet_state=initial_state,
    )

    outcome = run_postcreate_slurm_accounting(**_kwargs(tmp_path))

    assert outcome.outcome == ACCOUNTING_OUTCOME_RECOVERY_REQUIRED
    assert outcome.error_stage == "fleet_describe"
    assert outcome.terminal_fleet_state == initial_state
    assert requests == []


def test_replacement_headnode_is_reconfigured_only_when_identity_changes(monkeypatch, tmp_path):
    calls, _requests = _install_lifecycle_scenario(
        monkeypatch,
        tmp_path,
        replacement_headnode_id="i-replacement",
    )
    configured = []

    outcome = run_postcreate_slurm_accounting(
        **{
            **_kwargs(tmp_path),
            "configure_replacement_headnode": (
                lambda instance_id: configured.append(instance_id) or True
            ),
        }
    )

    assert outcome.outcome == ACCOUNTING_OUTCOME_ENABLED
    assert configured == ["i-replacement"]
    assert ("wait_for_ssm", "i-replacement") in calls
    assert not any(isinstance(call, tuple) and call[0] == "readiness" for call in calls)


def test_accounting_verification_is_read_only_and_runs_as_ubuntu(monkeypatch, tmp_path):
    calls, _requests = _install_lifecycle_scenario(monkeypatch, tmp_path)

    outcome = run_postcreate_slurm_accounting(**_kwargs(tmp_path))

    assert outcome.outcome == ACCOUNTING_OUTCOME_ENABLED
    verify = next(call for call in calls if isinstance(call, tuple) and call[0] == "verify")
    assert verify[1] == "ubuntu"
    command = verify[2]
    assert "sacct -X" in command
    assert "timeout 60" in command
    assert "systemctl is-active slurmdbd" in command
    assert "systemctl is-active slurmctld" in command
    assert "AccountingStorageType" in command
    assert "accounting_storage/slurmdbd" in command
    assert "sacctmgr -nP show cluster" in command
    for forbidden in ("sudo", " restart", " start", " stop", " enable", " disable"):
        assert forbidden not in command


@pytest.mark.parametrize(
    "failure,expected_stage,expected_outcome,expected_requests",
    [
        ("discovery", "service_preparation", ACCOUNTING_OUTCOME_WARNING, []),
        ("stack_creation", "service_preparation", ACCOUNTING_OUTCOME_WARNING, []),
        ("render", "service_preparation", ACCOUNTING_OUTCOME_WARNING, []),
        ("fleet_describe", "fleet_describe", ACCOUNTING_OUTCOME_WARNING, []),
        ("stop", "fleet_stop_request", ACCOUNTING_OUTCOME_WARNING, ["STOP_REQUESTED"]),
        (
            "stop_timeout",
            "fleet_stop_request",
            ACCOUNTING_OUTCOME_RECOVERY_REQUIRED,
            ["STOP_REQUESTED"],
        ),
        (
            "dry_run",
            "update_dry_run",
            ACCOUNTING_OUTCOME_WARNING,
            ["STOP_REQUESTED", "START_REQUESTED"],
        ),
        (
            "submit",
            "update_submit",
            ACCOUNTING_OUTCOME_WARNING,
            ["STOP_REQUESTED", "START_REQUESTED"],
        ),
        (
            "rollback",
            "update_wait",
            ACCOUNTING_OUTCOME_WARNING,
            ["STOP_REQUESTED", "START_REQUESTED"],
        ),
        (
            "update_timeout",
            "update_wait",
            ACCOUNTING_OUTCOME_RECOVERY_REQUIRED,
            ["STOP_REQUESTED"],
        ),
        (
            "indeterminate",
            "update_wait",
            ACCOUNTING_OUTCOME_RECOVERY_REQUIRED,
            ["STOP_REQUESTED"],
        ),
        (
            "headnode_describe",
            "headnode_readiness",
            ACCOUNTING_OUTCOME_WARNING,
            ["STOP_REQUESTED", "START_REQUESTED"],
        ),
        (
            "readiness",
            "headnode_readiness",
            ACCOUNTING_OUTCOME_WARNING,
            ["STOP_REQUESTED", "START_REQUESTED"],
        ),
        (
            "verification",
            "verification",
            ACCOUNTING_OUTCOME_WARNING,
            ["STOP_REQUESTED", "START_REQUESTED"],
        ),
        (
            "restart",
            "fleet_restore_request",
            ACCOUNTING_OUTCOME_RECOVERY_REQUIRED,
            ["STOP_REQUESTED", "START_REQUESTED"],
        ),
        (
            "restart_timeout",
            "fleet_restore_request",
            ACCOUNTING_OUTCOME_RECOVERY_REQUIRED,
            ["STOP_REQUESTED", "START_REQUESTED"],
        ),
    ],
)
def test_failure_matrix_recovery_and_redaction(
    monkeypatch,
    tmp_path,
    capsys,
    caplog,
    failure,
    expected_stage,
    expected_outcome,
    expected_requests,
):
    _calls, requests = _install_lifecycle_scenario(
        monkeypatch,
        tmp_path,
        failure=failure,
    )

    outcome = run_postcreate_slurm_accounting(**_kwargs(tmp_path))
    receipt = outcome.to_receipt()
    warning = warning_message(receipt.error_stage, receipt.recovery_required)
    captured = capsys.readouterr()
    all_public_output = "\n".join(
        [
            repr(outcome),
            json.dumps(asdict(outcome), sort_keys=True),
            receipt.model_dump_json(),
            warning,
            caplog.text,
            captured.out,
            captured.err,
        ]
    )

    assert outcome.error_stage == expected_stage
    assert outcome.outcome == expected_outcome
    assert requests == expected_requests
    if expected_outcome == ACCOUNTING_OUTCOME_RECOVERY_REQUIRED:
        assert outcome.recovery_required is True
        assert "START_REQUESTED" not in requests or failure.startswith("restart")
    for sentinel in (
        "mysql://",
        "db.internal.example",
        "10.91.82.73",
        "arn:aws:secretsmanager",
        "sacct-password",
    ):
        assert sentinel not in all_public_output
