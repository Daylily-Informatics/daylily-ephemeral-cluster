"""FSx export workflow for the ``daylily-ec export`` command."""

from __future__ import annotations

import dataclasses
import logging
import time
from pathlib import Path
from typing import Dict, Optional

import boto3
from botocore.exceptions import BotoCoreError, ClientError
import yaml

from daylily_ec import ui

LOGGER = logging.getLogger("daylily.export_fsx")

POLL_INTERVAL_SECONDS = 30
STATUS_FILENAME = "fsx_export.yaml"


@dataclasses.dataclass
class ExportOptions:
    cluster_name: str
    target_uri: str
    region: str
    profile: Optional[str]
    output_dir: Path


def configure_logging(verbose: bool) -> None:
    """Configure workflow logging for export operations."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(message)s")


def _create_session(options: ExportOptions):
    session_kwargs: Dict[str, str] = {"region_name": options.region}
    if options.profile:
        session_kwargs["profile_name"] = options.profile
    return boto3.Session(**session_kwargs)


def _find_filesystem(client, cluster_name: str) -> Dict[str, object]:
    paginator = client.get_paginator("describe_file_systems")
    for page in paginator.paginate():
        for filesystem in page.get("FileSystems", []):
            tags = {
                tag.get("Key"): tag.get("Value")
                for tag in filesystem.get("Tags", [])
                if tag.get("Key")
            }
            if tags.get("parallelcluster:cluster-name") == cluster_name:
                return filesystem
    raise RuntimeError(f"No FSx filesystem found for cluster {cluster_name}")


def _normalise_target(filesystem: Dict[str, object], target_uri: str) -> tuple[str, Optional[str]]:
    target = target_uri.strip()
    if not target:
        raise RuntimeError("Target URI must be provided")

    lustre_config = filesystem.get("LustreConfiguration", {}) or {}
    repo_config = lustre_config.get("DataRepositoryConfiguration", {}) or {}
    export_path = repo_config.get("ExportPath")

    if target.startswith("s3://"):
        if not export_path:
            raise RuntimeError(
                "Filesystem does not expose an export path to derive FSx destination"
            )
        normalised_export = export_path.rstrip("/") + "/"
        if not target.startswith(normalised_export):
            raise RuntimeError(
                f"Target URI must reside under the FSx export path; expected prefix {export_path}"
            )
        relative_path = target[len(normalised_export) :].lstrip("/")
        if not relative_path:
            raise RuntimeError("Target URI must resolve to a sub-path of the export root")
        return relative_path, target.rstrip("/")

    relative_path = target.lstrip("/")
    if not relative_path:
        raise RuntimeError("Target path must not be the FSx root")
    s3_uri = None
    if export_path:
        s3_uri = f"{export_path.rstrip('/')}/{relative_path}"
    return relative_path, s3_uri


def _start_export(client, filesystem: Dict[str, object], relative_path: str) -> str:
    filesystem_id = filesystem.get("FileSystemId")
    if not filesystem_id:
        raise RuntimeError("FSx filesystem is missing an identifier")
    lustre_config = filesystem.get("LustreConfiguration", {}) or {}
    repo_config = lustre_config.get("DataRepositoryConfiguration", {}) or {}
    export_path = repo_config.get("ExportPath")
    report_path = None
    if export_path:
        report_path = f"{export_path.rstrip('/')}/daylily-monitor/{int(time.time())}/export-report"
    kwargs: Dict[str, object] = {
        "FileSystemId": filesystem_id,
        "Type": "EXPORT_TO_REPOSITORY",
        "Paths": [relative_path],
    }
    if report_path:
        kwargs["Report"] = {
            "Enabled": True,
            "Path": report_path,
            "Format": "REPORT_CSV_20191124",
            "Scope": "FAILED_FILES_ONLY",
        }
    response = client.create_data_repository_task(**kwargs)
    task = response.get("DataRepositoryTask") or {}
    task_id = task.get("TaskId")
    if not task_id:
        raise RuntimeError("FSx create_data_repository_task did not return a task id")
    return task_id


def _await_export(client, task_id: str) -> Dict[str, object]:
    while True:
        response = client.describe_data_repository_tasks(TaskIds=[task_id])
        tasks = response.get("DataRepositoryTasks", [])
        if not tasks:
            raise RuntimeError("Unable to locate export task status")
        task = tasks[0]
        lifecycle = task.get("Lifecycle", "")
        LOGGER.info("Task %s status: %s", task_id, lifecycle)
        if lifecycle in {"SUCCEEDED", "FAILED", "CANCELED"}:
            return task
        time.sleep(POLL_INTERVAL_SECONDS)


def _write_status(
    options: ExportOptions, status: str, s3_uri: Optional[str], message: Optional[str]
) -> None:
    payload: Dict[str, object] = {"fsx_export": {"status": status, "s3_uri": s3_uri}}
    if message:
        payload["fsx_export"]["message"] = message
    options.output_dir.mkdir(parents=True, exist_ok=True)
    status_path = options.output_dir / STATUS_FILENAME
    status_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    LOGGER.info("Wrote export status to %s", status_path)


def run_export_workflow(options: ExportOptions) -> int:
    """Run the FSx export workflow and write ``fsx_export.yaml``."""
    ui.phase("EXPORT")
    ui.step(f"Preparing FSx export for cluster '{options.cluster_name}'")

    session = _create_session(options)
    client = session.client("fsx")
    try:
        filesystem = _find_filesystem(client, options.cluster_name)
        relative_path, s3_uri = _normalise_target(filesystem, options.target_uri)
        ui.info(f"Export path: {relative_path}")
        task_id = _start_export(client, filesystem, relative_path)
        ui.info(f"Started data repository task {task_id}")
        task = _await_export(client, task_id)
    except (ClientError, BotoCoreError, RuntimeError) as exc:
        LOGGER.error("FSx export failed: %s", exc)
        _write_status(options, "error", None, str(exc))
        ui.error_panel("Export failed", str(exc))
        return 1

    lifecycle = task.get("Lifecycle")
    if lifecycle == "SUCCEEDED":
        if not s3_uri:
            repo_config = (filesystem.get("LustreConfiguration", {}) or {}).get(
                "DataRepositoryConfiguration", {}
            ) or {}
            export_path = repo_config.get("ExportPath")
            if export_path:
                s3_uri = f"{export_path.rstrip('/')}/{relative_path}"
        _write_status(options, "success", s3_uri, None)
        ui.success_panel(
            "Export complete",
            f"Cluster: {options.cluster_name}\n"
            f"Target: {s3_uri or relative_path}\n"
            f"Status file: {options.output_dir / STATUS_FILENAME}",
        )
        return 0

    failure_details = task.get("FailureDetails") or {}
    message = failure_details.get("Message") or f"Task ended with status {lifecycle}"
    _write_status(options, "error", s3_uri, message)
    ui.error_panel("Export failed", message)
    return 1
