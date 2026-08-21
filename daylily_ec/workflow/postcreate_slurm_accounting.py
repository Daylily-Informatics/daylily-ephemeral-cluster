"""Create-only post-create Slurm accounting orchestration.

This module deliberately owns the compute-fleet lifecycle instead of changing
the standalone ``slurm-accounting attach`` command. Service resolution and
update-config rendering complete before the first fleet mutation, and callers
must treat every non-enabled requested-accounting result as a create failure.
"""

from __future__ import annotations

import sys
import re
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Callable, Literal, Optional, cast

import typer

from daylily_ec.aws.ssm import run_shell, wait_for_ssm_online
from daylily_ec.headnode_readiness import validate_headnode_readiness
from daylily_ec.pcluster.monitor import wait_for_cluster_update, wait_for_compute_fleet
from daylily_ec.pcluster.runner import (
    describe_cluster,
    describe_compute_fleet,
    update_cluster,
    update_compute_fleet,
)
from daylily_ec.state.models import SlurmAccountingReceipt, SlurmAccountingStage

ACCOUNTING_OUTCOME_OFF = "OFF"
ACCOUNTING_OUTCOME_ENABLED = "ENABLED"
ACCOUNTING_OUTCOME_WARNING = "WARNING"
ACCOUNTING_OUTCOME_RECOVERY_REQUIRED = "RECOVERY REQUIRED"
SAFE_CLUSTER_STATES = frozenset(
    {
        "UNKNOWN",
        "CREATE_COMPLETE",
        "UPDATE_IN_PROGRESS",
        "UPDATE_COMPLETE",
        "UPDATE_FAILED",
        "UPDATE_ROLLBACK_IN_PROGRESS",
        "UPDATE_ROLLBACK_COMPLETE",
        "UPDATE_ROLLBACK_FAILED",
    }
)
SAFE_FLEET_STATES = frozenset(
    {"UNKNOWN", "RUNNING", "STOPPED", "START_REQUESTED", "STOP_REQUESTED"}
)
ACCOUNTING_VERIFICATION_COMMAND = "\n".join(
    (
        "set -euo pipefail",
        "test \"$(systemctl is-active slurmdbd)\" = active",
        "test \"$(systemctl is-active slurmctld)\" = active",
        "accounting_storage=$(scontrol show config | awk -F= '",
        "  /^AccountingStorageType[[:space:]]*=/ {gsub(/[[:space:]]/, \"\", $2); print $2}'",
        ")",
        "test \"$accounting_storage\" = accounting_storage/slurmdbd",
        "cluster_name=$(scontrol show config | awk -F= '",
        "  /^ClusterName[[:space:]]*=/ {gsub(/^[[:space:]]+|[[:space:]]+$/, \"\", $2); print $2}'",
        ")",
        "test -n \"$cluster_name\"",
        "registered_cluster=$(sacctmgr -nP show cluster \"$cluster_name\" format=Cluster | head -n 1)",
        "test \"$registered_cluster\" = \"$cluster_name\"",
        "timeout 60 sacct -X --starttime now-1hour --noheader --parsable2 >/dev/null",
    )
)


def _safe_status(value: object, allowed: frozenset[str], default: str = "UNKNOWN") -> str:
    """Return only an AWS-style symbolic status safe for receipt/output."""
    text = value if isinstance(value, str) else ""
    return text if text in allowed and re.fullmatch(r"[A-Z0-9_]{1,64}", text) else default


@dataclass(frozen=True)
class PostCreateSlurmAccountingResult:
    """Non-secret outcome used to write the accounting receipt and final panel."""

    requested_mode: Literal["on", "off"]
    outcome: str
    create_approval_flag: bool
    cost_acknowledgement_flag: bool
    service_created: bool = False
    stack_name: str = ""
    stage_reached: str = "not_started"
    update_config_path: str = ""
    terminal_cluster_state: str = "CREATE_COMPLETE"
    terminal_fleet_state: str = ""
    fleet_restored: Optional[bool] = None
    error_stage: str = ""
    recovery_required: bool = False
    provider_accounting_stack_name: str = ""
    privatelink_stack_name: str = ""
    consumer_vpc_id: str = ""
    database_name: str = ""
    db_username: str = ""
    provider_instance_type: str = ""

    @property
    def succeeded(self) -> bool:
        return self.outcome in {ACCOUNTING_OUTCOME_OFF, ACCOUNTING_OUTCOME_ENABLED}

    def to_receipt(self) -> SlurmAccountingReceipt:
        """Convert this bounded result to the strict persisted receipt model."""
        return SlurmAccountingReceipt(
            requested_mode=self.requested_mode,
            create_approval_flag=self.create_approval_flag,
            cost_acknowledgement_flag=self.cost_acknowledgement_flag,
            service_created=self.service_created,
            stage_reached=SlurmAccountingStage(self.stage_reached),
            update_config_path=self.update_config_path,
            terminal_cluster_state=self.terminal_cluster_state,
            terminal_fleet_state=self.terminal_fleet_state,
            fleet_restored=self.fleet_restored,
            error_stage=(SlurmAccountingStage(self.error_stage) if self.error_stage else None),
            recovery_required=self.recovery_required,
            stack_name=self.stack_name,
            provider_accounting_stack_name=self.provider_accounting_stack_name,
            privatelink_stack_name=self.privatelink_stack_name,
            consumer_vpc_id=self.consumer_vpc_id,
            database_name=self.database_name,
            db_username=self.db_username,
            provider_instance_type=self.provider_instance_type,
        )


def validate_postcreate_slurm_accounting_options(
    *,
    slurm_accounting: str,
    create_slurm_accounting_if_missing: bool,
    acknowledge_slurm_accounting_create_cost: bool,
) -> None:
    """Validate the direct workflow-call contract before any AWS work."""
    if slurm_accounting not in {"on", "off"}:
        raise ValueError("--slurm-accounting must be exactly lowercase 'on' or 'off'.")
    if create_slurm_accounting_if_missing != acknowledge_slurm_accounting_create_cost:
        raise ValueError(
            "--create-slurm-accounting-if-missing and "
            "--acknowledge-slurm-accounting-create-cost must be supplied together."
        )


def _warning(
    result: PostCreateSlurmAccountingResult,
    stage: str,
    *,
    terminal_cluster_state: Optional[str] = None,
    terminal_fleet_state: Optional[str] = None,
    fleet_restored: Optional[bool] = None,
    recovery_required: bool = False,
) -> PostCreateSlurmAccountingResult:
    """Return a stable warning without copying an exception into output/state."""
    return replace(
        result,
        outcome=(
            ACCOUNTING_OUTCOME_RECOVERY_REQUIRED
            if recovery_required
            else ACCOUNTING_OUTCOME_WARNING
        ),
        stage_reached=stage,
        error_stage=stage,
        terminal_cluster_state=(
            terminal_cluster_state
            if terminal_cluster_state is not None
            else result.terminal_cluster_state
        ),
        terminal_fleet_state=(
            terminal_fleet_state
            if terminal_fleet_state is not None
            else result.terminal_fleet_state
        ),
        fleet_restored=(fleet_restored if fleet_restored is not None else result.fleet_restored),
        recovery_required=recovery_required,
    )


def _request_restore(
    result: PostCreateSlurmAccountingResult,
    *,
    cluster_name: str,
    region: str,
    profile: Optional[str],
    pcluster_executable: str,
) -> PostCreateSlurmAccountingResult:
    """Restore an initially running fleet after a known-safe failure state."""
    try:
        request = update_compute_fleet(
            cluster_name,
            "START_REQUESTED",
            region,
            profile=profile,
            executable=pcluster_executable,
        )
    except Exception:
        return _warning(
            result,
            "fleet_restore_request",
            fleet_restored=False,
            recovery_required=True,
        )
    if not request.success:
        return _warning(
            result,
            "fleet_restore_request",
            fleet_restored=False,
            recovery_required=True,
        )
    try:
        waited = wait_for_compute_fleet(
            cluster_name,
            region,
            "RUNNING",
            profile=profile,
            executable=pcluster_executable,
        )
    except Exception:
        return _warning(
            result,
            "fleet_restore_request",
            fleet_restored=False,
            recovery_required=True,
        )
    if not waited.success:
        return _warning(
            result,
            "fleet_restore_request",
            terminal_fleet_state=waited.final_status or "UNKNOWN",
            fleet_restored=False,
            recovery_required=True,
        )
    return replace(
        result,
        stage_reached="fleet_restored",
        terminal_fleet_state="RUNNING",
        fleet_restored=True,
    )


def _recover_after_safe_failure(
    result: PostCreateSlurmAccountingResult,
    error_stage: str,
    *,
    initially_running: bool,
    cluster_name: str,
    region: str,
    profile: Optional[str],
    pcluster_executable: str,
) -> PostCreateSlurmAccountingResult:
    if not initially_running:
        return _warning(
            result,
            error_stage,
            terminal_fleet_state="STOPPED",
            fleet_restored=None,
        )
    restored = _request_restore(
        result,
        cluster_name=cluster_name,
        region=region,
        profile=profile,
        pcluster_executable=pcluster_executable,
    )
    if restored.recovery_required:
        return restored
    return replace(
        restored,
        outcome=ACCOUNTING_OUTCOME_WARNING,
        error_stage=error_stage,
        recovery_required=False,
    )


def _interactive_terminal(non_interactive: bool) -> bool:
    return (
        not non_interactive
        and bool(getattr(sys.stdin, "isatty", lambda: False)())
        and bool(getattr(sys.stdout, "isatty", lambda: False)())
    )


def _confirm_first_singleton_creation(
    confirm_fn: Callable[..., bool],
) -> tuple[bool, bool]:
    first = confirm_fn(
        "No regional Slurm accounting service exists. Create the first regional singleton?",
        default=False,
    )
    if not first:
        return False, False
    second = bool(
        confirm_fn(
            "Creating the regional Slurm accounting service incurs ongoing AWS cost. Continue?",
            default=False,
        )
    )
    return True, second


def run_postcreate_slurm_accounting(
    *,
    cluster_name: str,
    region: str,
    region_az: str,
    profile: Optional[str],
    cluster_configuration: Path,
    initial_headnode_instance_id: str,
    slurm_accounting: str,
    non_interactive: bool,
    create_slurm_accounting_if_missing: bool,
    acknowledge_slurm_accounting_create_cost: bool,
    accounting_stack_name: str,
    accounting_privatelink_stack_name: str,
    accounting_direct: bool,
    accounting_consumer_vpc_id: str,
    accounting_database_name: str,
    accounting_db_username: str,
    accounting_instance_type: str,
    pcluster_executable: str = "pcluster",
    configure_replacement_headnode: Optional[Callable[[str], bool]] = None,
    confirm_fn: Callable[..., bool] = typer.confirm,
) -> PostCreateSlurmAccountingResult:
    """Attach accounting after a successful base create and persisted state.

    All returned values are safe for terminal, JSON, and receipt output.  Raw
    exceptions and resolved database connection values never leave this
    function.
    """
    validate_postcreate_slurm_accounting_options(
        slurm_accounting=slurm_accounting,
        create_slurm_accounting_if_missing=create_slurm_accounting_if_missing,
        acknowledge_slurm_accounting_create_cost=acknowledge_slurm_accounting_create_cost,
    )
    exact_stack_name = str(accounting_stack_name or "").strip()
    exact_bridge_name = str(accounting_privatelink_stack_name or "").strip()
    exact_consumer_vpc_id = str(accounting_consumer_vpc_id or "").strip()
    exact_database_name = str(accounting_database_name or "").strip()
    exact_db_username = str(accounting_db_username or "").strip()
    exact_instance_type = str(accounting_instance_type or "").strip()
    if not all(
        (
            exact_stack_name,
            exact_consumer_vpc_id,
            exact_database_name,
            exact_db_username,
            exact_instance_type,
        )
    ):
        raise ValueError("Exact Slurm-accounting target fields are required")
    if bool(exact_bridge_name) == bool(accounting_direct):
        raise ValueError(
            "Specify exactly one exact PrivateLink bridge or --slurm-accounting-direct"
        )
    if exact_bridge_name and create_slurm_accounting_if_missing:
        raise ValueError("An exact PrivateLink target forbids provider creation")
    result = PostCreateSlurmAccountingResult(
        requested_mode=cast(Literal["on", "off"], slurm_accounting),
        outcome=(
            ACCOUNTING_OUTCOME_OFF if slurm_accounting == "off" else ACCOUNTING_OUTCOME_WARNING
        ),
        create_approval_flag=create_slurm_accounting_if_missing,
        cost_acknowledgement_flag=acknowledge_slurm_accounting_create_cost,
        stage_reached=("off" if slurm_accounting == "off" else "not_started"),
    )
    if slurm_accounting == "off":
        return result

    from daylily_ec.workflow.attach_slurm_accounting import (
        SlurmAccountingPreparationError,
        prepare_slurm_accounting_update,
    )

    create_if_missing = create_slurm_accounting_if_missing
    try:
        prepared = prepare_slurm_accounting_update(
            cluster_name=cluster_name,
            region=region,
            profile=profile,
            cluster_configuration=cluster_configuration,
            create_if_missing=create_if_missing,
            stack_name=exact_stack_name,
            privatelink_stack_name=exact_bridge_name,
            database_name=exact_database_name,
            db_username=exact_db_username,
            instance_type=exact_instance_type,
            expected_region_az=region_az,
            exact_target_only=True,
        )
    except SlurmAccountingPreparationError as exc:
        missing_service_at_interactive_terminal = (
            not create_if_missing
            and exc.reason_code == "service_missing"
            and exc.regional_stack_count == 0
            and _interactive_terminal(non_interactive)
        )
        if not missing_service_at_interactive_terminal:
            return _warning(result, "service_preparation")
        create_approved, cost_acknowledged = _confirm_first_singleton_creation(confirm_fn)
        result = replace(
            result,
            create_approval_flag=create_approved,
            cost_acknowledgement_flag=cost_acknowledged,
        )
        if not (create_approved and cost_acknowledged):
            return _warning(result, "service_preparation")
        try:
            prepared = prepare_slurm_accounting_update(
                cluster_name=cluster_name,
                region=region,
                profile=profile,
                cluster_configuration=cluster_configuration,
                create_if_missing=True,
                stack_name=exact_stack_name,
                privatelink_stack_name=exact_bridge_name,
                database_name=exact_database_name,
                db_username=exact_db_username,
                instance_type=exact_instance_type,
                expected_region_az=region_az,
                exact_target_only=True,
            )
        except SlurmAccountingPreparationError:
            return _warning(result, "service_preparation")
        except Exception:
            return _warning(result, "service_preparation")
    except Exception:
        return _warning(result, "service_preparation")

    if prepared.consumer_vpc_id != exact_consumer_vpc_id:
        return _warning(result, "service_preparation")
    result = replace(
        result,
        service_created=prepared.service_created,
        stack_name=exact_stack_name,
        stage_reached="service_ready",
        update_config_path=str(prepared.update_config_path),
        provider_accounting_stack_name=prepared.provider_accounting_stack_name,
        privatelink_stack_name=prepared.privatelink_stack_name or "",
        consumer_vpc_id=prepared.consumer_vpc_id,
        database_name=prepared.database_name,
        db_username=prepared.db_username,
        provider_instance_type=prepared.provider_instance_type,
    )

    try:
        fleet = describe_compute_fleet(
            cluster_name,
            region,
            profile=profile,
            executable=pcluster_executable,
        )
    except Exception:
        return _warning(result, "fleet_describe")
    if not fleet.success:
        return _warning(result, "fleet_describe")
    fleet_status = fleet.json_body.get("status")
    if fleet_status not in {"RUNNING", "STOPPED"}:
        return _warning(
            result,
            "fleet_describe",
            terminal_fleet_state=_safe_status(fleet_status, SAFE_FLEET_STATES),
            recovery_required=True,
        )

    initially_running = fleet_status == "RUNNING"
    result = replace(
        result,
        terminal_fleet_state=fleet_status,
        fleet_restored=(False if initially_running else None),
    )
    if initially_running:
        try:
            stop = update_compute_fleet(
                cluster_name,
                "STOP_REQUESTED",
                region,
                profile=profile,
                executable=pcluster_executable,
            )
        except Exception:
            stop = None
        if stop is None or not stop.success:
            try:
                observed = describe_compute_fleet(
                    cluster_name,
                    region,
                    profile=profile,
                    executable=pcluster_executable,
                )
            except Exception:
                return _warning(
                    result,
                    "fleet_stop_request",
                    terminal_fleet_state="UNKNOWN",
                    recovery_required=True,
                )
            observed_status = (
                _safe_status(observed.json_body.get("status"), SAFE_FLEET_STATES)
                if observed.success
                else "UNKNOWN"
            )
            if observed_status == "RUNNING":
                return _warning(
                    result,
                    "fleet_stop_request",
                    terminal_fleet_state="RUNNING",
                    fleet_restored=True,
                )
            if observed_status == "STOPPED":
                return _recover_after_safe_failure(
                    result,
                    "fleet_stop_request",
                    initially_running=True,
                    cluster_name=cluster_name,
                    region=region,
                    profile=profile,
                    pcluster_executable=pcluster_executable,
                )
            return _warning(
                result,
                "fleet_stop_request",
                terminal_fleet_state=observed_status,
                recovery_required=True,
            )
        try:
            stopped = wait_for_compute_fleet(
                cluster_name,
                region,
                "STOPPED",
                profile=profile,
                executable=pcluster_executable,
            )
        except Exception:
            return _warning(
                result,
                "fleet_stop_request",
                terminal_fleet_state="UNKNOWN",
                recovery_required=True,
            )
        if not stopped.success:
            stopped_status = _safe_status(stopped.final_status, SAFE_FLEET_STATES)
            if stopped_status == "RUNNING":
                return _warning(
                    result,
                    "fleet_stop_request",
                    terminal_fleet_state="RUNNING",
                    fleet_restored=True,
                )
            return _warning(
                result,
                "fleet_stop_request",
                terminal_fleet_state=stopped_status,
                recovery_required=True,
            )
        result = replace(
            result,
            stage_reached="fleet_stopped",
            terminal_fleet_state="STOPPED",
        )

    try:
        dry_run = update_cluster(
            cluster_name,
            result.update_config_path,
            region,
            profile=profile,
            dry_run=True,
            executable=pcluster_executable,
        )
    except Exception:
        dry_run = None
    if dry_run is None or not dry_run.success:
        return _recover_after_safe_failure(
            result,
            "update_dry_run",
            initially_running=initially_running,
            cluster_name=cluster_name,
            region=region,
            profile=profile,
            pcluster_executable=pcluster_executable,
        )

    result = replace(result, stage_reached="update_dry_run")
    try:
        submitted = update_cluster(
            cluster_name,
            result.update_config_path,
            region,
            profile=profile,
            dry_run=False,
            executable=pcluster_executable,
        )
    except Exception:
        submitted = None
    if submitted is None or not submitted.success:
        # A non-zero CLI result is normally a rejected submission, but do not
        # assume the remote state is unchanged.  Restore only after both
        # cluster and fleet re-describe to the exact stable pre-update states.
        try:
            stable_cluster = describe_cluster(
                cluster_name,
                region,
                profile=profile,
                executable=pcluster_executable,
            )
            stable_fleet = describe_compute_fleet(
                cluster_name,
                region,
                profile=profile,
                executable=pcluster_executable,
            )
        except Exception:
            return _warning(
                result,
                "update_submit",
                terminal_cluster_state="UNKNOWN",
                terminal_fleet_state="UNKNOWN",
                recovery_required=True,
            )
        if (
            stable_cluster.success
            and stable_cluster.json_body.get("clusterStatus") == "CREATE_COMPLETE"
            and stable_fleet.success
            and stable_fleet.json_body.get("status") == "STOPPED"
        ):
            return _recover_after_safe_failure(
                result,
                "update_submit",
                initially_running=initially_running,
                cluster_name=cluster_name,
                region=region,
                profile=profile,
                pcluster_executable=pcluster_executable,
            )
        return _warning(
            result,
            "update_submit",
            terminal_cluster_state=(
                _safe_status(stable_cluster.json_body.get("clusterStatus"), SAFE_CLUSTER_STATES)
                if stable_cluster.success
                else "UNKNOWN"
            ),
            terminal_fleet_state=(
                _safe_status(stable_fleet.json_body.get("status"), SAFE_FLEET_STATES)
                if stable_fleet.success
                else "UNKNOWN"
            ),
            recovery_required=True,
        )

    result = replace(result, stage_reached="update_submit")
    try:
        update_wait = wait_for_cluster_update(
            cluster_name,
            region,
            profile=profile,
            executable=pcluster_executable,
        )
    except Exception:
        return _warning(
            result,
            "update_wait",
            terminal_cluster_state="UNKNOWN",
            recovery_required=True,
        )
    result = replace(
        result,
        terminal_cluster_state=_safe_status(update_wait.final_status, SAFE_CLUSTER_STATES),
        stage_reached="update_wait",
    )
    if not update_wait.success:
        if update_wait.safe_to_restore_fleet:
            return _recover_after_safe_failure(
                result,
                "update_wait",
                initially_running=initially_running,
                cluster_name=cluster_name,
                region=region,
                profile=profile,
                pcluster_executable=pcluster_executable,
            )
        return _warning(
            result,
            "update_wait",
            terminal_cluster_state=_safe_status(update_wait.final_status, SAFE_CLUSTER_STATES),
            recovery_required=True,
        )

    result = replace(result, stage_reached="update_complete")
    try:
        described = describe_cluster(
            cluster_name,
            region,
            profile=profile,
            executable=pcluster_executable,
        )
    except Exception:
        described = None
    if described is None or not described.success:
        return _recover_after_safe_failure(
            result,
            "headnode_readiness",
            initially_running=initially_running,
            cluster_name=cluster_name,
            region=region,
            profile=profile,
            pcluster_executable=pcluster_executable,
        )
    headnode = described.json_body.get("headNode") or {}
    replacement_id = headnode.get("instanceId") if isinstance(headnode, dict) else None
    if not isinstance(replacement_id, str) or not replacement_id:
        return _recover_after_safe_failure(
            result,
            "headnode_readiness",
            initially_running=initially_running,
            cluster_name=cluster_name,
            region=region,
            profile=profile,
            pcluster_executable=pcluster_executable,
        )

    try:
        if replacement_id != initial_headnode_instance_id:
            wait_for_ssm_online(replacement_id, region, profile=profile)
            if configure_replacement_headnode is None or not configure_replacement_headnode(
                replacement_id
            ):
                raise RuntimeError("replacement headnode configuration failed")
        else:
            validate_headnode_readiness(
                replacement_id,
                region,
                profile=profile,
                timeout=120,
                comment="Validate post-accounting headnode readiness",
                repo_name="daylily-ephemeral-cluster",
                remote_user="ubuntu",
            )
    except Exception:
        return _recover_after_safe_failure(
            result,
            "headnode_readiness",
            initially_running=initially_running,
            cluster_name=cluster_name,
            region=region,
            profile=profile,
            pcluster_executable=pcluster_executable,
        )

    result = replace(result, stage_reached="headnode_readiness")
    if initially_running:
        restored = _request_restore(
            result,
            cluster_name=cluster_name,
            region=region,
            profile=profile,
            pcluster_executable=pcluster_executable,
        )
        if restored.recovery_required:
            return restored
        result = restored

    try:
        run_shell(
            replacement_id,
            region,
            ACCOUNTING_VERIFICATION_COMMAND,
            profile=profile,
            as_user="ubuntu",
            timeout=120,
            comment="Validate Slurm accounting read-only",
        )
    except Exception:
        return _warning(
            result,
            "verification",
            terminal_fleet_state=("RUNNING" if initially_running else "STOPPED"),
            fleet_restored=(True if initially_running else None),
        )

    return replace(
        result,
        outcome=ACCOUNTING_OUTCOME_ENABLED,
        stage_reached="complete",
        error_stage="",
        recovery_required=False,
        terminal_cluster_state="UPDATE_COMPLETE",
        terminal_fleet_state=("RUNNING" if initially_running else "STOPPED"),
        fleet_restored=(True if initially_running else None),
    )
