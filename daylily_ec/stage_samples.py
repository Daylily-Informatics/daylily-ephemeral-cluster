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
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence, Tuple


RUN_ID = "RUN_ID"
SAMPLE_ID = "SAMPLE_ID"
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
BWA_KMER = "BWA_KMER"
DEEP_MODEL = "DEEP_MODEL"

S3_MULTIPART_MIN_PART_SIZE = 5 * 1024 * 1024
ONT_FASTQ_SHARD_RE = re.compile(
    r"^(?P<flowcell_id>[^_]+)_pass_(?P<tag>barcode[0-9]+|unclassified)_"
    r"(?P<protocol_run>[^_]+)_(?P<acquisition>[^_]+)_(?P<shard_index>[0-9]+)\.fastq\.gz$"
)

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


@dataclass(frozen=True)
class UnitMetadata:
    run_id: str
    experiment_id: str
    lib_prep: str
    seq_vendor: str
    seq_platform: str
    lane: str
    seqbc_id: str


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


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Stage analysis samples into FSx from the local workstation.",
    )
    parser.add_argument("analysis_samples", help="Path to analysis_samples.tsv")
    parser.add_argument(
        "--stage-target",
        default="/data/staged_sample_data",
        help="FSx staging base directory (default: %(default)s)",
    )
    parser.add_argument(
        "--reference-bucket",
        required=True,
        help="S3 URI (s3://bucket[/prefix]) mapped to the FSx data repository",
    )
    parser.add_argument(
        "--config-dir",
        help="Directory to place generated samples.tsv/units.tsv (default: TSV dir)",
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
        "--debug",
        action="store_true",
        help="Print AWS CLI commands before execution",
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
    if not stage_target.startswith("/data"):
        raise CommandError("Stage target must be an FSx path (expected to start with /data).")
    return stage_target.rstrip("/")


def build_stage_paths(stage_target: str, bucket_uri: str) -> StagePaths:
    stage_target = normalise_stage_target(stage_target)
    timestamp = dt.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    remote_stage_name = f"remote_stage_{timestamp}"
    remote_fsx_stage = f"{stage_target}/{remote_stage_name}"

    bucket, prefix = parse_s3_uri(bucket_uri.rstrip("/"))
    prefix = prefix.rstrip("/")
    fsx_relative = stage_target.lstrip("/")
    if prefix:
        remote_s3_stage = f"s3://{bucket}/{prefix}/{fsx_relative}/{remote_stage_name}"
    else:
        remote_s3_stage = f"s3://{bucket}/{fsx_relative}/{remote_stage_name}"
    return StagePaths(
        remote_fsx_root=stage_target,
        remote_stage_name=remote_stage_name,
        remote_fsx_stage=remote_fsx_stage,
        remote_s3_stage=remote_s3_stage,
    )


def headnode_visible_path(path: str) -> str:
    if path == "/data":
        return "/fsx/data"
    if path.startswith("/data/"):
        return f"/fsx{path}"
    return path


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
            raise CommandError(f"S3 listing for {prefix_uri} was truncated without a continuation token.")
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
    return (
        path == "/fsx/data"
        or path.startswith("/fsx/data/")
        or path == "/data"
        or path.startswith("/data/")
    )


def build_reference_uri(path: str, reference_bucket: str) -> str:
    if path == "/data":
        relative = "data"
    elif path.startswith("/data/"):
        relative = path.lstrip("/")
    elif path.startswith("/fsx/"):
        relative = path[len("/fsx/") :]
    else:
        raise CommandError(f"Path is not in the FSx data namespace: {path}")
    return f"{reference_bucket.rstrip('/')}/{relative.lstrip('/')}"


def check_source_path(
    path: str,
    *,
    reference_bucket: str,
    aws_env: Dict[str, str],
    debug: bool,
    allow_directory: bool = False,
) -> None:
    if not path or path.lower() == "na":
        return
    if path.startswith("s3://"):
        check_s3_path(path, aws_env=aws_env, debug=debug)
        return
    if is_headnode_visible_path(path):
        check_s3_path(
            build_reference_uri(path, reference_bucket),
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
    return value.replace("_", "-")


def normalise_run_id(value: str) -> str:
    return normalise_identifier(value).replace(".", "-")


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
        if raw == "false" and is_giab_control(entry):
            return "true"
        return raw
    return "true" if is_giab_control(entry) else "false"


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


def source_copy_reference(source: str, *, reference_bucket: str) -> str:
    if source.startswith("s3://"):
        return source
    if is_headnode_visible_path(source):
        return build_reference_uri(source, reference_bucket)
    return os.path.expanduser(source)


def parse_ont_fastq_prefix(prefix_uri: str) -> Tuple[str, str, str, str]:
    prefix_uri = normalise_s3_prefix_uri(prefix_uri)
    bucket, key = parse_s3_uri(prefix_uri)
    parts = [part for part in key.strip("/").split("/") if part]
    if len(parts) < 2 or parts[-2] != "fastq_pass" or not parts[-1]:
        raise CommandError(
            f"{ONT_FASTQ_PREFIX} must point to an S3 fastq_pass/<tag>/ prefix: {prefix_uri}"
        )
    run_id_candidates = [
        part for part in parts[:-2] if re.match(r"^[0-9]{8}_ONT(?:_|$)", part)
    ]
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
        raise CommandError(f"ONT final summary for {flowcell_id} does not show basecalling enabled.")
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
        unexpected = sorted(os.path.basename(obj.key) for obj in objects if obj not in fastq_objects)
        raise CommandError(
            f"{ONT_FASTQ_PREFIX} {prefix_uri} contains non-FASTQ objects: {', '.join(unexpected)}"
        )
    shards = [
        parse_ont_fastq_shard(obj, expected_tag=tag, run_id=run_id) for obj in fastq_objects
    ]

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
    reference_bucket: str,
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
                resolved.append(build_reference_uri(source, reference_bucket))
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
                concat_sources.append(S3ObjectSummary(uri=shard.uri, key=shard.key, size=shard.size))
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
    reference_bucket: str,
    aws_env: Dict[str, str],
    debug: bool,
) -> str:
    source = source.strip()
    if not source or source.lower() == "na" or is_headnode_visible_path(source):
        return headnode_visible_path(source) if source else "na"
    copy_source = source_copy_reference(source, reference_bucket=reference_bucket)
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
    reference_bucket: str,
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
        source_copy_reference(r1, reference_bucket=reference_bucket),
        remote_r1_s3,
        aws_env=aws_env,
        debug=debug,
    )
    aws_copy(
        source_copy_reference(r2, reference_bucket=reference_bucket),
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
    reference_bucket: str,
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
        reference_bucket=reference_bucket,
        aws_env=aws_env,
        debug=debug,
    )
    try:
        r2_sources, r2_uploaded = ensure_s3_objects(
            r2_files,
            dest_s3_dir=dest_s3_dir,
            sample_prefix=f"{sample_prefix}_R2",
            reference_bucket=reference_bucket,
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
    reference_bucket: Optional[str] = None,
    plan: Optional[OntFastqPrefixPlan] = None,
    aws_env: Dict[str, str],
    debug: bool,
) -> Tuple[str, List[str]]:
    del reference_bucket
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
    reference_bucket: str,
    aws_env: Dict[str, str],
    debug: bool,
) -> Tuple[str, List[str]]:
    filename = os.path.basename(source)
    remote_fsx = f"{dest_fsx_dir}/{filename}"
    remote_s3 = f"{dest_s3_dir}/{filename}"
    aws_copy(
        source_copy_reference(source, reference_bucket=reference_bucket),
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
    reference_bucket: str,
    aws_env: Dict[str, str],
    debug: bool,
) -> Tuple[str, List[str]]:
    remote_path, created = stage_path(
        source,
        dest_fsx_dir=dest_fsx_dir,
        dest_s3_dir=dest_s3_dir,
        reference_bucket=reference_bucket,
        aws_env=aws_env,
        debug=debug,
    )
    for suffix in sidecar_suffixes:
        sidecar = f"{source}{suffix}"
        _, sidecar_created = stage_path(
            sidecar,
            dest_fsx_dir=dest_fsx_dir,
            dest_s3_dir=dest_s3_dir,
            reference_bucket=reference_bucket,
            aws_env=aws_env,
            debug=debug,
        )
        created.extend(sidecar_created)
    return remote_path, created


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


def normalise_units_paths(rows: Sequence[Dict[str, str]]) -> None:
    for row in rows:
        for field, value in list(row.items()):
            if not isinstance(value, str):
                continue
            if value.startswith("/data/"):
                row[field] = f"/fsx{value}"
            elif value == "/data":
                row[field] = "/fsx/data"


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
    if directive in {"stage_data", "pass_through"}:
        return directive
    raise CommandError(
        f"Unsupported STAGE_DIRECTIVE '{value}'. Supported values are stage_data, pass_through, or blank."
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
    reference_bucket: str,
    aws_env: Dict[str, str],
    debug: bool,
) -> None:
    for suffix in sidecar_suffixes:
        check_source_path(
            f"{path}{suffix}",
            reference_bucket=reference_bucket,
            aws_env=aws_env,
            debug=debug,
        )


def validate_manifest_row(
    normalized: Mapping[str, str],
    *,
    row_number: int,
    reference_bucket: str,
    aws_env: Dict[str, str],
    debug: bool,
) -> None:
    raw_groups = raw_groups_present(normalized)
    ont_fastq_prefix = get_entry_value(normalized, ONT_FASTQ_PREFIX)
    directive = normalize_stage_directive(get_entry_value(normalized, STAGE_DIRECTIVE))
    aligned_fields = [
        field for field in ALIGNED_SOURCE_FIELDS if get_entry_value(normalized, field)
    ]
    if not raw_groups and not ont_fastq_prefix and not aligned_fields:
        raise CommandError(f"Row {row_number} does not define any supported data source columns.")
    if ont_fastq_prefix:
        vendor = normalise_identifier(get_entry_value(normalized, SEQ_VENDOR)).upper()
        if vendor != "ONT":
            raise CommandError(f"Row {row_number} requires {SEQ_VENDOR}=ONT for {ONT_FASTQ_PREFIX}.")
        ont_conflicts = [
            field
            for field in (ONT_R1_FQ, ONT_R2_FQ, ONT_CRAM, ONT_BAM)
            if get_entry_value(normalized, field)
        ]
        if raw_groups or aligned_fields or ont_conflicts:
            raise CommandError(
                f"Row {row_number} must not combine {ONT_FASTQ_PREFIX} with other staged data source columns."
            )
        if directive == "pass_through":
            raise CommandError(f"Row {row_number} requires STAGE_DIRECTIVE=stage_data for {ONT_FASTQ_PREFIX}.")
        parse_ont_fastq_prefix(ont_fastq_prefix)

    for r1_field, r2_field, _unit_r1, _unit_r2 in raw_groups:
        r1_value = get_entry_value(normalized, r1_field)
        r2_value = get_entry_value(normalized, r2_field)
        if not r1_value or not r2_value:
            raise CommandError(f"Row {row_number} must populate both {r1_field} and {r2_field}.")
        check_source_path(
            r1_value,
            reference_bucket=reference_bucket,
            aws_env=aws_env,
            debug=debug,
        )
        check_source_path(
            r2_value,
            reference_bucket=reference_bucket,
            aws_env=aws_env,
            debug=debug,
        )

    concordance_source = resolve_concordance_source(normalized)
    if is_populated_path(concordance_source):
        check_source_path(
            concordance_source,
            reference_bucket=reference_bucket,
            aws_env=aws_env,
            debug=debug,
            allow_directory=True,
        )

    if get_entry_value(normalized, ULTIMA_CRAM):
        check_source_path(
            get_entry_value(normalized, ULTIMA_CRAM),
            reference_bucket=reference_bucket,
            aws_env=aws_env,
            debug=debug,
        )
        validate_sidecar_paths(
            get_entry_value(normalized, ULTIMA_CRAM),
            sidecar_suffixes=(".crai",),
            reference_bucket=reference_bucket,
            aws_env=aws_env,
            debug=debug,
        )
        aligner = get_entry_value(normalized, ULTIMA_CRAM_ALIGNER).lower()
        if aligner not in {"ug", "hyb"}:
            raise CommandError(
                f"Row {row_number} requires {ULTIMA_CRAM_ALIGNER} to be one of ug, hyb when {ULTIMA_CRAM} is populated."
            )
        if directive != "stage_data":
            require_headnode_visible_path(
                get_entry_value(normalized, ULTIMA_CRAM), field=ULTIMA_CRAM
            )

    if get_entry_value(normalized, ONT_CRAM):
        check_source_path(
            get_entry_value(normalized, ONT_CRAM),
            reference_bucket=reference_bucket,
            aws_env=aws_env,
            debug=debug,
        )
        validate_sidecar_paths(
            get_entry_value(normalized, ONT_CRAM),
            sidecar_suffixes=(".crai",),
            reference_bucket=reference_bucket,
            aws_env=aws_env,
            debug=debug,
        )
        aligner = get_entry_value(normalized, ONT_CRAM_ALIGNER).lower()
        if aligner != "ont":
            raise CommandError(
                f"Row {row_number} requires {ONT_CRAM_ALIGNER}=ont when {ONT_CRAM} is populated."
            )
        if directive != "stage_data":
            require_headnode_visible_path(get_entry_value(normalized, ONT_CRAM), field=ONT_CRAM)

    if get_entry_value(normalized, PB_BAM):
        check_source_path(
            get_entry_value(normalized, PB_BAM),
            reference_bucket=reference_bucket,
            aws_env=aws_env,
            debug=debug,
        )
        aligner = get_entry_value(normalized, PB_BAM_ALIGNER).lower()
        if aligner not in {"pb", "sentmm2"}:
            raise CommandError(
                f"Row {row_number} requires {PB_BAM_ALIGNER} to be one of pb, sentmm2 when {PB_BAM} is populated."
            )
        if aligner == "pb":
            validate_sidecar_paths(
                get_entry_value(normalized, PB_BAM),
                sidecar_suffixes=(".csi",),
                reference_bucket=reference_bucket,
                aws_env=aws_env,
                debug=debug,
            )
        if directive != "stage_data":
            require_headnode_visible_path(get_entry_value(normalized, PB_BAM), field=PB_BAM)

    if get_entry_value(normalized, ONT_BAM):
        check_source_path(
            get_entry_value(normalized, ONT_BAM),
            reference_bucket=reference_bucket,
            aws_env=aws_env,
            debug=debug,
        )
        aligner = get_entry_value(normalized, ONT_BAM_ALIGNER).lower()
        if aligner != "sentmm2ont":
            raise CommandError(
                f"Row {row_number} requires {ONT_BAM_ALIGNER}=sentmm2ont when {ONT_BAM} is populated."
            )
        if directive != "stage_data":
            require_headnode_visible_path(get_entry_value(normalized, ONT_BAM), field=ONT_BAM)

    if get_entry_value(normalized, ROCHE_BAM):
        check_source_path(
            get_entry_value(normalized, ROCHE_BAM),
            reference_bucket=reference_bucket,
            aws_env=aws_env,
            debug=debug,
        )
        aligner = get_entry_value(normalized, ROCHE_BAM_ALIGNER).lower()
        if aligner != "roche":
            raise CommandError(
                f"Row {row_number} requires {ROCHE_BAM_ALIGNER}=roche when {ROCHE_BAM} is populated."
            )
        if directive != "stage_data":
            require_headnode_visible_path(get_entry_value(normalized, ROCHE_BAM), field=ROCHE_BAM)


def build_manifest_row(normalized: Mapping[str, str]) -> ManifestRow:
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
        sample_id=normalise_identifier(get_entry_value(normalized, SAMPLE_ID)),
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
    )
    vendor = normalise_identifier(get_entry_value(normalized, SEQ_VENDOR)).upper()
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
    )


def load_manifest_rows(
    analysis_samples: Path,
    *,
    reference_bucket: str,
    aws_env: Dict[str, str],
    debug: bool,
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
        missing_fields = [field for field in MANIFEST_REQUIRED_FIELDS if field not in header_fields]
        if missing_fields:
            raise CommandError(f"Missing required columns: {', '.join(missing_fields)}")

        for row_number, row in enumerate(reader, start=2):
            if not row:
                continue
            normalized = normalize_manifest_row(row, row_number=row_number)
            if not any(normalized.values()):
                continue
            validate_manifest_row(
                normalized,
                row_number=row_number,
                reference_bucket=reference_bucket,
                aws_env=aws_env,
                debug=debug,
            )
            rows.append(build_manifest_row(normalized))

    return rows


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
    reference_bucket: str,
    aws_env: Dict[str, str],
    debug: bool,
) -> Tuple[Dict[str, str], List[str]]:
    r1_field, r2_field, unit_r1_field, unit_r2_field = spec
    r1 = get_entry_value(row.sources, r1_field)
    r2 = get_entry_value(row.sources, r2_field)
    if row.staging.stage_directive == "pass_through":
        require_headnode_visible_path(r1, field=r1_field)
        require_headnode_visible_path(r2, field=r2_field)
        return {
            unit_r1_field: headnode_visible_path(r1),
            unit_r2_field: headnode_visible_path(r2),
        }, []
    remote_r1, remote_r2 = stage_single_lane(
        r1,
        r2,
        dest_fsx_dir,
        dest_s3_dir,
        reference_bucket=reference_bucket,
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
    reference_bucket: str,
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
            reference_bucket=reference_bucket,
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
    units_row = {column: "" for column in UNITS_HEADER}
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
            "SAMPLEUSE": row.units_passthrough.get(SAMPLEUSE)
            or ("posControl" if row.sample.is_pos_ctrl == "true" else "sample"),
            "BWA_KMER": row.units_passthrough.get(BWA_KMER) or "19",
        }
    )
    for field in MANIFEST_UNITS_PASSTHROUGH_FIELDS:
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
    reference_bucket: str,
    aws_env: Dict[str, str],
    debug: bool,
) -> Tuple[List[Dict[str, str]], List[Dict[str, str]], List[str], List[str]]:
    rows = load_manifest_rows(
        analysis_samples,
        reference_bucket=reference_bucket,
        aws_env=aws_env,
        debug=debug,
    )

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
            reference_bucket=reference_bucket,
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
                reference_bucket=reference_bucket,
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
                        reference_bucket=reference_bucket,
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
                        reference_bucket=reference_bucket,
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
                    (".csi",)
                    if get_entry_value(entry.units_passthrough, PB_BAM_ALIGNER).lower() == "pb"
                    else (),
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
                        reference_bucket=reference_bucket,
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

    stage = build_stage_paths(args.stage_target, args.reference_bucket)
    ensure_remote_stage_writable(stage, aws_env=aws_env, debug=args.debug)

    samples_rows, units_rows, created_files, _run_ids = process_samples(
        analysis_samples,
        stage,
        reference_bucket=args.reference_bucket,
        aws_env=aws_env,
        debug=args.debug,
    )

    timestamp = stage.remote_stage_name.replace("remote_stage_", "")
    samples_filename = f"{timestamp}_samples.tsv"
    units_filename = f"{timestamp}_units.tsv"

    if args.config_dir:
        config_dir = Path(args.config_dir).expanduser()
    else:
        config_dir = analysis_samples.parent

    samples_path = config_dir / samples_filename
    units_path = config_dir / units_filename
    unique_samples_rows = deduplicate_rows(samples_rows, SAMPLES_HEADER)
    normalise_units_paths(units_rows)

    write_tsv(samples_path, SAMPLES_HEADER, unique_samples_rows)
    write_tsv(units_path, UNITS_HEADER, units_rows)

    remote_samples_path = f"{stage.remote_s3_stage}/{samples_filename}"
    remote_units_path = f"{stage.remote_s3_stage}/{units_filename}"

    aws_copy(str(samples_path), remote_samples_path, aws_env=aws_env, debug=args.debug)
    aws_copy(str(units_path), remote_units_path, aws_env=aws_env, debug=args.debug)

    print("Remote staging completed successfully.")
    print(f"Remote FSx stage directory: {headnode_visible_path(stage.remote_fsx_stage)}")
    print(f"Staged files ({len(created_files)}):")
    for path in created_files:
        print(f"  {headnode_visible_path(path)}")
    print("Generated configuration files:")
    print(f"  samples.tsv -> {remote_samples_path}")
    print(f"  units.tsv   -> {remote_units_path}")
    return 0


if __name__ == "__main__":  # pragma: no cover - manual execution
    try:
        raise SystemExit(main())
    except CommandError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)
