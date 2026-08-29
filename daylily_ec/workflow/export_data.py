"""Direct analysis-directory FSx DRA export workflow."""

from __future__ import annotations

import dataclasses
import json
import logging
import shlex
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Dict, Mapping, Optional
from urllib.parse import urlparse

import boto3
import yaml
from botocore.exceptions import BotoCoreError, ClientError

from daylily_ec import ui
from daylily_ec.analysis_identity import validate_analysis_segment
from daylily_ec.execution_status import (
    STATUS_FILENAME as EXECUTION_STATUS_FILENAME,
)
from daylily_ec.execution_status import (
    STATUS_SCHEMA_VERSION as EXECUTION_STATUS_SCHEMA_VERSION,
)
from daylily_ec.execution_status import (
    ExecutionStatusError,
    validate_execution_status,
)
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
EXPORT_SCHEMA_VERSION = 6
EXPORT_PURPOSE_TAG = "output-export"
EXPORT_INSPECTION_SCHEMA = "dyec.exports.inspect.v1"
POLL_INTERVAL_SECONDS = 30
ANALYSIS_EXPORT_KIND = "analysis"
RUNTIME_CACHE_EXPORT_KIND = "runtime_cache"
RUNTIME_ASSET_EXPORT_KIND = "runtime_asset"
SHARED_REFERENCE_EXPORT_KIND = "shared_reference"
EXPORT_KINDS = frozenset(
    {
        ANALYSIS_EXPORT_KIND,
        RUNTIME_ASSET_EXPORT_KIND,
        RUNTIME_CACHE_EXPORT_KIND,
        SHARED_REFERENCE_EXPORT_KIND,
    }
)
MAX_DESTINATION_EVIDENCE_PAGES = 100
SHARED_REFERENCE_STAGE_MARKER = "DYEC_SHARED_REFERENCE_STAGE"


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
    export_kind: str = ANALYSIS_EXPORT_KIND


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


def validate_runtime_asset_export_source(source_path: str) -> str:
    """Require one immutable runtime asset beneath the aligned staging root."""

    normalized = normalize_export_source_path(source_path)
    suffix = normalized[len(ANALYSIS_EXPORT_ROOT) :].strip("/")
    parts = suffix.split("/")
    if len(parts) != 3 or parts[:2] != ["runtime_assets", "cached_envs"]:
        raise ExportError(
            "runtime_asset exports require exactly "
            "/fsx/analysis_results/runtime_assets/cached_envs/<asset>"
        )
    validate_analysis_segment(parts[2], field_name="runtime_asset")
    return normalized


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
    if (
        len(source_parts) == 3
        and source_parts[:2] == ["runtime_assets", "cached_envs"]
    ):
        # Runtime assets use the established standalone runtime-bucket layout,
        # not the reference-bucket layout used by their aligned FSx staging
        # path. Keep this exact so an export cannot drift into a second prefix.
        return [f"cached_envs/{source_parts[2]}/"]
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
    export_kind: str = ANALYSIS_EXPORT_KIND,
) -> str:
    destination = normalize_s3_uri(destination_s3_uri)
    parsed = urlparse(destination)
    key = parsed.path.lstrip("/")
    normalized_source = normalize_export_source_path(source_path)
    if export_kind == SHARED_REFERENCE_EXPORT_KIND:
        source_parts = (
            normalized_source[len(ANALYSIS_EXPORT_ROOT) :].rstrip("/").split("/")
        )
        if len(source_parts) != 2:
            raise ExportError(
                "shared-reference exports require one complete top-level "
                "/fsx/analysis_results/<executing_entity>/<resource_id> root"
            )
        resource_id = validate_analysis_segment(
            source_parts[1], field_name="shared_reference_resource_id"
        )
        destination_parts = [part for part in key.rstrip("/").split("/") if part]
        if len(destination_parts) < 2:
            raise ExportError(
                "shared-reference destination_s3_uri must include a namespace and resource id"
            )
        for index, part in enumerate(destination_parts, start=1):
            validate_analysis_segment(
                part, field_name=f"shared_reference_destination_component_{index}"
            )
        if destination_parts[-1] != resource_id:
            raise ExportError(
                "shared-reference destination leaf must exactly match source resource id "
                f"{resource_id!r}; got {destination_parts[-1]!r}"
            )
        return destination
    if export_kind not in EXPORT_KINDS:
        raise ExportError(
            f"unsupported export kind: {export_kind!r}; expected one of {sorted(EXPORT_KINDS)!r}"
        )
    expected_keys = _allowed_export_destination_suffixes(
        source_path=source_path,
        cluster_name=cluster_name,
        destination_analysis_id=destination_analysis_id,
    )
    source_parts = normalized_source[len(ANALYSIS_EXPORT_ROOT) :].rstrip("/").split("/")
    is_runtime_asset = (
        len(source_parts) == 3
        and source_parts[:2] == ["runtime_assets", "cached_envs"]
    )
    destination_matches = (
        key == expected_keys[0]
        if is_runtime_asset
        else any(key.endswith(expected_key) for expected_key in expected_keys)
    )
    if not destination_matches:
        raise ExportError(
            "destination_s3_uri must end with one of "
            f"{expected_keys!r}; got s3://{parsed.netloc}/{key}"
        )
    return destination


def clone_status_evidence_s3_uri(
    *,
    source_path: str,
    destination_s3_uri: str,
    cluster_name: Optional[str] = None,
    destination_analysis_id: Optional[str] = None,
) -> str:
    """Return the one v2 status object that a full analysis export must retain.

    This deliberately accepts only a complete analysis-root export.  A nested
    export cannot honestly claim to contain the clone-root execution record.
    """

    normalized_source = normalize_export_source_path(source_path)
    analysis_dir = analysis_dir_from_source_path(normalized_source)
    expected_source = f"{ANALYSIS_EXPORT_ROOT}{analysis_dir}/"
    if normalized_source != expected_source:
        raise ExportError(
            "clone-status evidence requires the complete analysis directory, not a nested export"
        )
    destination = validate_export_destination_s3_uri(
        destination_s3_uri,
        source_path=normalized_source,
        cluster_name=cluster_name,
        destination_analysis_id=destination_analysis_id,
    )
    return f"{destination}daylily-omics-analysis/{EXECUTION_STATUS_FILENAME}"


def verify_exported_clone_status_v2_evidence(
    s3_client: Any,
    *,
    source_path: str,
    destination_s3_uri: str,
    cluster_name: Optional[str] = None,
    destination_analysis_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Read and validate the exported canonical v2 record without mutation."""

    status_s3_uri = clone_status_evidence_s3_uri(
        source_path=source_path,
        destination_s3_uri=destination_s3_uri,
        cluster_name=cluster_name,
        destination_analysis_id=destination_analysis_id,
    )
    parsed = urlparse(status_s3_uri)
    bucket = parsed.netloc
    key = parsed.path.lstrip("/")
    try:
        response = s3_client.get_object(Bucket=bucket, Key=key)
        body = response.get("Body")
        if body is None or not hasattr(body, "read"):
            raise ExportError("S3 clone-status evidence object has no readable body")
        raw_bytes = body.read()
    except (BotoCoreError, ClientError, OSError) as exc:
        raise ExportError(
            "Unable to read exported clone-resident status v2 evidence "
            f"at {status_s3_uri}: {exc}"
        ) from exc
    if not isinstance(raw_bytes, bytes):
        raise ExportError("S3 clone-status evidence body must be bytes")
    try:
        payload = json.loads(raw_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ExportError(
            f"Exported clone-resident status v2 is not valid JSON: {status_s3_uri}"
        ) from exc
    normalized_source = normalize_export_source_path(source_path)
    analysis_root = analysis_headnode_path(normalized_source).rstrip("/")
    repo_path = f"{analysis_root}/daylily-omics-analysis"
    try:
        validated = validate_execution_status(
            payload,
            repo_path=repo_path,
            analysis_root=analysis_root,
        )
    except ExecutionStatusError as exc:
        raise ExportError(
            f"Exported clone-resident status v2 is invalid at {status_s3_uri}: {exc}"
        ) from exc
    attempts = validated["attempts"]
    if not attempts:
        raise ExportError(
            "Exported clone-resident status v2 contains no retained execution attempts: "
            f"{status_s3_uri}"
        )
    return {
        "required": True,
        "verified": True,
        "s3_uri": status_s3_uri,
        "schema_version": EXECUTION_STATUS_SCHEMA_VERSION,
        "attempt_count": len(attempts),
        "latest_attempt_id": attempts[-1]["attempt_id"],
    }


def verify_exported_destination_evidence(
    s3_client: Any,
    *,
    source_path: str,
    destination_s3_uri: str,
    cluster_name: Optional[str] = None,
    destination_analysis_id: Optional[str] = None,
    export_kind: str = ANALYSIS_EXPORT_KIND,
) -> Dict[str, Any]:
    """Return bounded, exact-prefix evidence for a completed DRA export.

    This verification stays inside DYEC so callers never substitute their own
    S3 listing logic for the public export receipt. It fails closed if a
    bounded listing cannot prove the complete destination is non-empty.
    """

    destination = validate_export_destination_s3_uri(
        destination_s3_uri,
        source_path=source_path,
        cluster_name=cluster_name,
        destination_analysis_id=destination_analysis_id,
        export_kind=export_kind,
    )
    parsed = urlparse(destination)
    bucket = parsed.netloc
    prefix = parsed.path.lstrip("/")
    continuation_token: str | None = None
    object_count = 0
    total_bytes = 0
    list_request_count = 0
    try:
        for _page in range(MAX_DESTINATION_EVIDENCE_PAGES):
            request: Dict[str, Any] = {"Bucket": bucket, "Prefix": prefix, "MaxKeys": 1000}
            if continuation_token is not None:
                request["ContinuationToken"] = continuation_token
            response = s3_client.list_objects_v2(**request)
            list_request_count += 1
            contents = response.get("Contents") or []
            if not isinstance(contents, list):
                raise ExportError("S3 export destination listing returned malformed contents")
            for item in contents:
                if not isinstance(item, dict):
                    raise ExportError("S3 export destination listing returned malformed object rows")
                size = item.get("Size")
                if isinstance(size, bool) or not isinstance(size, int) or size < 0:
                    raise ExportError("S3 export destination listing returned an invalid object size")
                object_count += 1
                total_bytes += size
            if response.get("IsTruncated") is not True:
                break
            continuation_token = str(response.get("NextContinuationToken") or "").strip()
            if not continuation_token:
                raise ExportError("S3 export destination listing was truncated without a token")
        else:
            raise ExportError(
                "S3 export destination exceeds the bounded verification page limit"
            )
    except (BotoCoreError, ClientError, OSError) as exc:
        raise ExportError(
            f"Unable to verify exported S3 destination {destination}: {exc}"
        ) from exc
    if object_count < 1:
        raise ExportError(f"Exported S3 destination contains no objects: {destination}")
    return {
        "required": True,
        "verified": True,
        "schema_version": "dyec.export.destination_evidence.v1",
        "s3_uri": destination,
        "list_request_count": list_request_count,
        "object_count": object_count,
        "total_bytes": total_bytes,
        "max_page_limit": MAX_DESTINATION_EVIDENCE_PAGES,
    }


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
    export_kind: str = ANALYSIS_EXPORT_KIND,
) -> str:
    """Validate the destination suffix and fail if the S3 prefix already has objects."""
    destination = validate_export_destination_s3_uri(
        destination_s3_uri,
        source_path=source_path,
        cluster_name=cluster_name,
        destination_analysis_id=destination_analysis_id,
        export_kind=export_kind,
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


def _parse_inspection_timestamp(value: str, *, field_name: str) -> datetime:
    raw = str(value or "").strip()
    if raw.endswith("Z"):
        raw = f"{raw[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise ExportError(f"{field_name} must be an ISO-8601 timestamp with timezone") from exc
    if parsed.tzinfo is None:
        raise ExportError(f"{field_name} must include a timezone")
    return parsed.astimezone(timezone.utc)


def _utc_iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _task_timestamp(task: Mapping[str, Any], field: str) -> datetime:
    value = task.get(field)
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ExportError(f"FSx export task is missing timezone-aware {field}")
    return value.astimezone(timezone.utc)


def _list_export_tasks(client: Any, *, fsx_file_system_id: str) -> list[Dict[str, Any]]:
    request: Dict[str, Any] = {
        "Filters": [{"Name": "file-system-id", "Values": [fsx_file_system_id]}],
        "MaxResults": 100,
    }
    tasks: list[Dict[str, Any]] = []
    while True:
        try:
            response = client.describe_data_repository_tasks(**request)
        except (BotoCoreError, ClientError) as exc:
            raise ExportError(f"Unable to inspect FSx data repository tasks: {exc}") from exc
        rows = response.get("DataRepositoryTasks") or []
        if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
            raise ExportError("FSx data repository task inventory is malformed")
        tasks.extend(rows)
        next_token = str(response.get("NextToken") or "").strip()
        if not next_token:
            return tasks
        request["NextToken"] = next_token


def _lookup_cloudtrail_events(
    client: Any,
    *,
    event_name: str,
    started_after: datetime,
    started_before: datetime,
) -> list[Dict[str, Any]]:
    request: Dict[str, Any] = {
        "LookupAttributes": [
            {"AttributeKey": "EventName", "AttributeValue": event_name}
        ],
        "StartTime": started_after,
        "EndTime": started_before,
        "MaxResults": 50,
    }
    events: list[Dict[str, Any]] = []
    for _page in range(20):
        try:
            response = client.lookup_events(**request)
        except (BotoCoreError, ClientError) as exc:
            raise ExportError(f"Unable to inspect CloudTrail {event_name} events: {exc}") from exc
        rows = response.get("Events") or []
        if not isinstance(rows, list):
            raise ExportError(f"CloudTrail {event_name} inventory is malformed")
        for row in rows:
            if not isinstance(row, Mapping):
                raise ExportError(f"CloudTrail {event_name} inventory contains a malformed row")
            raw_event = row.get("CloudTrailEvent")
            if not isinstance(raw_event, str):
                raise ExportError(f"CloudTrail {event_name} row has no event document")
            try:
                document = json.loads(raw_event)
            except json.JSONDecodeError as exc:
                raise ExportError(f"CloudTrail {event_name} event document is invalid") from exc
            if not isinstance(document, dict):
                raise ExportError(f"CloudTrail {event_name} event document is not an object")
            if (
                document.get("eventSource") != "fsx.amazonaws.com"
                or document.get("eventName") != event_name
                or document.get("errorCode") is not None
                or document.get("errorMessage") is not None
            ):
                continue
            event_time = _parse_inspection_timestamp(
                str(document.get("eventTime") or ""),
                field_name=f"CloudTrail {event_name} eventTime",
            )
            if not started_after <= event_time <= started_before:
                continue
            document["_event_id"] = str(row.get("EventId") or document.get("eventID") or "")
            document["_event_time"] = event_time
            events.append(document)
        next_token = str(response.get("NextToken") or "").strip()
        if not next_token:
            return events
        request["NextToken"] = next_token
    raise ExportError(f"CloudTrail {event_name} inspection exceeded the bounded page limit")


def _request_mapping(event: Mapping[str, Any], *, event_name: str) -> Mapping[str, Any]:
    request = event.get("requestParameters")
    if not isinstance(request, Mapping):
        raise ExportError(f"CloudTrail {event_name} event has no request parameters")
    return request


def _response_mapping(event: Mapping[str, Any], *, event_name: str) -> Mapping[str, Any]:
    response = event.get("responseElements")
    if not isinstance(response, Mapping):
        raise ExportError(f"CloudTrail {event_name} event has no response elements")
    return response


def _event_identity(event: Mapping[str, Any]) -> tuple[str, str]:
    identity = event.get("userIdentity")
    if not isinstance(identity, Mapping):
        raise ExportError("CloudTrail FSx event has no user identity")
    principal_id = str(identity.get("principalId") or "").strip()
    account_id = str(event.get("recipientAccountId") or "").strip()
    if not principal_id or not account_id:
        raise ExportError("CloudTrail FSx event has incomplete caller identity")
    return principal_id, account_id


def _event_receipt(event: Mapping[str, Any]) -> Dict[str, Any]:
    event_time = event.get("_event_time")
    if not isinstance(event_time, datetime):
        raise ExportError("CloudTrail FSx event has no parsed event time")
    event_id = str(event.get("_event_id") or "").strip()
    request_id = str(event.get("requestID") or "").strip()
    if not event_id or not request_id:
        raise ExportError("CloudTrail FSx event has incomplete immutable identifiers")
    return {
        "event_id": event_id,
        "request_id": request_id,
        "event_time": _utc_iso(event_time),
    }


def inspect_completed_export(
    *,
    cluster_name: str,
    fsx_file_system_id: str,
    source_path: str,
    destination_s3_uri: str,
    destination_analysis_id: str,
    started_after: str,
    started_before: str,
    region: str,
    profile: Optional[str],
    fsx_client: Optional[Any] = None,
    cloudtrail_client: Optional[Any] = None,
    s3_client: Optional[Any] = None,
) -> Dict[str, Any]:
    """Prove one completed transfer using only read-only provider and S3 calls."""

    normalized_cluster = str(cluster_name or "").strip()
    normalized_fsx_id = str(fsx_file_system_id or "").strip()
    if not normalized_cluster:
        raise ExportError("cluster_name is required for completed export inspection")
    if not normalized_fsx_id:
        raise ExportError("fsx_file_system_id is required for completed export inspection")
    normalized_source = normalize_export_source_path(source_path)
    normalized_destination = validate_export_destination_s3_uri(
        destination_s3_uri,
        source_path=normalized_source,
        cluster_name=normalized_cluster,
        destination_analysis_id=destination_analysis_id,
    )
    after = _parse_inspection_timestamp(started_after, field_name="started_after")
    before = _parse_inspection_timestamp(started_before, field_name="started_before")
    if before <= after:
        raise ExportError("started_before must be later than started_after")
    if before - after > timedelta(hours=6):
        raise ExportError("completed export inspection window must not exceed six hours")
    if before > datetime.now(timezone.utc) + timedelta(minutes=5):
        raise ExportError("started_before must not be in the future")

    session = None
    if fsx_client is None or cloudtrail_client is None or s3_client is None:
        session = _create_session(region, profile)
    fsx = fsx_client or session.client("fsx")
    cloudtrail = cloudtrail_client or session.client("cloudtrail")
    s3 = s3_client or session.client("s3")

    matching_tasks: list[Dict[str, Any]] = []
    for task in _list_export_tasks(fsx, fsx_file_system_id=normalized_fsx_id):
        paths = task.get("Paths")
        if (
            task.get("FileSystemId") != normalized_fsx_id
            or str(task.get("Type") or "").upper() != "EXPORT_TO_REPOSITORY"
            or str(task.get("Lifecycle") or "").upper() != "SUCCEEDED"
            or not isinstance(paths, list)
            or paths != [normalized_source]
        ):
            continue
        creation_time = _task_timestamp(task, "CreationTime")
        end_time = _task_timestamp(task, "EndTime")
        if not (after <= creation_time <= end_time <= before):
            continue
        report = task.get("Report")
        if not isinstance(report, Mapping):
            continue
        report_path = str(report.get("Path") or "").strip()
        expected_report_root = f"{normalized_destination}_daylily_monitor/fsx-export/"
        if (
            report.get("Enabled") is not True
            or report.get("Format") != "REPORT_CSV_20191124"
            or report.get("Scope") != "FAILED_FILES_ONLY"
            or not report_path.startswith(expected_report_root)
            or not report_path.endswith("/export-report/")
        ):
            continue
        matching_tasks.append(task)
    if len(matching_tasks) != 1:
        raise ExportError(
            "completed export inspection requires exactly one successful FSx task in the window"
        )
    task = matching_tasks[0]
    task_id = str(task.get("TaskId") or "").strip()
    if not task_id:
        raise ExportError("completed export inspection task has no task id")
    task_report = task.get("Report")
    if not isinstance(task_report, Mapping):
        raise ExportError("completed export inspection task has no report")
    report_path = str(task_report.get("Path") or "").strip()

    create_association_events = _lookup_cloudtrail_events(
        cloudtrail,
        event_name="CreateDataRepositoryAssociation",
        started_after=after,
        started_before=before,
    )
    matching_association_events: list[Dict[str, Any]] = []
    expected_name_tag = analysis_dir_from_source_path(normalized_source)
    for event in create_association_events:
        request = _request_mapping(event, event_name="CreateDataRepositoryAssociation")
        raw_tags = request.get("tags")
        tag_rows = raw_tags if isinstance(raw_tags, list) else []
        tags = {
            str(item.get("key") or ""): str(item.get("value") or "")
            for item in tag_rows
            if isinstance(item, Mapping)
        }
        try:
            event_destination = normalize_s3_uri(
                str(request.get("dataRepositoryPath") or "")
            )
        except RunMountError:
            continue
        if (
            request.get("fileSystemId") != normalized_fsx_id
            or request.get("fileSystemPath") != normalized_source
            or event_destination != normalized_destination
            or request.get("batchImportMetaDataOnCreate") is not False
            or tags.get("lsmc:purpose") != EXPORT_PURPOSE_TAG
            or tags.get("Name") != expected_name_tag
        ):
            continue
        response = _response_mapping(event, event_name="CreateDataRepositoryAssociation")
        association = response.get("association")
        if not isinstance(association, Mapping):
            continue
        association_id = str(association.get("associationId") or "").strip()
        if not association_id:
            continue
        event["_association_id"] = association_id
        matching_association_events.append(event)
    if len(matching_association_events) != 1:
        raise ExportError(
            "completed export inspection requires exactly one matching DRA creation event"
        )
    association_event = matching_association_events[0]
    association_id = str(association_event["_association_id"])

    create_task_events = _lookup_cloudtrail_events(
        cloudtrail,
        event_name="CreateDataRepositoryTask",
        started_after=after,
        started_before=before,
    )
    matching_task_events: list[Dict[str, Any]] = []
    for event in create_task_events:
        request = _request_mapping(event, event_name="CreateDataRepositoryTask")
        response = _response_mapping(event, event_name="CreateDataRepositoryTask")
        response_task = response.get("dataRepositoryTask")
        request_report = request.get("report")
        try:
            event_report_path = normalize_s3_uri(
                str(request_report.get("path") or "")
                if isinstance(request_report, Mapping)
                else ""
            )
        except RunMountError:
            continue
        if (
            request.get("fileSystemId") != normalized_fsx_id
            or str(request.get("type") or "").upper() != "EXPORT_TO_REPOSITORY"
            or request.get("paths") != [normalized_source]
            or not isinstance(request_report, Mapping)
            or event_report_path != normalize_s3_uri(report_path)
            or not isinstance(response_task, Mapping)
            or response_task.get("taskId") != task_id
        ):
            continue
        matching_task_events.append(event)
    if len(matching_task_events) != 1:
        raise ExportError(
            "completed export inspection requires exactly one matching task creation event"
        )
    task_event = matching_task_events[0]

    delete_events = _lookup_cloudtrail_events(
        cloudtrail,
        event_name="DeleteDataRepositoryAssociation",
        started_after=after,
        started_before=before,
    )
    matching_delete_events = [
        event
        for event in delete_events
        if (
            (request := _request_mapping(
                event,
                event_name="DeleteDataRepositoryAssociation",
            )).get("associationId")
            == association_id
            and request.get("deleteDataInFileSystem") is False
        )
    ]
    if len(matching_delete_events) != 1:
        raise ExportError(
            "completed export inspection requires exactly one preserving DRA deletion event"
        )
    delete_event = matching_delete_events[0]

    event_times = [
        association_event.get("_event_time"),
        task_event.get("_event_time"),
        delete_event.get("_event_time"),
    ]
    if any(not isinstance(value, datetime) for value in event_times):
        raise ExportError("completed export inspection event timeline is incomplete")
    if not event_times[0] <= event_times[1] <= event_times[2]:
        raise ExportError("completed export inspection event timeline is out of order")
    identities = {
        _event_identity(association_event),
        _event_identity(task_event),
        _event_identity(delete_event),
    }
    if len(identities) != 1:
        raise ExportError("completed export inspection events have different caller identities")

    try:
        association_response = fsx.describe_data_repository_associations(
            AssociationIds=[association_id]
        )
    except ClientError as exc:
        code = str((exc.response.get("Error") or {}).get("Code") or "")
        if code != "DataRepositoryAssociationNotFound":
            raise ExportError(f"Unable to confirm detached export DRA: {exc}") from exc
        association_response = {"Associations": []}
    except BotoCoreError as exc:
        raise ExportError(f"Unable to confirm detached export DRA: {exc}") from exc
    if association_response.get("Associations"):
        raise ExportError("completed export inspection found the output DRA still present")

    clone_status_evidence = verify_exported_clone_status_v2_evidence(
        s3,
        source_path=normalized_source,
        destination_s3_uri=normalized_destination,
        cluster_name=normalized_cluster,
        destination_analysis_id=destination_analysis_id,
    )
    destination_evidence = verify_exported_destination_evidence(
        s3,
        source_path=normalized_source,
        destination_s3_uri=normalized_destination,
        cluster_name=normalized_cluster,
        destination_analysis_id=destination_analysis_id,
    )
    return {
        "schema_version": EXPORT_INSPECTION_SCHEMA,
        "ok": True,
        "operation": "inspect",
        "read_only": True,
        "status": "success",
        "phase": "complete",
        "cluster_name": normalized_cluster,
        "region": region,
        "fsx_file_system_id": normalized_fsx_id,
        "association_id": association_id,
        "source_path": normalized_source,
        "headnode_path": analysis_headnode_path(normalized_source),
        "destination_s3_uri": normalized_destination,
        "destination_analysis_id": destination_analysis_id,
        "task_id": task_id,
        "task_lifecycle": "SUCCEEDED",
        "report_path": report_path,
        "detached": True,
        "detach_lifecycle": "DELETED",
        "delete_data_in_file_system": False,
        "failure_details": {},
        "started_after": _utc_iso(after),
        "started_before": _utc_iso(before),
        "task_created_at": _utc_iso(_task_timestamp(task, "CreationTime")),
        "task_completed_at": _utc_iso(_task_timestamp(task, "EndTime")),
        "cloudtrail": {
            "create_association": _event_receipt(association_event),
            "create_task": _event_receipt(task_event),
            "delete_association": _event_receipt(delete_event),
        },
        "clone_status_v2_evidence": clone_status_evidence,
        "destination_s3_evidence": destination_evidence,
    }


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


def resolve_shared_reference_dra(
    client: Any,
    *,
    fsx_file_system_id: str,
    destination_s3_uri: str,
) -> Dict[str, Any]:
    """Resolve one existing DRA that maps the requested shared-reference prefix."""

    destination = normalize_s3_uri(destination_s3_uri)
    matches: list[Dict[str, Any]] = []
    for association in describe_data_repository_associations(
        client,
        filters=[{"Name": "file-system-id", "Values": [fsx_file_system_id]}],
    ):
        if not association_is_active(association):
            continue
        repository = normalize_s3_uri(str(association.get("DataRepositoryPath") or ""))
        if not destination.startswith(repository) or destination == repository:
            continue
        file_system_path = str(association.get("FileSystemPath") or "").strip()
        if not file_system_path.startswith("/") or "//" in file_system_path:
            continue
        file_system_path = file_system_path.rstrip("/") + "/"
        relative = destination[len(repository) :]
        target_file_system_path = f"{file_system_path}{relative}".replace("//", "/")
        target_parts = PurePosixPath(target_file_system_path).parts
        if any(part in {".", ".."} for part in target_parts):
            continue
        matches.append(
            {
                "association_id": str(association.get("AssociationId") or ""),
                "association_lifecycle": str(association.get("Lifecycle") or "UNKNOWN"),
                "association_file_system_path": file_system_path,
                "association_data_repository_path": repository,
                "target_file_system_path": target_file_system_path,
                "target_headnode_path": f"/fsx{target_file_system_path}",
            }
        )
    if len(matches) != 1 or not matches[0]["association_id"]:
        raise ExportError(
            "shared-reference export requires exactly one active existing DRA that maps "
            f"the destination prefix; found {len(matches)}"
        )
    return matches[0]


def build_shared_reference_stage_script(*, source_path: str, target_path: str) -> str:
    """Build the fail-closed headnode copy into an existing reference DRA."""

    source = analysis_headnode_path(source_path).rstrip("/")
    target = str(target_path or "").rstrip("/")
    if not target.startswith("/fsx/") or "//" in target:
        raise ExportError("shared-reference target must be one absolute /fsx path")
    if any(part in {".", ".."} for part in PurePosixPath(target).parts):
        raise ExportError("shared-reference target must not contain '.' or '..'")
    incomplete = f"{target}.dyec-incomplete"
    return f"""set -Eeuo pipefail
umask 077
source_path={shlex.quote(source)}
target_path={shlex.quote(target)}
incomplete_path={shlex.quote(incomplete)}

test -d "${{source_path}}"
test ! -e "${{target_path}}"
test ! -e "${{incomplete_path}}"
command -v sudo >/dev/null
sudo -n true
sudo -n install -d -m 0755 "$(dirname -- "${{target_path}}")"
sudo -n cp -a --reflink=auto -- "${{source_path}}" "${{incomplete_path}}"
source_bytes="$(du -sb -- "${{source_path}}" | cut -f1)"
target_bytes="$(sudo -n du -sb -- "${{incomplete_path}}" | cut -f1)"
source_entries="$(find "${{source_path}}" -xdev -printf '.' | wc -c)"
target_entries="$(sudo -n find "${{incomplete_path}}" -xdev -printf '.' | wc -c)"
test "${{source_bytes}}" = "${{target_bytes}}"
test "${{source_entries}}" = "${{target_entries}}"
sudo -n mv -- "${{incomplete_path}}" "${{target_path}}"
printf '{SHARED_REFERENCE_STAGE_MARKER}\t%s\t%s\t%s\n' \
  "${{target_path}}" "${{target_bytes}}" "${{target_entries}}"
"""


def parse_shared_reference_stage_result(stdout: str) -> Dict[str, Any]:
    matches = [
        line
        for line in str(stdout or "").splitlines()
        if line.startswith(f"{SHARED_REFERENCE_STAGE_MARKER}\t")
    ]
    if len(matches) != 1:
        raise ExportError("shared-reference staging did not emit one terminal result")
    fields = matches[0].split("\t")
    if len(fields) != 4:
        raise ExportError("shared-reference staging result is malformed")
    try:
        byte_count = int(fields[2])
        entry_count = int(fields[3])
    except ValueError as exc:
        raise ExportError("shared-reference staging counts are not integers") from exc
    if byte_count <= 0 or entry_count <= 0:
        raise ExportError("shared-reference staging produced an empty target")
    return {
        "target_headnode_path": fields[1],
        "byte_count": byte_count,
        "entry_count": entry_count,
        "copy_command": "sudo -n cp -a --reflink=auto",
        "content_hashing": False,
    }


def preflight_export(
    *,
    cluster_name: Optional[str],
    fsx_file_system_id: Optional[str],
    source_path: str,
    destination_s3_uri: str,
    region: str,
    profile: Optional[str],
    destination_analysis_id: Optional[str] = None,
    export_kind: str = ANALYSIS_EXPORT_KIND,
    fsx_client: Optional[Any] = None,
    s3_client: Optional[Any] = None,
) -> Dict[str, Any]:
    """Read-only validate one exact fresh FSx-to-S3 export mapping."""

    session = None
    if fsx_client is None or s3_client is None:
        session = _create_session(region, profile)
    fsx = fsx_client or session.client("fsx")
    s3 = s3_client or session.client("s3")
    resolved_fsx_id = resolve_export_fsx_id(
        fsx,
        cluster_name=cluster_name,
        fsx_file_system_id=fsx_file_system_id,
    )
    validate_dra_compatible_file_system(describe_fsx_file_system(fsx, resolved_fsx_id))
    normalized_source = normalize_export_source_path(source_path)
    destination = validate_export_destination_s3_uri(
        destination_s3_uri,
        source_path=normalized_source,
        cluster_name=cluster_name,
        destination_analysis_id=destination_analysis_id,
        export_kind=export_kind,
    )
    shared_reference_dra: Dict[str, Any] | None = None
    if export_kind == SHARED_REFERENCE_EXPORT_KIND:
        shared_reference_dra = resolve_shared_reference_dra(
            fsx,
            fsx_file_system_id=resolved_fsx_id,
            destination_s3_uri=destination,
        )
    else:
        validate_no_overlapping_export_dra(
            fsx,
            fsx_file_system_id=resolved_fsx_id,
            source_path=normalized_source,
            destination_s3_uri=destination,
        )
    destination = validate_s3_destination_prefix_empty(
        s3,
        destination,
        source_path=normalized_source,
        cluster_name=cluster_name,
        destination_analysis_id=destination_analysis_id,
        export_kind=export_kind,
    )
    payload = {
        "schema_version": "dyec.exports.preflight.v1",
        "ok": True,
        "operation": "preflight",
        "read_only": True,
        "mutation_attempted": False,
        "cluster_name": cluster_name,
        "region": region,
        "fsx_file_system_id": resolved_fsx_id,
        "source_path": normalized_source,
        "headnode_path": analysis_headnode_path(normalized_source),
        "destination_s3_uri": destination,
        "destination_analysis_id": destination_analysis_id,
        "destination_empty": True,
        "overlapping_dra": False,
        "fsx_dra_compatible": True,
    }
    if export_kind != ANALYSIS_EXPORT_KIND:
        payload["export_kind"] = export_kind
    if shared_reference_dra is not None:
        payload["existing_reference_dra"] = shared_reference_dra
    return payload


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
    export_kind: str = ANALYSIS_EXPORT_KIND,
    fsx_client: Optional[Any] = None,
    s3_client: Optional[Any] = None,
    require_empty_destination: bool = False,
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
        export_kind=export_kind,
    )
    validate_no_overlapping_export_dra(
        client,
        fsx_file_system_id=resolved_fsx_id,
        source_path=file_system_path,
        destination_s3_uri=destination,
    )
    if require_empty_destination:
        destination_s3_client = s3_client
        if destination_s3_client is None and session is not None:
            destination_s3_client = session.client("s3")
        if destination_s3_client is None:
            raise ExportError(
                "S3 client is required to verify an empty export destination before DRA creation."
            )
        # This must stay directly adjacent to the mutating association request: a
        # non-empty destination is never a valid target for a fresh no-delete export.
        destination = validate_s3_destination_prefix_empty(
            destination_s3_client,
            destination,
            source_path=file_system_path,
            cluster_name=cluster_name,
            destination_analysis_id=destination_analysis_id,
            export_kind=export_kind,
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
    export_kind: str = ANALYSIS_EXPORT_KIND,
    task_source_path: Optional[str] = None,
) -> Dict[str, Any]:
    normalized_source = normalize_export_source_path(source_path)
    destination = validate_export_destination_s3_uri(
        destination_s3_uri,
        source_path=normalized_source,
        cluster_name=cluster_name,
        destination_analysis_id=destination_analysis_id,
        export_kind=export_kind,
    )
    normalized_task_source = normalized_source
    if task_source_path is not None:
        raw_task_source = str(task_source_path).strip()
        if raw_task_source.startswith("/fsx/"):
            raw_task_source = raw_task_source[len("/fsx") :]
        if not raw_task_source.startswith("/") or "//" in raw_task_source:
            raise ExportError("task_source_path must be one absolute FSx path")
        if any(part in {".", ".."} for part in PurePosixPath(raw_task_source).parts):
            raise ExportError("task_source_path must not contain '.' or '..'")
        normalized_task_source = raw_task_source.rstrip("/") + "/"
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    report_path = (
        f"{destination.rstrip('/')}/_daylily_monitor/fsx-export/"
        f"{timestamp}/export-report/"
    )
    try:
        response = fsx_client.create_data_repository_task(
            FileSystemId=fsx_file_system_id,
            Type="EXPORT_TO_REPOSITORY",
            Paths=[normalized_task_source],
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
        "source_path": normalized_task_source,
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
        "destination_analysis_id": destination_analysis_id,
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
    if options.export_kind not in EXPORT_KINDS:
        raise ExportError(
            f"unsupported export kind: {options.export_kind!r}; expected one of {sorted(EXPORT_KINDS)!r}"
        )
    normalized_source = normalize_export_source_path(options.source_path)
    if options.export_kind == RUNTIME_ASSET_EXPORT_KIND:
        validate_runtime_asset_export_source(normalized_source)
        if options.delete_data_in_file_system:
            raise ExportError(
                "runtime_asset exports must retain staged FSx data for verification"
            )
    if options.export_kind == SHARED_REFERENCE_EXPORT_KIND:
        if not options.cluster_name:
            raise ExportError("shared-reference exports require --cluster")
        if options.delete_data_in_file_system:
            raise ExportError(
                "shared-reference exports must retain source FSx data for verification"
            )
        if options.destination_analysis_id:
            raise ExportError(
                "shared-reference exports do not accept destination_analysis_id"
            )
    destination_s3_uri = validate_export_destination_s3_uri(
        options.destination_s3_uri,
        source_path=normalized_source,
        cluster_name=options.cluster_name,
        destination_analysis_id=options.destination_analysis_id,
        export_kind=options.export_kind,
    )
    headnode_path = analysis_headnode_path(normalized_source)
    clone_status_evidence: Dict[str, Any] | None = None
    destination_evidence: Dict[str, Any] | None = None
    if options.export_kind == ANALYSIS_EXPORT_KIND:
        clone_status_evidence = {
            "required": True,
            "verified": False,
            "s3_uri": clone_status_evidence_s3_uri(
                source_path=normalized_source,
                destination_s3_uri=destination_s3_uri,
                cluster_name=options.cluster_name,
                destination_analysis_id=options.destination_analysis_id,
            ),
        }
    if options.export_kind in {
        ANALYSIS_EXPORT_KIND,
        SHARED_REFERENCE_EXPORT_KIND,
    }:
        destination_evidence = {
            "required": True,
            "verified": False,
            "schema_version": "dyec.export.destination_evidence.v1",
            "s3_uri": destination_s3_uri,
        }
    receipt = {
        "fsx_export": {
            "schema_version": EXPORT_SCHEMA_VERSION,
            "export_kind": options.export_kind,
            "status": "started",
            "phase": "attach",
            "cluster_name": options.cluster_name,
            "region": options.region,
            "analysis_dir": analysis_dir_from_source_path(normalized_source),
            "source_path": normalized_source,
            "headnode_path": headnode_path,
            "destination_s3_uri": destination_s3_uri,
            "destination_analysis_id": options.destination_analysis_id,
            "fsx_root": headnode_path,
            "s3_root": destination_s3_uri,
            "detached": False,
            "delete_data_in_file_system": options.delete_data_in_file_system,
            "failure_details": {},
        }
    }
    if options.export_kind == ANALYSIS_EXPORT_KIND:
        receipt["fsx_export"].update(
            {
                "dayoa_analysis_root": f"{headnode_path}daylily-omics-analysis/",
                "dayoa_s3_root": f"{destination_s3_uri}daylily-omics-analysis/",
            }
        )
    if clone_status_evidence is not None:
        receipt["fsx_export"]["clone_status_v2_evidence"] = clone_status_evidence
    if destination_evidence is not None:
        receipt["fsx_export"]["destination_s3_evidence"] = destination_evidence
    return receipt


def run_shared_reference_export_workflow(options: ExportOptions) -> int:
    """Stage one resource into an existing reference DRA and export it."""

    from daylily_ec.aws.ssm import (
        SsmError,
        resolve_headnode_instance_id,
        run_shell,
        wait_for_ssm_online,
    )

    try:
        receipt = _base_receipt(options)
    except (RuntimeError, RunMountError, ExportError) as exc:
        receipt = {
            "fsx_export": {
                "schema_version": EXPORT_SCHEMA_VERSION,
                "status": "error",
                "phase": "validate",
                "export_kind": SHARED_REFERENCE_EXPORT_KIND,
                "source_path": options.source_path,
                "destination_s3_uri": options.destination_s3_uri,
                "delete_data_in_file_system": False,
                "failure_details": {"message": str(exc)},
            }
        }
        _write_status(options, receipt)
        ui.error_panel("Export failed", str(exc))
        return 1

    session = _create_session(options.region, options.profile)
    fsx = session.client("fsx")
    s3 = session.client("s3")
    try:
        receipt["fsx_export"]["phase"] = "preflight"
        preflight = preflight_export(
            cluster_name=options.cluster_name,
            fsx_file_system_id=options.fsx_file_system_id,
            source_path=options.source_path,
            destination_s3_uri=options.destination_s3_uri,
            destination_analysis_id=None,
            export_kind=SHARED_REFERENCE_EXPORT_KIND,
            region=options.region,
            profile=options.profile,
            fsx_client=fsx,
            s3_client=s3,
        )
        mapping = preflight["existing_reference_dra"]
        receipt["fsx_export"].update(
            {
                "fsx_file_system_id": preflight["fsx_file_system_id"],
                "existing_reference_dra": mapping,
                "association_id": mapping["association_id"],
                "existing_dra_preserved": True,
                "detached": False,
                "detach_not_applicable": True,
            }
        )

        target = resolve_headnode_instance_id(
            str(options.cluster_name),
            options.region,
            profile=options.profile,
        )
        wait_for_ssm_online(
            target.instance_id,
            options.region,
            profile=options.profile,
            timeout=120,
        )
        receipt["fsx_export"]["phase"] = "stage"
        stage_command = run_shell(
            target.instance_id,
            options.region,
            build_shared_reference_stage_script(
                source_path=options.source_path,
                target_path=mapping["target_headnode_path"],
            ),
            profile=options.profile,
            as_user="ubuntu",
            timeout=options.timeout_seconds,
            comment=(
                "DYEC shared-reference stage "
                f"{analysis_dir_from_source_path(options.source_path)}"
            ),
        )
        receipt["fsx_export"]["headnode_instance_id"] = target.instance_id
        receipt["fsx_export"]["stage_ssm_command_id"] = stage_command.command_id
        receipt["fsx_export"]["stage"] = parse_shared_reference_stage_result(
            stage_command.stdout
        )

        repeated = preflight_export(
            cluster_name=options.cluster_name,
            fsx_file_system_id=preflight["fsx_file_system_id"],
            source_path=options.source_path,
            destination_s3_uri=options.destination_s3_uri,
            destination_analysis_id=None,
            export_kind=SHARED_REFERENCE_EXPORT_KIND,
            region=options.region,
            profile=options.profile,
            fsx_client=fsx,
            s3_client=s3,
        )
        if repeated["existing_reference_dra"] != mapping:
            raise ExportError("reference DRA mapping changed after staging")

        receipt["fsx_export"]["phase"] = "run"
        task_payload = run_export_task(
            fsx_file_system_id=preflight["fsx_file_system_id"],
            source_path=options.source_path,
            task_source_path=mapping["target_file_system_path"],
            destination_s3_uri=options.destination_s3_uri,
            cluster_name=options.cluster_name,
            wait=options.wait,
            timeout_seconds=options.timeout_seconds,
            fsx_client=fsx,
            export_kind=SHARED_REFERENCE_EXPORT_KIND,
        )
        receipt["fsx_export"].update(task_payload)
        if task_payload["task_lifecycle"] != "SUCCEEDED":
            raise ExportError(
                "FSx export task ended with lifecycle "
                f"{task_payload['task_lifecycle']}: {task_payload['failure_details']}"
            )
        receipt["fsx_export"]["destination_s3_evidence"] = (
            verify_exported_destination_evidence(
                s3,
                source_path=options.source_path,
                destination_s3_uri=options.destination_s3_uri,
                cluster_name=options.cluster_name,
                export_kind=SHARED_REFERENCE_EXPORT_KIND,
            )
        )
        receipt["fsx_export"].update(
            {
                "status": "success",
                "phase": "complete",
                "failure_details": {},
                "source_fsx_preserved": True,
                "reference_fsx_present": True,
            }
        )
        _write_status(options, receipt)
        ui.success_panel(
            "Shared-reference export complete",
            f"S3: {options.destination_s3_uri}",
        )
        return 0
    except (BotoCoreError, ClientError, RuntimeError, RunMountError, ExportError, SsmError) as exc:
        receipt["fsx_export"].update(
            {
                "status": "error",
                "failure_details": {"message": str(exc)},
            }
        )
        _write_status(options, receipt)
        ui.error_panel("Shared-reference export failed", str(exc))
        return 1


def run_export_workflow(options: ExportOptions) -> int:
    """Attach an output DRA, run an explicit FSx export task, detach the DRA."""
    if options.export_kind == SHARED_REFERENCE_EXPORT_KIND:
        return run_shared_reference_export_workflow(options)
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
                "destination_analysis_id": options.destination_analysis_id,
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
            export_kind=options.export_kind,
            fsx_client=client,
            s3_client=session.client("s3"),
            require_empty_destination=True,
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
            export_kind=options.export_kind,
        )
        receipt["fsx_export"].update(task_payload)
        if task_payload["task_lifecycle"] != "SUCCEEDED":
            raise ExportError(
                "FSx export task ended with lifecycle "
                f"{task_payload['task_lifecycle']}: {task_payload['failure_details']}"
            )
        if options.export_kind == ANALYSIS_EXPORT_KIND:
            receipt["fsx_export"]["clone_status_v2_evidence"] = (
                verify_exported_clone_status_v2_evidence(
                    session.client("s3"),
                    source_path=record.headnode_path,
                    destination_s3_uri=record.destination_s3_uri,
                    cluster_name=record.cluster_name,
                    destination_analysis_id=options.destination_analysis_id,
                )
            )
        if options.export_kind in {
            ANALYSIS_EXPORT_KIND,
            SHARED_REFERENCE_EXPORT_KIND,
        }:
            receipt["fsx_export"]["destination_s3_evidence"] = (
                verify_exported_destination_evidence(
                    session.client("s3"),
                    source_path=record.headnode_path,
                    destination_s3_uri=record.destination_s3_uri,
                    cluster_name=record.cluster_name,
                    destination_analysis_id=options.destination_analysis_id,
                    export_kind=options.export_kind,
                )
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
