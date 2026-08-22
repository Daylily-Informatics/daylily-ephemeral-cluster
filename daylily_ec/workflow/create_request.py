"""Versioned, file-backed create-request and live-pricing contracts.

These helpers are the public-CLI implementation boundary used by upstream
services.  Request rendering is local and deterministic.  Preparation performs
only read-only AWS identity, instance-type, and Spot price queries; it never
creates or updates provider resources.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import stat
import tempfile
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from daylily_ec.aws.spot_pricing import (
    DEFAULT_GLOBAL_SPOT_MAX_COST,
    DEFAULT_SPOT_COST_LIMIT_PCT,
    DEFAULT_WRITE_SPOT_PRICING_WARN_THRESHOLD,
    MAX_SPOT_OBSERVATION_AGE_SECONDS,
    MAX_SPOT_OBSERVATION_FUTURE_SKEW_SECONDS,
    apply_spot_prices,
    validate_spot_pricing_limits,
)
from daylily_ec.config.models import REQUIRED_CONFIG_KEYS, Triplet
from daylily_ec.config.triplets import load_config, resolve_derived_max_count

CREATE_REQUEST_OVERRIDES_SCHEMA = "dyec.create_request_overrides.v1"
CREATE_REQUEST_SCHEMA = "dyec.create_request.v1"
CREATE_PREPARATION_SCHEMA = "dyec.create_preparation.v1"
CREATE_PRICING_RECEIPT_SCHEMA = "dyec.create_pricing_receipt.v1"
CREATE_TERMINAL_RECEIPT_SCHEMA = "dyec.create_terminal.v1"
CREATE_SUCCESS_SCHEMA = "dyec.create.v1"
SPOT_PRICE_POLICY = "CALCULATE_MAX_SPOT_PRICE"

MAX_CREATE_REQUEST_BYTES = 4 * 1024 * 1024
MAX_CREATE_OVERRIDES_BYTES = 256 * 1024
MAX_PREPARATION_RECEIPT_AGE_SECONDS = 3600
MAX_PREPARATION_RECEIPT_FUTURE_SKEW_SECONDS = 300
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

# cluster_template_yaml has its own exact CLI argument and cannot be smuggled
# through the overrides document.  Derived and retired fields are likewise not
# accepted as compatibility aliases.
CREATE_REQUEST_OVERRIDE_KEYS = frozenset(
    {
        "allowed_budget_users",
        "budget_amount",
        "budget_email",
        "cluster_name",
        "cost_center_allowed_users",
        "cost_center_monthly_cap_usd",
        "cost_center_name",
        "dayoa_deploy_key_policy_arn",
        "dayoa_deploy_key_secret_arn",
        "dyec_deploy_key_policy_arn",
        "dyec_deploy_key_secret_arn",
    }
)
CREATE_REQUEST_OPTIONAL_EMPTY_KEYS = frozenset(
    {
        "dragen_license_policy_arn",
        "dragen_license_secret_arn",
        "heartbeat_scheduler_role_arn",
        "pcluster_backport_manifest",
    }
)
CREATE_REQUEST_METADATA_KEYS = frozenset(
    {
        "cluster_name",
        "dyec_version",
        "override_keys",
        "overrides_file_sha256",
        "overrides_sha256",
        "region_az",
        "repository_credential_reference_keys",
        "repository_credential_references_sha256",
        "schema_version",
        "source_config_identity",
        "source_config_sha256",
        "source_template_identity",
        "source_template_sha256",
    }
)
REPOSITORY_CREDENTIAL_REFERENCE_KEYS = (
    "dayoa_deploy_key_policy_arn",
    "dayoa_deploy_key_secret_arn",
    "dyec_deploy_key_policy_arn",
    "dyec_deploy_key_secret_arn",
)


class CreateRequestError(RuntimeError):
    """Raised when a create-request identity or policy is not exact."""


class _StrictYamlLoader(yaml.SafeLoader):
    """Safe YAML loader that rejects ambiguous duplicate mapping keys."""


def _construct_unique_yaml_mapping(
    loader: _StrictYamlLoader,
    node: yaml.nodes.MappingNode,
    deep: bool = False,
) -> dict[Any, Any]:
    loader.flatten_mapping(node)
    pairs = loader.construct_pairs(node, deep=deep)
    result: dict[Any, Any] = {}
    for key, value in pairs:
        try:
            duplicate = key in result
        except TypeError as exc:
            raise yaml.constructor.ConstructorError(
                None,
                None,
                "YAML mapping keys must be scalar and hashable",
                node.start_mark,
            ) from exc
        if duplicate:
            raise yaml.constructor.ConstructorError(
                None,
                None,
                "YAML mapping contains a duplicate key",
                node.start_mark,
            )
        result[key] = value
    return result


_StrictYamlLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_yaml_mapping,
)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _dyec_version() -> str:
    from daylily_ec import __version__

    return __version__


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_path(path: str | Path, *, max_bytes: int = MAX_CREATE_REQUEST_BYTES) -> str:
    candidate = Path(path).expanduser().resolve()
    try:
        size = candidate.stat().st_size
    except OSError as exc:
        raise CreateRequestError(f"Required file is unavailable: {candidate}") from exc
    if size < 1 or size > max_bytes:
        raise CreateRequestError(
            f"Required file size is outside the supported 1..{max_bytes} byte range: {candidate}"
        )
    digest = hashlib.sha256()
    try:
        with candidate.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
    except OSError as exc:
        raise CreateRequestError(f"Could not read required file: {candidate}") from exc
    return digest.hexdigest()


def _require_sha256(value: str, *, label: str) -> str:
    normalized = str(value or "").strip().lower()
    if not _SHA256_RE.fullmatch(normalized):
        raise CreateRequestError(f"{label} must be a lowercase 64-character SHA-256 digest")
    return normalized


def _resolve_input_path(
    value: str | Path,
    *,
    label: str,
    reject_symlink: bool = False,
) -> Path:
    raw = str(value or "").strip()
    if not raw:
        raise CreateRequestError(f"{label} is required")
    candidate = Path(raw).expanduser()
    if candidate.is_absolute():
        if reject_symlink:
            try:
                mode = candidate.lstat().st_mode
            except OSError as exc:
                raise CreateRequestError(f"{label} does not exist: {candidate}") from exc
            if stat.S_ISLNK(mode):
                raise CreateRequestError(f"{label} must not be a symbolic link")
            if not stat.S_ISREG(mode):
                raise CreateRequestError(f"{label} must be a regular file")
        if not candidate.is_file():
            raise CreateRequestError(f"{label} does not exist: {candidate}")
        return candidate.resolve()
    if "\\" in raw or any(part in {"", ".", ".."} for part in candidate.parts):
        raise CreateRequestError(f"{label} must be an exact safe relative resource path")
    from daylily_ec.resources import resource_path

    try:
        resource = resource_path(raw)
        if reject_symlink:
            mode = resource.lstat().st_mode
            if stat.S_ISLNK(mode):
                raise CreateRequestError(f"{label} must not be a symbolic link")
            if not stat.S_ISREG(mode):
                raise CreateRequestError(f"{label} must be a regular file")
        return resource.resolve()
    except (FileNotFoundError, OSError) as exc:
        raise CreateRequestError(f"{label} does not exist: {raw}") from exc


def _logical_input_identity(value: str | Path, resolved: Path) -> str:
    raw = str(value or "").strip()
    candidate = Path(raw).expanduser()
    if (
        raw
        and not candidate.is_absolute()
        and "\\" not in raw
        and all(part not in {"", ".", ".."} for part in candidate.parts)
    ):
        return f"dyec-resource:{candidate.as_posix()}"
    return f"external-file:{resolved.name}"


def _require_absolute_output(path: str | Path, *, label: str) -> Path:
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        raise CreateRequestError(f"{label} must be an absolute path")
    return candidate.resolve()


def require_protected_file(path: str | Path, *, label: str) -> Path:
    """Require an existing regular file protected with exact mode ``0600``."""

    candidate = _resolve_input_path(path, label=label, reject_symlink=True)
    try:
        mode = candidate.lstat().st_mode
    except OSError as exc:
        raise CreateRequestError(f"Required protected file is unavailable: {label}") from exc
    if not stat.S_ISREG(mode):
        raise CreateRequestError(f"{label} must be a regular file")
    if stat.S_IMODE(mode) != 0o600:
        raise CreateRequestError(f"{label} must be protected with mode 0600")
    return candidate


def _require_protected_directory(path: Path, *, label: str) -> None:
    try:
        mode = path.stat().st_mode
    except OSError as exc:
        raise CreateRequestError(f"Required protected directory is unavailable: {label}") from exc
    if not path.is_dir() or stat.S_IMODE(mode) != 0o700:
        raise CreateRequestError(f"{label} must be a directory protected with mode 0700")


def _atomic_write_bytes(path: Path, payload: bytes, *, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    _require_protected_directory(path.parent, label=f"{path.name} parent")
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=str(path.parent),
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    body = json.dumps(dict(payload), indent=2, sort_keys=True) + "\n"
    _atomic_write_bytes(path, body.encode("utf-8"))


def _canonical_json_sha256(payload: Mapping[str, Any]) -> str:
    body = json.dumps(dict(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return sha256_bytes(body.encode("utf-8"))


def _artifact_identity(path: Path) -> dict[str, Any]:
    return {
        "name": path.name,
        "size_bytes": path.stat().st_size,
        "sha256": sha256_path(path),
    }


def _verify_artifact_identity(directory: Path, payload: Any, *, label: str) -> None:
    if not isinstance(payload, dict) or set(payload) != {"name", "size_bytes", "sha256"}:
        raise CreateRequestError(f"Preparation receipt {label} artifact identity is invalid")
    name = str(payload.get("name") or "")
    if not name or Path(name).name != name:
        raise CreateRequestError(f"Preparation receipt {label} artifact name is invalid")
    path = directory / name
    require_protected_file(path, label=f"{label} artifact")
    try:
        expected_size = int(payload.get("size_bytes"))
    except (TypeError, ValueError) as exc:
        raise CreateRequestError(f"Preparation receipt {label} artifact size is invalid") from exc
    try:
        actual_size = path.stat().st_size
    except OSError as exc:
        raise CreateRequestError(f"Preparation receipt {label} artifact is unavailable") from exc
    if expected_size < 1 or actual_size != expected_size:
        raise CreateRequestError(f"Preparation receipt {label} artifact size does not match")
    if sha256_path(path) != _require_sha256(
        str(payload.get("sha256") or ""), label=f"{label} artifact SHA-256"
    ):
        raise CreateRequestError(f"Preparation receipt {label} artifact digest does not match")


def _load_bounded_yaml(path: Path) -> dict[str, Any]:
    sha256_path(path)
    try:
        payload = yaml.load(
            path.read_text(encoding="utf-8"),
            Loader=_StrictYamlLoader,
        )
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise CreateRequestError(f"Invalid YAML document: {path}") from exc
    if not isinstance(payload, dict):
        raise CreateRequestError(f"YAML document must contain a top-level mapping: {path}")

    def reject_non_finite(value: Any) -> None:
        if isinstance(value, float) and not math.isfinite(value):
            raise CreateRequestError(f"YAML document contains a non-finite number: {path}")
        if isinstance(value, dict):
            for key, item in value.items():
                reject_non_finite(key)
                reject_non_finite(item)
        elif isinstance(value, list):
            for item in value:
                reject_non_finite(item)

    reject_non_finite(payload)
    return payload


def load_strict_create_request_payload(path: str | Path) -> dict[str, Any]:
    """Load one protected request with strict YAML and current-schema validation."""

    candidate = require_protected_file(path, label="create request")
    payload = _load_bounded_yaml(candidate)
    validate_strict_create_request_payload(payload)
    return payload


def _unique_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise CreateRequestError("JSON object contains a duplicate key")
        result[key] = value
    return result


def _reject_json_constant(_value: str) -> None:
    raise CreateRequestError("JSON document contains a non-finite number")


def _strict_json_loads(text: str) -> Any:
    try:
        return json.loads(
            text,
            object_pairs_hook=_unique_json_object,
            parse_constant=_reject_json_constant,
        )
    except json.JSONDecodeError as exc:
        raise CreateRequestError("Required JSON evidence is invalid") from exc


def _load_bounded_json(
    path: Path,
    *,
    max_bytes: int = MAX_CREATE_REQUEST_BYTES,
) -> dict[str, Any]:
    sha256_path(path, max_bytes=max_bytes)
    try:
        payload = _strict_json_loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError) as exc:
        raise CreateRequestError("Required JSON evidence is invalid") from exc
    if not isinstance(payload, dict):
        raise CreateRequestError("Required JSON evidence must contain one object")
    return payload


def _load_overrides(path: Path) -> tuple[dict[str, str], str, str]:
    file_sha256 = sha256_path(path, max_bytes=MAX_CREATE_OVERRIDES_BYTES)
    try:
        payload = _strict_json_loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError) as exc:
        raise CreateRequestError(f"Invalid create-request overrides JSON: {path}") from exc
    if not isinstance(payload, dict) or set(payload) != {"schema_version", "values"}:
        raise CreateRequestError(
            "Create-request overrides must contain exactly schema_version and values"
        )
    if payload.get("schema_version") != CREATE_REQUEST_OVERRIDES_SCHEMA:
        raise CreateRequestError(
            f"Create-request overrides require schema {CREATE_REQUEST_OVERRIDES_SCHEMA}"
        )
    values = payload.get("values")
    if not isinstance(values, dict) or not values:
        raise CreateRequestError("Create-request overrides values must be a non-empty object")
    actual_keys = set(values)
    if actual_keys != CREATE_REQUEST_OVERRIDE_KEYS:
        missing = sorted(CREATE_REQUEST_OVERRIDE_KEYS - actual_keys)
        unknown = sorted(actual_keys - CREATE_REQUEST_OVERRIDE_KEYS)
        details: list[str] = []
        if missing:
            details.append("missing=" + ",".join(missing))
        if unknown:
            details.append("unknown=" + ",".join(unknown))
        raise CreateRequestError(
            "Create-request overrides do not match the exact current schema: " + "; ".join(details)
        )
    normalized: dict[str, str] = {}
    for key in sorted(values):
        value = values[key]
        if not isinstance(value, str):
            raise CreateRequestError(f"Create-request override {key!r} must be a string")
        normalized_value = value.strip()
        if not normalized_value:
            raise CreateRequestError(f"Create-request override {key!r} must not be blank")
        if key in {"allowed_budget_users", "cost_center_allowed_users"}:
            entries = sorted(
                {entry.strip() for entry in normalized_value.split(",") if entry.strip()}
            )
            if not entries or any(any(char.isspace() for char in entry) for entry in entries):
                raise CreateRequestError(f"Create-request override {key!r} is invalid")
            normalized_value = ",".join(entries)
        normalized[key] = normalized_value
    if normalized["budget_amount"] != normalized["cost_center_monthly_cap_usd"]:
        raise CreateRequestError("budget_amount must exactly match cost_center_monthly_cap_usd")
    if normalized["allowed_budget_users"] != normalized["cost_center_allowed_users"]:
        raise CreateRequestError(
            "allowed_budget_users must exactly match cost_center_allowed_users"
        )
    try:
        from daylily_ec.aws.cost_centers import validate_cost_center_name
        from daylily_ec.workflow.create_cluster import validate_cluster_name

        validate_cluster_name(normalized["cluster_name"])
        validate_cost_center_name(normalized["cost_center_name"])
    except (RuntimeError, ValueError) as exc:
        raise CreateRequestError(str(exc)) from exc
    normalized_payload = {
        "schema_version": CREATE_REQUEST_OVERRIDES_SCHEMA,
        "values": normalized,
    }
    return normalized, file_sha256, _canonical_json_sha256(normalized_payload)


def _strict_source_config(
    config: Mapping[str, Any],
    *,
    overrides: Mapping[str, str],
    source_template_input: str,
) -> dict[str, list[str]]:
    current_keys = set(REQUIRED_CONFIG_KEYS)
    actual_keys = set(config)
    if actual_keys != current_keys:
        missing = sorted(current_keys - actual_keys)
        extra = sorted(actual_keys - current_keys)
        details: list[str] = []
        if missing:
            details.append("missing=" + ",".join(missing))
        if extra:
            details.append("extra=" + ",".join(extra))
        raise CreateRequestError(
            "Source create config does not match the exact current key schema: "
            + "; ".join(details)
        )
    rendered: dict[str, list[str]] = {}
    for key in REQUIRED_CONFIG_KEYS:
        if key == "cluster_template_yaml":
            value = source_template_input
        elif key in overrides:
            value = overrides[key]
        else:
            raw = config[key]
            if not isinstance(raw, list) or len(raw) != 3:
                raise CreateRequestError(
                    f"Source create config {key!r} must be an exact three-item triplet"
                )
            triplet = Triplet.model_validate(raw)
            if triplet.action != "USESETVALUE":
                raise CreateRequestError(
                    f"Source create config {key!r} must use USESETVALUE; defaults are forbidden"
                )
            value = triplet.set_value.strip()
        if not value and key not in CREATE_REQUEST_OPTIONAL_EMPTY_KEYS:
            raise CreateRequestError(
                f"Rendered create request {key!r} must have one explicit nonblank value"
            )
        rendered[key] = ["USESETVALUE", "", value]
    return rendered


def validate_strict_create_request_payload(payload: Mapping[str, Any]) -> None:
    if set(payload) != {"ephemeral_cluster", "dyec_create_request"}:
        raise CreateRequestError("Create request has unsupported or missing top-level fields")
    ephemeral_cluster = payload.get("ephemeral_cluster")
    if not isinstance(ephemeral_cluster, dict) or set(ephemeral_cluster) != {"config"}:
        raise CreateRequestError("Create request must contain only ephemeral_cluster.config")
    config = ephemeral_cluster.get("config")
    if not isinstance(config, dict) or set(config) != set(REQUIRED_CONFIG_KEYS):
        raise CreateRequestError("Create request config keys do not match the current schema")
    for key in REQUIRED_CONFIG_KEYS:
        raw = config[key]
        if not isinstance(raw, list) or len(raw) != 3:
            raise CreateRequestError(f"Create request {key!r} must be a three-item triplet")
        action, default_value, set_value = raw
        if action != "USESETVALUE" or default_value != "" or not isinstance(set_value, str):
            raise CreateRequestError(
                f"Create request {key!r} must be [USESETVALUE, '', <explicit string>]"
            )
        if not set_value and key not in CREATE_REQUEST_OPTIONAL_EMPTY_KEYS:
            raise CreateRequestError(f"Create request {key!r} must not be blank")
    metadata = payload.get("dyec_create_request")
    if not isinstance(metadata, dict) or set(metadata) != CREATE_REQUEST_METADATA_KEYS:
        raise CreateRequestError("Create request metadata does not match the current schema")


def _repository_credential_identity_from_mapping(
    config: Mapping[str, Any],
) -> tuple[list[str], str]:
    references: dict[str, str] = {}
    for key in REPOSITORY_CREDENTIAL_REFERENCE_KEYS:
        triplet = Triplet.model_validate(config.get(key))
        if triplet.action != "USESETVALUE" or not triplet.set_value.strip():
            raise CreateRequestError(
                f"Create request requires exact USESETVALUE repository reference {key!r}"
            )
        references[key] = triplet.set_value.strip()
    return list(REPOSITORY_CREDENTIAL_REFERENCE_KEYS), _canonical_json_sha256(references)


def repository_credential_identity_from_values(
    *,
    dayoa_policy_arn: str,
    dayoa_secret_arn: str,
    dyec_policy_arn: str,
    dyec_secret_arn: str,
) -> tuple[list[str], str]:
    references = {
        "dayoa_deploy_key_policy_arn": str(dayoa_policy_arn or "").strip(),
        "dayoa_deploy_key_secret_arn": str(dayoa_secret_arn or "").strip(),
        "dyec_deploy_key_policy_arn": str(dyec_policy_arn or "").strip(),
        "dyec_deploy_key_secret_arn": str(dyec_secret_arn or "").strip(),
    }
    if any(not value for value in references.values()):
        raise CreateRequestError("Repository credential references must all be nonblank")
    return list(REPOSITORY_CREDENTIAL_REFERENCE_KEYS), _canonical_json_sha256(references)


def require_dynamic_spot_policy(path: str | Path) -> None:
    candidate = Path(path).expanduser().resolve()
    payload = _load_bounded_yaml(candidate)
    queues = (payload.get("Scheduling") or {}).get("SlurmQueues") or []
    if not isinstance(queues, list) or not queues:
        raise CreateRequestError("Cluster template has no Slurm queue policy")
    spot_resources = 0
    for queue_index, queue in enumerate(queues):
        if not isinstance(queue, dict):
            raise CreateRequestError(f"Slurm queue {queue_index} is not an object")
        capacity_type = str(queue.get("CapacityType") or "").strip().upper()
        if capacity_type not in {"SPOT", "ONDEMAND"}:
            raise CreateRequestError(f"Slurm queue {queue_index} has unsupported CapacityType")
        resources = queue.get("ComputeResources") or []
        if not isinstance(resources, list) or not resources:
            raise CreateRequestError(f"Slurm queue {queue_index} has no compute resources")
        for resource_index, resource in enumerate(resources):
            if not isinstance(resource, dict):
                raise CreateRequestError(
                    f"Slurm queue {queue_index} resource {resource_index} is not an object"
                )
            has_price = "SpotPrice" in resource
            if capacity_type == "SPOT":
                spot_resources += 1
                if not has_price or resource.get("SpotPrice") != SPOT_PRICE_POLICY:
                    raise CreateRequestError(
                        f"Every SPOT compute resource must set SpotPrice: {SPOT_PRICE_POLICY}"
                    )
            elif has_price:
                raise CreateRequestError("ONDEMAND compute resources must not contain SpotPrice")
    if spot_resources < 1:
        raise CreateRequestError("Cluster template has no SPOT compute resources")


def require_priced_spot_policy(path: str | Path, *, maximum_bid: float) -> None:
    candidate = Path(path).expanduser().resolve()
    payload = _load_bounded_yaml(candidate)
    queues = (payload.get("Scheduling") or {}).get("SlurmQueues") or []
    if not isinstance(queues, list) or not queues:
        raise CreateRequestError("Priced cluster has no Slurm queue policy")
    spot_resources = 0
    for queue in queues:
        if not isinstance(queue, dict):
            raise CreateRequestError("Priced cluster Slurm queue is not an object")
        capacity_type = str(queue.get("CapacityType") or "").strip().upper()
        resources = queue.get("ComputeResources") or []
        if capacity_type not in {"SPOT", "ONDEMAND"} or not isinstance(resources, list):
            raise CreateRequestError("Priced cluster queue policy is invalid")
        for resource in resources:
            if not isinstance(resource, dict):
                raise CreateRequestError("Priced cluster compute resource is invalid")
            if capacity_type == "ONDEMAND":
                if "SpotPrice" in resource:
                    raise CreateRequestError(
                        "ONDEMAND compute resources must not contain SpotPrice"
                    )
                continue
            spot_resources += 1
            try:
                bid = float(resource["SpotPrice"])
            except (KeyError, TypeError, ValueError) as exc:
                raise CreateRequestError(
                    "Every SPOT compute resource requires one numeric SpotPrice"
                ) from exc
            if bid <= 0 or bid > maximum_bid:
                raise CreateRequestError("Priced SPOT bid is outside the approved limits")
    if spot_resources < 1:
        raise CreateRequestError("Priced cluster has no SPOT compute resources")


def render_create_request(
    *,
    source_config: str | Path,
    expected_source_config_sha256: str,
    source_template: str | Path,
    expected_source_template_sha256: str,
    overrides_json: str | Path,
    region_az: str,
    output_path: str | Path,
) -> dict[str, Any]:
    """Render one exact current-schema triplet request without AWS access."""

    from daylily_ec.aws.context import parse_region_az

    resolved_region_az = str(region_az or "").strip()
    parse_region_az(resolved_region_az)
    source_config_path = _resolve_input_path(
        source_config,
        label="source config",
        reject_symlink=True,
    )
    source_config_identity = _logical_input_identity(source_config, source_config_path)
    source_config_sha256 = sha256_path(source_config_path)
    if source_config_sha256 != _require_sha256(
        expected_source_config_sha256,
        label="expected source config SHA-256",
    ):
        raise CreateRequestError("Source config SHA-256 does not match the expected digest")
    source_payload = _load_bounded_yaml(source_config_path)
    if "dyec_create_request" in source_payload:
        raise CreateRequestError("Source config is already a rendered DYEC create request")
    if set(source_payload) != {"ephemeral_cluster"}:
        raise CreateRequestError("Source config contains unsupported top-level keys")
    ephemeral_cluster = source_payload.get("ephemeral_cluster")
    config = ephemeral_cluster.get("config") if isinstance(ephemeral_cluster, dict) else None
    if not isinstance(config, dict):
        raise CreateRequestError("Source config must define ephemeral_cluster.config")

    source_template_input = str(source_template or "").strip()
    if Path(source_template_input).expanduser().is_absolute():
        raise CreateRequestError(
            "source template must be an exact packaged DYEC resource path, not an absolute path"
        )
    source_template_path = _resolve_input_path(
        source_template_input,
        label="source template",
        reject_symlink=True,
    )
    source_template_identity = _logical_input_identity(source_template, source_template_path)
    source_template_sha256 = sha256_path(source_template_path)
    if source_template_sha256 != _require_sha256(
        expected_source_template_sha256,
        label="expected source template SHA-256",
    ):
        raise CreateRequestError("Source template SHA-256 does not match the expected digest")
    require_dynamic_spot_policy(source_template_path)

    overrides_path = require_protected_file(overrides_json, label="overrides JSON")
    overrides, overrides_file_sha256, overrides_sha256 = _load_overrides(overrides_path)
    rendered_config = _strict_source_config(
        config,
        overrides=overrides,
        source_template_input=source_template_input,
    )
    source_payload["ephemeral_cluster"] = {"config": rendered_config}
    credential_reference_keys, credential_references_sha256 = (
        _repository_credential_identity_from_mapping(rendered_config)
    )

    metadata = {
        "schema_version": CREATE_REQUEST_SCHEMA,
        "dyec_version": _dyec_version(),
        "region_az": resolved_region_az,
        "cluster_name": overrides["cluster_name"],
        "source_config_identity": source_config_identity,
        "source_config_sha256": source_config_sha256,
        "source_template_identity": source_template_identity,
        "source_template_sha256": source_template_sha256,
        "overrides_file_sha256": overrides_file_sha256,
        "overrides_sha256": overrides_sha256,
        "override_keys": sorted(overrides),
        "repository_credential_reference_keys": credential_reference_keys,
        "repository_credential_references_sha256": credential_references_sha256,
    }
    source_payload["dyec_create_request"] = metadata
    validate_strict_create_request_payload(source_payload)
    body = yaml.safe_dump(source_payload, sort_keys=False).encode("utf-8")
    if sha256_path(source_config_path) != source_config_sha256:
        raise CreateRequestError("Source config changed during request rendering")
    if sha256_path(source_template_path) != source_template_sha256:
        raise CreateRequestError("Source template changed during request rendering")
    if sha256_path(overrides_path, max_bytes=MAX_CREATE_OVERRIDES_BYTES) != overrides_file_sha256:
        raise CreateRequestError("Create-request overrides changed during rendering")
    destination = _require_absolute_output(output_path, label="output")
    created = True
    if destination.exists():
        try:
            existing = destination.read_bytes()
        except OSError as exc:
            raise CreateRequestError(f"Could not read existing output: {destination}") from exc
        if existing != body:
            raise CreateRequestError(
                f"Create-request output already exists with different content: {destination}"
            )
        require_protected_file(destination, label="existing create-request output")
        created = False
    else:
        _atomic_write_bytes(destination, body)
    require_protected_file(destination, label="create-request output")
    return {
        "schema_version": CREATE_REQUEST_SCHEMA,
        "dyec_version": _dyec_version(),
        "status": "rendered",
        "created": created,
        "region_az": resolved_region_az,
        "cluster_name": overrides["cluster_name"],
        "source_config_identity": source_config_identity,
        "source_config_sha256": source_config_sha256,
        "source_template_identity": source_template_identity,
        "source_template_sha256": source_template_sha256,
        "overrides_file_sha256": overrides_file_sha256,
        "overrides_sha256": overrides_sha256,
        "override_keys": sorted(overrides),
        "repository_credential_reference_keys": credential_reference_keys,
        "repository_credential_references_sha256": credential_references_sha256,
        "request_config_path": str(destination),
        "request_config_sha256": sha256_bytes(body),
    }


def _explicit_request_value(cfg: Any, key: str, *, allow_empty: bool = False) -> str:
    triplet = cfg.ephemeral_cluster.config.get(key)
    if triplet is None or triplet.action != "USESETVALUE":
        raise CreateRequestError(
            f"Rendered request requires {key!r} as an exact USESETVALUE triplet"
        )
    value = str(triplet.set_value or "").strip()
    if not value and not allow_empty:
        raise CreateRequestError(f"Rendered request requires a nonblank {key!r} value")
    return value


def _nonnegative_int(value: str, *, label: str) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise CreateRequestError(f"{label} must be an integer") from exc
    if result < 0:
        raise CreateRequestError(f"{label} must be nonnegative")
    return result


def _exact_create_substitutions(
    *,
    cfg: Any,
    aws_ctx: Any,
    region_az: str,
    write_spot_pricing_warn_threshold: float,
) -> tuple[dict[str, str], str]:
    from daylily_ec.aws.s3 import normalize_role_s3_uri
    from daylily_ec.aws.slurm_accounting import empty_slurm_accounting_render_blocks
    from daylily_ec.render.renderer import ALL_SUBSTITUTION_KEYS
    from daylily_ec.resources import resource_path
    from daylily_ec.workflow.create_cluster import cluster_boot_config_release_uri

    cluster_name = _explicit_request_value(cfg, "cluster_name")
    reference = normalize_role_s3_uri(
        _explicit_request_value(cfg, "reference_s3_uri"), role="reference"
    )
    control_data = normalize_role_s3_uri(
        _explicit_request_value(cfg, "control_data_s3_uri"), role="control_data"
    )
    staging = normalize_role_s3_uri(_explicit_request_value(cfg, "stage_s3_uri"), role="staging")
    export_destination = normalize_role_s3_uri(
        _explicit_request_value(cfg, "export_destination_s3_uri"),
        role="export_destination",
    )
    boot_base = f"{reference.uri.rstrip('/')}/runtime_assets/cluster_boot_config"
    boot_uri = cluster_boot_config_release_uri(
        base_uri=boot_base,
        source_dir=resource_path("config/day_cluster"),
    )
    max_8i = _nonnegative_int(_explicit_request_value(cfg, "max_count_8I"), label="max_count_8I")
    max_96i = _nonnegative_int(
        _explicit_request_value(cfg, "max_count_96I_NVME"), label="max_count_96I_NVME"
    )
    max_128i = _nonnegative_int(
        _explicit_request_value(cfg, "max_count_128I"), label="max_count_128I"
    )
    max_192i = _nonnegative_int(
        _explicit_request_value(cfg, "max_count_192I"), label="max_count_192I"
    )
    max_384i = _nonnegative_int(
        _explicit_request_value(cfg, "max_count_384I"), label="max_count_384I"
    )
    derived = {
        "max_count_128I_C": resolve_derived_max_count(cfg, "max_count_128I_C", max_128i),
        "max_count_128I_M": resolve_derived_max_count(cfg, "max_count_128I_M", max_128i),
        "max_count_128I_R": resolve_derived_max_count(cfg, "max_count_128I_R", max_128i),
        "max_count_128I_NVME": resolve_derived_max_count(cfg, "max_count_128I_NVME", max_128i),
        "max_count_192I_C": resolve_derived_max_count(cfg, "max_count_192I_C", max_192i),
        "max_count_192I_M": resolve_derived_max_count(cfg, "max_count_192I_M", max_192i),
        "max_count_192I_R": resolve_derived_max_count(cfg, "max_count_192I_R", max_192i),
        "max_count_192I_NVME_C": resolve_derived_max_count(cfg, "max_count_192I_NVME_C", max_192i),
        "max_count_192I_NVME_M": resolve_derived_max_count(cfg, "max_count_192I_NVME_M", max_192i),
        "max_count_192I_NVME_R": resolve_derived_max_count(cfg, "max_count_192I_NVME_R", max_192i),
        "max_count_192I_HUGENVME": resolve_derived_max_count(
            cfg, "max_count_192I_HUGENVME", max_192i
        ),
        "max_count_384I_NVME_C": resolve_derived_max_count(cfg, "max_count_384I_NVME_C", max_384i),
        "max_count_384I_NVME_M": resolve_derived_max_count(cfg, "max_count_384I_NVME_M", max_384i),
        "max_count_384I_NVME_R": resolve_derived_max_count(cfg, "max_count_384I_NVME_R", max_384i),
    }
    enforce_budget = _explicit_request_value(cfg, "enforce_budget").lower()
    if enforce_budget not in {"true", "false"}:
        raise CreateRequestError("enforce_budget must be exactly true or false")
    username = str(aws_ctx.iam_username or "").strip()
    if not username:
        raise CreateRequestError("AWS identity did not provide an IAM user/session name")
    substitutions = {
        "REGSUB_REGION": aws_ctx.region,
        "REGSUB_PUB_SUBNET": _explicit_request_value(cfg, "public_subnet_id"),
        "REGSUB_KEYNAME": "",
        "REGSUB_S3_BUCKET_INIT": boot_uri,
        "REGSUB_S3_IAM_POLICY": _explicit_request_value(cfg, "iam_policy_arn"),
        "REGSUB_PRIVATE_SUBNET": _explicit_request_value(cfg, "private_subnet_id"),
        "REGSUB_S3_REFERENCE_BUCKET": reference.bucket,
        "REGSUB_S3_CONTROL_DATA_BUCKET": control_data.bucket,
        "REGSUB_S3_STAGE_BUCKET": staging.bucket,
        "REGSUB_S3_EXPORT_BUCKET": export_destination.bucket,
        "REGSUB_S3_REFERENCE_URI": reference.uri.rstrip("/"),
        "REGSUB_S3_CONTROL_DATA_URI": control_data.uri.rstrip("/"),
        "REGSUB_S3_STAGE_URI": staging.uri.rstrip("/"),
        "REGSUB_FSX_SIZE": _explicit_request_value(cfg, "fsx_fs_size"),
        "REGSUB_DETAILED_MONITORING": _explicit_request_value(cfg, "enable_detailed_monitoring"),
        "REGSUB_CLUSTER_NAME": cluster_name,
        "REGSUB_USERNAME": username,
        "REGSUB_PROJECT": cluster_name,
        "REGSUB_DELETE_LOCAL_ROOT": _explicit_request_value(cfg, "delete_local_root"),
        "REGSUB_DRAGEN_PCLUSTER_AMI": "",
        "REGSUB_DRAGEN_LICENSE_POLICY_ARN": "",
        "REGSUB_DRAGEN_LICENSE_SECRET_ARN": "",
        "REGSUB_PCLUSTER_COOKBOOK_URI": "",
        "REGSUB_SAVE_FSX": "Delete",
        "REGSUB_ENFORCE_BUDGET": json.dumps(enforce_budget),
        "REGSUB_COST_CENTER_REGION": "us-west-2",
        "REGSUB_COST_CENTER_TABLE": "dayec-cost-centers",
        "REGSUB_COST_CENTER_USAGE_TABLE": "dayec-cost-center-usage",
        "REGSUB_AWS_ACCOUNT_ID": f"aws_profile-{aws_ctx.profile}",
        "REGSUB_ALLOCATION_STRATEGY": _explicit_request_value(
            cfg, "spot_instance_allocation_strategy"
        ),
        "REGSUB_DAYLILY_GIT_DEETS": "none",
        "REGSUB_MAX_COUNT_8I": str(max_8i),
        "REGSUB_MAX_COUNT_96I_NVME": str(max_96i),
        "REGSUB_MAX_COUNT_128I": str(max_128i),
        "REGSUB_MAX_COUNT_192I": str(max_192i),
        "REGSUB_MAX_COUNT_384I": str(max_384i),
        "REGSUB_MAX_COUNT_128I_C": derived["max_count_128I_C"],
        "REGSUB_MAX_COUNT_128I_M": derived["max_count_128I_M"],
        "REGSUB_MAX_COUNT_128I_R": derived["max_count_128I_R"],
        "REGSUB_MAX_COUNT_128I_NVME": derived["max_count_128I_NVME"],
        "REGSUB_MAX_COUNT_192I_C": derived["max_count_192I_C"],
        "REGSUB_MAX_COUNT_192I_M": derived["max_count_192I_M"],
        "REGSUB_MAX_COUNT_192I_R": derived["max_count_192I_R"],
        "REGSUB_MAX_COUNT_192I_NVME_C": derived["max_count_192I_NVME_C"],
        "REGSUB_MAX_COUNT_192I_NVME_M": derived["max_count_192I_NVME_M"],
        "REGSUB_MAX_COUNT_192I_NVME_R": derived["max_count_192I_NVME_R"],
        "REGSUB_MAX_COUNT_192I_HUGENVME": derived["max_count_192I_HUGENVME"],
        "REGSUB_MAX_COUNT_384I_NVME_C": derived["max_count_384I_NVME_C"],
        "REGSUB_MAX_COUNT_384I_NVME_M": derived["max_count_384I_NVME_M"],
        "REGSUB_MAX_COUNT_384I_NVME_R": derived["max_count_384I_NVME_R"],
        "REGSUB_HEADNODE_INSTANCE_TYPE": _explicit_request_value(cfg, "headnode_instance_type"),
        "REGSUB_HEARTBEAT_EMAIL": _explicit_request_value(cfg, "heartbeat_email"),
        "REGSUB_HEARTBEAT_SCHEDULE": _explicit_request_value(cfg, "heartbeat_schedule"),
        "REGSUB_HEARTBEAT_SCHEDULER_ROLE_ARN": _explicit_request_value(
            cfg, "heartbeat_scheduler_role_arn", allow_empty=True
        ),
        "REGSUB_SPOT_PRICE_WARN_THRESHOLD": json.dumps(f"{write_spot_pricing_warn_threshold:.2f}"),
        **empty_slurm_accounting_render_blocks(),
    }
    return {key: str(substitutions.get(key, "")) for key in ALL_SUBSTITUTION_KEYS}, boot_uri


def _validate_request_metadata(
    *,
    request_payload: Mapping[str, Any],
    request_config_path: Path,
    expected_request_sha256: str,
    source_template_path: Path,
    expected_source_template_sha256: str,
    region_az: str,
) -> tuple[dict[str, Any], str, str]:
    validate_strict_create_request_payload(request_payload)
    request_sha256 = sha256_path(request_config_path)
    if request_sha256 != _require_sha256(
        expected_request_sha256,
        label="expected request SHA-256",
    ):
        raise CreateRequestError("Rendered request SHA-256 does not match the expected digest")
    metadata = request_payload.get("dyec_create_request")
    if not isinstance(metadata, dict) or metadata.get("schema_version") != CREATE_REQUEST_SCHEMA:
        raise CreateRequestError(
            f"Rendered request must contain exact {CREATE_REQUEST_SCHEMA} metadata"
        )
    if metadata.get("dyec_version") != _dyec_version():
        raise CreateRequestError("Rendered request DYEC version does not match this executable")
    if str(metadata.get("region_az") or "") != region_az:
        raise CreateRequestError("Rendered request availability zone does not match")
    template_sha256 = sha256_path(source_template_path)
    expected_template_sha256 = _require_sha256(
        expected_source_template_sha256,
        label="expected source template SHA-256",
    )
    if template_sha256 != expected_template_sha256:
        raise CreateRequestError("Source template SHA-256 does not match the expected digest")
    if str(metadata.get("source_template_sha256") or "") != template_sha256:
        raise CreateRequestError("Rendered request metadata does not bind the source template")
    for digest_key in (
        "source_config_sha256",
        "source_template_sha256",
        "overrides_file_sha256",
        "overrides_sha256",
        "repository_credential_references_sha256",
    ):
        _require_sha256(str(metadata.get(digest_key) or ""), label=digest_key)
    config_root = request_payload.get("ephemeral_cluster")
    config = config_root.get("config") if isinstance(config_root, dict) else None
    if not isinstance(config, dict):
        raise CreateRequestError("Rendered request is missing ephemeral_cluster.config")
    configured_template_input = Triplet.model_validate(
        config.get("cluster_template_yaml")
    ).set_value
    configured_template = _resolve_input_path(
        configured_template_input,
        label="configured source template",
        reject_symlink=True,
    )
    configured_identity = _logical_input_identity(
        configured_template_input,
        configured_template,
    )
    if configured_identity != metadata.get("source_template_identity"):
        raise CreateRequestError("Rendered request source-template identity does not match")
    if sha256_path(configured_template) != template_sha256:
        raise CreateRequestError("Packaged source-template bytes do not match request metadata")
    override_keys = metadata.get("override_keys")
    if (
        not isinstance(override_keys, list)
        or any(not isinstance(key, str) for key in override_keys)
        or override_keys != sorted(set(override_keys))
        or set(override_keys) != CREATE_REQUEST_OVERRIDE_KEYS
    ):
        raise CreateRequestError("Rendered request metadata has invalid override key identity")
    loaded_request = load_config(request_config_path)
    normalized_overrides = {
        key: _explicit_request_value(loaded_request, key) for key in override_keys
    }
    if normalized_overrides["cluster_name"] != str(metadata.get("cluster_name") or ""):
        raise CreateRequestError("Rendered request cluster identity does not match")
    normalized_payload = {
        "schema_version": CREATE_REQUEST_OVERRIDES_SCHEMA,
        "values": normalized_overrides,
    }
    if str(metadata.get("overrides_sha256") or "") != _canonical_json_sha256(normalized_payload):
        raise CreateRequestError("Rendered request normalized overrides digest does not match")
    for identity_key in ("source_config_identity", "source_template_identity"):
        identity = str(metadata.get(identity_key) or "")
        if (
            not identity
            or len(identity) > 300
            or any(character in identity for character in "\r\n\x00")
            or not identity.startswith(("dyec-resource:", "external-file:"))
        ):
            raise CreateRequestError(f"Rendered request {identity_key} is invalid")
    credential_keys, credential_sha256 = _repository_credential_identity_from_mapping(config)
    if metadata.get("repository_credential_reference_keys") != credential_keys:
        raise CreateRequestError("Rendered request repository credential key identity is invalid")
    if metadata.get("repository_credential_references_sha256") != credential_sha256:
        raise CreateRequestError("Rendered request repository credential digest does not match")
    return dict(metadata), request_sha256, template_sha256


def _price_effective_cluster(
    *,
    effective_path: Path,
    priced_path: Path,
    summary_path: Path,
    region_az: str,
    ec2_client: Any,
    global_spot_max_cost: float,
    spot_cost_limit_pct: float,
    write_spot_pricing_warn_threshold: float,
) -> dict[str, Any]:
    require_dynamic_spot_policy(effective_path)
    priced_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    _require_protected_directory(priced_path.parent, label="pricing output directory")
    descriptor, temporary_priced_name = tempfile.mkstemp(
        prefix=f".{priced_path.name}.", suffix=".tmp", dir=str(priced_path.parent)
    )
    os.close(descriptor)
    temporary_priced = Path(temporary_priced_name)
    descriptor, temporary_summary_name = tempfile.mkstemp(
        prefix=f".{summary_path.name}.", suffix=".tmp", dir=str(summary_path.parent)
    )
    os.close(descriptor)
    temporary_summary = Path(temporary_summary_name)
    try:
        summary = apply_spot_prices(
            str(effective_path),
            str(temporary_priced),
            region_az,
            ec2_client=ec2_client,
            global_spot_max_cost=global_spot_max_cost,
            spot_cost_limit_pct=spot_cost_limit_pct,
            write_spot_pricing_warn_threshold=write_spot_pricing_warn_threshold,
            summary_output_path=temporary_summary,
        )
        os.chmod(temporary_priced, 0o600)
        os.chmod(temporary_summary, 0o600)
        os.replace(temporary_priced, priced_path)
        os.replace(temporary_summary, summary_path)
        require_priced_spot_policy(priced_path, maximum_bid=global_spot_max_cost)
        return summary
    finally:
        if temporary_priced.exists():
            temporary_priced.unlink()
        if temporary_summary.exists():
            temporary_summary.unlink()


def _observation_window(summary: Mapping[str, Any]) -> dict[str, Any]:
    observed_at: list[str] = []
    maximum_age_seconds = 0.0
    for resource in summary.get("resources", []):
        if not isinstance(resource, dict):
            raise CreateRequestError("Spot pricing summary resource evidence is invalid")
        observations = resource.get("spot_price_observations")
        if not isinstance(observations, list) or not observations:
            raise CreateRequestError("Spot pricing summary has no timestamped observations")
        for observation in observations:
            if not isinstance(observation, dict):
                raise CreateRequestError("Spot pricing observation evidence is invalid")
            timestamp = str(observation.get("observed_at") or "")
            try:
                age_seconds = float(observation.get("age_seconds"))
            except (TypeError, ValueError) as exc:
                raise CreateRequestError("Spot pricing observation age is invalid") from exc
            if not timestamp:
                raise CreateRequestError("Spot pricing observation timestamp is missing")
            observed_at.append(timestamp)
            maximum_age_seconds = max(maximum_age_seconds, age_seconds)
    if not observed_at:
        raise CreateRequestError("Spot pricing summary has no observation window")
    return {
        "earliest_observed_at": min(observed_at),
        "latest_observed_at": max(observed_at),
        "maximum_observation_age_seconds": round(maximum_age_seconds, 3),
        "observation_count": len(observed_at),
    }


def _pricing_source(
    *,
    summary: Mapping[str, Any],
    captured_at: str,
    freshness: str,
) -> dict[str, Any]:
    observation_policy = summary.get("observation_policy")
    expected_policy = {
        "maximum_age_seconds": MAX_SPOT_OBSERVATION_AGE_SECONDS,
        "maximum_future_skew_seconds": MAX_SPOT_OBSERVATION_FUTURE_SKEW_SECONDS,
    }
    if observation_policy != expected_policy:
        raise CreateRequestError("Spot pricing observation policy is not the exact current policy")
    return {
        "service": "ec2",
        "operation": "DescribeSpotPriceHistory",
        "selection": "latest Linux/UNIX observation per instance type and availability zone",
        "freshness": freshness,
        "captured_at": captured_at,
        **expected_policy,
        **_observation_window(summary),
    }


def _validate_pricing_source_and_result(
    *,
    source: Any,
    result: Any,
    captured_at: str,
    region_az: str,
    expected_freshness: str,
) -> None:
    if not isinstance(result, dict):
        raise CreateRequestError("Pricing receipt result is invalid")
    expected_source = _pricing_source(
        summary=result,
        captured_at=captured_at,
        freshness=expected_freshness,
    )
    if source != expected_source:
        raise CreateRequestError("Pricing receipt source/freshness evidence is invalid")
    if result.get("schema_version") != "dyec.spot_price_summary.v1":
        raise CreateRequestError("Pricing receipt summary schema is invalid")
    if result.get("availability_zone") != region_az:
        raise CreateRequestError("Pricing receipt summary availability zone does not match")


def prepare_create_request(
    *,
    request_config: str | Path,
    expected_request_sha256: str,
    source_template: str | Path,
    expected_source_template_sha256: str,
    profile: str,
    region_az: str,
    spot_price_policy: str,
    output_dir: str | Path,
    global_spot_max_cost: float = DEFAULT_GLOBAL_SPOT_MAX_COST,
    spot_cost_limit_pct: float = DEFAULT_SPOT_COST_LIMIT_PCT,
    write_spot_pricing_warn_threshold: float = DEFAULT_WRITE_SPOT_PRICING_WARN_THRESHOLD,
) -> dict[str, Any]:
    """Create a read-only, live-priced admission receipt for one request."""

    from daylily_ec.aws.context import AWSContext, parse_region_az
    from daylily_ec.render.renderer import REQUIRED_KEYS, render_template
    from daylily_ec.workflow.create_cluster import (
        attach_headnode_managed_policy,
        resolve_dayoa_deploy_key_inputs,
        resolve_dyec_deploy_key_inputs,
    )

    resolved_profile = str(profile or "").strip()
    if not resolved_profile:
        raise CreateRequestError("profile is required")
    resolved_region_az = str(region_az or "").strip()
    region, _az = parse_region_az(resolved_region_az)
    if spot_price_policy != SPOT_PRICE_POLICY:
        raise CreateRequestError(f"spot price policy must be exactly {SPOT_PRICE_POLICY}")
    global_max, pct, warn_threshold = validate_spot_pricing_limits(
        global_spot_max_cost=global_spot_max_cost,
        spot_cost_limit_pct=spot_cost_limit_pct,
        write_spot_pricing_warn_threshold=write_spot_pricing_warn_threshold,
    )
    request_path = require_protected_file(request_config, label="request config")
    request_payload = _load_bounded_yaml(request_path)
    template_path = _resolve_input_path(
        source_template,
        label="source template",
        reject_symlink=True,
    )
    metadata, request_sha256, template_sha256 = _validate_request_metadata(
        request_payload=request_payload,
        request_config_path=request_path,
        expected_request_sha256=expected_request_sha256,
        source_template_path=template_path,
        expected_source_template_sha256=expected_source_template_sha256,
        region_az=resolved_region_az,
    )
    require_dynamic_spot_policy(template_path)
    destination = _require_absolute_output(output_dir, label="output directory")
    destination.mkdir(parents=True, exist_ok=True, mode=0o700)
    _require_protected_directory(destination, label="output directory")
    effective_path = destination / "effective-cluster.yaml"
    priced_path = destination / "priced-cluster.yaml"
    summary_path = destination / "spot-price-summary.json"
    receipt_path = destination / "create-preparation.json"
    started_at = utc_now_iso()
    _atomic_write_json(
        receipt_path,
        {
            "schema_version": CREATE_PREPARATION_SCHEMA,
            "dyec_version": _dyec_version(),
            "status": "in_progress",
            "phase": "identity_resolution",
            "captured_at": started_at,
            "profile": resolved_profile,
            "region": region,
            "region_az": resolved_region_az,
            "cluster_name": str(metadata["cluster_name"]),
            "source_config_identity": str(metadata["source_config_identity"]),
            "source_config_sha256": str(metadata["source_config_sha256"]),
            "request_config_sha256": request_sha256,
            "source_template_identity": str(metadata["source_template_identity"]),
            "source_template_sha256": template_sha256,
            "overrides_file_sha256": str(metadata["overrides_file_sha256"]),
            "overrides_sha256": str(metadata["overrides_sha256"]),
            "override_keys": list(metadata["override_keys"]),
            "repository_credential_reference_keys": list(
                metadata["repository_credential_reference_keys"]
            ),
            "repository_credential_references_sha256": str(
                metadata["repository_credential_references_sha256"]
            ),
            "spot_price_policy": SPOT_PRICE_POLICY,
        },
    )
    try:
        try:
            aws_ctx = AWSContext.build(resolved_region_az, profile=resolved_profile)
        except RuntimeError as exc:
            raise CreateRequestError(
                "The exact AWS profile/account identity could not be resolved for preparation"
            ) from exc
        if aws_ctx.region != region or aws_ctx.profile != resolved_profile:
            raise CreateRequestError("AWS context identity does not match the exact request")
        cfg = load_config(request_path)
        dayoa_deploy_key = resolve_dayoa_deploy_key_inputs(
            cfg,
            region_az=resolved_region_az,
            account_id=aws_ctx.account_id,
            non_interactive=True,
        )
        dyec_deploy_key = resolve_dyec_deploy_key_inputs(
            cfg,
            region_az=resolved_region_az,
            account_id=aws_ctx.account_id,
            non_interactive=True,
        )
        credential_keys, credential_sha256 = repository_credential_identity_from_values(
            dayoa_policy_arn=dayoa_deploy_key.policy_arn,
            dayoa_secret_arn=dayoa_deploy_key.secret_arn,
            dyec_policy_arn=dyec_deploy_key.policy_arn,
            dyec_secret_arn=dyec_deploy_key.secret_arn,
        )
        if (
            metadata["repository_credential_reference_keys"] != credential_keys
            or metadata["repository_credential_references_sha256"] != credential_sha256
        ):
            raise CreateRequestError("Repository credential reference identity changed")
        configured_template_input = _explicit_request_value(cfg, "cluster_template_yaml")
        configured_template = _resolve_input_path(
            configured_template_input,
            label="configured source template",
            reject_symlink=True,
        )
        if sha256_path(configured_template) != template_sha256:
            raise CreateRequestError("Request config selects different source-template bytes")
        substitutions, _cluster_boot_s3_uri = _exact_create_substitutions(
            cfg=cfg,
            aws_ctx=aws_ctx,
            region_az=resolved_region_az,
            write_spot_pricing_warn_threshold=warn_threshold,
        )
        rendered = render_template(
            template_path.read_text(encoding="utf-8"),
            substitutions,
            required_keys=REQUIRED_KEYS,
        )
        descriptor, temporary_effective_name = tempfile.mkstemp(
            prefix=f".{effective_path.name}.", suffix=".tmp", dir=str(destination)
        )
        os.close(descriptor)
        temporary_effective = Path(temporary_effective_name)
        try:
            temporary_effective.write_text(rendered, encoding="utf-8")
            attach_headnode_managed_policy(
                temporary_effective,
                dayoa_deploy_key.policy_arn,
            )
            attach_headnode_managed_policy(
                temporary_effective,
                dyec_deploy_key.policy_arn,
            )
            os.chmod(temporary_effective, 0o600)
            os.replace(temporary_effective, effective_path)
        finally:
            if temporary_effective.exists():
                temporary_effective.unlink()
        summary = _price_effective_cluster(
            effective_path=effective_path,
            priced_path=priced_path,
            summary_path=summary_path,
            region_az=resolved_region_az,
            ec2_client=aws_ctx.client("ec2"),
            global_spot_max_cost=global_max,
            spot_cost_limit_pct=pct,
            write_spot_pricing_warn_threshold=warn_threshold,
        )
        captured_at = utc_now_iso()
        pricing_source = _pricing_source(
            summary=summary,
            captured_at=captured_at,
            freshness="queried live during this preparation",
        )
        unpriced_cluster_sha256 = sha256_path(effective_path)
        admission_priced_cluster_sha256 = sha256_path(priced_path)
        receipt = {
            "schema_version": CREATE_PREPARATION_SCHEMA,
            "dyec_version": _dyec_version(),
            "status": "complete",
            "phase": "admission",
            "captured_at": captured_at,
            "profile": resolved_profile,
            "account_id": aws_ctx.account_id,
            "region": region,
            "region_az": resolved_region_az,
            "cluster_name": _explicit_request_value(cfg, "cluster_name"),
            "spot_price_policy": SPOT_PRICE_POLICY,
            "pricing_limits": {
                "global_spot_max_cost": global_max,
                "spot_cost_limit_pct": pct,
                "write_spot_pricing_warn_threshold": warn_threshold,
            },
            "pricing_source": pricing_source,
            "source_config_sha256": str(metadata["source_config_sha256"]),
            "source_config_identity": str(metadata["source_config_identity"]),
            "request_config_sha256": request_sha256,
            "source_template_identity": str(metadata["source_template_identity"]),
            "source_template_sha256": template_sha256,
            "overrides_file_sha256": str(metadata["overrides_file_sha256"]),
            "overrides_sha256": str(metadata["overrides_sha256"]),
            "override_keys": list(metadata["override_keys"]),
            "repository_credential_reference_keys": list(
                metadata["repository_credential_reference_keys"]
            ),
            "repository_credential_references_sha256": str(
                metadata["repository_credential_references_sha256"]
            ),
            "unpriced_cluster_config_sha256": unpriced_cluster_sha256,
            "admission_priced_cluster_config_sha256": (admission_priced_cluster_sha256),
            "artifacts": {
                "effective_cluster": _artifact_identity(effective_path),
                "priced_cluster": _artifact_identity(priced_path),
                "spot_price_summary": _artifact_identity(summary_path),
            },
            "pricing_result": summary,
        }
        if sha256_path(request_path) != request_sha256:
            raise CreateRequestError("Rendered request changed during preparation")
        if sha256_path(template_path) != template_sha256:
            raise CreateRequestError("Source template changed during preparation")
        _atomic_write_json(receipt_path, receipt)
        return {
            **receipt,
            "receipt_path": str(receipt_path),
            "receipt_sha256": sha256_path(receipt_path),
        }
    except Exception:
        _atomic_write_json(
            receipt_path,
            {
                "schema_version": CREATE_PREPARATION_SCHEMA,
                "dyec_version": _dyec_version(),
                "status": "failed",
                "phase": "admission",
                "captured_at": utc_now_iso(),
                "profile": resolved_profile,
                "region": region,
                "region_az": resolved_region_az,
                "cluster_name": str(metadata["cluster_name"]),
                "source_config_identity": str(metadata["source_config_identity"]),
                "source_config_sha256": str(metadata["source_config_sha256"]),
                "request_config_sha256": request_sha256,
                "source_template_identity": str(metadata["source_template_identity"]),
                "source_template_sha256": template_sha256,
                "spot_price_policy": SPOT_PRICE_POLICY,
                "error_code": "create_preparation_failed",
            },
        )
        raise


def load_verified_preparation_receipt(
    *,
    receipt_path: str | Path,
    expected_receipt_sha256: str,
    request_config_path: str | Path,
    source_template_path: str | Path,
    profile: str,
    account_id: str,
    region_az: str,
    global_spot_max_cost: float,
    spot_cost_limit_pct: float,
    write_spot_pricing_warn_threshold: float,
) -> dict[str, Any]:
    """Verify optional admission evidence without reusing its numeric prices."""

    receipt = require_protected_file(receipt_path, label="preparation receipt")
    receipt_sha256 = sha256_path(receipt)
    if receipt_sha256 != _require_sha256(
        expected_receipt_sha256,
        label="expected preparation receipt SHA-256",
    ):
        raise CreateRequestError("Preparation receipt SHA-256 does not match")
    payload = _load_bounded_json(receipt)
    expected_keys = {
        "account_id",
        "admission_priced_cluster_config_sha256",
        "artifacts",
        "captured_at",
        "cluster_name",
        "dyec_version",
        "override_keys",
        "overrides_file_sha256",
        "overrides_sha256",
        "phase",
        "pricing_limits",
        "pricing_result",
        "pricing_source",
        "profile",
        "region",
        "region_az",
        "repository_credential_reference_keys",
        "repository_credential_references_sha256",
        "request_config_sha256",
        "schema_version",
        "source_config_identity",
        "source_config_sha256",
        "source_template_identity",
        "source_template_sha256",
        "spot_price_policy",
        "status",
        "unpriced_cluster_config_sha256",
    }
    if set(payload) != expected_keys:
        raise CreateRequestError("Preparation receipt fields do not match the current schema")
    if payload.get("schema_version") != CREATE_PREPARATION_SCHEMA:
        raise CreateRequestError(f"Preparation receipt must use {CREATE_PREPARATION_SCHEMA}")
    if payload.get("status") != "complete" or payload.get("phase") != "admission":
        raise CreateRequestError("Preparation receipt is not terminally complete")
    if payload.get("dyec_version") != _dyec_version():
        raise CreateRequestError("Preparation receipt DYEC version does not match create")
    captured_at = str(payload.get("captured_at") or "")
    try:
        captured = datetime.fromisoformat(captured_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CreateRequestError("Preparation receipt capture time is invalid") from exc
    if captured.tzinfo is None:
        raise CreateRequestError("Preparation receipt capture time must include a timezone")
    age_seconds = (datetime.now(timezone.utc) - captured.astimezone(timezone.utc)).total_seconds()
    if age_seconds < -MAX_PREPARATION_RECEIPT_FUTURE_SKEW_SECONDS:
        raise CreateRequestError("Preparation receipt capture time is too far in the future")
    if age_seconds > MAX_PREPARATION_RECEIPT_AGE_SECONDS:
        raise CreateRequestError("Preparation receipt is older than the admission bound")
    request = require_protected_file(request_config_path, label="request config")
    template = _resolve_input_path(
        source_template_path,
        label="source template",
        reject_symlink=True,
    )
    from daylily_ec.aws.context import parse_region_az

    resolved_region_az = str(region_az or "").strip()
    region, _az = parse_region_az(resolved_region_az)
    request_payload = _load_bounded_yaml(request)
    metadata, request_sha256, template_sha256 = _validate_request_metadata(
        request_payload=request_payload,
        request_config_path=request,
        expected_request_sha256=sha256_path(request),
        source_template_path=template,
        expected_source_template_sha256=sha256_path(template),
        region_az=resolved_region_az,
    )
    exact_values = {
        "profile": str(profile or "").strip(),
        "account_id": str(account_id or "").strip(),
        "region": region,
        "region_az": resolved_region_az,
        "cluster_name": str(metadata["cluster_name"]),
        "source_config_identity": str(metadata["source_config_identity"]),
        "request_config_sha256": request_sha256,
        "source_config_sha256": str(metadata["source_config_sha256"]),
        "source_template_identity": str(metadata["source_template_identity"]),
        "source_template_sha256": template_sha256,
        "overrides_file_sha256": str(metadata["overrides_file_sha256"]),
        "overrides_sha256": str(metadata["overrides_sha256"]),
        "override_keys": list(metadata["override_keys"]),
        "repository_credential_reference_keys": list(
            metadata["repository_credential_reference_keys"]
        ),
        "repository_credential_references_sha256": str(
            metadata["repository_credential_references_sha256"]
        ),
        "spot_price_policy": SPOT_PRICE_POLICY,
    }
    for key, expected in exact_values.items():
        if payload.get(key) != expected:
            raise CreateRequestError(f"Preparation receipt {key} does not match create")
    global_max, pct, warn = validate_spot_pricing_limits(
        global_spot_max_cost=global_spot_max_cost,
        spot_cost_limit_pct=spot_cost_limit_pct,
        write_spot_pricing_warn_threshold=write_spot_pricing_warn_threshold,
    )
    if payload.get("pricing_limits") != {
        "global_spot_max_cost": global_max,
        "spot_cost_limit_pct": pct,
        "write_spot_pricing_warn_threshold": warn,
    }:
        raise CreateRequestError("Preparation receipt pricing limits do not match create")
    artifacts = payload.get("artifacts")
    if not isinstance(artifacts, dict) or set(artifacts) != {
        "effective_cluster",
        "priced_cluster",
        "spot_price_summary",
    }:
        raise CreateRequestError("Preparation receipt artifact inventory is invalid")
    for label, artifact in artifacts.items():
        _verify_artifact_identity(receipt.parent, artifact, label=label)
    effective_artifact = artifacts["effective_cluster"]
    priced_artifact = artifacts["priced_cluster"]
    if payload.get("unpriced_cluster_config_sha256") != effective_artifact.get("sha256"):
        raise CreateRequestError("Preparation receipt unpriced digest does not match")
    if payload.get("admission_priced_cluster_config_sha256") != priced_artifact.get("sha256"):
        raise CreateRequestError("Preparation receipt priced digest does not match")
    require_dynamic_spot_policy(receipt.parent / str(effective_artifact["name"]))
    require_priced_spot_policy(
        receipt.parent / str(priced_artifact["name"]),
        maximum_bid=global_max,
    )
    pricing_result = payload.get("pricing_result")
    _validate_pricing_source_and_result(
        source=payload.get("pricing_source"),
        result=pricing_result,
        captured_at=captured_at,
        region_az=resolved_region_az,
        expected_freshness="queried live during this preparation",
    )
    summary_artifact = artifacts["spot_price_summary"]
    summary_payload = _load_bounded_json(receipt.parent / str(summary_artifact["name"]))
    if summary_payload != pricing_result:
        raise CreateRequestError("Preparation receipt pricing result does not match its artifact")
    return payload


def price_create_input_and_write_receipt(
    *,
    effective_path: str | Path,
    priced_path: str | Path,
    summary_path: str | Path,
    receipt_path: str | Path,
    request_config_path: str | Path,
    source_template_path: str | Path,
    profile: str,
    account_id: str,
    region: str,
    region_az: str,
    cluster_name: str,
    repository_credential_reference_keys: list[str],
    repository_credential_references_sha256: str,
    ec2_client: Any,
    global_spot_max_cost: float,
    spot_cost_limit_pct: float,
    write_spot_pricing_warn_threshold: float,
    admission_receipt_path: str | Path | None = None,
    admission_receipt_sha256: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Reprice the actual create input and durably receipt that fresh result."""

    effective = require_protected_file(effective_path, label="effective cluster input")
    priced = Path(priced_path).expanduser().resolve()
    summary_file = Path(summary_path).expanduser().resolve()
    receipt_file = Path(receipt_path).expanduser().resolve()
    request_file = require_protected_file(request_config_path, label="request config")
    template_file = _resolve_input_path(
        source_template_path,
        label="source template",
        reject_symlink=True,
    )
    request_sha256 = sha256_path(request_file)
    template_sha256 = sha256_path(template_file)
    request_payload = _load_bounded_yaml(request_file)
    validated_metadata, request_sha256, template_sha256 = _validate_request_metadata(
        request_payload=request_payload,
        request_config_path=request_file,
        expected_request_sha256=request_sha256,
        source_template_path=template_file,
        expected_source_template_sha256=template_sha256,
        region_az=region_az,
    )
    request_identity = {
        "source_config_identity": validated_metadata["source_config_identity"],
        "source_config_sha256": validated_metadata["source_config_sha256"],
        "source_template_identity": validated_metadata["source_template_identity"],
        "overrides_file_sha256": validated_metadata["overrides_file_sha256"],
        "overrides_sha256": validated_metadata["overrides_sha256"],
        "override_keys": list(validated_metadata["override_keys"]),
    }
    if (
        validated_metadata["repository_credential_reference_keys"]
        != repository_credential_reference_keys
        or validated_metadata["repository_credential_references_sha256"]
        != repository_credential_references_sha256
    ):
        raise CreateRequestError(
            "Create request repository credential identity changed before pricing"
        )
    global_max, pct, warn = validate_spot_pricing_limits(
        global_spot_max_cost=global_spot_max_cost,
        spot_cost_limit_pct=spot_cost_limit_pct,
        write_spot_pricing_warn_threshold=write_spot_pricing_warn_threshold,
    )
    if (admission_receipt_path is None) != (admission_receipt_sha256 is None):
        raise CreateRequestError("Admission receipt path and SHA-256 must be supplied together")
    normalized_admission_sha256 = (
        _require_sha256(
            str(admission_receipt_sha256 or ""),
            label="admission receipt SHA-256",
        )
        if admission_receipt_path is not None
        else None
    )
    unpriced_cluster_sha256 = sha256_path(effective)
    captured_at = utc_now_iso()
    _atomic_write_json(
        receipt_file,
        {
            "schema_version": CREATE_PRICING_RECEIPT_SCHEMA,
            "dyec_version": _dyec_version(),
            "status": "in_progress",
            "phase": "pre_create",
            "captured_at": captured_at,
            "cluster_name": cluster_name,
            "profile": profile,
            "account_id": account_id,
            "region": region,
            "region_az": region_az,
            "request_config_sha256": request_sha256,
            "source_template_sha256": template_sha256,
            "repository_credential_reference_keys": repository_credential_reference_keys,
            "repository_credential_references_sha256": (repository_credential_references_sha256),
        },
    )
    summary = _price_effective_cluster(
        effective_path=effective,
        priced_path=priced,
        summary_path=summary_file,
        region_az=region_az,
        ec2_client=ec2_client,
        global_spot_max_cost=global_max,
        spot_cost_limit_pct=pct,
        write_spot_pricing_warn_threshold=warn,
    )
    require_priced_spot_policy(priced, maximum_bid=global_max)
    final_cluster_sha256 = sha256_path(priced)
    captured_at = utc_now_iso()
    pricing_source = _pricing_source(
        summary=summary,
        captured_at=captured_at,
        freshness="queried live immediately before provider dry-run/create",
    )
    receipt = {
        "schema_version": CREATE_PRICING_RECEIPT_SCHEMA,
        "dyec_version": _dyec_version(),
        "status": "complete",
        "phase": "pre_create",
        "captured_at": captured_at,
        "cluster_name": cluster_name,
        "profile": profile,
        "account_id": account_id,
        "region": region,
        "region_az": region_az,
        "spot_price_policy": SPOT_PRICE_POLICY,
        "pricing_limits": {
            "global_spot_max_cost": global_max,
            "spot_cost_limit_pct": pct,
            "write_spot_pricing_warn_threshold": warn,
        },
        "pricing_source": pricing_source,
        **request_identity,
        "request_config_sha256": request_sha256,
        "source_template_sha256": template_sha256,
        "repository_credential_reference_keys": repository_credential_reference_keys,
        "repository_credential_references_sha256": repository_credential_references_sha256,
        "unpriced_cluster_config_sha256": unpriced_cluster_sha256,
        "final_cluster_config_sha256": final_cluster_sha256,
        "artifacts": {
            "effective_cluster": _artifact_identity(effective),
            "priced_cluster": _artifact_identity(priced),
            "spot_price_summary": _artifact_identity(summary_file),
        },
        "admission_receipt_supplied": admission_receipt_path is not None,
        "admission_receipt_sha256": normalized_admission_sha256,
        "pricing_result": summary,
    }
    if sha256_path(effective) != unpriced_cluster_sha256:
        raise CreateRequestError("Unpriced cluster input changed during final repricing")
    if sha256_path(priced) != final_cluster_sha256:
        raise CreateRequestError("Final priced cluster input changed before receipt")
    if sha256_path(request_file) != request_sha256:
        raise CreateRequestError("Create request changed during final repricing")
    if sha256_path(template_file) != template_sha256:
        raise CreateRequestError("Source template changed during final repricing")
    _atomic_write_json(receipt_file, receipt)
    return summary, {
        **receipt,
        "receipt_path": str(receipt_file),
        "receipt_sha256": sha256_path(receipt_file),
    }


def write_create_terminal_receipt(
    *,
    receipt_path: str | Path,
    cluster_name: str,
    profile: str,
    account_id: str,
    region: str,
    region_az: str,
    request_config_sha256: str,
    final_cluster_config_path: str | Path,
    final_cluster_config_sha256: str,
    pricing_receipt_path: str | Path,
    accounting_receipt_path: str | Path,
    accounting_recovery_receipt_path: str | Path,
    provider_cluster_state: str,
    fleet_state: str,
    accounting_state: str,
    sacct_verified: bool,
) -> dict[str, Any]:
    """Persist the exact terminal create evidence used by the public success object."""

    if provider_cluster_state != "UPDATE_COMPLETE":
        raise CreateRequestError("Terminal create receipt requires UPDATE_COMPLETE")
    if fleet_state != "RUNNING":
        raise CreateRequestError("Terminal create receipt requires a RUNNING fleet")
    if accounting_state != "ENABLED" or sacct_verified is not True:
        raise CreateRequestError("Terminal create receipt requires working Slurm accounting")
    destination = _require_absolute_output(receipt_path, label="terminal receipt")
    final_cluster_path = require_protected_file(
        final_cluster_config_path,
        label="final cluster config",
    )
    if sha256_path(final_cluster_path) != final_cluster_config_sha256:
        raise CreateRequestError("Terminal create final cluster config digest does not match")
    pricing_path = require_protected_file(pricing_receipt_path, label="pricing receipt")
    accounting_path = require_protected_file(
        accounting_receipt_path,
        label="accounting receipt",
    )
    recovery_path = require_protected_file(
        accounting_recovery_receipt_path,
        label="accounting recovery receipt",
    )
    pricing_payload = _load_bounded_json(pricing_path)
    if (
        pricing_payload.get("schema_version") != CREATE_PRICING_RECEIPT_SCHEMA
        or pricing_payload.get("status") != "complete"
        or pricing_payload.get("phase") != "pre_create"
        or pricing_payload.get("cluster_name") != cluster_name
        or pricing_payload.get("profile") != profile
        or pricing_payload.get("account_id") != account_id
        or pricing_payload.get("region") != region
        or pricing_payload.get("region_az") != region_az
        or pricing_payload.get("request_config_sha256") != request_config_sha256
        or pricing_payload.get("final_cluster_config_sha256") != final_cluster_config_sha256
    ):
        raise CreateRequestError("Terminal create pricing receipt identity is invalid")
    from daylily_ec.state.models import SlurmAccountingReceipt, SlurmAccountingStage

    try:
        accounting_payload = SlurmAccountingReceipt.model_validate(
            _load_bounded_json(accounting_path)
        )
    except (CreateRequestError, ValueError) as exc:
        raise CreateRequestError("Terminal create accounting receipt is invalid") from exc
    if (
        accounting_payload.requested_mode != "on"
        or accounting_payload.stage_reached != SlurmAccountingStage.COMPLETE
        or accounting_payload.terminal_cluster_state != "UPDATE_COMPLETE"
        or accounting_payload.terminal_fleet_state != "RUNNING"
        or accounting_payload.fleet_restored is not True
        or accounting_payload.error_stage is not None
        or accounting_payload.recovery_required is not False
    ):
        raise CreateRequestError("Terminal create accounting receipt does not prove working sacct")
    accounting_target = {
        "stack_name": accounting_payload.stack_name,
        "provider_accounting_stack_name": accounting_payload.provider_accounting_stack_name,
        "privatelink_stack_name": accounting_payload.privatelink_stack_name,
        "consumer_vpc_id": accounting_payload.consumer_vpc_id,
        "database_name": accounting_payload.database_name,
        "db_username": accounting_payload.db_username,
        "provider_instance_type": accounting_payload.provider_instance_type,
    }
    if any(
        not str(value or "").strip()
        for key, value in accounting_target.items()
        if key != "privatelink_stack_name"
    ):
        raise CreateRequestError("Terminal create accounting identity is incomplete")
    recovery_payload = _load_bounded_json(recovery_path)
    expected_recovery_identity = {
        "schema_version": "dyec.slurm_accounting_recovery.v1",
        "ok": True,
        "terminal": True,
        "status": "complete",
        "cluster": cluster_name,
        "region": region,
        "region_az": region_az,
        "aws_profile": profile,
        "aws_account_id": account_id,
        "accounting_stack_name": accounting_payload.provider_accounting_stack_name,
        "privatelink_stack_name": accounting_payload.privatelink_stack_name or None,
        "consumer_vpc_id": accounting_payload.consumer_vpc_id,
        "database_name": accounting_payload.database_name,
        "db_username": accounting_payload.db_username,
        "instance_type": accounting_payload.provider_instance_type,
        "cluster_configuration_path": str(final_cluster_path),
        "cluster_configuration_sha256": final_cluster_config_sha256,
        "final_cluster_state": "UPDATE_COMPLETE",
        "final_fleet_state": "RUNNING",
        "accounting_verified": True,
    }
    if any(
        recovery_payload.get(key) != value
        for key, value in expected_recovery_identity.items()
    ):
        raise CreateRequestError(
            "Terminal create recovery receipt does not bind the exact accounting operation"
        )
    phase_receipts = recovery_payload.get("phase_receipts")
    if not isinstance(phase_receipts, list) or not phase_receipts:
        raise CreateRequestError("Terminal create recovery receipt has no phase evidence")
    pricing_receipt_sha256 = sha256_path(pricing_path)
    accounting_receipt_sha256 = sha256_path(accounting_path)
    recovery_receipt_sha256 = sha256_path(recovery_path)
    payload = {
        "schema_version": CREATE_TERMINAL_RECEIPT_SCHEMA,
        "dyec_version": _dyec_version(),
        "status": "complete",
        "terminal": True,
        "phase": "terminal",
        "captured_at": utc_now_iso(),
        "cluster_name": cluster_name,
        "profile": profile,
        "account_id": account_id,
        "region": region,
        "region_az": region_az,
        "request_config_sha256": _require_sha256(
            request_config_sha256,
            label="request config SHA-256",
        ),
        "final_cluster_config_sha256": _require_sha256(
            final_cluster_config_sha256,
            label="final cluster config SHA-256",
        ),
        "final_cluster_config": _artifact_identity(final_cluster_path),
        "pricing_receipt": _artifact_identity(pricing_path),
        "pricing_receipt_sha256": pricing_receipt_sha256,
        "accounting_receipt": _artifact_identity(accounting_path),
        "accounting_receipt_sha256": accounting_receipt_sha256,
        "accounting_recovery_receipt": _artifact_identity(recovery_path),
        "accounting_recovery_receipt_sha256": recovery_receipt_sha256,
        "provider_cluster_state": provider_cluster_state,
        "fleet_state": fleet_state,
        "accounting_state": accounting_state,
        "sacct_verified": sacct_verified,
        "accounting_target": accounting_target,
    }
    _atomic_write_json(destination, payload)
    return {
        **payload,
        "terminal_receipt_path": str(destination),
        "terminal_receipt_sha256": sha256_path(destination),
    }


def validate_create_success_payload(payload: Mapping[str, Any]) -> None:
    """Validate the only public success shape accepted from root ``dyec create``."""

    expected_keys = {
        "account_id",
        "accounting_receipt_sha256",
        "accounting_recovery_receipt_sha256",
        "accounting_state",
        "accounting_target",
        "captured_at",
        "cluster_name",
        "dyec_version",
        "final_cluster_config_sha256",
        "final_cluster_config_path",
        "fleet_state",
        "phase",
        "pricing_receipt_sha256",
        "profile",
        "provider_cluster_state",
        "region",
        "region_az",
        "request_config_sha256",
        "sacct_verified",
        "schema_version",
        "status",
        "terminal",
        "terminal_receipt_path",
        "terminal_receipt_sha256",
    }
    if set(payload) != expected_keys:
        raise CreateRequestError("Create success fields do not match the current schema")
    exact_values = {
        "schema_version": CREATE_SUCCESS_SCHEMA,
        "dyec_version": _dyec_version(),
        "status": "complete",
        "terminal": True,
        "phase": "terminal",
        "provider_cluster_state": "UPDATE_COMPLETE",
        "fleet_state": "RUNNING",
        "accounting_state": "ENABLED",
        "sacct_verified": True,
    }
    for key, expected in exact_values.items():
        if payload.get(key) != expected:
            raise CreateRequestError(f"Create success {key} does not match")
    for key in ("cluster_name", "profile", "account_id", "region", "region_az"):
        value = str(payload.get(key) or "")
        if not value or len(value) > 256 or any(char in value for char in "\r\n\x00"):
            raise CreateRequestError(f"Create success {key} is invalid")
    captured_at = str(payload.get("captured_at") or "")
    try:
        captured = datetime.fromisoformat(captured_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CreateRequestError("Create success captured_at is invalid") from exc
    if captured.tzinfo is None:
        raise CreateRequestError("Create success captured_at must include a timezone")
    for key in (
        "request_config_sha256",
        "final_cluster_config_sha256",
        "pricing_receipt_sha256",
        "accounting_receipt_sha256",
        "accounting_recovery_receipt_sha256",
        "terminal_receipt_sha256",
    ):
        _require_sha256(str(payload.get(key) or ""), label=key)
    final_cluster_path = _resolve_input_path(
        str(payload.get("final_cluster_config_path") or ""),
        label="final cluster config",
    )
    if not final_cluster_path.is_absolute():
        raise CreateRequestError("Create success final cluster config path must be absolute")
    require_protected_file(final_cluster_path, label="create success final cluster config")
    if sha256_path(final_cluster_path) != payload["final_cluster_config_sha256"]:
        raise CreateRequestError("Create success final cluster config digest does not match")
    accounting_target = payload.get("accounting_target")
    expected_accounting_keys = {
        "stack_name",
        "provider_accounting_stack_name",
        "privatelink_stack_name",
        "consumer_vpc_id",
        "database_name",
        "db_username",
        "provider_instance_type",
    }
    if not isinstance(accounting_target, dict) or set(accounting_target) != expected_accounting_keys:
        raise CreateRequestError("Create success accounting_target is invalid")
    if any(
        not isinstance(value, str)
        or (not value and key != "privatelink_stack_name")
        or len(value) > 256
        or any(char in value for char in "\r\n\x00")
        for key, value in accounting_target.items()
    ):
        raise CreateRequestError("Create success accounting_target fields are invalid")
    terminal_path = _resolve_input_path(
        str(payload.get("terminal_receipt_path") or ""),
        label="terminal receipt",
    )
    if not terminal_path.is_absolute():
        raise CreateRequestError("Create success terminal receipt path must be absolute")
    require_protected_file(terminal_path, label="create success terminal receipt")
    if sha256_path(terminal_path) != payload["terminal_receipt_sha256"]:
        raise CreateRequestError("Create success terminal receipt digest does not match")
    terminal_payload = _load_bounded_json(terminal_path)
    terminal_expected_keys = {
        "account_id",
        "accounting_receipt",
        "accounting_receipt_sha256",
        "accounting_recovery_receipt",
        "accounting_recovery_receipt_sha256",
        "accounting_state",
        "accounting_target",
        "captured_at",
        "cluster_name",
        "dyec_version",
        "final_cluster_config_sha256",
        "final_cluster_config",
        "fleet_state",
        "phase",
        "pricing_receipt",
        "pricing_receipt_sha256",
        "profile",
        "provider_cluster_state",
        "region",
        "region_az",
        "request_config_sha256",
        "sacct_verified",
        "schema_version",
        "status",
        "terminal",
    }
    if set(terminal_payload) != terminal_expected_keys:
        raise CreateRequestError("Create terminal receipt fields do not match the schema")
    terminal_exact_values = {
        "schema_version": CREATE_TERMINAL_RECEIPT_SCHEMA,
        "dyec_version": payload["dyec_version"],
        "status": "complete",
        "terminal": True,
        "phase": "terminal",
        "captured_at": payload["captured_at"],
        "cluster_name": payload["cluster_name"],
        "profile": payload["profile"],
        "account_id": payload["account_id"],
        "region": payload["region"],
        "region_az": payload["region_az"],
        "request_config_sha256": payload["request_config_sha256"],
        "final_cluster_config_sha256": payload["final_cluster_config_sha256"],
        "pricing_receipt_sha256": payload["pricing_receipt_sha256"],
        "accounting_receipt_sha256": payload["accounting_receipt_sha256"],
        "accounting_recovery_receipt_sha256": payload[
            "accounting_recovery_receipt_sha256"
        ],
        "provider_cluster_state": "UPDATE_COMPLETE",
        "fleet_state": "RUNNING",
        "accounting_state": "ENABLED",
        "sacct_verified": True,
        "accounting_target": accounting_target,
    }
    for key, expected in terminal_exact_values.items():
        if terminal_payload.get(key) != expected:
            raise CreateRequestError(f"Create success terminal receipt {key} does not match")
    for label in (
        "final_cluster_config",
        "pricing_receipt",
        "accounting_receipt",
        "accounting_recovery_receipt",
    ):
        _verify_artifact_identity(
            terminal_path.parent,
            terminal_payload.get(label),
            label=label,
        )
        if terminal_payload[label]["sha256"] != payload[f"{label}_sha256"]:
            raise CreateRequestError(
                f"Create terminal receipt {label} digest identity does not match"
            )
