"""Safe state and output helpers for post-create Slurm accounting.

This module intentionally has no API that accepts an exception or free-form
error detail.  Accounting failures may contain resolved database connection
data, so user-facing output and persisted state are assembled only from
bounded enums and the strict non-secret receipt model.
"""

from __future__ import annotations

from pathlib import Path

from daylily_ec.state.models import (
    SlurmAccountingOutcome,
    SlurmAccountingReceipt,
    SlurmAccountingStage,
    StateRecord,
)


def outcome_for_receipt(receipt: SlurmAccountingReceipt) -> SlurmAccountingOutcome:
    """Derive the four-state public outcome from a validated receipt."""

    if receipt.requested_mode == "off":
        return SlurmAccountingOutcome.OFF
    if receipt.recovery_required:
        return SlurmAccountingOutcome.RECOVERY_REQUIRED
    if receipt.error_stage is not None:
        return SlurmAccountingOutcome.WARNING
    if receipt.stage_reached == SlurmAccountingStage.COMPLETE:
        return SlurmAccountingOutcome.ENABLED
    return SlurmAccountingOutcome.WARNING


def apply_receipt_to_state(
    state: StateRecord,
    receipt: SlurmAccountingReceipt,
    receipt_path: Path,
) -> StateRecord:
    """Return a state snapshot updated only with non-secret receipt facts."""

    return state.model_copy(
        update={
            "slurm_accounting_requested_mode": receipt.requested_mode,
            "slurm_accounting_outcome": outcome_for_receipt(receipt),
            "slurm_accounting_receipt_path": str(receipt_path),
            "slurm_accounting_stack_name": receipt.stack_name,
            "slurm_accounting_service_created": receipt.service_created,
            "slurm_accounting_recovery_required": receipt.recovery_required,
        }
    )


def warning_message(
    stage: SlurmAccountingStage,
    recovery_required: bool,
) -> str:
    """Build a loud accounting warning without accepting raw error text."""

    safe_stage = SlurmAccountingStage(stage).value.replace("_", " ")
    if recovery_required:
        return (
            "SLURM ACCOUNTING RECOVERY REQUIRED: cluster creation succeeded, "
            f"but accounting failed during {safe_stage}. The fleet was not "
            "automatically restored because the update state is unsafe or "
            "indeterminate. Inspect the non-secret accounting receipt before "
            "taking recovery action. First describe the cluster and compute "
            "fleet with pcluster; do not request START_REQUESTED until the "
            "cluster update or rollback reaches a known stable terminal state."
        )
    return (
        "SLURM ACCOUNTING WARNING: cluster creation succeeded and the cluster "
        f"was retained, but accounting failed during {safe_stage}. Accounting "
        "remains disabled. Inspect the non-secret accounting receipt for the "
        "bounded lifecycle state. After resolving its recorded stage, retry "
        "with dyec slurm-accounting attach while the fleet is explicitly STOPPED."
    )


def status_message(outcome: SlurmAccountingOutcome) -> str:
    """Return the fixed final-panel label for an accounting outcome."""

    return f"Slurm accounting: {SlurmAccountingOutcome(outcome).value}"
