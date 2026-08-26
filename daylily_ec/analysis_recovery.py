"""Strict artifact snapshot and fresh-capsule materialization contracts."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import uuid
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

RECOVERY_SPEC_SCHEMA = "dyec.analysis_recovery_spec/1.0"
RECOVERY_SOURCE_SCHEMA = "dyec.analysis_recovery_source/1.0"
RECOVERY_MATERIALIZATION_SCHEMA = "dyec.analysis_recovery_materialization/1.0"
SAFE_ROLE_RE = re.compile(r"[a-z][a-z0-9_.-]*")
SAFE_ANALYSIS_UNIT_RE = re.compile(r"[A-Za-z0-9_.-]+")
SHA256_RE = re.compile(r"[0-9a-f]{64}")


class AnalysisRecoveryError(RuntimeError):
    """Raised when recovery topology, ownership, or bytes are unsafe."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_json_sha256(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _mapping(value: object, field: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise AnalysisRecoveryError(f"{field} must be an object")
    return value


def _string_list(value: object, field: str, *, allow_empty: bool = False) -> list[str]:
    if not isinstance(value, list) or (not value and not allow_empty):
        qualifier = "a list" if allow_empty else "a non-empty list"
        raise AnalysisRecoveryError(f"{field} must be {qualifier}")
    result: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise AnalysisRecoveryError(f"{field} contains a non-string value")
        text = item
        if not text or text != text.strip():
            raise AnalysisRecoveryError(f"{field} contains a blank or modified value")
        result.append(text)
    if len(result) != len(set(result)):
        raise AnalysisRecoveryError(f"{field} contains duplicates")
    return result


def _relative_artifact_path(value: object) -> str:
    if not isinstance(value, str):
        raise AnalysisRecoveryError("artifact path must be a string")
    text = value
    candidate = PurePosixPath(text)
    if (
        not text
        or text != text.strip()
        or candidate.is_absolute()
        or ".." in candidate.parts
        or "." in candidate.parts
        or any(part.startswith(".") for part in candidate.parts)
        or str(candidate) != text
        or candidate.parts[:2] != ("daylily-omics-analysis", "results")
    ):
        raise AnalysisRecoveryError(
            "artifact paths must be canonical relative DayOA results paths: " + repr(text)
        )
    return text


def _validate_topology(value: object) -> dict[str, list[str]]:
    topology = _mapping(value, "topology")
    if set(topology) != {
        "expected_analysis_units",
        "recompute_analysis_units",
        "required_global_roles",
        "required_roles_per_reused_analysis_unit",
        "reused_analysis_units",
    }:
        raise AnalysisRecoveryError("recovery topology fields differ")
    expected = _string_list(topology["expected_analysis_units"], "expected_analysis_units")
    recompute = _string_list(
        topology["recompute_analysis_units"], "recompute_analysis_units"
    )
    reused = _string_list(topology["reused_analysis_units"], "reused_analysis_units")
    for value_name, values in (
        ("expected_analysis_units", expected),
        ("recompute_analysis_units", recompute),
        ("reused_analysis_units", reused),
    ):
        if any(SAFE_ANALYSIS_UNIT_RE.fullmatch(item) is None for item in values):
            raise AnalysisRecoveryError(f"{value_name} contains an unsafe identifier")
    if set(recompute) & set(reused):
        raise AnalysisRecoveryError("recomputed and reused analysis units overlap")
    if set(recompute) | set(reused) != set(expected):
        raise AnalysisRecoveryError(
            "recomputed and reused analysis units do not partition expected topology"
        )
    per_unit_roles = _string_list(
        topology["required_roles_per_reused_analysis_unit"],
        "required_roles_per_reused_analysis_unit",
    )
    global_roles = _string_list(
        topology["required_global_roles"], "required_global_roles", allow_empty=True
    )
    if any(SAFE_ROLE_RE.fullmatch(role) is None for role in (*per_unit_roles, *global_roles)):
        raise AnalysisRecoveryError("topology contains an unsafe artifact role")
    return {
        "expected_analysis_units": expected,
        "recompute_analysis_units": recompute,
        "reused_analysis_units": reused,
        "required_roles_per_reused_analysis_unit": per_unit_roles,
        "required_global_roles": global_roles,
    }


def _validate_artifact_specs(
    artifacts: object,
    *,
    topology: Mapping[str, list[str]],
    with_bindings: bool,
) -> list[dict[str, Any]]:
    if not isinstance(artifacts, list) or not artifacts:
        raise AnalysisRecoveryError("artifacts must be a non-empty list")
    reused = set(topology["reused_analysis_units"])
    required_roles = set(topology["required_roles_per_reused_analysis_unit"])
    required_global_roles = set(topology["required_global_roles"])
    roles_by_unit: dict[str, set[str]] = {unit: set() for unit in reused}
    global_roles: set[str] = set()
    seen_paths: set[str] = set()
    seen_owners: set[tuple[str | None, str]] = set()
    validated: list[dict[str, Any]] = []
    expected_fields = {"analysis_unit_uid", "complete", "path", "role"}
    if with_bindings:
        expected_fields |= {"size_bytes", "sha256"}
    for index, raw in enumerate(artifacts):
        artifact = _mapping(raw, f"artifacts[{index}]")
        if set(artifact) != expected_fields:
            raise AnalysisRecoveryError(f"artifacts[{index}] fields differ")
        role_raw = artifact.get("role")
        if not isinstance(role_raw, str):
            raise AnalysisRecoveryError(f"artifacts[{index}] role must be a string")
        role = role_raw
        if SAFE_ROLE_RE.fullmatch(role) is None:
            raise AnalysisRecoveryError(f"artifacts[{index}] role is unsafe")
        owner_raw = artifact.get("analysis_unit_uid")
        if owner_raw is not None and not isinstance(owner_raw, str):
            raise AnalysisRecoveryError(
                f"artifacts[{index}] analysis_unit_uid must be a string or null"
            )
        owner = owner_raw
        if owner is not None and owner not in reused:
            raise AnalysisRecoveryError(
                f"artifacts[{index}] owner is not a reused analysis unit"
            )
        if artifact.get("complete") is not True:
            raise AnalysisRecoveryError(f"artifacts[{index}] is not explicitly complete")
        relative = _relative_artifact_path(artifact.get("path"))
        ownership = (owner, role)
        if relative in seen_paths or ownership in seen_owners:
            raise AnalysisRecoveryError("artifact path or role ownership is ambiguous")
        seen_paths.add(relative)
        seen_owners.add(ownership)
        normalized: dict[str, Any] = {
            "analysis_unit_uid": owner,
            "complete": True,
            "path": relative,
            "role": role,
        }
        if with_bindings:
            size_raw = artifact.get("size_bytes")
            if not isinstance(size_raw, int) or isinstance(size_raw, bool):
                raise AnalysisRecoveryError(f"artifacts[{index}] size is invalid")
            size = size_raw
            digest_raw = artifact.get("sha256")
            if not isinstance(digest_raw, str):
                raise AnalysisRecoveryError(f"artifacts[{index}] digest is invalid")
            digest = digest_raw
            if size <= 0 or SHA256_RE.fullmatch(digest) is None:
                raise AnalysisRecoveryError(
                    f"artifacts[{index}] byte binding is incomplete"
                )
            normalized.update(size_bytes=size, sha256=digest)
        if owner is None:
            global_roles.add(role)
        else:
            roles_by_unit[owner].add(role)
        validated.append(normalized)
    for unit, roles in roles_by_unit.items():
        missing = required_roles - roles
        if missing:
            raise AnalysisRecoveryError(
                f"reused analysis unit {unit!r} is missing required roles: {sorted(missing)}"
            )
    missing_globals = required_global_roles - global_roles
    if missing_globals:
        raise AnalysisRecoveryError(f"required global roles are missing: {sorted(missing_globals)}")
    return sorted(
        validated,
        key=lambda item: (
            str(item["analysis_unit_uid"] or ""),
            str(item["role"]),
            str(item["path"]),
        ),
    )


def load_recovery_spec(path: Path, *, analysis_root: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise AnalysisRecoveryError(f"recovery spec must be a regular file: {path}")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise AnalysisRecoveryError(f"recovery spec is not valid JSON: {path}") from exc
    root = _mapping(raw, "recovery spec")
    if set(root) != {
        "artifact_count",
        "artifacts",
        "schema",
        "source_analysis_root",
        "topology",
    }:
        raise AnalysisRecoveryError("recovery spec fields differ")
    if root.get("schema") != RECOVERY_SPEC_SCHEMA:
        raise AnalysisRecoveryError("recovery spec schema differs")
    resolved_root = analysis_root.resolve()
    supplied_root_raw = root.get("source_analysis_root")
    if (
        not isinstance(supplied_root_raw, str)
        or supplied_root_raw != str(resolved_root)
    ):
        raise AnalysisRecoveryError("recovery spec source analysis root differs")
    topology = _validate_topology(root.get("topology"))
    artifacts = _validate_artifact_specs(root.get("artifacts"), topology=topology, with_bindings=False)
    artifact_count = root.get("artifact_count")
    if (
        not isinstance(artifact_count, int)
        or isinstance(artifact_count, bool)
        or artifact_count != len(artifacts)
    ):
        raise AnalysisRecoveryError("recovery spec artifact_count differs")
    return {
        "schema": RECOVERY_SPEC_SCHEMA,
        "source_analysis_root": str(resolved_root),
        "topology": topology,
        "artifact_count": len(artifacts),
        "artifacts": artifacts,
    }


def snapshot_artifacts(*, analysis_root: Path, spec_path: Path) -> dict[str, Any]:
    """Hash only exact operator-supplied paths; never discover source artifacts."""

    if analysis_root.is_symlink() or not analysis_root.is_dir():
        raise AnalysisRecoveryError(
            f"source analysis root is not a materialized directory: {analysis_root}"
        )
    root = analysis_root.resolve()
    spec = load_recovery_spec(spec_path, analysis_root=root)
    bound: list[dict[str, Any]] = []
    for artifact in spec["artifacts"]:
        source = root / str(artifact["path"])
        if source.is_symlink() or not source.is_file():
            raise AnalysisRecoveryError(f"source artifact is not a regular file: {source}")
        size = source.stat().st_size
        if size <= 0:
            raise AnalysisRecoveryError(f"source artifact is empty: {source}")
        bound.append(
            {
                **artifact,
                "size_bytes": size,
                "sha256": sha256_file(source),
            }
        )
    payload = {
        "schema": RECOVERY_SOURCE_SCHEMA,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_analysis_root": str(root),
        "source_spec_sha256": canonical_json_sha256(spec),
        "topology": spec["topology"],
        "artifact_count": len(bound),
        "artifacts": bound,
    }
    validate_recovery_source(payload, verify_source=True)
    return payload


def validate_recovery_source(
    payload: Mapping[str, Any],
    *,
    verify_source: bool,
) -> dict[str, Any]:
    if set(payload) != {
        "artifact_count",
        "artifacts",
        "created_at",
        "schema",
        "source_analysis_root",
        "source_spec_sha256",
        "topology",
    }:
        raise AnalysisRecoveryError("recovery source fields differ")
    if payload.get("schema") != RECOVERY_SOURCE_SCHEMA:
        raise AnalysisRecoveryError("recovery source schema differs")
    created_at = payload.get("created_at")
    if not isinstance(created_at, str) or not created_at or created_at != created_at.strip():
        raise AnalysisRecoveryError("recovery source created_at is invalid")
    try:
        created_datetime = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise AnalysisRecoveryError("recovery source created_at is invalid") from exc
    if created_datetime.tzinfo is None or created_datetime.utcoffset() is None:
        raise AnalysisRecoveryError("recovery source created_at must include a timezone")
    source_root_raw = payload.get("source_analysis_root")
    if not isinstance(source_root_raw, str) or not source_root_raw:
        raise AnalysisRecoveryError("recovery source analysis root is invalid")
    source_root_path = Path(source_root_raw)
    if (
        not source_root_path.is_absolute()
        or str(source_root_path) != source_root_raw
        or str(source_root_path.resolve()) != source_root_raw
    ):
        raise AnalysisRecoveryError(
            "recovery source analysis root must be canonical and absolute"
        )
    source_root = source_root_path.resolve()
    source_spec_sha256 = payload.get("source_spec_sha256")
    if not isinstance(source_spec_sha256, str) or SHA256_RE.fullmatch(source_spec_sha256) is None:
        raise AnalysisRecoveryError("source spec digest is invalid")
    topology = _validate_topology(payload.get("topology"))
    artifacts = _validate_artifact_specs(
        payload.get("artifacts"), topology=topology, with_bindings=True
    )
    artifact_count = payload.get("artifact_count")
    if (
        not isinstance(artifact_count, int)
        or isinstance(artifact_count, bool)
        or artifact_count != len(artifacts)
    ):
        raise AnalysisRecoveryError("recovery source artifact_count differs")
    if verify_source:
        for artifact in artifacts:
            path = source_root / str(artifact["path"])
            if (
                path.is_symlink()
                or not path.is_file()
                or path.stat().st_size != artifact["size_bytes"]
                or sha256_file(path) != artifact["sha256"]
            ):
                raise AnalysisRecoveryError(f"source artifact hash drift: {path}")
    return {
        **dict(payload),
        "source_analysis_root": str(source_root),
        "topology": topology,
        "artifacts": artifacts,
    }


def load_recovery_source(path: Path, *, verify_source: bool) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise AnalysisRecoveryError(f"recovery source must be a regular file: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise AnalysisRecoveryError(f"recovery source is not valid JSON: {path}") from exc
    return validate_recovery_source(_mapping(payload, "recovery source"), verify_source=verify_source)


def _destination_path(root: Path, relative: str) -> Path:
    path = root / relative
    resolved_parent = path.parent.resolve()
    if os.path.commonpath((str(root), str(resolved_parent))) != str(root):
        raise AnalysisRecoveryError(f"artifact destination escapes analysis root: {relative}")
    return path


def materialize_recovery_source(
    manifest_path: Path,
    *,
    destination_analysis_root: Path,
) -> dict[str, Any]:
    """Copy verified source bytes transactionally into one fresh capsule."""

    manifest = load_recovery_source(manifest_path, verify_source=True)
    source_root = Path(manifest["source_analysis_root"]).resolve()
    if destination_analysis_root.is_symlink():
        raise AnalysisRecoveryError("destination analysis root must not be a symlink")
    destination_root = destination_analysis_root.resolve()
    if source_root == destination_root:
        raise AnalysisRecoveryError("source and destination analysis roots must differ")
    if not destination_root.is_dir():
        raise AnalysisRecoveryError(f"destination analysis root is not a directory: {destination_root}")

    recovery_root = destination_root / ".dayoa_agent" / "recovery"
    receipt_path = recovery_root / "materialization.json"
    if receipt_path.exists():
        raise AnalysisRecoveryError(f"refusing to overwrite recovery receipt: {receipt_path}")
    destinations = [
        _destination_path(destination_root, str(artifact["path"]))
        for artifact in manifest["artifacts"]
    ]
    if any(path.exists() or path.is_symlink() for path in destinations):
        raise AnalysisRecoveryError("recovery destination already contains a selected artifact")

    stage = recovery_root / f"stage-{uuid.uuid4().hex}"
    committed: list[Path] = []
    try:
        stage.mkdir(parents=True)
        for artifact in manifest["artifacts"]:
            relative = str(artifact["path"])
            source = source_root / relative
            staged = stage / relative
            staged.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, staged, follow_symlinks=False)
            if (
                staged.is_symlink()
                or staged.stat().st_size != artifact["size_bytes"]
                or sha256_file(staged) != artifact["sha256"]
            ):
                raise AnalysisRecoveryError(f"staged recovery artifact bytes differ: {relative}")
        for artifact in manifest["artifacts"]:
            relative = str(artifact["path"])
            staged = stage / relative
            destination = _destination_path(destination_root, relative)
            destination.parent.mkdir(parents=True, exist_ok=True)
            os.replace(staged, destination)
            committed.append(destination)
        for artifact, destination in zip(manifest["artifacts"], destinations, strict=True):
            if (
                destination.is_symlink()
                or destination.stat().st_size != artifact["size_bytes"]
                or sha256_file(destination) != artifact["sha256"]
            ):
                raise AnalysisRecoveryError(
                    f"materialized recovery artifact bytes differ: {artifact['path']}"
                )
        receipt = {
            "schema": RECOVERY_MATERIALIZATION_SCHEMA,
            "status": "complete",
            "source_analysis_root": str(source_root),
            "destination_analysis_root": str(destination_root),
            "source_manifest_sha256": sha256_file(manifest_path),
            "analysis_unit_count": len(manifest["topology"]["expected_analysis_units"]),
            "recompute_analysis_units": manifest["topology"]["recompute_analysis_units"],
            "reused_analysis_units": manifest["topology"]["reused_analysis_units"],
            "artifact_count": len(manifest["artifacts"]),
            "copy_method": "shutil.copy2",
            "fallback_used": False,
        }
        recovery_root.mkdir(parents=True, exist_ok=True)
        temporary = receipt_path.with_suffix(".json.partial")
        temporary.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(temporary, receipt_path)
        return receipt
    except Exception:
        for path in reversed(committed):
            path.unlink(missing_ok=True)
        raise
    finally:
        shutil.rmtree(stage, ignore_errors=True)
