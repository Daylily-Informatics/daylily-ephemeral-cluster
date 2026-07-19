"""Offline-only identity receipt planning and application.

The receipt is supplied by an external owner.  DYEC verifies and transports
those values; it never calls that owner, creates an identity, or guesses one.
"""

from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from daylily_ec import __version__
from daylily_ec.manifest_set import (
    BLANK_VALUES,
    EUID_FIELDS,
    MANIFEST_NAMES,
    PRIMARY_KEYS,
    TEST_EUID_PREFIX,
    ManifestSet,
    ManifestSetError,
    atomic_json,
    identity_status,
    load_manifest_set,
    validation_receipt,
)


SOURCE_RECEIPT_SCHEMA = "dyec.identity_source_receipt.v1"
PLAN_SCHEMA = "dyec.identity_plan.v1"
APPLY_SCHEMA = "dyec.identity_apply.v1"
EVIDENCE_SCHEMA = "dyec.identity_evidence.v1"


class IdentityReceiptError(ValueError):
    """Raised when a local owner receipt or plan violates the contract."""


def _read_json(path: str | Path) -> dict[str, Any]:
    source = Path(path).expanduser().resolve()
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise IdentityReceiptError(f"identity JSON is unreadable: {source}: {exc}") from exc
    if not isinstance(payload, dict):
        raise IdentityReceiptError(f"identity JSON must be an object: {source}")
    return payload


def _digest_payload(payload: Mapping[str, Any]) -> str:
    rendered = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(rendered).hexdigest()


def _manifest_row_index(manifests: ManifestSet, manifest: str) -> dict[str, dict[str, str]]:
    fields = PRIMARY_KEYS[manifest]
    if len(fields) != 1:
        raise IdentityReceiptError(f"identity updates are not supported for {manifest}")
    field = fields[0]
    return {row[field]: row for row in manifests.rows[manifest]}


def validate(manifest_dir: str | Path) -> dict[str, Any]:
    """Validate topology and report identity eligibility without network access."""

    payload = validation_receipt(load_manifest_set(manifest_dir))
    payload["dyec_version"] = __version__
    return payload


def plan(
    manifest_dir: str | Path,
    *,
    identity_receipt: str | Path | None = None,
) -> dict[str, Any]:
    """Create an idempotent plan from local manifests and an optional owner receipt."""

    manifests = load_manifest_set(manifest_dir)
    source_payload: dict[str, Any] | None = None
    proposed: list[dict[str, str]] = []
    if identity_receipt is not None:
        source_payload = _read_json(identity_receipt)
        if source_payload.get("schema_version") != SOURCE_RECEIPT_SCHEMA:
            raise IdentityReceiptError(
                f"identity source receipt must use {SOURCE_RECEIPT_SCHEMA!r}"
            )
        updates = source_payload.get("updates")
        if not isinstance(updates, list):
            raise IdentityReceiptError("identity source receipt updates must be a list")
        seen: set[tuple[str, str, str]] = set()
        for index, raw in enumerate(updates):
            if not isinstance(raw, dict):
                raise IdentityReceiptError(f"identity update {index} must be an object")
            values = {
                key: str(raw.get(key, ""))
                for key in ("manifest", "key_value", "euid_field", "euid")
            }
            if any(not value or value != value.strip() for value in values.values()):
                raise IdentityReceiptError(
                    f"identity update {index} has a blank or whitespace-modified field"
                )
            manifest = values["manifest"]
            if manifest not in MANIFEST_NAMES or manifest == "analysis_unit_inputs.tsv":
                raise IdentityReceiptError(f"identity update {index} has unsupported manifest")
            if values["euid_field"] not in EUID_FIELDS[manifest]:
                raise IdentityReceiptError(
                    f"identity update {index} cannot set {values['euid_field']} in {manifest}"
                )
            if values["euid"].startswith(TEST_EUID_PREFIX):
                raise IdentityReceiptError(
                    "owner-issued identity receipts must not contain reserved Z- test EUIDs"
                )
            row = _manifest_row_index(manifests, manifest).get(values["key_value"])
            if row is None:
                raise IdentityReceiptError(
                    f"identity update {index} references absent key {values['key_value']!r}"
                )
            dedupe_key = (manifest, values["key_value"], values["euid_field"])
            if dedupe_key in seen:
                raise IdentityReceiptError(f"identity update {index} duplicates {dedupe_key}")
            seen.add(dedupe_key)
            current = row.get(values["euid_field"], "")
            if current.lower() not in BLANK_VALUES and current != values["euid"]:
                raise IdentityReceiptError(
                    f"identity update conflicts with existing {manifest} "
                    f"{values['euid_field']} for {values['key_value']!r}"
                )
            proposed.append({**values, "disposition": "unchanged" if current else "set"})

    payload: dict[str, Any] = {
        "schema_version": PLAN_SCHEMA,
        "dyec_version": __version__,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "manifest_dir": str(manifests.root),
        "source_manifest_hashes": dict(manifests.hashes),
        "source_receipt_sha256": _digest_payload(source_payload) if source_payload else None,
        "updates": proposed,
        "identity_status_before": identity_status(manifests),
        "network_accessed": False,
        "identities_created": False,
    }
    payload["plan_sha256"] = _digest_payload(payload)
    return payload


def _write_tsv(
    path: Path, columns: tuple[str, ...], rows: tuple[dict[str, str], ...]
) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(columns),
            delimiter="\t",
            lineterminator="\n",
            extrasaction="raise",
        )
        writer.writeheader()
        writer.writerows(rows)


def apply(
    manifest_dir: str | Path,
    *,
    plan_path: str | Path,
    output_dir: str | Path,
) -> dict[str, Any]:
    """Apply one hash-bound plan into an empty directory and validate the result."""

    manifests = load_manifest_set(manifest_dir)
    payload = _read_json(plan_path)
    if payload.get("schema_version") != PLAN_SCHEMA:
        raise IdentityReceiptError(f"identity plan must use {PLAN_SCHEMA!r}")
    expected_hash = payload.get("plan_sha256")
    unsigned = dict(payload)
    unsigned.pop("plan_sha256", None)
    if expected_hash != _digest_payload(unsigned):
        raise IdentityReceiptError("identity plan hash is invalid")
    if payload.get("source_manifest_hashes") != dict(manifests.hashes):
        raise IdentityReceiptError("identity plan source hashes do not match current manifests")
    destination = Path(output_dir).expanduser().resolve()
    if destination.exists() and any(destination.iterdir()):
        raise IdentityReceiptError(f"identity apply output directory must be empty: {destination}")
    destination.mkdir(parents=True, exist_ok=True)

    updates_by_manifest: dict[str, dict[tuple[str, str], str]] = {}
    for raw in payload.get("updates", []):
        manifest = raw["manifest"]
        updates_by_manifest.setdefault(manifest, {})[
            (raw["key_value"], raw["euid_field"])
        ] = raw["euid"]
    for name in MANIFEST_NAMES:
        key_field = PRIMARY_KEYS[name][0]
        columns = list(manifests.columns[name])
        required_fields = {
            field for _, field in updates_by_manifest.get(name, {}) if field not in columns
        }
        columns.extend(sorted(required_fields))
        output_rows: list[dict[str, str]] = []
        for source_row in manifests.rows[name]:
            row = {column: source_row.get(column, "") for column in columns}
            for (key_value, field), value in updates_by_manifest.get(name, {}).items():
                if row[key_field] == key_value:
                    row[field] = value
            output_rows.append(row)
        _write_tsv(destination / name, tuple(columns), tuple(output_rows))

    validated = load_manifest_set(destination)
    receipt: dict[str, Any] = {
        "schema_version": APPLY_SCHEMA,
        "dyec_version": __version__,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_manifest_dir": str(manifests.root),
        "output_manifest_dir": str(destination),
        "plan_sha256": expected_hash,
        "source_manifest_hashes": dict(manifests.hashes),
        "output_manifest_hashes": dict(validated.hashes),
        "updates_applied": len(payload.get("updates", [])),
        "identity_status_after": identity_status(validated),
        "network_accessed": False,
        "identities_created": False,
    }
    atomic_json(destination / "dyec_identity_apply_receipt.json", receipt)
    return receipt


def status(manifest_dir: str | Path) -> dict[str, Any]:
    """Return current local identifier classifications and release eligibility."""

    manifests = load_manifest_set(manifest_dir)
    return {
        "schema_version": "dyec.identity_status.v1",
        "dyec_version": __version__,
        "manifest_dir": str(manifests.root),
        "manifest_hashes": dict(manifests.hashes),
        "identity_status": identity_status(manifests),
        "network_accessed": False,
    }


def evidence(manifest_dir: str | Path) -> dict[str, Any]:
    """Generate a checksumed evidence bundle suitable for immutable handoff."""

    manifests = load_manifest_set(manifest_dir)
    payload: dict[str, Any] = {
        "schema_version": EVIDENCE_SCHEMA,
        "dyec_version": __version__,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "validation": validation_receipt(manifests),
        "network_accessed": False,
        "identities_created": False,
        "provider_neutral": True,
    }
    payload["evidence_sha256"] = _digest_payload(payload)
    return payload


def write_payload(payload: Mapping[str, Any], output: str | Path | None) -> None:
    """Write a CLI payload when requested; stdout remains the caller's concern."""

    if output is not None:
        try:
            atomic_json(output, payload)
        except ManifestSetError as exc:  # defensive normalization for CLI callers
            raise IdentityReceiptError(str(exc)) from exc
