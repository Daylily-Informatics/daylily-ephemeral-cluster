#!/usr/bin/env python3
"""Export FSx pipeline results to S3 and record status locally."""

from __future__ import annotations

import argparse
import dataclasses
import logging
import sys
import time
from pathlib import Path
from typing import Dict, Optional

import boto3
from botocore.exceptions import BotoCoreError, ClientError
import yaml

LOGGER = logging.getLogger("daylily.export_fsx")

POLL_INTERVAL_SECONDS = 30
STATUS_FILENAME = "fsx_export.yaml"


@dataclasses.dataclass
class ExportOptions:
    cluster: str
    target_uri: str
    region: str
    profile: Optional[str]
    output_dir: Path


def _configure_logging(verbose: bool) -> None:
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


def _normalise_target(
    filesystem: Dict[str, object], target_uri: str
) -> tuple[str, Optional[str]]:
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
                "Target URI must reside under the FSx export path; "
                f"expected prefix {export_path}"
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


def _start_export(
    client,
    filesystem: Dict[str, object],
    relative_path: str,
) -> str:
    filesystem_id = filesystem.get("FileSystemId")
    if not filesystem_id:
        raise RuntimeError("FSx filesystem is missing an identifier")
    lustre_config = filesystem.get("LustreConfiguration", {}) or {}
    repo_config = lustre_config.get("DataRepositoryConfiguration", {}) or {}
    export_path = repo_config.get("ExportPath")
    report_path = None
    if export_path:
        report_path = (
            f"{export_path.rstrip('/')}/daylily-monitor/{int(time.time())}/export-report"
        )
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
    payload: Dict[str, object] = {
        "fsx_export": {
            "status": status,
            "s3_uri": s3_uri,
        }
    }
    if message:
        payload["fsx_export"]["message"] = message
    options.output_dir.mkdir(parents=True, exist_ok=True)
    status_path = options.output_dir / STATUS_FILENAME
    status_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    LOGGER.info("Wrote export status to %s", status_path)


def _run(options: ExportOptions) -> int:
    session = _create_session(options)
    client = session.client("fsx")
    try:
        filesystem = _find_filesystem(client, options.cluster)
        relative_path, s3_uri = _normalise_target(filesystem, options.target_uri)
        LOGGER.info(
            "Launching export for cluster %s (path: %s)",
            options.cluster,
            relative_path,
        )
        task_id = _start_export(client, filesystem, relative_path)
        LOGGER.info("Started data repository task %s", task_id)
        task = _await_export(client, task_id)
    except (ClientError, BotoCoreError, RuntimeError) as exc:
        LOGGER.error("FSx export failed: %s", exc)
        _write_status(options, "error", None, str(exc))
        return 1

    lifecycle = task.get("Lifecycle")
    if lifecycle == "SUCCEEDED":
        message = None
        if not s3_uri:
            repo_config = (
                (filesystem.get("LustreConfiguration", {}) or {})
                .get("DataRepositoryConfiguration", {})
                or {}
            )
            export_path = repo_config.get("ExportPath")
            if export_path:
                s3_uri = f"{export_path.rstrip('/')}/{relative_path}"
        _write_status(options, "success", s3_uri, message)
        return 0

    failure_details = task.get("FailureDetails") or {}
    message = failure_details.get("Message") or f"Task ended with status {lifecycle}"
    _write_status(options, "error", s3_uri, message)
    return 1


def _parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cluster", required=True, help="ParallelCluster name")
    parser.add_argument("--target-uri", required=True, help="FSx relative path or S3 URI")
    parser.add_argument("--region", required=True, help="AWS region")
    parser.add_argument(
        "--profile",
        help="AWS profile for authentication (defaults to environment)",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Directory where the export status YAML should be written",
    )
    parser.add_argument(
        "--verbose", action="store_true", help="Enable verbose logging"
    )
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = _parse_args(argv)
    options = ExportOptions(
        cluster=args.cluster,
        target_uri=args.target_uri,
        region=args.region,
        profile=args.profile,
        output_dir=Path(args.output_dir).expanduser().resolve(),
    )
    _configure_logging(args.verbose)
    return _run(options)


if __name__ == "__main__":
    sys.exit(main())

