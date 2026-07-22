"""Offline Bjuice prevalence DayOA six-manifest generation helpers.

This module is intentionally local and provider-neutral.  It consumes reviewed
source evidence files plus read-only S3 object listings and writes exact DayOA
six-manifest inputs.  It does not read an existing analysis ``config/`` tree and
does not call Ursa, Bloom, Dayhoff, TapDB, or any identity service.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping, Sequence
from urllib.parse import urlparse

import boto3

from daylily_ec.manifest_set import load_manifest_set


SPECIMEN_COLUMNS = (
    "SPECIMEN_ID",
    "SPECIMEN_EUID",
    "SAMPLESOURCE",
    "SPECIMEN_TYPE",
    "EXTERNAL_SPECIMEN_ID",
    "BIOLOGICAL_SEX",
    "N_X",
    "N_Y",
    "SPECIMEN_COMMENT",
)
SAMPLE_COLUMNS = (
    "SAMPLEID",
    "SAMPLE_EUID",
    "SPECIMEN_ID",
    "SAMPLECLASS",
    "SAMPLE_TYPE",
    "SAMPLEUSE",
    "ORDER_TYPE",
    "CONCORDANCE_CONTROL_PATH",
    "IS_POSITIVE_CONTROL",
    "IS_NEGATIVE_CONTROL",
    "TUM_NRM_SAMPLEID_MATCH",
    "EXTERNAL_SAMPLE_ID",
    "IDDNA_UID",
    "TRUTH_DATA_DIR",
    "SAMPLE_COMMENT",
)
LIBRARY_COLUMNS = (
    "LIBRARY_ID",
    "LIBRARY_EUID",
    "SAMPLEID",
    "LIBPREP",
    "AMPLIFICATION_TYPE",
    "LIBRARY_COMMENT",
)
SEQUENCING_INPUT_COLUMNS = (
    "SEQUENCING_INPUT_UID",
    "POOL_TUBE_EUID",
    "SEQUENCING_RUN_EUID",
    "SOURCE_ARTIFACT_EUID",
    "LIBRARY_ID",
    "MODALITY",
    "LAYOUT",
    "RUNID",
    "EXPERIMENTID",
    "LANEID",
    "BARCODEID",
    "SEQ_PLATFORM",
    "SEQ_VENDOR",
    "ILMN_R1_PATH",
    "ILMN_R2_PATH",
    "PACBIO_R1_PATH",
    "PACBIO_R2_PATH",
    "ONT_R1_PATH",
    "ONT_R2_PATH",
    "UG_R1_PATH",
    "UG_R2_PATH",
    "ILMN_TRIM_READ_LENGTH",
    "LONGREADTRIM_READ_LENGTH",
    "LONGREADTRIM_MODE",
    "ONT_BAM",
    "ONT_BAM_ALIGNER",
    "ONT_BAM_SNV_CALLER",
    "ONT_CRAM",
    "ONT_CRAM_ALIGNER",
    "ONT_CRAM_SNV_CALLER",
    "ROCHE_BAM",
    "ROCHE_BAM_ALIGNER",
    "ROCHE_BAM_SNV_CALLER",
    "ROCHE_DOWNSAMPLE_RATIO",
    "ULTIMA_CRAM",
    "ULTIMA_CRAM_ALIGNER",
    "ULTIMA_CRAM_SNV_CALLER",
    "PB_BAM",
    "PB_BAM_ALIGNER",
    "PB_BAM_SNV_CALLER",
    "SR_VCF_PATH",
    "LR_VCF_PATH",
    "SEQUENCING_INPUT_COMMENT",
)
ANALYSIS_UNIT_COLUMNS = (
    "ANALYSIS_UNIT_UID",
    "ANALYSIS_UNIT_EUID",
    "SAMPLEID",
    "DELIVERY_EUID",
    "DELIVERY_PROFILE",
    "CUSTOMER_DELIVERY_ID",
    "SUBSAMPLE_PCT",
    "ONT_SUBSAMPLE_PCT",
    "ALIGNED_REF_UID",
    "BWA_KMER",
    "DEEP_MODEL",
    "MERGE_SINGLE",
    "ANALYSIS_UNIT_COMMENT",
)
ANALYSIS_UNIT_INPUT_COLUMNS = (
    "ANALYSIS_UNIT_UID",
    "SEQUENCING_INPUT_UID",
    "ROLE",
    "INPUT_ORDINAL",
)
MANIFEST_COLUMNS: Mapping[str, tuple[str, ...]] = {
    "specimens.tsv": SPECIMEN_COLUMNS,
    "samples.tsv": SAMPLE_COLUMNS,
    "libraries.tsv": LIBRARY_COLUMNS,
    "sequencing_inputs.tsv": SEQUENCING_INPUT_COLUMNS,
    "analysis_units.tsv": ANALYSIS_UNIT_COLUMNS,
    "analysis_unit_inputs.tsv": ANALYSIS_UNIT_INPUT_COLUMNS,
}

SAFE_LABEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]*$")
DAYOA_READ_GROUP_LABEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]*$")
S3_FASTQ_SUFFIX = ".fastq.gz"
DEFAULT_FSX_RUN_MOUNT_ROOT = "/fsx/run_dir_mounts"
DEFAULT_ONT_FSX_ROOT = "/fsx/run_dir_mounts/pca100-2026"


class BjuiceConfigError(ValueError):
    """Raised when Bjuice source evidence cannot produce a launchable config."""


@dataclass(frozen=True)
class BjuiceConfigResult:
    """Generated manifest paths and receipt."""

    output_dir: Path
    receipt_path: Path
    manifest_hashes: Mapping[str, str]
    receipt: Mapping[str, Any]


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
        rows = [{k: str(v or "") for k, v in row.items()} for row in reader]
    if not rows:
        raise BjuiceConfigError(f"{path} has no data rows")
    return list(reader.fieldnames), rows


def _write_tsv(path: Path, columns: Sequence[str], rows: Iterable[Mapping[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(columns),
            delimiter="\t",
            lineterminator="\n",
            extrasaction="ignore",
        )
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _parse_s3_uri(uri: str) -> tuple[str, str]:
    parsed = urlparse(uri)
    if parsed.scheme != "s3" or not parsed.netloc or not parsed.path:
        raise BjuiceConfigError(f"expected s3:// URI, found {uri!r}")
    return parsed.netloc, parsed.path.lstrip("/")


def _join_s3(bucket: str, key: str) -> str:
    return f"s3://{bucket}/{key}"


def _list_s3_objects(*, s3_client: Any, prefix_uri: str) -> list[str]:
    bucket, prefix = _parse_s3_uri(prefix_uri)
    paginator = s3_client.get_paginator("list_objects_v2")
    paths: list[str] = []
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for item in page.get("Contents", []):
            key = str(item.get("Key") or "")
            if key:
                paths.append(_join_s3(bucket, key))
    return sorted(paths)


def _s3_to_fsx_path(
    s3_uri: str,
    *,
    run_id: str,
    platform: str,
    fsx_run_mount_root: str,
    ont_fsx_root: str,
) -> str:
    _bucket, key = _parse_s3_uri(s3_uri)
    parts = PurePosixPath(key).parts
    if platform == "ILMN":
        if run_id not in parts:
            raise BjuiceConfigError(f"ILMN S3 key does not contain run id {run_id}: {s3_uri}")
        run_index = parts.index(run_id)
        relative = PurePosixPath(*parts[run_index + 1 :])
        return str(PurePosixPath(fsx_run_mount_root) / run_id / relative)
    if platform == "ONT":
        lower_parts = [part.lower() for part in parts]
        try:
            platform_index = lower_parts.index("pca100")
        except ValueError as exc:
            raise BjuiceConfigError(f"ONT S3 key is not under pca100/2026: {s3_uri}") from exc
        if len(parts) <= platform_index + 2 or parts[platform_index + 1] != "2026":
            raise BjuiceConfigError(f"ONT S3 key is not under pca100/2026: {s3_uri}")
        relative = PurePosixPath(*parts[platform_index + 2 :])
        return str(PurePosixPath(ont_fsx_root) / relative)
    raise BjuiceConfigError(f"unsupported platform {platform!r}")


def _safe_label(value: str, *, field_name: str) -> str:
    text = str(value or "").strip()
    if not SAFE_LABEL_RE.fullmatch(text):
        raise BjuiceConfigError(
            f"{field_name} must match {SAFE_LABEL_RE.pattern}; found {value!r}"
        )
    return text


def _dayoa_read_group_label(value: str, *, field_name: str) -> str:
    """Return a DayOA-safe SQ/RU/EX/LANE label without changing source identity.

    DayOA currently rejects dots and underscores in read-group-like fields. Bjuice
    source run IDs legitimately contain those characters, so the launch helper
    emits deterministic workflow-safe labels while preserving the raw run IDs in
    source paths, comments, and the generation receipt.
    """

    text = str(value or "").strip()
    normalized = re.sub(r"[^A-Za-z0-9-]+", "-", text).strip("-")
    normalized = re.sub(r"-+", "-", normalized)
    if not DAYOA_READ_GROUP_LABEL_RE.fullmatch(normalized):
        raise BjuiceConfigError(
            f"{field_name} cannot be converted to a DayOA-safe label from {value!r}"
        )
    return normalized


def _index_one(rows: Sequence[Mapping[str, str]], field: str) -> dict[str, Mapping[str, str]]:
    indexed: dict[str, Mapping[str, str]] = {}
    for row in rows:
        key = str(row.get(field) or "").strip()
        if not key:
            continue
        if key in indexed:
            raise BjuiceConfigError(f"duplicate {field}: {key}")
        indexed[key] = row
    return indexed


def _matrix_rows_by_sample(rows: Sequence[Mapping[str, str]]) -> dict[str, dict[str, Mapping[str, str]]]:
    by_sample: dict[str, dict[str, Mapping[str, str]]] = defaultdict(dict)
    for row in rows:
        sample = str(row.get("specimenExternalName") or "").strip()
        lib_type = str(row.get("libType") or "").strip().upper()
        if sample and lib_type:
            if lib_type in by_sample[sample]:
                raise BjuiceConfigError(f"duplicate {lib_type} matrix row for {sample}")
            by_sample[sample][lib_type] = row
    return by_sample


def _source_uri_by_id(source_manifest: Mapping[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    for source in source_manifest.get("sources") or []:
        source_id = str(source.get("source_id") or "").strip()
        uri = str(source.get("uri") or "").strip()
        if source_id and uri:
            result[source_id] = uri
    return result


def _run_by_id(source_manifest: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    result: dict[str, Mapping[str, Any]] = {}
    for run in source_manifest.get("runs") or []:
        run_id = str(run.get("run_id") or "").strip()
        if run_id:
            result[run_id] = run
    return result


def _mappings_by_sample(source_manifest: Mapping[str, Any]) -> dict[str, list[Mapping[str, Any]]]:
    result: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in source_manifest.get("mappings") or []:
        sample = str(row.get("sample_id") or "").strip()
        if sample:
            result[sample].append(row)
    for sample in result:
        result[sample] = sorted(result[sample], key=lambda row: str(row.get("run_id") or ""))
    return result


def _sample_ilmn_fastqs(
    *,
    s3_paths: Sequence[str],
    sample_id: str,
    run_id: str,
    fsx_run_mount_root: str,
    ont_fsx_root: str,
) -> tuple[list[str], list[str]]:
    r1: list[str] = []
    r2: list[str] = []
    for uri in sorted(s3_paths):
        basename = PurePosixPath(_parse_s3_uri(uri)[1]).name
        if not basename.startswith(f"{sample_id}_") or not basename.endswith(S3_FASTQ_SUFFIX):
            continue
        if "_R1_" in basename:
            r1.append(
                _s3_to_fsx_path(
                    uri,
                    run_id=run_id,
                    platform="ILMN",
                    fsx_run_mount_root=fsx_run_mount_root,
                    ont_fsx_root=ont_fsx_root,
                )
            )
        elif "_R2_" in basename:
            r2.append(
                _s3_to_fsx_path(
                    uri,
                    run_id=run_id,
                    platform="ILMN",
                    fsx_run_mount_root=fsx_run_mount_root,
                    ont_fsx_root=ont_fsx_root,
                )
            )
    if not r1 or not r2 or len(r1) != len(r2):
        raise BjuiceConfigError(
            f"{sample_id} ILMN FASTQs must contain equal nonzero R1/R2 lists; "
            f"found R1={len(r1)} R2={len(r2)}"
        )
    return r1, r2


def _sample_ont_fastqs(
    *,
    s3_paths: Sequence[str],
    barcode: str,
    run_id: str,
    fsx_run_mount_root: str,
    ont_fsx_root: str,
) -> list[str]:
    marker = f"/{barcode}/"
    selected = [
        _s3_to_fsx_path(
            uri,
            run_id=run_id,
            platform="ONT",
            fsx_run_mount_root=fsx_run_mount_root,
            ont_fsx_root=ont_fsx_root,
        )
        for uri in sorted(s3_paths)
        if marker in uri and uri.endswith(S3_FASTQ_SUFFIX)
    ]
    if not selected:
        raise BjuiceConfigError(f"{run_id} {barcode} has no ONT FASTQs")
    return selected


def generate_bjuice_preval_manifests(
    *,
    output_dir: Path,
    samples: Sequence[str],
    source_manifest_json: Path,
    run_evidence_json: Path,
    library_run_matrix_tsv: Path,
    sample_metadata_tsv: Path,
    legacy_units_tsv: Path,
    sr_subsample_pct: str,
    ont_subsample_pct: str,
    analysis_label: str,
    profile: str | None,
    region: str | None,
    fsx_run_mount_root: str = DEFAULT_FSX_RUN_MOUNT_ROOT,
    ont_fsx_root: str = DEFAULT_ONT_FSX_ROOT,
    order_type: str = "RESEARCH",
) -> BjuiceConfigResult:
    """Generate exact six manifests for a Bjuice prevalence sample subset."""

    resolved_samples = [_safe_label(sample, field_name="sample") for sample in samples]
    if not resolved_samples:
        raise BjuiceConfigError("at least one --sample is required")
    if len(resolved_samples) != len(set(resolved_samples)):
        raise BjuiceConfigError("duplicate --sample values are not allowed")
    resolved_label = _safe_label(analysis_label, field_name="analysis-label").upper()
    if output_dir.exists() and any(output_dir.iterdir()):
        raise BjuiceConfigError(f"output directory already exists and is not empty: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)

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
    source_uri_by_id = _source_uri_by_id(source_manifest)
    runs_by_id = _run_by_id(source_manifest)
    mappings_by_sample = _mappings_by_sample(source_manifest)

    ilmn_runs = [
        run for run in runs_by_id.values() if str(run.get("platform") or "").upper() == "ILMN"
    ]
    if len(ilmn_runs) != 1:
        raise BjuiceConfigError(f"expected exactly one ILMN run; found {len(ilmn_runs)}")
    ilmn_run = ilmn_runs[0]
    ilmn_run_id = str(ilmn_run["run_id"])
    ilmn_run_label = _dayoa_read_group_label(ilmn_run_id, field_name="ILMN run_id")
    ilmn_prefix = source_uri_by_id[str(ilmn_run["prefix_source_id"])]

    session_kwargs: dict[str, str] = {}
    if profile:
        session_kwargs["profile_name"] = profile
    if region:
        session_kwargs["region_name"] = region
    s3_client = boto3.Session(**session_kwargs).client("s3")
    ilmn_s3_paths = _list_s3_objects(s3_client=s3_client, prefix_uri=ilmn_prefix)
    ont_s3_paths_by_run: dict[str, list[str]] = {}

    specimens: list[dict[str, str]] = []
    sample_rows: list[dict[str, str]] = []
    libraries: list[dict[str, str]] = []
    sequencing_inputs: list[dict[str, str]] = []
    analysis_units: list[dict[str, str]] = []
    analysis_unit_inputs: list[dict[str, str]] = []
    receipt_samples: list[dict[str, Any]] = []

    for sample_id in resolved_samples:
        if sample_id not in metadata_by_sample:
            raise BjuiceConfigError(f"sample metadata is missing {sample_id}")
        if sample_id not in units_by_sample:
            raise BjuiceConfigError(f"legacy units metadata is missing {sample_id}")
        if sample_id not in matrix_by_sample:
            raise BjuiceConfigError(f"library/run matrix is missing {sample_id}")
        matrix_rows_for_sample = matrix_by_sample[sample_id]
        if "ILMN" not in matrix_rows_for_sample or "ONT" not in matrix_rows_for_sample:
            raise BjuiceConfigError(f"matrix must contain ILMN and ONT rows for {sample_id}")
        metadata = metadata_by_sample[sample_id]
        unit_metadata = units_by_sample[sample_id]
        sample_use = metadata.get("SAMPLEUSE", "") or unit_metadata.get("SAMPLEUSE", "")
        if not sample_use:
            raise BjuiceConfigError(
                f"{sample_id} SAMPLEUSE is blank in both sample metadata and legacy units TSV"
            )
        ilmn_matrix = matrix_rows_for_sample["ILMN"]
        ont_matrix = matrix_rows_for_sample["ONT"]
        specimen_euid = str(ilmn_matrix.get("specimenEUID") or "").strip()
        sample_euid = str(ilmn_matrix.get("sampleEUID") or "").strip()
        ilmn_library_euid = str(ilmn_matrix.get("libraryEUID") or "").strip()
        ont_library_euid = str(ont_matrix.get("libraryEUID") or "").strip()
        ilmn_library_id = f"{sample_id}-ILMN"
        ont_library_id = f"{sample_id}-ONT"
        analysis_unit_uid = f"{resolved_label}-{sample_id}-HIOMRS"

        r1_paths, r2_paths = _sample_ilmn_fastqs(
            s3_paths=ilmn_s3_paths,
            sample_id=sample_id,
            run_id=ilmn_run_id,
            fsx_run_mount_root=fsx_run_mount_root,
            ont_fsx_root=ont_fsx_root,
        )
        ilmn_input_uid = f"{sample_id}-ILMN-{ilmn_library_euid}"

        specimens.append(
            {
                "SPECIMEN_ID": sample_id,
                "SPECIMEN_EUID": specimen_euid,
                "SAMPLESOURCE": metadata.get("SAMPLESOURCE", ""),
                "SPECIMEN_TYPE": metadata.get("SAMPLE_TYPE", ""),
                "EXTERNAL_SPECIMEN_ID": sample_id,
                "BIOLOGICAL_SEX": metadata.get("BIOLOGICAL_SEX", ""),
                "N_X": metadata.get("N_X", ""),
                "N_Y": metadata.get("N_Y", ""),
                "SPECIMEN_COMMENT": (
                    f"Bjuice prevalence generated config for {sample_id}; "
                    f"source specimen EUID {specimen_euid}"
                ),
            }
        )
        sample_rows.append(
            {
                "SAMPLEID": sample_id,
                "SAMPLE_EUID": sample_euid,
                "SPECIMEN_ID": sample_id,
                "SAMPLECLASS": metadata.get("SAMPLECLASS", ""),
                "SAMPLE_TYPE": metadata.get("SAMPLE_TYPE", ""),
                "SAMPLEUSE": sample_use,
                "ORDER_TYPE": order_type,
                "CONCORDANCE_CONTROL_PATH": metadata.get("CONCORDANCE_CONTROL_PATH", ""),
                "IS_POSITIVE_CONTROL": metadata.get("IS_POSITIVE_CONTROL", ""),
                "IS_NEGATIVE_CONTROL": metadata.get("IS_NEGATIVE_CONTROL", ""),
                "TUM_NRM_SAMPLEID_MATCH": metadata.get("TUM_NRM_SAMPLEID_MATCH", ""),
                "EXTERNAL_SAMPLE_ID": metadata.get("EXTERNAL_SAMPLE_ID", sample_id),
                "IDDNA_UID": metadata.get("IDDNA_UID", ""),
                "TRUTH_DATA_DIR": metadata.get("TRUTH_DATA_DIR", ""),
                "SAMPLE_COMMENT": (
                    f"Bjuice prevalence generated config for {sample_id}; "
                    f"source sample EUID {sample_euid}"
                ),
            }
        )
        libraries.extend(
            [
                {
                    "LIBRARY_ID": ilmn_library_id,
                    "LIBRARY_EUID": ilmn_library_euid,
                    "SAMPLEID": sample_id,
                    "LIBPREP": "UNKNOWN",
                    "AMPLIFICATION_TYPE": "WGS",
                    "LIBRARY_COMMENT": (
                        f"{sample_id} ILMN library from reviewed matrix; "
                        f"source library EUID {ilmn_library_euid}"
                    ),
                },
                {
                    "LIBRARY_ID": ont_library_id,
                    "LIBRARY_EUID": ont_library_euid,
                    "SAMPLEID": sample_id,
                    "LIBPREP": "UNKNOWN",
                    "AMPLIFICATION_TYPE": "WGS",
                    "LIBRARY_COMMENT": (
                        f"{sample_id} ONT library from reviewed matrix; "
                        f"source library EUID {ont_library_euid}"
                    ),
                },
            ]
        )
        sequencing_inputs.append(
            {
                "SEQUENCING_INPUT_UID": ilmn_input_uid,
                "POOL_TUBE_EUID": "",
                "SEQUENCING_RUN_EUID": str(ilmn_matrix.get("ILMN RunEUID") or "").strip(),
                "SOURCE_ARTIFACT_EUID": "",
                "LIBRARY_ID": ilmn_library_id,
                "MODALITY": "sr",
                "LAYOUT": "paired_fastq",
                "RUNID": ilmn_run_label,
                "EXPERIMENTID": analysis_label,
                "LANEID": "L001-L008",
                "BARCODEID": sample_id,
                "SEQ_PLATFORM": "NOVASEQ",
                "SEQ_VENDOR": "ILMN",
                "ILMN_R1_PATH": ",".join(r1_paths),
                "ILMN_R2_PATH": ",".join(r2_paths),
                "SEQUENCING_INPUT_COMMENT": (
                    f"{sample_id} ILMN input generated from reviewed S3 prefix {ilmn_prefix}"
                ),
            }
        )
        input_ordinal = 1
        analysis_unit_inputs.append(
            {
                "ANALYSIS_UNIT_UID": analysis_unit_uid,
                "SEQUENCING_INPUT_UID": ilmn_input_uid,
                "ROLE": "sr",
                "INPUT_ORDINAL": str(input_ordinal),
            }
        )
        ont_receipts: list[dict[str, Any]] = []
        for mapping in mappings_by_sample.get(sample_id, []):
            run_id = str(mapping.get("run_id") or "").strip()
            run_label = _dayoa_read_group_label(run_id, field_name=f"{sample_id} ONT run_id")
            barcode = str(mapping.get("barcode") or "").strip()
            run = runs_by_id.get(run_id)
            if not run or str(run.get("platform") or "").upper() != "ONT":
                raise BjuiceConfigError(f"{sample_id} mapping references non-ONT run {run_id}")
            prefix_uri = source_uri_by_id[str(run["prefix_source_id"])]
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
            run_euids = [value.strip() for value in str(ont_matrix.get("ONT RunEUID") or "").split(";")]
            run_names = [value.strip() for value in str(ont_matrix.get("ONT RunName") or "").split(";")]
            run_euid_by_name = dict(zip(run_names, run_euids))
            sequencing_run_euid = run_euid_by_name.get(run_id, "")
            input_ordinal += 1
            input_uid = f"{sample_id}-ONT-{ont_library_euid}-{sequencing_run_euid or run_label}"
            sequencing_inputs.append(
                {
                    "SEQUENCING_INPUT_UID": input_uid,
                    "POOL_TUBE_EUID": "",
                    "SEQUENCING_RUN_EUID": sequencing_run_euid,
                    "SOURCE_ARTIFACT_EUID": "",
                    "LIBRARY_ID": ont_library_id,
                    "MODALITY": "lr",
                    "LAYOUT": "single_fastq",
                    "RUNID": run_label,
                    "EXPERIMENTID": analysis_label,
                    "LANEID": str(run.get("position_id") or ""),
                    "BARCODEID": barcode,
                    "SEQ_PLATFORM": "PROMETHION",
                    "SEQ_VENDOR": "ONT",
                    "ONT_R1_PATH": ",".join(ont_paths),
                    "SEQUENCING_INPUT_COMMENT": (
                    f"{sample_id} ONT input generated from reviewed S3 prefix "
                    f"{prefix_uri}, raw run ID {run_id}, and barcode {barcode}"
                    ),
                }
            )
            analysis_unit_inputs.append(
                {
                    "ANALYSIS_UNIT_UID": analysis_unit_uid,
                    "SEQUENCING_INPUT_UID": input_uid,
                    "ROLE": "lr",
                    "INPUT_ORDINAL": str(input_ordinal),
                }
            )
            ont_receipts.append(
                {
                    "run_id": run_id,
                    "dayoa_run_label": run_label,
                    "barcode": barcode,
                    "sequencing_input_uid": input_uid,
                    "fastq_count": len(ont_paths),
                    "prefix_uri": prefix_uri,
                }
            )
        if len(ont_receipts) != 3:
            raise BjuiceConfigError(f"{sample_id} must have exactly three ONT mappings")
        analysis_units.append(
            {
                "ANALYSIS_UNIT_UID": analysis_unit_uid,
                "ANALYSIS_UNIT_EUID": "",
                "SAMPLEID": sample_id,
                "DELIVERY_EUID": "",
                "DELIVERY_PROFILE": "local",
                "CUSTOMER_DELIVERY_ID": "",
                "SUBSAMPLE_PCT": sr_subsample_pct,
                "ONT_SUBSAMPLE_PCT": ont_subsample_pct,
                "ALIGNED_REF_UID": "",
                "BWA_KMER": (
                    metadata.get("BWA_KMER", "") or unit_metadata.get("BWA_KMER", "19") or "19"
                ),
                "DEEP_MODEL": (
                    metadata.get("DEEP_MODEL", "")
                    or unit_metadata.get("DEEP_MODEL", "WGS")
                    or "WGS"
                ),
                "MERGE_SINGLE": (
                    metadata.get("MERGE_SINGLE", "")
                    or unit_metadata.get("MERGE_SINGLE", "single")
                    or "single"
                ),
                "ANALYSIS_UNIT_COMMENT": (
                    f"Generated {analysis_label} HIOMRS analysis for {sample_id}; "
                    f"SR downsample {sr_subsample_pct or 'full'}; "
                    f"ONT downsample {ont_subsample_pct or 'full'}"
                ),
            }
        )
        receipt_samples.append(
            {
                "sample_id": sample_id,
                "analysis_unit_uid": analysis_unit_uid,
                "ilmn_input_uid": ilmn_input_uid,
                "ilmn_run_id": ilmn_run_id,
                "ilmn_dayoa_run_label": ilmn_run_label,
                "ilmn_fastq_r1_count": len(r1_paths),
                "ilmn_fastq_r2_count": len(r2_paths),
                "ont_inputs": ont_receipts,
            }
        )

    manifest_rows: Mapping[str, list[dict[str, str]]] = {
        "specimens.tsv": specimens,
        "samples.tsv": sample_rows,
        "libraries.tsv": libraries,
        "sequencing_inputs.tsv": sequencing_inputs,
        "analysis_units.tsv": analysis_units,
        "analysis_unit_inputs.tsv": analysis_unit_inputs,
    }
    for name, rows in manifest_rows.items():
        _write_tsv(output_dir / name, MANIFEST_COLUMNS[name], rows)
    manifest_set = load_manifest_set(output_dir)
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    receipt: dict[str, Any] = {
        "schema": "dyec.bjuice_preval_config_generation.v1",
        "generated_at": generated_at,
        "output_dir": str(output_dir),
        "source_manifest_json": str(source_manifest_json),
        "run_evidence_json": str(run_evidence_json),
        "library_run_matrix_tsv": str(library_run_matrix_tsv),
        "sample_metadata_tsv": str(sample_metadata_tsv),
        "legacy_units_tsv": str(legacy_units_tsv),
        "samples": receipt_samples,
        "analysis_label": analysis_label,
        "sr_subsample_pct": sr_subsample_pct,
        "ont_subsample_pct": ont_subsample_pct,
        "fsx_run_mount_root": fsx_run_mount_root,
        "ont_fsx_root": ont_fsx_root,
        "manifest_hashes": dict(manifest_set.hashes),
        "source_observations": {
            "ilmn_prefix": ilmn_prefix,
            "ilmn_s3_objects_listed": len(ilmn_s3_paths),
            "ont_s3_objects_listed_by_run": {
                run_id: len(paths) for run_id, paths in sorted(ont_s3_paths_by_run.items())
            },
        },
    }
    receipt_path = output_dir / "bjuice_preval_config_receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return BjuiceConfigResult(
        output_dir=output_dir,
        receipt_path=receipt_path,
        manifest_hashes=dict(manifest_set.hashes),
        receipt=receipt,
    )
