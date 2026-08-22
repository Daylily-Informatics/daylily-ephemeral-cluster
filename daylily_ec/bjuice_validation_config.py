"""Build fail-closed Bjuice validation source inventories and DayOA configs.

This module is deliberately separate from the prevalence and HG002-only
generators.  It consumes a reviewed workbook crosswalk and an explicit source
specification, inventories S3 read-only, and emits local six-manifest sets.  It
does not create identities, write S3, create mounts, launch DayOA, or mutate a
cluster.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlparse

import boto3
import yaml

from daylily_ec.bjuice_preval_config import (
    ANALYSIS_UNIT_COLUMNS,
    ANALYSIS_UNIT_INPUT_COLUMNS,
    LIBRARY_COLUMNS,
    SAMPLE_COLUMNS,
    SEQUENCING_INPUT_COLUMNS,
    SPECIMEN_COLUMNS,
    BjuiceConfigError,
    _dayoa_read_group_label,
    _sha256,
    _write_tsv,
)
from daylily_ec.manifest_set import load_manifest_set

SOURCE_SPEC_SCHEMA = "dyec.bjuice_validation_source_spec.v1"
SOURCE_INVENTORY_SCHEMA = "dyec.bjuice_validation_source_inventory.v1"
GENERATION_RECEIPT_SCHEMA = "dyec.bjuice_validation_config_generation.v1"
WORKBOOK_EXTRACT_SCHEMA = "codex.artifact_tool.bjuice_validation_workbook_extract.v1"
EXPECTED_WORKBOOK_SHA256 = "face0fc30a241b87ee02223c3f8117a831a6c16b17233b395ae8a15f4ba8bdd7"
EXPECTED_MAPPED_ROWS = {1: 48, 2: 33, 3: 35, 4: 41}
EXPECTED_PAIRED_ROWS = {1: 32, 2: 19, 3: 17, 4: 31}
EXPECTED_ONT_ROWS = {1: 32, 2: 32, 3: 32, 4: 32}
EXPECTED_SOURCE_COUNT = 37
ONT_START_HOUR = 0
ONT_END_HOUR = 24
DYEC_BASELINE = {
    "release_version": "18.0.43",
    "release_tag_object": "f46b58b6bdae0ccc9a621fb9f5d88ef8feafd6dd",
    "release_commit": "7e7e9a1bb0ce9b6989ab31b19e945a83c8a6fcbe",
    "catalog_snapshot": "dyec_builds.18.0.43",
    "pinned_dayoa_version": "15.0.24",
    "command_contract": "bjuice-v2-hg002-custom-multi-analysis-unit-hiomr2-kitchensink-mega",
}
DAYOA_BASELINE = {
    "requested_version": "15.0.24",
    "requested_commit": "9cd4e43fded97ea57f11f19c164ab1fbe3fa77d4",
}

ANALYSIS_UNIT_COLUMNS_WITH_ONT_HOURS = (
    *ANALYSIS_UNIT_COLUMNS[:8],
    "ONT_FQ_START_HOUR",
    "ONT_FQ_END_HOUR",
    *ANALYSIS_UNIT_COLUMNS[8:],
)
MANIFEST_COLUMNS: Mapping[str, tuple[str, ...]] = {
    "specimens.tsv": SPECIMEN_COLUMNS,
    "samples.tsv": SAMPLE_COLUMNS,
    "libraries.tsv": LIBRARY_COLUMNS,
    "sequencing_inputs.tsv": SEQUENCING_INPUT_COLUMNS,
    "analysis_units.tsv": ANALYSIS_UNIT_COLUMNS_WITH_ONT_HOURS,
    "analysis_unit_inputs.tsv": ANALYSIS_UNIT_INPUT_COLUMNS,
}

CROSSWALK_COLUMNS = (
    "CROSSWALK_ROW_ID",
    "WORKBOOK_ROW",
    "LOGICAL_RUN",
    "CANONICAL_SAMPLE_RAW",
    "BIOLOGICAL_SAMPLE",
    "ILMN_ALIAS",
    "ILMN_FASTQ_SAMPLE_ID",
    "ONT_ALIAS",
    "ONT_DECODER_ALIAS",
    "ONT_DECODER_ORDINAL",
    "ONT_SET",
    "ONT_CHIP",
    "ONT_POSITION",
    "ONT_BARCODE",
    "SOURCE_INTERNAL_ID",
    "MAPPING_INTERNAL_ID",
    "MAPPING_POOL_ID",
    "MATERIAL_CLASS",
    "ANALYSIS_ROLE",
    "VARIANT_FEATURE",
    "PAIRING_STATUS",
    "BLOCKER",
    "REVIEW_STATUS",
    "SOURCE_NOTES",
)

ILMN_FASTQ_RE = re.compile(r"^(?P<sample>.+)_S\d+_L(?P<lane>\d{3})_R(?P<mate>[12])_001\.fastq\.gz$")
ONT_FASTQ_RE = re.compile(
    r"^(?P<flowcell>[A-Z0-9]+)_pass_(?P<barcode>barcode\d{2})_"
    r"(?P<protocol>[0-9a-f]+)_(?P<acquisition>[0-9a-f]+)_(?P<hour>\d+)\.fastq\.gz$"
)
SAFE_LOCAL_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]*$")
GIAB_SNV_TRUTH_ROOT = (
    "/fsx/references/genomic_data/organism_annotations/H_sapiens/hg38/controls/giab/snv/v4.2.1"
)
GIAB_SEX = {
    "HG001": ("female", "2", "0"),
    "HG002": ("male", "1", "1"),
    "HG003": ("male", "1", "1"),
    "HG004": ("female", "2", "0"),
}
HG002_SV_TRUTHSET = {
    "alt_id": "HG002",
    "regions": {
        "giab_sv_v5_0q_hc": {
            "truth_vcf": (
                "/fsx/references/genomic_data/organism_annotations/H_sapiens/hg38/"
                "controls/giab/sv/v5.0q/HG002/giabHCv5q/"
                "HG002_GRCh38_v5.0q_stvar.vcf.gz"
            ),
            "truth_tbi": (
                "/fsx/references/genomic_data/organism_annotations/H_sapiens/hg38/"
                "controls/giab/sv/v5.0q/HG002/giabHCv5q/"
                "HG002_GRCh38_v5.0q_stvar.vcf.gz.tbi"
            ),
            "truth_bed": (
                "/fsx/references/genomic_data/organism_annotations/H_sapiens/hg38/"
                "controls/giab/sv/v5.0q/HG002/giabHCv5q/"
                "HG002_GRCh38_v5.0q_stvar.benchmark.bed"
            ),
        }
    },
}

# Literal source names differ from the canonical workbook labels in these
# reviewed cases.  These are explicit translations, not runtime discovery or
# fallback behavior.
ILMN_SAMPLE_OVERRIDES: Mapping[tuple[int, str], str] = {
    (2, "ILMN-CASE1-M-b"): "M-BCN-605",
    (2, "ILMN-CASE1-P-b"): "M-BCN-A613",
    (2, "ILMN-CASE1-F-b"): "M-BCN-A5AE",
    (2, "ILMN-BUCCAL7"): "WRD6-20-26",
    (2, "ILMN-BUCCAL8"): "BLD6-20-26",
    (2, "ILMN-BUCCAL9"): "CLD6-20-26",
    (3, "ILMN-CASE1-M-c"): "M-BCN-605",
    (3, "ILMN-CASE1-P-c"): "M-BCN-A613",
    (3, "ILMN-CASE1-F-c"): "M-BCN-A5AE",
    (3, "ILMN-HG002-c"): "HG002-b",
    (3, "ILMN-HG003-c"): "HG003-b",
    (3, "ILMN-HG004-c"): "HG004-b",
    (4, "ILMN-CASE17-P"): "ILMN-CASE17",
    (4, "ILMN-CASE18-P"): "ILMN-CASE18",
}


def _read_json(path: Path) -> Mapping[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise BjuiceConfigError(f"{path} is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise BjuiceConfigError(f"{path} must contain one JSON object")
    return payload


def _read_tsv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        if not reader.fieldnames:
            raise BjuiceConfigError(f"{path} has no header")
        rows = [{key: str(value or "") for key, value in row.items()} for row in reader]
    return list(reader.fieldnames), rows


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def _iso(value: Any) -> str:
    if value is None:
        return ""
    if hasattr(value, "isoformat"):
        return str(value.isoformat())
    return str(value)


def _normalize_alias(value: Any) -> str:
    text = str(value or "").strip().upper().replace(" ", "")
    for prefix in ("ONT-", "ILMN-"):
        if text.startswith(prefix):
            return text[len(prefix) :]
    return text


def _biological_sample(raw: str) -> str:
    value = str(raw or "").strip()
    value = value.removeprefix("ILMN-")
    if not value:
        raise BjuiceConfigError("workbook mapping row has a blank canonical sample")
    return value


def _metadata_for_sample(
    sample: str, metadata: Mapping[str, Mapping[str, str]]
) -> Mapping[str, str]:
    if sample.upper() in metadata:
        return metadata[sample.upper()]
    if sample.upper().startswith("CASE") and re.search(r"-[PMF]$", sample.upper()):
        candidate = sample[:-2].upper()
        if candidate in metadata:
            return metadata[candidate]
    return {}


def _resolve_ilmn_fastq_sample_id(logical_run: int, alias: str, sample: str) -> str:
    if not alias:
        return ""
    override = ILMN_SAMPLE_OVERRIDES.get((logical_run, alias))
    if override:
        return override
    if logical_run == 4:
        if alias.startswith("ILMN-BUCCAL"):
            value = alias[len("ILMN-") :]
            return re.sub(r"-[abc]$", "", value, flags=re.IGNORECASE)
        return alias
    if alias.startswith("ILMN-"):
        return alias[len("ILMN-") :]
    return alias


def _decoder_score(row: Mapping[str, str], decoder_alias: str) -> int:
    ont_alias = _normalize_alias(row.get("ONT_ALIAS", ""))
    biological = _normalize_alias(row.get("BIOLOGICAL_SAMPLE", ""))
    decoder = _normalize_alias(decoder_alias)
    if decoder == ont_alias:
        return 100
    if decoder == biological:
        return 90
    # Workbook mapping and decoder tabs use different technical-replicate
    # suffixes in a few reviewed rows (for example Run 3 CASE1 `-c` versus
    # decoder `-b`).  Match only after removing one terminal replicate suffix;
    # ambiguity is still rejected by the caller.
    if re.sub(r"-[ABC]$", "", decoder) == re.sub(r"-[ABC]$", "", ont_alias):
        return 85
    if biological.startswith("BUCCAL"):
        if re.sub(r"-[ABC]$", "", ont_alias) == re.sub(r"-[ABC]$", "", decoder):
            return 80
        if decoder == biological:
            return 80
    if (
        biological.startswith("CASE")
        and biological.endswith("-P")
        and (decoder == biological[:-2] or decoder == ont_alias.removesuffix("-P"))
    ):
        return 70
    return 0


def _decoder_entries(extract: Mapping[str, Any]) -> Mapping[int, list[dict[str, Any]]]:
    decoder = extract.get("ranges", {}).get("decoder")
    if not isinstance(decoder, list) or len(decoder) < 36:
        raise BjuiceConfigError("workbook extract is missing ONT Barcode decoder rows")
    columns = {1: (0, 1, 2), 2: (4, 5, 6), 3: (8, 9, 10), 4: (12, 13, 14)}
    result: dict[int, list[dict[str, Any]]] = {}
    for logical_run, (ordinal_col, alias_col, barcode_col) in columns.items():
        entries: list[dict[str, Any]] = []
        # Rows 4-36 are the four 33-entry decoder tables (32 samples plus
        # NTC).  The rows below are a separate helper/decoder block and must
        # never be interpreted as sequencing barcodes.
        for raw in decoder[3:36]:
            alias = str(raw[alias_col] or "").strip()
            barcode_native = str(raw[barcode_col] or "").strip()
            if not alias or alias.upper() == "NTC":
                continue
            try:
                ordinal = int(raw[ordinal_col])
            except (TypeError, ValueError) as exc:
                raise BjuiceConfigError(
                    f"ONT decoder run {logical_run} has invalid ordinal for {alias!r}"
                ) from exc
            barcode_match = re.fullmatch(r"NB(\d{1,2})", barcode_native, re.IGNORECASE)
            if not barcode_match:
                raise BjuiceConfigError(
                    f"ONT decoder run {logical_run} has invalid barcode {barcode_native!r}"
                )
            set_number = ((ordinal - 1) // 4) + 1
            within_set = (ordinal - 1) % 4
            chip = ((set_number - 1) * 3) + (1 if within_set == 0 else 2 if within_set == 1 else 3)
            # The 24-chip plate is three rows of eight positions.  Each Set uses
            # three consecutive positions, so Set 2 is 1D/1E/1F rather than
            # 2A/2B/2C, and Set 3 spans 1G/1H/2A.
            position = f"{((chip - 1) // 8) + 1}{chr(ord('A') + ((chip - 1) % 8))}"
            entries.append(
                {
                    "alias": alias,
                    "ordinal": ordinal,
                    "barcode": f"barcode{int(barcode_match.group(1)):02d}",
                    "set": set_number,
                    "chip": chip,
                    "position": position,
                }
            )
        if len(entries) != 32:
            raise BjuiceConfigError(
                f"ONT decoder run {logical_run} must have 32 non-NTC rows; found {len(entries)}"
            )
        barcodes = [str(entry["barcode"]) for entry in entries]
        if len(barcodes) != len(set(barcodes)):
            raise BjuiceConfigError(f"ONT decoder run {logical_run} has duplicate barcodes")
        result[logical_run] = sorted(entries, key=lambda entry: int(entry["ordinal"]))
    return result


def _unique_decoder_match(
    *,
    unmatched: Mapping[str, dict[str, str]],
    decoder_alias: str,
    logical_run: int,
) -> tuple[str, dict[str, str]]:
    scored = sorted(
        ((_decoder_score(row, decoder_alias), row_id, row) for row_id, row in unmatched.items()),
        reverse=True,
    )
    if not scored or scored[0][0] == 0:
        raise BjuiceConfigError(
            f"ONT decoder run {logical_run} alias {decoder_alias!r} has no mapping row"
        )
    if len(scored) > 1 and scored[0][0] == scored[1][0]:
        raise BjuiceConfigError(
            f"ONT decoder run {logical_run} alias {decoder_alias!r} is ambiguous"
        )
    _score, row_id, row = scored[0]
    return row_id, row


def build_crosswalk_from_artifact_extract(*, extract_json: Path, output_tsv: Path) -> None:
    """Normalize artifact-tool workbook ranges into the reviewed 157-row crosswalk."""

    extract = _read_json(extract_json)
    if extract.get("schema") != WORKBOOK_EXTRACT_SCHEMA:
        raise BjuiceConfigError(f"workbook extract schema must be {WORKBOOK_EXTRACT_SCHEMA}")
    if extract.get("workbook_sha256") != EXPECTED_WORKBOOK_SHA256:
        raise BjuiceConfigError("workbook extract SHA-256 does not match the approved workbook")
    ranges = extract.get("ranges")
    if not isinstance(ranges, Mapping):
        raise BjuiceConfigError("workbook extract ranges must be a mapping")
    mapping = ranges.get("mapping")
    ids = ranges.get("ids")
    if not isinstance(mapping, list) or len(mapping) != 102:
        raise BjuiceConfigError("workbook extract mapping range must contain 102 rows")
    if not isinstance(ids, list) or len(ids) < 2:
        raise BjuiceConfigError("workbook extract is missing Samples-wLSMC-IDs")

    metadata: dict[str, Mapping[str, str]] = {}
    for raw in ids[1:]:
        sample = str(raw[0] or "").strip()
        if not sample:
            continue
        metadata[sample.upper()] = {
            "internal_id": str(raw[1] or "").strip(),
            "material_class": str(raw[2] or "").strip(),
            "analysis_role": str(raw[3] or "").strip(),
            "variant_feature": str(raw[4] or "").strip(),
        }

    rows: list[dict[str, str]] = []
    ilmn_cols = {1: 1, 2: 2, 3: 3, 4: 4}
    ont_cols = {1: 5, 2: 6, 3: 7, 4: 8}
    for workbook_row, raw in enumerate(mapping[3:], start=4):
        canonical_raw = str(raw[0] or "").strip()
        biological = _biological_sample(canonical_raw)
        sample_metadata = _metadata_for_sample(biological, metadata)
        for logical_run in range(1, 5):
            ilmn_alias = str(raw[ilmn_cols[logical_run]] or "").strip()
            ont_alias = str(raw[ont_cols[logical_run]] or "").strip()
            if not ilmn_alias and not ont_alias:
                continue
            pairing_status = (
                "PAIRED" if ilmn_alias and ont_alias else "ILMN_ONLY" if ilmn_alias else "ONT_ONLY"
            )
            blocker = (
                ""
                if pairing_status == "PAIRED"
                else "MISSING_ONT_ALIAS"
                if pairing_status == "ILMN_ONLY"
                else "MISSING_ILMN_ALIAS"
            )
            row_id = f"R{logical_run}-WB{workbook_row:03d}"
            rows.append(
                {
                    "CROSSWALK_ROW_ID": row_id,
                    "WORKBOOK_ROW": str(workbook_row),
                    "LOGICAL_RUN": str(logical_run),
                    "CANONICAL_SAMPLE_RAW": canonical_raw,
                    "BIOLOGICAL_SAMPLE": biological,
                    "ILMN_ALIAS": ilmn_alias,
                    "ILMN_FASTQ_SAMPLE_ID": _resolve_ilmn_fastq_sample_id(
                        logical_run, ilmn_alias, biological
                    ),
                    "ONT_ALIAS": ont_alias,
                    "SOURCE_INTERNAL_ID": str(sample_metadata.get("internal_id") or ""),
                    "MAPPING_INTERNAL_ID": str(raw[9] or "").strip(),
                    "MAPPING_POOL_ID": str(raw[10] or "").strip(),
                    "MATERIAL_CLASS": str(sample_metadata.get("material_class") or ""),
                    "ANALYSIS_ROLE": str(sample_metadata.get("analysis_role") or ""),
                    "VARIANT_FEATURE": str(sample_metadata.get("variant_feature") or ""),
                    "PAIRING_STATUS": pairing_status,
                    "BLOCKER": blocker,
                    "REVIEW_STATUS": "REVIEWED",
                    "SOURCE_NOTES": "Workbook mapping plus ONT decoder/plate topology",
                }
            )

    decoders = _decoder_entries(extract)
    for logical_run in range(1, 5):
        ont_rows = [
            row for row in rows if row["LOGICAL_RUN"] == str(logical_run) and row["ONT_ALIAS"]
        ]
        unmatched = {row["CROSSWALK_ROW_ID"]: row for row in ont_rows}
        for entry in decoders[logical_run]:
            row_id, row = _unique_decoder_match(
                unmatched=unmatched,
                decoder_alias=str(entry["alias"]),
                logical_run=logical_run,
            )
            unmatched.pop(row_id)
            row.update(
                {
                    "ONT_DECODER_ALIAS": str(entry["alias"]),
                    "ONT_DECODER_ORDINAL": str(entry["ordinal"]),
                    "ONT_SET": str(entry["set"]),
                    "ONT_CHIP": str(entry["chip"]),
                    "ONT_POSITION": str(entry["position"]),
                    "ONT_BARCODE": str(entry["barcode"]),
                }
            )
        if unmatched:
            raise BjuiceConfigError(
                f"logical run {logical_run} has unmatched ONT rows: {sorted(unmatched)}"
            )

    validate_crosswalk_rows(rows)
    _write_tsv(output_tsv, CROSSWALK_COLUMNS, rows)


def validate_crosswalk_rows(rows: Sequence[Mapping[str, str]]) -> None:
    if len(rows) != sum(EXPECTED_MAPPED_ROWS.values()):
        raise BjuiceConfigError(f"crosswalk must contain exactly 157 rows; found {len(rows)}")
    row_ids = [str(row.get("CROSSWALK_ROW_ID") or "") for row in rows]
    if len(row_ids) != len(set(row_ids)) or any(not row_id for row_id in row_ids):
        raise BjuiceConfigError("crosswalk row IDs must be nonblank and unique")
    mapped_counts = Counter(int(row["LOGICAL_RUN"]) for row in rows)
    paired_counts = Counter(
        int(row["LOGICAL_RUN"]) for row in rows if row.get("PAIRING_STATUS") == "PAIRED"
    )
    ont_counts = Counter(int(row["LOGICAL_RUN"]) for row in rows if row.get("ONT_ALIAS"))
    if dict(mapped_counts) != EXPECTED_MAPPED_ROWS:
        raise BjuiceConfigError(f"unexpected mapped row totals: {dict(mapped_counts)}")
    if dict(paired_counts) != EXPECTED_PAIRED_ROWS:
        raise BjuiceConfigError(f"unexpected paired row totals: {dict(paired_counts)}")
    if dict(ont_counts) != EXPECTED_ONT_ROWS:
        raise BjuiceConfigError(f"unexpected ONT row totals: {dict(ont_counts)}")
    for row in rows:
        status = row.get("PAIRING_STATUS")
        if status not in {"PAIRED", "ILMN_ONLY", "ONT_ONLY"}:
            raise BjuiceConfigError(f"invalid pairing status in {row.get('CROSSWALK_ROW_ID')}")
        if row.get("REVIEW_STATUS") != "REVIEWED":
            raise BjuiceConfigError(f"crosswalk row is not reviewed: {row.get('CROSSWALK_ROW_ID')}")
        if str(row.get("BIOLOGICAL_SAMPLE") or "").upper() == "NTC":
            raise BjuiceConfigError("NTC must not appear in the crosswalk")
        if row.get("ILMN_ALIAS") and not row.get("ILMN_FASTQ_SAMPLE_ID"):
            raise BjuiceConfigError(
                f"{row.get('CROSSWALK_ROW_ID')} has no explicit ILMN FASTQ sample ID"
            )
        if row.get("ONT_ALIAS"):
            required = (
                "ONT_DECODER_ALIAS",
                "ONT_DECODER_ORDINAL",
                "ONT_SET",
                "ONT_CHIP",
                "ONT_POSITION",
                "ONT_BARCODE",
            )
            missing = [field for field in required if not row.get(field)]
            if missing:
                raise BjuiceConfigError(
                    f"{row.get('CROSSWALK_ROW_ID')} is missing ONT fields: {missing}"
                )
    for logical_run in range(1, 5):
        barcodes = [
            row["ONT_BARCODE"]
            for row in rows
            if row["LOGICAL_RUN"] == str(logical_run) and row.get("ONT_ALIAS")
        ]
        if len(barcodes) != len(set(barcodes)):
            raise BjuiceConfigError(f"logical run {logical_run} has duplicate ONT barcodes")


def load_crosswalk(path: Path) -> list[dict[str, str]]:
    columns, rows = _read_tsv(path)
    if tuple(columns) != CROSSWALK_COLUMNS:
        raise BjuiceConfigError(
            f"crosswalk header must exactly match the reviewed contract: {CROSSWALK_COLUMNS}"
        )
    validate_crosswalk_rows(rows)
    return rows


def _parse_s3_uri(uri: str) -> tuple[str, str]:
    parsed = urlparse(uri)
    if parsed.scheme != "s3" or not parsed.netloc or not parsed.path:
        raise BjuiceConfigError(f"expected an s3:// URI, found {uri!r}")
    return parsed.netloc, parsed.path.lstrip("/")


def _source_spec(path: Path) -> Mapping[str, Any]:
    spec = _read_json(path)
    if spec.get("schema") != SOURCE_SPEC_SCHEMA:
        raise BjuiceConfigError(f"source spec schema must be {SOURCE_SPEC_SCHEMA}")
    workbook = spec.get("workbook")
    if not isinstance(workbook, Mapping) or workbook.get("sha256") != EXPECTED_WORKBOOK_SHA256:
        raise BjuiceConfigError("source spec does not identify the approved workbook SHA-256")
    dyec = spec.get("dyec")
    if not isinstance(dyec, Mapping) or any(
        dyec.get(key) != value for key, value in DYEC_BASELINE.items()
    ):
        raise BjuiceConfigError("source spec does not identify the fixed DYEC 18.0.43 baseline")
    dayoa = spec.get("dayoa")
    if not isinstance(dayoa, Mapping) or any(
        dayoa.get(key) != value for key, value in DAYOA_BASELINE.items()
    ):
        raise BjuiceConfigError("source spec does not identify the DayOA 15.0.24 pin")
    sources = spec.get("sources")
    bundles = spec.get("bundles")
    if not isinstance(sources, list) or len(sources) != EXPECTED_SOURCE_COUNT:
        raise BjuiceConfigError(f"source spec must contain exactly {EXPECTED_SOURCE_COUNT} sources")
    if not isinstance(bundles, list) or len(bundles) != 5:
        raise BjuiceConfigError("source spec must contain exactly five bundles")
    source_ids = [str(source.get("source_id") or "") for source in sources]
    source_uris = [str(source.get("s3_uri") or "") for source in sources]
    if any(not value for value in source_ids) or len(source_ids) != len(set(source_ids)):
        raise BjuiceConfigError("source IDs must be nonblank and unique")
    if len(source_uris) != len(set(source_uris)):
        raise BjuiceConfigError("source S3 URIs must be unique")
    known_ids = set(source_ids)
    seen_bundles: set[str] = set()
    for bundle in bundles:
        bundle_id = str(bundle.get("bundle_id") or "")
        if not bundle_id or bundle_id in seen_bundles:
            raise BjuiceConfigError("bundle IDs must be nonblank and unique")
        seen_bundles.add(bundle_id)
        logical_run = int(bundle.get("logical_run") or 0)
        if int(bundle.get("expected_paired_aus") or -1) != EXPECTED_PAIRED_ROWS[logical_run]:
            raise BjuiceConfigError(f"{bundle_id} has an unexpected paired-AU total")
        references = [str(bundle.get("ilmn_source_id") or "")]
        references.extend(str(value) for value in bundle.get("ont_source_ids", []))
        if len(references) != 9 or not set(references) <= known_ids:
            raise BjuiceConfigError(f"{bundle_id} must reference one ILMN and eight ONT sources")
    expected_bucket = str(spec.get("aws", {}).get("bucket") or "")
    for source in sources:
        platform = str(source.get("platform") or "")
        if platform not in {"ILMN", "ONT"}:
            raise BjuiceConfigError(f"invalid platform for {source.get('source_id')}")
        uri = str(source.get("s3_uri") or "")
        bucket, prefix = _parse_s3_uri(uri)
        if bucket != expected_bucket or not uri.endswith("/") or not prefix.endswith("/"):
            raise BjuiceConfigError(f"noncanonical source URI: {uri}")
        if not prefix.startswith("basecalls/lsmc/ssf-hq/"):
            raise BjuiceConfigError(f"source is outside the approved canonical root: {uri}")
        lowered = uri.lower()
        if "preval" in lowered or "-migration-cleanup" in lowered or "/." in lowered:
            raise BjuiceConfigError(f"prohibited source URI: {uri}")
        mount_uri = str(source.get("mount_s3_uri") or "")
        mount_path = str(source.get("mount_path") or "")
        mount_bucket, mount_prefix = _parse_s3_uri(mount_uri)
        if mount_bucket != bucket or not prefix.startswith(mount_prefix):
            raise BjuiceConfigError(f"invalid mount projection for {source.get('source_id')}")
        if not mount_path.startswith("/fsx/run_dir_mounts/"):
            raise BjuiceConfigError(f"invalid mount path for {source.get('source_id')}")
    return spec


def _list_s3_object_records(*, s3_client: Any, bucket: str, prefix: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    paginator = s3_client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for item in page.get("Contents", []):
            key = str(item.get("Key") or "")
            if not key:
                continue
            records.append(
                {
                    "key": key,
                    "size": int(item.get("Size") or 0),
                    "last_modified": _iso(item.get("LastModified")),
                    "etag": str(item.get("ETag") or "").strip('"'),
                }
            )
    return sorted(records, key=lambda item: item["key"])


def _excluded_object_reason(key: str) -> str:
    lowered = key.lower()
    parts = PurePosixPath(key).parts
    if any(part.startswith(".") for part in parts):
        return "hidden_dot_prefix"
    if any(part.endswith("-migration-cleanup") for part in parts):
        return "migration_cleanup"
    if "bjuice-preval" in lowered or "bjuice_preval" in lowered:
        return "bjuice_preval"
    if "/fastq_fail/" in lowered:
        return "ont_fastq_fail"
    if "/unclassified/" in lowered:
        return "ont_unclassified"
    if "/qc/" in lowered or "/ont_qc/" in lowered or "/ont-qc/" in lowered:
        return "ont_qc"
    return ""


def _parse_final_summary(body: bytes, *, key: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in body.decode("utf-8").splitlines():
        if "=" not in raw_line:
            continue
        name, value = raw_line.split("=", 1)
        values[name.strip()] = value.strip()
    required = ("position", "flow_cell_id", "protocol_run_id", "acquisition_run_id")
    missing = [name for name in required if not values.get(name)]
    if missing:
        raise BjuiceConfigError(f"{key} is missing final-summary fields: {missing}")
    values["protocol_short"] = values["protocol_run_id"].split("-", 1)[0]
    values["acquisition_short"] = values["acquisition_run_id"][:8]
    values["key"] = key
    return values


def _inventory_one_source(*, s3_client: Any, source: Mapping[str, Any]) -> dict[str, Any]:
    uri = str(source["s3_uri"])
    bucket, prefix = _parse_s3_uri(uri)
    records = _list_s3_object_records(s3_client=s3_client, bucket=bucket, prefix=prefix)
    if not records:
        raise BjuiceConfigError(f"source prefix is empty: {uri}")
    excluded = Counter(
        reason for item in records if (reason := _excluded_object_reason(item["key"]))
    )
    keys = {item["key"] for item in records}
    platform = str(source["platform"])
    marker: dict[str, Any]
    summaries: dict[str, dict[str, str]] = {}
    if platform == "ILMN":
        copy_complete = prefix + "CopyComplete.txt"
        marker = {
            "copy_complete_key": copy_complete,
            "copy_complete": copy_complete in keys,
        }
        if not marker["copy_complete"]:
            raise BjuiceConfigError(f"ILMN source lacks CopyComplete.txt: {uri}")
    else:
        final_summary_keys = [
            key for key in keys if PurePosixPath(key).name.startswith("final_summary_")
        ]
        output_hash_keys = [
            key for key in keys if PurePosixPath(key).name.startswith("output_hash_")
        ]
        report_keys = [
            key
            for key in keys
            if PurePosixPath(key).name.startswith("report_") and key.endswith(".json")
        ]
        if not (len(final_summary_keys) == len(output_hash_keys) == len(report_keys) == 3):
            raise BjuiceConfigError(
                f"ONT source must have three final_summary/output_hash/report markers: {uri}"
            )
        for key in sorted(final_summary_keys):
            response = s3_client.get_object(Bucket=bucket, Key=key)
            parsed = _parse_final_summary(response["Body"].read(), key=key)
            position = parsed["position"]
            if position in summaries:
                raise BjuiceConfigError(f"duplicate ONT position {position} under {uri}")
            summaries[position] = parsed
        first_chip = ((int(source["set_number"]) - 1) * 3) + 1
        expected_positions = {
            f"{((chip - 1) // 8) + 1}{chr(ord('A') + ((chip - 1) % 8))}"
            for chip in range(first_chip, first_chip + 3)
        }
        if set(summaries) != expected_positions:
            raise BjuiceConfigError(
                f"ONT source positions {sorted(summaries)} do not match {sorted(expected_positions)}"
            )
        marker = {
            "final_summary_keys": sorted(final_summary_keys),
            "output_hash_keys": sorted(output_hash_keys),
            "report_keys": sorted(report_keys),
            "ready": True,
        }
    latest = max((item["last_modified"] for item in records), default="")
    return {
        **{key: value for key, value in source.items()},
        "object_count": len(records),
        "total_bytes": sum(int(item["size"]) for item in records),
        "latest_object_timestamp": latest,
        "oow_done": prefix + "OOW.done" in keys,
        "oow_err": prefix + "OOW.err" in keys,
        "readiness": marker,
        "excluded_object_counts": dict(sorted(excluded.items())),
        "flowcells_by_position": summaries,
        "_objects": records,
    }


def _project_mount_path(*, source: Mapping[str, Any], key: str) -> str:
    bucket, _source_prefix = _parse_s3_uri(str(source["s3_uri"]))
    mount_bucket, mount_prefix = _parse_s3_uri(str(source["mount_s3_uri"]))
    if bucket != mount_bucket or not key.startswith(mount_prefix):
        raise BjuiceConfigError(
            f"object cannot be projected through source mount: s3://{bucket}/{key}"
        )
    relative = key[len(mount_prefix) :]
    return str(PurePosixPath(str(source["mount_path"])) / relative)


def _ilmn_selection(*, source: Mapping[str, Any], row: Mapping[str, str]) -> dict[str, Any]:
    sample_id = str(row["ILMN_FASTQ_SAMPLE_ID"])
    by_mate: dict[str, dict[str, Mapping[str, Any]]] = {"1": {}, "2": {}}
    for item in source["_objects"]:
        key = str(item["key"])
        if _excluded_object_reason(key):
            continue
        match = ILMN_FASTQ_RE.fullmatch(PurePosixPath(key).name)
        if not match or match.group("sample") != sample_id:
            continue
        lane = match.group("lane")
        mate = match.group("mate")
        if lane in by_mate[mate]:
            raise BjuiceConfigError(
                f"{source['source_id']} {sample_id} repeats lane {lane} mate R{mate}"
            )
        if int(item["size"]) <= 0:
            raise BjuiceConfigError(
                f"{source['source_id']} {sample_id} lane {lane} R{mate} is empty"
            )
        by_mate[mate][lane] = item
    r1_lanes = set(by_mate["1"])
    r2_lanes = set(by_mate["2"])
    if not r1_lanes or r1_lanes != r2_lanes:
        raise BjuiceConfigError(
            f"{source['source_id']} {sample_id} has unequal or missing R1/R2 lanes: "
            f"R1={sorted(r1_lanes)} R2={sorted(r2_lanes)}"
        )

    def details(mate: str) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for lane in sorted(by_mate[mate]):
            item = by_mate[mate][lane]
            result.append(
                {
                    "lane": lane,
                    "s3_uri": f"s3://{_parse_s3_uri(str(source['s3_uri']))[0]}/{item['key']}",
                    "mount_path": _project_mount_path(source=source, key=str(item["key"])),
                    "size": int(item["size"]),
                    "last_modified": item["last_modified"],
                }
            )
        return result

    return {
        "source_id": source["source_id"],
        "run_id": source["run_id"],
        "sample_id": sample_id,
        "lanes": sorted(r1_lanes),
        "r1": details("1"),
        "r2": details("2"),
    }


def _ont_selection(*, source: Mapping[str, Any], row: Mapping[str, str]) -> dict[str, Any]:
    position = str(row["ONT_POSITION"])
    barcode = str(row["ONT_BARCODE"])
    summary = source["flowcells_by_position"].get(position)
    if not summary:
        raise BjuiceConfigError(f"{source['source_id']} lacks ONT position {position}")
    _bucket, prefix = _parse_s3_uri(str(source["s3_uri"]))
    barcode_prefix = f"{prefix}no_sample_id/fastq_pass/{barcode}/"
    selected: list[dict[str, Any]] = []
    for item in source["_objects"]:
        key = str(item["key"])
        if not key.startswith(barcode_prefix) or _excluded_object_reason(key):
            continue
        match = ONT_FASTQ_RE.fullmatch(PurePosixPath(key).name)
        if not match:
            raise BjuiceConfigError(f"unexpected ONT FASTQ name under {barcode_prefix}: {key}")
        if (
            match.group("flowcell") != summary["flow_cell_id"]
            or match.group("barcode") != barcode
            or match.group("protocol") != summary["protocol_short"]
            or match.group("acquisition") != summary["acquisition_short"]
        ):
            continue
        if int(item["size"]) <= 0:
            raise BjuiceConfigError(f"selected ONT FASTQ is empty: {key}")
        selected.append(
            {
                "hour": int(match.group("hour")),
                "s3_uri": f"s3://{_parse_s3_uri(str(source['s3_uri']))[0]}/{key}",
                "mount_path": _project_mount_path(source=source, key=key),
                "size": int(item["size"]),
                "last_modified": item["last_modified"],
            }
        )
    selected.sort(key=lambda item: (int(item["hour"]), item["s3_uri"]))
    if not selected:
        raise BjuiceConfigError(
            f"{source['source_id']} {position} {barcode} has no exact flowcell FASTQs"
        )
    window = [item for item in selected if ONT_START_HOUR <= int(item["hour"]) < ONT_END_HOUR]
    if not window:
        raise BjuiceConfigError(
            f"{source['source_id']} {position} {barcode} has no FASTQs in [0,24)"
        )
    return {
        "source_id": source["source_id"],
        "run_id": source["run_id"],
        "set_number": int(source["set_number"]),
        "position": position,
        "barcode": barcode,
        "flowcell_id": summary["flow_cell_id"],
        "protocol_short": summary["protocol_short"],
        "acquisition_short": summary["acquisition_short"],
        "fastqs": selected,
        "window_fastq_count": len(window),
        "window_total_bytes": sum(int(item["size"]) for item in window),
        "window_hours_present": sorted({int(item["hour"]) for item in window}),
    }


def build_source_inventory(
    *,
    source_spec_json: Path,
    crosswalk_tsv: Path,
    output_json: Path,
    profile: str,
    region: str,
    workers: int = 8,
) -> Mapping[str, Any]:
    """Inventory the explicit canonical run roots and resolve exact paired inputs."""

    spec = _source_spec(source_spec_json)
    rows = load_crosswalk(crosswalk_tsv)
    expected_profile = str(spec.get("aws", {}).get("profile") or "")
    expected_region = str(spec.get("aws", {}).get("region") or "")
    if profile != expected_profile or region != expected_region:
        raise BjuiceConfigError(
            f"inventory requires reviewed AWS context {expected_profile}/{expected_region}"
        )
    session = boto3.Session(profile_name=profile, region_name=region)
    s3_client = session.client("s3")
    identity = session.client("sts").get_caller_identity()
    source_results: dict[str, dict[str, Any]] = {}
    max_workers = max(1, min(int(workers), EXPECTED_SOURCE_COUNT))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        pending = {
            executor.submit(_inventory_one_source, s3_client=s3_client, source=source): source
            for source in spec["sources"]
        }
        for future in as_completed(pending):
            source = pending[future]
            source_results[str(source["source_id"])] = future.result()
    if len(source_results) != EXPECTED_SOURCE_COUNT:
        raise BjuiceConfigError("source inventory did not return all 37 source roots")

    ilmns_by_run: dict[int, list[Mapping[str, Any]]] = defaultdict(list)
    for source in source_results.values():
        if source["platform"] == "ILMN":
            ilmns_by_run[int(source["logical_run"])].append(source)
    selections: dict[str, dict[str, Any]] = {}
    for row in rows:
        logical_run = int(row["LOGICAL_RUN"])
        row_selection: dict[str, Any] = {
            "logical_run": logical_run,
            "pairing_status": row["PAIRING_STATUS"],
            "biological_sample": row["BIOLOGICAL_SAMPLE"],
            "ilmn": {},
            "ont": None,
        }
        if row.get("ILMN_ALIAS"):
            candidates = sorted(ilmns_by_run[logical_run], key=lambda item: item["source_id"])
            if len(candidates) != (2 if logical_run == 1 else 1):
                raise BjuiceConfigError(f"logical run {logical_run} has wrong ILMN source count")
            for source in candidates:
                row_selection["ilmn"][source["source_id"]] = _ilmn_selection(source=source, row=row)
        if row.get("ONT_ALIAS"):
            source_id = f"ont-run{logical_run}-set{row['ONT_SET']}"
            source = source_results.get(source_id)
            if not source:
                raise BjuiceConfigError(f"crosswalk references missing source {source_id}")
            row_selection["ont"] = _ont_selection(source=source, row=row)
        selections[row["CROSSWALK_ROW_ID"]] = row_selection

    selected_keys_by_source: dict[str, set[str]] = defaultdict(set)
    for selection in selections.values():
        for ilmn in selection["ilmn"].values():
            for mate in ("r1", "r2"):
                for item in ilmn[mate]:
                    _bucket, key = _parse_s3_uri(str(item["s3_uri"]))
                    selected_keys_by_source[str(ilmn["source_id"])].add(key)
        ont = selection.get("ont")
        if ont:
            for item in ont["fastqs"]:
                _bucket, key = _parse_s3_uri(str(item["s3_uri"]))
                selected_keys_by_source[str(ont["source_id"])].add(key)
    for source_id, source in source_results.items():
        all_fastqs: list[str] = []
        sample_ids: set[str] = set()
        for item in source["_objects"]:
            key = str(item["key"])
            if not key.endswith(".fastq.gz"):
                continue
            if source["platform"] == "ILMN":
                match = ILMN_FASTQ_RE.fullmatch(PurePosixPath(key).name)
                if not match:
                    continue
                sample_ids.add(match.group("sample"))
            elif "/no_sample_id/fastq_pass/barcode" not in key:
                continue
            all_fastqs.append(key)
        selected_keys = selected_keys_by_source[source_id]
        selection_summary: dict[str, Any] = {
            "candidate_fastq_count": len(all_fastqs),
            "selected_fastq_count": len(selected_keys),
            "unselected_fastq_count": len(set(all_fastqs) - selected_keys),
        }
        if source["platform"] == "ILMN":
            selected_samples = {
                str(selection["sample_id"])
                for row_selection in selections.values()
                for selection in row_selection["ilmn"].values()
                if selection["source_id"] == source_id
            }
            selection_summary["selected_sample_ids"] = sorted(selected_samples)
            selection_summary["unselected_sample_ids"] = sorted(sample_ids - selected_samples)
        else:
            selection_summary["unselected_reason"] = (
                "FASTQ does not match the workbook-decoded position, final-summary "
                "flowcell, and barcode tuple; NTC and cross-flowcell barcode copies stay excluded"
            )
        source["fastq_selection_summary"] = selection_summary

    public_sources: dict[str, dict[str, Any]] = {}
    for source_id, source in sorted(source_results.items()):
        public_sources[source_id] = {
            key: value for key, value in source.items() if key != "_objects"
        }
    inventory: dict[str, Any] = {
        "schema": SOURCE_INVENTORY_SCHEMA,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "source_spec": str(source_spec_json),
        "source_spec_sha256": _sha256(source_spec_json),
        "crosswalk": str(crosswalk_tsv),
        "crosswalk_sha256": _sha256(crosswalk_tsv),
        "aws": {
            "profile": profile,
            "region": region,
            "account": str(identity.get("Account") or ""),
            "arn": str(identity.get("Arn") or ""),
            "user_id": str(identity.get("UserId") or ""),
        },
        "sources": public_sources,
        "selections": selections,
        "summary": {
            "source_count": len(public_sources),
            "total_objects": sum(int(source["object_count"]) for source in public_sources.values()),
            "total_bytes": sum(int(source["total_bytes"]) for source in public_sources.values()),
            "oow_done_sources": sorted(
                source_id for source_id, source in public_sources.items() if source["oow_done"]
            ),
            "oow_missing_sources": sorted(
                source_id for source_id, source in public_sources.items() if not source["oow_done"]
            ),
            "mapped_rows": len(rows),
            "paired_rows": sum(row["PAIRING_STATUS"] == "PAIRED" for row in rows),
        },
    }
    _atomic_json(output_json, inventory)
    return inventory


def _safe_local_id(value: str, *, field_name: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9-]+", "-", str(value).strip()).strip("-")
    normalized = re.sub(r"-+", "-", normalized)
    if not SAFE_LOCAL_ID_RE.fullmatch(normalized):
        raise BjuiceConfigError(f"{field_name} cannot form a safe local ID: {value!r}")
    return normalized


def _runtime_config(*, bundle_id: str, sample_ids: Sequence[str]) -> dict[str, Any]:
    truthsets: dict[str, Any] = {}
    if "HG002" in sample_ids:
        truthsets["HG002"] = HG002_SV_TRUTHSET
    return {
        "ont_fastq_hour_window_mode": "per_analysis_unit",
        "sentdhiomr2": {
            "hg38_sentdhiomr2_chrms": "1-25",
            "lr_input_mode_by_sample": {sample_id: "fastq" for sample_id in sample_ids},
            "provenance_run_id": f"bjuice_validation_{bundle_id}",
            "retain_stage_artifacts": True,
        },
        "multiqc_qc": {
            "enable_tools": ["unmapped_metagenomics_ganon2"],
            "library_summary": {
                "primary_alignments": {
                    "sr": {"aligner": "sentdhiomr2sr", "deduper": "smd"},
                    "ont": {"aligner": "sentdhiomr2lr", "deduper": "na"},
                },
                "contamination_method": "site_mix",
            },
        },
        "sentdhiomr2_nicu_research": {
            "enabled": False,
            "fastq_recoverability_enabled": False,
        },
        "sentdhiomr2_slim_consensus": {"enabled": True},
        "sentdhiomr2_jasmine": {"enabled": False},
        "truvari_sv_benchmark": {
            "enabled": True,
            "env_yaml": "../envs/truari_v0.2.yaml",
            "threads": 32,
            "mem_mb": 64000,
            "partition": "i128nvme,i192nvme,i192hugenvme,i384nvme",
            "extra_args": (
                "--passonly --sizemin 50 --sizefilt 50 --sizemax -1 "
                "--refdist 500 --pctsize 0.7 --pctseq 0.7 --pctovl 0 --pick single"
            ),
            "truthsets": truthsets,
        },
    }


def _sample_source(sample_id: str, rows: Sequence[Mapping[str, str]]) -> str:
    if sample_id in GIAB_SEX or sample_id.startswith(("NA", "CASE")):
        return "blood"
    if sample_id.startswith("BUCCAL"):
        return "buccal"
    materials = {str(row.get("MATERIAL_CLASS") or "").strip().lower() for row in rows}
    materials.discard("")
    if len(materials) == 1:
        return next(iter(materials))
    return "unknown"


def _manifest_rows_for_bundle(
    *,
    bundle: Mapping[str, Any],
    crosswalk_rows: Sequence[Mapping[str, str]],
    inventory: Mapping[str, Any],
) -> tuple[dict[str, list[dict[str, str]]], list[dict[str, Any]]]:
    bundle_id = str(bundle["bundle_id"])
    logical_run = int(bundle["logical_run"])
    ilmn_source_id = str(bundle["ilmn_source_id"])
    paired = [
        row
        for row in crosswalk_rows
        if int(row["LOGICAL_RUN"]) == logical_run and row["PAIRING_STATUS"] == "PAIRED"
    ]
    if len(paired) != int(bundle["expected_paired_aus"]):
        raise BjuiceConfigError(f"{bundle_id} paired crosswalk count does not match its contract")
    selections = inventory.get("selections")
    if not isinstance(selections, Mapping):
        raise BjuiceConfigError("source inventory has no selections mapping")

    rows_by_sample: dict[str, list[Mapping[str, str]]] = defaultdict(list)
    for row in paired:
        rows_by_sample[row["BIOLOGICAL_SAMPLE"]].append(row)
    sample_ids = sorted(rows_by_sample)
    specimens: list[dict[str, str]] = []
    samples: list[dict[str, str]] = []
    libraries: list[dict[str, str]] = []
    sequencing_inputs: list[dict[str, str]] = []
    analysis_units: list[dict[str, str]] = []
    links: list[dict[str, str]] = []
    receipt_units: list[dict[str, Any]] = []

    for sample_id in sample_ids:
        sample_source = _sample_source(sample_id, rows_by_sample[sample_id])
        sex, n_x, n_y = GIAB_SEX.get(sample_id, ("", "", ""))
        specimens.append(
            {
                "SPECIMEN_ID": sample_id,
                "SPECIMEN_EUID": "",
                "SAMPLESOURCE": sample_source,
                "SPECIMEN_TYPE": sample_source,
                "EXTERNAL_SPECIMEN_ID": sample_id,
                "BIOLOGICAL_SEX": sex,
                "N_X": n_x,
                "N_Y": n_y,
                "SPECIMEN_COMMENT": (
                    "GIAB benchmark specimen"
                    if sample_id in GIAB_SEX
                    else "Canonical biological specimen from reviewed Bjuice validation workbook"
                ),
            }
        )
        truth_dir = f"{GIAB_SNV_TRUTH_ROOT}/{sample_id}/" if sample_id in GIAB_SEX else ""
        samples.append(
            {
                "SAMPLEID": sample_id,
                "SAMPLE_EUID": "",
                "SPECIMEN_ID": sample_id,
                "SAMPLECLASS": "research",
                "SAMPLE_TYPE": sample_source,
                "SAMPLEUSE": "posControl" if sample_id in GIAB_SEX else "research",
                "ORDER_TYPE": "positive control" if sample_id in GIAB_SEX else "research",
                "CONCORDANCE_CONTROL_PATH": truth_dir,
                "IS_POSITIVE_CONTROL": "true" if sample_id in GIAB_SEX else "false",
                "IS_NEGATIVE_CONTROL": "false",
                "TUM_NRM_SAMPLEID_MATCH": "na",
                "EXTERNAL_SAMPLE_ID": sample_id,
                "IDDNA_UID": "",
                "TRUTH_DATA_DIR": truth_dir,
                "SAMPLE_COMMENT": (
                    "GIAB benchmark positive control"
                    if sample_id in GIAB_SEX
                    else "Bjuice validation workbook sample; no sample-specific truth source verified"
                ),
            }
        )

    for row in paired:
        row_id = str(row["CROSSWALK_ROW_ID"])
        sample_id = str(row["BIOLOGICAL_SAMPLE"])
        selection = selections.get(row_id)
        if not isinstance(selection, Mapping) or selection.get("pairing_status") != "PAIRED":
            raise BjuiceConfigError(f"inventory lacks paired selection for {row_id}")
        ilmn_by_source = selection.get("ilmn")
        if not isinstance(ilmn_by_source, Mapping) or ilmn_source_id not in ilmn_by_source:
            raise BjuiceConfigError(f"{row_id} lacks ILMN source {ilmn_source_id}")
        ilmn = ilmn_by_source[ilmn_source_id]
        ont = selection.get("ont")
        if not isinstance(ont, Mapping) or ont.get("source_id") not in bundle["ont_source_ids"]:
            raise BjuiceConfigError(f"{row_id} lacks its bundle-qualified ONT source")
        id_stem = _safe_local_id(f"{bundle_id}-{row_id}", field_name="bundle row ID")
        au_uid = f"AU-{id_stem}-HIOMRS"
        ilmn_library = f"LIB-{id_stem}-ILMN"
        ont_library = f"LIB-{id_stem}-ONT"
        ilmn_input = f"INPUT-{id_stem}-ILMN"
        ont_input = f"INPUT-{id_stem}-ONT"
        libraries.extend(
            [
                {
                    "LIBRARY_ID": ilmn_library,
                    "LIBRARY_EUID": "",
                    "SAMPLEID": sample_id,
                    "LIBPREP": "UNKNOWN",
                    "AMPLIFICATION_TYPE": "WGS",
                    "LIBRARY_COMMENT": (
                        f"Distinct {bundle_id} technical library; workbook row {row['WORKBOOK_ROW']}; "
                        f"ILMN alias {row['ILMN_ALIAS']}"
                    ),
                },
                {
                    "LIBRARY_ID": ont_library,
                    "LIBRARY_EUID": "",
                    "SAMPLEID": sample_id,
                    "LIBPREP": "UNKNOWN",
                    "AMPLIFICATION_TYPE": "WGS",
                    "LIBRARY_COMMENT": (
                        f"Distinct {bundle_id} technical library; workbook row {row['WORKBOOK_ROW']}; "
                        f"ONT alias {row['ONT_ALIAS']}"
                    ),
                },
            ]
        )
        r1_paths = [str(item["mount_path"]) for item in ilmn["r1"]]
        r2_paths = [str(item["mount_path"]) for item in ilmn["r2"]]
        ont_paths = [str(item["mount_path"]) for item in ont["fastqs"]]
        ilmn_run_label = _dayoa_read_group_label(str(ilmn["run_id"]), field_name="ILMN run")
        ont_run_label = _dayoa_read_group_label(str(ont["run_id"]), field_name="ONT run")
        sequencing_inputs.extend(
            [
                {
                    "SEQUENCING_INPUT_UID": ilmn_input,
                    "POOL_TUBE_EUID": "",
                    "SEQUENCING_RUN_EUID": "",
                    "SOURCE_ARTIFACT_EUID": "",
                    "LIBRARY_ID": ilmn_library,
                    "MODALITY": "sr",
                    "LAYOUT": "paired_fastq",
                    "RUNID": ilmn_run_label,
                    "EXPERIMENTID": _safe_local_id(bundle_id, field_name="bundle ID"),
                    "LANEID": ",".join(f"L{lane}" for lane in ilmn["lanes"]),
                    "BARCODEID": str(ilmn["sample_id"]),
                    "SEQ_PLATFORM": "NOVASEQXPLUS",
                    "SEQ_VENDOR": "ILMN",
                    "ILMN_R1_PATH": ",".join(r1_paths),
                    "ILMN_R2_PATH": ",".join(r2_paths),
                    "SEQUENCING_INPUT_COMMENT": (
                        f"Full-coverage ILMN FASTQs from {ilmn['source_id']}; raw run {ilmn['run_id']}"
                    ),
                },
                {
                    "SEQUENCING_INPUT_UID": ont_input,
                    "POOL_TUBE_EUID": "",
                    "SEQUENCING_RUN_EUID": "",
                    "SOURCE_ARTIFACT_EUID": "",
                    "LIBRARY_ID": ont_library,
                    "MODALITY": "lr",
                    "LAYOUT": "single_fastq",
                    "RUNID": ont_run_label,
                    "EXPERIMENTID": _safe_local_id(bundle_id, field_name="bundle ID"),
                    "LANEID": str(ont["position"]),
                    "BARCODEID": str(ont["barcode"]),
                    "SEQ_PLATFORM": "PROMETHION",
                    "SEQ_VENDOR": "ONT",
                    "ONT_R1_PATH": ",".join(ont_paths),
                    "SEQUENCING_INPUT_COMMENT": (
                        f"Raw ONT fastq_pass input from {ont['source_id']}; position "
                        f"{ont['position']}; flowcell {ont['flowcell_id']}"
                    ),
                },
            ]
        )
        analysis_units.append(
            {
                "ANALYSIS_UNIT_UID": au_uid,
                "ANALYSIS_UNIT_EUID": "",
                "SAMPLEID": sample_id,
                "DELIVERY_EUID": "",
                "DELIVERY_PROFILE": "local",
                "CUSTOMER_DELIVERY_ID": "",
                "SUBSAMPLE_PCT": "",
                "ONT_SUBSAMPLE_PCT": "",
                "ONT_FQ_START_HOUR": str(ONT_START_HOUR),
                "ONT_FQ_END_HOUR": str(ONT_END_HOUR),
                "ALIGNED_REF_UID": "",
                "BWA_KMER": "19",
                "DEEP_MODEL": "WGS",
                "MERGE_SINGLE": "single",
                "ANALYSIS_UNIT_COMMENT": (
                    f"{bundle_id} technical replicate from {row_id}; full ILMN coverage; "
                    "ONT raw FASTQ interval [0,24)"
                ),
            }
        )
        links.extend(
            [
                {
                    "ANALYSIS_UNIT_UID": au_uid,
                    "SEQUENCING_INPUT_UID": ilmn_input,
                    "ROLE": "sr",
                    "INPUT_ORDINAL": "1",
                },
                {
                    "ANALYSIS_UNIT_UID": au_uid,
                    "SEQUENCING_INPUT_UID": ont_input,
                    "ROLE": "lr",
                    "INPUT_ORDINAL": "2",
                },
            ]
        )
        receipt_units.append(
            {
                "crosswalk_row_id": row_id,
                "workbook_row": int(row["WORKBOOK_ROW"]),
                "biological_sample": sample_id,
                "analysis_unit_uid": au_uid,
                "ilmn": ilmn,
                "ont": ont,
            }
        )
    return (
        {
            "specimens.tsv": specimens,
            "samples.tsv": samples,
            "libraries.tsv": libraries,
            "sequencing_inputs.tsv": sequencing_inputs,
            "analysis_units.tsv": analysis_units,
            "analysis_unit_inputs.tsv": links,
        },
        receipt_units,
    )


def _validate_generated_bundle(
    *, bundle_dir: Path, expected_aus: int, runtime_yaml: Path
) -> Mapping[str, Any]:
    manifests = load_manifest_set(bundle_dir)
    units = manifests.rows["analysis_units.tsv"]
    inputs = manifests.rows["sequencing_inputs.tsv"]
    links = manifests.rows["analysis_unit_inputs.tsv"]
    if (
        len(units) != expected_aus
        or len(inputs) != expected_aus * 2
        or len(links) != expected_aus * 2
    ):
        raise BjuiceConfigError(f"generated topology does not match {expected_aus} hybrid AUs")
    roles_by_unit: dict[str, list[str]] = defaultdict(list)
    for link in links:
        roles_by_unit[link["ANALYSIS_UNIT_UID"]].append(link["ROLE"])
    if any(sorted(roles) != ["lr", "sr"] for roles in roles_by_unit.values()):
        raise BjuiceConfigError("every AU must select exactly one SR and one LR input")
    for unit in units:
        if unit.get("SUBSAMPLE_PCT") or unit.get("ONT_SUBSAMPLE_PCT"):
            raise BjuiceConfigError("subsample percentages must remain blank")
        if unit.get("ONT_FQ_START_HOUR") != "0" or unit.get("ONT_FQ_END_HOUR") != "24":
            raise BjuiceConfigError("every AU must use the exact ONT [0,24) interval")
    for name, fields in (
        ("specimens.tsv", ("SPECIMEN_EUID",)),
        ("samples.tsv", ("SAMPLE_EUID",)),
        ("libraries.tsv", ("LIBRARY_EUID",)),
        (
            "sequencing_inputs.tsv",
            ("POOL_TUBE_EUID", "SEQUENCING_RUN_EUID", "SOURCE_ARTIFACT_EUID"),
        ),
        ("analysis_units.tsv", ("ANALYSIS_UNIT_EUID", "DELIVERY_EUID")),
    ):
        for row in manifests.rows[name]:
            if any(row.get(field) for field in fields):
                raise BjuiceConfigError(f"generated {name} contains an EUID value")
    forbidden = ("preval", "migration-cleanup", "/.", "/fastq_fail/", "/unclassified/")
    for source in inputs:
        paths = ",".join(
            source.get(field, "")
            for field in ("ILMN_R1_PATH", "ILMN_R2_PATH", "ONT_R1_PATH", "ONT_R2_PATH")
        ).lower()
        if any(value in paths for value in forbidden):
            raise BjuiceConfigError(f"generated input contains a prohibited path: {paths}")
        if source["MODALITY"] == "lr" and "/fastq_pass/barcode" not in paths:
            raise BjuiceConfigError("ONT input is not restricted to fastq_pass/barcodeNN")
    runtime = yaml.safe_load(runtime_yaml.read_text(encoding="utf-8"))
    if runtime.get("ont_fastq_hour_window_mode") != "per_analysis_unit":
        raise BjuiceConfigError("runtime YAML lacks per-analysis-unit ONT windows")
    if runtime.get("sentdhiomr2", {}).get("hg38_sentdhiomr2_chrms") != "1-25":
        raise BjuiceConfigError("runtime YAML must configure chromosomes 1-25")
    if runtime.get("sentdhiomr2_nicu_research", {}).get("enabled") is not False:
        raise BjuiceConfigError("NICU must be disabled")
    if runtime.get("sentdhiomr2_jasmine", {}).get("enabled") is not False:
        raise BjuiceConfigError("Jasmine must be disabled")
    if runtime.get("sentdhiomr2_slim_consensus", {}).get("enabled") is not True:
        raise BjuiceConfigError("slim consensus must be enabled")
    return {
        "manifest_hashes": dict(manifests.hashes),
        "analysis_unit_count": len(units),
        "sequencing_input_count": len(inputs),
        "analysis_unit_input_count": len(links),
    }


def generate_bundle_configs(
    *,
    source_spec_json: Path,
    crosswalk_tsv: Path,
    source_inventory_json: Path,
    output_root: Path,
    profile: str,
    region: str,
) -> list[Mapping[str, Any]]:
    """Generate all five reviewed six-manifest configuration capsules locally."""

    spec = _source_spec(source_spec_json)
    crosswalk_rows = load_crosswalk(crosswalk_tsv)
    inventory = _read_json(source_inventory_json)
    if inventory.get("schema") != SOURCE_INVENTORY_SCHEMA:
        raise BjuiceConfigError(f"inventory schema must be {SOURCE_INVENTORY_SCHEMA}")
    if inventory.get("source_spec_sha256") != _sha256(source_spec_json):
        raise BjuiceConfigError("source spec changed after inventory")
    if inventory.get("crosswalk_sha256") != _sha256(crosswalk_tsv):
        raise BjuiceConfigError("crosswalk changed after inventory")
    aws = inventory.get("aws", {})
    if aws.get("profile") != profile or aws.get("region") != region:
        raise BjuiceConfigError("generator AWS context does not match the reviewed inventory")
    sources = inventory.get("sources")
    if not isinstance(sources, Mapping) or len(sources) != EXPECTED_SOURCE_COUNT:
        raise BjuiceConfigError("inventory does not contain all 37 source roots")
    expected_source_ids = {str(source["source_id"]) for source in spec["sources"]}
    if set(sources) != expected_source_ids:
        raise BjuiceConfigError("inventory source IDs differ from the explicit source spec")

    outputs: list[Mapping[str, Any]] = []
    for bundle in spec["bundles"]:
        bundle_id = str(bundle["bundle_id"])
        bundle_dir = output_root / bundle_id
        if bundle_dir.exists() and any(bundle_dir.iterdir()):
            raise BjuiceConfigError(f"bundle output directory is not empty: {bundle_dir}")
        bundle_dir.mkdir(parents=True, exist_ok=True)
        manifest_rows, receipt_units = _manifest_rows_for_bundle(
            bundle=bundle, crosswalk_rows=crosswalk_rows, inventory=inventory
        )
        for name, rows in manifest_rows.items():
            _write_tsv(bundle_dir / name, MANIFEST_COLUMNS[name], rows)
        sample_ids = sorted({row["SAMPLEID"] for row in manifest_rows["samples.tsv"]})
        runtime_yaml = bundle_dir / f"bjuice_validation_{bundle_id}_hiomr2.yaml"
        runtime_yaml.write_text(
            yaml.safe_dump(
                _runtime_config(bundle_id=bundle_id, sample_ids=sample_ids),
                sort_keys=False,
                default_flow_style=False,
            ),
            encoding="utf-8",
        )
        validation = _validate_generated_bundle(
            bundle_dir=bundle_dir,
            expected_aus=int(bundle["expected_paired_aus"]),
            runtime_yaml=runtime_yaml,
        )
        launch_blockers = []
        used_source_ids = [str(bundle["ilmn_source_id"]), *map(str, bundle["ont_source_ids"])]
        if any(not bool(sources[source_id].get("oow_done")) for source_id in used_source_ids):
            launch_blockers.append("CANONICAL_OWY_OOW_DONE_MISSING")
        receipt: dict[str, Any] = {
            "schema": GENERATION_RECEIPT_SCHEMA,
            # Configuration generation is deterministic for one reviewed
            # inventory snapshot; do not inject a second wall-clock value.
            "generated_at": str(inventory["generated_at"]),
            "bundle_id": bundle_id,
            "logical_run": int(bundle["logical_run"]),
            "configuration_status": "CONFIG_COMPLETE",
            "launch_status": "LAUNCH_BLOCKED",
            "launch_blockers": launch_blockers,
            "dyec": spec["dyec"],
            "dayoa": spec["dayoa"],
            "aws": {"profile": profile, "region": region, "account": aws.get("account", "")},
            "source_spec": str(source_spec_json),
            "source_spec_sha256": _sha256(source_spec_json),
            "crosswalk": str(crosswalk_tsv),
            "crosswalk_sha256": _sha256(crosswalk_tsv),
            "source_inventory": str(source_inventory_json),
            "source_inventory_sha256": _sha256(source_inventory_json),
            "runtime_yaml": runtime_yaml.name,
            "runtime_yaml_sha256": _sha256(runtime_yaml),
            "source_roots": {source_id: sources[source_id] for source_id in used_source_ids},
            "topology": validation,
            "analysis_units": receipt_units,
            "saved_dy_r_command": (
                "DAY_CONTAINERIZED=true dy-r "
                "produce_sentdhiomr2_slim_kitchensink_mega "
                "produce_sentdhiomr2_inflection_analytical_package "
                f"--configfile config/{runtime_yaml.name} "
                "--config 'genome_build=hg38' 'aligners=[\"sentmm2ont\"]' "
                "'dedupers=[\"na\"]' 'snv_callers=[\"sentdhiomr2\"]' "
                '\'sentdhiomr2={"hg38_sentdhiomr2_chrms":"1-25"}\' '
                "'sv_callers=[]' 'htd_callers=[\"smn12\"]' "
                "'ont_fastq_hour_window_mode=per_analysis_unit' "
                "'hiomr2_inflection_package_mode=analytical' "
                '"seqone_delivery_batch_id=$ANALYSIS_ID" '
                "-j 345 -T 1 -p -k --rerun-triggers mtime"
            ),
        }
        receipt_path = bundle_dir / "generation_receipt.json"
        _atomic_json(receipt_path, receipt)
        outputs.append(receipt)
    return outputs


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build fail-closed Bjuice validation crosswalks, inventories, and configs."
    )
    commands = parser.add_subparsers(dest="command", required=True)
    crosswalk = commands.add_parser("crosswalk", help="normalize the reviewed workbook extract")
    crosswalk.add_argument("--extract-json", type=Path, required=True)
    crosswalk.add_argument("--output", type=Path, required=True)
    inventory = commands.add_parser("inventory", help="inventory all explicit S3 roots read-only")
    inventory.add_argument("--source-spec", type=Path, required=True)
    inventory.add_argument("--crosswalk", type=Path, required=True)
    inventory.add_argument("--output", type=Path, required=True)
    inventory.add_argument("--profile", required=True)
    inventory.add_argument("--region", required=True)
    inventory.add_argument("--workers", type=int, default=8)
    generate = commands.add_parser("generate", help="generate all five local config capsules")
    generate.add_argument("--source-spec", type=Path, required=True)
    generate.add_argument("--crosswalk", type=Path, required=True)
    generate.add_argument("--source-inventory", type=Path, required=True)
    generate.add_argument("--output-root", type=Path, required=True)
    generate.add_argument("--profile", required=True)
    generate.add_argument("--region", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "crosswalk":
        build_crosswalk_from_artifact_extract(
            extract_json=args.extract_json, output_tsv=args.output
        )
    elif args.command == "inventory":
        build_source_inventory(
            source_spec_json=args.source_spec,
            crosswalk_tsv=args.crosswalk,
            output_json=args.output,
            profile=args.profile,
            region=args.region,
            workers=args.workers,
        )
    elif args.command == "generate":
        generate_bundle_configs(
            source_spec_json=args.source_spec,
            crosswalk_tsv=args.crosswalk,
            source_inventory_json=args.source_inventory,
            output_root=args.output_root,
            profile=args.profile,
            region=args.region,
        )
    else:  # pragma: no cover - argparse enforces this branch.
        raise BjuiceConfigError(f"unknown command: {args.command}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
