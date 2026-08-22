"""Strict public receipts for immutable packaged DYEC resources and catalogs."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping

from daylily_ec import versioning
from daylily_ec.repositories import AnalysisCommand, default_catalog_path, load_repository_catalog
from daylily_ec.resources import resource_path


RESOURCE_RESOLVE_SCHEMA = "dyec.resources.resolve.v1"
RESOURCE_MATERIALIZE_SCHEMA = "dyec.resources.materialize.v1"
REPOSITORIES_COMMANDS_SCHEMA = "dyec.repositories.commands.v1"
CATALOG_LIST_SCHEMA = "dyec.catalog.list.v1"
CATALOG_SHOW_SCHEMA = "dyec.catalog.show.v1"
CATALOG_RENDER_SCHEMA = "dyec.catalog.render.v1"
CATALOG_LAUNCH_SCHEMA = "dyec.catalog.launch.v1"

_SEMVER_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+(?:\.[0-9]+)?$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_MAX_RESOURCE_BYTES = 64 * 1024 * 1024


class PublicContractError(RuntimeError):
    """Raised when an immutable public DYEC receipt cannot be constructed."""


def canonical_json_digest(value: Mapping[str, Any] | list[Any]) -> str:
    body = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _sha256_file(path: Path, *, maximum_bytes: int = _MAX_RESOURCE_BYTES) -> str:
    try:
        mode = path.lstat().st_mode
        size = path.stat().st_size
    except OSError as exc:
        raise PublicContractError("The requested packaged resource is unavailable") from exc
    if not stat.S_ISREG(mode) or stat.S_ISLNK(mode):
        raise PublicContractError("The requested packaged resource must be a regular file")
    if size < 1 or size > maximum_bytes:
        raise PublicContractError("The requested packaged resource exceeds the bounded size limit")
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise PublicContractError("The requested packaged resource could not be read") from exc
    return digest.hexdigest()


def validate_relative_resource_path(value: object) -> str:
    raw = str(value or "").strip().replace("\\", "/")
    if not raw or raw.startswith("/") or "\x00" in raw:
        raise PublicContractError("resource must be a non-empty relative payload path")
    path = PurePosixPath(raw)
    if any(part in {"", ".", ".."} for part in path.parts):
        raise PublicContractError("resource must not contain traversal segments")
    return path.as_posix()


def _resource_identity(relative_path: str) -> dict[str, Any]:
    source = resource_path(relative_path)
    content_sha256 = _sha256_file(source)
    return {
        "identity": f"dyec-resource:{relative_path}",
        "relative_path": relative_path,
        "relative_path_sha256": hashlib.sha256(relative_path.encode("utf-8")).hexdigest(),
        "content_sha256": content_sha256,
        "size_bytes": source.stat().st_size,
    }


def resolve_resource_receipt(relative_path: object) -> dict[str, Any]:
    """Return a path-independent receipt for one packaged file."""

    normalized = validate_relative_resource_path(relative_path)
    resource = _resource_identity(normalized)
    return {
        "schema_version": RESOURCE_RESOLVE_SCHEMA,
        "ok": True,
        "status": "resolved",
        "dyec_version": versioning.get_version(),
        "resource": resource,
        "receipt_sha256": canonical_json_digest(resource),
    }


def _require_protected_parent(destination: Path) -> Path:
    if not destination.is_absolute():
        raise PublicContractError("output must be an absolute path")
    parent = destination.parent
    parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        info = parent.lstat()
    except OSError as exc:
        raise PublicContractError("output parent is unavailable") from exc
    if not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode):
        raise PublicContractError("output parent must be a real directory")
    if info.st_uid != os.getuid():
        raise PublicContractError("output parent must be owned by the current user")
    os.chmod(parent, 0o700)
    if parent.lstat().st_mode & 0o077:
        raise PublicContractError("output parent must be owned and protected with mode 0700")
    return parent


def _atomic_write(destination: Path, content: bytes) -> None:
    parent = _require_protected_parent(destination)
    if destination.exists() and stat.S_ISLNK(destination.lstat().st_mode):
        raise PublicContractError("output must not replace a symbolic link")
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=str(parent)
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, destination)
    finally:
        if temporary.exists():
            temporary.unlink()


def materialize_resource_receipt(relative_path: object, output: object) -> dict[str, Any]:
    """Copy one immutable package file to a protected absolute path atomically."""

    normalized = validate_relative_resource_path(relative_path)
    raw_output = str(output or "").strip()
    if not raw_output:
        raise PublicContractError("output is required")
    destination = Path(raw_output).expanduser()
    if not destination.is_absolute():
        raise PublicContractError("output must be an absolute path")
    if destination.name in {"", ".", ".."}:
        raise PublicContractError("output must name one regular file")
    if destination.exists() and stat.S_ISLNK(destination.lstat().st_mode):
        raise PublicContractError("output must not be a symbolic link")
    destination = destination.parent.resolve() / destination.name
    source = resource_path(normalized)
    resource = _resource_identity(normalized)
    try:
        content = source.read_bytes()
    except OSError as exc:
        raise PublicContractError("The requested packaged resource could not be materialized") from exc
    _atomic_write(destination, content)
    written_digest = _sha256_file(destination)
    if written_digest != resource["content_sha256"]:
        raise PublicContractError("materialized resource content digest did not match source")
    result = {
        "output_path": str(destination),
        "output_sha256": written_digest,
        "output_size_bytes": destination.stat().st_size,
        "output_mode": "0600",
    }
    return {
        "schema_version": RESOURCE_MATERIALIZE_SCHEMA,
        "ok": True,
        "status": "materialized",
        "dyec_version": versioning.get_version(),
        "resource": resource,
        "result": result,
        "receipt_sha256": canonical_json_digest({"resource": resource, "result": result}),
    }


def require_numeric_catalog_build(value: object) -> str:
    build = str(value or "").strip()
    if not _SEMVER_RE.fullmatch(build):
        raise PublicContractError("dyec_build must be an exact non-v numeric release identifier")
    return build


def _catalog_source_identity() -> dict[str, Any]:
    catalog_path = default_catalog_path()
    try:
        content_sha256 = _sha256_file(catalog_path)
    except PublicContractError:
        raise
    return {
        "identity": "dyec-resource:config/daylily_pipeline_command_catalog.yaml",
        "relative_path": "config/daylily_pipeline_command_catalog.yaml",
        "content_sha256": content_sha256,
        "size_bytes": catalog_path.stat().st_size,
    }


def _command_payload(command: AnalysisCommand) -> dict[str, Any]:
    resolved = command.to_public_payload()
    resolved_digest = canonical_json_digest(resolved)
    payload = dict(resolved)
    payload.pop("dy_command", None)
    payload.pop("dryrun_dy_command", None)
    payload["resolved_command_sha256"] = resolved_digest
    return payload


def _repository_identities(commands: Iterable[AnalysisCommand], catalog: Any) -> list[dict[str, Any]]:
    names = sorted({command.repository for command in commands})
    rows: list[dict[str, Any]] = []
    for repository_name in names:
        repository = catalog.repositories.get(repository_name)
        if repository is None:
            raise PublicContractError("catalog command references an unavailable repository")
        payload = repository.to_public_payload()
        payload.pop("analysis_commands", None)
        rows.append(
            {
                "repository": repository_name,
                "identity_sha256": canonical_json_digest(payload),
                "default_ref": repository.default_ref,
                "relative_path": repository.relative_path,
                "source_url": repository.https_url,
                "clone_transport": repository.clone_transport,
                "auth_mode": repository.auth_mode,
            }
        )
    return rows


def catalog_contract(build: object, *, command_id: object | None = None, features: Iterable[object] = ()) -> dict[str, Any]:
    """Resolve one immutable catalog build, optional command, and explicit features."""

    build_key = require_numeric_catalog_build(build)
    catalog = load_repository_catalog()
    commands = list(catalog.commands_for_dyec_build(build_key))
    selected_features: tuple[str, ...] = ()
    if command_id is not None:
        command_key = str(command_id or "").strip()
        if not command_key:
            raise PublicContractError("command_id is required")
        try:
            command = catalog.get_command_for_dyec_build(command_key, build_key)
        except KeyError as exc:
            raise PublicContractError("requested catalog command is not present in the exact build") from exc
        feature_values = tuple(str(item or "").strip() for item in features)
        if any(not item for item in feature_values) or len(set(feature_values)) != len(feature_values):
            raise PublicContractError("--feature values must be explicit and unique")
        try:
            command = command.with_features(feature_values)
        except KeyError as exc:
            raise PublicContractError("requested feature is not allowed by the exact catalog command") from exc
        commands = [command]
        selected_features = feature_values
    command_rows = [_command_payload(command) for command in commands]
    runtime_rows = sorted(
        {
            (
                str(command["repository"]),
                str(command["git_tag"]),
            )
            for command in command_rows
        }
    )
    runtime_identities = [
        {
            "repository": repository,
            "runtime_identity": f"{repository}@{git_tag}",
            "runtime_sha256": hashlib.sha256(
                f"{repository}@{git_tag}".encode("utf-8")
            ).hexdigest(),
        }
        for repository, git_tag in runtime_rows
    ]
    contract = {
        "dyec_version": versioning.get_version(),
        "dyec_build": build_key,
        "catalog_schema_version": int(catalog.command_catalog_version),
        "catalog": _catalog_source_identity(),
        "repositories": _repository_identities(commands, catalog),
        "runtime_identities": runtime_identities,
        "commands": command_rows,
        "selected_features": list(selected_features),
        "result_export": (
            catalog.result_export.model_dump(mode="json")
            if catalog.result_export is not None
            else None
        ),
    }
    contract["contract_sha256"] = canonical_json_digest(contract)
    return contract


def catalog_receipt(schema_version: str, build: object, *, command_id: object | None = None, features: Iterable[object] = (), extra: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Wrap an immutable catalog resolution in one versioned public receipt."""

    if schema_version not in {
        REPOSITORIES_COMMANDS_SCHEMA,
        CATALOG_LIST_SCHEMA,
        CATALOG_SHOW_SCHEMA,
        CATALOG_RENDER_SCHEMA,
        CATALOG_LAUNCH_SCHEMA,
    }:
        raise PublicContractError("unsupported public catalog receipt schema")
    contract = catalog_contract(build, command_id=command_id, features=features)
    payload: dict[str, Any] = {
        "schema_version": schema_version,
        "ok": True,
        "status": "resolved",
        "contract": contract,
    }
    if extra:
        payload["result"] = dict(extra)
    payload["receipt_sha256"] = canonical_json_digest(
        {key: value for key, value in payload.items() if key != "receipt_sha256"}
    )
    return payload


__all__ = [
    "CATALOG_LIST_SCHEMA",
    "CATALOG_LAUNCH_SCHEMA",
    "CATALOG_RENDER_SCHEMA",
    "CATALOG_SHOW_SCHEMA",
    "PublicContractError",
    "REPOSITORIES_COMMANDS_SCHEMA",
    "RESOURCE_MATERIALIZE_SCHEMA",
    "RESOURCE_RESOLVE_SCHEMA",
    "canonical_json_digest",
    "catalog_contract",
    "catalog_receipt",
    "materialize_resource_receipt",
    "require_numeric_catalog_build",
    "resolve_resource_receipt",
    "validate_relative_resource_path",
]
