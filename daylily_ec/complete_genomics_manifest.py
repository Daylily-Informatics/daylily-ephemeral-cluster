"""Generate the declared six-manifest fixture for Complete Genomics slim data.

This is intentionally a one-way, provider-neutral conversion of the reviewed
Complete source table. It does not discover a prior staging directory or accept
alternate input locations. It emits only the explicitly reserved test-only
``Z-`` fixture identities required by this non-customer validation contract.
"""

from __future__ import annotations

import csv
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from urllib.parse import urlparse

from daylily_ec.bjuice_preval_config import MANIFEST_COLUMNS, _write_tsv
from daylily_ec.manifest_set import load_manifest_set

CONTRACT_VERSION = "complete-genomics-solo-six-manifest-v1"
SLIM_MOUNTED_REFERENCE_CONTRACT_VERSION = "complete-genomics-slim-mounted-reference-v1"
CG_TEST_ONLY_IDENTITIES = {
    "specimen_euid": "Z-CG-TVBCG5X-HG003-5X-D0-SPECIMEN",
    "sample_euid": "Z-CG-TVBCG5X-HG003-5X-SAMPLE",
    "library_euid": "Z-CG-TVBCG5X-HG003-5X-D0-SR-LIBRARY",
}
CG_SLIM_TEST_ONLY_IDENTITIES = {
    "specimen_euid": "Z-CG-TVBCG5X-HG003-5X-SLIM-SPECIMEN",
    "sample_euid": "Z-CG-TVBCG5X-HG003-5X-SLIM-SAMPLE",
    "library_euid": "Z-CG-TVBCG5X-HG003-5X-SLIM-SR-LIBRARY",
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


def _normalize_s3_uri(value: str, *, field: str) -> str:
    parsed = urlparse(value)
    if (
        parsed.scheme != "s3"
        or not parsed.netloc
        or parsed.params
        or parsed.query
        or parsed.fragment
    ):
        raise CompleteGenomicsManifestError(f"{field} must be an unadorned s3:// URI")
    key = parsed.path.lstrip("/")
    return f"s3://{parsed.netloc}" + (f"/{key}" if key else "")


def _mounted_reference_target(
    *, source_s3_uri: str, reference_s3_uri: str, reference_fsx_root: str
) -> str:
    normalized_source = _normalize_s3_uri(source_s3_uri, field="CG source read")
    normalized_root = _normalize_s3_uri(reference_s3_uri, field="reference_s3_uri")
    normalized_fsx_root = reference_fsx_root.rstrip("/")
    if normalized_fsx_root != "/fsx/references":
        raise CompleteGenomicsManifestError(
            "reference_fsx_root must be exactly /fsx/references for mounted reference input"
        )
    prefix = normalized_root + "/"
    if not normalized_source.startswith(prefix):
        raise CompleteGenomicsManifestError(
            "CG source read must be beneath the explicit reference_s3_uri"
        )
    relative = normalized_source[len(prefix) :]
    if not relative or any(part in {"", ".", ".."} for part in relative.split("/")):
        raise CompleteGenomicsManifestError("CG source read has an unsafe relative S3 key")
    return normalized_fsx_root + "/" + relative


def _write_manifest_set(
    *,
    output_dir: Path,
    row: Mapping[str, str],
    identities: Mapping[str, str],
    r1_target: str,
    r2_target: str,
    comment: str,
) -> None:
    if output_dir.exists():
        raise CompleteGenomicsManifestError(
            f"refusing to overwrite an existing Complete Genomics manifest directory: {output_dir}"
        )
    output_dir.mkdir(parents=True)

    run_id = _required(row, "RUN_ID")
    sample_id = _required(row, "SAMPLE_ID")
    experiment_id = _required(row, "EXPERIMENTID")
    lane = _required(row, "LANE")
    barcode = _required(row, "SEQBC_ID")
    specimen_euid = identities["specimen_euid"]
    sample_euid = identities["sample_euid"]
    library_euid = identities["library_euid"]
    prefix = f"{run_id}-{sample_id}-{experiment_id}-{lane}-{barcode}"
    library_id = prefix + "-LIB"
    input_uid = prefix + "-INPUT"
    unit_uid = prefix + "-ANALYSIS"
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
                "SPECIMEN_COMMENT": comment,
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
                "SAMPLE_COMMENT": comment,
            }
        ],
        "libraries.tsv": [
            {
                "LIBRARY_ID": library_id,
                "LIBRARY_EUID": library_euid,
                "SAMPLEID": sample_id,
                "LIBPREP": _required(row, "LIB_PREP"),
                "AMPLIFICATION_TYPE": "",
                "LIBRARY_COMMENT": comment + "; reserved test-only identity.",
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
                "ANALYSIS_UNIT_COMMENT": comment,
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

    r1_target = _fsx_target(stage_target, row, Path(r1_source).name)
    r2_target = _fsx_target(stage_target, row, Path(r2_source).name)
    _write_manifest_set(
        output_dir=output_dir,
        row=row,
        identities=CG_TEST_ONLY_IDENTITIES,
        r1_target=r1_target,
        r2_target=r2_target,
        comment="Source-backed Complete Genomics slim-data fixture.",
    )
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
            "specimen_euid": CG_TEST_ONLY_IDENTITIES["specimen_euid"],
            "sample_euid": CG_TEST_ONLY_IDENTITIES["sample_euid"],
            "library_euid": CG_TEST_ONLY_IDENTITIES["library_euid"],
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


def generate_complete_genomics_slim_mounted_reference_six_manifest(
    *,
    source: Path,
    output_dir: Path,
    reference_s3_uri: str,
    reference_fsx_root: str,
) -> Path:
    """Write a planned six-manifest set for an explicit mounted slim CG pair.

    This mode is deliberately narrow.  It accepts only the user-declared
    read-only reference role mount and does not copy, move, or discover input
    data.  The accompanying receipt remains non-materialized until a DYEC
    headnode verifier records the exact two files.
    """

    row = _read_single_row(source)
    if _required(row, "SEQ_VENDOR") != "CG":
        raise CompleteGenomicsManifestError("source SEQ_VENDOR must be exactly CG")
    if _required(row, "SEQ_PLATFORM") != "CG":
        raise CompleteGenomicsManifestError("source SEQ_PLATFORM must be exactly CG")
    if _required(row, "STAGE_DIRECTIVE") != "pass_through":
        raise CompleteGenomicsManifestError(
            "mounted slim CG source STAGE_DIRECTIVE must be exactly pass_through"
        )
    if _required(row, "STAGE_TARGET").rstrip("/") != reference_fsx_root.rstrip("/"):
        raise CompleteGenomicsManifestError(
            "mounted slim CG source STAGE_TARGET must exactly match reference_fsx_root"
        )
    r1_source = _required(row, "CG_R1_FQ")
    r2_source = _required(row, "CG_R2_FQ")
    r1_target = _mounted_reference_target(
        source_s3_uri=r1_source,
        reference_s3_uri=reference_s3_uri,
        reference_fsx_root=reference_fsx_root,
    )
    r2_target = _mounted_reference_target(
        source_s3_uri=r2_source,
        reference_s3_uri=reference_s3_uri,
        reference_fsx_root=reference_fsx_root,
    )
    _write_manifest_set(
        output_dir=output_dir,
        row=row,
        identities=CG_SLIM_TEST_ONLY_IDENTITIES,
        r1_target=r1_target,
        r2_target=r2_target,
        comment="Source-backed Complete Genomics downsampled slim-data fixture.",
    )
    receipt = {
        "access_mode": "mounted_reference_dra",
        "contract_version": SLIM_MOUNTED_REFERENCE_CONTRACT_VERSION,
        "state": "materialization_required",
        "source_manifest": str(source),
        "source_contract_provenance": {
            "customer_release_eligible": False,
            "order_type": _required(row, "ORDER_TYPE"),
            "source": "explicit downsampled slim reference S3 pair",
        },
        "reference_mapping": {
            "source_s3_uri": _normalize_s3_uri(reference_s3_uri, field="reference_s3_uri"),
            "workflow_fsx_root": reference_fsx_root.rstrip("/"),
        },
        "mappings": [
            {
                "source_s3_uri": _normalize_s3_uri(r1_source, field="CG_R1_FQ"),
                "workflow_path": r1_target,
            },
            {
                "source_s3_uri": _normalize_s3_uri(r2_source, field="CG_R2_FQ"),
                "workflow_path": r2_target,
            },
        ],
        "test_only_identity_contract": {
            "scope": "Reserved Z- fixture identifiers only; never owner-issued, persisted, registered, or used for customer release.",
            **CG_SLIM_TEST_ONLY_IDENTITIES,
        },
    }
    (output_dir / "staging_receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_dir


def finalize_complete_genomics_slim_mounted_reference_materialization(
    *,
    manifest_dir: Path,
    files_verified: Sequence[Mapping[str, object]],
    verified_at: str,
    headnode: Mapping[str, str],
) -> dict[str, object]:
    """Record verified mounted-reference input evidence in a planned receipt.

    The final receipt can only attest regular, readable gzip files that match
    the two workflow paths already present in the validated six-manifest set.
    """

    receipt_path = manifest_dir / "staging_receipt.json"
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CompleteGenomicsManifestError(
            f"unable to read planned mounted slim CG receipt: {receipt_path}: {exc}"
        ) from exc
    if receipt.get("contract_version") != SLIM_MOUNTED_REFERENCE_CONTRACT_VERSION:
        raise CompleteGenomicsManifestError("receipt is not a mounted slim CG receipt")
    if receipt.get("state") != "materialization_required":
        raise CompleteGenomicsManifestError(
            "mounted slim CG receipt must be materialization_required before finalization"
        )

    manifests = load_manifest_set(manifest_dir)
    sequencing_inputs = manifests.rows["sequencing_inputs.tsv"]
    if len(sequencing_inputs) != 1:
        raise CompleteGenomicsManifestError(
            "mounted slim CG contract requires exactly one input row"
        )
    expected_paths = [
        sequencing_inputs[0]["ILMN_R1_PATH"],
        sequencing_inputs[0]["ILMN_R2_PATH"],
    ]
    receipt_mappings = receipt.get("mappings")
    if (
        not isinstance(receipt_mappings, list)
        or [
            mapping.get("workflow_path") if isinstance(mapping, dict) else None
            for mapping in receipt_mappings
        ]
        != expected_paths
    ):
        raise CompleteGenomicsManifestError(
            "planned receipt paths do not exactly match sequencing_inputs.tsv"
        )

    verified_by_path: dict[str, dict[str, object]] = {}
    for item in files_verified:
        path = str(item.get("workflow_path") or "")
        size = item.get("size_bytes")
        gzip_magic = str(item.get("gzip_magic") or "")
        if path not in expected_paths:
            raise CompleteGenomicsManifestError(
                f"verification returned an unexpected workflow path: {path!r}"
            )
        if path in verified_by_path:
            raise CompleteGenomicsManifestError(f"verification returned duplicate path: {path}")
        if not isinstance(size, int) or size <= 0:
            raise CompleteGenomicsManifestError(f"verification has invalid size for {path}")
        if gzip_magic != "1f8b":
            raise CompleteGenomicsManifestError(f"verification lacks gzip magic for {path}")
        verified_by_path[path] = {
            "workflow_path": path,
            "size_bytes": size,
            "gzip_magic": gzip_magic,
        }
    if set(verified_by_path) != set(expected_paths):
        raise CompleteGenomicsManifestError("verification did not attest both CG workflow paths")

    clean_headnode = {key: str(value) for key, value in headnode.items() if str(value)}
    if not {"cluster", "instance_id", "ssm_command_id"}.issubset(clean_headnode):
        raise CompleteGenomicsManifestError(
            "mounted slim CG materialization requires cluster, instance_id, and ssm_command_id"
        )
    receipt["state"] = "materialized"
    receipt["materialization"] = {
        "copy_performed": False,
        "files_verified": [verified_by_path[path] for path in expected_paths],
        "headnode": clean_headnode,
        "kind": "mounted_reference_dra",
        "verified_at": verified_at,
        "verification_scope": "regular_file_readable_and_gzip_magic",
    }
    receipt_path.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return receipt
