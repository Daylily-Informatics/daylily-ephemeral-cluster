"""Generate the fixed HG002 Bjuice v2 full-prevalence manifest set.

This is deliberately a separate contract from the generic Bjuice prevalence
helper.  It accepts exactly one direct Illumina coverage denominator backed by
one terminal receipt, emits the seven agreed analysis units, and never imports
or invents live EUIDs.  Source-owned EUID fields may be present in reviewed
inputs, but every nullable live EUID output field is intentionally blank.
"""

from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation, ROUND_DOWN, localcontext
from pathlib import Path
from typing import Any, Mapping, Sequence

import boto3

from daylily_ec.bjuice_preval_config import (
    ANALYSIS_UNIT_COLUMNS,
    ANALYSIS_UNIT_INPUT_COLUMNS,
    DEFAULT_FSX_RUN_MOUNT_ROOT,
    DEFAULT_ONT_FSX_ROOT,
    LIBRARY_COLUMNS,
    SAMPLE_COLUMNS,
    SEQUENCING_INPUT_COLUMNS,
    SPECIMEN_COLUMNS,
    BjuiceConfigError,
    BjuiceConfigResult,
    _dayoa_read_group_label,
    _index_one,
    _list_s3_objects,
    _matrix_rows_by_sample,
    _mappings_by_sample,
    _read_json,
    _read_tsv,
    _run_by_id,
    _sample_ilmn_fastqs,
    _sample_ont_fastqs,
    _sha256,
    _source_uri_by_id,
    _write_tsv,
)
from daylily_ec.manifest_set import load_manifest_set


HG002_SAMPLE_ID = "HG002"
DIRECT_ILMN_COVERAGE_RECEIPT_SCHEMA = "dyec.bjuice_v2_direct_ilmn_coverage_receipt.v1"
SUBSAMPLE_DECIMAL_PLACES = 12
SUBSAMPLE_QUANTUM = Decimal("0.000000000001")

V2_ANALYSIS_UNIT_COLUMNS = (
    *ANALYSIS_UNIT_COLUMNS[:8],
    "ONT_FQ_START_HOUR",
    "ONT_FQ_END_HOUR",
    *ANALYSIS_UNIT_COLUMNS[8:],
)
V2_MANIFEST_COLUMNS: Mapping[str, tuple[str, ...]] = {
    "specimens.tsv": SPECIMEN_COLUMNS,
    "samples.tsv": SAMPLE_COLUMNS,
    "libraries.tsv": LIBRARY_COLUMNS,
    "sequencing_inputs.tsv": SEQUENCING_INPUT_COLUMNS,
    "analysis_units.tsv": V2_ANALYSIS_UNIT_COLUMNS,
    "analysis_unit_inputs.tsv": ANALYSIS_UNIT_INPUT_COLUMNS,
}

# (AU label, target Illumina coverage, inclusive start / exclusive end ONT hour)
AU_MATRIX: tuple[tuple[str, Decimal, int, int], ...] = (
    ("p5xp5", Decimal("0.5"), 0, 1),
    ("1x1", Decimal("1"), 0, 2),
    ("3x3", Decimal("3"), 0, 7),
    ("5x5", Decimal("5"), 0, 11),
    ("10x5", Decimal("10"), 0, 19),
    ("15x5", Decimal("15"), 0, 24),
    ("15x10", Decimal("15"), 0, 19),
)
AU_ONT_TARGETS: Mapping[str, Decimal] = {
    "p5xp5": Decimal("0.5"),
    "1x1": Decimal("1"),
    "3x3": Decimal("3"),
    "5x5": Decimal("5"),
    "10x5": Decimal("5"),
    "15x5": Decimal("5"),
    "15x10": Decimal("10"),
}
RETARGET_PLAN_SCHEMA = "dyec.bjuice_v2_hg002_retarget_plan.v1"


def _parse_direct_coverage(value: str, *, field_name: str) -> Decimal:
    text = str(value or "").strip()
    if not text:
        raise BjuiceConfigError(f"{field_name} is required")
    try:
        parsed = Decimal(text)
    except InvalidOperation as exc:
        raise BjuiceConfigError(f"{field_name} must be a decimal coverage value; found {value!r}") from exc
    if not parsed.is_finite() or parsed <= 0:
        raise BjuiceConfigError(f"{field_name} must be finite and greater than zero; found {value!r}")
    return parsed


def _format_subsample_pct(*, target_x: Decimal, coverage_x: Decimal, au_label: str) -> str:
    if target_x > coverage_x:
        raise BjuiceConfigError(
            f"AU {au_label} target {target_x}x exceeds verified direct Illumina coverage "
            f"{coverage_x}x"
        )
    with localcontext() as context:
        context.prec = 50
        value = target_x / coverage_x
    rounded = value.quantize(SUBSAMPLE_QUANTUM, rounding=ROUND_DOWN)
    if rounded <= 0:
        raise BjuiceConfigError(
            f"AU {au_label} produced a non-positive rounded SUBSAMPLE_PCT from "
            f"target {target_x}x and coverage {coverage_x}x"
        )
    return format(rounded, "f")


def _parse_subsample_pct(value: Any, *, field_name: str) -> Decimal:
    parsed = _parse_direct_coverage(str(value or ""), field_name=field_name)
    if parsed > 1:
        raise BjuiceConfigError(f"{field_name} must not exceed 1; found {value!r}")
    return parsed


def _load_retarget_plan(
    path: Path, *, direct_ilmn_coverage_x: Decimal
) -> Mapping[str, Mapping[str, Any]]:
    """Load the explicit, fixed-seven-AU measurement-based retarget plan.

    This contract deliberately rejects partial/general manifest edits. It only
    accepts the canonical Bjuice-v2 labels and targets and proves that each
    requested fraction is independently derived from the verified direct
    Illumina denominator. Prior observations are retained as audit metadata;
    they cannot override the full-prevalence source denominator.
    """
    if not path.is_file():
        raise BjuiceConfigError(f"retarget plan is missing: {path}")
    payload = _read_json(path)
    if payload.get("schema") != RETARGET_PLAN_SCHEMA:
        raise BjuiceConfigError(f"retarget plan schema must be {RETARGET_PLAN_SCHEMA}")
    if str(payload.get("sample_id") or "").strip() != HG002_SAMPLE_ID:
        raise BjuiceConfigError("retarget plan must be for HG002")
    if not str(payload.get("source_analysis_id") or "").strip():
        raise BjuiceConfigError("retarget plan must declare source_analysis_id")
    rows = payload.get("analysis_units")
    if not isinstance(rows, list):
        raise BjuiceConfigError("retarget plan analysis_units must be a list")
    expected_targets = {label: target for label, target, _start, _end in AU_MATRIX}
    if len(rows) != len(expected_targets):
        raise BjuiceConfigError(f"retarget plan must contain exactly {len(expected_targets)} analysis units")
    by_label: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            raise BjuiceConfigError("retarget plan analysis_units rows must be objects")
        label = str(row.get("label") or "").strip()
        if label in by_label:
            raise BjuiceConfigError(f"retarget plan has duplicate AU label {label!r}")
        by_label[label] = row
    if set(by_label) != set(expected_targets):
        raise BjuiceConfigError(
            "retarget plan labels must exactly match the canonical AU matrix; found "
            + ", ".join(sorted(by_label))
        )
    for label, target_x in expected_targets.items():
        row = by_label[label]
        declared_target = _parse_direct_coverage(
            str(row.get("target_ilmn_coverage_x") or ""),
            field_name=f"retarget plan {label} target_ilmn_coverage_x",
        )
        if declared_target != target_x:
            raise BjuiceConfigError(
                f"retarget plan {label} target_ilmn_coverage_x must be {target_x}; found {declared_target}"
            )
        prior_measured = _parse_direct_coverage(
            str(row.get("prior_measured_ilmn_coverage_x") or ""),
            field_name=f"retarget plan {label} prior_measured_ilmn_coverage_x",
        )
        prior_pct = _parse_subsample_pct(
            row.get("prior_subsample_pct"), field_name=f"retarget plan {label} prior_subsample_pct"
        )
        actual_pct = _parse_subsample_pct(
            row.get("subsample_pct"), field_name=f"retarget plan {label} subsample_pct"
        )
        expected_pct = _format_subsample_pct(
            target_x=target_x,
            coverage_x=direct_ilmn_coverage_x,
            au_label=label,
        )
        if format(actual_pct.quantize(SUBSAMPLE_QUANTUM), "f") != expected_pct:
            raise BjuiceConfigError(
                f"retarget plan {label} subsample_pct must equal target_ilmn_coverage_x / "
                f"verified direct_ilmn_coverage_x ({format(direct_ilmn_coverage_x, 'f')}) "
                f"rounded down: {expected_pct}"
            )
        declared_ont_target = _parse_direct_coverage(
            str(row.get("target_ont_coverage_x") or ""),
            field_name=f"retarget plan {label} target_ont_coverage_x",
        )
        if declared_ont_target != AU_ONT_TARGETS[label]:
            raise BjuiceConfigError(
                f"retarget plan {label} target_ont_coverage_x must be {AU_ONT_TARGETS[label]}; "
                f"found {declared_ont_target}"
            )
        try:
            start_hour = int(row.get("ont_fq_start_hour"))
            end_hour = int(row.get("ont_fq_end_hour"))
        except (TypeError, ValueError) as exc:
            raise BjuiceConfigError(f"retarget plan {label} ONT hours must be integers") from exc
        if start_hour != 0 or end_hour <= start_hour:
            raise BjuiceConfigError(
                f"retarget plan {label} requires a valid cumulative [0,end) ONT interval"
            )
    return by_label


def _load_direct_ilmn_coverage_receipt(
    path: Path,
    *,
    requested_coverage_x: Decimal,
) -> Mapping[str, Any]:
    if not path.is_file():
        raise BjuiceConfigError(f"direct Illumina coverage evidence is missing: {path}")
    receipt = _read_json(path)
    if receipt.get("schema") != DIRECT_ILMN_COVERAGE_RECEIPT_SCHEMA:
        raise BjuiceConfigError(
            "direct Illumina coverage evidence schema must be "
            f"{DIRECT_ILMN_COVERAGE_RECEIPT_SCHEMA}"
        )
    if str(receipt.get("sample_id") or "").strip() != HG002_SAMPLE_ID:
        raise BjuiceConfigError("direct Illumina coverage evidence must be for HG002")
    if str(receipt.get("status") or "").strip().lower() != "terminal":
        raise BjuiceConfigError("direct Illumina coverage evidence status must be terminal")
    if "ilmn_direct_coverage_x" not in receipt:
        raise BjuiceConfigError(
            "direct Illumina coverage evidence must provide ilmn_direct_coverage_x; "
            "total or hybrid coverage is not accepted"
        )
    forbidden = [
        key
        for key in receipt
        if "hybrid" in str(key).lower()
        or "total_coverage" in str(key).lower()
        or "combined_coverage" in str(key).lower()
    ]
    if forbidden:
        raise BjuiceConfigError(
            "direct Illumina coverage evidence is ambiguous because it includes non-direct "
            "coverage fields: "
            + ", ".join(sorted(forbidden))
        )
    receipt_coverage_x = _parse_direct_coverage(
        str(receipt["ilmn_direct_coverage_x"]),
        field_name="direct Illumina coverage evidence ilmn_direct_coverage_x",
    )
    if receipt_coverage_x != requested_coverage_x:
        raise BjuiceConfigError(
            "--direct-ilmn-coverage-x does not exactly match direct Illumina coverage evidence: "
            f"{requested_coverage_x} != {receipt_coverage_x}"
        )
    return receipt


def _required_matching_value(
    *,
    field: str,
    primary: Mapping[str, str],
    secondary: Mapping[str, str],
) -> str:
    primary_value = str(primary.get(field) or "").strip()
    secondary_value = str(secondary.get(field) or "").strip()
    if primary_value and secondary_value and primary_value != secondary_value:
        raise BjuiceConfigError(
            f"HG002 {field} is ambiguous between sample metadata and legacy units TSV"
        )
    value = primary_value or secondary_value
    if not value:
        raise BjuiceConfigError(
            f"HG002 {field} is missing from both sample metadata and legacy units TSV"
        )
    return value


def _source_uri(source_uri_by_id: Mapping[str, str], source_id: str, *, owner: str) -> str:
    try:
        return source_uri_by_id[source_id]
    except KeyError as exc:
        raise BjuiceConfigError(f"{owner} references missing source_id {source_id!r}") from exc


def generate_bjuice_v2_hg002_multi_au_manifests(
    *,
    output_dir: Path,
    source_manifest_json: Path,
    run_evidence_json: Path,
    library_run_matrix_tsv: Path,
    sample_metadata_tsv: Path,
    legacy_units_tsv: Path,
    direct_ilmn_coverage_x: str,
    direct_ilmn_coverage_evidence: Path,
    retarget_plan_json: Path | None = None,
    profile: str | None,
    region: str | None,
    fsx_run_mount_root: str = DEFAULT_FSX_RUN_MOUNT_ROOT,
    ont_fsx_root: str = DEFAULT_ONT_FSX_ROOT,
) -> BjuiceConfigResult:
    """Write the fixed HG002 Bjuice v2 seven-AU DayOA six-manifest set.

    ``direct_ilmn_coverage_x`` must be the exact denominator in a terminal,
    direct-only receipt. It is not inferred from source FASTQs, read counts,
    total coverage, or hybrid coverage. When ``retarget_plan_json`` is present,
    its strict, measurement-derived fractions and ONT intervals replace only
    the canonical defaults; the seven labels/targets remain immutable.
    """

    if output_dir.exists() and any(output_dir.iterdir()):
        raise BjuiceConfigError(f"output directory already exists and is not empty: {output_dir}")

    coverage_x = _parse_direct_coverage(
        direct_ilmn_coverage_x,
        field_name="direct Illumina coverage",
    )
    _load_direct_ilmn_coverage_receipt(
        direct_ilmn_coverage_evidence,
        requested_coverage_x=coverage_x,
    )
    retarget_plan = (
        _load_retarget_plan(retarget_plan_json, direct_ilmn_coverage_x=coverage_x)
        if retarget_plan_json
        else None
    )
    for au_label, target_x, _start_hour, _end_hour in AU_MATRIX:
        _format_subsample_pct(target_x=target_x, coverage_x=coverage_x, au_label=au_label)

    source_manifest = _read_json(source_manifest_json)
    run_evidence = _read_json(run_evidence_json)
    if source_manifest.get("schema") != "ursa.bjuice_hybrid_source_manifest.v1":
        raise BjuiceConfigError("source manifest schema must be ursa.bjuice_hybrid_source_manifest.v1")
    if run_evidence.get("schema") != "ursa.bjuice_hybrid_run_evidence.v2":
        raise BjuiceConfigError("run evidence schema must be ursa.bjuice_hybrid_run_evidence.v2")

    _matrix_columns, matrix_rows = _read_tsv(library_run_matrix_tsv)
    _metadata_columns, metadata_rows = _read_tsv(sample_metadata_tsv)
    _unit_columns, unit_rows = _read_tsv(legacy_units_tsv)
    metadata_by_sample = _index_one(metadata_rows, "SAMPLEID")
    units_by_sample = _index_one(unit_rows, "SAMPLEID")
    matrix_by_sample = _matrix_rows_by_sample(matrix_rows)
    if HG002_SAMPLE_ID not in metadata_by_sample:
        raise BjuiceConfigError("sample metadata is missing HG002")
    if HG002_SAMPLE_ID not in units_by_sample:
        raise BjuiceConfigError("legacy units metadata is missing HG002")
    if HG002_SAMPLE_ID not in matrix_by_sample:
        raise BjuiceConfigError("library/run matrix is missing HG002")
    matrix_rows_for_sample = matrix_by_sample[HG002_SAMPLE_ID]
    if set(matrix_rows_for_sample) != {"ILMN", "ONT"}:
        raise BjuiceConfigError("HG002 library/run matrix must contain exactly ILMN and ONT rows")

    metadata = metadata_by_sample[HG002_SAMPLE_ID]
    unit_metadata = units_by_sample[HG002_SAMPLE_ID]
    sample_use = _required_matching_value(
        field="SAMPLEUSE", primary=metadata, secondary=unit_metadata
    )
    order_type = _required_matching_value(
        field="ORDER_TYPE", primary=metadata, secondary=unit_metadata
    )
    bwa_kmer = _required_matching_value(
        field="BWA_KMER", primary=metadata, secondary=unit_metadata
    )
    deep_model = _required_matching_value(
        field="DEEP_MODEL", primary=metadata, secondary=unit_metadata
    )
    merge_single = _required_matching_value(
        field="MERGE_SINGLE", primary=metadata, secondary=unit_metadata
    )

    source_uri_by_id = _source_uri_by_id(source_manifest)
    runs_by_id = _run_by_id(source_manifest)
    mappings_by_sample = _mappings_by_sample(source_manifest)
    ilmn_runs = [
        run for run in runs_by_id.values() if str(run.get("platform") or "").upper() == "ILMN"
    ]
    if len(ilmn_runs) != 1:
        raise BjuiceConfigError(f"expected exactly one ILMN run; found {len(ilmn_runs)}")
    ilmn_run = ilmn_runs[0]
    ilmn_run_id = str(ilmn_run.get("run_id") or "").strip()
    if not ilmn_run_id:
        raise BjuiceConfigError("ILMN run is missing run_id")
    ilmn_run_label = _dayoa_read_group_label(ilmn_run_id, field_name="ILMN run_id")
    ilmn_prefix = _source_uri(
        source_uri_by_id,
        str(ilmn_run.get("prefix_source_id") or "").strip(),
        owner="ILMN run",
    )

    mappings = mappings_by_sample.get(HG002_SAMPLE_ID, [])
    if len(mappings) != 3:
        raise BjuiceConfigError(f"HG002 must have exactly three ONT mappings; found {len(mappings)}")
    mapping_keys: set[tuple[str, str]] = set()
    for mapping in mappings:
        run_id = str(mapping.get("run_id") or "").strip()
        barcode = str(mapping.get("barcode") or "").strip()
        if not run_id or not barcode:
            raise BjuiceConfigError("HG002 ONT mappings require non-empty run_id and barcode")
        key = (run_id, barcode)
        if key in mapping_keys:
            raise BjuiceConfigError(f"duplicate HG002 ONT mapping for {run_id} {barcode}")
        mapping_keys.add(key)
        run = runs_by_id.get(run_id)
        if run is None or str(run.get("platform") or "").upper() != "ONT":
            raise BjuiceConfigError(f"HG002 mapping references non-ONT run {run_id}")
        _source_uri(
            source_uri_by_id,
            str(run.get("prefix_source_id") or "").strip(),
            owner=f"ONT run {run_id}",
        )

    session_kwargs: dict[str, str] = {}
    if profile:
        session_kwargs["profile_name"] = profile
    if region:
        session_kwargs["region_name"] = region
    s3_client = boto3.Session(**session_kwargs).client("s3")
    ilmn_s3_paths = _list_s3_objects(s3_client=s3_client, prefix_uri=ilmn_prefix)
    ilmn_r1_paths, ilmn_r2_paths = _sample_ilmn_fastqs(
        s3_paths=ilmn_s3_paths,
        sample_id=HG002_SAMPLE_ID,
        run_id=ilmn_run_id,
        fsx_run_mount_root=fsx_run_mount_root,
        ont_fsx_root=ont_fsx_root,
    )

    ont_s3_paths_by_run: dict[str, list[str]] = {}
    ont_input_rows: list[dict[str, str]] = []
    receipt_ont_inputs: list[dict[str, Any]] = []
    seen_input_uids: set[str] = set()
    for mapping in mappings:
        run_id = str(mapping["run_id"])
        barcode = str(mapping["barcode"])
        run = runs_by_id[run_id]
        prefix_uri = _source_uri(
            source_uri_by_id,
            str(run.get("prefix_source_id") or "").strip(),
            owner=f"ONT run {run_id}",
        )
        if run_id not in ont_s3_paths_by_run:
            ont_s3_paths_by_run[run_id] = _list_s3_objects(
                s3_client=s3_client,
                prefix_uri=prefix_uri,
            )
        ont_paths = _sample_ont_fastqs(
            s3_paths=ont_s3_paths_by_run[run_id],
            barcode=barcode,
            run_id=run_id,
            fsx_run_mount_root=fsx_run_mount_root,
            ont_fsx_root=ont_fsx_root,
        )
        run_label = _dayoa_read_group_label(run_id, field_name=f"HG002 ONT run_id")
        barcode_label = _dayoa_read_group_label(barcode, field_name=f"HG002 {run_id} barcode")
        input_uid = f"{HG002_SAMPLE_ID}-ONT-{run_label}-{barcode_label}"
        if input_uid in seen_input_uids:
            raise BjuiceConfigError(f"duplicate generated sequencing input UID {input_uid}")
        seen_input_uids.add(input_uid)
        ont_input_rows.append(
            {
                "SEQUENCING_INPUT_UID": input_uid,
                "POOL_TUBE_EUID": "",
                "SEQUENCING_RUN_EUID": "",
                "SOURCE_ARTIFACT_EUID": "",
                "LIBRARY_ID": f"{HG002_SAMPLE_ID}-ONT",
                "MODALITY": "lr",
                "LAYOUT": "single_fastq",
                "RUNID": run_label,
                "EXPERIMENTID": "bjuice-v2-hg002-full-preval",
                "LANEID": str(run.get("position_id") or ""),
                "BARCODEID": barcode,
                "SEQ_PLATFORM": "PROMETHION",
                "SEQ_VENDOR": "ONT",
                "ONT_R1_PATH": ",".join(ont_paths),
                "SEQUENCING_INPUT_COMMENT": (
                    "HG002 ONT input from reviewed full-prevalence source prefix "
                    f"{prefix_uri}; raw run ID {run_id}; barcode {barcode}"
                ),
            }
        )
        receipt_ont_inputs.append(
            {
                "run_id": run_id,
                "dayoa_run_label": run_label,
                "barcode": barcode,
                "sequencing_input_uid": input_uid,
                "fastq_count": len(ont_paths),
                "prefix_uri": prefix_uri,
            }
        )

    ilmn_input_uid = f"{HG002_SAMPLE_ID}-ILMN-{ilmn_run_label}"
    if ilmn_input_uid in seen_input_uids:
        raise BjuiceConfigError(f"duplicate generated sequencing input UID {ilmn_input_uid}")
    sequencing_inputs: list[dict[str, str]] = [
        {
            "SEQUENCING_INPUT_UID": ilmn_input_uid,
            "POOL_TUBE_EUID": "",
            "SEQUENCING_RUN_EUID": "",
            "SOURCE_ARTIFACT_EUID": "",
            "LIBRARY_ID": f"{HG002_SAMPLE_ID}-ILMN",
            "MODALITY": "sr",
            "LAYOUT": "paired_fastq",
            "RUNID": ilmn_run_label,
            "EXPERIMENTID": "bjuice-v2-hg002-full-preval",
            "LANEID": str(ilmn_run.get("position_id") or ""),
            "BARCODEID": HG002_SAMPLE_ID,
            "SEQ_PLATFORM": "NOVASEQ",
            "SEQ_VENDOR": "ILMN",
            "ILMN_R1_PATH": ",".join(ilmn_r1_paths),
            "ILMN_R2_PATH": ",".join(ilmn_r2_paths),
            "SEQUENCING_INPUT_COMMENT": (
                "HG002 Illumina input from reviewed full-prevalence source prefix "
                f"{ilmn_prefix}; raw run ID {ilmn_run_id}"
            ),
        },
        *ont_input_rows,
    ]

    specimens = [
        {
            "SPECIMEN_ID": HG002_SAMPLE_ID,
            "SPECIMEN_EUID": "",
            "SAMPLESOURCE": metadata.get("SAMPLESOURCE", ""),
            "SPECIMEN_TYPE": metadata.get("SAMPLE_TYPE", ""),
            "EXTERNAL_SPECIMEN_ID": HG002_SAMPLE_ID,
            "BIOLOGICAL_SEX": metadata.get("BIOLOGICAL_SEX", ""),
            "N_X": metadata.get("N_X", ""),
            "N_Y": metadata.get("N_Y", ""),
            "SPECIMEN_COMMENT": "Bjuice v2 HG002 full-prevalence analysis specimen.",
        }
    ]
    samples = [
        {
            "SAMPLEID": HG002_SAMPLE_ID,
            "SAMPLE_EUID": "",
            "SPECIMEN_ID": HG002_SAMPLE_ID,
            "SAMPLECLASS": metadata.get("SAMPLECLASS", ""),
            "SAMPLE_TYPE": metadata.get("SAMPLE_TYPE", ""),
            "SAMPLEUSE": sample_use,
            "ORDER_TYPE": order_type,
            "CONCORDANCE_CONTROL_PATH": metadata.get("CONCORDANCE_CONTROL_PATH", ""),
            "IS_POSITIVE_CONTROL": metadata.get("IS_POSITIVE_CONTROL", ""),
            "IS_NEGATIVE_CONTROL": metadata.get("IS_NEGATIVE_CONTROL", ""),
            "TUM_NRM_SAMPLEID_MATCH": metadata.get("TUM_NRM_SAMPLEID_MATCH", ""),
            "EXTERNAL_SAMPLE_ID": metadata.get("EXTERNAL_SAMPLE_ID", HG002_SAMPLE_ID),
            "IDDNA_UID": metadata.get("IDDNA_UID", ""),
            "TRUTH_DATA_DIR": metadata.get("TRUTH_DATA_DIR", ""),
            "SAMPLE_COMMENT": "Bjuice v2 HG002 full-prevalence analysis sample.",
        }
    ]
    libraries = [
        {
            "LIBRARY_ID": f"{HG002_SAMPLE_ID}-ILMN",
            "LIBRARY_EUID": "",
            "SAMPLEID": HG002_SAMPLE_ID,
            "LIBPREP": str(matrix_rows_for_sample["ILMN"].get("LIBPREP") or ""),
            "AMPLIFICATION_TYPE": str(
                matrix_rows_for_sample["ILMN"].get("AMPLIFICATION_TYPE") or ""
            ),
            "LIBRARY_COMMENT": "HG002 Bjuice v2 full-prevalence Illumina library.",
        },
        {
            "LIBRARY_ID": f"{HG002_SAMPLE_ID}-ONT",
            "LIBRARY_EUID": "",
            "SAMPLEID": HG002_SAMPLE_ID,
            "LIBPREP": str(matrix_rows_for_sample["ONT"].get("LIBPREP") or ""),
            "AMPLIFICATION_TYPE": str(
                matrix_rows_for_sample["ONT"].get("AMPLIFICATION_TYPE") or ""
            ),
            "LIBRARY_COMMENT": "HG002 Bjuice v2 full-prevalence ONT library.",
        },
    ]

    analysis_units: list[dict[str, str]] = []
    analysis_unit_inputs: list[dict[str, str]] = []
    generated_aus: list[dict[str, Any]] = []
    for au_label, target_x, start_hour, end_hour in AU_MATRIX:
        analysis_unit_uid = f"{HG002_SAMPLE_ID}-{au_label}"
        if retarget_plan:
            retarget_row = retarget_plan[au_label]
            subsample_pct = _format_subsample_pct(
                target_x=target_x,
                coverage_x=coverage_x,
                au_label=au_label,
            )
            start_hour = int(retarget_row["ont_fq_start_hour"])
            end_hour = int(retarget_row["ont_fq_end_hour"])
            comment = (
                f"Bjuice v2 HG002 AU {au_label}: direct ILMN target {target_x}x / "
                f"verified {coverage_x}x; measured ONT target "
                f"{retarget_row['target_ont_coverage_x']}x interval [{start_hour},{end_hour})."
            )
        else:
            subsample_pct = _format_subsample_pct(
                target_x=target_x,
                coverage_x=coverage_x,
                au_label=au_label,
            )
            comment = (
                f"Bjuice v2 HG002 AU {au_label}: direct ILMN target {target_x}x / "
                f"{coverage_x}x; ONT interval [{start_hour},{end_hour})."
            )
        analysis_units.append(
            {
                "ANALYSIS_UNIT_UID": analysis_unit_uid,
                "ANALYSIS_UNIT_EUID": "",
                "SAMPLEID": HG002_SAMPLE_ID,
                "DELIVERY_EUID": "",
                "DELIVERY_PROFILE": "",
                "CUSTOMER_DELIVERY_ID": "",
                "SUBSAMPLE_PCT": subsample_pct,
                "ONT_SUBSAMPLE_PCT": "",
                "ONT_FQ_START_HOUR": str(start_hour),
                "ONT_FQ_END_HOUR": str(end_hour),
                "ALIGNED_REF_UID": "",
                "BWA_KMER": bwa_kmer,
                "DEEP_MODEL": deep_model,
                "MERGE_SINGLE": merge_single,
                "ANALYSIS_UNIT_COMMENT": comment,
            }
        )
        for ordinal, sequencing_input in enumerate(sequencing_inputs, start=1):
            analysis_unit_inputs.append(
                {
                    "ANALYSIS_UNIT_UID": analysis_unit_uid,
                    "SEQUENCING_INPUT_UID": sequencing_input["SEQUENCING_INPUT_UID"],
                    "ROLE": "sr" if ordinal == 1 else "lr",
                    "INPUT_ORDINAL": str(ordinal),
                }
            )
        generated_aus.append(
            {
                "analysis_unit_uid": analysis_unit_uid,
                "target_ilmn_coverage_x": str(target_x),
                "subsample_pct": subsample_pct,
                "ont_fq_start_hour": start_hour,
                "ont_fq_end_hour": end_hour,
                **(
                    {
                        "prior_measured_ilmn_coverage_x": str(
                            retarget_plan[au_label]["prior_measured_ilmn_coverage_x"]
                        ),
                        "prior_subsample_pct": str(retarget_plan[au_label]["prior_subsample_pct"]),
                        "target_ont_coverage_x": str(retarget_plan[au_label]["target_ont_coverage_x"]),
                    }
                    if retarget_plan
                    else {}
                ),
            }
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_rows: Mapping[str, Sequence[Mapping[str, str]]] = {
        "specimens.tsv": specimens,
        "samples.tsv": samples,
        "libraries.tsv": libraries,
        "sequencing_inputs.tsv": sequencing_inputs,
        "analysis_units.tsv": analysis_units,
        "analysis_unit_inputs.tsv": analysis_unit_inputs,
    }
    for filename, rows in manifest_rows.items():
        _write_tsv(output_dir / filename, V2_MANIFEST_COLUMNS[filename], rows)
    manifest_set = load_manifest_set(output_dir)
    receipt: dict[str, Any] = {
        "schema": "dyec.bjuice_v2_hg002_multi_au_manifest_generation.v1",
        "sample_id": HG002_SAMPLE_ID,
        "coverage_method": "direct_illumina_terminal_receipt",
        "direct_ilmn_coverage_x": str(coverage_x),
        "direct_ilmn_coverage_evidence": str(direct_ilmn_coverage_evidence),
        "direct_ilmn_coverage_evidence_sha256": _sha256(direct_ilmn_coverage_evidence),
        "retarget_plan": (
            {
                "schema": RETARGET_PLAN_SCHEMA,
                "path": str(retarget_plan_json),
                "sha256": _sha256(retarget_plan_json),
                "mode": "measured_ont_hours_direct_ilmn_denominator",
            }
            if retarget_plan_json
            else None
        ),
        "subsample_rounding": {
            "mode": "ROUND_DOWN",
            "decimal_places": SUBSAMPLE_DECIMAL_PLACES,
        },
        "analysis_units": generated_aus,
        "source_manifest_json": str(source_manifest_json),
        "run_evidence_json": str(run_evidence_json),
        "library_run_matrix_tsv": str(library_run_matrix_tsv),
        "sample_metadata_tsv": str(sample_metadata_tsv),
        "legacy_units_tsv": str(legacy_units_tsv),
        "fsx_run_mount_root": fsx_run_mount_root,
        "ont_fsx_root": ont_fsx_root,
        "source_observations": {
            "ilmn_run_id": ilmn_run_id,
            "ilmn_dayoa_run_label": ilmn_run_label,
            "ilmn_prefix": ilmn_prefix,
            "ilmn_fastq_r1_count": len(ilmn_r1_paths),
            "ilmn_fastq_r2_count": len(ilmn_r2_paths),
            "ont_inputs": receipt_ont_inputs,
        },
        "manifest_hashes": dict(manifest_set.hashes),
    }
    receipt_path = output_dir / "bjuice_v2_hg002_multi_au_manifest_receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return BjuiceConfigResult(
        output_dir=output_dir,
        receipt_path=receipt_path,
        manifest_hashes=dict(manifest_set.hashes),
        receipt=receipt,
    )
