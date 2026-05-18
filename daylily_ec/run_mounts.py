"""FSx Data Repository Association lifecycle helpers for run directory mounts."""

from __future__ import annotations

import dataclasses
import getpass
import json
import re
import shlex
import time
from datetime import datetime, timezone
from pathlib import PurePosixPath
from typing import Any, Dict, Iterable, List, Optional, Sequence
from urllib.parse import urlparse

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from daylily_ec.state.store import config_dir

MOUNT_ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")
MAX_MOUNT_ID_LENGTH = 128
FSX_RUN_MOUNT_ROOT = "/run_dir_mounts/"
HEADNODE_RUN_MOUNT_ROOT = "/fsx/run_dir_mounts/"
DEFAULT_AUTO_IMPORT_EVENTS = ("NEW", "CHANGED")
ALL_AUTO_IMPORT_EVENTS = ("NEW", "CHANGED", "DELETED")
TERMINAL_FAILURE_LIFECYCLES = {"FAILED", "MISCONFIGURED"}
INACTIVE_LIFECYCLES = {"DELETED", "DELETING", "DELETE_IN_PROGRESS", "FAILED"}
RUN_MOUNT_PURPOSE_TAG = "run-dir-mount"
STATE_SCHEMA_VERSION = 1
LOCAL_PROJECTION_CREATED = "created"
LOCAL_PROJECTION_PRESENT = "present"
LOCAL_PROJECTION_MISSING = "missing"
LOCAL_PROJECTION_UNKNOWN = "unknown"


class RunMountError(RuntimeError):
    """Raised when a run mount request is invalid or cannot be completed."""


@dataclasses.dataclass(frozen=True)
class RunMountRecord:
    """Stable local projection of an FSx run directory mount."""

    mount_id: str
    run_id: str
    platform: str
    cluster_name: Optional[str]
    region: str
    source_s3_uri: str
    fsx_file_system_id: str
    file_system_path: str
    headnode_path: str
    association_id: str
    lifecycle: str
    read_only: bool
    profile_hint: Optional[str] = None
    auto_import_events: Sequence[str] = dataclasses.field(default_factory=tuple)
    auto_export_events: Sequence[str] = dataclasses.field(default_factory=tuple)
    batch_import_metadata_on_create: bool = True
    created_at: str = ""
    updated_at: str = ""
    created_by: str = ""
    tags: Dict[str, str] = dataclasses.field(default_factory=dict)
    warnings: Sequence[str] = dataclasses.field(default_factory=tuple)
    local_projection_status: str = LOCAL_PROJECTION_UNKNOWN

    @property
    def data_repository_path(self) -> str:
        return self.source_s3_uri

    def to_output_payload(self) -> Dict[str, Any]:
        """Return stable JSON fields consumed by Ursa and operators."""
        payload: Dict[str, Any] = {
            "mount_id": self.mount_id,
            "run_id": self.run_id,
            "platform": self.platform,
            "cluster_name": self.cluster_name,
            "region": self.region,
            "source_s3_uri": self.source_s3_uri,
            "fsx_file_system_id": self.fsx_file_system_id,
            "file_system_path": self.file_system_path,
            "headnode_path": self.headnode_path,
            "association_id": self.association_id,
            "lifecycle": self.lifecycle,
            "read_only": self.read_only,
            "data_repository_path": self.data_repository_path,
            "auto_import_events": list(self.auto_import_events),
            "auto_export_events": list(self.auto_export_events),
            "batch_import_metadata_on_create": self.batch_import_metadata_on_create,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
        if self.profile_hint:
            payload["profile_hint"] = self.profile_hint
        if self.created_by:
            payload["created_by"] = self.created_by
        if self.tags:
            payload["tags"] = dict(self.tags)
        if self.warnings:
            payload["warnings"] = list(self.warnings)
        payload["local_projection_status"] = self.local_projection_status
        return payload

    def to_state_payload(self) -> Dict[str, Any]:
        payload = {
            "schema_version": STATE_SCHEMA_VERSION,
            **self.to_output_payload(),
        }
        return payload


@dataclasses.dataclass(frozen=True)
class CreateRunMountRequest:
    """Validated request for creating an FSx run directory mount."""

    cluster_name: Optional[str]
    fsx_file_system_id: Optional[str]
    region: str
    profile: Optional[str]
    source_s3_uri: str
    mount_id: Optional[str] = None
    run_id: Optional[str] = None
    platform: str = "OTHER"
    file_system_path: Optional[str] = None
    read_only: bool = True
    batch_import_metadata_on_create: bool = True
    auto_import_events: Sequence[str] = DEFAULT_AUTO_IMPORT_EVENTS
    auto_export_events: Sequence[str] = dataclasses.field(default_factory=tuple)
    allow_writeback_admin: bool = False
    wait: bool = True
    timeout_seconds: int = 900
    tags: Dict[str, str] = dataclasses.field(default_factory=dict)


def validate_mount_id(mount_id: str) -> str:
    """Validate and return a safe mount id."""
    candidate = str(mount_id or "").strip()
    if not candidate:
        raise RunMountError("mount_id is required.")
    if candidate in {".", ".."}:
        raise RunMountError("mount_id must not be '.' or '..'.")
    if len(candidate) > MAX_MOUNT_ID_LENGTH:
        raise RunMountError(
            f"mount_id must be at most {MAX_MOUNT_ID_LENGTH} characters: {candidate!r}"
        )
    if ".." in candidate or "%" in candidate:
        raise RunMountError("mount_id must not contain '..' or percent-encoding characters.")
    if not MOUNT_ID_RE.fullmatch(candidate):
        raise RunMountError(
            "mount_id may contain only letters, numbers, dot, underscore, and dash."
        )
    return candidate


def normalize_s3_uri(uri: str) -> str:
    """Normalize an S3 URI to a bucket/prefix form with one trailing slash."""
    raw = str(uri or "").strip()
    parsed = urlparse(raw)
    if parsed.scheme != "s3" or not parsed.netloc:
        raise RunMountError(f"Expected an s3:// URI, got {uri!r}.")
    if parsed.query or parsed.fragment or parsed.params:
        raise RunMountError("S3 URI must not include params, query, or fragment components.")
    key = parsed.path.lstrip("/")
    if not key:
        return f"s3://{parsed.netloc}/"
    return f"s3://{parsed.netloc}/{key.rstrip('/')}/"


def mount_id_from_request(
    *,
    mount_id: Optional[str],
    run_id: Optional[str],
    source_s3_uri: str,
) -> str:
    """Resolve a mount id from explicit mount id, run id, or S3 basename."""
    if mount_id:
        return validate_mount_id(mount_id)
    if run_id:
        return validate_mount_id(run_id)
    normalized = normalize_s3_uri(source_s3_uri)
    parsed = urlparse(normalized)
    parts = [part for part in parsed.path.split("/") if part]
    if not parts:
        raise RunMountError("Provide --mount-id or --run-id for bucket-root S3 mounts.")
    return validate_mount_id(parts[-1])


def normalize_file_system_path(path: Optional[str], *, mount_id: str) -> str:
    """Normalize the FSx API path for a run mount."""
    if path is None or not str(path).strip():
        return f"{FSX_RUN_MOUNT_ROOT}{mount_id}/"

    raw = str(path).strip()
    if raw.startswith(HEADNODE_RUN_MOUNT_ROOT) or raw == HEADNODE_RUN_MOUNT_ROOT.rstrip("/"):
        raise RunMountError(
            "FSx API path must use /run_dir_mounts/<mount_id>/, not /fsx/run_dir_mounts/."
        )
    if not raw.startswith("/"):
        raise RunMountError("FSx file-system path must be absolute.")
    if raw == "/":
        raise RunMountError("FSx file-system path must not be '/'.")
    if not raw.startswith(FSX_RUN_MOUNT_ROOT):
        raise RunMountError(f"FSx file-system path must be under {FSX_RUN_MOUNT_ROOT}.")
    if "//" in raw:
        raise RunMountError("FSx file-system path must not contain duplicate slashes.")
    parts = PurePosixPath(raw).parts
    if ".." in parts:
        raise RunMountError("FSx file-system path must not contain '..'.")
    normalized = "/" + "/".join(part for part in parts if part != "/")
    if normalized == FSX_RUN_MOUNT_ROOT.rstrip("/"):
        raise RunMountError("FSx file-system path must not be the run mount root.")
    return normalized.rstrip("/") + "/"


def headnode_path_from_file_system_path(file_system_path: str) -> str:
    normalized = normalize_file_system_path(file_system_path, mount_id="_validated")
    if not normalized.startswith(FSX_RUN_MOUNT_ROOT):
        raise RunMountError(f"FSx file-system path must be under {FSX_RUN_MOUNT_ROOT}.")
    suffix = normalized[len(FSX_RUN_MOUNT_ROOT) :]
    validate_mount_id(suffix.strip("/").split("/", 1)[0])
    return f"{HEADNODE_RUN_MOUNT_ROOT}{suffix}"


def paths_overlap(left: str, right: str) -> bool:
    """Return true when two normalized S3 prefixes or FSx paths overlap."""
    first = _with_trailing_slash(left)
    second = _with_trailing_slash(right)
    return first == second or first.startswith(second) or second.startswith(first)


def validate_no_overlaps(
    associations: Iterable[Dict[str, Any]],
    *,
    file_system_path: str,
    source_s3_uri: str,
) -> None:
    """Reject active DRA path or S3 prefix overlaps."""
    for association in associations:
        if not association_is_active(association):
            continue
        existing_fsx = str(association.get("FileSystemPath") or "")
        existing_s3 = str(association.get("DataRepositoryPath") or "")
        assoc_id = str(association.get("AssociationId") or "unknown")
        if existing_fsx and paths_overlap(existing_fsx, file_system_path):
            raise RunMountError(
                f"FSx file-system path overlaps active DRA {assoc_id}: {existing_fsx}"
            )
        if existing_s3 and paths_overlap(normalize_s3_uri(existing_s3), source_s3_uri):
            raise RunMountError(
                f"S3 source prefix overlaps active DRA {assoc_id}: {existing_s3}"
            )


def parse_auto_import_events(raw: Optional[str]) -> List[str]:
    """Parse the CLI auto-import value."""
    if raw is None or raw.strip() == "":
        return list(DEFAULT_AUTO_IMPORT_EVENTS)
    return _parse_event_tokens(raw, default=DEFAULT_AUTO_IMPORT_EVENTS)


def parse_auto_export_events(
    raw: Optional[str],
    *,
    allow_writeback_admin: bool,
    read_only: bool,
) -> List[str]:
    """Parse AutoExport events and enforce the read-only default policy."""
    if raw is None or raw.strip() == "":
        if not read_only and not allow_writeback_admin:
            raise RunMountError("--no-read-only requires --allow-writeback-admin.")
        return []
    if not allow_writeback_admin:
        raise RunMountError("--auto-export is forbidden unless --allow-writeback-admin is set.")
    if read_only:
        raise RunMountError("--auto-export requires --no-read-only.")
    return _parse_event_tokens(raw, default=())


def parse_tags(values: Optional[Sequence[str]]) -> Dict[str, str]:
    tags: Dict[str, str] = {"lsmc:purpose": RUN_MOUNT_PURPOSE_TAG}
    for value in values or []:
        if "=" not in value:
            raise RunMountError(f"Tag must be KEY=VALUE, got {value!r}.")
        key, tag_value = value.split("=", 1)
        key = key.strip()
        if not key:
            raise RunMountError(f"Tag key must not be empty: {value!r}.")
        tags[key] = tag_value
    return tags


def create_run_mount(
    request: CreateRunMountRequest,
    *,
    fsx_client: Optional[Any] = None,
) -> RunMountRecord:
    """Create an FSx DRA for a run directory and persist the local record."""
    _require_region(request.region)
    if not request.cluster_name and not request.fsx_file_system_id:
        raise RunMountError("Provide --cluster or --fsx-file-system-id.")

    client = fsx_client or _build_fsx_client(region=request.region, profile=request.profile)
    source_s3_uri = normalize_s3_uri(request.source_s3_uri)
    mount_id = mount_id_from_request(
        mount_id=request.mount_id,
        run_id=request.run_id,
        source_s3_uri=source_s3_uri,
    )
    run_id = validate_mount_id(request.run_id) if request.run_id else mount_id
    platform = _normalize_platform(request.platform)
    file_system_path = normalize_file_system_path(request.file_system_path, mount_id=mount_id)
    auto_import_events = list(request.auto_import_events)
    auto_export_events = list(request.auto_export_events)
    read_only = bool(request.read_only and not auto_export_events)

    fsx_file_system_id = request.fsx_file_system_id or resolve_fsx_file_system_id(
        client,
        request.cluster_name or "",
    )
    filesystem = describe_fsx_file_system(client, fsx_file_system_id)
    validate_dra_compatible_file_system(filesystem)
    associations = list_data_repository_associations(client, fsx_file_system_id)
    active_count = sum(1 for association in associations if association_is_active(association))
    if active_count >= 8:
        raise RunMountError(
            f"FSx file system {fsx_file_system_id} already has {active_count} active DRAs."
        )
    validate_no_overlaps(
        associations,
        file_system_path=file_system_path,
        source_s3_uri=source_s3_uri,
    )

    params = _create_association_params(
        fsx_file_system_id=fsx_file_system_id,
        file_system_path=file_system_path,
        source_s3_uri=source_s3_uri,
        batch_import_metadata_on_create=request.batch_import_metadata_on_create,
        auto_import_events=auto_import_events,
        auto_export_events=auto_export_events,
        tags=request.tags,
    )
    try:
        response = client.create_data_repository_association(**params)
    except (BotoCoreError, ClientError) as exc:
        raise RunMountError(f"Unable to create FSx data repository association: {exc}") from exc

    association = response.get("Association") or {}
    association_id = str(association.get("AssociationId") or "")
    if not association_id:
        raise RunMountError("FSx did not return a data repository association id.")
    if request.wait:
        association = wait_for_association(
            client,
            association_id,
            target_lifecycles={"AVAILABLE"},
            timeout_seconds=request.timeout_seconds,
        )

    warnings: List[str] = []
    if active_count >= 6:
        warnings.append(
            f"FSx file system {fsx_file_system_id} has {active_count + 1} active DRAs after create."
        )
    record = record_from_association(
        association,
        mount_id=mount_id,
        run_id=run_id,
        platform=platform,
        cluster_name=request.cluster_name,
        region=request.region,
        profile_hint=request.profile,
        read_only=read_only,
        batch_import_metadata_on_create=request.batch_import_metadata_on_create,
        tags=request.tags,
        warnings=warnings,
        local_projection_status=LOCAL_PROJECTION_CREATED,
    )
    write_mount_record(record)
    return record


def list_run_mounts(
    *,
    cluster_name: Optional[str],
    fsx_file_system_id: Optional[str],
    region: str,
    profile: Optional[str],
    fsx_client: Optional[Any] = None,
) -> List[RunMountRecord]:
    """List run mount DRAs for a cluster or FSx file system."""
    _require_region(region)
    if not cluster_name and not fsx_file_system_id:
        raise RunMountError("Provide --cluster or --fsx-file-system-id.")
    client = fsx_client or _build_fsx_client(region=region, profile=profile)
    resolved_fsx_id = fsx_file_system_id or resolve_fsx_file_system_id(client, cluster_name or "")
    local_records = _load_mount_records_by_mount_id(
        region=region,
        cluster_name=cluster_name,
        fsx_file_system_id=resolved_fsx_id,
    )
    records: List[RunMountRecord] = []
    for association in list_data_repository_associations(client, resolved_fsx_id):
        fsx_path = str(association.get("FileSystemPath") or "")
        if not fsx_path.startswith(FSX_RUN_MOUNT_ROOT):
            continue
        mount_id = extract_mount_id(fsx_path)
        local = local_records.get(mount_id)
        records.append(
            record_from_association(
                association,
                mount_id=mount_id,
                run_id=local.run_id if local else mount_id,
                platform=local.platform if local else "OTHER",
                cluster_name=cluster_name if cluster_name is not None else (local.cluster_name if local else None),
                region=region,
                profile_hint=profile if profile is not None else (local.profile_hint if local else None),
                read_only=local.read_only if local else _association_is_read_only(association),
                batch_import_metadata_on_create=(
                    local.batch_import_metadata_on_create if local else True
                ),
                tags=local.tags if local else {},
                local_projection_status=(
                    LOCAL_PROJECTION_PRESENT if local else LOCAL_PROJECTION_MISSING
                ),
            )
        )
    return sorted(records, key=lambda record: (record.mount_id, record.association_id))


def describe_run_mount(
    *,
    mount_id: Optional[str],
    association_id: Optional[str],
    cluster_name: Optional[str],
    fsx_file_system_id: Optional[str],
    region: str,
    profile: Optional[str],
    fsx_client: Optional[Any] = None,
) -> RunMountRecord:
    """Describe one run mount by mount id or FSx association id."""
    _require_region(region)
    if bool(mount_id) == bool(association_id):
        raise RunMountError("Provide exactly one of --mount-id or --association-id.")
    client = fsx_client or _build_fsx_client(region=region, profile=profile)

    if association_id:
        associations = describe_data_repository_associations(
            client,
            association_ids=[association_id],
        )
        if not associations:
            raise RunMountError(f"FSx data repository association not found: {association_id}")
        association = associations[0]
        inferred_mount_id = extract_mount_id(str(association.get("FileSystemPath") or ""))
        local = _find_local_record_by_association_id(region, association_id)
        return record_from_association(
            association,
            mount_id=local.mount_id if local else inferred_mount_id,
            run_id=local.run_id if local else inferred_mount_id,
            platform=local.platform if local else "OTHER",
            cluster_name=cluster_name if cluster_name is not None else (local.cluster_name if local else None),
            region=region,
            profile_hint=profile if profile is not None else (local.profile_hint if local else None),
            read_only=local.read_only if local else _association_is_read_only(association),
            batch_import_metadata_on_create=(
                local.batch_import_metadata_on_create if local else True
            ),
            tags=local.tags if local else {},
            local_projection_status=LOCAL_PROJECTION_PRESENT if local else LOCAL_PROJECTION_MISSING,
        )

    valid_mount_id = validate_mount_id(mount_id or "")
    records = list_run_mounts(
        cluster_name=cluster_name,
        fsx_file_system_id=fsx_file_system_id,
        region=region,
        profile=profile,
        fsx_client=client,
    )
    for record in records:
        if record.mount_id == valid_mount_id:
            return record
    raise RunMountError(f"Run mount not found: {valid_mount_id}")


def delete_run_mount(
    *,
    mount_id: Optional[str],
    association_id: Optional[str],
    cluster_name: Optional[str],
    fsx_file_system_id: Optional[str],
    region: str,
    profile: Optional[str],
    wait: bool,
    timeout_seconds: int,
    fsx_client: Optional[Any] = None,
) -> RunMountRecord:
    """Delete one FSx DRA without deleting S3 objects or FSx cached data."""
    client = fsx_client or _build_fsx_client(region=region, profile=profile)
    existing = describe_run_mount(
        mount_id=mount_id,
        association_id=association_id,
        cluster_name=cluster_name,
        fsx_file_system_id=fsx_file_system_id,
        region=region,
        profile=profile,
        fsx_client=client,
    )
    try:
        response = client.delete_data_repository_association(
            AssociationId=existing.association_id,
            DeleteDataInFileSystem=False,
        )
    except (BotoCoreError, ClientError) as exc:
        raise RunMountError(f"Unable to delete FSx data repository association: {exc}") from exc

    association = response.get("Association") or {}
    if wait:
        association = wait_for_deleted_association(
            client,
            existing.association_id,
            fallback_association=association,
            timeout_seconds=timeout_seconds,
        )
    record = record_from_association(
        association or _association_from_record(existing, lifecycle="DELETED"),
        mount_id=existing.mount_id,
        run_id=existing.run_id,
        platform=existing.platform,
        cluster_name=existing.cluster_name,
        region=existing.region,
        profile_hint=existing.profile_hint,
        read_only=existing.read_only,
        batch_import_metadata_on_create=existing.batch_import_metadata_on_create,
        tags=existing.tags,
        local_projection_status=LOCAL_PROJECTION_PRESENT,
    )
    write_mount_record(record)
    return record


def verify_run_mount(
    *,
    mount_id: Optional[str] = None,
    association_id: Optional[str] = None,
    cluster_name: str,
    fsx_file_system_id: Optional[str],
    region: str,
    profile: Optional[str],
    platform: Optional[str] = None,
    scope: str = "headnode",
    timeout_seconds: int = 300,
    fsx_client: Optional[Any] = None,
    headnode_resolver: Optional[Any] = None,
    shell_runner: Optional[Any] = None,
) -> Dict[str, Any]:
    """Verify a run mount path is usable on the headnode through SSM."""
    if bool(mount_id) == bool(association_id):
        raise RunMountError("Provide exactly one of --mount-id or --association-id.")
    normalized_scope = str(scope or "").strip().lower()
    if normalized_scope != "headnode":
        raise RunMountError("Run mount verification is headnode-only.")
    record = describe_run_mount(
        mount_id=mount_id,
        association_id=association_id,
        cluster_name=cluster_name,
        fsx_file_system_id=fsx_file_system_id,
        region=region,
        profile=profile,
        fsx_client=fsx_client,
    )
    resolver = headnode_resolver or _resolve_headnode_instance_id
    runner = shell_runner or _run_headnode_shell
    target = resolver(cluster_name, region, profile=profile)
    verify_platform = _normalize_platform(platform or record.platform)
    result = runner(
        target.instance_id,
        region,
        _verification_script(record.headnode_path, verify_platform),
        profile=profile,
        timeout=timeout_seconds,
        comment=f"Verify run mount {record.mount_id} on headnode",
    )

    payload = record.to_output_payload()
    payload["verified"] = True
    payload["verification"] = {
        "instance_id": target.instance_id,
        "command_id": result.command_id,
        "stdout": result.stdout,
        "stderr": result.stderr,
        **_parse_verification_stdout(result.stdout),
    }
    return payload


def record_from_association(
    association: Dict[str, Any],
    *,
    mount_id: str,
    run_id: str,
    platform: str,
    cluster_name: Optional[str],
    region: str,
    profile_hint: Optional[str],
    read_only: bool,
    batch_import_metadata_on_create: bool,
    tags: Dict[str, str],
    warnings: Optional[Sequence[str]] = None,
    local_projection_status: str = LOCAL_PROJECTION_UNKNOWN,
) -> RunMountRecord:
    """Build a stable local record from an FSx association payload."""
    file_system_path = normalize_file_system_path(
        str(association.get("FileSystemPath") or ""),
        mount_id=mount_id,
    )
    s3_config = association.get("S3") or {}
    auto_import_events = tuple(
        (s3_config.get("AutoImportPolicy") or {}).get("Events") or ()
    )
    auto_export_events = tuple(
        (s3_config.get("AutoExportPolicy") or {}).get("Events") or ()
    )
    return RunMountRecord(
        mount_id=validate_mount_id(mount_id),
        run_id=validate_mount_id(run_id),
        platform=_normalize_platform(platform),
        cluster_name=cluster_name,
        region=region,
        source_s3_uri=normalize_s3_uri(str(association.get("DataRepositoryPath") or "")),
        fsx_file_system_id=str(association.get("FileSystemId") or ""),
        file_system_path=file_system_path,
        headnode_path=headnode_path_from_file_system_path(file_system_path),
        association_id=str(association.get("AssociationId") or ""),
        lifecycle=str(association.get("Lifecycle") or "UNKNOWN"),
        read_only=bool(read_only and not auto_export_events),
        profile_hint=profile_hint,
        auto_import_events=auto_import_events,
        auto_export_events=auto_export_events,
        batch_import_metadata_on_create=batch_import_metadata_on_create,
        created_at=_format_timestamp(association.get("CreationTime")) or _utc_now(),
        updated_at=_utc_now(),
        created_by=getpass.getuser(),
        tags=dict(tags),
        warnings=tuple(warnings or ()),
        local_projection_status=local_projection_status,
    )


def write_mount_record(record: RunMountRecord) -> Any:
    """Persist a mount record under the DayEC config state directory."""
    path = mount_record_path(
        region=record.region,
        cluster_name=record.cluster_name,
        fsx_file_system_id=record.fsx_file_system_id,
        mount_id=record.mount_id,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(record.to_state_payload(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def mount_record_path(
    *,
    region: str,
    cluster_name: Optional[str],
    fsx_file_system_id: Optional[str],
    mount_id: str,
) -> Any:
    owner = cluster_name or fsx_file_system_id
    if not owner:
        raise RunMountError("cluster_name or fsx_file_system_id is required for mount state.")
    return (
        config_dir()
        / "run_mounts"
        / _state_component(region)
        / _state_component(owner)
        / f"{validate_mount_id(mount_id)}.json"
    )


def resolve_fsx_file_system_id(client: Any, cluster_name: str) -> str:
    """Resolve the FSx file system id tagged for a ParallelCluster cluster."""
    if not cluster_name:
        raise RunMountError("cluster_name is required to resolve an FSx file system.")
    matches: List[str] = []
    try:
        paginator = client.get_paginator("describe_file_systems")
        pages = paginator.paginate()
        for page in pages:
            for filesystem in page.get("FileSystems", []) or []:
                tags = {
                    str(tag.get("Key")): str(tag.get("Value"))
                    for tag in filesystem.get("Tags", []) or []
                    if tag.get("Key")
                }
                if tags.get("parallelcluster:cluster-name") == cluster_name:
                    filesystem_id = str(filesystem.get("FileSystemId") or "")
                    if filesystem_id:
                        matches.append(filesystem_id)
    except Exception as exc:  # noqa: BLE001
        raise RunMountError(f"Unable to describe FSx file systems: {exc}") from exc

    if not matches:
        raise RunMountError(f"No FSx file system found for cluster {cluster_name!r}.")
    if len(matches) > 1:
        raise RunMountError(f"Multiple FSx file systems found for cluster {cluster_name!r}.")
    return matches[0]


def describe_fsx_file_system(client: Any, fsx_file_system_id: str) -> Dict[str, Any]:
    """Describe one FSx filesystem by id and fail hard if AWS cannot prove it exists."""
    if not str(fsx_file_system_id or "").strip():
        raise RunMountError("fsx_file_system_id is required.")
    try:
        response = client.describe_file_systems(FileSystemIds=[fsx_file_system_id])
    except Exception as exc:  # noqa: BLE001
        raise RunMountError(f"Unable to describe FSx file system {fsx_file_system_id}: {exc}") from exc
    filesystems = response.get("FileSystems") or []
    if len(filesystems) != 1:
        raise RunMountError(f"Unable to describe exactly one FSx file system: {fsx_file_system_id}")
    filesystem = filesystems[0]
    if not isinstance(filesystem, dict):
        raise RunMountError(f"Malformed FSx describe response for {fsx_file_system_id}.")
    return filesystem


def validate_dra_compatible_file_system(filesystem: Dict[str, Any]) -> None:
    """Reject FSx filesystems that cannot accept additional DRA mounts."""
    fsx_id = str(filesystem.get("FileSystemId") or "unknown")
    fsx_type = str(filesystem.get("FileSystemType") or "").upper()
    if fsx_type != "LUSTRE":
        raise RunMountError(
            f"FSx file system {fsx_id} is {fsx_type or 'UNKNOWN'}; DRA mounts require Lustre."
        )
    lifecycle = str(filesystem.get("Lifecycle") or "").upper()
    if lifecycle and lifecycle != "AVAILABLE":
        raise RunMountError(
            f"FSx file system {fsx_id} lifecycle is {lifecycle}; DRA mounts require AVAILABLE."
        )
    lustre = filesystem.get("LustreConfiguration") or {}
    if not isinstance(lustre, dict):
        raise RunMountError(f"FSx file system {fsx_id} is missing LustreConfiguration.")
    deployment_type = str(lustre.get("DeploymentType") or "").upper()
    if deployment_type == "SCRATCH_1":
        raise RunMountError(f"FSx file system {fsx_id} uses SCRATCH_1, which does not support DRAs.")
    legacy_repo_config = lustre.get("DataRepositoryConfiguration")
    if legacy_repo_config:
        raise RunMountError(
            f"FSx file system {fsx_id} has legacy LustreConfiguration.DataRepositoryConfiguration; "
            "create a DRA-backed filesystem before adding run mounts."
        )


def list_data_repository_associations(client: Any, fsx_file_system_id: str) -> List[Dict[str, Any]]:
    return describe_data_repository_associations(
        client,
        filters=[{"Name": "file-system-id", "Values": [fsx_file_system_id]}],
    )


def describe_data_repository_associations(
    client: Any,
    *,
    association_ids: Optional[Sequence[str]] = None,
    filters: Optional[Sequence[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    params: Dict[str, Any] = {}
    if association_ids:
        params["AssociationIds"] = list(association_ids)
    if filters:
        params["Filters"] = list(filters)

    associations: List[Dict[str, Any]] = []
    while True:
        try:
            response = client.describe_data_repository_associations(**params)
        except (BotoCoreError, ClientError) as exc:
            raise RunMountError(f"Unable to describe FSx data repository associations: {exc}") from exc
        associations.extend(response.get("Associations", []) or [])
        next_token = response.get("NextToken")
        if not next_token:
            break
        params["NextToken"] = next_token
    return associations


def wait_for_association(
    client: Any,
    association_id: str,
    *,
    target_lifecycles: Sequence[str],
    timeout_seconds: int,
    poll_interval_seconds: int = 15,
) -> Dict[str, Any]:
    deadline = time.time() + timeout_seconds
    target_set = set(target_lifecycles)
    while True:
        associations = describe_data_repository_associations(
            client,
            association_ids=[association_id],
        )
        if not associations:
            raise RunMountError(f"FSx data repository association not found: {association_id}")
        association = associations[0]
        lifecycle = str(association.get("Lifecycle") or "")
        if lifecycle in target_set:
            return association
        if lifecycle in TERMINAL_FAILURE_LIFECYCLES:
            raise RunMountError(
                f"FSx data repository association {association_id} entered {lifecycle}."
            )
        if time.time() >= deadline:
            raise RunMountError(
                f"Timed out waiting for FSx data repository association {association_id}; "
                f"last lifecycle was {lifecycle or 'UNKNOWN'}."
            )
        time.sleep(max(poll_interval_seconds, 1))


def wait_for_deleted_association(
    client: Any,
    association_id: str,
    *,
    fallback_association: Dict[str, Any],
    timeout_seconds: int,
    poll_interval_seconds: int = 15,
) -> Dict[str, Any]:
    deadline = time.time() + timeout_seconds
    while True:
        try:
            associations = describe_data_repository_associations(
                client,
                association_ids=[association_id],
            )
        except RunMountError as exc:
            if _looks_not_found(exc):
                result = dict(fallback_association)
                result["Lifecycle"] = "DELETED"
                return result
            raise
        if not associations:
            result = dict(fallback_association)
            result["Lifecycle"] = "DELETED"
            return result
        association = associations[0]
        lifecycle = str(association.get("Lifecycle") or "")
        if lifecycle == "DELETED":
            return association
        if time.time() >= deadline:
            raise RunMountError(
                f"Timed out waiting for FSx data repository association {association_id} delete; "
                f"last lifecycle was {lifecycle or 'UNKNOWN'}."
            )
        time.sleep(max(poll_interval_seconds, 1))


def association_is_active(association: Dict[str, Any]) -> bool:
    lifecycle = str(association.get("Lifecycle") or "").upper()
    return lifecycle not in INACTIVE_LIFECYCLES


def extract_mount_id(file_system_path: str) -> str:
    normalized = normalize_file_system_path(file_system_path, mount_id="_validated")
    if not normalized.startswith(FSX_RUN_MOUNT_ROOT):
        raise RunMountError(f"File-system path is not a run mount path: {file_system_path}")
    suffix = normalized[len(FSX_RUN_MOUNT_ROOT) :].strip("/")
    first = suffix.split("/", 1)[0]
    return validate_mount_id(first)


def format_mount_created(record: RunMountRecord) -> str:
    return "\n".join(
        [
            f"Run directory mounted: {record.mount_id}",
            f"Association ID: {record.association_id}",
            f"FSx file system: {record.fsx_file_system_id}",
            f"FSx API path: {record.file_system_path}",
            f"Headnode path: {record.headnode_path}",
            f"Source S3 URI: {record.source_s3_uri}",
            f"Lifecycle: {record.lifecycle}",
        ]
    )


def format_mount_deleted(record: RunMountRecord) -> str:
    return "\n".join(
        [
            f"Run directory mount deleted: {record.mount_id}",
            f"Association ID: {record.association_id}",
            f"FSx file system: {record.fsx_file_system_id}",
            f"Lifecycle: {record.lifecycle}",
        ]
    )


def format_mount_described(record: RunMountRecord) -> str:
    return json.dumps(record.to_output_payload(), indent=2, sort_keys=False)


def format_mount_list(records: Sequence[RunMountRecord]) -> str:
    if not records:
        return "No run directory mounts found."
    lines = [
        "%-32s %-32s %-8s %-16s %-18s %-38s %-36s %-20s"
        % (
            "MOUNT_ID",
            "RUN_ID",
            "PLATFORM",
            "LIFECYCLE",
            "ASSOCIATION_ID",
            "HEADNODE_PATH",
            "SOURCE_S3_URI",
            "CREATED_AT",
        ),
        "%s %s %s %s %s %s %s %s"
        % (
            "-" * 32,
            "-" * 32,
            "-" * 8,
            "-" * 16,
            "-" * 18,
            "-" * 38,
            "-" * 36,
            "-" * 20,
        ),
    ]
    for record in records:
        lines.append(
            "%-32s %-32s %-8s %-16s %-18s %-38s %-36s %-20s"
            % (
                record.mount_id,
                record.run_id,
                record.platform,
                record.lifecycle,
                record.association_id,
                record.headnode_path,
                record.source_s3_uri,
                record.created_at,
            )
        )
    return "\n".join(lines)


def format_mount_verified(payload: Dict[str, Any]) -> str:
    return "\n".join(
        [
            f"Run directory mount verified: {payload['mount_id']}",
            f"Association ID: {payload['association_id']}",
            f"Headnode path: {payload['headnode_path']}",
            f"Lifecycle: {payload['lifecycle']}",
        ]
    )


def _parse_event_tokens(raw: str, *, default: Sequence[str]) -> List[str]:
    text = raw.strip()
    if not text:
        return list(default)
    lowered = text.lower()
    if lowered in {"none", "false", "off"}:
        return []
    if lowered == "all":
        return list(ALL_AUTO_IMPORT_EVENTS)
    result: List[str] = []
    aliases = {"new": "NEW", "changed": "CHANGED", "deleted": "DELETED"}
    for token in re.split(r"[, ]+", text):
        if not token:
            continue
        normalized = aliases.get(token.lower(), token.upper())
        if normalized not in ALL_AUTO_IMPORT_EVENTS:
            raise RunMountError(f"Unsupported FSx S3 event type: {token!r}.")
        if normalized not in result:
            result.append(normalized)
    return result


def _create_association_params(
    *,
    fsx_file_system_id: str,
    file_system_path: str,
    source_s3_uri: str,
    batch_import_metadata_on_create: bool,
    auto_import_events: Sequence[str],
    auto_export_events: Sequence[str],
    tags: Dict[str, str],
) -> Dict[str, Any]:
    params: Dict[str, Any] = {
        "FileSystemId": fsx_file_system_id,
        "FileSystemPath": file_system_path,
        "DataRepositoryPath": source_s3_uri,
        "BatchImportMetaDataOnCreate": batch_import_metadata_on_create,
        "Tags": [{"Key": key, "Value": value} for key, value in sorted(tags.items())],
    }
    s3_policy: Dict[str, Any] = {}
    if auto_import_events:
        s3_policy["AutoImportPolicy"] = {"Events": list(auto_import_events)}
    if auto_export_events:
        s3_policy["AutoExportPolicy"] = {"Events": list(auto_export_events)}
    if s3_policy:
        params["S3"] = s3_policy
    return params


def _association_is_read_only(association: Dict[str, Any]) -> bool:
    s3_config = association.get("S3") or {}
    export_events = (s3_config.get("AutoExportPolicy") or {}).get("Events") or []
    return not bool(export_events)


def _association_from_record(record: RunMountRecord, *, lifecycle: str) -> Dict[str, Any]:
    return {
        "AssociationId": record.association_id,
        "FileSystemId": record.fsx_file_system_id,
        "FileSystemPath": record.file_system_path,
        "DataRepositoryPath": record.source_s3_uri,
        "Lifecycle": lifecycle,
        "CreationTime": record.created_at,
        "S3": {
            "AutoImportPolicy": {"Events": list(record.auto_import_events)},
            **(
                {"AutoExportPolicy": {"Events": list(record.auto_export_events)}}
                if record.auto_export_events
                else {}
            ),
        },
    }


def _build_fsx_client(*, region: str, profile: Optional[str]) -> Any:
    session_kwargs: Dict[str, str] = {"region_name": region}
    if profile:
        session_kwargs["profile_name"] = profile
    return boto3.Session(**session_kwargs).client("fsx")


def _with_trailing_slash(value: str) -> str:
    raw = str(value or "").strip()
    if raw.startswith("s3://"):
        return normalize_s3_uri(raw)
    if not raw:
        raise RunMountError("Path must not be empty.")
    return raw.rstrip("/") + "/"


def _normalize_platform(platform: Optional[str]) -> str:
    value = str(platform or "OTHER").strip().upper()
    allowed = {"ILMN", "ONT", "ULTIMA", "PACBIO", "OTHER"}
    if value not in allowed:
        raise RunMountError(
            f"Unsupported platform {platform!r}; expected one of {', '.join(sorted(allowed))}."
        )
    return value


def _require_region(region: str) -> None:
    if not str(region or "").strip():
        raise RunMountError("region is required.")


def _state_component(value: str) -> str:
    component = str(value or "").strip()
    if not component or not re.fullmatch(r"[A-Za-z0-9._:-]+", component):
        raise RunMountError(f"Unsafe state path component: {value!r}.")
    return component


def _load_mount_records_by_mount_id(
    *,
    region: str,
    cluster_name: Optional[str],
    fsx_file_system_id: Optional[str],
) -> Dict[str, RunMountRecord]:
    owner = cluster_name or fsx_file_system_id
    if not owner:
        return {}
    directory = config_dir() / "run_mounts" / _state_component(region) / _state_component(owner)
    records: Dict[str, RunMountRecord] = {}
    if not directory.exists():
        return records
    for path in sorted(directory.glob("*.json")):
        try:
            record = _record_from_state_payload(json.loads(path.read_text(encoding="utf-8")))
        except Exception:
            continue
        records[record.mount_id] = record
    return records


def _load_mount_record(
    *,
    region: str,
    cluster_name: Optional[str],
    fsx_file_system_id: Optional[str],
    mount_id: str,
) -> Optional[RunMountRecord]:
    try:
        path = mount_record_path(
            region=region,
            cluster_name=cluster_name,
            fsx_file_system_id=fsx_file_system_id,
            mount_id=mount_id,
        )
    except RunMountError:
        return None
    if not path.is_file():
        return None
    return _record_from_state_payload(json.loads(path.read_text(encoding="utf-8")))


def _find_local_record_by_association_id(region: str, association_id: str) -> Optional[RunMountRecord]:
    root = config_dir() / "run_mounts" / _state_component(region)
    if not root.exists():
        return None
    for path in sorted(root.glob("*/*.json")):
        try:
            record = _record_from_state_payload(json.loads(path.read_text(encoding="utf-8")))
        except Exception:
            continue
        if record.association_id == association_id:
            return record
    return None


def _record_from_state_payload(payload: Dict[str, Any]) -> RunMountRecord:
    if int(payload.get("schema_version") or 0) != STATE_SCHEMA_VERSION:
        raise RunMountError("Unsupported run mount state schema version.")
    return RunMountRecord(
        mount_id=str(payload["mount_id"]),
        run_id=str(payload["run_id"]),
        platform=str(payload.get("platform") or "OTHER"),
        cluster_name=payload.get("cluster_name"),
        region=str(payload["region"]),
        source_s3_uri=str(payload.get("source_s3_uri") or payload["data_repository_path"]),
        fsx_file_system_id=str(payload["fsx_file_system_id"]),
        file_system_path=str(payload["file_system_path"]),
        headnode_path=str(payload["headnode_path"]),
        association_id=str(payload["association_id"]),
        lifecycle=str(payload["lifecycle"]),
        read_only=bool(payload["read_only"]),
        profile_hint=payload.get("profile_hint"),
        auto_import_events=tuple(payload.get("auto_import_events") or ()),
        auto_export_events=tuple(payload.get("auto_export_events") or ()),
        batch_import_metadata_on_create=bool(
            payload.get("batch_import_metadata_on_create", True)
        ),
        created_at=str(payload.get("created_at") or ""),
        updated_at=str(payload.get("updated_at") or ""),
        created_by=str(payload.get("created_by") or ""),
        tags=dict(payload.get("tags") or {}),
        warnings=tuple(payload.get("warnings") or ()),
        local_projection_status=str(
            payload.get("local_projection_status") or LOCAL_PROJECTION_PRESENT
        ),
    )


def _format_timestamp(value: Any) -> str:
    if not value:
        return ""
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace(
            "+00:00",
            "Z",
        )
    return str(value)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _looks_not_found(exc: BaseException) -> bool:
    return "not found" in str(exc).lower() or "notfound" in str(exc).lower()


def _resolve_headnode_instance_id(cluster_name: str, region: str, *, profile: Optional[str]):
    from daylily_ec.aws.ssm import resolve_headnode_instance_id

    return resolve_headnode_instance_id(cluster_name, region, profile=profile)


def _run_headnode_shell(
    instance_id: str,
    region: str,
    script: str,
    *,
    profile: Optional[str],
    timeout: int,
    comment: str,
):
    from daylily_ec.aws.ssm import run_shell

    return run_shell(
        instance_id,
        region,
        script,
        profile=profile,
        timeout=timeout,
        comment=comment,
    )


def _verification_script(headnode_path: str, platform: str) -> str:
    path = shlex.quote(headnode_path)
    _ = platform
    python_code = "\n".join(
        [
            "import json, os, pathlib",
            "root = pathlib.Path(os.environ['DAYLILY_VERIFY_ROOT'])",
            "print(json.dumps({'path': str(root), 'usable': True}, sort_keys=True))",
        ]
    )
    return "\n".join(
        [
            "set -euo pipefail",
            f"root={path}",
            'case "$root" in /fsx|/fsx/*) ;; *) echo "Verify path is not under /fsx: $root" >&2; exit 1 ;; esac',
            'if [ ! -d "$root" ]; then echo "Verify path is not a directory: $root" >&2; exit 1; fi',
            'if [ ! -r "$root" ] || [ ! -x "$root" ]; then echo "Verify path is not readable/executable: $root" >&2; exit 1; fi',
            'cd "$root"',
            'ls -A . >/dev/null',
            f"export DAYLILY_VERIFY_ROOT={path}",
            f"python3 -c {shlex.quote(python_code)}",
        ]
    )


def _parse_verification_stdout(stdout: str) -> Dict[str, Any]:
    for line in stdout.splitlines():
        stripped = line.strip()
        if not stripped.startswith("{"):
            continue
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return {
                "path": str(payload.get("path") or ""),
                "usable": bool(payload.get("usable")),
            }
    return {"path": "", "usable": False}
