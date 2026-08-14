"""Receipt-bound FSx readability verification for Bjuice v2 HG002 inputs.

The seven-AU Bjuice manifest generator records the requested mounted FASTQ
paths.  This module deliberately separates that request from the successful
headnode verification: workflow launch only accepts the latter.
"""

from __future__ import annotations

import hashlib
import json
import shlex
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

from daylily_ec.manifest_set import ManifestSet, load_manifest_set


STAGING_RECEIPT_SCHEMA = "dyec.bjuice_v2_hg002_run_mount_staging_receipt.v1"
STAGING_RECEIPT_NAME = "staging_receipt.json"
FSX_RUN_MOUNT_PREFIX = "/fsx/run_dir_mounts/"


class BjuiceV2StagingError(ValueError):
    """Raised when Bjuice v2 mounted-input staging evidence is invalid."""


@dataclass(frozen=True)
class BjuiceV2StagingPlan:
    """Exact input paths and hash-bound manifest evidence to verify remotely."""

    manifest_dir: Path
    manifest_hashes: Mapping[str, str]
    ilmn_r1_paths: tuple[str, ...]
    ilmn_r2_paths: tuple[str, ...]
    ont_paths: tuple[str, ...]
    mount_roots: tuple[str, ...]

    @property
    def all_paths(self) -> tuple[str, ...]:
        return (*self.ilmn_r1_paths, *self.ilmn_r2_paths, *self.ont_paths)

    @property
    def path_set_sha256(self) -> str:
        return hashlib.sha256("\n".join(self.all_paths).encode("utf-8")).hexdigest()

    @property
    def expected_counts(self) -> dict[str, int]:
        return {
            "ilmn_r1": len(self.ilmn_r1_paths),
            "ilmn_r2": len(self.ilmn_r2_paths),
            "ont": len(self.ont_paths),
            "total": len(self.all_paths),
        }


def _split_paths(value: str, *, field: str, input_uid: str) -> tuple[str, ...]:
    text = str(value or "").strip()
    if not text:
        return ()
    paths = tuple(part.strip() for part in text.split(","))
    if any(not path for path in paths):
        raise BjuiceV2StagingError(
            f"sequencing input {input_uid!r} has an empty path in {field}"
        )
    return paths


def _validate_path(path: str, *, field: str, input_uid: str) -> str:
    if not path.startswith(FSX_RUN_MOUNT_PREFIX):
        raise BjuiceV2StagingError(
            f"sequencing input {input_uid!r} {field} must be under {FSX_RUN_MOUNT_PREFIX}: {path}"
        )
    parsed = PurePosixPath(path)
    if not parsed.is_absolute() or ".." in parsed.parts or len(parsed.parts) < 5:
        raise BjuiceV2StagingError(
            f"sequencing input {input_uid!r} {field} is not a valid mounted absolute path: {path}"
        )
    if parsed.parts[:3] != ("/", "fsx", "run_dir_mounts"):
        raise BjuiceV2StagingError(
            f"sequencing input {input_uid!r} {field} must identify an explicit run mount: {path}"
        )
    return path


def _unique_paths(paths: tuple[str, ...], *, field: str) -> tuple[str, ...]:
    if len(set(paths)) != len(paths):
        raise BjuiceV2StagingError(f"duplicate mounted FASTQ path in {field}")
    return paths


def _plan_from_manifests(manifests: ManifestSet) -> BjuiceV2StagingPlan:
    ilmn_r1: list[str] = []
    ilmn_r2: list[str] = []
    ont: list[str] = []
    for row in manifests.rows["sequencing_inputs.tsv"]:
        input_uid = row["SEQUENCING_INPUT_UID"]
        modality = row["MODALITY"].strip().lower()
        if modality == "sr":
            for field, destination in (("ILMN_R1_PATH", ilmn_r1), ("ILMN_R2_PATH", ilmn_r2)):
                paths = _split_paths(row.get(field, ""), field=field, input_uid=input_uid)
                if not paths:
                    raise BjuiceV2StagingError(
                        f"sequencing input {input_uid!r} must provide {field} for Bjuice v2"
                    )
                destination.extend(
                    _validate_path(path, field=field, input_uid=input_uid) for path in paths
                )
        elif modality == "lr":
            paths = _split_paths(row.get("ONT_R1_PATH", ""), field="ONT_R1_PATH", input_uid=input_uid)
            if not paths:
                raise BjuiceV2StagingError(
                    f"sequencing input {input_uid!r} must provide ONT_R1_PATH for Bjuice v2"
                )
            ont.extend(_validate_path(path, field="ONT_R1_PATH", input_uid=input_uid) for path in paths)
        else:
            raise BjuiceV2StagingError(
                f"sequencing input {input_uid!r} has unsupported Bjuice v2 modality {modality!r}"
            )
    if not ilmn_r1 or not ilmn_r2 or not ont:
        raise BjuiceV2StagingError("Bjuice v2 requires non-empty ILMN R1, ILMN R2, and ONT path sets")
    ilmn_r1_paths = _unique_paths(tuple(ilmn_r1), field="ILMN_R1_PATH")
    ilmn_r2_paths = _unique_paths(tuple(ilmn_r2), field="ILMN_R2_PATH")
    ont_paths = _unique_paths(tuple(ont), field="ONT_R1_PATH")
    all_paths = (*ilmn_r1_paths, *ilmn_r2_paths, *ont_paths)
    if len(set(all_paths)) != len(all_paths):
        raise BjuiceV2StagingError("a mounted FASTQ path is assigned to more than one Bjuice input role")
    mount_roots = tuple(
        sorted({f"{FSX_RUN_MOUNT_PREFIX}{PurePosixPath(path).parts[3]}/" for path in all_paths})
    )
    return BjuiceV2StagingPlan(
        manifest_dir=manifests.root,
        manifest_hashes=dict(manifests.hashes),
        ilmn_r1_paths=ilmn_r1_paths,
        ilmn_r2_paths=ilmn_r2_paths,
        ont_paths=ont_paths,
        mount_roots=mount_roots,
    )


def load_bjuice_v2_staging_plan(manifest_dir: Path) -> BjuiceV2StagingPlan:
    """Load only the exact Bjuice mounted FASTQs declared in six manifests."""

    return _plan_from_manifests(load_manifest_set(manifest_dir))


def _planned_receipt(plan: BjuiceV2StagingPlan) -> dict[str, Any]:
    return {
        "schema": STAGING_RECEIPT_SCHEMA,
        "state": "materialization_required",
        "manifest_hashes": dict(plan.manifest_hashes),
        "path_set_sha256": plan.path_set_sha256,
        "files_requested": plan.expected_counts,
        "mount_roots": list(plan.mount_roots),
        "materialization_command": "dyec catalog materialize-bjuice-v2-hg002-multi-au-staging",
    }


def write_planned_bjuice_v2_staging_receipt(manifest_dir: Path) -> Path:
    """Record the non-materialized mounted-path request next to the manifests."""

    plan = load_bjuice_v2_staging_plan(manifest_dir)
    receipt_path = plan.manifest_dir / STAGING_RECEIPT_NAME
    if receipt_path.exists():
        raise BjuiceV2StagingError(f"staging receipt already exists: {receipt_path}")
    receipt_path.write_text(
        json.dumps(_planned_receipt(plan), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return receipt_path


def _read_receipt(receipt_path: Path) -> dict[str, Any]:
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BjuiceV2StagingError(f"unable to read staging receipt {receipt_path}: {exc}") from exc
    if not isinstance(receipt, dict):
        raise BjuiceV2StagingError(f"staging receipt must be a JSON object: {receipt_path}")
    return receipt


def _validate_plan_receipt(plan: BjuiceV2StagingPlan, receipt: Mapping[str, Any]) -> None:
    if receipt.get("schema") != STAGING_RECEIPT_SCHEMA:
        raise BjuiceV2StagingError("staging receipt schema does not match the Bjuice v2 contract")
    if receipt.get("manifest_hashes") != dict(plan.manifest_hashes):
        raise BjuiceV2StagingError("staging receipt manifest hashes do not match the current manifests")
    if receipt.get("path_set_sha256") != plan.path_set_sha256:
        raise BjuiceV2StagingError("staging receipt path set does not match the current manifests")
    if receipt.get("files_requested") != plan.expected_counts:
        raise BjuiceV2StagingError("staging receipt file counts do not match the current manifests")
    if receipt.get("mount_roots") != list(plan.mount_roots):
        raise BjuiceV2StagingError("staging receipt mount roots do not match the current manifests")


def render_bjuice_v2_staging_verification_script(plan: BjuiceV2StagingPlan) -> str:
    """Render a no-copy headnode scan of the exact mounted FASTQ paths."""

    quoted_paths = " ".join(shlex.quote(path) for path in plan.all_paths)
    return "\n".join(
        (
            "set -euo pipefail",
            "verified_files=0",
            "total_size_bytes=0",
            f"for path in {quoted_paths}; do",
            '  test -f "$path"',
            '  test -r "$path"',
            '  bytes=$(stat -c %s -- "$path")',
            '  verified_files=$((verified_files + 1))',
            '  total_size_bytes=$((total_size_bytes + bytes))',
            "done",
            'printf "DYEC_BJUICE_VERIFIED_FILES=%s\\n" "$verified_files"',
            'printf "DYEC_BJUICE_TOTAL_SIZE_BYTES=%s\\n" "$total_size_bytes"',
        )
    )


def parse_bjuice_v2_staging_verification_output(output: str) -> tuple[int, int]:
    """Parse the two bounded result markers emitted by the remote scan."""

    values: dict[str, int] = {}
    for line in str(output or "").splitlines():
        key, separator, value = line.partition("=")
        if separator and key in {"DYEC_BJUICE_VERIFIED_FILES", "DYEC_BJUICE_TOTAL_SIZE_BYTES"}:
            try:
                parsed = int(value)
            except ValueError as exc:
                raise BjuiceV2StagingError(f"invalid remote staging marker {line!r}") from exc
            if parsed < 0:
                raise BjuiceV2StagingError(f"negative remote staging marker {line!r}")
            values[key] = parsed
    if set(values) != {"DYEC_BJUICE_VERIFIED_FILES", "DYEC_BJUICE_TOTAL_SIZE_BYTES"}:
        raise BjuiceV2StagingError("remote Bjuice staging scan did not return both verification markers")
    return values["DYEC_BJUICE_VERIFIED_FILES"], values["DYEC_BJUICE_TOTAL_SIZE_BYTES"]


def finalize_bjuice_v2_staging_receipt(
    *,
    manifest_dir: Path,
    cluster: str,
    region: str,
    headnode_instance_id: str,
    remote_user: str,
    verified_files: int,
    total_size_bytes: int,
    verification_script: str,
) -> Path:
    """Atomically replace a planned receipt after a successful remote scan."""

    plan = load_bjuice_v2_staging_plan(manifest_dir)
    receipt_path = plan.manifest_dir / STAGING_RECEIPT_NAME
    planned = _read_receipt(receipt_path)
    _validate_plan_receipt(plan, planned)
    if planned.get("state") != "materialization_required":
        raise BjuiceV2StagingError(
            "Bjuice v2 staging receipt must be materialization_required before headnode finalization"
        )
    if verified_files != plan.expected_counts["total"]:
        raise BjuiceV2StagingError(
            f"headnode verified {verified_files} files but manifest requires {plan.expected_counts['total']}"
        )
    if total_size_bytes <= 0:
        raise BjuiceV2StagingError("headnode staging verification returned a non-positive total size")
    receipt = {
        **_planned_receipt(plan),
        "state": "materialized",
        "verified_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "cluster": cluster,
        "region": region,
        "headnode_instance_id": headnode_instance_id,
        "remote_user": remote_user,
        "files_verified": {**plan.expected_counts, "total_size_bytes": total_size_bytes},
        "verification": {
            "method": "DYEC headnode remote readable-file scan",
            "script_sha256": hashlib.sha256(verification_script.encode("utf-8")).hexdigest(),
        },
    }
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=plan.manifest_dir, prefix=".staging_receipt.", delete=False
    ) as handle:
        temporary_path = Path(handle.name)
        handle.write(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    temporary_path.replace(receipt_path)
    return receipt_path


def validate_materialized_bjuice_v2_staging_receipt(manifest_dir: Path) -> dict[str, Any]:
    """Reject incomplete, forged, stale, or mismatched Bjuice staging evidence."""

    plan = load_bjuice_v2_staging_plan(manifest_dir)
    receipt_path = plan.manifest_dir / STAGING_RECEIPT_NAME
    if not receipt_path.is_file():
        raise BjuiceV2StagingError(
            f"Bjuice v2 staging receipt is missing: {receipt_path}. Run `dyec catalog "
            "materialize-bjuice-v2-hg002-multi-au-staging --manifest-dir ...` first."
        )
    receipt = _read_receipt(receipt_path)
    _validate_plan_receipt(plan, receipt)
    if receipt.get("state") != "materialized":
        raise BjuiceV2StagingError(
            "Bjuice v2 staging receipt is not materialized. Run `dyec catalog "
            "materialize-bjuice-v2-hg002-multi-au-staging --manifest-dir ...` first."
        )
    files_verified = receipt.get("files_verified")
    if not isinstance(files_verified, dict):
        raise BjuiceV2StagingError("Bjuice v2 staging receipt is missing files_verified")
    expected = plan.expected_counts
    for key, value in expected.items():
        if files_verified.get(key) != value:
            raise BjuiceV2StagingError(
                f"Bjuice v2 staging receipt {key} does not match current manifests"
            )
    if not isinstance(files_verified.get("total_size_bytes"), int) or files_verified["total_size_bytes"] <= 0:
        raise BjuiceV2StagingError("Bjuice v2 staging receipt has invalid total_size_bytes")
    for key in ("verified_at", "cluster", "region", "headnode_instance_id"):
        if not str(receipt.get(key) or "").strip():
            raise BjuiceV2StagingError(f"Bjuice v2 staging receipt is missing {key}")
    if receipt.get("remote_user") != "ubuntu":
        raise BjuiceV2StagingError("Bjuice v2 staging receipt must be verified as ubuntu")
    verification = receipt.get("verification")
    if not isinstance(verification, dict) or not str(verification.get("script_sha256") or "").strip():
        raise BjuiceV2StagingError("Bjuice v2 staging receipt is missing verification script evidence")
    return receipt
