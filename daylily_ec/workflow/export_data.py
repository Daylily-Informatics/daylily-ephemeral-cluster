"""Direct analysis-directory FSx DRA export workflow."""

from __future__ import annotations

import dataclasses
import logging
import time
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Dict, Optional
from urllib.parse import urlparse

import boto3
import yaml
from botocore.exceptions import BotoCoreError, ClientError

from daylily_ec import ui
from daylily_ec.analysis_identity import validate_analysis_segment
from daylily_ec.run_mounts import (
    RunMountError,
    association_is_active,
    describe_data_repository_associations,
    describe_fsx_file_system,
    normalize_s3_uri,
    paths_overlap,
    resolve_fsx_file_system_id,
    validate_dra_compatible_file_system,
    wait_for_association,
    wait_for_deleted_association,
)

LOGGER = logging.getLogger("daylily.export_fsx")

ANALYSIS_EXPORT_ROOT = "/analysis_results/"
HEADNODE_ANALYSIS_EXPORT_ROOT = "/fsx/analysis_results/"
STATUS_FILENAME = "fsx_export.yaml"
EXPORT_SCHEMA_VERSION = 4
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
    destination_analysis_id: Optional[str] = None
    wait: bool = True
    timeout_seconds: int = 3600
    delete_data_in_file_system: bool = False


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
    parts = [part for part in str(candidate or "").strip("/").split("/") if part]
    if len(parts) != 2:
        raise ExportError("source_path must include <executing_entity>/<analysis_id>.")
    entity = validate_analysis_segment(parts[0], field_name="executing_entity")
    analysis_id = validate_analysis_segment(parts[1], field_name="analysis_id")
    return f"{entity}/{analysis_id}"


def analysis_headnode_path(source_path: str) -> str:
    normalized = normalize_export_source_path(source_path)
    suffix = normalized[len(ANALYSIS_EXPORT_ROOT) :]
    return f"{HEADNODE_ANALYSIS_EXPORT_ROOT}{suffix}"


def analysis_dir_from_source_path(source_path: str) -> str:
    normalized = normalize_export_source_path(source_path)
    suffix = normalized[len(ANALYSIS_EXPORT_ROOT) :].strip("/")
    return _safe_analysis_dir("/".join(suffix.split("/")[:2]))


def normalize_export_source_path(source_path: str) -> str:
    raw = str(source_path or "").strip()
    if not raw:
        raise ExportError("source_path is required.")
    if raw.startswith("/fsx/run_dir_mounts/") or raw == "/fsx/run_dir_mounts":
        raise ExportError("Run-directory mounts are read-oriented inputs, not export sources.")
    if raw.startswith("/fsx/data/") or raw == "/fsx/data":
        raise ExportError("Legacy /fsx/data is not an export source.")
    for role_root in (
        "/fsx/references",
        "/fsx/control_data",
        "/fsx/staging",
    ):
        if raw == role_root or raw.startswith(f"{role_root}/"):
            raise ExportError(f"{role_root} is not an export source.")
    if raw.startswith("/fsx/exports/") or raw == "/fsx/exports":
        raise ExportError("The /fsx/exports staging namespace is not supported.")
    if raw.startswith(HEADNODE_ANALYSIS_EXPORT_ROOT):
        raw = ANALYSIS_EXPORT_ROOT + raw[len(HEADNODE_ANALYSIS_EXPORT_ROOT) :]
    elif raw.startswith("/fsx/"):
        raise ExportError(
            "source_path must be under /fsx/analysis_results/<executing_entity>/<analysis_id>."
        )
    if raw.startswith("/run_dir_mounts/"):
        raise ExportError("Run-directory mounts are read-oriented inputs, not export sources.")
    if raw.startswith("/data/") or raw == "/data":
        raise ExportError("Legacy /data is not an export source.")
    for role_root in ("/references", "/control_data", "/staging"):
        if raw == role_root or raw.startswith(f"{role_root}/"):
            raise ExportError(f"{role_root} is not an export source.")
    if raw.startswith("/exports/") or raw == "/exports":
        raise ExportError("The /fsx/exports staging namespace is not supported.")
    if not raw.startswith("/"):
        raise ExportError("source_path must be an absolute FSx path.")
    if "//" in raw:
        raise ExportError("source_path must not contain duplicate slashes.")
    raw_parts = raw.strip("/").split("/")
    if any(part in {".", ".."} for part in raw_parts):
        raise ExportError("source_path must not contain '.' or '..' components.")
    parts = PurePosixPath(raw).parts
    normalized = "/" + "/".join(part for part in parts if part != "/")
    if not normalized.startswith(ANALYSIS_EXPORT_ROOT):
        raise ExportError(
            "source_path must be under /analysis_results/<executing_entity>/<analysis_id>."
        )
    suffix = normalized[len(ANALYSIS_EXPORT_ROOT) :].strip("/")
    source_parts = suffix.split("/")
    if len(source_parts) < 2:
        raise ExportError("source_path must include <executing_entity>/<analysis_id>.")
    _safe_analysis_dir("/".join(source_parts[:2]))
    for index, part in enumerate(source_parts[2:], start=1):
        validate_analysis_segment(part, field_name=f"nested_source_component_{index}")
    return normalized.rstrip("/") + "/"


def _allowed_export_destination_suffixes(
    *,
    source_path: str,
    cluster_name: Optional[str] = None,
    destination_analysis_id: Optional[str] = None,
) -> list[str]:
    normalized_source = normalize_export_source_path(source_path)
    source_suffix = normalized_source[len(ANALYSIS_EXPORT_ROOT) :]
    source_parts = source_suffix.rstrip("/").split("/")
    analysis_dir = "/".join(source_parts[:2])
    nested_suffix = "/".join(source_parts[2:])
    nested_tail = f"{nested_suffix}/" if nested_suffix else ""
    suffixes = [source_suffix]
    if cluster_name:
        cluster_segment = validate_analysis_segment(cluster_name, field_name="cluster_name")
        analysis_id = analysis_dir.split("/", 1)[1]
        cluster_suffix = f"{cluster_segment}/{analysis_id}/{nested_tail}"
        if cluster_suffix not in suffixes:
            suffixes.append(cluster_suffix)
        if destination_analysis_id:
            destination_segment = validate_analysis_segment(
                destination_analysis_id,
                field_name="destination_analysis_id",
            )
            if nested_suffix:
                source_leaf = source_parts[-1]
                package_suffix = (
                    f"{cluster_segment}/{destination_segment}/{source_leaf}/"
                )
                if package_suffix not in suffixes:
                    suffixes.append(package_suffix)
            destination_suffix = (
                f"{cluster_segment}/analysis_results/{destination_segment}/{nested_tail}"
            )
            if destination_suffix not in suffixes:
                suffixes.append(destination_suffix)
    elif destination_analysis_id:
        raise ExportError(
            "cluster_name is required when destination_analysis_id is provided"
        )
    return suffixes


def validate_export_destination_s3_uri(
    destination_s3_uri: str,
    *,
    source_path: str,
    cluster_name: Optional[str] = None,
    destination_analysis_id: Optional[str] = None,
) -> str:
    destination = normalize_s3_uri(destination_s3_uri)
    parsed = urlparse(destination)
    key = parsed.path.lstrip("/")
    expected_keys = _allowed_export_destination_suffixes(
        source_path=source_path,
        cluster_name=cluster_name,
        destination_analysis_id=destination_analysis_id,
    )
    if not any(key.endswith(expected_key) for expected_key in expected_keys):
        raise ExportError(
            "destination_s3_uri must end with one of "
            f"{expected_keys!r}; got s3://{parsed.netloc}/{key}"
        )
    return destination


def resolve_launch_export_destination_s3_uri(
    destination_s3_uri: str,
    *,
    source_path: str,
    cluster_name: Optional[str] = None,
    destination_analysis_id: Optional[str] = None,
) -> str:
    """Resolve a workflow launch auto-export destination.

    The workflow launcher accepts either a full destination or an export root. When an
    export root is supplied, append <cluster>/<analysis_id>/ before handing the value
    to the headnode/export workflow.
    """

    destination = normalize_s3_uri(destination_s3_uri)
    parsed = urlparse(destination)
    key = parsed.path.lstrip("/")
    expected_keys = _allowed_export_destination_suffixes(
        source_path=source_path,
        cluster_name=cluster_name,
        destination_analysis_id=destination_analysis_id,
    )
    if any(key.endswith(expected_key) for expected_key in expected_keys):
        return validate_export_destination_s3_uri(
            destination,
            source_path=source_path,
            cluster_name=cluster_name,
            destination_analysis_id=destination_analysis_id,
        )
    if not cluster_name:
        raise ExportError(
            "--cluster is required when --export-destination-s3-uri is an export root "
            "instead of a full <executing_entity>/<analysis_id>/ destination."
        )
    normalized_source = normalize_export_source_path(source_path)
    source_parts = normalized_source[len(ANALYSIS_EXPORT_ROOT) :].rstrip("/").split("/")
    analysis_id = source_parts[1]
    nested_suffix = "/".join(source_parts[2:])
    nested_tail = f"{nested_suffix}/" if nested_suffix else ""
    cluster_segment = validate_analysis_segment(cluster_name, field_name="cluster_name")
    return validate_export_destination_s3_uri(
        f"{destination}{cluster_segment}/{analysis_id}/{nested_tail}",
        source_path=source_path,
        cluster_name=cluster_name,
        destination_analysis_id=destination_analysis_id,
    )


def validate_s3_destination_prefix_empty(
    client: Any,
    destination_s3_uri: str,
    *,
    source_path: str,
    cluster_name: Optional[str] = None,
    destination_analysis_id: Optional[str] = None,
) -> str:
    """Validate the destination suffix and fail if the S3 prefix already has objects."""
    destination = validate_export_destination_s3_uri(
        destination_s3_uri,
        source_path=source_path,
        cluster_name=cluster_name,
        destination_analysis_id=destination_analysis_id,
    )
    parsed = urlparse(destination)
    bucket = parsed.netloc
    prefix = parsed.path.lstrip("/")
    try:
        response = client.list_objects_v2(Bucket=bucket, Prefix=prefix, MaxKeys=1)
    except (BotoCoreError, ClientError) as exc:
        raise ExportError(f"Unable to inspect S3 destination prefix {destination}: {exc}") from exc
    if response.get("KeyCount", 0):
        raise ExportError(f"S3 destination prefix is not empty: {destination}")
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
    destination_s3_uri: Optional[str] = None,
) -> None:
    try:
        associations = describe_data_repository_associations(
            client,
            filters=[{"Name": "file-system-id", "Values": [fsx_file_system_id]}],
        )
    except (BotoCoreError, ClientError, RunMountError) as exc:
        raise ExportError(f"Unable to inspect existing FSx data repository associations: {exc}") from exc
    normalized_source = normalize_export_source_path(source_path)
    normalized_destination = (
        normalize_s3_uri(destination_s3_uri) if destination_s3_uri else None
    )
    for association in associations:
        if not association_is_active(association):
            continue
        association_id = str(association.get("AssociationId") or "unknown")
        existing_path = str(association.get("FileSystemPath") or "")
        if existing_path and paths_overlap(existing_path, normalized_source):
            raise ExportError(
                "source_path overlaps existing FSx data repository association "
                f"{association_id} at {existing_path}."
            )
        existing_repository = str(association.get("DataRepositoryPath") or "")
        if (
            normalized_destination
            and existing_repository
            and paths_overlap(
                normalize_s3_uri(existing_repository),
                normalized_destination,
            )
        ):
            raise ExportError(
                "destination_s3_uri overlaps existing FSx data repository association "
                f"{association_id} at {existing_repository}."
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
    destination_analysis_id: Optional[str] = None,
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
        cluster_name=cluster_name,
        destination_analysis_id=destination_analysis_id,
    )
    validate_no_overlapping_export_dra(
        client,
        fsx_file_system_id=resolved_fsx_id,
        source_path=file_system_path,
        destination_s3_uri=destination,
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
    cluster_name: Optional[str],
    wait: bool,
    timeout_seconds: int,
    fsx_client: Any,
    destination_analysis_id: Optional[str] = None,
) -> Dict[str, Any]:
    normalized_source = normalize_export_source_path(source_path)
    destination = validate_export_destination_s3_uri(
        destination_s3_uri,
        source_path=normalized_source,
        cluster_name=cluster_name,
        destination_analysis_id=destination_analysis_id,
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
    allow_absent: bool = False,
    delete_data_in_file_system: bool = False,
) -> Dict[str, Any]:
    client = fsx_client or _create_session(region, profile).client("fsx")
    try:
        response = client.delete_data_repository_association(
            AssociationId=association_id,
            DeleteDataInFileSystem=delete_data_in_file_system,
        )
    except ClientError as exc:
        if allow_absent and _is_association_not_found(exc):
            return {
                "association_id": association_id,
                "detach_lifecycle": "NOT_FOUND",
                "detach_absent": True,
                "delete_data_in_file_system": delete_data_in_file_system,
            }
        raise ExportError(f"Unable to detach export data repository association: {exc}") from exc
    except BotoCoreError as exc:
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
        "delete_data_in_file_system": delete_data_in_file_system,
    }


def cleanup_exported_analysis(
    *,
    cluster_name: str,
    fsx_file_system_id: Optional[str],
    source_path: str,
    destination_s3_uri: str,
    destination_analysis_id: str,
    region: str,
    profile: Optional[str],
    timeout_seconds: int,
    fsx_client: Optional[Any] = None,
) -> Dict[str, Any]:
    """Delete one exact exported analysis directory from FSx, never from S3.

    The caller must invoke this only after its owner-side export and registration
    receipts are durable. The temporary DRA has no auto-export policy, and the
    only destructive request is ``DeleteDataInFileSystem=True`` for the exact
    validated ``/analysis_results/<owner>/<execution>/`` mapping.
    """

    client = fsx_client or _create_session(region, profile).client("fsx")
    normalized_source = normalize_export_source_path(source_path)
    destination = validate_export_destination_s3_uri(
        destination_s3_uri,
        source_path=normalized_source,
        cluster_name=cluster_name,
        destination_analysis_id=destination_analysis_id,
    )
    created: Optional[ExportDraRecord] = None

    def _capture_created(record: ExportDraRecord) -> None:
        nonlocal created
        created = record

    try:
        record = attach_export_dra(
            cluster_name=cluster_name,
            fsx_file_system_id=fsx_file_system_id,
            source_path=normalized_source,
            destination_s3_uri=destination,
            destination_analysis_id=destination_analysis_id,
            region=region,
            profile=profile,
            wait=True,
            timeout_seconds=timeout_seconds,
            fsx_client=client,
            on_created=_capture_created,
        )
    except (BotoCoreError, ClientError, RunMountError, ExportError) as exc:
        rollback = ""
        if created is not None:
            try:
                rollback_payload = detach_export_dra(
                    association_id=created.association_id,
                    region=region,
                    profile=profile,
                    wait=True,
                    timeout_seconds=timeout_seconds,
                    fsx_client=client,
                    allow_absent=True,
                    delete_data_in_file_system=False,
                )
                rollback = (
                    "; temporary DRA was detached without deleting FSx data "
                    f"({rollback_payload['detach_lifecycle']})"
                )
            except (BotoCoreError, ClientError, RunMountError, ExportError) as rollback_exc:
                rollback = (
                    "; temporary DRA safe-detach also failed and requires inspection: "
                    f"{rollback_exc}"
                )
        raise ExportError(f"Unable to attach exact FSx cleanup DRA: {exc}{rollback}") from exc

    if record.file_system_path != normalized_source:
        raise ExportError(
            "FSx cleanup DRA path mismatch: "
            f"expected {normalized_source}, got {record.file_system_path}"
        )
    if record.destination_s3_uri != destination:
        raise ExportError(
            "FSx cleanup DRA destination mismatch: "
            f"expected {destination}, got {record.destination_s3_uri}"
        )

    try:
        response = client.delete_data_repository_association(
            AssociationId=record.association_id,
            DeleteDataInFileSystem=True,
        )
    except (BotoCoreError, ClientError) as exc:
        raise ExportError(
            "Unable to delete exact exported analysis data from FSx: "
            f"{record.file_system_path}: {exc}"
        ) from exc

    response_association_id = str(response.get("AssociationId") or "")
    if response_association_id != record.association_id:
        raise ExportError(
            "FSx cleanup response association mismatch: "
            f"expected {record.association_id}, got {response_association_id or 'missing'}"
        )
    if response.get("DeleteDataInFileSystem") is not True:
        raise ExportError(
            "FSx cleanup response did not confirm DeleteDataInFileSystem=true"
        )
    fallback_association = {
        "AssociationId": response_association_id,
        "Lifecycle": str(response.get("Lifecycle") or "DELETING"),
        "FileSystemId": record.fsx_file_system_id,
        "FileSystemPath": record.file_system_path,
        "DataRepositoryPath": record.destination_s3_uri,
    }
    deleted = wait_for_deleted_association(
        client,
        record.association_id,
        fallback_association=fallback_association,
        timeout_seconds=timeout_seconds,
    )
    lifecycle = str(deleted.get("Lifecycle") or "")
    if lifecycle != "DELETED":
        raise ExportError(
            "FSx cleanup DRA did not reach DELETED: "
            f"{record.association_id} lifecycle={lifecycle or 'UNKNOWN'}"
        )
    return {
        "schema_version": 1,
        "status": "success",
        "cluster_name": cluster_name,
        "region": region,
        "fsx_file_system_id": record.fsx_file_system_id,
        "association_id": record.association_id,
        "source_path": record.file_system_path,
        "headnode_path": record.headnode_path,
        "destination_s3_uri": record.destination_s3_uri,
        "detach_lifecycle": lifecycle,
        "delete_data_in_file_system": True,
        "s3_delete_requested": False,
    }


def _is_association_not_found(exc: ClientError) -> bool:
    code = str((exc.response.get("Error") or {}).get("Code") or "")
    return code == "DataRepositoryAssociationNotFound"


def _write_status(options: ExportOptions, payload: Dict[str, Any]) -> None:
    options.output_dir.mkdir(parents=True, exist_ok=True)
    status_path = options.output_dir / STATUS_FILENAME
    status_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    LOGGER.info("Wrote export status to %s", status_path)


def _base_receipt(options: ExportOptions) -> Dict[str, Any]:
    normalized_source = normalize_export_source_path(options.source_path)
    destination_s3_uri = validate_export_destination_s3_uri(
        options.destination_s3_uri,
        source_path=normalized_source,
        cluster_name=options.cluster_name,
        destination_analysis_id=options.destination_analysis_id,
    )
    headnode_path = analysis_headnode_path(normalized_source)
    return {
        "fsx_export": {
            "schema_version": EXPORT_SCHEMA_VERSION,
            "status": "started",
            "phase": "attach",
            "cluster_name": options.cluster_name,
            "region": options.region,
            "analysis_dir": analysis_dir_from_source_path(normalized_source),
            "source_path": normalized_source,
            "headnode_path": headnode_path,
            "destination_s3_uri": destination_s3_uri,
            "fsx_root": headnode_path,
            "s3_root": destination_s3_uri,
            "dayoa_analysis_root": f"{headnode_path}daylily-omics-analysis/",
            "dayoa_s3_root": f"{destination_s3_uri}daylily-omics-analysis/",
            "detached": False,
            "delete_data_in_file_system": options.delete_data_in_file_system,
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
                "delete_data_in_file_system": options.delete_data_in_file_system,
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
        receipt["fsx_export"]["phase"] = "preflight"
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
            destination_analysis_id=options.destination_analysis_id,
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
            cluster_name=options.cluster_name,
            wait=options.wait,
            timeout_seconds=options.timeout_seconds,
            fsx_client=client,
            destination_analysis_id=options.destination_analysis_id,
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
                delete_after_success = bool(
                    options.delete_data_in_file_system
                    and rc == 0
                    and task_payload.get("task_lifecycle") == "SUCCEEDED"
                )
                detach_payload = detach_export_dra(
                    association_id=record.association_id,
                    region=options.region,
                    profile=options.profile,
                    wait=options.wait,
                    timeout_seconds=options.timeout_seconds,
                    fsx_client=client,
                    allow_absent=True,
                    delete_data_in_file_system=delete_after_success,
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
