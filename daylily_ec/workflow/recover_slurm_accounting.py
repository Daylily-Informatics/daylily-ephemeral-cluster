"""Crash-safe recovery of a partially provisioned Slurm-accounting cluster.

This public DYEC workflow owns service preparation, compute-fleet lifecycle,
ParallelCluster update submission/reclaim, and final read-only accounting
verification.  Callers supply deterministic identities and persisted paths;
the workflow never discovers an alternate configuration or service target.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from daylily_ec.aws.context import AWSContext, parse_region_az
from daylily_ec.aws.ssm import run_shell, wait_for_ssm_online
from daylily_ec.pcluster.monitor import wait_for_cluster_update
from daylily_ec.pcluster.runner import (
    describe_cluster,
    describe_compute_fleet,
    update_cluster,
)
from daylily_ec.workflow.attach_slurm_accounting import (
    PreparedSlurmAccountingUpdate,
    prepare_slurm_accounting_update,
)
from daylily_ec.workflow.compute_fleet import (
    ClusterIdleProof,
    probe_cluster_idle,
    run_compute_fleet_transition,
)
from daylily_ec.workflow.postcreate_slurm_accounting import ACCOUNTING_VERIFICATION_COMMAND

SLURM_ACCOUNTING_RECOVERY_SCHEMA = "dyec.slurm_accounting_recovery.v1"
RECOVERY_RECEIPT_FILENAME = "slurm-accounting-recovery.json"
UPDATE_CONFIGURATION_FILENAME = "slurm-accounting-update.yaml"
RECOVERY_STATUS_IN_PROGRESS = "in_progress"
RECOVERY_STATUS_COMPLETE = "complete"
MAX_RECOVERY_RECEIPT_BYTES = 1024 * 1024
SUBMISSION_INTENT_RESOLUTION_SECONDS = 300.0

PHASE_RENDER_INTENT = "render_intent"
PHASE_SERVICE_READY = "service_ready"
PHASE_PRE_STOP_EXACT_TARGET_VERIFIED = "pre_stop_exact_target_verified"
PHASE_POST_PREPARE_IDLE_PROOF = "post_prepare_idle_proof"
PHASE_FLEET_STOPPED = "fleet_stopped"
PHASE_UPDATE_SUBMISSION_INTENT = "update_submission_intent"
PHASE_UPDATE_SUBMISSION = "update_submission"
PHASE_UPDATE_COMPLETE = "update_complete"
PHASE_POST_UPDATE_EXACT_TARGET_VERIFIED = "post_update_exact_target_verified"
PHASE_FLEET_RUNNING = "fleet_running"
PHASE_ACCOUNTING_VERIFIED = "accounting_verified"

IN_PROGRESS_RECOVERY_PHASES = frozenset(
    {
        PHASE_RENDER_INTENT,
        PHASE_SERVICE_READY,
        PHASE_PRE_STOP_EXACT_TARGET_VERIFIED,
        PHASE_POST_PREPARE_IDLE_PROOF,
        PHASE_FLEET_STOPPED,
        PHASE_UPDATE_SUBMISSION_INTENT,
        PHASE_UPDATE_SUBMISSION,
        PHASE_UPDATE_COMPLETE,
        PHASE_POST_UPDATE_EXACT_TARGET_VERIFIED,
        PHASE_FLEET_RUNNING,
        PHASE_ACCOUNTING_VERIFIED,
    }
)
CREATE_COMPLETE_RECEIPT_PHASES = frozenset(
    {
        PHASE_RENDER_INTENT,
        PHASE_SERVICE_READY,
        PHASE_PRE_STOP_EXACT_TARGET_VERIFIED,
        PHASE_POST_PREPARE_IDLE_PROOF,
        PHASE_FLEET_STOPPED,
        PHASE_UPDATE_SUBMISSION_INTENT,
        PHASE_UPDATE_SUBMISSION,
    }
)
UPDATE_PROGRESS_RECEIPT_PHASES = frozenset(
    {PHASE_UPDATE_SUBMISSION_INTENT, PHASE_UPDATE_SUBMISSION}
)
UPDATE_COMPLETE_RECEIPT_PHASES = frozenset(
    {
        *UPDATE_PROGRESS_RECEIPT_PHASES,
        PHASE_UPDATE_COMPLETE,
        PHASE_POST_UPDATE_EXACT_TARGET_VERIFIED,
        PHASE_FLEET_RUNNING,
        PHASE_ACCOUNTING_VERIFIED,
    }
)

UPDATE_PROGRESS_STATES = frozenset(
    {
        "UPDATE_IN_PROGRESS",
        "UPDATE_COMPLETE_CLEANUP_IN_PROGRESS",
    }
)
SUPPORTED_INITIAL_CLUSTER_STATES = frozenset(
    {"CREATE_COMPLETE", "UPDATE_COMPLETE", *UPDATE_PROGRESS_STATES}
)
SUPPORTED_INITIAL_FLEET_STATES = frozenset(
    {
        "RUNNING",
        "STOPPED",
        "STOP_REQUESTED",
        "STOPPING",
        "START_REQUESTED",
        "STARTING",
    }
)


class SlurmAccountingRecoveryError(RuntimeError):
    """Raised when accounting recovery cannot continue without ambiguity."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _required_text(value: object, *, field: str) -> str:
    text = str(value or "")
    if not text or text != text.strip():
        raise SlurmAccountingRecoveryError(f"{field} must be a non-empty trimmed string.")
    return text


def _positive_number(value: object, *, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        raise SlurmAccountingRecoveryError(f"{field} must be greater than zero.")
    return float(value)


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError:
        raise SlurmAccountingRecoveryError(f"Could not read required file: {path}.") from None
    return digest.hexdigest()


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> str:
    content = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(
        dir=str(path.parent),
        prefix=f".{path.name}.tmp-",
        text=True,
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
    except OSError:
        temporary_path.unlink(missing_ok=True)
        raise SlurmAccountingRecoveryError(
            "Could not atomically persist the accounting recovery receipt."
        ) from None
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _phase(phase: str, status: str) -> dict[str, str]:
    return {"phase": phase, "status": status, "observed_at": _utc_now()}


def _describe_cluster_state(
    cluster_name: str,
    region: str,
    *,
    profile: str | None,
) -> tuple[str, dict[str, Any]]:
    try:
        result = describe_cluster(cluster_name, region, profile=profile)
    except Exception:  # noqa: BLE001 - provider exceptions are normalized at this boundary
        raise SlurmAccountingRecoveryError("Could not describe the recovery cluster.") from None
    if not result.success or not isinstance(result.json_body, dict):
        raise SlurmAccountingRecoveryError("Could not describe the recovery cluster.")
    status = result.json_body.get("clusterStatus")
    if not isinstance(status, str) or not status:
        raise SlurmAccountingRecoveryError("The recovery cluster has no valid status.")
    return status, result.json_body


def _describe_fleet_state(
    cluster_name: str,
    region: str,
    *,
    profile: str | None,
) -> str:
    try:
        result = describe_compute_fleet(cluster_name, region, profile=profile)
    except Exception:  # noqa: BLE001 - provider exceptions are normalized at this boundary
        raise SlurmAccountingRecoveryError("Could not describe the recovery fleet.") from None
    if not result.success:
        raise SlurmAccountingRecoveryError("Could not describe the recovery fleet.")
    status = result.json_body.get("status")
    if status not in SUPPORTED_INITIAL_FLEET_STATES:
        raise SlurmAccountingRecoveryError("The recovery fleet returned an unsupported state.")
    return status


def _remaining(deadline: float, monotonic_fn: Callable[[], float]) -> float:
    remaining = deadline - monotonic_fn()
    if remaining <= 0:
        raise SlurmAccountingRecoveryError("The accounting recovery timed out.")
    return remaining


def _existing_update_config(path: Path) -> tuple[str, str]:
    if not path.exists():
        return "", ""
    if not path.is_file():
        raise SlurmAccountingRecoveryError(
            "The deterministic accounting update path exists but is not a file."
        )
    return str(path), _sha256_path(path)


def _resolve_account_id(*, region: str, profile: str) -> str:
    try:
        account_id = str(AWSContext.build_region(region, profile=profile).account_id or "").strip()
    except Exception:  # noqa: BLE001 - credential/provider errors are normalized here
        raise SlurmAccountingRecoveryError(
            "The exact AWS profile/account identity could not be resolved."
        ) from None
    if not account_id:
        raise SlurmAccountingRecoveryError(
            "The exact AWS profile resolved without an account identity."
        )
    return account_id


def _validate_prepared_identity(
    prepared: PreparedSlurmAccountingUpdate,
    *,
    cluster_name: str,
    region: str,
    stack_name: str,
    database_name: str,
    db_username: str,
) -> None:
    if (
        prepared.cluster_name != cluster_name
        or prepared.region != region
        or prepared.accounting_stack_name != stack_name
        or prepared.database_name != database_name
        or prepared.db_username != db_username
    ):
        raise SlurmAccountingRecoveryError(
            "The prepared accounting stack/database/user identity does not match the "
            "exact recovery request."
        )


def _progress_payload(
    *,
    phase: str,
    cluster_name: str,
    region: str,
    region_az: str,
    aws_profile: str,
    aws_account_id: str,
    stack_name: str,
    database_name: str,
    db_username: str,
    instance_type: str,
    create_if_missing: bool,
    acknowledge_create_cost: bool,
    service_created: bool,
    source_config: Path,
    source_sha256: str,
    update_config: Path,
    update_sha256: str | None,
    started_at: str,
    phases: list[dict[str, str]],
) -> dict[str, Any]:
    if phase not in IN_PROGRESS_RECOVERY_PHASES:
        raise SlurmAccountingRecoveryError(
            "The accounting recovery cannot persist an unknown phase."
        )
    return {
        "schema_version": SLURM_ACCOUNTING_RECOVERY_SCHEMA,
        "ok": False,
        "terminal": False,
        "status": RECOVERY_STATUS_IN_PROGRESS,
        "phase": phase,
        "cluster": cluster_name,
        "region": region,
        "region_az": region_az,
        "aws_profile": aws_profile,
        "aws_account_id": aws_account_id,
        "accounting_stack_name": stack_name,
        "database_name": database_name,
        "db_username": db_username,
        "instance_type": instance_type,
        "create_slurm_accounting_if_missing": create_if_missing,
        "acknowledge_slurm_accounting_create_cost": acknowledge_create_cost,
        "service_created": service_created,
        "cluster_configuration_path": str(source_config),
        "cluster_configuration_sha256": source_sha256,
        "update_configuration_path": str(update_config),
        "update_configuration_sha256": update_sha256,
        "phase_receipts": list(phases),
        "started_at": started_at,
        "updated_at": _utc_now(),
    }


def _persist_progress_receipt(
    receipt_path: Path,
    *,
    phase: str,
    cluster_name: str,
    region: str,
    region_az: str,
    aws_profile: str,
    aws_account_id: str,
    stack_name: str,
    database_name: str,
    db_username: str,
    instance_type: str,
    create_if_missing: bool,
    acknowledge_create_cost: bool,
    service_created: bool,
    source_config: Path,
    source_sha256: str,
    update_config: Path,
    update_sha256: str | None,
    started_at: str,
    phases: list[dict[str, str]],
) -> None:
    _atomic_write_json(
        receipt_path,
        _progress_payload(
            phase=phase,
            cluster_name=cluster_name,
            region=region,
            region_az=region_az,
            aws_profile=aws_profile,
            aws_account_id=aws_account_id,
            stack_name=stack_name,
            database_name=database_name,
            db_username=db_username,
            instance_type=instance_type,
            create_if_missing=create_if_missing,
            acknowledge_create_cost=acknowledge_create_cost,
            service_created=service_created,
            source_config=source_config,
            source_sha256=source_sha256,
            update_config=update_config,
            update_sha256=update_sha256,
            started_at=started_at,
            phases=phases,
        ),
    )


def _load_bound_recovery_receipt(
    receipt_path: Path,
    *,
    cluster_name: str,
    region: str,
    region_az: str,
    aws_profile: str,
    aws_account_id: str,
    stack_name: str,
    database_name: str,
    db_username: str,
    instance_type: str,
    create_if_missing: bool,
    acknowledge_create_cost: bool,
    source_config: Path,
    source_sha256: str,
    update_config: Path,
) -> dict[str, Any]:
    try:
        if not receipt_path.is_file() or receipt_path.stat().st_size > MAX_RECOVERY_RECEIPT_BYTES:
            raise OSError
        payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        raise SlurmAccountingRecoveryError(
            "The deterministic accounting recovery identity receipt is missing or invalid."
        ) from None
    if not isinstance(payload, dict):
        raise SlurmAccountingRecoveryError(
            "The deterministic accounting recovery identity receipt is invalid."
        )
    status = payload.get("status")
    terminal = payload.get("terminal")
    if (
        payload.get("schema_version") != SLURM_ACCOUNTING_RECOVERY_SCHEMA
        or status not in {RECOVERY_STATUS_IN_PROGRESS, RECOVERY_STATUS_COMPLETE}
        or not isinstance(terminal, bool)
        or terminal != (status == RECOVERY_STATUS_COMPLETE)
    ):
        raise SlurmAccountingRecoveryError(
            "The deterministic accounting recovery identity receipt has an invalid schema/state."
        )
    expected_values: dict[str, object] = {
        "cluster": cluster_name,
        "region": region,
        "region_az": region_az,
        "aws_profile": aws_profile,
        "aws_account_id": aws_account_id,
        "accounting_stack_name": stack_name,
        "database_name": database_name,
        "db_username": db_username,
        "instance_type": instance_type,
        "create_slurm_accounting_if_missing": create_if_missing,
        "acknowledge_slurm_accounting_create_cost": acknowledge_create_cost,
        "cluster_configuration_path": str(source_config),
        "cluster_configuration_sha256": source_sha256,
        "update_configuration_path": str(update_config),
    }
    if any(payload.get(field) != value for field, value in expected_values.items()):
        raise SlurmAccountingRecoveryError(
            "The deterministic accounting recovery identity receipt does not match the "
            "exact request."
        )
    recorded_phase = payload.get("phase")
    if status == RECOVERY_STATUS_IN_PROGRESS:
        if not isinstance(recorded_phase, str) or recorded_phase not in IN_PROGRESS_RECOVERY_PHASES:
            raise SlurmAccountingRecoveryError(
                "The deterministic accounting recovery identity receipt has an "
                "unknown in-progress phase."
            )
    elif "phase" in payload:
        raise SlurmAccountingRecoveryError(
            "A terminal accounting recovery receipt must not contain an in-progress phase."
        )
    recorded_update_sha256 = payload.get("update_configuration_sha256")
    if recorded_phase == PHASE_RENDER_INTENT:
        if recorded_update_sha256 is not None:
            raise SlurmAccountingRecoveryError(
                "The pre-render recovery identity receipt has an unexpected update hash."
            )
    elif (
        not update_config.is_file()
        or not isinstance(recorded_update_sha256, str)
        or len(recorded_update_sha256) != 64
        or recorded_update_sha256 != _sha256_path(update_config)
    ):
        raise SlurmAccountingRecoveryError(
            "The deterministic accounting update configuration hash does not match its "
            "recovery identity receipt."
        )
    phase_receipts = payload.get("phase_receipts")
    if not isinstance(phase_receipts, list) or not all(
        isinstance(item, dict)
        and set(item) == {"phase", "status", "observed_at"}
        and all(isinstance(value, str) and value for value in item.values())
        for item in phase_receipts
    ):
        raise SlurmAccountingRecoveryError(
            "The deterministic accounting recovery phase history is invalid."
        )
    if not isinstance(payload.get("started_at"), str) or not payload["started_at"]:
        raise SlurmAccountingRecoveryError(
            "The deterministic accounting recovery start time is invalid."
        )
    if not isinstance(payload.get("service_created"), bool):
        raise SlurmAccountingRecoveryError(
            "The deterministic accounting recovery service-created flag is invalid."
        )
    return payload


def _validate_provider_receipt_phase(
    *,
    provider_state: str,
    receipt: dict[str, Any],
) -> None:
    """Reject impossible provider-state/recovery-phase pairs before mutation."""

    status = receipt["status"]
    if status == RECOVERY_STATUS_COMPLETE:
        if provider_state != "UPDATE_COMPLETE":
            raise SlurmAccountingRecoveryError(
                "A terminal recovery receipt is valid only while the provider reports "
                "UPDATE_COMPLETE."
            )
        return

    phase = str(receipt["phase"])
    if provider_state == "CREATE_COMPLETE":
        allowed_phases = CREATE_COMPLETE_RECEIPT_PHASES
    elif provider_state in UPDATE_PROGRESS_STATES:
        allowed_phases = UPDATE_PROGRESS_RECEIPT_PHASES
    elif provider_state == "UPDATE_COMPLETE":
        allowed_phases = UPDATE_COMPLETE_RECEIPT_PHASES
    else:  # Defensive: callers validate provider states before this boundary.
        raise SlurmAccountingRecoveryError(
            "The provider returned an unsupported cluster state for recovery."
        )
    if phase not in allowed_phases:
        raise SlurmAccountingRecoveryError(
            f"Recovery phase {phase!r} is invalid while the provider reports {provider_state}."
        )


def _verify_exact_target_binding(
    *,
    cluster_name: str,
    region: str,
    region_az: str,
    profile: str,
    source_config: Path,
    source_sha256: str,
    update_config: Path,
    update_sha256: str,
    stack_name: str,
    database_name: str,
    db_username: str,
    instance_type: str,
) -> None:
    if _sha256_path(source_config) != source_sha256:
        raise SlurmAccountingRecoveryError(
            "The source cluster configuration changed after recovery identity capture."
        )
    if _sha256_path(update_config) != update_sha256:
        raise SlurmAccountingRecoveryError(
            "The bound accounting update configuration changed after identity capture."
        )
    with tempfile.TemporaryDirectory(prefix="dyec-accounting-target-verify-") as temp_dir:
        candidate_path = Path(temp_dir) / UPDATE_CONFIGURATION_FILENAME
        try:
            prepared = prepare_slurm_accounting_update(
                cluster_name=cluster_name,
                region=region,
                profile=profile,
                cluster_configuration=source_config,
                stack_name=stack_name,
                database_name=database_name,
                db_username=db_username,
                instance_type=instance_type,
                create_if_missing=False,
                destination_config=candidate_path,
                expected_region_az=region_az,
                exact_target_only=True,
            )
        except Exception:  # noqa: BLE001 - exact target errors are normalized here
            raise SlurmAccountingRecoveryError(
                "The exact accounting singleton could not be revalidated safely."
            ) from None
        _validate_prepared_identity(
            prepared,
            cluster_name=cluster_name,
            region=region,
            stack_name=stack_name,
            database_name=database_name,
            db_username=db_username,
        )
        candidate_sha256 = _sha256_path(candidate_path)
    if _sha256_path(source_config) != source_sha256:
        raise SlurmAccountingRecoveryError(
            "The source cluster configuration changed while accounting was revalidated."
        )
    if _sha256_path(update_config) != update_sha256:
        raise SlurmAccountingRecoveryError(
            "The bound accounting update configuration changed while accounting was revalidated."
        )
    if candidate_sha256 != update_sha256:
        raise SlurmAccountingRecoveryError(
            "The exact accounting singleton no longer renders the bound update configuration."
        )


def _resolve_delayed_update_submission(
    *,
    cluster_name: str,
    region: str,
    profile: str,
    deadline: float,
    poll_interval: float,
    monotonic_fn: Callable[[], float],
    sleep_fn: Callable[[float], None],
) -> str:
    resolution_deadline = min(
        deadline,
        monotonic_fn() + SUBMISSION_INTENT_RESOLUTION_SECONDS,
    )
    while True:
        status, _payload = _describe_cluster_state(
            cluster_name,
            region,
            profile=profile,
        )
        if status in {*UPDATE_PROGRESS_STATES, "UPDATE_COMPLETE"}:
            return status
        if status != "CREATE_COMPLETE":
            raise SlurmAccountingRecoveryError(
                "The cluster entered an unexpected state while resolving update submission intent."
            )
        remaining = resolution_deadline - monotonic_fn()
        if remaining <= 0:
            return status
        sleep_fn(min(poll_interval, remaining))


def _verify_accounting(
    *,
    cluster_name: str,
    region: str,
    profile: str | None,
    timeout: float,
) -> str:
    bounded_timeout = min(int(timeout), 600)
    if bounded_timeout < 120:
        raise SlurmAccountingRecoveryError(
            "Less than 120 seconds remain for bounded Slurm accounting verification."
        )
    _status, payload = _describe_cluster_state(cluster_name, region, profile=profile)
    head_node = payload.get("headNode")
    instance_id = head_node.get("instanceId") if isinstance(head_node, dict) else None
    if not isinstance(instance_id, str) or not instance_id:
        raise SlurmAccountingRecoveryError(
            "The updated cluster description has no headnode identity."
        )
    try:
        wait_for_ssm_online(
            instance_id,
            region,
            profile=profile,
            timeout=min(bounded_timeout, 120),
        )
        run_shell(
            instance_id,
            region,
            ACCOUNTING_VERIFICATION_COMMAND,
            profile=profile,
            as_user="ubuntu",
            timeout=bounded_timeout,
            comment="Validate recovered Slurm accounting read-only",
        )
    except Exception:  # noqa: BLE001 - SSM/provider exceptions are normalized here
        raise SlurmAccountingRecoveryError(
            "Slurm accounting verification failed after fleet restoration."
        ) from None
    return instance_id


@dataclass(frozen=True)
class SlurmAccountingRecoveryResult:
    """Stable, non-secret terminal recovery receipt."""

    cluster: str
    region: str
    region_az: str
    aws_profile: str
    aws_account_id: str
    accounting_stack_name: str
    database_name: str
    db_username: str
    instance_type: str
    create_slurm_accounting_if_missing: bool
    acknowledge_slurm_accounting_create_cost: bool
    service_created: bool
    cluster_configuration_path: str
    cluster_configuration_sha256: str
    update_configuration_path: str
    update_configuration_sha256: str
    initial_cluster_state: str
    initial_fleet_state: str
    final_cluster_state: str
    final_fleet_state: str
    update_submitted: bool
    update_reclaimed: bool
    fleet_stop_submitted: bool
    fleet_start_submitted: bool
    accounting_verified: bool
    phase_receipts: tuple[dict[str, str], ...]
    started_at: str
    completed_at: str
    elapsed_seconds: float
    recovery_receipt_path: str
    recovery_receipt_sha256: str

    def _receipt_payload(self) -> dict[str, Any]:
        return {
            "schema_version": SLURM_ACCOUNTING_RECOVERY_SCHEMA,
            "ok": True,
            "terminal": True,
            "status": RECOVERY_STATUS_COMPLETE,
            "cluster": self.cluster,
            "region": self.region,
            "region_az": self.region_az,
            "aws_profile": self.aws_profile,
            "aws_account_id": self.aws_account_id,
            "accounting_stack_name": self.accounting_stack_name,
            "database_name": self.database_name,
            "db_username": self.db_username,
            "instance_type": self.instance_type,
            "create_slurm_accounting_if_missing": self.create_slurm_accounting_if_missing,
            "acknowledge_slurm_accounting_create_cost": (
                self.acknowledge_slurm_accounting_create_cost
            ),
            "service_created": self.service_created,
            "cluster_configuration_path": self.cluster_configuration_path,
            "cluster_configuration_sha256": self.cluster_configuration_sha256,
            "update_configuration_path": self.update_configuration_path,
            "update_configuration_sha256": self.update_configuration_sha256,
            "initial_cluster_state": self.initial_cluster_state,
            "initial_fleet_state": self.initial_fleet_state,
            "final_cluster_state": self.final_cluster_state,
            "final_fleet_state": self.final_fleet_state,
            "update_submitted": self.update_submitted,
            "update_reclaimed": self.update_reclaimed,
            "fleet_stop_submitted": self.fleet_stop_submitted,
            "fleet_start_submitted": self.fleet_start_submitted,
            "accounting_verified": self.accounting_verified,
            "phase_receipts": list(self.phase_receipts),
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "elapsed_seconds": round(self.elapsed_seconds, 3),
        }

    def to_payload(self) -> dict[str, Any]:
        return {
            **self._receipt_payload(),
            "recovery_receipt_path": self.recovery_receipt_path,
            "recovery_receipt_sha256": self.recovery_receipt_sha256,
        }


def recover_slurm_accounting(
    *,
    cluster_name: str,
    region: str,
    region_az: str,
    profile: str | None,
    cluster_configuration: Path,
    output_dir: Path,
    stack_name: str,
    database_name: str,
    db_username: str,
    instance_type: str,
    create_slurm_accounting_if_missing: bool,
    acknowledge_slurm_accounting_create_cost: bool,
    timeout_seconds: float,
    poll_interval_seconds: float,
    idle_probe_fn: Callable[..., ClusterIdleProof] = probe_cluster_idle,
    account_id_resolver: Callable[..., str] = _resolve_account_id,
    monotonic_fn: Callable[[], float] = time.monotonic,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> SlurmAccountingRecoveryResult:
    """Recover one exact cluster to verified accounting and a running fleet."""

    cluster_name = _required_text(cluster_name, field="cluster")
    region = _required_text(region, field="region")
    region_az = _required_text(region_az, field="region_az")
    profile = _required_text(profile, field="profile")
    stack_name = _required_text(stack_name, field="stack_name")
    database_name = _required_text(database_name, field="database_name")
    db_username = _required_text(db_username, field="db_username")
    instance_type = _required_text(instance_type, field="instance_type")
    timeout = _positive_number(timeout_seconds, field="timeout_seconds")
    poll_interval = _positive_number(
        poll_interval_seconds,
        field="poll_interval_seconds",
    )
    try:
        parsed_region, _az = parse_region_az(region_az)
    except ValueError:
        raise SlurmAccountingRecoveryError("region_az is invalid.") from None
    if parsed_region != region:
        raise SlurmAccountingRecoveryError("region_az does not belong to region.")
    if create_slurm_accounting_if_missing != acknowledge_slurm_accounting_create_cost:
        raise SlurmAccountingRecoveryError(
            "--create-slurm-accounting-if-missing and "
            "--acknowledge-slurm-accounting-create-cost must be supplied together."
        )
    aws_account_id = _required_text(
        account_id_resolver(region=region, profile=profile),
        field="aws_account_id",
    )

    source_config = cluster_configuration.expanduser().resolve()
    if not source_config.is_file():
        raise SlurmAccountingRecoveryError(
            "cluster_configuration must be an existing regular file."
        )
    source_sha256 = _sha256_path(source_config)
    destination_dir = output_dir.expanduser().resolve()
    if destination_dir.exists() and not destination_dir.is_dir():
        raise SlurmAccountingRecoveryError("output_dir exists but is not a directory.")
    try:
        destination_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        raise SlurmAccountingRecoveryError("Could not create output_dir.") from None
    update_config = destination_dir / UPDATE_CONFIGURATION_FILENAME
    receipt_path = destination_dir / RECOVERY_RECEIPT_FILENAME

    started_at = _utc_now()
    start = monotonic_fn()
    deadline = start + timeout
    phases: list[dict[str, str]] = []
    initial_cluster_state, _initial_payload = _describe_cluster_state(
        cluster_name,
        region,
        profile=profile,
    )
    if initial_cluster_state not in SUPPORTED_INITIAL_CLUSTER_STATES:
        raise SlurmAccountingRecoveryError(
            "Recovery supports only CREATE_COMPLETE, UPDATE_IN_PROGRESS, "
            "UPDATE_COMPLETE_CLEANUP_IN_PROGRESS, or UPDATE_COMPLETE."
        )
    initial_fleet_state = _describe_fleet_state(cluster_name, region, profile=profile)
    if initial_cluster_state in UPDATE_PROGRESS_STATES and initial_fleet_state in {
        "RUNNING",
        "START_REQUESTED",
        "STARTING",
    }:
        raise SlurmAccountingRecoveryError(
            "An in-progress accounting update must retain a stopped or stopping fleet."
        )
    accounting_stack_name = stack_name
    service_created = False
    update_configuration_path, update_configuration_sha256 = _existing_update_config(update_config)
    receipt_exists = receipt_path.exists()
    update_exists = bool(update_configuration_path)
    if update_exists and not receipt_exists:
        raise SlurmAccountingRecoveryError(
            "The deterministic accounting update configuration exists without its "
            "write-ahead recovery identity receipt."
        )
    bound_receipt: dict[str, Any] | None = None
    bound_phase = ""
    if receipt_exists:
        bound_receipt = _load_bound_recovery_receipt(
            receipt_path,
            cluster_name=cluster_name,
            region=region,
            region_az=region_az,
            aws_profile=profile,
            aws_account_id=aws_account_id,
            stack_name=stack_name,
            database_name=database_name,
            db_username=db_username,
            instance_type=instance_type,
            create_if_missing=create_slurm_accounting_if_missing,
            acknowledge_create_cost=acknowledge_slurm_accounting_create_cost,
            source_config=source_config,
            source_sha256=source_sha256,
            update_config=update_config,
        )
        phases = [dict(item) for item in bound_receipt["phase_receipts"]]
        phases.append(_phase("inventory", "reclaimed"))
        started_at = str(bound_receipt["started_at"])
        service_created = bool(bound_receipt["service_created"])
        bound_phase = str(bound_receipt.get("phase") or "")
        _validate_provider_receipt_phase(
            provider_state=initial_cluster_state,
            receipt=bound_receipt,
        )
    else:
        phases.append(_phase("inventory", "complete"))
    if initial_cluster_state != "CREATE_COMPLETE" and bound_receipt is None:
        raise SlurmAccountingRecoveryError(
            "A deterministic accounting update and matching recovery identity receipt are "
            "required for an already-started or completed update."
        )
    update_submitted = False
    update_reclaimed = initial_cluster_state in UPDATE_PROGRESS_STATES
    fleet_stop_submitted = False

    def persist_progress(phase: str) -> None:
        _persist_progress_receipt(
            receipt_path,
            phase=phase,
            cluster_name=cluster_name,
            region=region,
            region_az=region_az,
            aws_profile=profile,
            aws_account_id=aws_account_id,
            stack_name=stack_name,
            database_name=database_name,
            db_username=db_username,
            instance_type=instance_type,
            create_if_missing=create_slurm_accounting_if_missing,
            acknowledge_create_cost=acknowledge_slurm_accounting_create_cost,
            service_created=service_created,
            source_config=source_config,
            source_sha256=source_sha256,
            update_config=update_config,
            update_sha256=(None if phase == PHASE_RENDER_INTENT else update_configuration_sha256),
            started_at=started_at,
            phases=phases,
        )

    if initial_cluster_state == "CREATE_COMPLETE":
        if initial_fleet_state in {"START_REQUESTED", "STARTING"}:
            raise SlurmAccountingRecoveryError(
                "The CREATE_COMPLETE fleet is starting; recovery refuses ambiguous state."
            )
        idle_proof = idle_probe_fn(
            cluster_name=cluster_name,
            region=region,
            profile=profile,
            timeout=max(1, int(_remaining(deadline, monotonic_fn))),
        )
        if not idle_proof.idle:
            raise SlurmAccountingRecoveryError(
                "Accounting recovery refused because controllers or Slurm jobs remain."
            )
        phases.append(_phase("idle_proof", "complete"))

        provider_update_already_started = False
        if bound_phase in {PHASE_UPDATE_SUBMISSION_INTENT, PHASE_UPDATE_SUBMISSION}:
            resolved_state = _resolve_delayed_update_submission(
                cluster_name=cluster_name,
                region=region,
                profile=profile,
                deadline=deadline,
                poll_interval=poll_interval,
                monotonic_fn=monotonic_fn,
                sleep_fn=sleep_fn,
            )
            if resolved_state in {*UPDATE_PROGRESS_STATES, "UPDATE_COMPLETE"}:
                provider_update_already_started = True
                update_reclaimed = True
            else:
                raise SlurmAccountingRecoveryError(
                    "A reclaimed accounting update-submission intent remains ambiguous "
                    "after bounded provider-state polling; recovery will not resubmit it."
                )

        if provider_update_already_started:
            phases.append(_phase(PHASE_UPDATE_SUBMISSION, "reclaimed"))
            persist_progress(PHASE_UPDATE_SUBMISSION)
        else:
            needs_render = bound_receipt is None or bound_phase == PHASE_RENDER_INTENT
            if needs_render:
                if bound_receipt is None:
                    phases.append(_phase(PHASE_RENDER_INTENT, "pending"))
                    persist_progress(PHASE_RENDER_INTENT)
                try:
                    prepared: PreparedSlurmAccountingUpdate = prepare_slurm_accounting_update(
                        cluster_name=cluster_name,
                        region=region,
                        profile=profile,
                        cluster_configuration=source_config,
                        stack_name=stack_name,
                        database_name=database_name,
                        db_username=db_username,
                        instance_type=instance_type,
                        create_if_missing=create_slurm_accounting_if_missing,
                        destination_config=update_config,
                        expected_region_az=region_az,
                        exact_target_only=True,
                    )
                except Exception:  # noqa: BLE001 - preparation errors normalized here
                    raise SlurmAccountingRecoveryError(
                        "The exact accounting service/update configuration was not prepared."
                    ) from None
                _validate_prepared_identity(
                    prepared,
                    cluster_name=cluster_name,
                    region=region,
                    stack_name=stack_name,
                    database_name=database_name,
                    db_username=db_username,
                )
                if prepared.update_config_path.resolve() != update_config:
                    raise SlurmAccountingRecoveryError(
                        "Accounting preparation did not write the deterministic update path."
                    )
                if _sha256_path(source_config) != source_sha256:
                    raise SlurmAccountingRecoveryError(
                        "The source cluster configuration changed while accounting was rendered."
                    )
                accounting_stack_name = prepared.accounting_stack_name
                service_created = prepared.service_created
                update_configuration_path = str(update_config)
                update_configuration_sha256 = _sha256_path(update_config)
                phases.append(_phase(PHASE_SERVICE_READY, "complete"))
                persist_progress(PHASE_SERVICE_READY)
            else:
                _verify_exact_target_binding(
                    cluster_name=cluster_name,
                    region=region,
                    region_az=region_az,
                    profile=profile,
                    source_config=source_config,
                    source_sha256=source_sha256,
                    update_config=update_config,
                    update_sha256=update_configuration_sha256,
                    stack_name=stack_name,
                    database_name=database_name,
                    db_username=db_username,
                    instance_type=instance_type,
                )
                phases.append(_phase(PHASE_PRE_STOP_EXACT_TARGET_VERIFIED, "reclaimed"))
                persist_progress(PHASE_PRE_STOP_EXACT_TARGET_VERIFIED)

            post_prepare_idle_proof = idle_probe_fn(
                cluster_name=cluster_name,
                region=region,
                profile=profile,
                timeout=max(1, int(_remaining(deadline, monotonic_fn))),
            )
            if not post_prepare_idle_proof.idle:
                raise SlurmAccountingRecoveryError(
                    "Accounting recovery refused because controllers or Slurm jobs "
                    "appeared during service preparation."
                )
            phases.append(_phase(PHASE_POST_PREPARE_IDLE_PROOF, "complete"))
            persist_progress(PHASE_POST_PREPARE_IDLE_PROOF)

            stop_result = run_compute_fleet_transition(
                cluster_name=cluster_name,
                region=region,
                profile=profile,
                request_status="STOP_REQUESTED",
                wait_for_status="STOPPED",
                drain=False,
                timeout_seconds=_remaining(deadline, monotonic_fn),
                poll_interval_seconds=poll_interval,
                idle_probe_fn=lambda **_kwargs: post_prepare_idle_proof,
                monotonic_fn=monotonic_fn,
                sleep_fn=sleep_fn,
            )
            fleet_stop_submitted = stop_result.request_submitted
            phases.append(_phase(PHASE_FLEET_STOPPED, "complete"))
            persist_progress(PHASE_FLEET_STOPPED)

            try:
                dry_run = update_cluster(
                    cluster_name,
                    update_configuration_path,
                    region,
                    profile=profile,
                    dry_run=True,
                )
            except Exception:  # noqa: BLE001 - dry-run provider errors normalized here
                dry_run = None
            if dry_run is None or not dry_run.success:
                raise SlurmAccountingRecoveryError(
                    "ParallelCluster rejected the accounting update dry-run."
                )
            phases.append(_phase(PHASE_UPDATE_SUBMISSION_INTENT, "pending"))
            persist_progress(PHASE_UPDATE_SUBMISSION_INTENT)
            try:
                submitted = update_cluster(
                    cluster_name,
                    update_configuration_path,
                    region,
                    profile=profile,
                    dry_run=False,
                )
            except Exception:  # noqa: BLE001 - bounded provider resolution follows
                submitted = None
            if submitted is None or not submitted.success:
                observed_state = _resolve_delayed_update_submission(
                    cluster_name=cluster_name,
                    region=region,
                    profile=profile,
                    deadline=deadline,
                    poll_interval=poll_interval,
                    monotonic_fn=monotonic_fn,
                    sleep_fn=sleep_fn,
                )
                if observed_state == "CREATE_COMPLETE":
                    raise SlurmAccountingRecoveryError(
                        "The accounting update submission remains unresolved after bounded "
                        "provider-state polling."
                    )
                update_reclaimed = True
            else:
                update_submitted = True
            phases.append(
                _phase(
                    PHASE_UPDATE_SUBMISSION,
                    "reclaimed" if update_reclaimed else "complete",
                )
            )
            persist_progress(PHASE_UPDATE_SUBMISSION)

    if (
        initial_cluster_state in UPDATE_PROGRESS_STATES
        or initial_cluster_state == "CREATE_COMPLETE"
    ):
        try:
            update_wait = wait_for_cluster_update(
                cluster_name,
                region,
                profile=profile,
                timeout=_remaining(deadline, monotonic_fn),
                update_start_timeout=min(300.0, _remaining(deadline, monotonic_fn)),
                poll_interval=poll_interval,
            )
        except Exception:  # noqa: BLE001 - provider exceptions are normalized at this boundary
            raise SlurmAccountingRecoveryError(
                "The accounting update wait failed with indeterminate provider state."
            ) from None
        if not update_wait.success or update_wait.final_status != "UPDATE_COMPLETE":
            raise SlurmAccountingRecoveryError(
                "The accounting update did not reach UPDATE_COMPLETE; recovery failed closed."
            )
    phases.append(
        _phase(
            PHASE_UPDATE_COMPLETE,
            "reclaimed" if update_reclaimed else "complete",
        )
    )
    persist_progress(PHASE_UPDATE_COMPLETE)

    _verify_exact_target_binding(
        cluster_name=cluster_name,
        region=region,
        region_az=region_az,
        profile=profile,
        source_config=source_config,
        source_sha256=source_sha256,
        update_config=update_config,
        update_sha256=update_configuration_sha256,
        stack_name=stack_name,
        database_name=database_name,
        db_username=db_username,
        instance_type=instance_type,
    )
    phases.append(_phase(PHASE_POST_UPDATE_EXACT_TARGET_VERIFIED, "complete"))
    persist_progress(PHASE_POST_UPDATE_EXACT_TARGET_VERIFIED)

    start_result = run_compute_fleet_transition(
        cluster_name=cluster_name,
        region=region,
        profile=profile,
        request_status="START_REQUESTED",
        wait_for_status="RUNNING",
        drain=False,
        timeout_seconds=_remaining(deadline, monotonic_fn),
        poll_interval_seconds=poll_interval,
        monotonic_fn=monotonic_fn,
        sleep_fn=sleep_fn,
    )
    phases.append(_phase(PHASE_FLEET_RUNNING, "complete"))
    persist_progress(PHASE_FLEET_RUNNING)

    _verify_accounting(
        cluster_name=cluster_name,
        region=region,
        profile=profile,
        timeout=_remaining(deadline, monotonic_fn),
    )
    phases.append(_phase(PHASE_ACCOUNTING_VERIFIED, "complete"))
    persist_progress(PHASE_ACCOUNTING_VERIFIED)
    final_cluster_state, _final_payload = _describe_cluster_state(
        cluster_name,
        region,
        profile=profile,
    )
    final_fleet_state = _describe_fleet_state(cluster_name, region, profile=profile)
    if final_cluster_state != "UPDATE_COMPLETE" or final_fleet_state != "RUNNING":
        raise SlurmAccountingRecoveryError(
            "Final cluster/fleet states changed before the recovery receipt was persisted."
        )

    completed = monotonic_fn()
    provisional = SlurmAccountingRecoveryResult(
        cluster=cluster_name,
        region=region,
        region_az=region_az,
        aws_profile=profile,
        aws_account_id=aws_account_id,
        accounting_stack_name=accounting_stack_name,
        database_name=database_name,
        db_username=db_username,
        instance_type=instance_type,
        create_slurm_accounting_if_missing=create_slurm_accounting_if_missing,
        acknowledge_slurm_accounting_create_cost=acknowledge_slurm_accounting_create_cost,
        service_created=service_created,
        cluster_configuration_path=str(source_config),
        cluster_configuration_sha256=source_sha256,
        update_configuration_path=update_configuration_path,
        update_configuration_sha256=update_configuration_sha256,
        initial_cluster_state=initial_cluster_state,
        initial_fleet_state=initial_fleet_state,
        final_cluster_state=final_cluster_state,
        final_fleet_state=final_fleet_state,
        update_submitted=update_submitted,
        update_reclaimed=update_reclaimed,
        fleet_stop_submitted=fleet_stop_submitted,
        fleet_start_submitted=start_result.request_submitted,
        accounting_verified=True,
        phase_receipts=tuple(phases),
        started_at=started_at,
        completed_at=_utc_now(),
        elapsed_seconds=max(0.0, completed - start),
        recovery_receipt_path=str(receipt_path),
        recovery_receipt_sha256="",
    )
    receipt_sha256 = _atomic_write_json(receipt_path, provisional._receipt_payload())
    return replace(provisional, recovery_receipt_sha256=receipt_sha256)
