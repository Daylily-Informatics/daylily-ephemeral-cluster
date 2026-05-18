"""Direct analysis-directory FSx DRA export workflow."""

from __future__ import annotations

import dataclasses
import logging
import time
from datetime import datetime, timezone
from pathlib import PurePosixPath, Path
from typing import Any, Callable, Dict, Optional
from urllib.parse import urlparse

import boto3
from botocore.exceptions import BotoCoreError, ClientError
import yaml

from daylily_ec import ui
from daylily_ec.run_mounts import (
    RunMountError,
    association_is_active,
    describe_fsx_file_system,
    describe_data_repository_associations,
    normalize_s3_uri,
    paths_overlap,
    resolve_fsx_file_system_id,
    validate_dra_compatible_file_system,
    wait_for_association,
    wait_for_deleted_association,
)

LOGGER = logging.getLogger("daylily.export_fsx")

ANALYSIS_EXPORT_ROOT = "/analysis_results/ubuntu/"
HEADNODE_ANALYSIS_EXPORT_ROOT = "/fsx/analysis_results/ubuntu/"
STATUS_FILENAME = "fsx_export.yaml"
EXPORT_SCHEMA_VERSION = 3
EXPORT_PURPOSE_TAG = "output-export"
POLL_INTERVAL_SECONDS = 30


class ExportError(RuntimeError):
    """Raised when an explicit FSx DRA export cannot complete."""


@dataclasses.dataclass
class ExportOptions:
    cluster_name: Optional[str]
    fsx_file_system_id: Optional[str]
    source_path: str
    destination_s3_uri: str
    region: str
    profile: Optional[str]
    output_dir: Path
    wait: bool = True
    timeout_seconds: int = 3600


@dataclasses.dataclass(frozen=True)
class ExportDraRecord:
    analysis_dir: str
    cluster_name: Optional[str]
    region: str
    fsx_file_system_id: str
    file_system_path: str
    headnode_path: str
    destination_s3_uri: str
    association_id: str
    lifecycle: str

    def to_payload(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)


def configure_logging(verbose: bool) -> None:
    """Configure workflow logging for export operations."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(message)s")


def _create_session(region: str, profile: Optional[str]):
    session_kwargs: Dict[str, str] = {"region_name": region}
    if profile:
        session_kwargs["profile_name"] = profile
    return boto3.Session(**session_kwargs)


def _safe_analysis_dir(candidate: str) -> str:
    if not candidate:
        raise ExportError("source_path must include one analysis directory.")
    if candidate in {".", ".."} or ".." in candidate or "/" in candidate or "%" in candidate:
        raise ExportError("analysis_dir must be a single safe path component.")
    return candidate


def analysis_headnode_path(source_path: str) -> str:
    normalized = normalize_export_source_path(source_path)
    return f"{HEADNODE_ANALYSIS_EXPORT_ROOT}{analysis_dir_from_source_path(normalized)}/"


def analysis_dir_from_source_path(source_path: str) -> str:
    normalized = normalize_export_source_path(source_path)
    suffix = normalized[len(ANALYSIS_EXPORT_ROOT) :].strip("/")
    return _safe_analysis_dir(suffix)


def normalize_export_source_path(source_path: str) -> str:
    raw = str(source_path or "").strip()
    if not raw:
        raise ExportError("source_path is required.")
    if raw.startswith("/fsx/run_dir_mounts/") or raw == "/fsx/run_dir_mounts":
        raise ExportError("Run-directory mounts are read-oriented inputs, not export sources.")
    if raw.startswith("/fsx/data/") or raw == "/fsx/data":
        raise ExportError("Reference data under /fsx/data is not an export source.")
    if raw.startswith("/fsx/exports/") or raw == "/fsx/exports":
        raise ExportError("The /fsx/exports staging namespace is not supported.")
    if raw.startswith(HEADNODE_ANALYSIS_EXPORT_ROOT):
        raw = ANALYSIS_EXPORT_ROOT + raw[len(HEADNODE_ANALYSIS_EXPORT_ROOT) :]
    elif raw.startswith("/fsx/"):
        raise ExportError("source_path must be under /fsx/analysis_results/ubuntu/<analysis_dir>.")
    if raw.startswith("/run_dir_mounts/"):
        raise ExportError("Run-directory mounts are read-oriented inputs, not export sources.")
    if raw.startswith("/data/") or raw == "/data":
        raise ExportError("Reference data under /fsx/data is not an export source.")
    if raw.startswith("/exports/") or raw == "/exports":
        raise ExportError("The /fsx/exports staging namespace is not supported.")
    if not raw.startswith("/"):
        raise ExportError("source_path must be an absolute FSx path.")
    if "//" in raw:
        raise ExportError("source_path must not contain duplicate slashes.")
    parts = PurePosixPath(raw).parts
    if ".." in parts:
        raise ExportError("source_path must not contain '..'.")
    normalized = "/" + "/".join(part for part in parts if part != "/")
    if not normalized.startswith(ANALYSIS_EXPORT_ROOT):
        raise ExportError("source_path must be under /analysis_results/ubuntu/<analysis_dir>.")
    suffix = normalized[len(ANALYSIS_EXPORT_ROOT) :].strip("/")
    _safe_analysis_dir(suffix)
    return normalized.rstrip("/") + "/"


def validate_export_destination_s3_uri(destination_s3_uri: str, *, source_path: str) -> str:
    destination = normalize_s3_uri(destination_s3_uri)
    parsed = urlparse(destination)
    key = parsed.path.lstrip("/")
    analysis_dir = analysis_dir_from_source_path(source_path)
    expected_key = f"analysis_results/ubuntu/{analysis_dir}/"
    if key != expected_key:
        raise ExportError(
            "destination_s3_uri must end with "
            f"{expected_key!r}; got s3://{parsed.netloc}/{key}"
        )
    return destination


def resolve_export_fsx_id(
    client: Any,
    *,
    cluster_name: Optional[str],
    fsx_file_system_id: Optional[str],
) -> str:
    if fsx_file_system_id:
        return str(fsx_file_system_id).strip()
    if not cluster_name:
        raise ExportError("Provide --cluster or --fsx-file-system-id.")
    return resolve_fsx_file_system_id(client, cluster_name)


def validate_no_overlapping_export_dra(
    client: Any,
    *,
    fsx_file_system_id: str,
    source_path: str,
) -> None:
    try:
        associations = describe_data_repository_associations(
            client,
            filters=[{"Name": "file-system-id", "Values": [fsx_file_system_id]}],
        )
    except (BotoCoreError, ClientError, RunMountError) as exc:
        raise ExportError(f"Unable to inspect existing FSx data repository associations: {exc}") from exc
    normalized_source = normalize_export_source_path(source_path)
    for association in associations:
        if not association_is_active(association):
            continue
        existing_path = str(association.get("FileSystemPath") or "")
        if existing_path and paths_overlap(existing_path, normalized_source):
            association_id = str(association.get("AssociationId") or "unknown")
            raise ExportError(
                "source_path overlaps existing FSx data repository association "
                f"{association_id} at {existing_path}."
            )


def attach_export_dra(
    *,
    cluster_name: Optional[str],
    fsx_file_system_id: Optional[str],
    source_path: str,
    destination_s3_uri: str,
    region: str,
    profile: Optional[str],
    wait: bool,
    timeout_seconds: int,
    fsx_client: Optional[Any] = None,
    on_created: Optional[Callable[[ExportDraRecord], None]] = None,
) -> ExportDraRecord:
    """Create an output DRA directly on an analysis directory without AutoExport."""
    session = None if fsx_client is not None else _create_session(region, profile)
    client = fsx_client or session.client("fsx")
    resolved_fsx_id = resolve_export_fsx_id(
        client,
        cluster_name=cluster_name,
        fsx_file_system_id=fsx_file_system_id,
    )
    validate_dra_compatible_file_system(describe_fsx_file_system(client, resolved_fsx_id))
    file_system_path = normalize_export_source_path(source_path)
    destination = validate_export_destination_s3_uri(
        destination_s3_uri,
        source_path=file_system_path,
    )
    validate_no_overlapping_export_dra(
        client,
        fsx_file_system_id=resolved_fsx_id,
        source_path=file_system_path,
    )
    try:
        response = client.create_data_repository_association(
            FileSystemId=resolved_fsx_id,
            FileSystemPath=file_system_path,
            DataRepositoryPath=destination,
            BatchImportMetaDataOnCreate=False,
            Tags=[
                {"Key": "lsmc:purpose", "Value": EXPORT_PURPOSE_TAG},
                {"Key": "Name", "Value": analysis_dir_from_source_path(file_system_path)},
            ],
        )
    except (BotoCoreError, ClientError) as exc:
        raise ExportError(f"Unable to create export data repository association: {exc}") from exc
    association = response.get("Association") or {}
    association_id = str(association.get("AssociationId") or "")
    if not association_id:
        raise ExportError("FSx did not return an export data repository association id.")
    created_record = ExportDraRecord(
        analysis_dir=analysis_dir_from_source_path(file_system_path),
        cluster_name=cluster_name,
        region=region,
        fsx_file_system_id=resolved_fsx_id,
        file_system_path=str(association.get("FileSystemPath") or file_system_path),
        headnode_path=analysis_headnode_path(file_system_path),
        destination_s3_uri=destination,
        association_id=association_id,
        lifecycle=str(association.get("Lifecycle") or "UNKNOWN"),
    )
    if on_created is not None:
        on_created(created_record)
    if wait:
        association = wait_for_association(
            client,
            association_id,
            target_lifecycles={"AVAILABLE"},
            timeout_seconds=timeout_seconds,
        )
    return ExportDraRecord(
        analysis_dir=analysis_dir_from_source_path(file_system_path),
        cluster_name=cluster_name,
        region=region,
        fsx_file_system_id=resolved_fsx_id,
        file_system_path=str(association.get("FileSystemPath") or file_system_path),
        headnode_path=analysis_headnode_path(file_system_path),
        destination_s3_uri=destination,
        association_id=association_id,
        lifecycle=str(association.get("Lifecycle") or "UNKNOWN"),
    )


def run_export_task(
    *,
    fsx_file_system_id: str,
    source_path: str,
    destination_s3_uri: str,
    wait: bool,
    timeout_seconds: int,
    fsx_client: Any,
) -> Dict[str, Any]:
    normalized_source = normalize_export_source_path(source_path)
    destination = validate_export_destination_s3_uri(
        destination_s3_uri,
        source_path=normalized_source,
    )
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    report_path = (
        f"{destination.rstrip('/')}/_daylily_monitor/fsx-export/"
        f"{timestamp}/export-report/"
    )
    try:
        response = fsx_client.create_data_repository_task(
            FileSystemId=fsx_file_system_id,
            Type="EXPORT_TO_REPOSITORY",
            Paths=[normalized_source],
            Report={
                "Enabled": True,
                "Path": report_path,
                "Format": "REPORT_CSV_20191124",
                "Scope": "FAILED_FILES_ONLY",
            },
        )
    except (BotoCoreError, ClientError) as exc:
        raise ExportError(f"Unable to start FSx export task: {exc}") from exc
    task = response.get("DataRepositoryTask") or {}
    task_id = str(task.get("TaskId") or "")
    if not task_id:
        raise ExportError("FSx create_data_repository_task did not return a task id.")
    if wait:
        task = await_export_task(
            fsx_client,
            task_id,
            timeout_seconds=timeout_seconds,
        )
    return {
        "task_id": task_id,
        "task_lifecycle": str(task.get("Lifecycle") or "UNKNOWN"),
        "source_path": normalized_source,
        "report_path": report_path,
        "failure_details": task.get("FailureDetails") or {},
    }


def await_export_task(
    client: Any,
    task_id: str,
    *,
    timeout_seconds: int,
) -> Dict[str, Any]:
    deadline = time.time() + timeout_seconds
    while True:
        try:
            response = client.describe_data_repository_tasks(TaskIds=[task_id])
        except (BotoCoreError, ClientError) as exc:
            raise ExportError(f"Unable to describe FSx export task {task_id}: {exc}") from exc
        tasks = response.get("DataRepositoryTasks", []) or []
        if not tasks:
            raise ExportError(f"Unable to locate export task status: {task_id}")
        task = tasks[0]
        lifecycle = str(task.get("Lifecycle") or "")
        LOGGER.info("Task %s status: %s", task_id, lifecycle)
        if lifecycle in {"SUCCEEDED", "FAILED", "CANCELED"}:
            return task
        if time.time() >= deadline:
            raise ExportError(
                f"Timed out waiting for FSx export task {task_id}; "
                f"last lifecycle was {lifecycle or 'UNKNOWN'}."
            )
        time.sleep(POLL_INTERVAL_SECONDS)


def detach_export_dra(
    *,
    association_id: str,
    region: str,
    profile: Optional[str],
    wait: bool,
    timeout_seconds: int,
    fsx_client: Optional[Any] = None,
) -> Dict[str, Any]:
    client = fsx_client or _create_session(region, profile).client("fsx")
    try:
        response = client.delete_data_repository_association(
            AssociationId=association_id,
            DeleteDataInFileSystem=False,
        )
    except (BotoCoreError, ClientError) as exc:
        raise ExportError(f"Unable to detach export data repository association: {exc}") from exc
    association = response.get("Association") or {}
    if wait:
        association = wait_for_deleted_association(
            client,
            association_id,
            fallback_association=association,
            timeout_seconds=timeout_seconds,
        )
    return {
        "association_id": association_id,
        "detach_lifecycle": str(association.get("Lifecycle") or "UNKNOWN"),
        "delete_data_in_file_system": False,
    }


def _write_status(options: ExportOptions, payload: Dict[str, Any]) -> None:
    options.output_dir.mkdir(parents=True, exist_ok=True)
    status_path = options.output_dir / STATUS_FILENAME
    status_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    LOGGER.info("Wrote export status to %s", status_path)


def _base_receipt(options: ExportOptions) -> Dict[str, Any]:
    normalized_source = normalize_export_source_path(options.source_path)
    return {
        "fsx_export": {
            "schema_version": EXPORT_SCHEMA_VERSION,
            "status": "started",
            "phase": "attach",
            "cluster_name": options.cluster_name,
            "region": options.region,
            "analysis_dir": analysis_dir_from_source_path(normalized_source),
            "source_path": normalized_source,
            "headnode_path": analysis_headnode_path(normalized_source),
            "destination_s3_uri": validate_export_destination_s3_uri(
                options.destination_s3_uri,
                source_path=normalized_source,
            ),
            "detached": False,
            "delete_data_in_file_system": False,
            "failure_details": {},
        }
    }


def run_export_workflow(options: ExportOptions) -> int:
    """Attach an output DRA, run an explicit FSx export task, detach the DRA."""
    ui.phase("EXPORT")
    ui.step("Preparing direct FSx export DRA")

    try:
        receipt = _base_receipt(options)
    except (RuntimeError, RunMountError, ExportError) as exc:
        receipt = {
            "fsx_export": {
                "schema_version": EXPORT_SCHEMA_VERSION,
                "status": "error",
                "phase": "validate",
                "cluster_name": options.cluster_name,
                "region": options.region,
                "source_path": options.source_path,
                "destination_s3_uri": options.destination_s3_uri,
                "detached": False,
                "delete_data_in_file_system": False,
                "failure_details": {"message": str(exc)},
            }
        }
        _write_status(options, receipt)
        ui.error_panel("Export failed", str(exc))
        return 1
    session = _create_session(options.region, options.profile)
    client = session.client("fsx")
    record: Optional[ExportDraRecord] = None
    task_payload: Dict[str, Any] = {}
    detach_payload: Dict[str, Any] = {}
    rc = 1
    message = ""

    try:
        def _capture_created_dra(created_record: ExportDraRecord) -> None:
            nonlocal record
            record = created_record
            receipt["fsx_export"].update(created_record.to_payload())

        record = attach_export_dra(
            cluster_name=options.cluster_name,
            fsx_file_system_id=options.fsx_file_system_id,
            source_path=options.source_path,
            destination_s3_uri=options.destination_s3_uri,
            region=options.region,
            profile=options.profile,
            wait=options.wait,
            timeout_seconds=options.timeout_seconds,
            fsx_client=client,
            on_created=_capture_created_dra,
        )
        receipt["fsx_export"].update(record.to_payload())
        receipt["fsx_export"]["phase"] = "run"
        ui.info(f"Attached export DRA {record.association_id} at {record.headnode_path}")

        task_payload = run_export_task(
            fsx_file_system_id=record.fsx_file_system_id,
            source_path=record.file_system_path,
            destination_s3_uri=record.destination_s3_uri,
            wait=options.wait,
            timeout_seconds=options.timeout_seconds,
            fsx_client=client,
        )
        receipt["fsx_export"].update(task_payload)
        if task_payload["task_lifecycle"] != "SUCCEEDED":
            raise ExportError(
                "FSx export task ended with lifecycle "
                f"{task_payload['task_lifecycle']}: {task_payload['failure_details']}"
            )
        rc = 0
        message = "Export complete"
    except (ClientError, BotoCoreError, RuntimeError, RunMountError, ExportError) as exc:
        message = str(exc)
        receipt["fsx_export"]["status"] = "error"
        failure_details = {"message": message}
        if task_payload.get("failure_details"):
            failure_details["task_failure_details"] = task_payload["failure_details"]
        receipt["fsx_export"]["failure_details"] = failure_details
        LOGGER.error("FSx export failed: %s", exc)
    finally:
        if record is not None:
            receipt["fsx_export"]["phase"] = "detach"
            try:
                detach_payload = detach_export_dra(
                    association_id=record.association_id,
                    region=options.region,
                    profile=options.profile,
                    wait=options.wait,
                    timeout_seconds=options.timeout_seconds,
                    fsx_client=client,
                )
                receipt["fsx_export"].update(detach_payload)
                receipt["fsx_export"]["detached"] = True
            except (ClientError, BotoCoreError, RuntimeError, RunMountError, ExportError) as exc:
                rc = 1
                message = str(exc)
                receipt["fsx_export"]["status"] = "error"
                receipt["fsx_export"]["failure_details"] = {"message": message}
                receipt["fsx_export"]["detached"] = False
        if rc == 0:
            receipt["fsx_export"]["status"] = "success"
            receipt["fsx_export"]["phase"] = "complete"
        _write_status(options, receipt)

    if rc == 0:
        ui.success_panel(
            "Export complete",
            f"Cluster: {options.cluster_name or 'n/a'}\n"
            f"FSx: {receipt['fsx_export']['fsx_file_system_id']}\n"
            f"Source: {receipt['fsx_export']['source_path']}\n"
            f"S3: {receipt['fsx_export']['destination_s3_uri']}\n"
            f"Status file: {options.output_dir / STATUS_FILENAME}",
        )
        return 0

    ui.error_panel("Export failed", message)
    return 1


def shell_copy_hint(record: ExportDraRecord) -> str:
    """Return the analysis directory path exported by *record*."""
    return record.headnode_path
