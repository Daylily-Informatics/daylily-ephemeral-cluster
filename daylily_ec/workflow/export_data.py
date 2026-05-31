"""Direct analysis-directory FSx DRA export workflow."""

from __future__ import annotations

import dataclasses
import base64
import fnmatch
import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import PurePosixPath, Path
from typing import Any, Callable, Dict, Optional
from urllib.parse import urlparse

import boto3
from botocore.exceptions import BotoCoreError, ClientError
import yaml

from daylily_ec.analysis_identity import validate_analysis_segment
from daylily_ec.repositories import ArtifactRegistrationPolicy
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
    wait: bool = True
    timeout_seconds: int = 3600
    artifact_registration_policy: Optional[ArtifactRegistrationPolicy] = None
    artifact_registration_genome: str = ""
    dewey_url: str = ""
    dewey_token_env: str = ""
    dewey_analysis_dir_external_object_id: str = ""
    dewey_run_artifact_euid: str = ""
    dewey_ursa_analysis_euid: str = ""
    artifact_registration_command_id: str = ""


@dataclasses.dataclass
class RegisterExistingExportOptions:
    source_path: str
    destination_s3_uri: str
    region: str
    profile: Optional[str]
    output_dir: Path
    artifact_registration_policy: ArtifactRegistrationPolicy
    artifact_registration_genome: str
    artifact_registration_manifest_source: str
    artifact_registration_command_id: str
    dewey_url: str
    dewey_token_env: str
    dewey_analysis_dir_external_object_id: str = ""
    dewey_run_artifact_euid: str = ""
    dewey_ursa_analysis_euid: str = ""


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
    parts = PurePosixPath(raw).parts
    if ".." in parts:
        raise ExportError("source_path must not contain '..'.")
    normalized = "/" + "/".join(part for part in parts if part != "/")
    if not normalized.startswith(ANALYSIS_EXPORT_ROOT):
        raise ExportError(
            "source_path must be under /analysis_results/<executing_entity>/<analysis_id>."
        )
    suffix = normalized[len(ANALYSIS_EXPORT_ROOT) :].strip("/")
    _safe_analysis_dir(suffix)
    return normalized.rstrip("/") + "/"


def validate_export_destination_s3_uri(destination_s3_uri: str, *, source_path: str) -> str:
    destination = normalize_s3_uri(destination_s3_uri)
    parsed = urlparse(destination)
    key = parsed.path.lstrip("/")
    analysis_dir = analysis_dir_from_source_path(source_path)
    expected_key = f"{analysis_dir}/"
    if not key.endswith(expected_key):
        raise ExportError(
            "destination_s3_uri must end with "
            f"{expected_key!r}; got s3://{parsed.netloc}/{key}"
        )
    return destination


def validate_s3_destination_prefix_empty(
    client: Any,
    destination_s3_uri: str,
    *,
    source_path: str,
) -> str:
    """Validate the destination suffix and fail if the S3 prefix already has objects."""
    destination = validate_export_destination_s3_uri(
        destination_s3_uri,
        source_path=source_path,
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
    allow_absent: bool = False,
) -> Dict[str, Any]:
    client = fsx_client or _create_session(region, profile).client("fsx")
    try:
        response = client.delete_data_repository_association(
            AssociationId=association_id,
            DeleteDataInFileSystem=False,
        )
    except ClientError as exc:
        if allow_absent and _is_association_not_found(exc):
            return {
                "association_id": association_id,
                "detach_lifecycle": "NOT_FOUND",
                "detach_absent": True,
                "delete_data_in_file_system": False,
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
        "delete_data_in_file_system": False,
    }


def _is_association_not_found(exc: ClientError) -> bool:
    code = str((exc.response.get("Error") or {}).get("Code") or "")
    return code == "DataRepositoryAssociationNotFound"


def _write_status(options: ExportOptions, payload: Dict[str, Any]) -> None:
    options.output_dir.mkdir(parents=True, exist_ok=True)
    status_path = options.output_dir / STATUS_FILENAME
    status_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    LOGGER.info("Wrote export status to %s", status_path)


def _read_s3_json(client: Any, uri: str) -> Dict[str, Any]:
    parsed = urlparse(uri)
    if parsed.scheme != "s3" or not parsed.netloc:
        raise ExportError(f"S3 JSON URI must use s3://, got: {uri}")
    try:
        response = client.get_object(Bucket=parsed.netloc, Key=parsed.path.lstrip("/"))
        body = response["Body"].read().decode("utf-8")
    except (BotoCoreError, ClientError, KeyError, OSError) as exc:
        raise ExportError(f"Unable to read exported JSON manifest {uri}: {exc}") from exc
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise ExportError(f"Exported JSON manifest is malformed: {uri}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ExportError(f"Exported JSON manifest must be an object: {uri}")
    return payload


def _s3_parts(uri: str) -> tuple[str, str]:
    parsed = urlparse(uri)
    if parsed.scheme != "s3" or not parsed.netloc:
        raise ExportError(f"S3 URI must use s3://, got: {uri}")
    return parsed.netloc, parsed.path.lstrip("/")


def _iter_s3_objects(client: Any, *, bucket: str, prefix: str) -> list[dict[str, Any]]:
    objects: list[dict[str, Any]] = []
    continuation_token = ""
    while True:
        params: dict[str, Any] = {"Bucket": bucket, "Prefix": prefix}
        if continuation_token:
            params["ContinuationToken"] = continuation_token
        try:
            response = client.list_objects_v2(**params)
        except (BotoCoreError, ClientError) as exc:
            raise ExportError(f"Unable to list S3 prefix s3://{bucket}/{prefix}: {exc}") from exc
        objects.extend(response.get("Contents") or [])
        if not response.get("IsTruncated"):
            break
        continuation_token = str(response.get("NextContinuationToken") or "")
        if not continuation_token:
            raise ExportError(f"S3 listing for s3://{bucket}/{prefix} was truncated without a token")
    if not objects:
        raise ExportError(f"S3 prefix has no objects: s3://{bucket}/{prefix}")
    return objects


def _sha256_from_head_object(head: dict[str, Any], *, uri: str) -> str:
    metadata = head.get("Metadata") or {}
    for key in ("sha256", "file-sha256", "checksum-sha256"):
        value = str(metadata.get(key) or "").strip().lower()
        if len(value) == 64 and all(char in "0123456789abcdef" for char in value):
            return value
    checksum = str(head.get("ChecksumSHA256") or "").strip()
    if checksum:
        try:
            value = base64.b64decode(checksum).hex()
        except (ValueError, TypeError) as exc:
            raise ExportError(f"S3 object has malformed ChecksumSHA256: {uri}") from exc
        if len(value) == 64:
            return value
    raise ExportError(f"S3 object is missing SHA-256 metadata required by Dewey: {uri}")


def _classify_exported_artifact(relative_path: str) -> str:
    rel = str(relative_path)
    if rel == "config/samples.tsv":
        return "samples_manifest"
    if rel == "config/units.tsv":
        return "units_manifest"
    if not rel.startswith("results/"):
        return ""
    name = PurePosixPath(rel).name
    lower = rel.lower()
    if name in {"DAY_final_multiqc.html", "multiqc_report.html"}:
        return "multiqc_html"
    if "/day_final_multiqc_data/" in lower or "/multiqc_report_data/" in lower:
        if name == "multiqc_data.json":
            return "multiqc_data_json"
        if name == "multiqc_general_stats.txt":
            return "multiqc_general_stats"
        if name == "multiqc_sources.txt":
            return "multiqc_sources"
        if name == "multiqc.log":
            return "multiqc_log"
        return "multiqc_data_file"
    if lower.endswith("/manifest.tsv") and "/multiqc_inputs/" in lower:
        return "staging_manifest"
    if lower.endswith("_mqc.tsv"):
        return "custom_mqc_tsv"
    if "benchmark" in lower and lower.endswith((".txt", ".tsv", ".json")):
        return "benchmark"
    if lower.endswith(".cram"):
        return "alignment_cram"
    if lower.endswith((".cram.crai", ".crai")):
        return "alignment_cram_index"
    if lower.endswith(".bam"):
        return "alignment_bam"
    if lower.endswith((".bam.bai", ".bai")):
        return "alignment_bam_index"
    if lower.endswith(".bam.csi"):
        return "alignment_bam_index"
    if lower.endswith((".vcf", ".vcf.gz")):
        return "variant_vcf"
    if lower.endswith((".vcf.tbi", ".vcf.gz.tbi", ".tbi", ".vcf.csi", ".vcf.gz.csi")):
        return "variant_vcf_index"
    if lower.endswith(".csi"):
        return "variant_vcf_index"
    return ""


def _parser_relevant(classification: str, relative_path: str) -> bool:
    if classification in {
        "multiqc_data_json",
        "multiqc_general_stats",
        "multiqc_sources",
        "multiqc_log",
        "staging_manifest",
        "custom_mqc_tsv",
    }:
        return True
    if classification == "multiqc_data_file" and relative_path.lower().endswith(
        (".json", ".tsv", ".txt", ".log")
    ):
        return True
    return False


def _selected_by_policy(
    *,
    relative_path: str,
    classification: str,
    policy: ArtifactRegistrationPolicy,
    genome: str,
    analysis_id: str,
    executing_entity: str,
) -> bool:
    from daylily_ec.workflow.dewey_registration import template_value

    if classification and classification in policy.include_classifications:
        return True
    patterns = [
        template_value(
            path,
            analysis_id=analysis_id,
            executing_entity=executing_entity,
            genome=genome,
        )
        for path in policy.include_paths
    ]
    return any(fnmatch.fnmatch(relative_path, pattern) for pattern in patterns)


def _build_s3_inventory_manifest(
    *,
    client: Any,
    export_receipt: Dict[str, Any],
    policy: ArtifactRegistrationPolicy,
    genome: str,
    command_id: str,
) -> Dict[str, Any]:
    from daylily_ec.workflow.dewey_registration import canonical_sha256, dayoa_s3_root

    executing_entity, analysis_id = _safe_analysis_dir(export_receipt["analysis_dir"]).split("/")
    root = dayoa_s3_root(export_receipt)
    bucket, prefix = _s3_parts(root)
    objects = _iter_s3_objects(client, bucket=bucket, prefix=prefix)
    files: list[dict[str, Any]] = []
    for obj in objects:
        key = str(obj.get("Key") or "")
        if not key or key.endswith("/") or not key.startswith(prefix):
            continue
        relative_path = key[len(prefix) :]
        if not relative_path:
            continue
        classification = _classify_exported_artifact(relative_path)
        if not _selected_by_policy(
            relative_path=relative_path,
            classification=classification,
            policy=policy,
            genome=genome,
            analysis_id=analysis_id,
            executing_entity=executing_entity,
        ):
            continue
        if not classification:
            classification = "registered_file"
        uri = f"s3://{bucket}/{key}"
        try:
            head = client.head_object(Bucket=bucket, Key=key)
        except (BotoCoreError, ClientError) as exc:
            raise ExportError(f"Unable to inspect S3 object {uri}: {exc}") from exc
        sha256 = _sha256_from_head_object(head, uri=uri)
        files.append(
            {
                "relative_path": relative_path,
                "size_bytes": int(head.get("ContentLength") or obj.get("Size") or 0),
                "sha256": sha256,
                "classification": classification,
                "parser_relevant": _parser_relevant(classification, relative_path),
                "required": True,
                "metadata": {
                    "evidence_source": "dyec_s3_export_inventory",
                    "s3_uri": uri,
                    "s3_etag": str(head.get("ETag") or obj.get("ETag") or "").strip('"'),
                    "analysis_id": analysis_id,
                    "executing_entity": executing_entity,
                    "genome_build": genome,
                    "command_id": command_id,
                    "result_scope": "runs" if relative_path.startswith("results/runs/") else "day",
                },
            }
        )
    manifest = {
        "schema_version": "dyec.s3_export_inventory_manifest.v1",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
            "+00:00", "Z"
        ),
        "analysis": {"genome_build": genome},
        "workflow": {
            "pipeline_name": "daylily-omics-analysis",
            "pipeline_version": "",
            "git_sha": "",
            "snakemake_version": "",
            "workflow_config_hash": canonical_sha256(
                {
                    "source": "dyec_s3_export_inventory",
                    "root": root,
                    "command_id": command_id,
                    "genome": genome,
                }
            ),
            "workflow_profile": "exported-s3-inventory",
        },
        "files": sorted(files, key=lambda record: record["relative_path"]),
    }
    if not manifest["files"]:
        raise ExportError("S3 inventory selected zero files for Dewey registration")
    manifest["manifest_checksum"] = canonical_sha256(manifest["files"])
    return manifest


def _run_dewey_registration(
    *,
    options: ExportOptions,
    receipt: Dict[str, Any],
    s3_client: Any,
    manifest_source: str | None = None,
) -> Dict[str, Any]:
    from daylily_ec.workflow.dewey_registration import (
        build_registration_requests,
        dayoa_s3_root,
        register_exported_analysis_directory_links,
        register_with_dewey,
        template_value,
    )

    policy = options.artifact_registration_policy
    if policy is None:
        raise ExportError("artifact_registration_policy is required")
    if not options.artifact_registration_genome.strip():
        raise ExportError("artifact_registration_genome is required")
    if not options.dewey_url.strip():
        raise ExportError("dewey_url is required for artifact registration")
    if not options.dewey_token_env.strip():
        raise ExportError("dewey_token_env is required for artifact registration")
    token = os.environ.get(options.dewey_token_env, "")
    if not token:
        raise ExportError(f"Dewey token environment variable is not set: {options.dewey_token_env}")
    fsx_export = receipt["fsx_export"]
    resolved_manifest_source = str(manifest_source or policy.manifest_source).strip()
    if resolved_manifest_source == "dayoa_manifest":
        executing_entity, analysis_id = fsx_export["analysis_dir"].split("/", 1)
        manifest_rel = template_value(
            policy.evidence_manifest_path,
            analysis_id=analysis_id,
            executing_entity=executing_entity,
            genome=options.artifact_registration_genome,
        )
        manifest_s3_uri = dayoa_s3_root(fsx_export).rstrip("/") + "/" + manifest_rel
        manifest = _read_s3_json(s3_client, manifest_s3_uri)
    elif resolved_manifest_source == "s3_inventory":
        manifest_s3_uri = "dyec:s3_inventory"
        manifest = _build_s3_inventory_manifest(
            client=s3_client,
            export_receipt=fsx_export,
            policy=policy,
            genome=options.artifact_registration_genome,
            command_id=options.artifact_registration_command_id,
        )
    else:
        raise ExportError(
            "artifact_registration manifest source must be dayoa_manifest or s3_inventory"
        )
    requests = build_registration_requests(
        manifest=manifest,
        export_receipt=fsx_export,
        policy=policy,
    )
    dewey_receipt = register_with_dewey(
        dewey_url=options.dewey_url,
        token=token,
        requests=requests,
    )
    if options.dewey_analysis_dir_external_object_id.strip():
        dewey_receipt["analysis_directory_links"] = register_exported_analysis_directory_links(
            dewey_url=options.dewey_url,
            token=token,
            export_receipt=fsx_export,
            dewey_receipt=dewey_receipt,
            external_object_id=options.dewey_analysis_dir_external_object_id,
            run_artifact_euid=options.dewey_run_artifact_euid,
            ursa_analysis_euid=options.dewey_ursa_analysis_euid,
        )
    dewey_receipt["source_manifest_s3_uri"] = manifest_s3_uri
    dewey_receipt["source_manifest_mode"] = resolved_manifest_source
    dewey_receipt["selected_artifact_count"] = len(requests["analysis"]["artifacts"])
    dewey_receipt["multiqc_artifact_set_count"] = len(requests["multiqc"])
    receipt_path = options.output_dir / "dewey_registration_receipt.json"
    receipt_path.write_text(
        json.dumps(dewey_receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {
        "dewey_registration_status": "success",
        "dewey_registration_receipt": str(receipt_path),
        "dewey_source_manifest_s3_uri": manifest_s3_uri,
        "dewey_source_manifest_mode": resolved_manifest_source,
        "dewey_selected_artifact_count": dewey_receipt["selected_artifact_count"],
        "dewey_multiqc_artifact_set_count": dewey_receipt["multiqc_artifact_set_count"],
        "dewey_analysis_directory_link_status": (
            "success" if "analysis_directory_links" in dewey_receipt else "not_requested"
        ),
    }


def _base_receipt(options: ExportOptions) -> Dict[str, Any]:
    normalized_source = normalize_export_source_path(options.source_path)
    destination_s3_uri = validate_export_destination_s3_uri(
        options.destination_s3_uri,
        source_path=normalized_source,
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
            "delete_data_in_file_system": False,
            "failure_details": {},
        }
    }


def run_dewey_registration_for_existing_export(options: RegisterExistingExportOptions) -> int:
    """Register an already-exported analysis directory with Dewey without DRA side effects."""

    ui.phase("DEWEY REGISTRATION")
    ui.step("Preparing existing exported analysis directory registration")
    export_options = ExportOptions(
        cluster_name=None,
        fsx_file_system_id=None,
        source_path=options.source_path,
        destination_s3_uri=options.destination_s3_uri,
        region=options.region,
        profile=options.profile,
        output_dir=options.output_dir,
        wait=True,
        timeout_seconds=0,
        artifact_registration_policy=options.artifact_registration_policy,
        artifact_registration_genome=options.artifact_registration_genome,
        dewey_url=options.dewey_url,
        dewey_token_env=options.dewey_token_env,
        dewey_analysis_dir_external_object_id=options.dewey_analysis_dir_external_object_id,
        dewey_run_artifact_euid=options.dewey_run_artifact_euid,
        dewey_ursa_analysis_euid=options.dewey_ursa_analysis_euid,
        artifact_registration_command_id=options.artifact_registration_command_id,
    )
    try:
        receipt = _base_receipt(export_options)
    except (RuntimeError, RunMountError, ExportError) as exc:
        receipt = {
            "fsx_export": {
                "schema_version": EXPORT_SCHEMA_VERSION,
                "status": "error",
                "phase": "validate",
                "region": options.region,
                "source_path": options.source_path,
                "destination_s3_uri": options.destination_s3_uri,
                "registration_only": True,
                "delete_data_in_file_system": False,
                "failure_details": {"message": str(exc)},
            }
        }
        _write_status(export_options, receipt)
        ui.error_panel("Dewey registration failed", str(exc))
        return 1

    receipt["fsx_export"].update(
        {
            "status": "success",
            "phase": "dewey_registration",
            "registration_only": True,
            "detached": True,
            "delete_data_in_file_system": False,
        }
    )
    try:
        if options.artifact_registration_manifest_source not in {"dayoa_manifest", "s3_inventory"}:
            raise ExportError(
                "artifact_registration_manifest_source must be dayoa_manifest or s3_inventory"
            )
        s3_client = _create_session(options.region, options.profile).client("s3")
        receipt["fsx_export"].update(
            _run_dewey_registration(
                options=export_options,
                receipt=receipt,
                s3_client=s3_client,
                manifest_source=options.artifact_registration_manifest_source,
            )
        )
        receipt["fsx_export"]["phase"] = "complete"
        _write_status(export_options, receipt)
        ui.success_panel(
            "Dewey registration complete",
            f"Source: {receipt['fsx_export']['source_path']}\n"
            f"S3: {receipt['fsx_export']['destination_s3_uri']}\n"
            f"Status file: {options.output_dir / STATUS_FILENAME}",
        )
        return 0
    except (RuntimeError, ExportError, BotoCoreError, ClientError) as exc:
        receipt["fsx_export"]["status"] = "error"
        receipt["fsx_export"]["phase"] = "dewey_registration"
        receipt["fsx_export"]["dewey_registration_status"] = "error"
        receipt["fsx_export"]["failure_details"] = {"message": str(exc)}
        _write_status(export_options, receipt)
        ui.error_panel("Dewey registration failed", str(exc))
        return 1


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
    s3_client = session.client("s3")
    record: Optional[ExportDraRecord] = None
    task_payload: Dict[str, Any] = {}
    detach_payload: Dict[str, Any] = {}
    rc = 1
    message = ""

    try:
        receipt["fsx_export"]["phase"] = "preflight"
        validate_s3_destination_prefix_empty(
            s3_client,
            options.destination_s3_uri,
            source_path=options.source_path,
        )
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
                    allow_absent=True,
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
            if options.artifact_registration_policy is not None:
                receipt["fsx_export"]["phase"] = "dewey_registration"
                try:
                    receipt["fsx_export"].update(
                        _run_dewey_registration(
                            options=options,
                            receipt=receipt,
                            s3_client=s3_client,
                        )
                    )
                except (RuntimeError, ExportError, BotoCoreError, ClientError) as exc:
                    rc = 1
                    message = str(exc)
                    receipt["fsx_export"]["status"] = "error"
                    receipt["fsx_export"]["dewey_registration_status"] = "error"
                    receipt["fsx_export"]["failure_details"] = {"message": message}
            if rc == 0:
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
