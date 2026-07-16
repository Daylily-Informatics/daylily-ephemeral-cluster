"""Non-secret state and receipt coverage for post-create accounting."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from daylily_ec.state.models import (
    SlurmAccountingOutcome,
    SlurmAccountingReceipt,
    SlurmAccountingStage,
    StateRecord,
)
from daylily_ec.state.slurm_accounting import (
    apply_receipt_to_state,
    outcome_for_receipt,
    status_message,
    warning_message,
)
from daylily_ec.state.store import (
    load_slurm_accounting_receipt,
    write_slurm_accounting_receipt,
)


def _receipt(**overrides: object) -> SlurmAccountingReceipt:
    values: dict[str, object] = {
        "requested_mode": "on",
        "create_approval_flag": True,
        "cost_acknowledgement_flag": True,
        "service_created": False,
        "stage_reached": SlurmAccountingStage.COMPLETE,
        "update_config_path": "/tmp/daylily/cluster-slurm-accounting-update.yaml",
        "terminal_cluster_state": "UPDATE_COMPLETE",
        "terminal_fleet_state": "RUNNING",
        "fleet_restored": True,
        "error_stage": None,
        "recovery_required": False,
        "stack_name": "dayec-slurm-accounting-us-west-2",
    }
    values.update(overrides)
    return SlurmAccountingReceipt(**values)


def test_receipt_contains_only_non_secret_contract_fields() -> None:
    payload = _receipt().model_dump(mode="json")

    assert set(payload) == {
        "requested_mode",
        "create_approval_flag",
        "cost_acknowledgement_flag",
        "service_created",
        "stage_reached",
        "update_config_path",
        "terminal_cluster_state",
        "terminal_fleet_state",
        "fleet_restored",
        "error_stage",
        "recovery_required",
        "stack_name",
    }
    assert not any(
        token in json.dumps(payload).lower()
        for token in ("mysql://", "secret_arn", "private_ip", "password", "username")
    )


@pytest.mark.parametrize(
    "forbidden_field",
    [
        "uri",
        "private_ip",
        "secret_arn",
        "password",
        "username",
        "slurm_accounting_uri",
        "slurm_accounting_secret_arn",
    ],
)
def test_receipt_rejects_sensitive_or_unknown_fields(forbidden_field: str) -> None:
    with pytest.raises(ValidationError):
        SlurmAccountingReceipt(**{forbidden_field: "SENTINEL_DO_NOT_PRINT"})


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("update_config_path", "mysql://sentinel.internal:3306/slurm"),
        ("update_config_path", "arn:aws:secretsmanager:us-west-2:123:secret:sentinel"),
        ("terminal_cluster_state", "sentinel.internal"),
        ("terminal_cluster_state", "SENTINEL_SECRET"),
        ("terminal_fleet_state", "10.0.0.42"),
        ("terminal_fleet_state", "SENTINEL_PRIVATE_IP"),
        ("stack_name", "mysql://sentinel.internal"),
    ],
)
def test_receipt_rejects_sensitive_shapes_in_safe_fields(field: str, value: str) -> None:
    with pytest.raises(ValidationError):
        _receipt(**{field: value})


def test_write_and_load_receipt_round_trip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    receipt = _receipt()

    path = write_slurm_accounting_receipt(
        receipt,
        cluster_name="fresh-cluster",
        run_id="20260716015218",
    )

    assert path.name == "slurm_accounting_fresh-cluster_20260716015218_receipt.json"
    assert path.read_text(encoding="utf-8").endswith("\n")
    assert load_slurm_accounting_receipt(path) == receipt


@pytest.mark.parametrize(
    ("receipt", "expected"),
    [
        (_receipt(requested_mode="off", stage_reached="off"), SlurmAccountingOutcome.OFF),
        (_receipt(), SlurmAccountingOutcome.ENABLED),
        (
            _receipt(stage_reached="service_preparation", error_stage="service_preparation"),
            SlurmAccountingOutcome.WARNING,
        ),
        (
            _receipt(
                stage_reached="update_wait",
                error_stage="update_wait",
                recovery_required=True,
            ),
            SlurmAccountingOutcome.RECOVERY_REQUIRED,
        ),
    ],
)
def test_outcome_for_receipt(
    receipt: SlurmAccountingReceipt,
    expected: SlurmAccountingOutcome,
) -> None:
    assert outcome_for_receipt(receipt) is expected


def test_apply_receipt_to_state_copies_only_safe_facts(tmp_path: Path) -> None:
    original = StateRecord(cluster_name="fresh-cluster", bucket="keep-me")
    receipt = _receipt(service_created=True, recovery_required=True, error_stage="update_wait")

    updated = apply_receipt_to_state(original, receipt, tmp_path / "receipt.json")

    assert updated.bucket == "keep-me"
    assert updated.slurm_accounting_requested_mode == "on"
    assert updated.slurm_accounting_outcome is SlurmAccountingOutcome.RECOVERY_REQUIRED
    assert updated.slurm_accounting_stack_name == "dayec-slurm-accounting-us-west-2"
    assert updated.slurm_accounting_service_created is True
    assert updated.slurm_accounting_recovery_required is True
    dumped = updated.model_dump(mode="json")
    assert "slurm_accounting_uri" not in dumped
    assert "slurm_accounting_secret_arn" not in dumped
    assert "slurm_accounting_client_security_group_id" not in dumped
    assert "slurm_accounting_database_name" not in dumped
    assert "slurm_accounting_username" not in dumped


def test_legacy_sensitive_state_fields_are_never_reserialized() -> None:
    state = StateRecord(
        cluster_name="greenfield",
        slurm_accounting_uri="mysql://SENTINEL_ENDPOINT",
        slurm_accounting_secret_arn="arn:aws:secretsmanager:SENTINEL_SECRET",
        slurm_accounting_client_security_group_id="sg-SENTINEL_PRIVATE",
        slurm_accounting_database_name="SENTINEL_DATABASE",
        slurm_accounting_username="SENTINEL_USERNAME",
    )

    serialized = state.to_sorted_json()
    assert "SENTINEL" not in serialized
    assert not {
        "slurm_accounting_uri",
        "slurm_accounting_secret_arn",
        "slurm_accounting_client_security_group_id",
        "slurm_accounting_database_name",
        "slurm_accounting_username",
    }.intersection(StateRecord.model_fields)


@pytest.mark.parametrize("recovery_required", [False, True])
def test_warning_message_is_bounded_and_never_accepts_exception_text(
    recovery_required: bool,
) -> None:
    message = warning_message(SlurmAccountingStage.UPDATE_WAIT, recovery_required)

    assert "cluster creation succeeded" in message
    assert "update wait" in message
    assert "SENTINEL_ENDPOINT" not in message
    assert "mysql://" not in message
    assert "arn:aws:secretsmanager" not in message


@pytest.mark.parametrize(
    "outcome",
    [
        SlurmAccountingOutcome.OFF,
        SlurmAccountingOutcome.ENABLED,
        SlurmAccountingOutcome.WARNING,
        SlurmAccountingOutcome.RECOVERY_REQUIRED,
    ],
)
def test_status_message_uses_only_public_outcome(outcome: SlurmAccountingOutcome) -> None:
    assert status_message(outcome) == f"Slurm accounting: {outcome.value}"
