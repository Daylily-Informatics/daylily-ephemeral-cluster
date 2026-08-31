"""Materialize one attachment-selected Bjuice crosswalk run locally.

This is deliberately an offline, provider-neutral materializer.  It consumes
four explicit local inputs and two exact FSx mount roots; it neither lists S3
nor creates a mount, analysis, identity, or workflow.  In particular, the
attachment's ``ont_chips`` field is the complete ONT membership contract.  A
source inventory which has only one of the declared flowcells therefore fails
closed instead of silently constructing a single-flowcell AU.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlparse

import yaml

from daylily_ec.bjuice_preval_config import BjuiceConfigError, _sha256, _write_tsv
from daylily_ec.bjuice_validation_config import (
    CROSSWALK_COLUMNS,
    GENERATION_RECEIPT_SCHEMA,
    ILMN_FASTQ_RE,
    MANIFEST_COLUMNS,
    ONT_FASTQ_RE,
    _manifest_rows_for_bundle,
    _runtime_config,
)
from daylily_ec.manifest_set import load_manifest_set

MATERIALIZATION_RECEIPT_SCHEMA = "dyec.bjuice_crosswalk_run_materialization.v1"
CONTRIBUTING_DATA_SCHEMA = "dayoa.contributing_data.v1"
CONTRIBUTING_DATA_RECEIPT_RELATIVE_PATH = Path("config/contributing_data_receipt.v1.json")
ILMN_SOURCE_BY_RUN = {"13": "ilmn-run2", "14": "ilmn-run1b", "15": "ilmn-run3", "16": "ilmn-run4"}
ONT_SOURCE_PREFIX_BY_RUN = {
    "Run1(ValR1)": "ont-run1",
    "Run2": "ont-run2",
    "Run3": "ont-run3",
    "Run4": "ont-run4",
}
ATTACHMENT_REQUIRED_COLUMNS = frozenset(
    {
        "unit_id",
        "canonical",
        "ilmn_run",
        "ilmn_lib_id",
        "ilmn_ok",
        "ont_run",
        "ont_lib_name",
        "ont_barcode",
        "ont_set",
        "ont_chips",
        "ont_ok",
    }
)
CHIP_RE = re.compile(r"^[A-Z0-9]+$")


def _read_tsv(path: Path) -> tuple[tuple[str, ...], list[dict[str, str]]]:
    try:
        with path.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle, delimiter="\t")
            if not reader.fieldnames:
                raise BjuiceConfigError(f"{path} has no header")
            rows = [{key: str(value or "") for key, value in row.items()} for row in reader]
    except OSError as exc:
        raise BjuiceConfigError(f"cannot read {path}: {exc}") from exc
    return tuple(reader.fieldnames), rows


def _read_inventory(path: Path) -> Mapping[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BjuiceConfigError(f"cannot read source inventory {path}: {exc}") from exc
    if not isinstance(payload, Mapping):
        raise BjuiceConfigError("source inventory must be one JSON object")
    selections = payload.get("selections")
    if not isinstance(selections, Mapping):
        raise BjuiceConfigError("source inventory has no selections mapping")
    return payload


def _absolute_mount(value: str, *, field_name: str) -> PurePosixPath:
    path = PurePosixPath(str(value).strip())
    if not path.is_absolute() or ".." in path.parts:
        raise BjuiceConfigError(f"{field_name} must be an absolute normalized FSx path")
    return path


def _one(
    values: Sequence[tuple[str, Mapping[str, Any]]], *, label: str
) -> tuple[str, Mapping[str, Any]]:
    if len(values) != 1:
        raise BjuiceConfigError(
            f"{label} matched {len(values)} inventory selections; expected exactly one"
        )
    return values[0]


def _canonical_hash(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
            "utf-8"
        )
    ).hexdigest()


def _nonnegative_int(value: Any, *, label: str) -> int:
    if isinstance(value, bool):
        raise BjuiceConfigError(f"{label} must be a nonnegative integer")
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise BjuiceConfigError(f"{label} must be a nonnegative integer") from exc
    if result < 0 or str(value).strip() != str(result):
        raise BjuiceConfigError(f"{label} must be a nonnegative integer")
    return result


def _positive_size(value: Any, *, label: str) -> int:
    size = _nonnegative_int(value, label=label)
    if size == 0:
        raise BjuiceConfigError(f"{label} must be greater than zero")
    return size


def _nonnegative_number(value: Any, *, label: str) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        raise BjuiceConfigError(f"{label} must be a nonnegative number")
    return value


def _s3_parts(uri: str, *, label: str) -> tuple[str, ...]:
    parsed = urlparse(uri)
    if parsed.scheme != "s3" or not parsed.netloc or not parsed.path:
        raise BjuiceConfigError(f"{label} must have an absolute s3:// URI")
    return PurePosixPath(parsed.path.lstrip("/")).parts


def _project_ilmn_path(uri: str, *, mount: PurePosixPath, run_id: str) -> str:
    parts = _s3_parts(uri, label="ILMN inventory object")
    if not run_id or parts.count(run_id) != 1:
        raise BjuiceConfigError(f"ILMN inventory object lacks its declared run ID {run_id}: {uri}")
    index = parts.index(run_id)
    return str(mount / PurePosixPath(*parts[index:]))


def _project_ont_path(uri: str, *, mount: PurePosixPath) -> str:
    parts = _s3_parts(uri, label="ONT inventory object")
    lower = [part.lower() for part in parts]
    if "pca100" not in lower:
        raise BjuiceConfigError(f"ONT inventory object is not under pca100: {uri}")
    index = lower.index("pca100")
    if len(parts) <= index + 2 or parts[index + 1] not in {"2025", "2026"}:
        raise BjuiceConfigError(f"ONT inventory object has no supported pca100 year: {uri}")
    return str(mount / PurePosixPath(*parts[index + 1 :]))


def _validate_optional_header(
    item: Mapping[str, Any], *, sample: str, lane: str, mate: str, label: str
) -> None:
    """Check embedded source-inventory FASTQ header evidence when it is supplied."""

    header = item.get("fastq_header")
    if header is None:
        return
    if not isinstance(header, Mapping):
        raise BjuiceConfigError(f"{label} fastq_header evidence must be an object")
    expected = {"sample_id": sample, "lane": lane, "mate": mate}
    if any(str(header.get(key) or "") != value for key, value in expected.items()):
        raise BjuiceConfigError(f"{label} FASTQ header evidence does not match its filename")


def _verified_ilmn_fastqs(
    component: Mapping[str, Any], *, sample_id: str, mount: PurePosixPath, unit_id: str
) -> tuple[dict[str, Any], Mapping[str, Any]]:
    run_id = str(component.get("run_id") or "")
    declared_lanes = component.get("lanes")
    if not run_id or not isinstance(declared_lanes, list) or not declared_lanes:
        raise BjuiceConfigError(f"attachment unit {unit_id} has incomplete ILMN run or lane evidence")
    lanes = [str(value) for value in declared_lanes]
    if len(lanes) != len(set(lanes)) or any(not value for value in lanes):
        raise BjuiceConfigError(f"attachment unit {unit_id} has duplicate or blank ILMN lanes")
    rewritten = dict(component)
    all_paths: set[str] = set()
    normalized: dict[str, list[dict[str, Any]]] = {}
    for field, mate in (("r1", "1"), ("r2", "2")):
        files = component.get(field)
        if not isinstance(files, list) or not files:
            raise BjuiceConfigError(f"attachment unit {unit_id} has no explicit ILMN {field} files")
        normalized[field] = []
        for item in files:
            if not isinstance(item, Mapping):
                raise BjuiceConfigError(f"attachment unit {unit_id} has malformed ILMN {field} files")
            uri = str(item.get("s3_uri") or "")
            name = PurePosixPath(urlparse(uri).path).name
            match = ILMN_FASTQ_RE.fullmatch(name)
            if match is None or match.group("sample") != sample_id or match.group("mate") != mate:
                raise BjuiceConfigError(f"attachment unit {unit_id} has an ILMN FASTQ filename mismatch")
            lane = match.group("lane")
            if lane not in lanes or str(item.get("lane") or lane) != lane:
                raise BjuiceConfigError(f"attachment unit {unit_id} has an ILMN lane mismatch")
            _validate_optional_header(
                item,
                sample=sample_id,
                lane=lane,
                mate=mate,
                label=f"attachment unit {unit_id} ILMN {field}",
            )
            if uri in all_paths:
                raise BjuiceConfigError(f"attachment unit {unit_id} has a duplicate ILMN FASTQ path {uri}")
            all_paths.add(uri)
            rewritten_item = dict(item)
            rewritten_item["size"] = _positive_size(
                item.get("size"), label=f"attachment unit {unit_id} ILMN FASTQ size"
            )
            rewritten_item["lane"] = lane
            rewritten_item["mount_path"] = _project_ilmn_path(uri, mount=mount, run_id=run_id)
            normalized[field].append(rewritten_item)
        normalized[field].sort(key=lambda item: (str(item["lane"]), str(item["s3_uri"])))
    rewritten.update(normalized)
    return rewritten, {
        "selected_paths": sorted(all_paths),
        "selected_paths_sha256": _canonical_hash(sorted(all_paths)),
        "selected_fastq_count": len(all_paths),
        "selected_total_bytes": sum(
            int(item["size"]) for items in normalized.values() for item in items
        ),
    }


def _chips(value: str, *, unit_id: str) -> tuple[str, ...]:
    chips = tuple(part.strip() for part in value.split(";") if part.strip())
    if (
        not chips
        or len(chips) != len(set(chips))
        or any(not CHIP_RE.fullmatch(chip) for chip in chips)
    ):
        raise BjuiceConfigError(
            f"attachment unit {unit_id} has an invalid exact ont_chips membership"
        )
    return chips


def _verified_ont_fastqs(
    component: Mapping[str, Any],
    *,
    chips: tuple[str, ...],
    barcode: str,
    ont_set: int,
    ont_mount: PurePosixPath,
    unit_id: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if component.get("barcode") != barcode or component.get("set_number") != ont_set:
        raise BjuiceConfigError(f"attachment unit {unit_id} has an ONT set or barcode mismatch")
    run_id = str(component.get("run_id") or "")
    if not run_id:
        raise BjuiceConfigError(f"attachment unit {unit_id} has no explicit ONT run ID")
    raw = component.get("fastqs")
    if not isinstance(raw, list) or not raw:
        raise BjuiceConfigError(
            f"attachment unit {unit_id} has no explicit ONT FASTQs in its inventory selection"
        )
    selected: list[dict[str, Any]] = []
    seen_paths: set[str] = set()
    for item in raw:
        if not isinstance(item, Mapping):
            raise BjuiceConfigError(f"attachment unit {unit_id} has a malformed ONT FASTQ entry")
        uri = str(item.get("s3_uri") or "")
        parts = _s3_parts(uri, label="ONT inventory object")
        if parts.count(run_id) != 1:
            raise BjuiceConfigError(f"attachment unit {unit_id} has an ONT run/path mismatch")
        try:
            fastq_pass_index = parts.index("fastq_pass")
        except ValueError as exc:
            raise BjuiceConfigError(
                f"attachment unit {unit_id} has an ONT FASTQ outside fastq_pass"
            ) from exc
        if len(parts) <= fastq_pass_index + 2 or parts[fastq_pass_index + 1] != barcode:
            raise BjuiceConfigError(f"attachment unit {unit_id} has an ONT barcode/path mismatch")
        name = PurePosixPath(urlparse(uri).path).name
        match = ONT_FASTQ_RE.fullmatch(name)
        if match is None or match.group("barcode") != barcode:
            raise BjuiceConfigError(
                f"attachment unit {unit_id} has an ONT FASTQ outside its exact barcode"
            )
        chip = match.group("flowcell")
        if chip not in chips:
            raise BjuiceConfigError(
                f"attachment unit {unit_id} has an ONT FASTQ outside exact ont_chips membership: {chip}"
            )
        if uri in seen_paths:
            raise BjuiceConfigError(
                f"attachment unit {unit_id} has duplicate ONT FASTQ {uri}"
            )
        seen_paths.add(uri)
        rewritten = dict(item)
        rewritten["size"] = _positive_size(
            item.get("size"), label=f"attachment unit {unit_id} ONT FASTQ size"
        )
        if "hour" in item and _nonnegative_int(item["hour"], label="ONT FASTQ hour") != int(
            match.group("hour")
        ):
            raise BjuiceConfigError(f"attachment unit {unit_id} has an ONT hour/header mismatch")
        rewritten["mount_path"] = _project_ont_path(uri, mount=ont_mount)
        rewritten["hour"] = int(match.group("hour"))
        selected.append(rewritten)
    by_chip = {
        chip: [
            item
            for item in selected
            if PurePosixPath(urlparse(str(item["s3_uri"])).path).name.startswith(f"{chip}_")
        ]
        for chip in chips
    }
    missing = [chip for chip, files in by_chip.items() if not files]
    if missing:
        raise BjuiceConfigError(
            f"attachment unit {unit_id} is missing verified FASTQs for declared chips: {', '.join(missing)}"
        )
    selected.sort(
        key=lambda item: (
            chips.index(PurePosixPath(urlparse(str(item["s3_uri"])).path).name.split("_", 1)[0]),
            int(item["hour"]),
            str(item["s3_uri"]),
        )
    )
    receipt = [
        {
            "flowcell": chip,
            "fastq_count": len(by_chip[chip]),
            "total_bytes": sum(int(item["size"]) for item in by_chip[chip]),
            "hours": sorted(int(item["hour"]) for item in by_chip[chip]),
            "selected_paths": [str(item["s3_uri"]) for item in by_chip[chip]],
            "selected_paths_sha256": _canonical_hash(
                [str(item["s3_uri"]) for item in by_chip[chip]]
            ),
        }
        for chip in chips
    ]
    return selected, receipt


def _contributing_data_evidence(
    *,
    ilmn: Mapping[str, Any],
    ont: Mapping[str, Any],
    ilmn_fastq_count: int,
    ilmn_lanes: Sequence[str],
    chips: Sequence[str],
    chip_receipt: Sequence[Mapping[str, Any]],
    unit_id: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Validate source-declared metrics; counts are never estimated from FASTQ bytes."""

    ilmn_evidence = ilmn.get("contributing_data")
    ont_evidence = ont.get("contributing_data")
    if not isinstance(ilmn_evidence, Mapping) or not isinstance(ont_evidence, Mapping):
        raise BjuiceConfigError(
            f"attachment unit {unit_id} lacks explicit source-inventory contributing_data evidence"
        )
    flowcells = ilmn_evidence.get("illumina_flowcells")
    cells = ont_evidence.get("ont_cells")
    if not isinstance(flowcells, list) or not flowcells or not isinstance(cells, list):
        raise BjuiceConfigError(f"attachment unit {unit_id} has malformed contributing_data evidence")
    declared_lanes = [str(lane) for lane in ilmn_lanes]
    validated_flowcells: list[dict[str, Any]] = []
    contributing_fastq_count = 0
    contributing_lanes: set[str] = set()
    for value in flowcells:
        if not isinstance(value, Mapping):
            raise BjuiceConfigError(f"attachment unit {unit_id} has malformed ILMN flowcell evidence")
        flowcell_id = str(value.get("flowcell_id") or "")
        evidence_lanes = value.get("lanes_used")
        if (
            not flowcell_id
            or not str(value.get("type") or "")
            or not isinstance(evidence_lanes, list)
            or not evidence_lanes
            or not set(map(str, evidence_lanes)).issubset(set(declared_lanes))
            or len(evidence_lanes) != len(set(map(str, evidence_lanes)))
        ):
            raise BjuiceConfigError(f"attachment unit {unit_id} has inconsistent ILMN flowcell evidence")
        flowcell_fastq_count = _nonnegative_int(
            value.get("fastq_count"), label="ILMN contributing fastq_count"
        )
        contributing_fastq_count += flowcell_fastq_count
        contributing_lanes.update(map(str, evidence_lanes))
        validated_flowcells.append(
            {
                "flowcell_id": flowcell_id,
                "type": str(value["type"]),
                "lanes_used": list(map(str, evidence_lanes)),
                "fastq_count": flowcell_fastq_count,
                "pass_filter_reads": _nonnegative_int(
                    value.get("pass_filter_reads"), label="ILMN contributing pass_filter_reads"
                ),
            }
        )
    if len({item["flowcell_id"] for item in validated_flowcells}) != len(validated_flowcells):
        raise BjuiceConfigError(f"attachment unit {unit_id} has duplicate ILMN flowcell evidence")
    if contributing_fastq_count != ilmn_fastq_count or contributing_lanes != set(declared_lanes):
        raise BjuiceConfigError(
            f"attachment unit {unit_id} ILMN contributing flowcells do not partition the selected FASTQs and lanes"
        )
    counts_by_chip = {str(item["flowcell"]): item for item in chip_receipt}
    cells_by_chip = {
        str(value.get("chip_id") or ""): value for value in cells if isinstance(value, Mapping)
    }
    if len(cells_by_chip) != len(cells) or set(cells_by_chip) != set(chips):
        raise BjuiceConfigError(f"attachment unit {unit_id} ONT contributing chip membership mismatch")
    validated_cells: list[dict[str, Any]] = []
    for chip in chips:
        value = cells_by_chip[chip]
        observed = counts_by_chip[chip]
        total = _nonnegative_int(value.get("total_fastq_count"), label="ONT contributing total_fastq_count")
        selected_count = _nonnegative_int(
            value.get("selected_fastq_count"), label="ONT contributing selected_fastq_count"
        )
        if total != selected_count or selected_count != int(observed["fastq_count"]):
            raise BjuiceConfigError(f"attachment unit {unit_id} ONT contributing FASTQ count mismatch")
        if not str(value.get("type") or ""):
            raise BjuiceConfigError(f"attachment unit {unit_id} ONT contributing type is blank")
        validated_cells.append(
            {
                "chip_id": chip,
                "type": str(value["type"]),
                "runtime_hours": _nonnegative_number(
                    value.get("runtime_hours"), label="ONT contributing runtime_hours"
                ),
                "total_fastq_count": total,
                "selection_start_hour": None,
                "selection_stop_hour": None,
                "selected_fastq_count": selected_count,
                "selected_pass_filter_reads": _nonnegative_int(
                    value.get("selected_pass_filter_reads"),
                    label="ONT contributing selected_pass_filter_reads",
                ),
            }
        )
    return validated_flowcells, validated_cells


def _validate_generated(
    *, output_dir: Path, expected_aus: int, runtime_yaml: Path
) -> Mapping[str, Any]:
    manifests = load_manifest_set(output_dir)
    units = manifests.rows["analysis_units.tsv"]
    inputs = manifests.rows["sequencing_inputs.tsv"]
    links = manifests.rows["analysis_unit_inputs.tsv"]
    if (
        len(units) != expected_aus
        or len(inputs) != expected_aus * 2
        or len(links) != expected_aus * 2
    ):
        raise BjuiceConfigError(f"generated topology does not match {expected_aus} hybrid AUs")
    if any(row.get("ONT_FQ_START_HOUR") or row.get("ONT_FQ_END_HOUR") for row in units):
        raise BjuiceConfigError("crosswalk-run AUs must have blank full-input ONT hour slicing")
    roles: dict[str, list[str]] = {}
    for link in links:
        roles.setdefault(link["ANALYSIS_UNIT_UID"], []).append(link["ROLE"])
    if any(sorted(value) != ["lr", "sr"] for value in roles.values()):
        raise BjuiceConfigError("each generated AU must have exactly one SR and one LR input")
    runtime = yaml.safe_load(runtime_yaml.read_text(encoding="utf-8"))
    if "ont_fastq_hour_window_mode" in runtime:
        raise BjuiceConfigError(
            "runtime YAML must omit ont_fastq_hour_window_mode for blank full-input ONT slicing"
        )
    return {
        "manifest_hashes": dict(manifests.hashes),
        "analysis_unit_count": len(units),
        "sequencing_input_count": len(inputs),
        "analysis_unit_input_count": len(links),
    }


def materialize_bjuice_crosswalk_run(
    *,
    run_number: str,
    attachment: Path,
    internal_crosswalk: Path,
    source_inventory: Path,
    ilmn_mount: str,
    ont_mount: str,
    output_dir: Path,
) -> Mapping[str, Any]:
    """Build one exact attachment-selected six-manifest configuration capsule."""

    if run_number not in ILMN_SOURCE_BY_RUN:
        raise BjuiceConfigError(
            f"unsupported ILMN run {run_number}; expected one of {sorted(ILMN_SOURCE_BY_RUN)}"
        )
    if output_dir.exists() and any(output_dir.iterdir()):
        raise BjuiceConfigError(f"output directory is not empty: {output_dir}")
    ilmn_mount_path = _absolute_mount(ilmn_mount, field_name="ilmn_mount")
    ont_mount_path = _absolute_mount(ont_mount, field_name="ont_mount")
    attachment_columns, attachment_rows = _read_tsv(attachment)
    missing = sorted(ATTACHMENT_REQUIRED_COLUMNS - set(attachment_columns))
    if missing:
        raise BjuiceConfigError(f"attachment is missing required columns: {', '.join(missing)}")
    selected = [row for row in attachment_rows if row["ilmn_run"] == run_number]
    if not selected or len({row["unit_id"] for row in selected}) != len(selected):
        raise BjuiceConfigError(
            f"ILMN run {run_number} has no rows or duplicate attachment unit_id values"
        )
    if any(row["ilmn_ok"] != "TRUE" or row["ont_ok"] != "TRUE" for row in selected):
        raise BjuiceConfigError(
            f"ILMN run {run_number} includes an attachment row without explicit TRUE source verification"
        )
    crosswalk_columns, crosswalk_rows = _read_tsv(internal_crosswalk)
    if crosswalk_columns != CROSSWALK_COLUMNS:
        raise BjuiceConfigError(
            "internal crosswalk header must exactly match the reviewed crosswalk contract"
        )
    crosswalk_by_id = {row["CROSSWALK_ROW_ID"]: row for row in crosswalk_rows}
    if len(crosswalk_by_id) != len(crosswalk_rows):
        raise BjuiceConfigError("internal crosswalk has duplicate CROSSWALK_ROW_ID values")
    inventory = _read_inventory(source_inventory)
    selections = inventory["selections"]
    ilmn_source_id = ILMN_SOURCE_BY_RUN[run_number]
    synthetic_rows: list[dict[str, str]] = []
    synthetic_selections: dict[str, dict[str, Any]] = {}
    contributing_evidence: dict[str, tuple[list[dict[str, Any]], list[dict[str, Any]]]] = {}
    joins: list[dict[str, Any]] = []
    used_ont_sources: set[str] = set()
    for ordinal, row in enumerate(selected, start=1):
        ont_prefix = ONT_SOURCE_PREFIX_BY_RUN.get(row["ont_run"])
        if ont_prefix is None:
            raise BjuiceConfigError(
                f"attachment unit {row['unit_id']} has unsupported exact ont_run {row['ont_run']!r}"
            )
        try:
            ont_set = int(row["ont_set"])
        except ValueError as exc:
            raise BjuiceConfigError(
                f"attachment unit {row['unit_id']} has a non-integer ont_set"
            ) from exc
        ont_source_id = f"{ont_prefix}-set{ont_set}"
        chips = _chips(row["ont_chips"], unit_id=row["unit_id"])
        ilmn_matches: list[tuple[str, Mapping[str, Any]]] = []
        ont_matches: list[tuple[str, Mapping[str, Any]]] = []
        for key, value in selections.items():
            if not isinstance(value, Mapping):
                continue
            ilmn_by_source = value.get("ilmn")
            if isinstance(ilmn_by_source, Mapping) and isinstance(
                ilmn_by_source.get(ilmn_source_id), Mapping
            ):
                candidate = ilmn_by_source[ilmn_source_id]
                if candidate.get("sample_id") == row["ilmn_lib_id"]:
                    ilmn_matches.append((str(key), candidate))
            candidate_ont = value.get("ont")
            if (
                isinstance(candidate_ont, Mapping)
                and candidate_ont.get("source_id") == ont_source_id
                and candidate_ont.get("barcode") == row["ont_barcode"]
            ):
                ont_matches.append((str(key), candidate_ont))
        ilmn_key, ilmn = _one(ilmn_matches, label=f"ILMN {run_number} {row['ilmn_lib_id']}")
        ont_key, ont = _one(
            ont_matches, label=f"ONT {row['ont_run']} set {ont_set} {row['ont_barcode']}"
        )
        if ilmn_key not in crosswalk_by_id or ont_key not in crosswalk_by_id:
            raise BjuiceConfigError(
                f"attachment unit {row['unit_id']} has an inventory selection absent from internal crosswalk"
            )
        ilmn_meta, ont_meta = crosswalk_by_id[ilmn_key], crosswalk_by_id[ont_key]
        identities = {
            ilmn_meta["BIOLOGICAL_SAMPLE"],
            ont_meta["BIOLOGICAL_SAMPLE"],
            str(selections[ilmn_key].get("biological_sample") or ""),
            str(selections[ont_key].get("biological_sample") or ""),
        }
        if (
            len(identities) != 1
            or "" in identities
            or next(iter(identities)) not in {row["canonical"], row["ont_lib_name"]}
        ):
            raise BjuiceConfigError(
                f"attachment unit {row['unit_id']} has an explicit source-identity mismatch"
            )
        if (
            ilmn_meta.get("REVIEW_STATUS") != "REVIEWED"
            or ont_meta.get("REVIEW_STATUS") != "REVIEWED"
        ):
            raise BjuiceConfigError(
                f"attachment unit {row['unit_id']} references an unreviewed internal crosswalk row"
            )
        rewritten_ilmn, ilmn_receipt = _verified_ilmn_fastqs(
            ilmn,
            sample_id=row["ilmn_lib_id"],
            mount=ilmn_mount_path,
            unit_id=row["unit_id"],
        )
        rewritten_ont = dict(ont)
        fastqs, chip_receipt = _verified_ont_fastqs(
            ont,
            chips=chips,
            barcode=row["ont_barcode"],
            ont_set=ont_set,
            ont_mount=ont_mount_path,
            unit_id=row["unit_id"],
        )
        ilmn_flowcells, ont_cells = _contributing_data_evidence(
            ilmn=ilmn,
            ont=ont,
            ilmn_fastq_count=int(ilmn_receipt["selected_fastq_count"]),
            ilmn_lanes=[str(lane) for lane in rewritten_ilmn["lanes"]],
            chips=chips,
            chip_receipt=chip_receipt,
            unit_id=row["unit_id"],
        )
        rewritten_ont["fastqs"] = fastqs
        rewritten_ont["flowcell_id"] = ";".join(chips)
        synthetic_id = f"XW-ILMN{run_number}-{ordinal:02d}-{row['unit_id']}"
        merged = dict(ilmn_meta)
        for field in (
            "ONT_ALIAS",
            "ONT_DECODER_ALIAS",
            "ONT_DECODER_ORDINAL",
            "ONT_SET",
            "ONT_CHIP",
            "ONT_POSITION",
            "ONT_BARCODE",
        ):
            merged[field] = ont_meta[field]
        merged.update(
            {
                "CROSSWALK_ROW_ID": synthetic_id,
                "LOGICAL_RUN": run_number,
                "BIOLOGICAL_SAMPLE": next(iter(identities)),
                "CANONICAL_SAMPLE_RAW": next(iter(identities)),
                "ILMN_FASTQ_SAMPLE_ID": row["ilmn_lib_id"],
                "PAIRING_STATUS": "PAIRED",
                "BLOCKER": "",
                "REVIEW_STATUS": "REVIEWED",
                "SOURCE_NOTES": f"attachment unit {row['unit_id']}; ILMN inventory {ilmn_key}; ONT inventory {ont_key}; exact chips {','.join(chips)}",
            }
        )
        synthetic_rows.append(merged)
        synthetic_selections[synthetic_id] = {
            "biological_sample": merged["BIOLOGICAL_SAMPLE"],
            "ilmn": {ilmn_source_id: rewritten_ilmn},
            "logical_run": int(run_number),
            "ont": rewritten_ont,
            "pairing_status": "PAIRED",
        }
        contributing_evidence[synthetic_id] = (ilmn_flowcells, ont_cells)
        used_ont_sources.add(ont_source_id)
        joins.append(
            {
                "attachment_unit_id": row["unit_id"],
                "synthetic_crosswalk_row_id": synthetic_id,
                "biological_sample": merged["BIOLOGICAL_SAMPLE"],
                "ilmn_inventory_row": ilmn_key,
                "ilmn_source_id": ilmn_source_id,
                "ont_inventory_row": ont_key,
                "ont_source_id": ont_source_id,
                "ont_barcode": row["ont_barcode"],
                "ont_chips": list(chips),
                "ilmn_fastq_receipt": ilmn_receipt,
                "ont_fastq_count": len(fastqs),
                "chip_receipt": chip_receipt,
            }
        )
    bundle_id = f"ilmnrun{run_number}-crosswalk"
    synthetic_inventory = dict(inventory)
    synthetic_inventory["selections"] = synthetic_selections
    manifest_rows, receipt_units = _manifest_rows_for_bundle(
        bundle={
            "bundle_id": bundle_id,
            "logical_run": int(run_number),
            "ilmn_source_id": ilmn_source_id,
            "ont_source_ids": sorted(used_ont_sources),
            "expected_paired_aus": len(selected),
        },
        crosswalk_rows=synthetic_rows,
        inventory=synthetic_inventory,
    )
    for unit in manifest_rows["analysis_units.tsv"]:
        unit["ONT_FQ_START_HOUR"] = ""
        unit["ONT_FQ_END_HOUR"] = ""
        unit["ANALYSIS_UNIT_COMMENT"] = unit["ANALYSIS_UNIT_COMMENT"].replace(
            "ONT raw FASTQ interval [0,24)",
            "all verified declared-chip ONT FASTQs; no hour slicing",
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, rows in manifest_rows.items():
        _write_tsv(output_dir / name, MANIFEST_COLUMNS[name], rows)
    runtime = _runtime_config(
        bundle_id=bundle_id,
        sample_ids=sorted({row["SAMPLEID"] for row in manifest_rows["samples.tsv"]}),
    )
    runtime["bjuice_workflow_config_file"] = "config/dyec_runtime_config.yaml"
    runtime.pop("ont_fastq_hour_window_mode", None)
    runtime["multiqc_qc"]["contributing_data"] = {
        "enabled": True,
        "receipt": str(CONTRIBUTING_DATA_RECEIPT_RELATIVE_PATH),
        "sr_alignment": {"aligner": "sentdhiomr2sr", "deduper": "smd"},
    }
    runtime_yaml = output_dir / f"bjuice_crosswalk_{bundle_id}_hiomr2.yaml"
    runtime_yaml.write_text(
        yaml.safe_dump(runtime, sort_keys=False, default_flow_style=False), encoding="utf-8"
    )
    topology = _validate_generated(
        output_dir=output_dir, expected_aus=len(selected), runtime_yaml=runtime_yaml
    )
    links_by_unit: dict[str, dict[str, str]] = {}
    for link in load_manifest_set(output_dir).rows["analysis_unit_inputs.tsv"]:
        links_by_unit.setdefault(link["ANALYSIS_UNIT_UID"], {})[link["ROLE"]] = link[
            "SEQUENCING_INPUT_UID"
        ]
    contributing_units: list[dict[str, Any]] = []
    for unit in receipt_units:
        synthetic_id = str(unit["crosswalk_row_id"])
        au_uid = str(unit["analysis_unit_uid"])
        if synthetic_id not in contributing_evidence or set(links_by_unit.get(au_uid, {})) != {"sr", "lr"}:
            raise BjuiceConfigError("generated contributing-data receipt cannot reconcile AU inputs")
        flowcells, cells = contributing_evidence[synthetic_id]
        contributing_units.append(
            {
                "analysis_unit_uid": au_uid,
                "illumina_flowcells": [
                    {"sequencing_input_uid": links_by_unit[au_uid]["sr"], **flowcell}
                    for flowcell in flowcells
                ],
                "ont_cells": [
                    {"sequencing_input_uid": links_by_unit[au_uid]["lr"], **cell}
                    for cell in cells
                ],
            }
        )
    contributing_receipt = {
        "schema_version": CONTRIBUTING_DATA_SCHEMA,
        "manifest_sha256": topology["manifest_hashes"],
        "analysis_units": contributing_units,
    }
    contributing_path = output_dir / CONTRIBUTING_DATA_RECEIPT_RELATIVE_PATH
    contributing_path.parent.mkdir(parents=True, exist_ok=True)
    contributing_path.write_text(
        json.dumps(contributing_receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    receipt = {
        "schema": MATERIALIZATION_RECEIPT_SCHEMA,
        "generation_schema": GENERATION_RECEIPT_SCHEMA,
        "purpose": "attachment-selected crosswalk-run Bjuice materialization",
        "configuration_status": "CONFIG_COMPLETE",
        "bundle_id": bundle_id,
        "ilmn_run_number": int(run_number),
        "attachment": str(attachment),
        "attachment_sha256": _sha256(attachment),
        "internal_crosswalk": str(internal_crosswalk),
        "internal_crosswalk_sha256": _sha256(internal_crosswalk),
        "source_inventory": str(source_inventory),
        "source_inventory_sha256": _sha256(source_inventory),
        "mounts": {"ilmn_mount": str(ilmn_mount_path), "ont_mount": str(ont_mount_path)},
        "runtime_yaml": runtime_yaml.name,
        "runtime_yaml_sha256": _sha256(runtime_yaml),
        "contributing_data_receipt": str(CONTRIBUTING_DATA_RECEIPT_RELATIVE_PATH),
        "contributing_data_receipt_sha256": _sha256(contributing_path),
        "selection_contract": {
            "attachment_row_count": len(selected),
            "ilmn_source_id": ilmn_source_id,
            "ont_source_ids": sorted(used_ont_sources),
            "ont_hour_slicing": "blank_full_input",
            "joins_sha256": _canonical_hash(joins),
        },
        "topology": topology,
        "joins": joins,
        "analysis_units": receipt_units,
    }
    receipt_path = output_dir / "generation_receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"output_dir": output_dir, "receipt_path": receipt_path, "receipt": receipt}
