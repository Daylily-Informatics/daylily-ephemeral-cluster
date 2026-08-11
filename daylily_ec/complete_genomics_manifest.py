"""Generate the declared six-manifest fixture for Complete Genomics slim data.

This is intentionally a one-way, provider-neutral conversion of the reviewed
Complete source table. It does not discover a prior staging directory or accept
alternate input locations. It emits only the explicitly reserved test-only
``Z-`` fixture identities required by this non-customer validation contract.
"""

from __future__ import annotations

import csv
import json
from collections.abc import Mapping
from pathlib import Path
from urllib.parse import urlparse

from daylily_ec.bjuice_preval_config import MANIFEST_COLUMNS, _write_tsv
from daylily_ec.manifest_set import load_manifest_set

CONTRACT_VERSION = "complete-genomics-solo-six-manifest-v1"
CG_TEST_ONLY_IDENTITIES = {
    "specimen_euid": "Z-CG-TVBCG5X-HG003-5X-D0-SPECIMEN",
    "sample_euid": "Z-CG-TVBCG5X-HG003-5X-SAMPLE",
    "library_euid": "Z-CG-TVBCG5X-HG003-5X-D0-SR-LIBRARY",
}


class CompleteGenomicsManifestError(ValueError):
    """Raised when the supplied Complete source cannot produce the declared contract."""


def _read_single_row(source: Path) -> Mapping[str, str]:
    with source.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        rows = list(reader)
    if len(rows) != 1:
        raise CompleteGenomicsManifestError("Complete fixture source must contain exactly one row")
    return {str(key): str(value or "") for key, value in rows[0].items() if key}


def _required(row: Mapping[str, str], field: str) -> str:
    value = row.get(field, "").strip()
    if not value:
        raise CompleteGenomicsManifestError(f"source row requires nonblank {field}")
    return value


def _fsx_target(stage_target: str, row: Mapping[str, str], filename: str) -> str:
    return "/".join(
        [
            stage_target.rstrip("/"),
            CONTRACT_VERSION,
            _required(row, "RUN_ID"),
            _required(row, "SAMPLE_ID"),
            _required(row, "EXPERIMENTID"),
            f"lane-{_required(row, 'LANE')}",
            _required(row, "SEQBC_ID"),
            filename,
        ]
    )


def _s3_target(stage_s3_uri: str, stage_target: str, fsx_target: str) -> str:
    parsed = urlparse(stage_s3_uri)
    if parsed.scheme != "s3" or not parsed.netloc:
        raise CompleteGenomicsManifestError("stage_s3_uri must be an s3:// URI")
    prefix = stage_target.rstrip("/") + "/"
    if not fsx_target.startswith(prefix):
        raise CompleteGenomicsManifestError("staged FSx path must remain beneath STAGE_TARGET")
    return stage_s3_uri.rstrip("/") + "/" + fsx_target[len(prefix) :]


def generate_complete_genomics_six_manifest(
    *, source: Path, output_dir: Path, stage_s3_uri: str
) -> Path:
    """Write six manifests and a planned deterministic staging contract.

    The companion ``staging_receipt.json`` is deliberately a *request*, not a
    completion receipt.  Workflow launch must receive a separately produced
    successful receipt from the supported DYEC materialization step.
    """

    row = _read_single_row(source)
    if _required(row, "SEQ_VENDOR") != "CG":
        raise CompleteGenomicsManifestError("source SEQ_VENDOR must be exactly CG")
    if _required(row, "SEQ_PLATFORM") != "CG":
        raise CompleteGenomicsManifestError("source SEQ_PLATFORM must be exactly CG")
    if _required(row, "STAGE_DIRECTIVE") != "stage_data":
        raise CompleteGenomicsManifestError("source STAGE_DIRECTIVE must be exactly stage_data")
    stage_target = _required(row, "STAGE_TARGET")
    r1_source = _required(row, "CG_R1_FQ")
    r2_source = _required(row, "CG_R2_FQ")
    for path in (r1_source, r2_source):
        if not path.startswith("s3://"):
            raise CompleteGenomicsManifestError("CG source reads must be explicit s3:// URIs")

    run_id = _required(row, "RUN_ID")
    sample_id = _required(row, "SAMPLE_ID")
    experiment_id = _required(row, "EXPERIMENTID")
    lane = _required(row, "LANE")
    barcode = _required(row, "SEQBC_ID")
    specimen_euid = CG_TEST_ONLY_IDENTITIES["specimen_euid"]
    sample_euid = CG_TEST_ONLY_IDENTITIES["sample_euid"]
    library_euid = CG_TEST_ONLY_IDENTITIES["library_euid"]
    prefix = f"{run_id}-{sample_id}-{experiment_id}-{lane}-{barcode}"
    library_id = prefix + "-LIB"
    input_uid = prefix + "-INPUT"
    unit_uid = prefix + "-ANALYSIS"
    r1_target = _fsx_target(stage_target, row, Path(r1_source).name)
    r2_target = _fsx_target(stage_target, row, Path(r2_source).name)

    output_dir.mkdir(parents=True, exist_ok=True)
    manifests = {
        "specimens.tsv": [
            {
                "SPECIMEN_ID": sample_id,
                "SPECIMEN_EUID": specimen_euid,
                "SAMPLESOURCE": _required(row, "SAMPLESOURCE"),
                "SPECIMEN_TYPE": _required(row, "SAMPLE_TYPE"),
                "EXTERNAL_SPECIMEN_ID": _required(row, "EXTERNAL_SAMPLE_ID"),
                "BIOLOGICAL_SEX": _required(row, "BIOLOGICAL_SEX"),
                "N_X": _required(row, "N_X"),
                "N_Y": _required(row, "N_Y"),
                "SPECIMEN_COMMENT": "Source-backed Complete Genomics slim-data fixture.",
            }
        ],
        "samples.tsv": [
            {
                "SAMPLEID": sample_id,
                "SAMPLE_EUID": sample_euid,
                "SPECIMEN_ID": sample_id,
                "SAMPLECLASS": _required(row, "SAMPLECLASS"),
                "SAMPLE_TYPE": _required(row, "SAMPLE_TYPE"),
                "SAMPLEUSE": _required(row, "SAMPLEUSE"),
                "ORDER_TYPE": _required(row, "ORDER_TYPE"),
                "CONCORDANCE_CONTROL_PATH": _required(row, "CONCORDANCE_CONTROL_PATH").replace(
                    "s3://lsmc-dayoa-references-usw2", "/fsx/references"
                ),
                "IS_POSITIVE_CONTROL": _required(row, "IS_POS_CTRL"),
                "IS_NEGATIVE_CONTROL": _required(row, "IS_NEG_CTRL"),
                "TUM_NRM_SAMPLEID_MATCH": _required(row, "TUM_NRM_SAMPLEID_MATCH"),
                "EXTERNAL_SAMPLE_ID": _required(row, "EXTERNAL_SAMPLE_ID"),
                "IDDNA_UID": "",
                "TRUTH_DATA_DIR": _required(row, "TRUTH_DATA_DIR").replace(
                    "s3://lsmc-dayoa-references-usw2", "/fsx/references"
                ),
                "SAMPLE_COMMENT": "Source-backed Complete Genomics slim-data fixture.",
            }
        ],
        "libraries.tsv": [
            {
                "LIBRARY_ID": library_id,
                "LIBRARY_EUID": library_euid,
                "SAMPLEID": sample_id,
                "LIBPREP": _required(row, "LIB_PREP"),
                "AMPLIFICATION_TYPE": "",
                "LIBRARY_COMMENT": "Source-backed Complete Genomics slim-data fixture; reserved test-only identity.",
            }
        ],
        "sequencing_inputs.tsv": [
            {
                "SEQUENCING_INPUT_UID": input_uid,
                "POOL_TUBE_EUID": "",
                "SEQUENCING_RUN_EUID": "",
                "SOURCE_ARTIFACT_EUID": "",
                "LIBRARY_ID": library_id,
                "MODALITY": "sr",
                "LAYOUT": "paired_fastq",
                "RUNID": run_id,
                "EXPERIMENTID": experiment_id,
                "LANEID": lane,
                "BARCODEID": barcode,
                "SEQ_PLATFORM": "CG",
                "SEQ_VENDOR": "CG",
                "ILMN_R1_PATH": r1_target,
                "ILMN_R2_PATH": r2_target,
                "SEQUENCING_INPUT_COMMENT": "Complete Genomics fixture; EUIDs are explicit reserved test-only Z- values.",
            }
        ],
        "analysis_units.tsv": [
            {
                "ANALYSIS_UNIT_UID": unit_uid,
                "ANALYSIS_UNIT_EUID": "",
                "SAMPLEID": sample_id,
                "DELIVERY_EUID": "",
                "DELIVERY_PROFILE": "",
                "CUSTOMER_DELIVERY_ID": "",
                "SUBSAMPLE_PCT": _required(row, "SUBSAMPLE_PCT"),
                "ONT_SUBSAMPLE_PCT": "",
                "ALIGNED_REF_UID": "",
                "BWA_KMER": _required(row, "BWA_KMER"),
                "DEEP_MODEL": _required(row, "DEEP_MODEL"),
                "MERGE_SINGLE": "",
                "ANALYSIS_UNIT_COMMENT": "Source-backed Complete Genomics slim-data fixture.",
            }
        ],
        "analysis_unit_inputs.tsv": [
            {
                "ANALYSIS_UNIT_UID": unit_uid,
                "SEQUENCING_INPUT_UID": input_uid,
                "ROLE": "sr",
                "INPUT_ORDINAL": "1",
            }
        ],
    }
    for name, rows in manifests.items():
        _write_tsv(output_dir / name, MANIFEST_COLUMNS[name], rows)
    load_manifest_set(output_dir)
    receipt = {
        "contract_version": CONTRACT_VERSION,
        "state": "materialization_required",
        "source_manifest": str(source),
        "source_contract_provenance": {
            "order_type": _required(row, "ORDER_TYPE"),
            "reviewed_planner_ledger": "docs/plans/20260719T133324Z_majors_bjuiceprevalanalysis_complete_ledger.md",
            "reviewed_planner_bundle": "docs/plans/20260719T133324Z_majors_bjuiceprevalanalysis_complete_artifacts/manifest_assembly/review_bundle_v1/reviewed_planner_bundle.json",
        },
        "test_only_identity_contract": {
            "scope": "Reserved Z- fixture identifiers only; never owner-issued, persisted, registered, or used for customer release.",
            "specimen_euid": specimen_euid,
            "sample_euid": sample_euid,
            "library_euid": library_euid,
        },
        "stage_target": stage_target,
        "mappings": [
            {
                "source_s3_uri": r1_source,
                "staged_fsx_path": r1_target,
                "staged_s3_uri": _s3_target(stage_s3_uri, stage_target, r1_target),
            },
            {
                "source_s3_uri": r2_source,
                "staged_fsx_path": r2_target,
                "staged_s3_uri": _s3_target(stage_s3_uri, stage_target, r2_target),
            },
        ],
    }
    (output_dir / "staging_receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    )
    return output_dir
