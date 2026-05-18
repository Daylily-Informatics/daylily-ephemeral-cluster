"""Cluster deletion workflow for the ``daylily-ec delete`` command."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import boto3
import typer

from daylily_ec import ui
from daylily_ec.aws.context import resolve_profile
from daylily_ec.aws.heartbeat import delete_heartbeat_resources
from daylily_ec.pcluster.monitor import get_cluster_status, wait_for_deletion
from daylily_ec.pcluster.runner import delete_cluster as start_delete_cluster
from daylily_ec.state.models import StateRecord
from daylily_ec.state.store import load_state_record

POLL_INTERVAL_SECONDS = 15.0
CONFIRMATION_TEXT = "please delete"


@dataclass
class DeleteOptions:
    cluster_name: Optional[str]
    region: Optional[str]
    profile: Optional[str]
    state_file: Optional[Path] = None
    yes: bool = False
    poll_interval: float = POLL_INTERVAL_SECONDS


@dataclass
class ResolvedDeleteOptions:
    cluster_name: str
    region: str
    profile: str
    state_file: Optional[Path]
    yes: bool
    poll_interval: float


def _load_state(state_file: Optional[Path]) -> Optional[StateRecord]:
    if state_file is None:
        return None
    path = state_file.expanduser().resolve()
    if not path.is_file():
        raise RuntimeError(f"State file not found: {path}")
    return load_state_record(path)


def _resolve_delete_options(
    options: DeleteOptions,
    *,
    prompt_fn=typer.prompt,
) -> tuple[ResolvedDeleteOptions, Optional[StateRecord]]:
    state = _load_state(options.state_file)

    cluster_name = (options.cluster_name or (state.cluster_name if state else "") or "").strip()
    if not cluster_name:
        cluster_name = str(prompt_fn("Enter the AWS ParallelCluster cluster name")).strip()

    region = (options.region or (state.region if state else "") or "").strip()
    if not region:
        region = str(prompt_fn("Enter the AWS region where the cluster is located")).strip()

    profile_hint = options.profile or (state.aws_profile if state else None)
    profile = resolve_profile(profile_hint)

    return (
        ResolvedDeleteOptions(
            cluster_name=cluster_name,
            region=region,
            profile=profile,
            state_file=options.state_file,
            yes=options.yes,
            poll_interval=options.poll_interval,
        ),
        state,
    )


def find_fsx_associations(fsx_client, cluster_name: str) -> list[str]:
    """Return FSx file system IDs tagged to *cluster_name*."""
    associations: list[str] = []
    paginator = fsx_client.get_paginator("describe_file_systems")
    for page in paginator.paginate():
        for filesystem in page.get("FileSystems", []):
            tags = {
                tag.get("Key"): tag.get("Value")
                for tag in filesystem.get("Tags", [])
                if tag.get("Key")
            }
            if tags.get("parallelcluster:cluster-name") == cluster_name:
                fsx_id = filesystem.get("FileSystemId")
                if fsx_id:
                    associations.append(str(fsx_id))
    return associations


def find_active_fsx_repository_activity(fsx_client, fsx_ids: list[str]) -> dict[str, Any]:
    """Return active DRAs and export tasks for the FSx filesystems being deleted."""
    active_lifecycles = {"AVAILABLE", "CREATING", "UPDATING", "MISCONFIGURED"}
    active_task_lifecycles = {"PENDING", "EXECUTING"}
    activity: dict[str, Any] = {"associations": [], "export_tasks": []}
    for fsx_id in fsx_ids:
        assoc_response = fsx_client.describe_data_repository_associations(
            Filters=[{"Name": "file-system-id", "Values": [fsx_id]}]
        )
        for association in assoc_response.get("Associations", []) or []:
            lifecycle = str(association.get("Lifecycle") or "")
            if lifecycle.upper() not in active_lifecycles:
                continue
            s3_config = association.get("S3") or {}
            auto_export = (s3_config.get("AutoExportPolicy") or {}).get("Events") or []
            activity["associations"].append(
                {
                    "association_id": association.get("AssociationId"),
                    "file_system_id": fsx_id,
                    "file_system_path": association.get("FileSystemPath"),
                    "data_repository_path": association.get("DataRepositoryPath"),
                    "lifecycle": lifecycle,
                    "auto_export_events": list(auto_export),
                }
            )
        task_response = fsx_client.describe_data_repository_tasks(
            Filters=[{"Name": "file-system-id", "Values": [fsx_id]}]
        )
        for task in task_response.get("DataRepositoryTasks", []) or []:
            lifecycle = str(task.get("Lifecycle") or "")
            if lifecycle.upper() not in active_task_lifecycles:
                continue
            if str(task.get("Type") or "") != "EXPORT_TO_REPOSITORY":
                continue
            activity["export_tasks"].append(
                {
                    "task_id": task.get("TaskId"),
                    "file_system_id": fsx_id,
                    "lifecycle": lifecycle,
                    "paths": list(task.get("Paths") or []),
                }
            )
    return activity


def confirm_delete(fsx_ids: list[str], *, yes: bool, prompt_fn=typer.prompt) -> bool:
    """Return ``True`` when deletion should proceed."""
    if not fsx_ids:
        ui.info("No FSx filesystems associated with the cluster.")
        return True

    ui.warn("FSx filesystems are still associated with the cluster:")
    for fsx_id in fsx_ids:
        ui.detail("FSx", fsx_id)
    ui.info("Export results with `daylily-ec export` before deleting if needed.")

    if yes:
        ui.info("Skipping confirmation (--yes provided).")
        return True

    confirmation = str(prompt_fn("Type 'please delete' to proceed with cluster deletion")).strip()
    return confirmation == CONFIRMATION_TEXT


def _teardown_heartbeat_best_effort(
    session,
    options: ResolvedDeleteOptions,
    state: Optional[StateRecord],
) -> None:
    try:
        account_id = state.account_id if state and state.account_id else ""
        if not account_id and not (state and state.heartbeat_topic_arn):
            account_id = session.client("sts").get_caller_identity()["Account"]

        result = delete_heartbeat_resources(
            session.client("sns"),
            session.client("scheduler"),
            session.client("lambda"),
            cluster_name=options.cluster_name,
            region=options.region,
            account_id=account_id,
            topic_arn=state.heartbeat_topic_arn if state else "",
            schedule_name=state.heartbeat_schedule_name if state else "",
        )
        if result.deleted_schedule or result.deleted_function or result.deleted_topic:
            ui.info("Heartbeat resources removed where present.")
        else:
            ui.info("Heartbeat resources were already absent or skipped.")
    except Exception as exc:  # noqa: BLE001
        ui.warn(f"Heartbeat teardown skipped: {exc}")


def run_delete_workflow(options: DeleteOptions) -> int:
    """Delete a ParallelCluster cluster and monitor teardown to completion."""
    try:
        resolved, state = _resolve_delete_options(options)
    except RuntimeError as exc:
        ui.error_panel("Delete failed", str(exc))
        return 1

    ui.phase("DELETE")
    ui.step(f"Preparing cluster deletion for '{resolved.cluster_name}' in {resolved.region}")

    session = boto3.Session(
        profile_name=resolved.profile,
        region_name=resolved.region,
    )
    existing_status = get_cluster_status(
        resolved.cluster_name,
        resolved.region,
        profile=resolved.profile,
    )
    if existing_status is None:
        ui.error_panel(
            "Delete failed",
            f"Cluster '{resolved.cluster_name}' does not exist in region '{resolved.region}'.",
        )
        return 1

    fsx_ids = find_fsx_associations(session.client("fsx"), resolved.cluster_name)
    repository_activity = find_active_fsx_repository_activity(
        session.client("fsx"),
        fsx_ids,
    )
    if repository_activity["associations"] or repository_activity["export_tasks"]:
        ui.warn("Active FSx data repository activity exists on the cluster filesystem:")
        for association in repository_activity["associations"]:
            ui.detail(
                "DRA",
                "%s %s -> %s (%s)"
                % (
                    association["association_id"],
                    association["file_system_path"],
                    association["data_repository_path"],
                    association["lifecycle"],
                ),
            )
        for task in repository_activity["export_tasks"]:
            ui.detail("Export task", f"{task['task_id']} {task['paths']} ({task['lifecycle']})")
    if not confirm_delete(fsx_ids, yes=resolved.yes):
        ui.warn("Aborting cluster deletion.")
        return 1

    _teardown_heartbeat_best_effort(session, resolved, state)

    delete_result = start_delete_cluster(
        resolved.cluster_name,
        resolved.region,
        profile=resolved.profile,
    )
    if not delete_result.success:
        ui.error_panel(
            "Delete failed to start",
            delete_result.stderr or delete_result.stdout or "pcluster delete-cluster failed.",
        )
        return 1

    monitor_result = wait_for_deletion(
        resolved.cluster_name,
        resolved.region,
        profile=resolved.profile,
        poll_interval=resolved.poll_interval,
    )
    if monitor_result.success:
        ui.success_panel(
            "Cluster deleted",
            f"Cluster: {resolved.cluster_name}\nRegion: {resolved.region}",
        )
        return 0

    ui.error_panel(
        "Delete failed",
        monitor_result.error
        or f"Cluster ended in unexpected status: {monitor_result.final_status}",
    )
    return 1


def run_delete_dry_run(options: DeleteOptions) -> int:
    """Inspect the resources that would be affected by a cluster deletion."""
    try:
        resolved, state = _resolve_delete_options(options)
    except RuntimeError as exc:
        ui.error_panel("Delete dry run failed", str(exc))
        return 1

    ui.phase("DELETE DRY RUN")
    ui.step(f"Inspecting cluster deletion target '{resolved.cluster_name}' in {resolved.region}")

    existing_status = get_cluster_status(
        resolved.cluster_name,
        resolved.region,
        profile=resolved.profile,
    )
    if existing_status is None:
        ui.error_panel(
            "Delete dry run failed",
            f"Cluster '{resolved.cluster_name}' does not exist in region '{resolved.region}'.",
        )
        return 1

    session = boto3.Session(
        profile_name=resolved.profile,
        region_name=resolved.region,
    )
    fsx_client = session.client("fsx")
    fsx_ids = find_fsx_associations(fsx_client, resolved.cluster_name)
    repository_activity = find_active_fsx_repository_activity(fsx_client, fsx_ids)

    ui.info("No AWS resources were changed.")
    ui.detail("Cluster", resolved.cluster_name)
    ui.detail("Region", resolved.region)
    ui.detail("Profile", resolved.profile)
    ui.detail("Current status", existing_status)
    if state and resolved.state_file:
        ui.detail("State file", str(resolved.state_file))
    if fsx_ids:
        ui.warn("FSx filesystems are still associated with the cluster:")
        for fsx_id in fsx_ids:
            ui.detail("FSx", fsx_id)
        ui.info("Export results with `daylily-ec export` before deleting if needed.")
        if repository_activity["associations"]:
            ui.warn("Active FSx data repository associations are still attached:")
            for association in repository_activity["associations"]:
                auto_export = association["auto_export_events"]
                suffix = f" AutoExport={auto_export}" if auto_export else ""
                ui.detail(
                    "DRA",
                    "%s %s -> %s (%s)%s"
                    % (
                        association["association_id"],
                        association["file_system_path"],
                        association["data_repository_path"],
                        association["lifecycle"],
                        suffix,
                    ),
                )
        if repository_activity["export_tasks"]:
            ui.warn("Active FSx export tasks are still running:")
            for task in repository_activity["export_tasks"]:
                ui.detail("Export task", f"{task['task_id']} {task['paths']} ({task['lifecycle']})")
    else:
        ui.info("No FSx filesystems associated with the cluster.")
    return 0
