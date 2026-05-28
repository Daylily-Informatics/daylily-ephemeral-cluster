"""DYEC-side Dewey registration from exported DayOA evidence manifests."""

from __future__ import annotations

import fnmatch
import hashlib
import json
import mimetypes
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import PurePosixPath
from typing import Any

import yaml

from daylily_ec.repositories import ArtifactRegistrationPolicy


ANALYSIS_REGISTER_ENDPOINT = "/api/v1/artifact-sets/analysis/register"
MULTIQC_REGISTER_ENDPOINT = "/api/v1/artifact-sets/multiqc/register"


class DeweyRegistrationError(RuntimeError):
    """Raised when DYEC cannot register exported DayOA evidence."""


def canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
        "utf-8"
    )


def canonical_sha256(payload: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


def manifest_sha256_for_request(request: dict[str, Any]) -> str:
    material = dict(request)
    material.pop("manifest_sha256", None)
    return canonical_sha256(material)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: str) -> dict[str, Any]:
    try:
        payload = json.loads(open(path, encoding="utf-8").read())
    except json.JSONDecodeError as exc:
        raise DeweyRegistrationError(f"JSON document is malformed: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise DeweyRegistrationError(f"JSON document must be an object: {path}")
    return payload


def load_export_receipt(path: str) -> dict[str, Any]:
    payload = yaml.safe_load(open(path, encoding="utf-8").read())
    if not isinstance(payload, dict) or not isinstance(payload.get("fsx_export"), dict):
        raise DeweyRegistrationError(f"Export receipt is missing fsx_export object: {path}")
    return payload["fsx_export"]


def validate_relative_path(relative_path: str) -> str:
    cleaned = str(relative_path or "").strip()
    if not cleaned:
        raise DeweyRegistrationError("Artifact relative_path is required")
    if cleaned.startswith("/"):
        raise DeweyRegistrationError(f"Artifact relative_path must be relative: {cleaned}")
    if ".." in PurePosixPath(cleaned).parts:
        raise DeweyRegistrationError(f"Artifact relative_path must not contain '..': {cleaned}")
    return cleaned


def s3_join(root: str, relative_path: str) -> str:
    cleaned_root = str(root or "").strip()
    if not cleaned_root.startswith("s3://"):
        raise DeweyRegistrationError(f"S3 root must use s3://, got: {cleaned_root}")
    rel_path = validate_relative_path(relative_path)
    return cleaned_root.rstrip("/") + "/" + rel_path


def template_value(template: str, *, analysis_id: str, executing_entity: str, genome: str) -> str:
    return (
        str(template)
        .replace("{analysis_id}", analysis_id)
        .replace("{executing_entity}", executing_entity)
        .replace("{genome}", genome)
    )


def analysis_parts_from_receipt(export_receipt: dict[str, Any]) -> tuple[str, str]:
    analysis_dir = str(export_receipt.get("analysis_dir") or "").strip("/")
    parts = [part for part in analysis_dir.split("/") if part]
    if len(parts) != 2:
        raise DeweyRegistrationError(
            "Export receipt analysis_dir must be <executing_entity>/<analysis_id>"
        )
    return parts[0], parts[1]


def dayoa_s3_root(export_receipt: dict[str, Any]) -> str:
    if export_receipt.get("status") != "success":
        raise DeweyRegistrationError("Dewey registration requires successful fsx_export receipt")
    root = str(export_receipt.get("dayoa_s3_root") or "").strip()
    if not root:
        raise DeweyRegistrationError("Export receipt is missing dayoa_s3_root")
    if not root.startswith("s3://"):
        raise DeweyRegistrationError(f"dayoa_s3_root must use s3://, got: {root}")
    return root.rstrip("/") + "/"


def selected_manifest_files(
    *,
    manifest: dict[str, Any],
    policy: ArtifactRegistrationPolicy,
    genome: str,
) -> list[dict[str, Any]]:
    if not policy.enabled:
        raise DeweyRegistrationError("Artifact registration policy is disabled")
    files = manifest.get("files")
    if not isinstance(files, list):
        raise DeweyRegistrationError("DayOA evidence manifest is missing files list")
    include_paths = [
        template_value(path, analysis_id="", executing_entity="", genome=genome)
        for path in policy.include_paths
    ]
    selected = []
    for record in files:
        if not isinstance(record, dict):
            continue
        relative_path = validate_relative_path(str(record.get("relative_path") or ""))
        classification = str(record.get("classification") or "")
        if classification in policy.include_classifications or any(
            fnmatch.fnmatch(relative_path, pattern) for pattern in include_paths
        ):
            selected.append(record)
    if not selected:
        raise DeweyRegistrationError("Artifact registration policy selected zero manifest files")
    if policy.require_existing:
        selected_paths = {str(record.get("relative_path") or "") for record in selected}
        missing_exact_paths = [
            path
            for path in include_paths
            if not any(ch in path for ch in "*?[") and path not in selected_paths
        ]
        if missing_exact_paths:
            raise DeweyRegistrationError(
                "Artifact registration policy required path(s) missing from manifest: "
                + ", ".join(sorted(missing_exact_paths))
            )
    return sorted(selected, key=lambda record: str(record.get("relative_path") or ""))


def mime_type_for_path(relative_path: str) -> str:
    if relative_path.endswith("/"):
        return "inode/directory"
    guessed, _ = mimetypes.guess_type(relative_path)
    if guessed:
        return guessed
    if relative_path.endswith(".tsv"):
        return "text/tab-separated-values"
    return "application/octet-stream"


def file_artifact_from_record(
    *,
    record: dict[str, Any],
    storage_root: str,
    produced_by: str,
) -> dict[str, Any]:
    relative_path = validate_relative_path(str(record.get("relative_path") or ""))
    sha256 = str(record.get("sha256") or "").lower()
    if len(sha256) != 64:
        raise DeweyRegistrationError(f"Manifest record has invalid sha256: {relative_path}")
    return {
        "logical_name": PurePosixPath(relative_path).name,
        "relative_path": relative_path,
        "storage_uri": s3_join(storage_root, relative_path),
        "sha256": sha256,
        "size_bytes": int(record.get("size_bytes") or 0),
        "mime_type": mime_type_for_path(relative_path),
        "artifact_role": str(record.get("classification") or "unknown"),
        "parser_hint": str(record.get("classification") or ""),
        "required": bool(record.get("required", True)),
        "produced_by": produced_by,
        "parent_artifact_euids": [],
    }


def directory_artifact(
    *,
    relative_path: str,
    storage_root: str,
    manifest_sha256: str,
    produced_by: str,
) -> dict[str, Any]:
    rel = validate_relative_path(relative_path).rstrip("/") + "/"
    return {
        "logical_name": PurePosixPath(rel.rstrip("/")).name,
        "relative_path": rel,
        "storage_uri": s3_join(storage_root, rel),
        "sha256": manifest_sha256,
        "size_bytes": 0,
        "mime_type": "inode/directory",
        "artifact_role": "directory",
        "parser_hint": None,
        "required": True,
        "produced_by": produced_by,
        "parent_artifact_euids": [],
    }


def build_registration_requests(
    *,
    manifest: dict[str, Any],
    export_receipt: dict[str, Any],
    policy: ArtifactRegistrationPolicy,
) -> dict[str, dict[str, Any]]:
    executing_entity, analysis_id = analysis_parts_from_receipt(export_receipt)
    genome = str((manifest.get("analysis") or {}).get("genome_build") or "").strip()
    if not genome:
        raise DeweyRegistrationError("DayOA evidence manifest is missing analysis.genome_build")
    root = dayoa_s3_root(export_receipt)
    selected = selected_manifest_files(manifest=manifest, policy=policy, genome=genome)
    produced_by = str((manifest.get("workflow") or {}).get("pipeline_name") or "dayoa")
    artifacts = [
        file_artifact_from_record(record=record, storage_root=root, produced_by=produced_by)
        for record in selected
    ]
    html_artifacts = [
        artifact for artifact in artifacts if artifact["artifact_role"] == "multiqc_html"
    ]
    if len(html_artifacts) != 1:
        raise DeweyRegistrationError("Selected manifest files must include exactly one MultiQC HTML")
    data_records = [
        record
        for record in selected
        if str(record.get("relative_path") or "").endswith("/multiqc_data.json")
    ]
    if len(data_records) != 1:
        raise DeweyRegistrationError("Selected manifest files must include one multiqc_data.json")
    data_dir_rel = str(data_records[0]["relative_path"]).rsplit("/", 1)[0] + "/"
    workflow = manifest.get("workflow") or {}
    generated_at = str(manifest.get("generated_at") or utc_now_iso())
    workflow_config_hash = str(workflow.get("workflow_config_hash") or "")
    if len(workflow_config_hash) != 64:
        workflow_config_hash = canonical_sha256(workflow_config_hash)
    identity = policy.identity
    analysis_request = {
        "schema_version": "1.0",
        "analysis_euid": template_value(
            identity.analysis_euid,
            analysis_id=analysis_id,
            executing_entity=executing_entity,
            genome=genome,
        ),
        "run_euid": template_value(
            identity.run_euid,
            analysis_id=analysis_id,
            executing_entity=executing_entity,
            genome=genome,
        ),
        "workset_euid": template_value(
            identity.workset_euid,
            analysis_id=analysis_id,
            executing_entity=executing_entity,
            genome=genome,
        )
        or None,
        "project_euid": template_value(
            identity.project_euid,
            analysis_id=analysis_id,
            executing_entity=executing_entity,
            genome=genome,
        )
        or None,
        "assay_id": template_value(
            identity.assay_id,
            analysis_id=analysis_id,
            executing_entity=executing_entity,
            genome=genome,
        )
        or None,
        "pipeline_name": str(workflow.get("pipeline_name") or "daylily-omics-analysis"),
        "pipeline_version": str(workflow.get("pipeline_version") or ""),
        "workflow_engine": "snakemake",
        "workflow_engine_version": str(workflow.get("snakemake_version") or ""),
        "snakemake_version": str(workflow.get("snakemake_version") or ""),
        "workflow_git_sha": str(workflow.get("git_sha") or ""),
        "workflow_config_sha256": workflow_config_hash,
        "workflow_profile": str(workflow.get("workflow_profile") or ""),
        "generated_at": generated_at,
        "manifest_sha256": "",
        "parent_analysis_artifact_set_euid": None,
        "rerun_of": None,
        "status": "completed",
        "artifacts": artifacts,
        "lineage_refs": [],
        "local_only": False,
        "parser_family_hint": policy.parser_family_hint,
    }
    analysis_request["manifest_sha256"] = manifest_sha256_for_request(analysis_request)

    data_dir_artifact = directory_artifact(
        relative_path=data_dir_rel,
        storage_root=root,
        manifest_sha256=str(manifest.get("manifest_checksum") or analysis_request["manifest_sha256"]),
        produced_by=produced_by,
    )
    key_files = [
        artifact
        for artifact in artifacts
        if artifact["artifact_role"]
        in {
            "multiqc_data_json",
            "multiqc_general_stats",
            "multiqc_sources",
            "multiqc_log",
            "staging_manifest",
        }
    ]
    parser_relevant_files = [
        artifact
        for artifact, record in zip(artifacts, selected, strict=True)
        if bool(record.get("parser_relevant"))
    ]
    multiqc_request = {
        "schema_version": "1.0",
        "analysis_euid": analysis_request["analysis_euid"],
        "report_kind": policy.multiqc_report_kind,
        "multiqc_version": policy.multiqc_version,
        "html_artifact": html_artifacts[0],
        "data_dir_artifact": data_dir_artifact,
        "key_files": key_files,
        "parser_relevant_files": parser_relevant_files,
        "generated_at": generated_at,
        "manifest_sha256": "",
        "local_only": False,
        "parser_family_hint": policy.parser_family_hint,
    }
    multiqc_request["manifest_sha256"] = manifest_sha256_for_request(multiqc_request)
    return {"analysis": analysis_request, "multiqc": multiqc_request}


def post_json(url: str, token: str, payload: dict[str, Any]) -> dict[str, Any]:
    if not token.strip():
        raise DeweyRegistrationError("Dewey bearer token is required")
    request = urllib.request.Request(
        url,
        data=canonical_json_bytes(payload),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            response_body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise DeweyRegistrationError(f"Dewey request failed with HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise DeweyRegistrationError(f"Dewey request failed: {exc}") from exc
    if not response_body.strip():
        return {}
    try:
        payload = json.loads(response_body)
    except json.JSONDecodeError as exc:
        raise DeweyRegistrationError(f"Dewey response is malformed JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise DeweyRegistrationError("Dewey response must be a JSON object")
    return payload


def register_with_dewey(
    *,
    dewey_url: str,
    token: str,
    requests: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    base = dewey_url.rstrip("/")
    if not base:
        raise DeweyRegistrationError("Dewey URL is required")
    analysis_response = post_json(base + ANALYSIS_REGISTER_ENDPOINT, token, requests["analysis"])
    multiqc_response = post_json(base + MULTIQC_REGISTER_ENDPOINT, token, requests["multiqc"])
    return {
        "schema_version": "dyec.dewey_registration_receipt.v1",
        "registered_at": utc_now_iso(),
        "analysis_endpoint": ANALYSIS_REGISTER_ENDPOINT,
        "multiqc_endpoint": MULTIQC_REGISTER_ENDPOINT,
        "analysis_request_manifest_sha256": requests["analysis"]["manifest_sha256"],
        "multiqc_request_manifest_sha256": requests["multiqc"]["manifest_sha256"],
        "analysis_response": analysis_response,
        "multiqc_response": multiqc_response,
    }
