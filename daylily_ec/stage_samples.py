"""Stage analysis samples into the headnode-visible FSx namespace.

This module is the source of truth for ``daylily-ec samples stage`` and the
legacy ``bin/daylily-stage-samples-from-local-to-headnode`` wrapper.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import uuid
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

RUN_ID = "RUN_ID"
SAMPLE_ID = "SAMPLE_ID"
SAMPLEID = "SAMPLEID"
SPECIMEN_ID = "SPECIMEN_ID"
SPECIMEN_EUID = "SPECIMEN_EUID"
SAMPLE_EUID = "SAMPLE_EUID"
ANALYSIS_UNIT_UID = "ANALYSIS_UNIT_UID"
LIBRARY_EUID = "LIBRARY_EUID"
INFLECTION_DELIVERY_ID = "INFLECTION_DELIVERY_ID"
EXPERIMENT_ID = "EXPERIMENTID"
SAMPLE_TYPE = "SAMPLE_TYPE"
SAMPLESOURCE = "SAMPLESOURCE"
SAMPLECLASS = "SAMPLECLASS"
BIOLOGICAL_SEX = "BIOLOGICAL_SEX"
TUM_NRM_SAMPLEID_MATCH = "TUM_NRM_SAMPLEID_MATCH"
LIB_PREP = "LIB_PREP"
SEQ_VENDOR = "SEQ_VENDOR"
SEQ_PLATFORM = "SEQ_PLATFORM"
LANE = "LANE"
SEQBC_ID = "SEQBC_ID"
PATH_TO_CONCORDANCE = "PATH_TO_CONCORDANCE_DATA_DIR"
CONCORDANCE_CONTROL_PATH = "CONCORDANCE_CONTROL_PATH"
TRUTH_DATA_DIR = "TRUTH_DATA_DIR"
R1_FQ = "R1_FQ"
R2_FQ = "R2_FQ"
ILMN_R1_FQ = "ILMN_R1_FQ"
ILMN_R2_FQ = "ILMN_R2_FQ"
CG_R1_FQ = "CG_R1_FQ"
CG_R2_FQ = "CG_R2_FQ"
PACBIO_R1_FQ = "PACBIO_R1_FQ"
PACBIO_R2_FQ = "PACBIO_R2_FQ"
ONT_R1_FQ = "ONT_R1_FQ"
ONT_R2_FQ = "ONT_R2_FQ"
ONT_FASTQ_PREFIX = "ONT_FASTQ_PREFIX"
ONT_FLOWCELL_ID = "ONT_FLOWCELL_ID"
UG_R1_FQ = "UG_R1_FQ"
UG_R2_FQ = "UG_R2_FQ"
ULTIMA_CRAM = "ULTIMA_CRAM"
ULTIMA_CRAM_ALIGNER = "ULTIMA_CRAM_ALIGNER"
ULTIMA_CRAM_SNV_CALLER = "ULTIMA_CRAM_SNV_CALLER"
ULTIMA_SUBSAMPLE_PCT = "ULTIMA_SUBSAMPLE_PCT"
ONT_CRAM = "ONT_CRAM"
ONT_CRAM_ALIGNER = "ONT_CRAM_ALIGNER"
ONT_CRAM_SNV_CALLER = "ONT_CRAM_SNV_CALLER"
ONT_SUBSAMPLE_PCT = "ONT_SUBSAMPLE_PCT"
PB_BAM = "PB_BAM"
PB_BAM_ALIGNER = "PB_BAM_ALIGNER"
PB_BAM_SNV_CALLER = "PB_BAM_SNV_CALLER"
ONT_BAM = "ONT_BAM"
ONT_BAM_ALIGNER = "ONT_BAM_ALIGNER"
ONT_BAM_SNV_CALLER = "ONT_BAM_SNV_CALLER"
ROCHE_BAM = "ROCHE_BAM"
ROCHE_BAM_ALIGNER = "ROCHE_BAM_ALIGNER"
ROCHE_BAM_SNV_CALLER = "ROCHE_BAM_SNV_CALLER"
ROCHE_DOWNSAMPLE_RATIO = "ROCHE_DOWNSAMPLE_RATIO"
STAGE_DIRECTIVE = "STAGE_DIRECTIVE"
STAGE_TARGET = "STAGE_TARGET"
MOUNT_ID = "MOUNT_ID"
MOUNT_SOURCE_S3_URI = "MOUNT_SOURCE_S3_URI"
MOUNT_FSX_PATH = "MOUNT_FSX_PATH"
DATA_LOCALITY = "DATA_LOCALITY"
SUBSAMPLE_PCT = "SUBSAMPLE_PCT"
ILMN_TRIM_READ_LENGTH = "ILMN_TRIM_READ_LENGTH"
LONGREADTRIM_READ_LENGTH = "LONGREADTRIM_READ_LENGTH"
LONGREADTRIM_MODE = "LONGREADTRIM_MODE"
IS_POS_CTRL = "IS_POS_CTRL"
IS_NEG_CTRL = "IS_NEG_CTRL"
N_X = "N_X"
N_Y = "N_Y"
EXTERNAL_SAMPLE_ID = "EXTERNAL_SAMPLE_ID"
SAMPLEUSE = "SAMPLEUSE"
SPECIMEN_TYPE = "SPECIMEN_TYPE"
EXTERNAL_SPECIMEN_ID = "EXTERNAL_SPECIMEN_ID"
ORDER_TYPE = "ORDER_TYPE"
IDDNA_UID = "IDDNA_UID"
SPECIMEN_COMMENT = "SPECIMEN_COMMENT"
SAMPLE_COMMENT = "SAMPLE_COMMENT"
LIBRARY_COMMENT = "LIBRARY_COMMENT"
SR_VCF_PATH = "SR_VCF_PATH"
LR_VCF_PATH = "LR_VCF_PATH"
AMPLIFICATION_TYPE = "AMPLIFICATION_TYPE"
ALIGNED_REF_UID = "ALIGNED_REF_UID"
MERGE_SINGLE = "MERGE_SINGLE"
BWA_KMER = "BWA_KMER"
DEEP_MODEL = "DEEP_MODEL"

S3_MULTIPART_MIN_PART_SIZE = 5 * 1024 * 1024
MOUNT_PATH_ROOTS = ("/fsx/run_dir_mounts", "/run_dir_mounts")
SCRATCH_PATH_ROOTS = ("/fsx/scratch",)
MOUNT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
ONT_FASTQ_SHARD_RE = re.compile(
    r"^(?P<flowcell_id>[^_]+)_pass_(?P<tag>barcode[0-9]+|unclassified)_"
    r"(?P<protocol_run>[^_]+)_(?P<acquisition>[^_]+)_(?P<shard_index>[0-9]+)\.fastq\.gz$"
)
EMPTY_PATH_TOKENS = {"", "na", "none", "null"}

KEY_FIELDS = [
    RUN_ID,
    SAMPLE_ID,
    EXPERIMENT_ID,
    SAMPLE_TYPE,
    LIB_PREP,
    SEQ_VENDOR,
    SEQ_PLATFORM,
]

MANIFEST_REQUIRED_FIELDS = [
    RUN_ID,
    SAMPLE_ID,
    EXPERIMENT_ID,
    SAMPLE_TYPE,
    LIB_PREP,
    SEQ_VENDOR,
    SEQ_PLATFORM,
    LANE,
    SEQBC_ID,
]

DAYOA12_MANIFEST_REQUIRED_FIELDS = [
    SPECIMEN_ID,
    SPECIMEN_EUID,
    SAMPLEID,
    SAMPLE_EUID,
    ANALYSIS_UNIT_UID,
    LIBRARY_EUID,
    RUN_ID,
    EXPERIMENT_ID,
    SAMPLE_TYPE,
    SAMPLESOURCE,
    SPECIMEN_TYPE,
    SAMPLECLASS,
    SAMPLEUSE,
    ORDER_TYPE,
    BIOLOGICAL_SEX,
    LIB_PREP,
    SEQ_VENDOR,
    SEQ_PLATFORM,
    LANE,
    SEQBC_ID,
]

# These columns are part of the DayOA 12 schema, but their values are
# intentionally conditional.  Persisted EUIDs are required only when metadata
# enrichment or customer packaging is requested, INFLECTION_DELIVERY_ID is
# required only for Inflection delivery, and a blank ANALYSIS_UNIT_UID retains
# DayOA's established deterministic construction contract.
DAYOA12_CONDITIONALLY_REQUIRED_FIELDS = {
    SPECIMEN_EUID,
    SAMPLE_EUID,
    ANALYSIS_UNIT_UID,
    LIBRARY_EUID,
    INFLECTION_DELIVERY_ID,
}
DAYOA12_NONBLANK_REQUIRED_FIELDS = [
    field
    for field in DAYOA12_MANIFEST_REQUIRED_FIELDS
    if field not in DAYOA12_CONDITIONALLY_REQUIRED_FIELDS
]

DAYOA12_BYTE_EXACT_IDENTITY_FIELDS = (
    SPECIMEN_ID,
    SPECIMEN_EUID,
    SAMPLEID,
    SAMPLE_EUID,
    ANALYSIS_UNIT_UID,
    LIBRARY_EUID,
    INFLECTION_DELIVERY_ID,
    EXTERNAL_SPECIMEN_ID,
    EXTERNAL_SAMPLE_ID,
    IDDNA_UID,
)

RAW_SOURCE_SPECS = (
    (ILMN_R1_FQ, ILMN_R2_FQ, "ILMN_R1_PATH", "ILMN_R2_PATH"),
    (CG_R1_FQ, CG_R2_FQ, "ILMN_R1_PATH", "ILMN_R2_PATH"),
    (PACBIO_R1_FQ, PACBIO_R2_FQ, "PACBIO_R1_PATH", "PACBIO_R2_PATH"),
    (ONT_R1_FQ, ONT_R2_FQ, "ONT_R1_PATH", "ONT_R2_PATH"),
    (UG_R1_FQ, UG_R2_FQ, "UG_R1_PATH", "UG_R2_PATH"),
)

ALIGNED_SOURCE_FIELDS = (
    ULTIMA_CRAM,
    ONT_CRAM,
    PB_BAM,
    ONT_BAM,
    ROCHE_BAM,
)

MOUNTED_READONLY_SOURCE_FIELDS = {
    field for raw_spec in RAW_SOURCE_SPECS for field in raw_spec[:2]
} | set(ALIGNED_SOURCE_FIELDS)

MANIFEST_UNITS_PASSTHROUGH_FIELDS = [
    SAMPLEUSE,
    BWA_KMER,
    DEEP_MODEL,
    ILMN_TRIM_READ_LENGTH,
    LONGREADTRIM_READ_LENGTH,
    LONGREADTRIM_MODE,
    ULTIMA_CRAM_ALIGNER,
    ULTIMA_CRAM_SNV_CALLER,
    ULTIMA_SUBSAMPLE_PCT,
    ONT_CRAM_ALIGNER,
    ONT_CRAM_SNV_CALLER,
    ONT_SUBSAMPLE_PCT,
    PB_BAM_ALIGNER,
    PB_BAM_SNV_CALLER,
    ONT_BAM_ALIGNER,
    ONT_BAM_SNV_CALLER,
    ROCHE_BAM_ALIGNER,
    ROCHE_BAM_SNV_CALLER,
    ROCHE_DOWNSAMPLE_RATIO,
]

ALLOWED_MANIFEST_FIELDS = {
    *MANIFEST_REQUIRED_FIELDS,
    SAMPLESOURCE,
    SAMPLECLASS,
    BIOLOGICAL_SEX,
    TUM_NRM_SAMPLEID_MATCH,
    PATH_TO_CONCORDANCE,
    CONCORDANCE_CONTROL_PATH,
    TRUTH_DATA_DIR,
    R1_FQ,
    R2_FQ,
    ILMN_R1_FQ,
    ILMN_R2_FQ,
    CG_R1_FQ,
    CG_R2_FQ,
    PACBIO_R1_FQ,
    PACBIO_R2_FQ,
    ONT_R1_FQ,
    ONT_R2_FQ,
    ONT_FASTQ_PREFIX,
    ONT_FLOWCELL_ID,
    UG_R1_FQ,
    UG_R2_FQ,
    ULTIMA_CRAM,
    ULTIMA_CRAM_ALIGNER,
    ULTIMA_CRAM_SNV_CALLER,
    ULTIMA_SUBSAMPLE_PCT,
    ONT_CRAM,
    ONT_CRAM_ALIGNER,
    ONT_CRAM_SNV_CALLER,
    ONT_SUBSAMPLE_PCT,
    PB_BAM,
    PB_BAM_ALIGNER,
    PB_BAM_SNV_CALLER,
    ONT_BAM,
    ONT_BAM_ALIGNER,
    ONT_BAM_SNV_CALLER,
    ROCHE_BAM,
    ROCHE_BAM_ALIGNER,
    ROCHE_BAM_SNV_CALLER,
    ROCHE_DOWNSAMPLE_RATIO,
    STAGE_DIRECTIVE,
    STAGE_TARGET,
    MOUNT_ID,
    MOUNT_SOURCE_S3_URI,
    MOUNT_FSX_PATH,
    DATA_LOCALITY,
    SUBSAMPLE_PCT,
    ILMN_TRIM_READ_LENGTH,
    LONGREADTRIM_READ_LENGTH,
    LONGREADTRIM_MODE,
    IS_POS_CTRL,
    IS_NEG_CTRL,
    N_X,
    N_Y,
    EXTERNAL_SAMPLE_ID,
    SAMPLEUSE,
    BWA_KMER,
    DEEP_MODEL,
    SAMPLEID,
    SPECIMEN_ID,
    SPECIMEN_EUID,
    SAMPLE_EUID,
    ANALYSIS_UNIT_UID,
    LIBRARY_EUID,
    INFLECTION_DELIVERY_ID,
    SPECIMEN_TYPE,
    EXTERNAL_SPECIMEN_ID,
    ORDER_TYPE,
    IDDNA_UID,
    SPECIMEN_COMMENT,
    SAMPLE_COMMENT,
    LIBRARY_COMMENT,
    SR_VCF_PATH,
    LR_VCF_PATH,
    AMPLIFICATION_TYPE,
    ALIGNED_REF_UID,
    MERGE_SINGLE,
}

LEGACY_SOURCE_ALIASES = {
    R1_FQ: ILMN_R1_FQ,
    R2_FQ: ILMN_R2_FQ,
}

UNITS_HEADER = [
    "RUNID",
    "SAMPLEID",
    "EXPERIMENTID",
    "LANEID",
    "BARCODEID",
    "LIBPREP",
    "SEQ_VENDOR",
    "SEQ_PLATFORM",
    "ILMN_R1_PATH",
    "ILMN_R2_PATH",
    "PACBIO_R1_PATH",
    "PACBIO_R2_PATH",
    "ONT_R1_PATH",
    "ONT_R2_PATH",
    "UG_R1_PATH",
    "UG_R2_PATH",
    "SUBSAMPLE_PCT",
    ILMN_TRIM_READ_LENGTH,
    "SAMPLEUSE",
    "BWA_KMER",
    "DEEP_MODEL",
    ULTIMA_CRAM,
    ULTIMA_CRAM_ALIGNER,
    ULTIMA_CRAM_SNV_CALLER,
    ONT_CRAM,
    ONT_CRAM_ALIGNER,
    ONT_CRAM_SNV_CALLER,
    PB_BAM,
    PB_BAM_ALIGNER,
    PB_BAM_SNV_CALLER,
    ROCHE_BAM,
    ROCHE_BAM_ALIGNER,
    ROCHE_BAM_SNV_CALLER,
    ROCHE_DOWNSAMPLE_RATIO,
    LONGREADTRIM_READ_LENGTH,
    LONGREADTRIM_MODE,
    ULTIMA_SUBSAMPLE_PCT,
    ONT_SUBSAMPLE_PCT,
    ONT_BAM,
    ONT_BAM_ALIGNER,
    ONT_BAM_SNV_CALLER,
]

SPECIMENS_HEADER = [
    SPECIMEN_ID,
    SPECIMEN_EUID,
    SAMPLESOURCE,
    SPECIMEN_TYPE,
    EXTERNAL_SPECIMEN_ID,
    BIOLOGICAL_SEX,
    N_X,
    N_Y,
    SPECIMEN_COMMENT,
]

DAYOA12_SAMPLES_HEADER = [
    SAMPLEID,
    SAMPLE_EUID,
    SPECIMEN_ID,
    SAMPLECLASS,
    SAMPLE_TYPE,
    SAMPLEUSE,
    ORDER_TYPE,
    "CONCORDANCE_CONTROL_PATH",
    "IS_POSITIVE_CONTROL",
    "IS_NEGATIVE_CONTROL",
    TUM_NRM_SAMPLEID_MATCH,
    EXTERNAL_SAMPLE_ID,
    IDDNA_UID,
    TRUTH_DATA_DIR,
    SAMPLE_COMMENT,
]

LIBRARIES_HEADER = [
    ANALYSIS_UNIT_UID,
    LIBRARY_EUID,
    INFLECTION_DELIVERY_ID,
    *[column for column in UNITS_HEADER if column != SAMPLEUSE],
    "SR_VCF_PATH",
    "LR_VCF_PATH",
    "AMPLIFICATION_TYPE",
    "ALIGNED_REF_UID",
    "MERGE_SINGLE",
    LIBRARY_COMMENT,
]

SAMPLES_HEADER = [
    "SAMPLEID",
    "SAMPLESOURCE",
    "SAMPLECLASS",
    "BIOLOGICAL_SEX",
    "CONCORDANCE_CONTROL_PATH",
    "IS_POSITIVE_CONTROL",
    "IS_NEGATIVE_CONTROL",
    "SAMPLE_TYPE",
    "TUM_NRM_SAMPLEID_MATCH",
    "EXTERNAL_SAMPLE_ID",
    "N_X",
    "N_Y",
    "TRUTH_DATA_DIR",
]


class CommandError(RuntimeError):
    """Raised when an external command fails."""


@dataclass(frozen=True)
class AwsConfig:
    profile: str
    region: Optional[str]


@dataclass
class StagePaths:
    remote_fsx_root: str
    remote_stage_name: str
    remote_fsx_stage: str
    remote_s3_stage: str


@dataclass(frozen=True)
class SampleMetadata:
    sample_id: str
    sample_type: str
    sample_source: str
    sample_class: str
    biological_sex: str
    path_to_concordance: str
    is_pos_ctrl: str
    is_neg_ctrl: str
    tum_nrm_sampleid_match: str
    n_x: str
    n_y: str
    external_sample_id: str
    specimen_id: str = ""
    specimen_euid: str = ""
    sample_euid: str = ""
    specimen_type: str = ""
    external_specimen_id: str = ""
    sample_use: str = ""
    order_type: str = ""
    iddna_uid: str = ""
    specimen_comment: str = ""
    sample_comment: str = ""


@dataclass(frozen=True)
class UnitMetadata:
    run_id: str
    experiment_id: str
    lib_prep: str
    seq_vendor: str
    seq_platform: str
    lane: str
    seqbc_id: str
    analysis_unit_uid: str = ""
    library_euid: str = ""
    inflection_delivery_id: str = ""
    library_comment: str = ""


@dataclass(frozen=True)
class StagingOptions:
    stage_directive: str
    stage_target: str
    subsample_pct: str


@dataclass(frozen=True)
class ManifestRow:
    sample: SampleMetadata
    unit: UnitMetadata
    staging: StagingOptions
    sources: Mapping[str, str]
    units_passthrough: Mapping[str, str]
    original: Mapping[str, str]
    row_number: int = 0
    manifest_contract: str = "legacy_v11"


@dataclass(frozen=True)
class S3ObjectSummary:
    uri: str
    key: str
    size: int


@dataclass(frozen=True)
class OntFastqShard:
    uri: str
    key: str
    size: int
    filename: str
    flowcell_id: str
    run_id: str
    tag: str
    shard_index: int
    gzip_compressed: bool


@dataclass(frozen=True)
class OntFastqPrefixPlan:
    prefix: str
    tag: str
    flowcell_id: str
    run_id: str
    shards: Tuple[OntFastqShard, ...]
    gzip_compressed: bool


@dataclass(frozen=True)
class PrecheckIssue:
    row_number: int
    sample_id: str
    run_id: str
    field: str
    path: str
    message: str


@dataclass(frozen=True)
class PrecheckReport:
    rows_checked: int
    samples_checked: int
    source_objects_checked: int
    concordance_dirs_checked: int
    issues: Tuple[PrecheckIssue, ...]


@dataclass(frozen=True)
class RunMetricStagingSpec:
    run_uid: str
    platform: str
    fofn: Path


@dataclass(frozen=True)
class RunMetricFile:
    spec: RunMetricStagingSpec
    source: str
    destination_relative_path: str


@dataclass(frozen=True)
class S3RoleUris:
    reference_s3_uri: str
    control_data_s3_uri: str = ""
    stage_s3_uri: str = ""
    fsx_s3_uri_maps: Tuple[Tuple[str, str], ...] = ()


GIAB_TRUTH_SUFFIXES = (".bed", ".vcf.gz", ".vcf.gz.tbi")
ACTIVE_EXTERNAL_STAGE_ROOT = "/fsx/staging/staged_external_sequencing_data"
RETIRED_STAGE_ROOTS = (
    "/fsx/staging/staged_sample_data",
    "/fsx/staging/staged",
    "/fsx/staged_sample_data",
    "/fsx/staged",
)


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Stage analysis samples into FSx from the local workstation.",
    )
    parser.add_argument("analysis_samples", help="Path to analysis_samples.tsv")
    parser.add_argument(
        "--manifest-contract",
        choices=("legacy_v11", "dayoa12"),
        default="legacy_v11",
        help=(
            "Explicit generated-manifest contract. dayoa12 requires persisted lineage "
            "identifiers and writes specimens.tsv, samples.tsv, and libraries.tsv; "
            "legacy_v11 is only for commands explicitly pinned before DayOA 12."
        ),
    )
    parser.add_argument(
        "--stage-target",
        default=ACTIVE_EXTERNAL_STAGE_ROOT,
        help="FSx staging base directory (default: %(default)s)",
    )
    parser.add_argument(
        "--reference-s3-uri",
        required=True,
        help="S3 URI (s3://bucket[/prefix]) mapped to /fsx/references and /fsx/data",
    )
    parser.add_argument(
        "--control-data-s3-uri",
        required=True,
        help="S3 URI (s3://bucket[/prefix]) mapped to /fsx/control_data",
    )
    parser.add_argument(
        "--stage-s3-uri",
        required=True,
        help=(
            "S3 URI (s3://bucket[/prefix]) used as the exact root for external "
            "staging remote_stage_* prefixes"
        ),
    )
    parser.add_argument(
        "--fsx-s3-uri-map",
        action="append",
        default=[],
        metavar="/fsx/prefix=s3://bucket/prefix",
        help=(
            "Explicit FSx-to-S3 mapping for mounted read-only subpaths. "
            "Can be specified multiple times; longest prefix wins."
        ),
    )
    parser.add_argument(
        "--config-dir",
        help=(
            "Directory for generated manifests (default: TSV dir). dayoa12 writes "
            "specimens.tsv, samples.tsv, and libraries.tsv; legacy_v11 writes "
            "samples.tsv and units.tsv."
        ),
    )
    parser.add_argument(
        "--profile",
        default=os.environ.get("AWS_PROFILE"),
        help="AWS CLI profile to use (default: $AWS_PROFILE)",
    )
    parser.add_argument(
        "--region",
        default=os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION"),
        help="AWS region to use for CLI commands (defaults to environment)",
    )
    parser.add_argument(
        "--cluster",
        "--cluster-name",
        dest="cluster_name",
        help="ParallelCluster name for creating the staged-prefix FSx DRA.",
    )
    parser.add_argument(
        "--fsx-file-system-id",
        help="FSx file system id for creating the staged-prefix DRA without resolving a cluster.",
    )
    parser.add_argument(
        "--staging-mount-timeout-seconds",
        type=int,
        default=900,
        help="Seconds to wait for the staged-prefix DRA to become available.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Print AWS CLI commands before execution",
    )
    parser.add_argument(
        "--precheck-only",
        action="store_true",
        help="Validate the manifest and exit without staging or writing generated configs.",
    )
    parser.add_argument(
        "--config-only",
        action="store_true",
        help=(
            "Validate the manifest and write generated manifests locally without "
            "uploading a remote stage or creating a staged-prefix DRA. All sample inputs must "
            "use pass_through or mounted_readonly."
        ),
    )
    parser.add_argument(
        "--run-metric-staging",
        action="append",
        default=[],
        metavar="RUN_UID:PLATFORM:FOFN",
        help=(
            "Copy run-level metric files listed in FOFN under runs/<RUN_UID>/ in the "
            "remote stage. Can be specified multiple times."
        ),
    )
    return parser.parse_args(argv)


def ensure_profile(profile: Optional[str]) -> str:
    if not profile:
        raise CommandError("AWS profile is required. Set AWS_PROFILE or pass --profile.")
    return profile


def parse_s3_uri(uri: str) -> Tuple[str, str]:
    if not uri.startswith("s3://"):
        raise CommandError(f"Expected an s3:// URI, received: {uri}")
    without_scheme = uri[5:]
    if "/" in without_scheme:
        bucket, key = without_scheme.split("/", 1)
    else:
        bucket, key = without_scheme, ""
    return bucket, key


def normalise_stage_target(stage_target: str) -> str:
    stage_target = stage_target.strip()
    if stage_target == "/data" or stage_target.startswith("/data/"):
        raise CommandError("Stage target must use /fsx/staging; /data is not supported.")
    if stage_target == "/fsx/data" or stage_target.startswith("/fsx/data/"):
        raise CommandError("Stage target must use /fsx/staging; /fsx/data is not supported.")
    reject_retired_stage_path(stage_target)
    if not (stage_target == "/fsx/staging" or stage_target.startswith("/fsx/staging/")):
        raise CommandError("Stage target must be under /fsx/staging.")
    stage_target = stage_target.rstrip("/")
    if not (
        stage_target == ACTIVE_EXTERNAL_STAGE_ROOT
        or stage_target.startswith(f"{ACTIVE_EXTERNAL_STAGE_ROOT}/")
    ):
        raise CommandError(
            f"Stage target must be under {ACTIVE_EXTERNAL_STAGE_ROOT}; "
            "other /fsx/staging subpaths are not supported for external sequencing data."
        )
    return stage_target


def build_stage_paths(stage_target: str, bucket_uri: str) -> StagePaths:
    stage_target = normalise_stage_target(stage_target)
    timestamp = dt.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    remote_stage_name = f"remote_stage_{timestamp}_{uuid.uuid4().hex[:8]}"
    remote_fsx_stage = f"{stage_target}/{remote_stage_name}"

    bucket, prefix = parse_s3_uri(bucket_uri.rstrip("/"))
    prefix = prefix.rstrip("/")
    stage_root_uri = f"s3://{bucket}/{prefix}" if prefix else f"s3://{bucket}"
    remote_s3_stage = _join_s3_uri(stage_root_uri, remote_stage_name)
    return StagePaths(
        remote_fsx_root=stage_target,
        remote_stage_name=remote_stage_name,
        remote_fsx_stage=remote_fsx_stage,
        remote_s3_stage=remote_s3_stage,
    )


def create_staged_prefix_mount(
    stage: StagePaths,
    *,
    cluster_name: Optional[str],
    fsx_file_system_id: Optional[str],
    profile: Optional[str],
    region: Optional[str],
    timeout_seconds: int,
):
    """Attach only the staged remote prefix as a runtime staging DRA."""
    if not cluster_name and not fsx_file_system_id:
        return None
    if not region:
        raise CommandError("AWS region is required to create the staged-prefix DRA.")
    if timeout_seconds <= 0:
        raise CommandError("--staging-mount-timeout-seconds must be positive.")
    file_system_path = stage.remote_fsx_stage.removeprefix("/fsx")
    from daylily_ec import run_mounts

    try:
        return run_mounts.create_run_mount(
            run_mounts.CreateRunMountRequest(
                cluster_name=cluster_name,
                fsx_file_system_id=fsx_file_system_id,
                region=region,
                profile=profile,
                source_s3_uri=stage.remote_s3_stage,
                mount_id=stage.remote_stage_name,
                run_id=stage.remote_stage_name,
                purpose=run_mounts.MOUNT_PURPOSE_STAGING,
                platform="STAGING",
                file_system_path=file_system_path,
                read_only=True,
                batch_import_metadata_on_create=True,
                auto_import_events=(),
                wait=False,
                timeout_seconds=timeout_seconds,
                tags={"daylily:staging-root": ACTIVE_EXTERNAL_STAGE_ROOT},
            )
        )
    except run_mounts.RunMountError as exc:
        raise CommandError(f"Unable to create staged-prefix FSx DRA: {exc}") from exc


def headnode_visible_path(path: str) -> str:
    if path == "/data" or path.startswith("/data/"):
        raise CommandError("The /fsx/data namespace is not supported; use explicit role roots.")
    reject_retired_stage_path(path)
    return path


def is_retired_stage_path(path: str) -> bool:
    return any(path == root or path.startswith(f"{root}/") for root in RETIRED_STAGE_ROOTS)


def reject_retired_stage_path(path: str) -> None:
    if is_retired_stage_path(path):
        raise CommandError(
            f"The retired staging path {path} is not supported; "
            f"use {ACTIVE_EXTERNAL_STAGE_ROOT} for external sequencing staging."
        )


def is_mounted_run_dir_path(path: str) -> bool:
    return any(path == root or path.startswith(f"{root}/") for root in MOUNT_PATH_ROOTS)


def validate_mount_id(value: str) -> str:
    mount_id = (value or "").strip()
    if not mount_id:
        raise CommandError(f"{MOUNT_ID} is required for STAGE_DIRECTIVE=mounted_readonly.")
    if mount_id in {".", ".."} or not MOUNT_ID_RE.fullmatch(mount_id):
        raise CommandError(
            f"{MOUNT_ID} must be a safe path component containing only letters, numbers, "
            f"underscore, dash, or dot: {value}"
        )
    return mount_id


def parse_mounted_run_dir_path(path: str, *, field: str) -> Tuple[str, str, Tuple[str, ...]]:
    for root in MOUNT_PATH_ROOTS:
        if path != root and not path.startswith(f"{root}/"):
            continue
        relative = path[len(root) :]
        if relative.startswith("/"):
            relative = relative[1:]
        if relative.endswith("/"):
            relative = relative[:-1]
        parts = tuple(relative.split("/")) if relative else ()
        if not parts:
            raise CommandError(
                f"{field} must include {MOUNT_ID} under /fsx/run_dir_mounts/ "
                f"or /run_dir_mounts/: {path}"
            )
        if any(part in {"", ".", ".."} for part in parts):
            raise CommandError(
                f"{field} mounted path must not contain empty, '.', or '..' components: {path}"
            )
        mount_id = validate_mount_id(parts[0])
        return root, mount_id, parts[1:]
    raise CommandError(
        f"{field} must be under /fsx/run_dir_mounts/<{MOUNT_ID}>/ "
        f"or /run_dir_mounts/<{MOUNT_ID}>/: {path}"
    )


def require_mounted_source_path(path: str, *, field: str, expected_mount_id: str) -> None:
    _root, actual_mount_id, relative_parts = parse_mounted_run_dir_path(path, field=field)
    if actual_mount_id != expected_mount_id:
        raise CommandError(
            f"{field} uses mount ID {actual_mount_id}, but {MOUNT_ID} is {expected_mount_id}: {path}"
        )
    if not relative_parts or path.endswith("/"):
        raise CommandError(
            f"{field} must name a file below the mount root for {MOUNT_ID}={expected_mount_id}: {path}"
        )


def require_mounted_root_path(path: str, *, expected_mount_id: str) -> None:
    _root, actual_mount_id, relative_parts = parse_mounted_run_dir_path(path, field=MOUNT_FSX_PATH)
    if actual_mount_id != expected_mount_id:
        raise CommandError(
            f"{MOUNT_FSX_PATH} uses mount ID {actual_mount_id}, "
            f"but {MOUNT_ID} is {expected_mount_id}: {path}"
        )
    if relative_parts:
        raise CommandError(f"{MOUNT_FSX_PATH} must be the mount root, not a child path: {path}")


def build_aws_env(config: AwsConfig) -> Dict[str, str]:
    env = dict(os.environ)
    env["AWS_PROFILE"] = config.profile
    if config.region:
        env["AWS_REGION"] = config.region
        env.setdefault("AWS_DEFAULT_REGION", config.region)
    return env


def run_command(
    command: Sequence[str],
    *,
    env: Optional[Dict[str, str]] = None,
    check: bool = True,
    capture_output: bool = False,
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            list(command),
            env=env,
            check=check,
            text=True,
            capture_output=capture_output,
        )
    except subprocess.CalledProcessError as exc:  # pragma: no cover - runtime path
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        message = f"Command failed ({exc.returncode}): {' '.join(command)}"
        if stdout:
            message += f"\nSTDOUT:\n{stdout.strip()}"
        if stderr:
            message += f"\nSTDERR:\n{stderr.strip()}"
        raise CommandError(message) from exc


def aws_command(
    args: Sequence[str],
    *,
    aws_env: Dict[str, str],
    debug: bool = False,
    capture_output: bool = False,
) -> subprocess.CompletedProcess[str]:
    command = ["aws", *args]
    if debug:
        print("[DEBUG]", " ".join(command))
    return run_command(command, env=aws_env, capture_output=capture_output)


def aws_command_binary_to_handle(
    args: Sequence[str],
    handle,
    *,
    aws_env: Dict[str, str],
    debug: bool = False,
) -> None:
    command = ["aws", *args]
    if debug:
        print("[DEBUG]", " ".join(command))
    try:
        with subprocess.Popen(
            command,
            env=aws_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        ) as proc:
            assert proc.stdout is not None
            shutil.copyfileobj(proc.stdout, handle)
            _stdout, stderr = proc.communicate()
            if proc.returncode != 0:
                message = f"Command failed ({proc.returncode}): {' '.join(command)}"
                if stderr:
                    message += f"\nSTDERR:\n{stderr.decode(errors='replace').strip()}"
                raise CommandError(message)
    except OSError as exc:  # pragma: no cover - runtime path
        raise CommandError(f"Command failed: {' '.join(command)}\n{exc}") from exc


def check_local_path(path: str, *, allow_directory: bool = False) -> None:
    expanded = os.path.expanduser(path)
    if allow_directory and os.path.isdir(expanded):
        return
    if not os.path.exists(expanded):
        raise CommandError(f"Local path not found: {path}")


def check_s3_path(
    uri: str,
    *,
    aws_env: Dict[str, str],
    debug: bool,
) -> None:
    args = ["s3", "ls", uri]
    result = aws_command(args, aws_env=aws_env, debug=debug, capture_output=True)
    if not result.stdout.strip():
        raise CommandError(f"S3 object or prefix not accessible: {uri}")


def normalise_s3_prefix_uri(uri: str) -> str:
    bucket, key = parse_s3_uri(uri)
    key = key.strip("/")
    if key:
        return f"s3://{bucket}/{key}/"
    return f"s3://{bucket}/"


def list_s3_objects(
    prefix_uri: str,
    *,
    aws_env: Dict[str, str],
    debug: bool,
) -> List[S3ObjectSummary]:
    bucket, prefix = parse_s3_uri(normalise_s3_prefix_uri(prefix_uri))
    objects: List[S3ObjectSummary] = []
    continuation_token: Optional[str] = None
    while True:
        args = ["s3api", "list-objects-v2", "--bucket", bucket, "--prefix", prefix]
        if continuation_token:
            args.extend(["--continuation-token", continuation_token])
        result = aws_command(args, aws_env=aws_env, debug=debug, capture_output=True)
        payload = json.loads(result.stdout or "{}")
        for item in payload.get("Contents", []):
            if not isinstance(item, dict):
                continue
            key = str(item.get("Key", ""))
            size = int(item.get("Size") or 0)
            if not key or key.endswith("/"):
                continue
            objects.append(S3ObjectSummary(uri=f"s3://{bucket}/{key}", key=key, size=size))
        if not payload.get("IsTruncated"):
            break
        continuation_token = payload.get("NextContinuationToken")
        if not continuation_token:
            raise CommandError(
                f"S3 listing for {prefix_uri} was truncated without a continuation token."
            )
    return objects


def read_s3_text(
    uri: str,
    *,
    aws_env: Dict[str, str],
    debug: bool,
) -> str:
    result = aws_command(["s3", "cp", uri, "-"], aws_env=aws_env, debug=debug, capture_output=True)
    return result.stdout or ""


def is_headnode_visible_path(path: str) -> bool:
    if is_retired_stage_path(path):
        return False
    return (
        path == "/fsx/references"
        or path.startswith("/fsx/references/")
        or path == "/fsx/data"
        or path.startswith("/fsx/data/")
        or path == "/fsx/control_data"
        or path.startswith("/fsx/control_data/")
        or path == "/fsx/staging"
        or path.startswith("/fsx/staging/")
        or is_headnode_scratch_path(path)
        or is_mounted_run_dir_path(path)
    )


def is_headnode_scratch_path(path: str) -> bool:
    return any(path == root or path.startswith(f"{root}/") for root in SCRATCH_PATH_ROOTS)


def _coerce_s3_role_uris(reference_s3_uri: str | S3RoleUris) -> S3RoleUris:
    if isinstance(reference_s3_uri, S3RoleUris):
        return reference_s3_uri
    return S3RoleUris(reference_s3_uri=str(reference_s3_uri or ""))


def _role_relative(path: str, root: str) -> str:
    if path == root:
        return ""
    return path.removeprefix(f"{root}/").lstrip("/")


def _staging_relative(path: str) -> str:
    normalised = path.rstrip("/")
    if normalised == ACTIVE_EXTERNAL_STAGE_ROOT:
        return ""
    if normalised.startswith(f"{ACTIVE_EXTERNAL_STAGE_ROOT}/"):
        return normalised.removeprefix(f"{ACTIVE_EXTERNAL_STAGE_ROOT}/")
    raise CommandError(
        f"Stage path must be under {ACTIVE_EXTERNAL_STAGE_ROOT}; "
        "other /fsx/staging subpaths are not supported."
    )


def _join_s3_uri(base: str, relative: str) -> str:
    if not base:
        raise CommandError("Missing required S3 role bucket for path resolution.")
    base = base.rstrip("/")
    relative = relative.lstrip("/")
    return f"{base}/{relative}" if relative else base


def parse_fsx_s3_uri_maps(values: Optional[Sequence[str]]) -> Tuple[Tuple[str, str], ...]:
    mappings: List[Tuple[str, str]] = []
    for raw in values or []:
        if "=" not in raw:
            raise CommandError("--fsx-s3-uri-map must use /fsx/prefix=s3://bucket/prefix syntax.")
        fsx_prefix, s3_uri = (part.strip() for part in raw.split("=", 1))
        fsx_prefix = fsx_prefix.rstrip("/")
        s3_uri = s3_uri.rstrip("/")
        if not fsx_prefix.startswith("/fsx/"):
            raise CommandError(f"--fsx-s3-uri-map FSx prefix must start with /fsx/: {raw}")
        if not s3_uri.startswith("s3://"):
            raise CommandError(f"--fsx-s3-uri-map S3 URI must start with s3://: {raw}")
        mappings.append((fsx_prefix, s3_uri))
    return tuple(sorted(mappings, key=lambda item: len(item[0]), reverse=True))


def _explicit_mapped_s3_uri(path: str, roles: S3RoleUris) -> Optional[str]:
    for fsx_prefix, s3_uri in roles.fsx_s3_uri_maps:
        if path == fsx_prefix or path.startswith(f"{fsx_prefix}/"):
            return _join_s3_uri(s3_uri, _role_relative(path, fsx_prefix))
    return None


def build_reference_uri(path: str, reference_s3_uri: str | S3RoleUris) -> str:
    roles = _coerce_s3_role_uris(reference_s3_uri)
    if is_mounted_run_dir_path(path):
        raise CommandError(
            f"Mounted run-directory paths are not static role-bucket objects: {path}"
        )
    if path == "/data" or path.startswith("/data/"):
        raise CommandError("The /fsx/data namespace is not supported; use explicit role roots.")
    if path == "/fsx/runtime_assets" or path.startswith("/fsx/runtime_assets/"):
        raise CommandError(
            "The /fsx/runtime_assets namespace is not supported; use /fsx/references/runtime_assets."
        )
    reject_retired_stage_path(path)
    explicit_uri = _explicit_mapped_s3_uri(path, roles)
    if explicit_uri:
        return explicit_uri
    if path == "/fsx/data" or path.startswith("/fsx/data/"):
        return _join_s3_uri(roles.reference_s3_uri, _role_relative(path, "/fsx/data"))
    if path == "/fsx/references" or path.startswith("/fsx/references/"):
        return _join_s3_uri(roles.reference_s3_uri, _role_relative(path, "/fsx/references"))
    if path == "/fsx/control_data" or path.startswith("/fsx/control_data/"):
        return _join_s3_uri(roles.control_data_s3_uri, _role_relative(path, "/fsx/control_data"))
    if path == "/fsx/staging" or path.startswith("/fsx/staging/"):
        return _join_s3_uri(roles.stage_s3_uri, _staging_relative(path))
    raise CommandError(f"Path is not in a DayOA FSx role namespace: {path}")


def check_source_path(
    path: str,
    *,
    reference_s3_uri: str | S3RoleUris,
    aws_env: Dict[str, str],
    debug: bool,
    allow_directory: bool = False,
) -> None:
    if not path or path.lower() == "na":
        return
    reject_retired_stage_path(path)
    if path.startswith("s3://"):
        check_s3_path(path, aws_env=aws_env, debug=debug)
        return
    if is_mounted_run_dir_path(path):
        parse_mounted_run_dir_path(path, field="source path")
        return
    if is_headnode_scratch_path(path):
        return
    if is_headnode_visible_path(path):
        check_s3_path(
            build_reference_uri(path, reference_s3_uri),
            aws_env=aws_env,
            debug=debug,
        )
        return
    check_local_path(path, allow_directory=allow_directory)


def validate_subsample_pct(value: str) -> str:
    if not value:
        return "na"
    try:
        pct = float(value)
    except ValueError:
        return "na"
    return value if 0.0 < pct < 1.0 else "na"


def ensure_remote_stage_writable(
    stage: StagePaths, *, aws_env: Dict[str, str], debug: bool
) -> None:
    with tempfile.NamedTemporaryFile("w", delete=False) as handle:
        handle.write("daylily staging write test\n")
        handle.flush()
        temp_path = handle.name
    dest = f"{stage.remote_s3_stage}/_write_test.txt"
    try:
        aws_command(["s3", "cp", temp_path, dest], aws_env=aws_env, debug=debug)
    finally:
        os.unlink(temp_path)
    aws_command(["s3", "rm", dest], aws_env=aws_env, debug=debug)


def safe_int(value: str, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def determine_sex(n_x: int, n_y: int) -> str:
    if n_x == 2 and n_y == 0:
        return "female"
    if n_x == 1 and n_y == 1:
        return "male"
    return "na"


def get_entry_value(entry: Mapping[str, str], field: str, default: str = "") -> str:
    return (entry.get(field, default) or default).strip()


def normalise_identifier(value: str) -> str:
    if "/" in value or "\\" in value:
        raise CommandError(f"Identifier fields must not contain path separators: {value}")
    return value.replace("_", "-")


def exact_source_identifier(value: str, *, field: str) -> str:
    if not value:
        raise CommandError(f"{field} must not be blank")
    if value != value.strip():
        raise CommandError(f"{field} must not have surrounding whitespace")
    if "/" in value or "\\" in value:
        raise CommandError(f"{field} must not contain path separators: {value}")
    return value


def normalise_run_id(value: str) -> str:
    return normalise_identifier(value).replace(".", "-")


def canonical_manifest_seq_vendor(value: str) -> str:
    raw = value.strip()
    if raw.upper() == "CG/MGI":
        return "CG"
    normalized = normalise_identifier(raw).upper()
    if normalized in {"COMPLETE-GENOMICS", "COMPLETEGENOMICS"}:
        return "CG"
    return normalized


def _validate_run_metric_component(value: str, *, label: str) -> None:
    if not value:
        raise CommandError(f"Run metric staging {label} is required.")
    if "/" in value or "\\" in value:
        raise CommandError(f"Run metric staging {label} must not contain path separators: {value}")


def parse_run_metric_staging_spec(value: str) -> RunMetricStagingSpec:
    parts = value.split(":", 2)
    if len(parts) != 3:
        raise CommandError(
            f"Run metric staging spec must be RUN_UID:PLATFORM:FOFN; received: {value}"
        )
    raw_run_uid, raw_platform, raw_fofn = (part.strip() for part in parts)
    run_uid = normalise_run_id(raw_run_uid)
    platform = normalise_identifier(raw_platform).upper()
    _validate_run_metric_component(run_uid, label="RUN_UID")
    _validate_run_metric_component(platform, label="PLATFORM")
    if not raw_fofn:
        raise CommandError("Run metric staging FOFN is required.")
    return RunMetricStagingSpec(
        run_uid=run_uid,
        platform=platform,
        fofn=Path(raw_fofn).expanduser(),
    )


def parse_run_metric_staging_specs(values: Sequence[str]) -> Tuple[RunMetricStagingSpec, ...]:
    return tuple(parse_run_metric_staging_spec(value) for value in values)


def _normalise_run_metric_relative_destination(path: str) -> str:
    if path.endswith("/"):
        raise CommandError(f"Run metric FOFN entry must name a file, not a directory: {path}")
    rel_path = PurePosixPath(path)
    if rel_path.is_absolute():
        raise CommandError(f"Run metric destination must be relative: {path}")
    parts = tuple(part for part in rel_path.parts if part not in {"", "."})
    if not parts:
        raise CommandError(f"Run metric FOFN entry has no destination filename: {path}")
    if any(part == ".." for part in parts):
        raise CommandError(f"Run metric FOFN entry must not contain '..': {path}")
    return "/".join(parts)


def _run_metric_source_basename(source: str) -> str:
    if source.endswith("/"):
        raise CommandError(f"Run metric source must name a file, not a directory: {source}")
    if source.startswith("s3://"):
        _bucket, key = parse_s3_uri(source)
        name = PurePosixPath(key).name
    else:
        name = Path(source).name
    if not name:
        raise CommandError(f"Run metric source has no destination filename: {source}")
    return name


def _is_fofn_relative_source(source: str) -> bool:
    if source.startswith("s3://"):
        return False
    return not Path(source).expanduser().is_absolute()


def _resolve_run_metric_file(
    spec: RunMetricStagingSpec,
    source: str,
    *,
    line_number: int,
) -> RunMetricFile:
    source = source.strip()
    if not source:
        raise CommandError(f"Run metric FOFN {spec.fofn} line {line_number} is empty.")
    if _is_fofn_relative_source(source):
        destination_relative_path = _normalise_run_metric_relative_destination(source)
        resolved_source = str((spec.fofn.parent / source).expanduser().resolve())
    else:
        destination_relative_path = _run_metric_source_basename(source)
        resolved_source = source
    return RunMetricFile(
        spec=spec,
        source=resolved_source,
        destination_relative_path=destination_relative_path,
    )


def precheck_run_metrics(
    specs: Sequence[RunMetricStagingSpec],
    *,
    reference_s3_uri: str,
    aws_env: Dict[str, str],
    debug: bool,
) -> List[RunMetricFile]:
    resolved_files: List[RunMetricFile] = []
    destinations_by_run: Dict[Tuple[str, str], str] = {}
    platforms_by_run: Dict[str, str] = {}

    for spec in specs:
        fofn = spec.fofn
        if not fofn.exists():
            raise CommandError(f"Run metric FOFN not found: {fofn}")
        if not fofn.is_file():
            raise CommandError(f"Run metric FOFN is not a file: {fofn}")

        existing_platform = platforms_by_run.get(spec.run_uid)
        if existing_platform is not None and existing_platform != spec.platform:
            raise CommandError(
                f"Run metric staging for RUN_UID={spec.run_uid} uses conflicting platforms: "
                f"{existing_platform} and {spec.platform}."
            )
        platforms_by_run.setdefault(spec.run_uid, spec.platform)

        files_for_spec = 0
        with fofn.open(encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                source = line.strip()
                if not source:
                    continue
                metric_file = _resolve_run_metric_file(
                    spec,
                    source,
                    line_number=line_number,
                )
                destination_key = (spec.run_uid, metric_file.destination_relative_path)
                existing_source = destinations_by_run.get(destination_key)
                if existing_source is not None:
                    raise CommandError(
                        f"Run metric staging for RUN_UID={spec.run_uid} maps multiple sources "
                        f"to runs/{spec.run_uid}/{metric_file.destination_relative_path}: "
                        f"{existing_source}, {metric_file.source}"
                    )
                check_source_path(
                    metric_file.source,
                    reference_s3_uri=reference_s3_uri,
                    aws_env=aws_env,
                    debug=debug,
                )
                destinations_by_run[destination_key] = metric_file.source
                resolved_files.append(metric_file)
                files_for_spec += 1
        if files_for_spec == 0:
            raise CommandError(f"Run metric FOFN contains no files: {fofn}")

    return resolved_files


def format_run_metric_precheck_success(
    specs: Sequence[RunMetricStagingSpec],
    files: Sequence[RunMetricFile],
) -> str:
    return (
        "Run metric precheck passed: "
        f"run specs checked={len(specs)}, "
        f"metric files checked={len(files)}."
    )


def canonical_manifest_libprep(value: str, *, vendor: str) -> str:
    normalized = normalise_identifier(value)
    if vendor == "ILMN" and normalized.upper() in {
        "NOAMPWGS",
        "PCRFREE",
        "PCR-FREE",
        "TRUSEQPF",
        "TRUSEQ-PF",
    }:
        return "PCR-FREE"
    return normalized


def canonical_manifest_seq_platform(value: str, *, vendor: str) -> str:
    normalized = normalise_identifier(value)
    if vendor == "ILMN" and normalized.upper() in {"NOVASEQ", "NOVASEQX"}:
        return "NOVASEQ"
    return normalized


def is_giab_control(entry: Mapping[str, str]) -> bool:
    concordance = resolve_concordance_source(entry).lower()
    return "/controls/giab/" in concordance


def resolve_positive_control(entry: Mapping[str, str]) -> str:
    raw = get_entry_value(entry, IS_POS_CTRL).lower()
    if raw in {"true", "false"}:
        return raw
    return "true" if is_giab_control(entry) else "false"


def should_precheck_giab_truth(entry: Mapping[str, str]) -> bool:
    raw = get_entry_value(entry, IS_POS_CTRL).lower()
    concordance = resolve_concordance_source(entry)
    if raw == "true":
        return is_populated_path(concordance)
    if raw == "false":
        return False
    return is_giab_control(entry)


def resolve_negative_control(entry: Mapping[str, str]) -> str:
    raw = get_entry_value(entry, IS_NEG_CTRL).lower()
    if raw in {"true", "false"}:
        return raw
    return "false"


def aws_copy(
    source: str,
    destination: str,
    *,
    aws_env: Dict[str, str],
    debug: bool,
    recursive: bool = False,
) -> None:
    args = ["s3", "cp", source, destination]
    if recursive:
        args.append("--recursive")
    aws_command(args, aws_env=aws_env, debug=debug)


def cleanup_s3_objects(uris: Sequence[str], *, aws_env: Dict[str, str], debug: bool) -> None:
    for uri in uris:
        try:
            aws_command(["s3", "rm", uri], aws_env=aws_env, debug=debug)
        except CommandError:
            pass


def source_copy_reference(source: str, *, reference_s3_uri: str) -> str:
    reject_retired_stage_path(source)
    if source.startswith("s3://"):
        return source
    if is_mounted_run_dir_path(source):
        return headnode_visible_path(source)
    if is_headnode_scratch_path(source):
        raise CommandError(
            f"Scratch source {source} is headnode-only; set {STAGE_DIRECTIVE}=pass_through."
        )
    if is_headnode_visible_path(source):
        return build_reference_uri(source, reference_s3_uri)
    return os.path.expanduser(source)


def parse_ont_fastq_prefix(prefix_uri: str) -> Tuple[str, str, str, str]:
    prefix_uri = normalise_s3_prefix_uri(prefix_uri)
    bucket, key = parse_s3_uri(prefix_uri)
    parts = [part for part in key.strip("/").split("/") if part]
    if len(parts) < 2 or parts[-2] != "fastq_pass" or not parts[-1]:
        raise CommandError(
            f"{ONT_FASTQ_PREFIX} must point to an S3 fastq_pass/<tag>/ prefix: {prefix_uri}"
        )
    run_id_candidates = [part for part in parts[:-2] if re.match(r"^[0-9]{8}_ONT(?:_|$)", part)]
    if not run_id_candidates:
        raise CommandError(
            f"{ONT_FASTQ_PREFIX} must be under an ONT run directory like YYYYMMDD_ONT_*: {prefix_uri}"
        )
    run_output_key = "/".join(parts[:-2])
    return (
        prefix_uri,
        normalise_identifier(parts[-1]),
        normalise_run_id(run_id_candidates[-1]),
        f"s3://{bucket}/{run_output_key}/",
    )


def _strip_fastq_suffix(filename: str) -> Tuple[str, bool]:
    match = re.match(r"^(?P<stem>.+)\.(?P<ext>fastq|fq)(?P<gz>\.gz)?$", filename)
    if not match:
        raise CommandError(f"ONT shard filename is not FASTQ: {filename}")
    return match.group("stem"), bool(match.group("gz"))


def parse_ont_fastq_shard(
    obj: S3ObjectSummary,
    *,
    expected_tag: str,
    run_id: str,
) -> OntFastqShard:
    filename = os.path.basename(obj.key)
    _stem, gzip_compressed = _strip_fastq_suffix(filename)
    match = ONT_FASTQ_SHARD_RE.match(filename)
    if not match:
        raise CommandError(
            f"Could not parse ONT shard filename {filename}; expected "
            "<flowcell>_pass_<tag>_<protocol-run>_<acquisition>_<shard>.fastq.gz."
        )
    shard_tag = normalise_identifier(match.group("tag"))
    if shard_tag != expected_tag:
        raise CommandError(
            f"ONT shard {filename} belongs to tag {shard_tag}, not prefix tag {expected_tag}."
        )
    return OntFastqShard(
        uri=obj.uri,
        key=obj.key,
        size=obj.size,
        filename=filename,
        flowcell_id=normalise_identifier(match.group("flowcell_id")),
        run_id=run_id,
        tag=shard_tag,
        shard_index=int(match.group("shard_index")),
        gzip_compressed=gzip_compressed,
    )


def parse_key_value_text(text: str) -> Dict[str, str]:
    values: Dict[str, str] = {}
    for line in text.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def validate_ont_run_output(
    run_output_prefix: str,
    *,
    flowcell_id: str,
    aws_env: Dict[str, str],
    debug: bool,
) -> None:
    objects = list_s3_objects(run_output_prefix, aws_env=aws_env, debug=debug)
    if not objects:
        raise CommandError(f"ONT run output prefix is empty: {run_output_prefix}")

    keys = [obj.key for obj in objects]
    basenames = {os.path.basename(key) for key in keys}
    required_markers = {
        "fastq_pass/": "fastq_pass",
        "pod5_pass/": "pod5_pass",
    }
    for marker, label in required_markers.items():
        if not any(marker in key for key in keys):
            raise CommandError(f"ONT run output {run_output_prefix} is missing {label} data.")

    final_summaries = [
        obj
        for obj in objects
        if os.path.basename(obj.key).startswith("final_summary_")
        and os.path.basename(obj.key).endswith(".txt")
    ]
    sample_sheets = [name for name in basenames if name.startswith("sample_sheet_")]
    sequencing_summaries = [name for name in basenames if name.startswith("sequencing_summary_")]
    reports = [name for name in basenames if name.startswith("report_")]
    if not final_summaries:
        raise CommandError(f"ONT run output {run_output_prefix} is missing final_summary_*.txt.")
    if not sample_sheets:
        raise CommandError(f"ONT run output {run_output_prefix} is missing sample_sheet_*.")
    if not sequencing_summaries:
        raise CommandError(f"ONT run output {run_output_prefix} is missing sequencing_summary_*.")
    if not reports:
        raise CommandError(f"ONT run output {run_output_prefix} is missing report_* outputs.")

    matching_summaries = [
        obj for obj in final_summaries if flowcell_id in os.path.basename(obj.key)
    ]
    if not matching_summaries:
        raise CommandError(
            f"ONT run output {run_output_prefix} has no final summary for flowcell {flowcell_id}."
        )
    summary = parse_key_value_text(
        read_s3_text(matching_summaries[0].uri, aws_env=aws_env, debug=debug)
    )
    summary_flowcell = summary.get("flow_cell_id", "")
    if summary_flowcell and normalise_identifier(summary_flowcell) != flowcell_id:
        raise CommandError(
            f"ONT final summary flow_cell_id={summary_flowcell} does not match {flowcell_id}."
        )
    if summary.get("basecalling_enabled") not in {"1", "true", "True"}:
        raise CommandError(
            f"ONT final summary for {flowcell_id} does not show basecalling enabled."
        )
    if safe_int(summary.get("fastq_files_in_final_dest", "0")) <= 0:
        raise CommandError(f"ONT final summary for {flowcell_id} reports no delivered FASTQs.")
    observed_fastqs = sum(
        1
        for key in keys
        if ("/fastq_pass/" in key or "/fastq_fail/" in key)
        and os.path.basename(key).startswith(f"{flowcell_id}_")
        and os.path.basename(key).endswith(".fastq.gz")
    )
    expected_fastqs = safe_int(summary.get("fastq_files_in_final_dest", "0"))
    if observed_fastqs != expected_fastqs:
        raise CommandError(
            f"ONT final summary for {flowcell_id} reports {expected_fastqs} FASTQs, "
            f"but S3 contains {observed_fastqs}."
        )
    if "pod5_files_in_final_dest" in summary:
        observed_pod5 = sum(
            1
            for key in keys
            if ("/pod5_pass/" in key or "/pod5_fail/" in key)
            and os.path.basename(key).startswith(f"{flowcell_id}_")
            and os.path.basename(key).endswith(".pod5")
        )
        expected_pod5 = safe_int(summary.get("pod5_files_in_final_dest", "0"))
        if observed_pod5 != expected_pod5:
            raise CommandError(
                f"ONT final summary for {flowcell_id} reports {expected_pod5} POD5 files, "
                f"but S3 contains {observed_pod5}."
            )
    for field in ("fallback_fastq_files_in_final_dest", "fallback_pod5_files_in_final_dest"):
        if field in summary and safe_int(summary[field]) != 0:
            raise CommandError(
                f"ONT final summary for {flowcell_id} reports {field}={summary[field]}."
            )


def resolve_ont_fastq_prefix_plan(
    prefix_uri: str,
    *,
    flowcell_id: str,
    aws_env: Dict[str, str],
    debug: bool,
) -> OntFastqPrefixPlan:
    prefix_uri, tag, run_id, run_output_prefix = parse_ont_fastq_prefix(prefix_uri)
    objects = list_s3_objects(prefix_uri, aws_env=aws_env, debug=debug)
    if not objects:
        raise CommandError(f"No ONT FASTQ shards found under {prefix_uri}")
    zero_byte_objects = [os.path.basename(obj.key) for obj in objects if obj.size == 0]
    if zero_byte_objects:
        raise CommandError(
            f"{ONT_FASTQ_PREFIX} {prefix_uri} contains zero-byte objects: "
            + ", ".join(sorted(zero_byte_objects))
        )
    fastq_objects = [obj for obj in objects if obj.key.endswith(".fastq.gz")]
    if len(fastq_objects) != len(objects):
        unexpected = sorted(
            os.path.basename(obj.key) for obj in objects if obj not in fastq_objects
        )
        raise CommandError(
            f"{ONT_FASTQ_PREFIX} {prefix_uri} contains non-FASTQ objects: {', '.join(unexpected)}"
        )
    shards = [parse_ont_fastq_shard(obj, expected_tag=tag, run_id=run_id) for obj in fastq_objects]

    flowcells = sorted({shard.flowcell_id for shard in shards})
    requested_flowcell = normalise_identifier(flowcell_id) if flowcell_id else ""
    if len(flowcells) > 1 and not requested_flowcell:
        raise CommandError(
            f"{ONT_FASTQ_PREFIX} {prefix_uri} contains multiple flowcells "
            f"({', '.join(flowcells)}); populate {ONT_FLOWCELL_ID} explicitly."
        )
    if requested_flowcell:
        selected = [shard for shard in shards if shard.flowcell_id == requested_flowcell]
        if not selected:
            raise CommandError(
                f"{ONT_FLOWCELL_ID}={requested_flowcell} did not match any FASTQ shards under {prefix_uri}."
            )
    else:
        selected = shards

    selected_tags = sorted({shard.tag for shard in selected})
    if selected_tags != [tag]:
        raise CommandError(
            f"{ONT_FASTQ_PREFIX} {prefix_uri} must resolve to one tag; found {', '.join(selected_tags)}."
        )
    compression_modes = sorted({shard.gzip_compressed for shard in selected})
    if len(compression_modes) != 1:
        raise CommandError(f"ONT FASTQ shards under {prefix_uri} mix gzip and plain FASTQ files.")

    selected = sorted(selected, key=lambda shard: (shard.shard_index, shard.filename))
    shard_indexes = [shard.shard_index for shard in selected]
    expected_indexes = list(range(0, len(selected)))
    if shard_indexes != expected_indexes:
        raise CommandError(
            f"ONT FASTQ shard indexes under {prefix_uri} must be contiguous from 0; "
            f"found {', '.join(str(index) for index in shard_indexes)}."
        )
    validate_ont_run_output(
        run_output_prefix,
        flowcell_id=selected[0].flowcell_id,
        aws_env=aws_env,
        debug=debug,
    )

    return OntFastqPrefixPlan(
        prefix=prefix_uri,
        tag=tag,
        flowcell_id=selected[0].flowcell_id,
        run_id=run_id,
        shards=tuple(selected),
        gzip_compressed=compression_modes[0],
    )


def require_headnode_visible_path(path: str, *, field: str) -> None:
    reject_retired_stage_path(path)
    if is_headnode_visible_path(path):
        return
    raise CommandError(
        f"{field} uses {path}, which is not headnode-visible. "
        "Use STAGE_DIRECTIVE=stage_data to copy it into the remote stage."
    )


def ensure_s3_objects(
    sources: Sequence[str],
    *,
    dest_s3_dir: str,
    sample_prefix: str,
    reference_s3_uri: str,
    aws_env: Dict[str, str],
    debug: bool,
) -> Tuple[List[str], List[str]]:
    uploaded: List[str] = []
    resolved: List[str] = []
    try:
        for idx, source in enumerate(sources, start=1):
            if source.startswith("s3://"):
                resolved.append(source)
                continue
            if is_headnode_visible_path(source):
                resolved.append(build_reference_uri(source, reference_s3_uri))
                continue
            expanded = os.path.expanduser(source)
            part_name = f"{sample_prefix}_part{idx}_{uuid.uuid4().hex}_{Path(expanded).name}"
            remote = f"{dest_s3_dir}/_parts/{part_name}"
            aws_copy(expanded, remote, aws_env=aws_env, debug=debug)
            uploaded.append(remote)
            resolved.append(remote)
    except Exception:
        cleanup_s3_objects(uploaded, aws_env=aws_env, debug=debug)
        raise
    return resolved, uploaded


def multipart_concatenate(
    sources: Sequence[str],
    destination: str,
    *,
    aws_env: Dict[str, str],
    debug: bool,
) -> None:
    if not sources:
        raise CommandError("No sources provided for multipart concatenation")

    bucket, key = parse_s3_uri(destination)
    create = aws_command(
        ["s3api", "create-multipart-upload", "--bucket", bucket, "--key", key],
        aws_env=aws_env,
        debug=debug,
        capture_output=True,
    )
    upload_id = json.loads(create.stdout or "{}").get("UploadId")
    if not upload_id:
        raise CommandError(f"Failed to initiate multipart upload for destination {destination}")

    parts: List[Dict[str, str]] = []
    try:
        for idx, source in enumerate(sources, start=1):
            src_bucket, src_key = parse_s3_uri(source)
            copy_source = f"{src_bucket}/{src_key}"
            result = aws_command(
                [
                    "s3api",
                    "upload-part-copy",
                    "--bucket",
                    bucket,
                    "--key",
                    key,
                    "--part-number",
                    str(idx),
                    "--upload-id",
                    upload_id,
                    "--copy-source",
                    copy_source,
                ],
                aws_env=aws_env,
                debug=debug,
                capture_output=True,
            )
            payload = json.loads(result.stdout or "{}")
            etag = (
                payload.get("CopyPartResult", {}).get("ETag") if isinstance(payload, dict) else None
            )
            if not etag:
                raise CommandError(f"Failed to copy part from {source} during multipart upload")
            parts.append({"PartNumber": idx, "ETag": etag})

        complete_body = json.dumps({"Parts": parts})
        aws_command(
            [
                "s3api",
                "complete-multipart-upload",
                "--bucket",
                bucket,
                "--key",
                key,
                "--upload-id",
                upload_id,
                "--multipart-upload",
                complete_body,
            ],
            aws_env=aws_env,
            debug=debug,
        )
    except Exception:
        try:
            aws_command(
                [
                    "s3api",
                    "abort-multipart-upload",
                    "--bucket",
                    bucket,
                    "--key",
                    key,
                    "--upload-id",
                    upload_id,
                ],
                aws_env=aws_env,
                debug=debug,
            )
        except CommandError:
            pass
        raise


def _write_bundle_file(
    sources: Sequence[OntFastqShard],
    bundle_path: Path,
    *,
    aws_env: Dict[str, str],
    debug: bool,
) -> None:
    with bundle_path.open("wb") as bundle_handle:
        for source in sources:
            aws_command_binary_to_handle(
                ["s3", "cp", source.uri, "-"],
                bundle_handle,
                aws_env=aws_env,
                debug=debug,
            )


def _upload_concat_bundle(
    sources: Sequence[OntFastqShard],
    *,
    bundle_s3_dir: str,
    sample_prefix: str,
    bundle_number: int,
    suffix: str,
    aws_env: Dict[str, str],
    debug: bool,
) -> S3ObjectSummary:
    bundle_name = f"{sample_prefix}_ont_bundle{bundle_number}_{uuid.uuid4().hex}{suffix}"
    bundle_uri = f"{bundle_s3_dir}/{bundle_name}"
    size = sum(source.size for source in sources)
    with tempfile.NamedTemporaryFile(delete=False) as handle:
        bundle_path = Path(handle.name)
    try:
        _write_bundle_file(sources, bundle_path, aws_env=aws_env, debug=debug)
        aws_copy(str(bundle_path), bundle_uri, aws_env=aws_env, debug=debug)
    except Exception:
        cleanup_s3_objects([bundle_uri], aws_env=aws_env, debug=debug)
        raise
    finally:
        try:
            bundle_path.unlink()
        except FileNotFoundError:
            pass
    _bucket, key = parse_s3_uri(bundle_uri)
    return S3ObjectSummary(uri=bundle_uri, key=key, size=size)


def build_size_aware_concat_sources(
    shards: Sequence[OntFastqShard],
    *,
    bundle_s3_dir: str,
    sample_prefix: str,
    suffix: str,
    aws_env: Dict[str, str],
    debug: bool,
) -> Tuple[List[S3ObjectSummary], List[str]]:
    concat_sources: List[S3ObjectSummary] = []
    uploaded_bundles: List[str] = []
    pending_bundle: List[OntFastqShard] = []
    pending_size = 0
    bundle_number = 1

    def flush_pending() -> None:
        nonlocal bundle_number, pending_bundle, pending_size
        if not pending_bundle:
            return
        bundle = _upload_concat_bundle(
            pending_bundle,
            bundle_s3_dir=bundle_s3_dir,
            sample_prefix=sample_prefix,
            bundle_number=bundle_number,
            suffix=suffix,
            aws_env=aws_env,
            debug=debug,
        )
        concat_sources.append(bundle)
        uploaded_bundles.append(bundle.uri)
        bundle_number += 1
        pending_bundle = []
        pending_size = 0

    try:
        for shard in shards:
            if pending_bundle:
                pending_bundle.append(shard)
                pending_size += shard.size
                if pending_size >= S3_MULTIPART_MIN_PART_SIZE:
                    flush_pending()
                continue

            if shard.size >= S3_MULTIPART_MIN_PART_SIZE:
                concat_sources.append(
                    S3ObjectSummary(uri=shard.uri, key=shard.key, size=shard.size)
                )
                continue

            pending_bundle.append(shard)
            pending_size += shard.size

        flush_pending()
    except Exception:
        cleanup_s3_objects(uploaded_bundles, aws_env=aws_env, debug=debug)
        raise

    return concat_sources, uploaded_bundles


def concatenate_ont_fastq_shards(
    plan: OntFastqPrefixPlan,
    destination: str,
    *,
    bundle_s3_dir: str,
    sample_prefix: str,
    aws_env: Dict[str, str],
    debug: bool,
) -> None:
    suffix = ".fastq.gz" if plan.gzip_compressed else ".fastq"
    if len(plan.shards) == 1:
        aws_copy(plan.shards[0].uri, destination, aws_env=aws_env, debug=debug)
        return

    concat_sources, uploaded_bundles = build_size_aware_concat_sources(
        plan.shards,
        bundle_s3_dir=bundle_s3_dir,
        sample_prefix=sample_prefix,
        suffix=suffix,
        aws_env=aws_env,
        debug=debug,
    )
    try:
        if len(concat_sources) == 1:
            aws_copy(concat_sources[0].uri, destination, aws_env=aws_env, debug=debug)
        else:
            multipart_concatenate(
                [source.uri for source in concat_sources],
                destination,
                aws_env=aws_env,
                debug=debug,
            )
    except Exception:
        cleanup_s3_objects([destination], aws_env=aws_env, debug=debug)
        raise
    finally:
        cleanup_s3_objects(uploaded_bundles, aws_env=aws_env, debug=debug)


def stage_concordance(
    source: str,
    dest_fsx: str,
    dest_s3: str,
    *,
    reference_s3_uri: str,
    aws_env: Dict[str, str],
    debug: bool,
) -> str:
    source = source.strip()
    if not source or source.lower() == "na" or is_headnode_visible_path(source):
        return headnode_visible_path(source) if source else "na"
    copy_source = source_copy_reference(source, reference_s3_uri=reference_s3_uri)
    if copy_source.startswith("s3://"):
        aws_copy(copy_source, dest_s3, aws_env=aws_env, debug=debug, recursive=True)
    else:
        if os.path.isdir(copy_source):
            aws_copy(copy_source, dest_s3, aws_env=aws_env, debug=debug, recursive=True)
        else:
            aws_copy(copy_source, dest_s3, aws_env=aws_env, debug=debug)
    return dest_fsx


def stage_single_lane(
    r1: str,
    r2: str,
    dest_fsx_dir: str,
    dest_s3_dir: str,
    *,
    reference_s3_uri: str,
    aws_env: Dict[str, str],
    debug: bool,
) -> Tuple[str, str]:
    r1_name = os.path.basename(r1)
    r2_name = os.path.basename(r2)
    remote_r1_fsx = f"{dest_fsx_dir}/{r1_name}"
    remote_r2_fsx = f"{dest_fsx_dir}/{r2_name}"
    remote_r1_s3 = f"{dest_s3_dir}/{r1_name}"
    remote_r2_s3 = f"{dest_s3_dir}/{r2_name}"
    aws_copy(
        source_copy_reference(r1, reference_s3_uri=reference_s3_uri),
        remote_r1_s3,
        aws_env=aws_env,
        debug=debug,
    )
    aws_copy(
        source_copy_reference(r2, reference_s3_uri=reference_s3_uri),
        remote_r2_s3,
        aws_env=aws_env,
        debug=debug,
    )
    return remote_r1_fsx, remote_r2_fsx


def stage_multi_lane(
    r1_files: Sequence[str],
    r2_files: Sequence[str],
    sample_prefix: str,
    dest_fsx_dir: str,
    dest_s3_dir: str,
    *,
    reference_s3_uri: str,
    aws_env: Dict[str, str],
    debug: bool,
) -> Tuple[str, str]:
    merged_r1_name = f"{sample_prefix}_merged_R1.fastq.gz"
    merged_r2_name = f"{sample_prefix}_merged_R2.fastq.gz"
    remote_r1_s3 = f"{dest_s3_dir}/{merged_r1_name}"
    remote_r2_s3 = f"{dest_s3_dir}/{merged_r2_name}"

    r1_sources, r1_uploaded = ensure_s3_objects(
        r1_files,
        dest_s3_dir=dest_s3_dir,
        sample_prefix=f"{sample_prefix}_R1",
        reference_s3_uri=reference_s3_uri,
        aws_env=aws_env,
        debug=debug,
    )
    try:
        r2_sources, r2_uploaded = ensure_s3_objects(
            r2_files,
            dest_s3_dir=dest_s3_dir,
            sample_prefix=f"{sample_prefix}_R2",
            reference_s3_uri=reference_s3_uri,
            aws_env=aws_env,
            debug=debug,
        )
    except Exception:
        cleanup_s3_objects(r1_uploaded, aws_env=aws_env, debug=debug)
        raise

    try:
        multipart_concatenate(r1_sources, remote_r1_s3, aws_env=aws_env, debug=debug)
        multipart_concatenate(r2_sources, remote_r2_s3, aws_env=aws_env, debug=debug)
    finally:
        cleanup_s3_objects(r1_uploaded, aws_env=aws_env, debug=debug)
        cleanup_s3_objects(r2_uploaded, aws_env=aws_env, debug=debug)

    remote_r1_fsx = f"{dest_fsx_dir}/{merged_r1_name}"
    remote_r2_fsx = f"{dest_fsx_dir}/{merged_r2_name}"
    return remote_r1_fsx, remote_r2_fsx


def stage_ont_fastq_prefix(
    prefix: str,
    *,
    flowcell_id: str,
    sample_prefix: str,
    dest_fsx_dir: str,
    dest_s3_dir: str,
    reference_s3_uri: Optional[str] = None,
    plan: Optional[OntFastqPrefixPlan] = None,
    aws_env: Dict[str, str],
    debug: bool,
) -> Tuple[str, List[str]]:
    del reference_s3_uri
    if plan is None:
        plan = resolve_ont_fastq_prefix_plan(
            prefix,
            flowcell_id=flowcell_id,
            aws_env=aws_env,
            debug=debug,
        )
    suffix = ".fastq.gz" if plan.gzip_compressed else ".fastq"
    filename = f"{plan.run_id}-{plan.flowcell_id}-{plan.tag}-R1{suffix}"
    remote_r1_fsx = f"{dest_fsx_dir}/{filename}"
    remote_r1_s3 = f"{dest_s3_dir}/{filename}"
    concatenate_ont_fastq_shards(
        plan,
        remote_r1_s3,
        bundle_s3_dir=f"{dest_s3_dir}/_parts",
        sample_prefix=sample_prefix,
        aws_env=aws_env,
        debug=debug,
    )
    return remote_r1_fsx, [remote_r1_fsx]


def stage_path(
    source: str,
    *,
    dest_fsx_dir: str,
    dest_s3_dir: str,
    reference_s3_uri: str,
    aws_env: Dict[str, str],
    debug: bool,
) -> Tuple[str, List[str]]:
    filename = os.path.basename(source)
    remote_fsx = f"{dest_fsx_dir}/{filename}"
    remote_s3 = f"{dest_s3_dir}/{filename}"
    aws_copy(
        source_copy_reference(source, reference_s3_uri=reference_s3_uri),
        remote_s3,
        aws_env=aws_env,
        debug=debug,
    )
    return remote_fsx, [remote_fsx]


def stage_path_with_sidecars(
    source: str,
    *,
    sidecar_suffixes: Sequence[str],
    dest_fsx_dir: str,
    dest_s3_dir: str,
    reference_s3_uri: str,
    aws_env: Dict[str, str],
    debug: bool,
) -> Tuple[str, List[str]]:
    remote_path, created = stage_path(
        source,
        dest_fsx_dir=dest_fsx_dir,
        dest_s3_dir=dest_s3_dir,
        reference_s3_uri=reference_s3_uri,
        aws_env=aws_env,
        debug=debug,
    )
    for suffix in sidecar_suffixes:
        sidecar = f"{source}{suffix}"
        _, sidecar_created = stage_path(
            sidecar,
            dest_fsx_dir=dest_fsx_dir,
            dest_s3_dir=dest_s3_dir,
            reference_s3_uri=reference_s3_uri,
            aws_env=aws_env,
            debug=debug,
        )
        created.extend(sidecar_created)
    return remote_path, created


def stage_run_metrics(
    files: Sequence[RunMetricFile],
    stage: StagePaths,
    *,
    reference_s3_uri: str,
    aws_env: Dict[str, str],
    debug: bool,
) -> List[str]:
    created: List[str] = []
    for metric_file in files:
        remote_fsx = (
            f"{stage.remote_fsx_stage}/runs/{metric_file.spec.run_uid}/"
            f"{metric_file.destination_relative_path}"
        )
        remote_s3 = (
            f"{stage.remote_s3_stage}/runs/{metric_file.spec.run_uid}/"
            f"{metric_file.destination_relative_path}"
        )
        aws_copy(
            source_copy_reference(metric_file.source, reference_s3_uri=reference_s3_uri),
            remote_s3,
            aws_env=aws_env,
            debug=debug,
        )
        created.append(remote_fsx)
    return created


def reject_duplicate_multi_lane_sources(
    entries: Sequence[ManifestRow],
    *,
    sample_name: str,
) -> None:
    seen: set[Tuple[str, str]] = set()
    duplicates: list[Tuple[str, str]] = []
    for entry in entries:
        pair = (
            get_entry_value(entry.sources, ILMN_R1_FQ),
            get_entry_value(entry.sources, ILMN_R2_FQ),
        )
        if pair in seen and pair not in duplicates:
            duplicates.append(pair)
        seen.add(pair)
    if duplicates:
        duplicate_inputs = ", ".join(f"{r1} | {r2}" for r1, r2 in duplicates)
        raise CommandError(
            "Duplicate FASTQ lane sources are not supported for multi-lane samples. "
            f"Sample {sample_name} repeats the same R1/R2 pair across lanes: {duplicate_inputs}. "
            "Use distinct lane FASTQs or a single premerged/downsampled input instead."
        )


def split_fastq_path_list(value: str, *, field: str) -> List[str]:
    text = (value or "").strip()
    if text.lower() in EMPTY_PATH_TOKENS:
        return []
    try:
        paths = next(csv.reader([text], skipinitialspace=True))
    except csv.Error as exc:
        raise CommandError(f"{field} has an invalid comma-separated FASTQ list: {exc}") from exc
    cleaned = [path.strip() for path in paths]
    empty_positions = [
        str(index + 1) for index, path in enumerate(cleaned) if path.lower() in EMPTY_PATH_TOKENS
    ]
    if empty_positions:
        raise CommandError(
            f"{field} has empty FASTQ path(s) at position(s): {', '.join(empty_positions)}"
        )
    return cleaned


def paired_fastq_path_lists(
    r1_value: str,
    r2_value: str,
    *,
    r1_field: str,
    r2_field: str,
    row_number: int,
    require_r2: bool = True,
) -> Tuple[List[str], List[str]]:
    r1_paths = split_fastq_path_list(r1_value, field=r1_field)
    r2_paths = split_fastq_path_list(r2_value, field=r2_field)
    if not r1_paths and not r2_paths:
        return [], []
    if require_r2 and (not r1_paths or not r2_paths):
        raise CommandError(f"Row {row_number} must populate both {r1_field} and {r2_field}.")
    if not require_r2 and not r1_paths:
        raise CommandError(f"Row {row_number} must populate {r1_field}.")
    if not require_r2 and not r2_paths:
        return r1_paths, []
    if len(r1_paths) != len(r2_paths):
        raise CommandError(
            f"Row {row_number} {r1_field}/{r2_field} comma-separated lists must have the "
            f"same number of entries (R1={len(r1_paths)}, R2={len(r2_paths)})."
        )
    return r1_paths, r2_paths


def _strip_fastq_name_suffix(path: str) -> str:
    name = os.path.basename(path)
    for suffix in (".fastq.gz", ".fq.gz", ".fastq", ".fq"):
        if name.lower().endswith(suffix):
            return name[: -len(suffix)]
    return name


def _fastq_mate_signature(path: str, *, mate: str) -> str:
    stem = _strip_fastq_name_suffix(path)
    mate_pattern = re.compile(rf"(?i)(^|[._-]){mate}(?=([._-]|$))")
    signature, replacements = mate_pattern.subn(r"\1<MATE>", stem, count=1)
    if replacements != 1:
        raise CommandError(
            f"Cannot identify {mate} mate token in FASTQ path for pair-order validation: {path}"
        )
    return signature


def validate_fastq_pair_order(
    r1_paths: Sequence[str],
    r2_paths: Sequence[str],
    *,
    row_number: int,
    r1_field: str,
    r2_field: str,
) -> None:
    for index, (r1_path, r2_path) in enumerate(zip(r1_paths, r2_paths), start=1):
        r1_signature = _fastq_mate_signature(r1_path, mate="R1")
        r2_signature = _fastq_mate_signature(r2_path, mate="R2")
        if r1_signature != r2_signature:
            raise CommandError(
                f"Row {row_number} {r1_field}/{r2_field} pair {index} is out of order "
                f"or not mate-matched: {r1_path} vs {r2_path}"
            )


def write_tsv(path: Path, header: Sequence[str], rows: Sequence[Dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=header, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def deduplicate_rows(rows: Sequence[Dict[str, str]], header: Sequence[str]) -> List[Dict[str, str]]:
    seen: set[Tuple[str, ...]] = set()
    unique_rows: List[Dict[str, str]] = []
    for row in rows:
        key = tuple(row.get(column, "") for column in header)
        if key in seen:
            continue
        seen.add(key)
        unique_rows.append(row)
    return unique_rows


def unique_entity_rows(
    rows: Sequence[Dict[str, str]],
    *,
    key_field: str,
    entity: str,
) -> List[Dict[str, str]]:
    by_key: Dict[str, Dict[str, str]] = {}
    for row in rows:
        key = row.get(key_field, "")
        if not key:
            raise CommandError(f"Generated {entity} row is missing {key_field}")
        existing = by_key.get(key)
        if existing is not None and existing != row:
            raise CommandError(f"Generated {entity} rows conflict for {key_field}={key!r}")
        by_key[key] = row
    return [by_key[key] for key in sorted(by_key)]


def _normalise_headnode_data_path(value: str) -> str:
    if value == "/data" or value.startswith("/data/"):
        raise CommandError("The /fsx/data namespace is not supported; use explicit role roots.")
    return value


def normalise_units_paths(rows: Sequence[Dict[str, str]]) -> None:
    for row in rows:
        for field, value in list(row.items()):
            if not isinstance(value, str):
                continue
            if "," in value:
                parts = [part.strip() for part in value.split(",")]
                if any(part.startswith("/data/") or part == "/data" for part in parts):
                    row[field] = ",".join(_normalise_headnode_data_path(part) for part in parts)
                continue
            row[field] = _normalise_headnode_data_path(value)


def normalize_manifest_row(
    row: Mapping[str, str],
    *,
    row_number: int,
) -> Dict[str, str]:
    normalized = {k: (v or "").strip() for k, v in row.items() if k}
    for legacy_field, canonical_field in LEGACY_SOURCE_ALIASES.items():
        legacy_value = normalized.get(legacy_field, "")
        canonical_value = normalized.get(canonical_field, "")
        if legacy_value and canonical_value and legacy_value != canonical_value:
            raise CommandError(
                f"Row {row_number} sets both {legacy_field} and {canonical_field} with different values."
            )
        if legacy_value and not canonical_value:
            normalized[canonical_field] = legacy_value
    return normalized


def validate_raw_dayoa12_identities(row: Mapping[str, str], *, row_number: int) -> None:
    for field in DAYOA12_BYTE_EXACT_IDENTITY_FIELDS:
        raw = str(row.get(field) or "")
        if raw and raw != raw.strip():
            raise CommandError(
                f"Row {row_number} {field} contains surrounding whitespace; DayOA 12 identity "
                "and delivery fields are byte-exact and are never silently rewritten"
            )


def raw_groups_present(row: Mapping[str, str]) -> List[Tuple[str, str, str, str]]:
    present: List[Tuple[str, str, str, str]] = []
    for spec in RAW_SOURCE_SPECS:
        if get_entry_value(row, spec[0]) or get_entry_value(row, spec[1]):
            present.append(spec)
    return present


def normalize_stage_directive(value: str) -> str:
    directive = (value or "").strip().lower()
    if directive in {"", "na"}:
        return ""
    if directive in {"stage_data", "pass_through", "mounted_readonly"}:
        return directive
    raise CommandError(
        f"Unsupported STAGE_DIRECTIVE '{value}'. Supported values are "
        "stage_data, pass_through, mounted_readonly, or blank."
    )


def is_populated_path(value: str) -> bool:
    return bool(value) and value.lower() != "na"


def resolve_concordance_source(row: Mapping[str, str]) -> str:
    candidates = {
        field: get_entry_value(row, field)
        for field in (PATH_TO_CONCORDANCE, CONCORDANCE_CONTROL_PATH, TRUTH_DATA_DIR)
    }
    populated = {field: value for field, value in candidates.items() if is_populated_path(value)}
    unique_values = set(populated.values())
    if len(unique_values) > 1:
        details = ", ".join(f"{field}={value}" for field, value in populated.items())
        raise CommandError(
            f"Concordance path columns must agree when more than one is populated: {details}"
        )
    if unique_values:
        return next(iter(unique_values))
    return "na"


def validate_sidecar_paths(
    path: str,
    *,
    sidecar_suffixes: Sequence[str],
    reference_s3_uri: str,
    aws_env: Dict[str, str],
    debug: bool,
) -> None:
    for suffix in sidecar_suffixes:
        check_source_path(
            f"{path}{suffix}",
            reference_s3_uri=reference_s3_uri,
            aws_env=aws_env,
            debug=debug,
        )


def mounted_readonly_source_paths(normalized: Mapping[str, str]) -> List[Tuple[str, str]]:
    paths: List[Tuple[str, str]] = []
    for field in MOUNTED_READONLY_SOURCE_FIELDS:
        value = get_entry_value(normalized, field)
        if value:
            try:
                for path in split_fastq_path_list(value, field=field):
                    paths.append((field, path))
            except CommandError:
                paths.append((field, value))
    return sorted(paths)


def validate_manifest_row(
    normalized: Mapping[str, str],
    *,
    row_number: int,
    reference_s3_uri: str,
    aws_env: Dict[str, str],
    debug: bool,
    check_access: bool = True,
) -> None:
    issues = collect_manifest_row_issues(
        normalized,
        row_number=row_number,
        reference_s3_uri=reference_s3_uri,
        aws_env=aws_env,
        debug=debug,
        check_access=check_access,
    )
    if issues:
        raise CommandError(issues[0].message)


def build_manifest_row(
    normalized: Mapping[str, str],
    *,
    row_number: int = 0,
    manifest_contract: str = "legacy_v11",
) -> ManifestRow:
    if manifest_contract not in {"legacy_v11", "dayoa12"}:
        raise CommandError(f"Unsupported manifest contract: {manifest_contract}")
    source_sample_field = SAMPLEID if manifest_contract == "dayoa12" else SAMPLE_ID
    source_sample_id = get_entry_value(normalized, source_sample_field)
    sample_id = (
        exact_source_identifier(source_sample_id, field=SAMPLEID)
        if manifest_contract == "dayoa12"
        else normalise_identifier(source_sample_id)
    )
    sample_type = normalise_identifier(get_entry_value(normalized, SAMPLE_TYPE))
    sample_source = get_entry_value(normalized, SAMPLESOURCE) or sample_type
    sample_class = get_entry_value(normalized, SAMPLECLASS) or "research"
    n_x = get_entry_value(normalized, N_X)
    n_y = get_entry_value(normalized, N_Y)
    biological_sex = get_entry_value(normalized, BIOLOGICAL_SEX) or determine_sex(
        safe_int(n_x),
        safe_int(n_y),
    )
    tum_nrm_sampleid_match = get_entry_value(normalized, TUM_NRM_SAMPLEID_MATCH)
    if TUM_NRM_SAMPLEID_MATCH not in normalized:
        tum_nrm_sampleid_match = "na"
    sample = SampleMetadata(
        sample_id=sample_id,
        sample_type=sample_type,
        sample_source=sample_source,
        sample_class=sample_class,
        biological_sex=biological_sex,
        path_to_concordance=resolve_concordance_source(normalized),
        is_pos_ctrl=resolve_positive_control(normalized),
        is_neg_ctrl=resolve_negative_control(normalized),
        tum_nrm_sampleid_match=tum_nrm_sampleid_match,
        n_x=n_x,
        n_y=n_y,
        external_sample_id=get_entry_value(normalized, EXTERNAL_SAMPLE_ID) or "na",
        specimen_id=get_entry_value(normalized, SPECIMEN_ID),
        specimen_euid=get_entry_value(normalized, SPECIMEN_EUID),
        sample_euid=get_entry_value(normalized, SAMPLE_EUID),
        specimen_type=get_entry_value(normalized, SPECIMEN_TYPE),
        external_specimen_id=get_entry_value(normalized, EXTERNAL_SPECIMEN_ID),
        sample_use=get_entry_value(normalized, SAMPLEUSE),
        order_type=get_entry_value(normalized, ORDER_TYPE),
        iddna_uid=get_entry_value(normalized, IDDNA_UID),
        specimen_comment=get_entry_value(normalized, SPECIMEN_COMMENT),
        sample_comment=get_entry_value(normalized, SAMPLE_COMMENT),
    )
    vendor = canonical_manifest_seq_vendor(get_entry_value(normalized, SEQ_VENDOR))
    ont_fastq_prefix = get_entry_value(normalized, ONT_FASTQ_PREFIX)
    if ont_fastq_prefix:
        _prefix_uri, ont_tag, ont_run_id, _run_output_prefix = parse_ont_fastq_prefix(
            ont_fastq_prefix
        )
    else:
        ont_tag = ""
        ont_run_id = ""
    unit = UnitMetadata(
        run_id=ont_run_id or normalise_run_id(get_entry_value(normalized, RUN_ID)),
        experiment_id=normalise_identifier(get_entry_value(normalized, EXPERIMENT_ID)),
        lib_prep=canonical_manifest_libprep(get_entry_value(normalized, LIB_PREP), vendor=vendor),
        seq_vendor=vendor,
        seq_platform=canonical_manifest_seq_platform(
            get_entry_value(normalized, SEQ_PLATFORM), vendor=vendor
        ),
        lane=normalise_identifier(
            get_entry_value(normalized, ONT_FLOWCELL_ID) or get_entry_value(normalized, LANE)
        ),
        seqbc_id=ont_tag or normalise_identifier(get_entry_value(normalized, SEQBC_ID)),
        analysis_unit_uid=get_entry_value(normalized, ANALYSIS_UNIT_UID),
        library_euid=get_entry_value(normalized, LIBRARY_EUID),
        inflection_delivery_id=get_entry_value(normalized, INFLECTION_DELIVERY_ID),
        library_comment=get_entry_value(normalized, LIBRARY_COMMENT),
    )
    staging = StagingOptions(
        stage_directive=normalize_stage_directive(get_entry_value(normalized, STAGE_DIRECTIVE)),
        stage_target=get_entry_value(normalized, STAGE_TARGET),
        subsample_pct=validate_subsample_pct(get_entry_value(normalized, SUBSAMPLE_PCT, "na")),
    )
    sources = {
        field: get_entry_value(normalized, field)
        for field in {
            ILMN_R1_FQ,
            ILMN_R2_FQ,
            CG_R1_FQ,
            CG_R2_FQ,
            PACBIO_R1_FQ,
            PACBIO_R2_FQ,
            ONT_R1_FQ,
            ONT_R2_FQ,
            ONT_FASTQ_PREFIX,
            ONT_FLOWCELL_ID,
            UG_R1_FQ,
            UG_R2_FQ,
            ULTIMA_CRAM,
            ONT_CRAM,
            PB_BAM,
            ONT_BAM,
            ROCHE_BAM,
        }
    }
    units_passthrough = {
        field: get_entry_value(normalized, field)
        for field in MANIFEST_UNITS_PASSTHROUGH_FIELDS
        if get_entry_value(normalized, field)
    }
    return ManifestRow(
        sample=sample,
        unit=unit,
        staging=staging,
        sources=sources,
        units_passthrough=units_passthrough,
        original=dict(normalized),
        row_number=row_number,
        manifest_contract=manifest_contract,
    )


def load_manifest_rows(
    analysis_samples: Path,
    *,
    reference_s3_uri: str,
    aws_env: Dict[str, str],
    debug: bool,
    manifest_contract: str = "legacy_v11",
) -> List[ManifestRow]:
    rows: List[ManifestRow] = []
    with analysis_samples.open(newline="") as ff:
        reader = csv.DictReader(ff, delimiter="\t")
        if reader.fieldnames is None:
            raise CommandError("Input TSV is missing a header row")
        header_fields = [field.strip() for field in reader.fieldnames if field and field.strip()]
        unknown_fields = sorted(set(header_fields) - ALLOWED_MANIFEST_FIELDS)
        if unknown_fields:
            raise CommandError(
                "Unknown columns in analysis samples manifest: " + ", ".join(unknown_fields)
            )
        required_fields = (
            DAYOA12_MANIFEST_REQUIRED_FIELDS
            if manifest_contract == "dayoa12"
            else MANIFEST_REQUIRED_FIELDS
        )
        missing_fields = [field for field in required_fields if field not in header_fields]
        if missing_fields:
            raise CommandError(f"Missing required columns: {', '.join(missing_fields)}")

        for row_number, row in enumerate(reader, start=2):
            if not row:
                continue
            if manifest_contract == "dayoa12":
                validate_raw_dayoa12_identities(row, row_number=row_number)
            normalized = normalize_manifest_row(row, row_number=row_number)
            if not any(normalized.values()):
                continue
            if manifest_contract == "dayoa12":
                blank_required = [
                    field for field in DAYOA12_NONBLANK_REQUIRED_FIELDS if not normalized.get(field)
                ]
                if blank_required:
                    raise CommandError(
                        "DayOA 12 source manifests require explicit nonblank values; blank "
                        f"columns: {', '.join(blank_required)}. DYEC does not infer identifiers."
                    )
            validate_manifest_row(
                normalized,
                row_number=row_number,
                reference_s3_uri=reference_s3_uri,
                aws_env=aws_env,
                debug=debug,
            )
            rows.append(
                build_manifest_row(
                    normalized,
                    row_number=row_number,
                    manifest_contract=manifest_contract,
                )
            )

    if manifest_contract == "dayoa12":
        validate_dayoa12_lineage(rows)
    return rows


def _row_issue(
    normalized: Mapping[str, str],
    *,
    row_number: int,
    field: str,
    path: str = "",
    message: str,
) -> PrecheckIssue:
    sample_id = (
        get_entry_value(normalized, SAMPLEID)
        or normalise_identifier(get_entry_value(normalized, SAMPLE_ID))
        or "na"
    )
    run_id = normalise_run_id(get_entry_value(normalized, RUN_ID)) or "na"
    message = re.sub(rf"^Row {row_number}\s+", "", message).strip()
    return PrecheckIssue(
        row_number=row_number,
        sample_id=sample_id,
        run_id=run_id,
        field=field,
        path=path,
        message=message,
    )


def _issue_from_exception(
    normalized: Mapping[str, str],
    *,
    row_number: int,
    default_field: str,
    default_path: str = "",
    exc: Exception,
) -> PrecheckIssue:
    message = str(exc)
    field = default_field
    path = default_path
    for candidate in sorted(ALLOWED_MANIFEST_FIELDS, key=len, reverse=True):
        if candidate in message:
            field = candidate
            path = get_entry_value(normalized, candidate) or path
            break
    return _row_issue(
        normalized,
        row_number=row_number,
        field=field,
        path=path,
        message=message,
    )


def _require_consistent_entity(
    records: Dict[str, Dict[str, str]],
    *,
    key: str,
    row: Dict[str, str],
    entity: str,
) -> None:
    value = row[key]
    existing = records.get(value)
    if existing is not None and existing != row:
        raise CommandError(f"Conflicting {entity} metadata for {key}={value!r}")
    records[value] = row


def build_specimens_rows(rows: Sequence[ManifestRow]) -> List[Dict[str, str]]:
    specimens: Dict[str, Dict[str, str]] = {}
    for entry in rows:
        row = {
            SPECIMEN_ID: entry.sample.specimen_id,
            SPECIMEN_EUID: entry.sample.specimen_euid,
            SAMPLESOURCE: entry.sample.sample_source,
            SPECIMEN_TYPE: entry.sample.specimen_type,
            EXTERNAL_SPECIMEN_ID: entry.sample.external_specimen_id,
            BIOLOGICAL_SEX: entry.sample.biological_sex,
            N_X: entry.sample.n_x,
            N_Y: entry.sample.n_y,
            SPECIMEN_COMMENT: entry.sample.specimen_comment,
        }
        _require_consistent_entity(
            specimens,
            key=SPECIMEN_ID,
            row=row,
            entity="specimen",
        )
    return [specimens[key] for key in sorted(specimens)]


def validate_dayoa12_lineage(rows: Sequence[ManifestRow]) -> None:
    specimen_euids: Dict[str, str] = {}
    sample_euids: Dict[str, str] = {}
    library_euids: Dict[str, str] = {}
    sample_specimens: Dict[str, str] = {}
    analysis_units: Dict[str, str] = {}
    delivery_ids: Dict[str, str] = {}
    for entry in rows:
        for field, value in (
            (SPECIMEN_ID, entry.sample.specimen_id),
            (SAMPLEID, entry.sample.sample_id),
        ):
            exact_source_identifier(value, field=field)
        for field, value in (
            (SPECIMEN_EUID, entry.sample.specimen_euid),
            (SAMPLE_EUID, entry.sample.sample_euid),
            (ANALYSIS_UNIT_UID, entry.unit.analysis_unit_uid),
            (LIBRARY_EUID, entry.unit.library_euid),
        ):
            if value:
                exact_source_identifier(value, field=field)
        identities = (
            ("specimen", entry.sample.specimen_euid, entry.sample.specimen_id, specimen_euids),
            ("sample", entry.sample.sample_euid, entry.sample.sample_id, sample_euids),
            ("library", entry.unit.library_euid, entry.unit.analysis_unit_uid, library_euids),
        )
        for entity, euid, key, seen in identities:
            if not euid:
                continue
            existing = seen.get(euid)
            if existing is not None and existing != key:
                raise CommandError(
                    f"{entity} EUID {euid!r} is assigned to multiple identifiers: "
                    f"{existing!r}, {key!r}"
                )
            seen[euid] = key
        delivery_id = entry.unit.inflection_delivery_id
        if delivery_id:
            exact_source_identifier(delivery_id, field=INFLECTION_DELIVERY_ID)
            delivery_owner = (
                entry.unit.analysis_unit_uid
                or entry.unit.library_euid
                or f"{entry.sample.sample_id}:{entry.row_number}"
            )
            existing_delivery = delivery_ids.get(delivery_id)
            if existing_delivery is not None and existing_delivery != delivery_owner:
                raise CommandError(
                    f"INFLECTION_DELIVERY_ID {delivery_id!r} is assigned to multiple "
                    f"library rows: {existing_delivery!r}, {delivery_owner!r}"
                )
            delivery_ids[delivery_id] = delivery_owner
        existing_specimen = sample_specimens.get(entry.sample.sample_id)
        if existing_specimen is not None and existing_specimen != entry.sample.specimen_id:
            raise CommandError(
                f"SAMPLEID {entry.sample.sample_id!r} references multiple SPECIMEN_ID values"
            )
        sample_specimens[entry.sample.sample_id] = entry.sample.specimen_id
        if entry.unit.analysis_unit_uid:
            existing_library = analysis_units.get(entry.unit.analysis_unit_uid)
            if existing_library is not None and existing_library != entry.unit.library_euid:
                raise CommandError(
                    f"ANALYSIS_UNIT_UID {entry.unit.analysis_unit_uid!r} references multiple "
                    "LIBRARY_EUID values"
                )
            analysis_units[entry.unit.analysis_unit_uid] = entry.unit.library_euid


def collect_manifest_row_issues(
    normalized: Mapping[str, str],
    *,
    row_number: int,
    reference_s3_uri: str,
    aws_env: Dict[str, str],
    debug: bool,
    check_access: bool = True,
) -> List[PrecheckIssue]:
    issues: List[PrecheckIssue] = []

    def add_issue(field: str, message: str, path: str = "") -> None:
        issues.append(
            _row_issue(
                normalized,
                row_number=row_number,
                field=field,
                path=path,
                message=message,
            )
        )

    def add_exception(field: str, exc: Exception, path: str = "") -> None:
        issues.append(
            _issue_from_exception(
                normalized,
                row_number=row_number,
                default_field=field,
                default_path=path,
                exc=exc,
            )
        )

    def maybe_check_source_path(
        field: str,
        path: str,
        *,
        allow_directory: bool = False,
    ) -> None:
        if not check_access or not path:
            return
        if directive == "mounted_readonly" and field in MOUNTED_READONLY_SOURCE_FIELDS:
            return
        try:
            check_source_path(
                path,
                reference_s3_uri=reference_s3_uri,
                aws_env=aws_env,
                debug=debug,
                allow_directory=allow_directory,
            )
        except CommandError as exc:
            add_issue(field, str(exc), path)

    def maybe_validate_sidecars(
        field: str,
        path: str,
        *,
        sidecar_suffixes: Sequence[str],
    ) -> None:
        if not check_access or not path:
            return
        if directive == "mounted_readonly" and field in MOUNTED_READONLY_SOURCE_FIELDS:
            return
        for suffix in sidecar_suffixes:
            sidecar = f"{path}{suffix}"
            try:
                check_source_path(
                    sidecar,
                    reference_s3_uri=reference_s3_uri,
                    aws_env=aws_env,
                    debug=debug,
                )
            except CommandError as exc:
                add_issue(f"{field}{suffix}", str(exc), sidecar)

    raw_groups = raw_groups_present(normalized)
    ont_fastq_prefix = get_entry_value(normalized, ONT_FASTQ_PREFIX)
    aligned_fields = [
        field for field in ALIGNED_SOURCE_FIELDS if get_entry_value(normalized, field)
    ]

    try:
        directive = normalize_stage_directive(get_entry_value(normalized, STAGE_DIRECTIVE))
    except CommandError as exc:
        directive = ""
        add_exception(STAGE_DIRECTIVE, exc, get_entry_value(normalized, STAGE_DIRECTIVE))

    if not raw_groups and not ont_fastq_prefix and not aligned_fields:
        add_issue(
            "data source",
            f"Row {row_number} does not define any supported data source columns.",
        )

    if directive == "mounted_readonly":
        expected_mount_id = ""
        try:
            expected_mount_id = validate_mount_id(get_entry_value(normalized, MOUNT_ID))
        except CommandError as exc:
            add_issue(MOUNT_ID, str(exc), get_entry_value(normalized, MOUNT_ID))

        mount_source_s3_uri = get_entry_value(normalized, MOUNT_SOURCE_S3_URI)
        if mount_source_s3_uri:
            try:
                bucket, _key = parse_s3_uri(mount_source_s3_uri)
                if not bucket:
                    raise CommandError(f"{MOUNT_SOURCE_S3_URI} must include an S3 bucket.")
            except CommandError as exc:
                add_issue(MOUNT_SOURCE_S3_URI, str(exc), mount_source_s3_uri)

        mount_fsx_path = get_entry_value(normalized, MOUNT_FSX_PATH)
        if mount_fsx_path:
            try:
                if expected_mount_id:
                    require_mounted_root_path(
                        mount_fsx_path,
                        expected_mount_id=expected_mount_id,
                    )
                else:
                    _root, _mount_id, relative_parts = parse_mounted_run_dir_path(
                        mount_fsx_path,
                        field=MOUNT_FSX_PATH,
                    )
                    if relative_parts:
                        raise CommandError(
                            f"{MOUNT_FSX_PATH} must be the mount root, not a child path: "
                            f"{mount_fsx_path}"
                        )
            except CommandError as exc:
                add_issue(MOUNT_FSX_PATH, str(exc), mount_fsx_path)

        if ont_fastq_prefix:
            add_issue(
                ONT_FASTQ_PREFIX,
                (
                    f"Row {row_number} uses STAGE_DIRECTIVE=mounted_readonly, which requires "
                    "mounted FASTQ/CRAM/BAM file paths instead of ONT_FASTQ_PREFIX."
                ),
                ont_fastq_prefix,
            )

        if expected_mount_id:
            for field, path in mounted_readonly_source_paths(normalized):
                try:
                    require_mounted_source_path(
                        path,
                        field=field,
                        expected_mount_id=expected_mount_id,
                    )
                except CommandError as exc:
                    add_issue(field, str(exc), path)

    if ont_fastq_prefix:
        vendor = canonical_manifest_seq_vendor(get_entry_value(normalized, SEQ_VENDOR))
        if vendor != "ONT":
            add_issue(
                SEQ_VENDOR,
                f"Row {row_number} requires {SEQ_VENDOR}=ONT for {ONT_FASTQ_PREFIX}.",
                get_entry_value(normalized, SEQ_VENDOR),
            )
        ont_conflicts = [
            field
            for field in (ONT_R1_FQ, ONT_R2_FQ, ONT_CRAM, ONT_BAM)
            if get_entry_value(normalized, field)
        ]
        if raw_groups or aligned_fields or ont_conflicts:
            add_issue(
                ONT_FASTQ_PREFIX,
                (
                    f"Row {row_number} must not combine {ONT_FASTQ_PREFIX} "
                    "with other staged data source columns."
                ),
                ont_fastq_prefix,
            )
        if directive == "pass_through":
            add_issue(
                STAGE_DIRECTIVE,
                f"Row {row_number} requires STAGE_DIRECTIVE=stage_data for {ONT_FASTQ_PREFIX}.",
                get_entry_value(normalized, STAGE_DIRECTIVE),
            )
        try:
            parse_ont_fastq_prefix(ont_fastq_prefix)
        except CommandError as exc:
            add_issue(ONT_FASTQ_PREFIX, str(exc), ont_fastq_prefix)

    for r1_field, r2_field, _unit_r1, _unit_r2 in raw_groups:
        r1_value = get_entry_value(normalized, r1_field)
        r2_value = get_entry_value(normalized, r2_field)
        try:
            r1_paths, r2_paths = paired_fastq_path_lists(
                r1_value,
                r2_value,
                r1_field=r1_field,
                r2_field=r2_field,
                row_number=row_number,
                require_r2=r1_field != ONT_R1_FQ,
            )
            if len(r1_paths) > 1 and (r1_field, r2_field) not in {
                (ILMN_R1_FQ, ILMN_R2_FQ),
                (ONT_R1_FQ, ONT_R2_FQ),
            }:
                add_issue(
                    f"{r1_field}/{r2_field}",
                    (
                        f"Row {row_number} comma-separated FASTQ lists are only supported "
                        f"for {ILMN_R1_FQ}/{ILMN_R2_FQ} or {ONT_R1_FQ}/{ONT_R2_FQ}."
                    ),
                    r1_value,
                )
            if len(r1_paths) > 1 and r2_paths:
                try:
                    validate_fastq_pair_order(
                        r1_paths,
                        r2_paths,
                        row_number=row_number,
                        r1_field=r1_field,
                        r2_field=r2_field,
                    )
                except CommandError as exc:
                    add_issue(f"{r1_field}/{r2_field}", str(exc), r1_value)
            if r1_field == ONT_R1_FQ and not r2_paths and directive != "pass_through":
                add_issue(
                    f"{r1_field}/{r2_field}",
                    (
                        f"Row {row_number} uses single-end ONT raw FASTQ; "
                        f"set {STAGE_DIRECTIVE}=pass_through or use {ONT_FASTQ_PREFIX} "
                        "for staged ONT shards."
                    ),
                    r1_value,
                )
        except CommandError as exc:
            r1_paths = [r1_value] if r1_value else []
            r2_paths = [r2_value] if r2_value else []
            add_issue(f"{r1_field}/{r2_field}", str(exc), r1_value or r2_value)
        for source_path in r1_paths:
            if is_headnode_scratch_path(source_path) and directive != "pass_through":
                add_issue(
                    r1_field,
                    (
                        f"Row {row_number} uses scratch source {source_path}; "
                        f"set {STAGE_DIRECTIVE}=pass_through for /fsx/scratch inputs."
                    ),
                    source_path,
                )
            maybe_check_source_path(r1_field, source_path)
        for source_path in r2_paths:
            if is_headnode_scratch_path(source_path) and directive != "pass_through":
                add_issue(
                    r2_field,
                    (
                        f"Row {row_number} uses scratch source {source_path}; "
                        f"set {STAGE_DIRECTIVE}=pass_through for /fsx/scratch inputs."
                    ),
                    source_path,
                )
            maybe_check_source_path(r2_field, source_path)
        if directive == "pass_through":
            for field, value in (
                *((r1_field, path) for path in r1_paths),
                *((r2_field, path) for path in r2_paths),
            ):
                if not value:
                    continue
                try:
                    require_headnode_visible_path(value, field=field)
                except CommandError as exc:
                    add_issue(field, str(exc), value)

    try:
        concordance_source = resolve_concordance_source(normalized)
    except CommandError as exc:
        concordance_source = "na"
        add_exception(CONCORDANCE_CONTROL_PATH, exc)
    if is_populated_path(concordance_source):
        maybe_check_source_path(CONCORDANCE_CONTROL_PATH, concordance_source, allow_directory=True)

    if get_entry_value(normalized, ULTIMA_CRAM):
        source = get_entry_value(normalized, ULTIMA_CRAM)
        maybe_check_source_path(ULTIMA_CRAM, source)
        maybe_validate_sidecars(ULTIMA_CRAM, source, sidecar_suffixes=(".crai",))
        aligner = get_entry_value(normalized, ULTIMA_CRAM_ALIGNER).lower()
        if aligner not in {"ug", "hyb"}:
            add_issue(
                ULTIMA_CRAM_ALIGNER,
                (
                    f"Row {row_number} requires {ULTIMA_CRAM_ALIGNER} to be one of ug, hyb "
                    f"when {ULTIMA_CRAM} is populated."
                ),
                get_entry_value(normalized, ULTIMA_CRAM_ALIGNER),
            )
        if directive != "stage_data":
            try:
                require_headnode_visible_path(source, field=ULTIMA_CRAM)
            except CommandError as exc:
                add_issue(ULTIMA_CRAM, str(exc), source)

    if get_entry_value(normalized, ONT_CRAM):
        source = get_entry_value(normalized, ONT_CRAM)
        maybe_check_source_path(ONT_CRAM, source)
        maybe_validate_sidecars(ONT_CRAM, source, sidecar_suffixes=(".crai",))
        aligner = get_entry_value(normalized, ONT_CRAM_ALIGNER).lower()
        if aligner != "ont":
            add_issue(
                ONT_CRAM_ALIGNER,
                f"Row {row_number} requires {ONT_CRAM_ALIGNER}=ont when {ONT_CRAM} is populated.",
                get_entry_value(normalized, ONT_CRAM_ALIGNER),
            )
        if directive != "stage_data":
            try:
                require_headnode_visible_path(source, field=ONT_CRAM)
            except CommandError as exc:
                add_issue(ONT_CRAM, str(exc), source)

    if get_entry_value(normalized, PB_BAM):
        source = get_entry_value(normalized, PB_BAM)
        maybe_check_source_path(PB_BAM, source)
        aligner = get_entry_value(normalized, PB_BAM_ALIGNER).lower()
        if aligner not in {"pb", "sentmm2"}:
            add_issue(
                PB_BAM_ALIGNER,
                (
                    f"Row {row_number} requires {PB_BAM_ALIGNER} to be one of pb, sentmm2 "
                    f"when {PB_BAM} is populated."
                ),
                get_entry_value(normalized, PB_BAM_ALIGNER),
            )
        if aligner == "pb":
            maybe_validate_sidecars(PB_BAM, source, sidecar_suffixes=(".csi",))
        if directive != "stage_data":
            try:
                require_headnode_visible_path(source, field=PB_BAM)
            except CommandError as exc:
                add_issue(PB_BAM, str(exc), source)

    if get_entry_value(normalized, ONT_BAM):
        source = get_entry_value(normalized, ONT_BAM)
        maybe_check_source_path(ONT_BAM, source)
        aligner = get_entry_value(normalized, ONT_BAM_ALIGNER).lower()
        if aligner != "sentmm2ont":
            add_issue(
                ONT_BAM_ALIGNER,
                (
                    f"Row {row_number} requires {ONT_BAM_ALIGNER}=sentmm2ont "
                    f"when {ONT_BAM} is populated."
                ),
                get_entry_value(normalized, ONT_BAM_ALIGNER),
            )
        if directive != "stage_data":
            try:
                require_headnode_visible_path(source, field=ONT_BAM)
            except CommandError as exc:
                add_issue(ONT_BAM, str(exc), source)

    if get_entry_value(normalized, ROCHE_BAM):
        source = get_entry_value(normalized, ROCHE_BAM)
        maybe_check_source_path(ROCHE_BAM, source)
        aligner = get_entry_value(normalized, ROCHE_BAM_ALIGNER).lower()
        if aligner != "roche":
            add_issue(
                ROCHE_BAM_ALIGNER,
                f"Row {row_number} requires {ROCHE_BAM_ALIGNER}=roche when {ROCHE_BAM} is populated.",
                get_entry_value(normalized, ROCHE_BAM_ALIGNER),
            )
        if directive != "stage_data":
            try:
                require_headnode_visible_path(source, field=ROCHE_BAM)
            except CommandError as exc:
                add_issue(ROCHE_BAM, str(exc), source)

    return issues


def _source_checks_for_precheck(normalized: Mapping[str, str]) -> List[Tuple[str, str]]:
    checks: List[Tuple[str, str]] = []
    try:
        if (
            normalize_stage_directive(get_entry_value(normalized, STAGE_DIRECTIVE))
            == "mounted_readonly"
        ):
            return checks
    except CommandError:
        pass
    for r1_field, r2_field, _unit_r1, _unit_r2 in raw_groups_present(normalized):
        r1_value = get_entry_value(normalized, r1_field)
        r2_value = get_entry_value(normalized, r2_field)
        try:
            r1_paths = split_fastq_path_list(r1_value, field=r1_field)
        except CommandError:
            r1_paths = [r1_value] if r1_value else []
        try:
            r2_paths = split_fastq_path_list(r2_value, field=r2_field)
        except CommandError:
            r2_paths = [r2_value] if r2_value else []
        for path in r1_paths:
            checks.append((r1_field, path))
        for path in r2_paths:
            checks.append((r2_field, path))

    aligned_sidecars = (
        (ULTIMA_CRAM, (".crai",)),
        (ONT_CRAM, (".crai",)),
        (
            PB_BAM,
            (".csi",) if get_entry_value(normalized, PB_BAM_ALIGNER).lower() == "pb" else (),
        ),
        (ONT_BAM, ()),
        (ROCHE_BAM, ()),
    )
    for field, sidecars in aligned_sidecars:
        source = get_entry_value(normalized, field)
        if not source:
            continue
        checks.append((field, source))
        for suffix in sidecars:
            checks.append((f"{field}{suffix}", f"{source}{suffix}"))
    return checks


def _concordance_source_field(normalized: Mapping[str, str]) -> Tuple[str, str]:
    for field in (PATH_TO_CONCORDANCE, CONCORDANCE_CONTROL_PATH, TRUTH_DATA_DIR):
        value = get_entry_value(normalized, field)
        if is_populated_path(value):
            return field, value
    return PATH_TO_CONCORDANCE, "na"


def _s3_child_directories(
    prefix_uri: str,
    *,
    aws_env: Dict[str, str],
    debug: bool,
) -> List[str]:
    normalized_prefix = normalise_s3_prefix_uri(prefix_uri)
    _bucket, prefix = parse_s3_uri(normalized_prefix)
    base_prefix = prefix.strip("/")
    if base_prefix:
        base_prefix += "/"
    child_dirs: set[str] = set()
    for obj in list_s3_objects(normalized_prefix, aws_env=aws_env, debug=debug):
        if base_prefix and not obj.key.startswith(base_prefix):
            continue
        relative = obj.key[len(base_prefix) :] if base_prefix else obj.key
        parts = [part for part in relative.split("/") if part]
        if len(parts) > 1:
            child_dirs.add(parts[0])
    return sorted(child_dirs)


def detect_giab_roi_dirs(
    concordance_source: str,
    *,
    reference_s3_uri: str,
    aws_env: Dict[str, str],
    debug: bool,
) -> List[str]:
    if concordance_source.startswith("s3://"):
        return _s3_child_directories(concordance_source, aws_env=aws_env, debug=debug)
    if is_mounted_run_dir_path(concordance_source):
        return []
    if is_headnode_visible_path(concordance_source):
        return _s3_child_directories(
            build_reference_uri(concordance_source, reference_s3_uri),
            aws_env=aws_env,
            debug=debug,
        )

    source_path = Path(os.path.expanduser(concordance_source))
    if not source_path.is_dir():
        return []
    try:
        return sorted(path.name for path in source_path.iterdir() if path.is_dir())
    except OSError as exc:
        raise CommandError(
            f"Could not inspect local concordance directory {concordance_source}: {exc}"
        ) from exc


def _precheck_giab_truth_files(
    normalized: Mapping[str, str],
    *,
    row_number: int,
    concordance_source: str,
    reference_s3_uri: str,
    aws_env: Dict[str, str],
    debug: bool,
) -> Tuple[List[PrecheckIssue], int]:
    try:
        should_check = should_precheck_giab_truth(normalized)
        has_giab_path = is_giab_control(normalized)
    except CommandError:
        return [], 0
    if not should_check:
        return [], 0

    issues: List[PrecheckIssue] = []
    checked = 0
    if get_entry_value(normalized, IS_POS_CTRL).lower() == "true" and not has_giab_path:
        return [
            _row_issue(
                normalized,
                row_number=row_number,
                field=IS_POS_CTRL,
                path=concordance_source,
                message=(
                    "IS_POS_CTRL=true requires a GIAB concordance path under /controls/giab/ "
                    "for truth validation."
                ),
            )
        ], checked

    external_sample_id = get_entry_value(normalized, EXTERNAL_SAMPLE_ID)
    if not external_sample_id or external_sample_id.lower() == "na":
        return [
            _row_issue(
                normalized,
                row_number=row_number,
                field=EXTERNAL_SAMPLE_ID,
                message="Positive GIAB controls require EXTERNAL_SAMPLE_ID for truth file lookup.",
            )
        ], checked

    try:
        roi_dirs = detect_giab_roi_dirs(
            concordance_source,
            reference_s3_uri=reference_s3_uri,
            aws_env=aws_env,
            debug=debug,
        )
    except CommandError as exc:
        return [
            _row_issue(
                normalized,
                row_number=row_number,
                field=CONCORDANCE_CONTROL_PATH,
                path=concordance_source,
                message=f"Could not inspect GIAB ROI directories: {exc}",
            )
        ], checked

    if not roi_dirs:
        return [
            _row_issue(
                normalized,
                row_number=row_number,
                field=CONCORDANCE_CONTROL_PATH,
                path=concordance_source,
                message="Positive GIAB control has no detected ROI directories.",
            )
        ], checked

    for roi in roi_dirs:
        missing_suffixes: List[str] = []
        truth_base = f"{concordance_source.rstrip('/')}/{roi}/{external_sample_id}"
        for suffix in GIAB_TRUTH_SUFFIXES:
            checked += 1
            truth_path = f"{truth_base}{suffix}"
            try:
                check_source_path(
                    truth_path,
                    reference_s3_uri=reference_s3_uri,
                    aws_env=aws_env,
                    debug=debug,
                )
            except CommandError:
                missing_suffixes.append(suffix)
        if missing_suffixes:
            issues.append(
                _row_issue(
                    normalized,
                    row_number=row_number,
                    field=EXTERNAL_SAMPLE_ID,
                    path=truth_base,
                    message=(
                        f"GIAB truth files missing for EXTERNAL_SAMPLE_ID={external_sample_id} "
                        f"in ROI {roi}: {', '.join(missing_suffixes)}."
                    ),
                )
            )
    return issues, checked


def _precheck_manifest_groups(rows: Sequence[ManifestRow]) -> List[PrecheckIssue]:
    issues: List[PrecheckIssue] = []

    grouped_rows: Dict[Tuple[str, ...], List[ManifestRow]] = defaultdict(list)
    for row in rows:
        grouped_rows[merge_grouping_key(row)].append(row)
    for entries in grouped_rows.values():
        first = entries[0]
        try:
            if should_merge_rows(entries):
                _composite_sample_id, sample_name, _sample_prefix, _unused = build_sample_context(
                    first
                )
                if first.unit.lane == "0":
                    raise CommandError(f"Invalid LANE=0 for multi-lane sample: {sample_name}")
                reject_duplicate_multi_lane_sources(entries, sample_name=sample_name)
        except CommandError as exc:
            issues.append(
                _issue_from_exception(
                    first.original,
                    row_number=first.row_number or 0,
                    default_field="multi-lane group",
                    exc=exc,
                )
            )

    sample_concordance_sources: Dict[str, str] = {}
    sample_rows: Dict[str, Dict[str, str]] = {}
    for row in rows:
        sample_id = row.sample.sample_id
        source = row.sample.path_to_concordance
        existing_source = sample_concordance_sources.get(sample_id)
        if existing_source is not None and existing_source != source:
            issues.append(
                _row_issue(
                    row.original,
                    row_number=row.row_number or 0,
                    field=CONCORDANCE_CONTROL_PATH,
                    path=source,
                    message=f"Duplicate SAMPLEID with conflicting concordance source: {sample_id}",
                )
            )
        sample_concordance_sources.setdefault(sample_id, source)

        samples_row = build_samples_row(row, concordance_path=source)
        existing_row = sample_rows.get(sample_id)
        if existing_row is not None and existing_row != samples_row:
            issues.append(
                _row_issue(
                    row.original,
                    row_number=row.row_number or 0,
                    field=SAMPLE_ID,
                    path=sample_id,
                    message=f"Duplicate SAMPLEID with conflicting metadata: {sample_id}",
                )
            )
        sample_rows.setdefault(sample_id, samples_row)

    return issues


def precheck_manifest(
    analysis_samples: Path,
    *,
    reference_s3_uri: str,
    aws_env: Dict[str, str],
    debug: bool,
    manifest_contract: str = "legacy_v11",
) -> Tuple[PrecheckReport, List[ManifestRow]]:
    rows: List[ManifestRow] = []
    issues: List[PrecheckIssue] = []
    samples_checked: set[str] = set()
    rows_checked = 0
    source_objects_checked = 0
    concordance_dirs_checked = 0

    with analysis_samples.open(newline="") as ff:
        reader = csv.DictReader(ff, delimiter="\t")
        if reader.fieldnames is None:
            issues.append(
                PrecheckIssue(
                    row_number=1,
                    sample_id="na",
                    run_id="na",
                    field="header",
                    path=str(analysis_samples),
                    message="Input TSV is missing a header row.",
                )
            )
            report = PrecheckReport(0, 0, 0, 0, tuple(issues))
            return report, rows

        header_fields = [field.strip() for field in reader.fieldnames if field and field.strip()]
        unknown_fields = sorted(set(header_fields) - ALLOWED_MANIFEST_FIELDS)
        required_fields = (
            DAYOA12_MANIFEST_REQUIRED_FIELDS
            if manifest_contract == "dayoa12"
            else MANIFEST_REQUIRED_FIELDS
        )
        missing_fields = [field for field in required_fields if field not in header_fields]
        for field_group, message in (
            (unknown_fields, "Unknown columns in analysis samples manifest"),
            (missing_fields, "Missing required columns"),
        ):
            if not field_group:
                continue
            issues.append(
                PrecheckIssue(
                    row_number=1,
                    sample_id="na",
                    run_id="na",
                    field="header",
                    path=str(analysis_samples),
                    message=f"{message}: {', '.join(field_group)}",
                )
            )
        if issues:
            report = PrecheckReport(0, 0, 0, 0, tuple(issues))
            return report, rows

        for row_number, row in enumerate(reader, start=2):
            if not row:
                continue
            try:
                if manifest_contract == "dayoa12":
                    validate_raw_dayoa12_identities(row, row_number=row_number)
                normalized = normalize_manifest_row(row, row_number=row_number)
            except CommandError as exc:
                placeholder = {key: value or "" for key, value in row.items() if key}
                issues.append(
                    _issue_from_exception(
                        placeholder,
                        row_number=row_number,
                        default_field="manifest row",
                        exc=exc,
                    )
                )
                continue
            if not any(normalized.values()):
                continue

            if manifest_contract == "dayoa12":
                blank_required = [
                    field for field in DAYOA12_NONBLANK_REQUIRED_FIELDS if not normalized.get(field)
                ]
                if blank_required:
                    issues.append(
                        _row_issue(
                            normalized,
                            row_number=row_number,
                            field=blank_required[0],
                            message=(
                                "DayOA 12 source manifests require explicit nonblank values; "
                                f"blank columns: {', '.join(blank_required)}. Use "
                                "`dayoa migrate-manifests` with a reviewed identity map; DYEC "
                                "does not infer identifiers."
                            ),
                        )
                    )
                    continue

            rows_checked += 1
            sample_id = (
                get_entry_value(normalized, SAMPLEID)
                if manifest_contract == "dayoa12"
                else normalise_identifier(get_entry_value(normalized, SAMPLE_ID))
            )
            if sample_id:
                samples_checked.add(sample_id)

            row_issues = collect_manifest_row_issues(
                normalized,
                row_number=row_number,
                reference_s3_uri=reference_s3_uri,
                aws_env=aws_env,
                debug=debug,
                check_access=False,
            )
            issues.extend(row_issues)

            row_has_structural_issues = bool(row_issues)

            for field, path in _source_checks_for_precheck(normalized):
                source_objects_checked += 1
                try:
                    check_source_path(
                        path,
                        reference_s3_uri=reference_s3_uri,
                        aws_env=aws_env,
                        debug=debug,
                    )
                except CommandError as exc:
                    issues.append(
                        _row_issue(
                            normalized,
                            row_number=row_number,
                            field=field,
                            path=path,
                            message=str(exc),
                        )
                    )

            ont_fastq_prefix = get_entry_value(normalized, ONT_FASTQ_PREFIX)
            try:
                directive = normalize_stage_directive(get_entry_value(normalized, STAGE_DIRECTIVE))
            except CommandError:
                directive = ""
            if ont_fastq_prefix and directive != "mounted_readonly":
                try:
                    parse_ont_fastq_prefix(ont_fastq_prefix)
                    can_resolve_ont_prefix = True
                except CommandError:
                    can_resolve_ont_prefix = False
                if can_resolve_ont_prefix:
                    source_objects_checked += 1
                    try:
                        plan = resolve_ont_fastq_prefix_plan(
                            ont_fastq_prefix,
                            flowcell_id=get_entry_value(normalized, ONT_FLOWCELL_ID),
                            aws_env=aws_env,
                            debug=debug,
                        )
                        source_objects_checked += max(len(plan.shards) - 1, 0)
                    except CommandError as exc:
                        issues.append(
                            _row_issue(
                                normalized,
                                row_number=row_number,
                                field=ONT_FASTQ_PREFIX,
                                path=ont_fastq_prefix,
                                message=str(exc),
                            )
                        )

            concordance_field, concordance_source = _concordance_source_field(normalized)
            concordance_accessible = True
            if is_populated_path(concordance_source):
                concordance_dirs_checked += 1
                try:
                    check_source_path(
                        concordance_source,
                        reference_s3_uri=reference_s3_uri,
                        aws_env=aws_env,
                        debug=debug,
                        allow_directory=True,
                    )
                except CommandError as exc:
                    concordance_accessible = False
                    issues.append(
                        _row_issue(
                            normalized,
                            row_number=row_number,
                            field=concordance_field,
                            path=concordance_source,
                            message=str(exc),
                        )
                    )
            if concordance_accessible and is_populated_path(concordance_source):
                giab_issues, giab_checked = _precheck_giab_truth_files(
                    normalized,
                    row_number=row_number,
                    concordance_source=concordance_source,
                    reference_s3_uri=reference_s3_uri,
                    aws_env=aws_env,
                    debug=debug,
                )
                issues.extend(giab_issues)
                source_objects_checked += giab_checked

            if row_has_structural_issues:
                continue

            try:
                rows.append(
                    build_manifest_row(
                        normalized,
                        row_number=row_number,
                        manifest_contract=manifest_contract,
                    )
                )
            except CommandError as exc:
                issues.append(
                    _issue_from_exception(
                        normalized,
                        row_number=row_number,
                        default_field="manifest row",
                        exc=exc,
                    )
                )

    issues.extend(_precheck_manifest_groups(rows))
    if manifest_contract == "dayoa12" and not issues:
        try:
            validate_dayoa12_lineage(rows)
        except CommandError as exc:
            issues.append(
                PrecheckIssue(
                    row_number=1,
                    sample_id="na",
                    run_id="na",
                    field="lineage",
                    path=str(analysis_samples),
                    message=str(exc),
                )
            )
    report = PrecheckReport(
        rows_checked=rows_checked,
        samples_checked=len(samples_checked),
        source_objects_checked=source_objects_checked,
        concordance_dirs_checked=concordance_dirs_checked,
        issues=tuple(issues),
    )
    return report, rows


def format_precheck_success(report: PrecheckReport) -> str:
    return (
        "Precheck passed: "
        f"rows checked={report.rows_checked}, "
        f"samples checked={report.samples_checked}, "
        f"source objects checked={report.source_objects_checked}, "
        f"concordance directories checked={report.concordance_dirs_checked}."
    )


def format_precheck_failure(report: PrecheckReport) -> str:
    lines = [
        "Precheck failed; no files were copied.",
        (
            "Summary: "
            f"rows checked={report.rows_checked}, "
            f"samples checked={report.samples_checked}, "
            f"source objects checked={report.source_objects_checked}, "
            f"concordance directories checked={report.concordance_dirs_checked}."
        ),
        "Blockers:",
    ]
    grouped: Dict[Tuple[int, str, str], List[PrecheckIssue]] = defaultdict(list)
    for issue in report.issues:
        grouped[(issue.row_number, issue.sample_id, issue.run_id)].append(issue)
    for row_number, sample_id, run_id in sorted(grouped):
        lines.append(f"- row {row_number}; SAMPLE_ID={sample_id}; RUN_ID={run_id}")
        for issue in grouped[(row_number, sample_id, run_id)]:
            path_suffix = f"; path={issue.path}" if issue.path else ""
            lines.append(f"  - field={issue.field}{path_suffix}: {issue.message}")
    return "\n".join(lines)


def _row_source_groups(row: Mapping[str, str]) -> set[str]:
    groups: set[str] = set()
    if get_entry_value(row, ILMN_R1_FQ) or get_entry_value(row, ILMN_R2_FQ):
        groups.add("ilmn")
    if get_entry_value(row, CG_R1_FQ) or get_entry_value(row, CG_R2_FQ):
        groups.add("complete_genomics")
    if (
        get_entry_value(row, UG_R1_FQ)
        or get_entry_value(row, UG_R2_FQ)
        or get_entry_value(row, ULTIMA_CRAM)
    ):
        groups.add("ultima")
    if (
        get_entry_value(row, ONT_R1_FQ)
        or get_entry_value(row, ONT_R2_FQ)
        or get_entry_value(row, ONT_FASTQ_PREFIX)
        or get_entry_value(row, ONT_CRAM)
        or get_entry_value(row, ONT_BAM)
    ):
        groups.add("ont")
    if (
        get_entry_value(row, PACBIO_R1_FQ)
        or get_entry_value(row, PACBIO_R2_FQ)
        or get_entry_value(row, PB_BAM)
    ):
        groups.add("pacbio")
    if get_entry_value(row, ROCHE_BAM):
        groups.add("roche")
    return groups


def _data_mode_for_source_groups(groups: set[str], *, row_number: int) -> str:
    mode_by_groups = {
        frozenset({"ilmn"}): "ilmn_solo",
        frozenset({"complete_genomics"}): "complete_genomics_solo",
        frozenset({"ultima"}): "ultima_solo",
        frozenset({"ont"}): "ont_solo",
        frozenset({"pacbio"}): "pacbio_solo",
        frozenset({"roche"}): "roche_solo",
        frozenset({"ilmn", "ont"}): "hybrid_ilmn_ont",
        frozenset({"ultima", "ont"}): "hybrid_ug_ont",
    }
    mode = mode_by_groups.get(frozenset(groups))
    if mode:
        return mode
    detail = ", ".join(sorted(groups)) or "none"
    raise CommandError(f"Row {row_number} has unsupported source group combination: {detail}.")


def detect_manifest_data_modes(analysis_samples: Path) -> List[str]:
    """Return sorted logical data modes from an analysis samples manifest."""

    modes: set[str] = set()
    with analysis_samples.open(newline="") as ff:
        reader = csv.DictReader(ff, delimiter="\t")
        if reader.fieldnames is None:
            raise CommandError("Input TSV is missing a header row")
        header_fields = [field.strip() for field in reader.fieldnames if field and field.strip()]
        unknown_fields = sorted(set(header_fields) - ALLOWED_MANIFEST_FIELDS)
        if unknown_fields:
            raise CommandError(
                "Unknown columns in analysis samples manifest: " + ", ".join(unknown_fields)
            )
        missing_fields = [field for field in MANIFEST_REQUIRED_FIELDS if field not in header_fields]
        if missing_fields:
            raise CommandError(f"Missing required columns: {', '.join(missing_fields)}")

        for row_number, row in enumerate(reader, start=2):
            if not row:
                continue
            normalized = normalize_manifest_row(row, row_number=row_number)
            if not any(normalized.values()):
                continue
            source_groups = _row_source_groups(normalized)
            if not source_groups:
                raise CommandError(
                    f"Row {row_number} does not define any supported data source columns."
                )
            modes.add(_data_mode_for_source_groups(source_groups, row_number=row_number))

    if not modes:
        raise CommandError(f"No data rows found in analysis samples manifest: {analysis_samples}")
    return sorted(modes)


def merge_grouping_key(row: ManifestRow) -> Tuple[str, ...]:
    return (
        row.unit.run_id,
        row.sample.sample_id,
        row.unit.experiment_id,
        row.sample.sample_type,
        row.unit.lib_prep,
        row.unit.seq_vendor,
        row.unit.seq_platform,
    )


def should_merge_rows(entries: Sequence[ManifestRow]) -> bool:
    if len(entries) <= 1:
        return False
    for entry in entries:
        raw_groups = raw_groups_present(entry.original)
        if len(raw_groups) != 1 or raw_groups[0][:2] != (ILMN_R1_FQ, ILMN_R2_FQ):
            return False
        if any(get_entry_value(entry.original, field) for field in ALIGNED_SOURCE_FIELDS):
            return False
        if entry.staging.stage_directive == "pass_through":
            raise CommandError(
                "Multi-lane Illumina inputs require staging and cannot use STAGE_DIRECTIVE=pass_through."
            )
        if entry.staging.stage_directive == "mounted_readonly":
            return False
    return True


def build_sample_context(
    row: ManifestRow,
) -> Tuple[str, str, str, str]:
    composite_sample_id = (
        f"{row.sample.sample_id}-{row.unit.seq_platform}-{row.unit.lib_prep}-"
        f"{row.sample.sample_type}-{row.unit.experiment_id}"
    )
    sample_name = f"{row.unit.run_id}_{composite_sample_id}"
    sample_prefix = f"{row.unit.run_id}_{composite_sample_id}_{row.unit.seqbc_id}_0"
    dest_fsx_dir = sample_prefix
    return composite_sample_id, sample_name, sample_prefix, dest_fsx_dir


def build_ont_fastq_sample_context(
    row: ManifestRow,
    plan: OntFastqPrefixPlan,
) -> Tuple[str, str, str, str]:
    composite_sample_id = (
        f"{row.sample.sample_id}-{row.unit.seq_platform}-{row.unit.lib_prep}-"
        f"{row.sample.sample_type}-{row.unit.experiment_id}"
    )
    sample_name = f"{plan.run_id}_{composite_sample_id}"
    sample_prefix = f"{plan.run_id}_{composite_sample_id}_{plan.flowcell_id}_{plan.tag}_0"
    dest_fsx_dir = sample_prefix
    return composite_sample_id, sample_name, sample_prefix, dest_fsx_dir


def emit_single_raw_group(
    row: ManifestRow,
    *,
    spec: Tuple[str, str, str, str],
    dest_fsx_dir: str,
    dest_s3_dir: str,
    reference_s3_uri: str,
    aws_env: Dict[str, str],
    debug: bool,
) -> Tuple[Dict[str, str], List[str]]:
    r1_field, r2_field, unit_r1_field, unit_r2_field = spec
    r1 = get_entry_value(row.sources, r1_field)
    r2 = get_entry_value(row.sources, r2_field)
    r1_paths, r2_paths = paired_fastq_path_lists(
        r1,
        r2,
        r1_field=r1_field,
        r2_field=r2_field,
        row_number=row.row_number,
        require_r2=r1_field != ONT_R1_FQ,
    )
    if len(r1_paths) > 1:
        if (r1_field, r2_field) not in {
            (ILMN_R1_FQ, ILMN_R2_FQ),
            (ONT_R1_FQ, ONT_R2_FQ),
        }:
            raise CommandError(
                f"Row {row.row_number} comma-separated FASTQ lists are only supported "
                f"for {ILMN_R1_FQ}/{ILMN_R2_FQ} or {ONT_R1_FQ}/{ONT_R2_FQ}."
            )
        if r2_paths:
            validate_fastq_pair_order(
                r1_paths,
                r2_paths,
                row_number=row.row_number,
                r1_field=r1_field,
                r2_field=r2_field,
            )
    if row.staging.stage_directive in {"pass_through", "mounted_readonly"}:
        for path in r1_paths:
            require_headnode_visible_path(path, field=r1_field)
        for path in r2_paths:
            require_headnode_visible_path(path, field=r2_field)
        return {
            unit_r1_field: ",".join(headnode_visible_path(path) for path in r1_paths),
            unit_r2_field: (
                ",".join(headnode_visible_path(path) for path in r2_paths) if r2_paths else "na"
            ),
        }, []
    if len(r1_paths) > 1:
        remote_r1_paths: List[str] = []
        remote_r2_paths: List[str] = []
        created: List[str] = []
        for index, (r1_path, r2_path) in enumerate(zip(r1_paths, r2_paths), start=1):
            lane_fsx_dir = f"{dest_fsx_dir}/lane{index}"
            lane_s3_dir = f"{dest_s3_dir}/lane{index}"
            remote_r1, remote_r2 = stage_single_lane(
                r1_path,
                r2_path,
                lane_fsx_dir,
                lane_s3_dir,
                reference_s3_uri=reference_s3_uri,
                aws_env=aws_env,
                debug=debug,
            )
            remote_r1_paths.append(remote_r1)
            remote_r2_paths.append(remote_r2)
            created.extend([remote_r1, remote_r2])
        return {
            unit_r1_field: ",".join(remote_r1_paths),
            unit_r2_field: ",".join(remote_r2_paths),
        }, created
    remote_r1, remote_r2 = stage_single_lane(
        r1_paths[0],
        r2_paths[0],
        dest_fsx_dir,
        dest_s3_dir,
        reference_s3_uri=reference_s3_uri,
        aws_env=aws_env,
        debug=debug,
    )
    return {unit_r1_field: remote_r1, unit_r2_field: remote_r2}, [remote_r1, remote_r2]


def emit_aligned_source(
    row: ManifestRow,
    *,
    path_field: str,
    sidecar_suffixes: Sequence[str],
    dest_fsx_dir: str,
    dest_s3_dir: str,
    reference_s3_uri: str,
    aws_env: Dict[str, str],
    debug: bool,
) -> Tuple[str, List[str]]:
    source = get_entry_value(row.sources, path_field)
    if not source:
        return "", []
    if row.staging.stage_directive == "stage_data":
        return stage_path_with_sidecars(
            source,
            sidecar_suffixes=sidecar_suffixes,
            dest_fsx_dir=dest_fsx_dir,
            dest_s3_dir=dest_s3_dir,
            reference_s3_uri=reference_s3_uri,
            aws_env=aws_env,
            debug=debug,
        )
    return headnode_visible_path(source), []


def build_units_row_from_manifest(
    row: ManifestRow,
    *,
    lane_id: str,
    source_values: Mapping[str, str],
) -> Dict[str, str]:
    header = LIBRARIES_HEADER if row.manifest_contract == "dayoa12" else UNITS_HEADER
    units_row = {column: "" for column in header}
    units_row.update(
        {
            "RUNID": row.unit.run_id,
            "SAMPLEID": row.sample.sample_id,
            "EXPERIMENTID": row.unit.experiment_id,
            "LANEID": lane_id,
            "BARCODEID": row.unit.seqbc_id,
            "LIBPREP": row.unit.lib_prep,
            "SEQ_VENDOR": row.unit.seq_vendor,
            "SEQ_PLATFORM": row.unit.seq_platform,
            "SUBSAMPLE_PCT": row.staging.subsample_pct,
            "BWA_KMER": row.units_passthrough.get(BWA_KMER) or "19",
        }
    )
    if row.manifest_contract == "dayoa12":
        units_row.update(
            {
                ANALYSIS_UNIT_UID: row.unit.analysis_unit_uid,
                LIBRARY_EUID: row.unit.library_euid,
                INFLECTION_DELIVERY_ID: row.unit.inflection_delivery_id,
                LIBRARY_COMMENT: row.unit.library_comment,
                "SR_VCF_PATH": get_entry_value(row.original, "SR_VCF_PATH"),
                "LR_VCF_PATH": get_entry_value(row.original, "LR_VCF_PATH"),
                "AMPLIFICATION_TYPE": get_entry_value(row.original, "AMPLIFICATION_TYPE"),
                "ALIGNED_REF_UID": get_entry_value(row.original, "ALIGNED_REF_UID"),
                "MERGE_SINGLE": get_entry_value(row.original, "MERGE_SINGLE"),
            }
        )
    else:
        units_row["SAMPLEUSE"] = row.units_passthrough.get(SAMPLEUSE) or (
            "posControl" if row.sample.is_pos_ctrl == "true" else "sample"
        )
    for field in MANIFEST_UNITS_PASSTHROUGH_FIELDS:
        if row.manifest_contract == "dayoa12" and field == SAMPLEUSE:
            continue
        value = row.units_passthrough.get(field, "")
        if value:
            units_row[field] = value
    units_row.update(source_values)
    return units_row


def build_samples_row(
    row: ManifestRow,
    *,
    concordance_path: str,
) -> Dict[str, str]:
    if row.manifest_contract == "dayoa12":
        return {
            SAMPLEID: row.sample.sample_id,
            SAMPLE_EUID: row.sample.sample_euid,
            SPECIMEN_ID: row.sample.specimen_id,
            SAMPLECLASS: row.sample.sample_class,
            SAMPLE_TYPE: row.sample.sample_type,
            SAMPLEUSE: row.sample.sample_use,
            ORDER_TYPE: row.sample.order_type,
            "CONCORDANCE_CONTROL_PATH": concordance_path,
            "IS_POSITIVE_CONTROL": row.sample.is_pos_ctrl,
            "IS_NEGATIVE_CONTROL": row.sample.is_neg_ctrl,
            TUM_NRM_SAMPLEID_MATCH: row.sample.tum_nrm_sampleid_match,
            EXTERNAL_SAMPLE_ID: row.sample.external_sample_id,
            IDDNA_UID: row.sample.iddna_uid,
            TRUTH_DATA_DIR: concordance_path,
            SAMPLE_COMMENT: row.sample.sample_comment,
        }
    return {
        "SAMPLEID": row.sample.sample_id,
        "SAMPLESOURCE": row.sample.sample_source,
        "SAMPLECLASS": row.sample.sample_class,
        "BIOLOGICAL_SEX": row.sample.biological_sex,
        "CONCORDANCE_CONTROL_PATH": concordance_path,
        "IS_POSITIVE_CONTROL": row.sample.is_pos_ctrl,
        "IS_NEGATIVE_CONTROL": row.sample.is_neg_ctrl,
        "SAMPLE_TYPE": row.sample.sample_type,
        "TUM_NRM_SAMPLEID_MATCH": row.sample.tum_nrm_sampleid_match,
        "EXTERNAL_SAMPLE_ID": row.sample.external_sample_id or "na",
        "N_X": row.sample.n_x,
        "N_Y": row.sample.n_y,
        "TRUTH_DATA_DIR": concordance_path,
    }


def process_samples(
    analysis_samples: Path,
    stage: StagePaths,
    *,
    reference_s3_uri: str,
    aws_env: Dict[str, str],
    debug: bool,
    rows: Sequence[ManifestRow],
) -> Tuple[List[Dict[str, str]], List[Dict[str, str]], List[str], List[str]]:
    grouped_rows: Dict[Tuple[str, ...], List[ManifestRow]] = defaultdict(list)
    for row in rows:
        grouped_rows[merge_grouping_key(row)].append(row)

    samples_rows: Dict[str, Dict[str, str]] = {}
    units_rows: List[Dict[str, str]] = []
    created_files: List[str] = []
    run_ids: set[str] = set()
    sample_concordance_sources: Dict[str, str] = {}
    sample_concordance_paths: Dict[str, str] = {}
    staged_raw_pairs: Dict[Tuple[str, str, str, str, str], Dict[str, str]] = {}
    staged_ont_prefixes: Dict[Tuple[str, str], Dict[str, str]] = {}
    staged_aligned_sources: Dict[Tuple[str, str, str, Tuple[str, ...]], str] = {}

    def staged_concordance_for_sample(
        entry: ManifestRow,
        *,
        concordance_fsx: str,
        concordance_s3: str,
    ) -> Tuple[str, List[str]]:
        concordance_source = entry.sample.path_to_concordance
        sample_id = entry.sample.sample_id
        existing_source = sample_concordance_sources.get(sample_id)
        if existing_source is not None:
            if existing_source != concordance_source:
                raise CommandError(
                    f"Duplicate SAMPLEID with conflicting concordance source: {sample_id}"
                )
            return sample_concordance_paths[sample_id], []

        concordance_path = stage_concordance(
            concordance_source,
            concordance_fsx,
            concordance_s3,
            reference_s3_uri=reference_s3_uri,
            aws_env=aws_env,
            debug=debug,
        )
        sample_concordance_sources[sample_id] = concordance_source
        sample_concordance_paths[sample_id] = concordance_path
        staged_files = (
            [concordance_path] if concordance_path.startswith(stage.remote_fsx_root) else []
        )
        return concordance_path, staged_files

    processed_groups: set[Tuple[str, ...]] = set()
    for row in rows:
        key = merge_grouping_key(row)
        if key in processed_groups:
            continue
        processed_groups.add(key)
        entries = grouped_rows[key]

        _composite_sample_id, sample_name, sample_prefix, _unused = build_sample_context(row)
        dest_fsx_dir = f"{stage.remote_fsx_stage}/{sample_prefix}"
        dest_s3_dir = f"{stage.remote_s3_stage}/{sample_prefix}"

        if should_merge_rows(entries):
            first = entries[0]
            if first.unit.lane == "0":
                raise CommandError(f"Invalid LANE=0 for multi-lane sample: {sample_name}")
            reject_duplicate_multi_lane_sources(entries, sample_name=sample_name)
            r1_files = [get_entry_value(entry.sources, ILMN_R1_FQ) for entry in entries]
            r2_files = [get_entry_value(entry.sources, ILMN_R2_FQ) for entry in entries]
            remote_r1, remote_r2 = stage_multi_lane(
                r1_files,
                r2_files,
                sample_prefix,
                dest_fsx_dir,
                dest_s3_dir,
                reference_s3_uri=reference_s3_uri,
                aws_env=aws_env,
                debug=debug,
            )
            source_values = {
                "ILMN_R1_PATH": remote_r1,
                "ILMN_R2_PATH": remote_r2,
            }
            created_files.extend([remote_r1, remote_r2])
            lane_id = "0"
            manifest_for_units = first
            concordance_fsx = dest_fsx_dir + "/concordance_data"
            concordance_s3 = dest_s3_dir + "/concordance_data"
            concordance_path, staged_concordance_files = staged_concordance_for_sample(
                first,
                concordance_fsx=concordance_fsx,
                concordance_s3=concordance_s3,
            )
            created_files.extend(staged_concordance_files)
            units_rows.append(
                build_units_row_from_manifest(
                    manifest_for_units,
                    lane_id=lane_id,
                    source_values=source_values,
                )
            )
            samples_row = build_samples_row(manifest_for_units, concordance_path=concordance_path)
            sample_id = manifest_for_units.sample.sample_id
            existing = samples_rows.get(sample_id)
            if existing and existing != samples_row:
                raise CommandError(f"Duplicate SAMPLEID with conflicting metadata: {sample_id}")
            samples_rows[sample_id] = samples_row
            run_ids.add(manifest_for_units.unit.run_id)
            continue

        for entry in entries:
            _composite_sample_id, sample_name, sample_prefix, _unused = build_sample_context(entry)
            ont_fastq_prefix = get_entry_value(entry.sources, ONT_FASTQ_PREFIX)
            ont_plan: Optional[OntFastqPrefixPlan] = None
            if ont_fastq_prefix:
                ont_plan = resolve_ont_fastq_prefix_plan(
                    ont_fastq_prefix,
                    flowcell_id=get_entry_value(entry.sources, ONT_FLOWCELL_ID),
                    aws_env=aws_env,
                    debug=debug,
                )
                _composite_sample_id, sample_name, sample_prefix, _unused = (
                    build_ont_fastq_sample_context(entry, ont_plan)
                )
            dest_fsx_dir = f"{stage.remote_fsx_stage}/{sample_prefix}"
            dest_s3_dir = f"{stage.remote_s3_stage}/{sample_prefix}"
            source_values: Dict[str, str] = {}

            for spec in raw_groups_present(entry.original):
                r1_field, r2_field, _unit_r1_field, _unit_r2_field = spec
                raw_cache_key = (
                    entry.staging.stage_directive,
                    r1_field,
                    r2_field,
                    get_entry_value(entry.sources, r1_field),
                    get_entry_value(entry.sources, r2_field),
                )
                if raw_cache_key in staged_raw_pairs:
                    staged_source_values = staged_raw_pairs[raw_cache_key]
                    staged_created_files = []
                else:
                    staged_source_values, staged_created_files = emit_single_raw_group(
                        entry,
                        spec=spec,
                        dest_fsx_dir=dest_fsx_dir,
                        dest_s3_dir=dest_s3_dir,
                        reference_s3_uri=reference_s3_uri,
                        aws_env=aws_env,
                        debug=debug,
                    )
                    staged_raw_pairs[raw_cache_key] = staged_source_values
                source_values.update(staged_source_values)
                created_files.extend(staged_created_files)

            if ont_plan:
                ont_cache_key = (
                    ont_plan.prefix,
                    ont_plan.flowcell_id,
                )
                if ont_cache_key in staged_ont_prefixes:
                    staged_source_values = staged_ont_prefixes[ont_cache_key]
                    staged_created_files = []
                else:
                    staged_r1_path, staged_created_files = stage_ont_fastq_prefix(
                        ont_plan.prefix,
                        flowcell_id=ont_plan.flowcell_id,
                        sample_prefix=sample_prefix,
                        dest_fsx_dir=dest_fsx_dir,
                        dest_s3_dir=dest_s3_dir,
                        reference_s3_uri=reference_s3_uri,
                        plan=ont_plan,
                        aws_env=aws_env,
                        debug=debug,
                    )
                    staged_source_values = {
                        "RUNID": ont_plan.run_id,
                        "BARCODEID": ont_plan.tag,
                        "ONT_R1_PATH": staged_r1_path,
                        "ONT_R2_PATH": "na",
                    }
                    staged_ont_prefixes[ont_cache_key] = staged_source_values
                source_values.update(staged_source_values)
                created_files.extend(staged_created_files)

            for path_field, sidecars in (
                (ULTIMA_CRAM, (".crai",)),
                (ONT_CRAM, (".crai",)),
                (
                    PB_BAM,
                    (
                        (".csi",)
                        if get_entry_value(entry.units_passthrough, PB_BAM_ALIGNER).lower() == "pb"
                        else ()
                    ),
                ),
                (ONT_BAM, ()),
                (ROCHE_BAM, ()),
            ):
                aligned_cache_key = (
                    entry.staging.stage_directive,
                    path_field,
                    get_entry_value(entry.sources, path_field),
                    tuple(sidecars),
                )
                if aligned_cache_key in staged_aligned_sources:
                    staged_path = staged_aligned_sources[aligned_cache_key]
                    staged_created = []
                else:
                    staged_path, staged_created = emit_aligned_source(
                        entry,
                        path_field=path_field,
                        sidecar_suffixes=sidecars,
                        dest_fsx_dir=dest_fsx_dir,
                        dest_s3_dir=dest_s3_dir,
                        reference_s3_uri=reference_s3_uri,
                        aws_env=aws_env,
                        debug=debug,
                    )
                    if staged_path:
                        staged_aligned_sources[aligned_cache_key] = staged_path
                if staged_path:
                    source_values[path_field] = staged_path
                created_files.extend(staged_created)

            concordance_fsx = dest_fsx_dir + "/concordance_data"
            concordance_s3 = dest_s3_dir + "/concordance_data"
            concordance_path, staged_concordance_files = staged_concordance_for_sample(
                entry,
                concordance_fsx=concordance_fsx,
                concordance_s3=concordance_s3,
            )
            created_files.extend(staged_concordance_files)

            units_rows.append(
                build_units_row_from_manifest(
                    entry,
                    lane_id=ont_plan.flowcell_id if ont_plan else entry.unit.lane,
                    source_values=source_values,
                )
            )

            samples_row = build_samples_row(entry, concordance_path=concordance_path)
            sample_id = entry.sample.sample_id
            existing = samples_rows.get(sample_id)
            if existing and existing != samples_row:
                raise CommandError(f"Duplicate SAMPLEID with conflicting metadata: {sample_id}")
            samples_rows[sample_id] = samples_row
            run_ids.add(ont_plan.run_id if ont_plan else entry.unit.run_id)

    sorted_samples = [samples_rows[sample_id] for sample_id in sorted(samples_rows.keys())]
    return sorted_samples, units_rows, sorted(created_files), sorted(run_ids)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    analysis_samples = Path(args.analysis_samples).expanduser().resolve()
    if not analysis_samples.exists():
        raise CommandError(f"Analysis samples TSV not found: {analysis_samples}")

    aws_config = AwsConfig(profile=ensure_profile(args.profile), region=args.region)
    aws_env = build_aws_env(aws_config)

    s3_role_uris = S3RoleUris(
        reference_s3_uri=args.reference_s3_uri,
        control_data_s3_uri=args.control_data_s3_uri,
        stage_s3_uri=args.stage_s3_uri,
        fsx_s3_uri_maps=parse_fsx_s3_uri_maps(args.fsx_s3_uri_map),
    )
    stage = build_stage_paths(args.stage_target, args.stage_s3_uri)
    run_metric_specs = parse_run_metric_staging_specs(args.run_metric_staging)
    precheck_report, prechecked_rows = precheck_manifest(
        analysis_samples,
        reference_s3_uri=s3_role_uris,
        aws_env=aws_env,
        debug=args.debug,
        manifest_contract=args.manifest_contract,
    )
    if precheck_report.issues:
        print(format_precheck_failure(precheck_report), file=sys.stderr)
        return 1
    print(format_precheck_success(precheck_report))
    run_metric_files = precheck_run_metrics(
        run_metric_specs,
        reference_s3_uri=s3_role_uris,
        aws_env=aws_env,
        debug=args.debug,
    )
    if run_metric_specs:
        print(format_run_metric_precheck_success(run_metric_specs, run_metric_files))
    if args.precheck_only:
        return 0

    if args.config_only:
        if run_metric_specs:
            print(
                "--config-only cannot be used with --run-metric-staging; run metrics require a remote stage.",
                file=sys.stderr,
            )
            return 1
        stage_data_rows = [
            row.row_number for row in prechecked_rows if row.staging.stage_directive == "stage_data"
        ]
        if stage_data_rows:
            print(
                "--config-only requires all rows to use STAGE_DIRECTIVE=pass_through or "
                f"mounted_readonly; stage_data rows: {stage_data_rows}.",
                file=sys.stderr,
            )
            return 1

    if not args.config_only:
        ensure_remote_stage_writable(stage, aws_env=aws_env, debug=args.debug)

    samples_rows, units_rows, created_files, _run_ids = process_samples(
        analysis_samples,
        stage,
        reference_s3_uri=s3_role_uris,
        aws_env=aws_env,
        debug=args.debug,
        rows=prechecked_rows,
    )
    created_files.extend(
        stage_run_metrics(
            run_metric_files,
            stage,
            reference_s3_uri=s3_role_uris,
            aws_env=aws_env,
            debug=args.debug,
        )
    )

    timestamp = stage.remote_stage_name.replace("remote_stage_", "")
    specimens_filename = f"{timestamp}_specimens.tsv"
    samples_filename = f"{timestamp}_samples.tsv"
    libraries_filename = f"{timestamp}_libraries.tsv"
    units_filename = f"{timestamp}_units.tsv"

    if args.config_dir:
        config_dir = Path(args.config_dir).expanduser()
    else:
        config_dir = analysis_samples.parent

    samples_path = config_dir / samples_filename
    generated_sample_header = (
        DAYOA12_SAMPLES_HEADER if args.manifest_contract == "dayoa12" else SAMPLES_HEADER
    )
    generated_library_header = (
        LIBRARIES_HEADER if args.manifest_contract == "dayoa12" else UNITS_HEADER
    )
    unique_samples_rows = deduplicate_rows(samples_rows, generated_sample_header)
    normalise_units_paths(units_rows)
    if args.manifest_contract == "dayoa12":
        if all(row.get(ANALYSIS_UNIT_UID) for row in units_rows):
            units_rows = unique_entity_rows(
                units_rows,
                key_field=ANALYSIS_UNIT_UID,
                entity="library",
            )
        else:
            # DayOA constructs blank ANALYSIS_UNIT_UID values from the exact
            # library fields after loading.  Preserve those rows byte-for-byte
            # here and only collapse exact duplicates.
            units_rows = deduplicate_rows(units_rows, generated_library_header)
    write_tsv(samples_path, generated_sample_header, unique_samples_rows)

    specimens_path: Optional[Path] = None
    libraries_path: Optional[Path] = None
    units_path: Optional[Path] = None
    if args.manifest_contract == "dayoa12":
        specimens_path = config_dir / specimens_filename
        libraries_path = config_dir / libraries_filename
        write_tsv(specimens_path, SPECIMENS_HEADER, build_specimens_rows(prechecked_rows))
        write_tsv(libraries_path, generated_library_header, units_rows)
    else:
        units_path = config_dir / units_filename
        write_tsv(units_path, generated_library_header, units_rows)

    if args.config_only:
        print("Generated configuration files:")
        if specimens_path is not None:
            print(f"  specimens.tsv -> {specimens_path}")
        print(f"  samples.tsv -> {samples_path}")
        if libraries_path is not None:
            print(f"  libraries.tsv -> {libraries_path}")
        if units_path is not None:
            print(f"  units.tsv   -> {units_path}")
        return 0

    remote_specimens_path = f"{stage.remote_s3_stage}/{specimens_filename}"
    remote_samples_path = f"{stage.remote_s3_stage}/{samples_filename}"
    remote_libraries_path = f"{stage.remote_s3_stage}/{libraries_filename}"
    remote_units_path = f"{stage.remote_s3_stage}/{units_filename}"

    aws_copy(str(samples_path), remote_samples_path, aws_env=aws_env, debug=args.debug)
    if args.manifest_contract == "dayoa12":
        assert specimens_path is not None and libraries_path is not None
        aws_copy(str(specimens_path), remote_specimens_path, aws_env=aws_env, debug=args.debug)
        aws_copy(str(libraries_path), remote_libraries_path, aws_env=aws_env, debug=args.debug)
    else:
        assert units_path is not None
        aws_copy(str(units_path), remote_units_path, aws_env=aws_env, debug=args.debug)

    staging_mount = create_staged_prefix_mount(
        stage,
        cluster_name=args.cluster_name,
        fsx_file_system_id=args.fsx_file_system_id,
        profile=aws_config.profile,
        region=aws_config.region,
        timeout_seconds=args.staging_mount_timeout_seconds,
    )

    print("Remote staging completed successfully.")
    print(f"Remote FSx stage directory: {headnode_visible_path(stage.remote_fsx_stage)}")
    if staging_mount is not None:
        print(f"Staging DRA: {staging_mount.association_id}")
        print(f"Staging DRA lifecycle: {staging_mount.lifecycle}")
    print(f"Staged files ({len(created_files)}):")
    for path in created_files:
        print(f"  {headnode_visible_path(path)}")
    print("Generated configuration files:")
    if args.manifest_contract == "dayoa12":
        print(f"  specimens.tsv -> {remote_specimens_path}")
    print(f"  samples.tsv -> {remote_samples_path}")
    if args.manifest_contract == "dayoa12":
        print(f"  libraries.tsv -> {remote_libraries_path}")
    else:
        print(f"  units.tsv   -> {remote_units_path}")
    return 0


if __name__ == "__main__":  # pragma: no cover - manual execution
    try:
        raise SystemExit(main())
    except CommandError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)
