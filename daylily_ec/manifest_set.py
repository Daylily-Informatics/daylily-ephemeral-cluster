"""Provider-neutral validation and evidence for DayOA six-manifest inputs.

This module deliberately has no AWS, HTTP, metadata-service, or identity-service
dependencies.  DYEC transports identifiers supplied by an operator; it never
creates, resolves, or rewrites them.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import tempfile
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


MANIFEST_NAMES = (
    "specimens.tsv",
    "samples.tsv",
    "libraries.tsv",
    "sequencing_inputs.tsv",
    "analysis_units.tsv",
    "analysis_unit_inputs.tsv",
)
LEGACY_MANIFEST_NAMES = ("units.tsv",)
REQUIRED_COLUMNS: Mapping[str, tuple[str, ...]] = {
    "specimens.tsv": ("SPECIMEN_ID",),
    "samples.tsv": ("SAMPLEID", "SPECIMEN_ID"),
    "libraries.tsv": ("LIBRARY_ID", "SAMPLEID"),
    "sequencing_inputs.tsv": (
        "SEQUENCING_INPUT_UID",
        "LIBRARY_ID",
        "MODALITY",
        "LAYOUT",
    ),
    "analysis_units.tsv": ("ANALYSIS_UNIT_UID", "SAMPLEID"),
    "analysis_unit_inputs.tsv": (
        "ANALYSIS_UNIT_UID",
        "SEQUENCING_INPUT_UID",
        "ROLE",
        "INPUT_ORDINAL",
    ),
}
PRIMARY_KEYS: Mapping[str, tuple[str, ...]] = {
    "specimens.tsv": ("SPECIMEN_ID",),
    "samples.tsv": ("SAMPLEID",),
    "libraries.tsv": ("LIBRARY_ID",),
    "sequencing_inputs.tsv": ("SEQUENCING_INPUT_UID",),
    "analysis_units.tsv": ("ANALYSIS_UNIT_UID",),
    "analysis_unit_inputs.tsv": ("ANALYSIS_UNIT_UID", "INPUT_ORDINAL"),
}
EUID_FIELDS: Mapping[str, tuple[str, ...]] = {
    "specimens.tsv": ("SPECIMEN_EUID",),
    "samples.tsv": ("SAMPLE_EUID",),
    "libraries.tsv": ("LIBRARY_EUID",),
    "sequencing_inputs.tsv": (
        "POOL_TUBE_EUID",
        "SEQUENCING_RUN_EUID",
        "SOURCE_ARTIFACT_EUID",
    ),
    "analysis_units.tsv": ("ANALYSIS_UNIT_EUID", "DELIVERY_EUID"),
    "analysis_unit_inputs.tsv": (),
}
TEST_EUID_PREFIX = "Z-"
BLANK_VALUES = {"", "na", "none", "null"}
INPUT_BUNDLES: Mapping[str, tuple[str, tuple[str, ...]]] = {
    "ILMN_FASTQ": ("sr", ("ILMN_R1_PATH", "ILMN_R2_PATH")),
    "UG_FASTQ": ("sr", ("UG_R1_PATH", "UG_R2_PATH")),
    "ONT_FASTQ": ("lr", ("ONT_R1_PATH", "ONT_R2_PATH")),
    "PACBIO_FASTQ": ("lr", ("PACBIO_R1_PATH", "PACBIO_R2_PATH")),
    "ROCHE_BAM": ("sr", ("ROCHE_BAM",)),
    "ONT_BAM": ("lr", ("ONT_BAM",)),
    "PB_BAM": ("lr", ("PB_BAM",)),
    "ONT_CRAM": ("lr", ("ONT_CRAM",)),
    "ULTIMA_CRAM": ("sr", ("ULTIMA_CRAM",)),
    "SR_VCF": ("sr", ("SR_VCF_PATH",)),
    "LR_VCF": ("lr", ("LR_VCF_PATH",)),
}
LAYOUT_BUNDLES: Mapping[str, frozenset[str]] = {
    "paired_fastq": frozenset(
        {"ILMN_FASTQ", "UG_FASTQ", "ONT_FASTQ", "PACBIO_FASTQ"}
    ),
    "single_fastq": frozenset(
        {"ILMN_FASTQ", "UG_FASTQ", "ONT_FASTQ", "PACBIO_FASTQ"}
    ),
    "aligned_bam": frozenset({"ROCHE_BAM", "ONT_BAM", "PB_BAM"}),
    "aligned_cram": frozenset({"ONT_CRAM", "ULTIMA_CRAM"}),
    "vcf": frozenset({"SR_VCF", "LR_VCF"}),
}


class ManifestSetError(ValueError):
    """Raised when a six-manifest set is incomplete or inconsistent."""


@dataclass(frozen=True)
class ManifestSet:
    """Validated six-manifest rows, headers, paths, and byte hashes."""

    root: Path
    paths: Mapping[str, Path]
    columns: Mapping[str, tuple[str, ...]]
    rows: Mapping[str, tuple[dict[str, str], ...]]
    hashes: Mapping[str, str]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_tsv(path: Path, *, name: str) -> tuple[tuple[str, ...], tuple[dict[str, str], ...]]:
    if not path.is_file():
        raise ManifestSetError(f"missing required manifest {name}: {path}")
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        raw_columns = reader.fieldnames or []
        columns = tuple(str(column).strip().upper() for column in raw_columns)
        if not columns:
            raise ManifestSetError(f"{name} has no header")
        if len(columns) != len(set(columns)):
            raise ManifestSetError(f"{name} has duplicate case-insensitive columns")
        rows: list[dict[str, str]] = []
        for line_number, raw_row in enumerate(reader, start=2):
            if None in raw_row or any(raw_row.get(column) is None for column in raw_columns):
                raise ManifestSetError(f"{name} line {line_number} does not match its header")
            rows.append(
                {
                    normalized: str(raw_row[raw] or "")
                    for raw, normalized in zip(raw_columns, columns, strict=True)
                }
            )
    if not rows:
        raise ManifestSetError(f"{name} has no data rows")
    return columns, tuple(rows)


def _key(row: Mapping[str, str], fields: Sequence[str]) -> tuple[str, ...]:
    return tuple(row.get(field, "") for field in fields)


def _require_keys(name: str, rows: Sequence[Mapping[str, str]]) -> None:
    fields = PRIMARY_KEYS[name]
    values = [_key(row, fields) for row in rows]
    if any(any(not value or value != value.strip() for value in key) for key in values):
        raise ManifestSetError(f"{name} has a blank or whitespace-modified key for {fields}")
    if len(values) != len(set(values)):
        raise ManifestSetError(f"{name} has duplicate key values for {fields}")


def _require_fk(
    *, name: str, rows: Sequence[Mapping[str, str]], field: str, parents: set[str]
) -> None:
    missing = sorted({row[field] for row in rows} - parents)
    if missing:
        raise ManifestSetError(f"{name} has orphan {field} value(s): {missing}")


def _validate_sequencing_input(row: Mapping[str, str]) -> None:
    """Require one exact source bundle whose modality and layout are explicit."""

    uid = row["SEQUENCING_INPUT_UID"]
    modality = row["MODALITY"]
    layout = row["LAYOUT"]
    if modality not in {"sr", "lr"}:
        raise ManifestSetError(
            f"sequencing input {uid!r} MODALITY must be exactly sr or lr"
        )
    if layout not in LAYOUT_BUNDLES:
        raise ManifestSetError(
            f"sequencing input {uid!r} LAYOUT must be one of "
            + ", ".join(LAYOUT_BUNDLES)
        )

    populated: list[str] = []
    for bundle, (_, fields) in INPUT_BUNDLES.items():
        primary = row.get(fields[0], "")
        if primary:
            if primary != primary.strip():
                raise ManifestSetError(
                    f"sequencing input {uid!r} has whitespace-modified {fields[0]}"
                )
            populated.append(bundle)
        for secondary in fields[1:]:
            value = row.get(secondary, "")
            if value and not primary:
                raise ManifestSetError(
                    f"sequencing input {uid!r} sets {secondary} without {fields[0]}"
                )
            if value and value != value.strip():
                raise ManifestSetError(
                    f"sequencing input {uid!r} has whitespace-modified {secondary}"
                )
    if len(populated) != 1:
        raise ManifestSetError(
            f"sequencing input {uid!r} must populate exactly one source bundle; "
            f"found {populated}"
        )
    bundle = populated[0]
    expected_modality, fields = INPUT_BUNDLES[bundle]
    if modality != expected_modality:
        raise ManifestSetError(
            f"sequencing input {uid!r} MODALITY {modality!r} conflicts with {bundle}"
        )
    if bundle not in LAYOUT_BUNDLES[layout]:
        raise ManifestSetError(
            f"sequencing input {uid!r} LAYOUT {layout!r} conflicts with {bundle}"
        )
    if bundle.endswith("_FASTQ"):
        has_r2 = bool(row.get(fields[1], ""))
        expected_layout = "paired_fastq" if has_r2 else "single_fastq"
        if layout != expected_layout:
            raise ManifestSetError(
                f"sequencing input {uid!r} LAYOUT must be {expected_layout} for {bundle}"
            )


def load_manifest_set(root: str | Path) -> ManifestSet:
    """Load exactly the supported local manifests and validate their topology."""

    root_path = Path(root).expanduser().resolve()
    if not root_path.is_dir():
        raise ManifestSetError(f"manifest directory does not exist: {root_path}")
    legacy = [name for name in LEGACY_MANIFEST_NAMES if (root_path / name).exists()]
    if legacy:
        raise ManifestSetError(
            "legacy manifest files are prohibited by the six-manifest contract: "
            + ", ".join(legacy)
        )
    paths = {name: root_path / name for name in MANIFEST_NAMES}
    columns: dict[str, tuple[str, ...]] = {}
    rows: dict[str, tuple[dict[str, str], ...]] = {}
    hashes: dict[str, str] = {}
    for name in MANIFEST_NAMES:
        manifest_columns, manifest_rows = _read_tsv(paths[name], name=name)
        missing = sorted(set(REQUIRED_COLUMNS[name]) - set(manifest_columns))
        if missing:
            raise ManifestSetError(f"{name} is missing required column(s): {', '.join(missing)}")
        for row in manifest_rows:
            for field in REQUIRED_COLUMNS[name]:
                if not row.get(field, "") or row[field] != row[field].strip():
                    raise ManifestSetError(f"{name} has blank or whitespace-modified {field}")
        _require_keys(name, manifest_rows)
        columns[name] = manifest_columns
        rows[name] = manifest_rows
        hashes[name] = _sha256(paths[name])

    specimens = rows["specimens.tsv"]
    samples = rows["samples.tsv"]
    libraries = rows["libraries.tsv"]
    inputs = rows["sequencing_inputs.tsv"]
    units = rows["analysis_units.tsv"]
    links = rows["analysis_unit_inputs.tsv"]
    specimen_ids = {row["SPECIMEN_ID"] for row in specimens}
    sample_ids = {row["SAMPLEID"] for row in samples}
    library_ids = {row["LIBRARY_ID"] for row in libraries}
    input_ids = {row["SEQUENCING_INPUT_UID"] for row in inputs}
    unit_ids = {row["ANALYSIS_UNIT_UID"] for row in units}
    _require_fk(name="samples.tsv", rows=samples, field="SPECIMEN_ID", parents=specimen_ids)
    _require_fk(name="libraries.tsv", rows=libraries, field="SAMPLEID", parents=sample_ids)
    _require_fk(
        name="sequencing_inputs.tsv", rows=inputs, field="LIBRARY_ID", parents=library_ids
    )
    _require_fk(name="analysis_units.tsv", rows=units, field="SAMPLEID", parents=sample_ids)
    _require_fk(
        name="analysis_unit_inputs.tsv",
        rows=links,
        field="ANALYSIS_UNIT_UID",
        parents=unit_ids,
    )
    _require_fk(
        name="analysis_unit_inputs.tsv",
        rows=links,
        field="SEQUENCING_INPUT_UID",
        parents=input_ids,
    )
    link_pairs = {
        (row["ANALYSIS_UNIT_UID"], row["SEQUENCING_INPUT_UID"]) for row in links
    }
    if len(link_pairs) != len(links):
        raise ManifestSetError("analysis_unit_inputs.tsv repeats an analysis/input pair")

    input_by_id = {row["SEQUENCING_INPUT_UID"]: row for row in inputs}
    library_by_id = {row["LIBRARY_ID"]: row for row in libraries}
    unit_by_id = {row["ANALYSIS_UNIT_UID"]: row for row in units}
    for source in inputs:
        _validate_sequencing_input(source)
    links_by_unit: dict[str, list[Mapping[str, str]]] = defaultdict(list)
    for link in links:
        if link["ROLE"] not in {"sr", "lr"}:
            raise ManifestSetError("analysis_unit_inputs.tsv ROLE must be sr or lr")
        try:
            ordinal = int(link["INPUT_ORDINAL"])
        except ValueError as exc:
            raise ManifestSetError("INPUT_ORDINAL must be a canonical positive integer") from exc
        if ordinal < 1 or str(ordinal) != link["INPUT_ORDINAL"]:
            raise ManifestSetError("INPUT_ORDINAL must be a canonical positive integer")
        source = input_by_id[link["SEQUENCING_INPUT_UID"]]
        if link["ROLE"] != source["MODALITY"]:
            raise ManifestSetError(
                "analysis_unit_inputs.tsv ROLE must equal the selected input MODALITY"
            )
        links_by_unit[link["ANALYSIS_UNIT_UID"]].append(link)
    for unit_uid in unit_ids:
        unit_links = sorted(links_by_unit[unit_uid], key=lambda row: int(row["INPUT_ORDINAL"]))
        if not unit_links:
            raise ManifestSetError(f"analysis unit {unit_uid!r} has no selected inputs")
        ordinals = [int(row["INPUT_ORDINAL"]) for row in unit_links]
        if ordinals != list(range(1, len(unit_links) + 1)):
            raise ManifestSetError(
                f"analysis unit {unit_uid!r} INPUT_ORDINAL values are not contiguous: {ordinals}"
            )
        resolved_samples = {
            library_by_id[input_by_id[link["SEQUENCING_INPUT_UID"]]["LIBRARY_ID"]]["SAMPLEID"]
            for link in unit_links
        }
        if resolved_samples != {unit_by_id[unit_uid]["SAMPLEID"]}:
            raise ManifestSetError(
                f"analysis unit {unit_uid!r} selected inputs do not resolve to its SAMPLEID"
            )

    return ManifestSet(
        root=root_path,
        paths=paths,
        columns=columns,
        rows=rows,
        hashes=hashes,
    )


def selected_input_details(manifests: ManifestSet) -> dict[str, dict[str, Any]]:
    """Return deterministic plural library/input context for every analysis unit."""

    inputs = {
        row["SEQUENCING_INPUT_UID"]: row for row in manifests.rows["sequencing_inputs.tsv"]
    }
    libraries = {row["LIBRARY_ID"]: row for row in manifests.rows["libraries.tsv"]}
    by_unit: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in manifests.rows["analysis_unit_inputs.tsv"]:
        by_unit[row["ANALYSIS_UNIT_UID"]].append(row)
    result: dict[str, dict[str, Any]] = {}
    for unit in manifests.rows["analysis_units.tsv"]:
        unit_uid = unit["ANALYSIS_UNIT_UID"]
        links = sorted(by_unit[unit_uid], key=lambda row: int(row["INPUT_ORDINAL"]))
        selected = []
        library_ids: list[str] = []
        library_euids: list[str] = []
        for link in links:
            source = inputs[link["SEQUENCING_INPUT_UID"]]
            library = libraries[source["LIBRARY_ID"]]
            if library["LIBRARY_ID"] not in library_ids:
                library_ids.append(library["LIBRARY_ID"])
            euid = library.get("LIBRARY_EUID", "")
            if euid and euid.lower() not in BLANK_VALUES and euid not in library_euids:
                library_euids.append(euid)
            selected.append(
                {
                    "sequencing_input_uid": link["SEQUENCING_INPUT_UID"],
                    "role": link["ROLE"],
                    "input_ordinal": int(link["INPUT_ORDINAL"]),
                    "library_id": library["LIBRARY_ID"],
                    "library_euid": euid or None,
                }
            )
        result[unit_uid] = {
            "library_ids": library_ids,
            "library_euids": library_euids,
            "sequencing_inputs": selected,
        }
    return result


def identity_status(manifests: ManifestSet) -> dict[str, Any]:
    """Classify supplied local EUIDs without resolving or creating identities."""

    fields: dict[str, dict[str, int]] = {}
    for name, euid_fields in EUID_FIELDS.items():
        for field in euid_fields:
            counts = {"blank": 0, "test": 0, "owner_issued": 0}
            for row in manifests.rows[name]:
                value = row.get(field, "")
                if value.lower() in BLANK_VALUES:
                    counts["blank"] += 1
                elif value.startswith(TEST_EUID_PREFIX):
                    counts["test"] += 1
                else:
                    counts["owner_issued"] += 1
            fields[f"{name}:{field}"] = counts

    specimens = {row["SPECIMEN_ID"]: row for row in manifests.rows["specimens.tsv"]}
    samples = {row["SAMPLEID"]: row for row in manifests.rows["samples.tsv"]}
    libraries = {row["LIBRARY_ID"]: row for row in manifests.rows["libraries.tsv"]}
    details = selected_input_details(manifests)
    unit_results: list[dict[str, Any]] = []
    for unit in manifests.rows["analysis_units.tsv"]:
        sample = samples[unit["SAMPLEID"]]
        specimen = specimens[sample["SPECIMEN_ID"]]
        required = {
            "SPECIMEN_EUID": specimen.get("SPECIMEN_EUID", ""),
            "SAMPLE_EUID": sample.get("SAMPLE_EUID", ""),
            "ANALYSIS_UNIT_EUID": unit.get("ANALYSIS_UNIT_EUID", ""),
            "DELIVERY_EUID": unit.get("DELIVERY_EUID", ""),
        }
        for library_id in details[unit["ANALYSIS_UNIT_UID"]]["library_ids"]:
            required[f"LIBRARY_EUID[{library_id}]"] = libraries[library_id].get(
                "LIBRARY_EUID", ""
            )
        missing = sorted(key for key, value in required.items() if value.lower() in BLANK_VALUES)
        test = sorted(key for key, value in required.items() if value.startswith(TEST_EUID_PREFIX))
        unit_results.append(
            {
                "analysis_unit_uid": unit["ANALYSIS_UNIT_UID"],
                "customer_release_eligible": not missing and not test,
                "missing_identity_fields": missing,
                "test_identity_fields": test,
            }
        )
    return {
        "fields": fields,
        "analysis_units": unit_results,
        "customer_release_eligible_units": sum(
            row["customer_release_eligible"] for row in unit_results
        ),
        "analysis_units_total": len(unit_results),
    }


def validation_receipt(manifests: ManifestSet) -> dict[str, Any]:
    """Build immutable local evidence for one validated set."""

    return {
        "schema_version": "dyec.six_manifest.validation.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "manifest_dir": str(manifests.root),
        "manifest_order": list(MANIFEST_NAMES),
        "inputs": {
            name: {
                "path": str(manifests.paths[name]),
                "sha256": manifests.hashes[name],
                "rows": len(manifests.rows[name]),
            }
            for name in MANIFEST_NAMES
        },
        "identity_status": identity_status(manifests),
        "invariants": {
            "provider_neutral": True,
            "network_accessed": False,
            "identifiers_created": False,
            "identifiers_rewritten": False,
            "foreign_keys_valid": True,
            "ordered_inputs_valid": True,
        },
    }


def atomic_json(path: str | Path, payload: Mapping[str, Any]) -> None:
    """Write deterministic JSON atomically without following a fallback path."""

    destination = Path(path).expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{destination.name}.", dir=destination.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(temporary, destination)
    except Exception:
        Path(temporary).unlink(missing_ok=True)
        raise
