#!/usr/bin/env python3
"""Durable forked DayOA command-catalog validation driver.

This driver implements the ledger in this directory. It is intentionally
stateful through events.jsonl so interrupted runs can resume without guessing.
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
import time
from pathlib import Path
from typing import Any

from daylily_ec.aws.ssm import (
    SsmCommandFailedError,
    resolve_headnode_instance_id,
    run_shell,
    wait_for_ssm_online,
)
from daylily_ec.repositories import load_repository_catalog


ROOT = Path(__file__).resolve().parents[3]
LEDGER_ROOT = Path(__file__).resolve().parent
STAMP = LEDGER_ROOT.name.split("_", 1)[0]
CATALOG_PATH = ROOT / "config" / "daylily_pipeline_command_catalog.yaml"
EVENTS_PATH = LEDGER_ROOT / "events.jsonl"
REPORT_PATH = LEDGER_ROOT / "report.md"
LOG_ROOT = LEDGER_ROOT / "logs"
GENERATED_CONFIG_ROOT = LEDGER_ROOT / "generated_sample_configs"
RUN_CONTEXT_ROOT = LEDGER_ROOT / "run_contexts"

PROFILE = "lsmc"
REGION = "us-west-2"
CLUSTER = "forked"
EXECUTING_ENTITY = "forked"
REPOSITORY = "daylily-omics-analysis"
EXPORT_ROOT = "s3://lsmc-ssf-sequencing-data/derived/analysis_results/forked"
DAYOA_GIT_REF = ""
ANALYSIS_ID_PREFIX = "ccvforked_j100_jitter_r5"

REFERENCE_S3_URI = "s3://lsmc-dayoa-references-usw2"
CONTROL_DATA_S3_URI = "s3://lsmc-dayoa-control-data-usw2"
STAGE_S3_URI = "s3://lsmc-ssf-sequencing-data/staged_external_data"
STAGE_TARGET = "/fsx/staging/staged_external_sequencing_data"

MIN_BCL_FREE_BYTES = 6 * 1024**4
COMMAND_TERMINAL_PHASES = {"SUCCESS", "FAILED", "BLOCKED"}

SOURCE_MANIFESTS = {
    "illumina_hg003_5x": ROOT
    / "docs/plans/20260526T224018Z_blahab44_inputs/illumina_hg003_5x.tsv",
    "illumina_hg002_kitchen": ROOT
    / "docs/plans/20260526T223700Z_goodole3_inputs/illumina_0p1x_kitchensink.tsv",
    "ultima_hg003_5x": ROOT
    / "docs/plans/20260526T224018Z_blahab44_inputs/ultima_hg003_5x.tsv",
    "ont_hg003_5x": ROOT
    / "docs/plans/20260526T224018Z_blahab44_inputs/ont_hg003_5x.tsv",
    "pacbio_hg003_5x": ROOT
    / "docs/plans/20260526T224018Z_blahab44_inputs/pacbio_hg003_5x.tsv",
    "roche_hg003_5x": ROOT
    / "docs/plans/20260526T224018Z_blahab44_inputs/roche_hg003_5x.tsv",
    "hybrid_ilmn_ont_hg003_5x5x": ROOT
    / "docs/plans/20260526T224018Z_blahab44_inputs/hybrid_ilmn_ont_hg003_5x5x.tsv",
    "hybrid_ultima_ont_hg003_5x5x": ROOT
    / "docs/plans/20260526T224018Z_blahab44_inputs/hybrid_ultima_ont_hg003_5x5x.tsv",
    "complete_genomics_mgi_hg003": ROOT
    / "docs/plans/20260526T224018Z_blahab44_inputs/complete_genomics_mgi_hg003_candidate_blocked.tsv",
}

COMMAND_SOURCE_ALIAS = {
    "illumina_snv_alignstats": "illumina_hg003_5x",
    "illumina_snv_alignstats_relatedness_vep_multiqc": "illumina_hg003_5x",
    "illumina_hg002_kitchensink_multiqc": "illumina_hg002_kitchen",
    "ultima_snv_alignstats": "ultima_hg003_5x",
    "ultima_snv_alignstats_kitchensink": "ultima_hg003_5x",
    "ont_snv_alignstats": "ont_hg003_5x",
    "ont_snv_alignstats_kitchensink": "ont_hg003_5x",
    "pacbio_snv_alignstats": "pacbio_hg003_5x",
    "roche_snv_alignstats": "roche_hg003_5x",
    "hybrid_ilmn_ont_snv": "hybrid_ilmn_ont_hg003_5x5x",
    "hybrid_ilmn_ont_snv_kitchensink": "hybrid_ilmn_ont_hg003_5x5x",
    "inflection-bjuice-product-v0.1": "hybrid_ilmn_ont_hg003_5x5x",
    "hybrid_ultima_ont_snv": "hybrid_ultima_ont_hg003_5x5x",
    "complete_genomics_mgi_snv_concordance": "complete_genomics_mgi_hg003",
}

RUN_CONTEXT_SOURCES = {
    "illumina": ROOT / "docs/plans/20260526T223700Z_goodole3_inputs/illumina_run_context.tsv",
    "ont": ROOT / "docs/plans/20260526T223700Z_goodole3_inputs/ont_run_context.tsv",
    "ultima": ROOT
    / "docs/plans/20260526T223700Z_goodole3_inputs/ultima_run_context_candidate.tsv",
}

COMMAND_RUN_CONTEXT = {
    "illumina_run_qc": "illumina",
    "illumina_bclconvert": "illumina",
    "illumina_run_qc_bclconvert": "illumina",
    "ont_run_qc": "ont",
    "ultima_run_qc": "ultima",
}

RUN_MOUNT_GROUPS = {
    "illumina": {
        "mount_id": "20260514_LH01106_0009_B23TVLGLT4",
        "commands": ["illumina_run_qc", "illumina_bclconvert", "illumina_run_qc_bclconvert"],
    },
    "ont": {
        "mount_id": "20260513_ONT_HG003",
        "commands": ["ont_run_qc"],
    },
    "ultima": {
        "mount_id": "602221-20260417_2346",
        "commands": ["ultima_run_qc"],
    },
}

BCL_COMMANDS = {"illumina_bclconvert", "illumina_run_qc_bclconvert"}

COMMAND_ORDER = [
    "simple-test",
    "illumina_snv_alignstats",
    "illumina_snv_alignstats_relatedness_vep_multiqc",
    "illumina_hg002_kitchensink_multiqc",
    "ultima_snv_alignstats",
    "ultima_snv_alignstats_kitchensink",
    "ont_snv_alignstats",
    "ont_snv_alignstats_kitchensink",
    "pacbio_snv_alignstats",
    "roche_snv_alignstats",
    "hybrid_ilmn_ont_snv",
    "hybrid_ilmn_ont_snv_kitchensink",
    "inflection-bjuice-product-v0.1",
    "hybrid_ultima_ont_snv",
    "complete_genomics_mgi_snv_concordance",
    "illumina_run_qc",
    "illumina_bclconvert",
    "illumina_run_qc_bclconvert",
    "ont_run_qc",
    "ultima_run_qc",
]

SAMPLE_BATCHES = [
    [
        "illumina_snv_alignstats",
        "illumina_snv_alignstats_relatedness_vep_multiqc",
    ],
    [
        "illumina_hg002_kitchensink_multiqc",
        "ultima_snv_alignstats",
    ],
    [
        "ultima_snv_alignstats_kitchensink",
        "ont_snv_alignstats",
    ],
    [
        "ont_snv_alignstats_kitchensink",
        "pacbio_snv_alignstats",
    ],
    [
        "roche_snv_alignstats",
        "hybrid_ilmn_ont_snv",
    ],
    [
        "hybrid_ilmn_ont_snv_kitchensink",
        "inflection-bjuice-product-v0.1",
    ],
    ["hybrid_ultima_ont_snv", "complete_genomics_mgi_snv_concordance"],
]


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def dyec() -> str:
    executable = shutil.which("dyec")
    if not executable:
        raise RuntimeError("dyec is not on PATH; run `source ./activate` from the DYEC repo root.")
    return executable


def load_events() -> list[dict[str, Any]]:
    if not EVENTS_PATH.exists():
        return []
    events: list[dict[str, Any]] = []
    for line in EVENTS_PATH.read_text(encoding="utf-8").splitlines():
        if line.strip():
            events.append(json.loads(line))
    return events


def append_event(event: dict[str, Any]) -> None:
    LOG_ROOT.mkdir(parents=True, exist_ok=True)
    EVENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {"ts": utc_now(), **event}
    with EVENTS_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")


def events_for(command_id: str | None = None, phase: str | None = None) -> list[dict[str, Any]]:
    events = load_events()
    if command_id is not None:
        events = [event for event in events if event.get("command_id") == command_id]
    if phase is not None:
        events = [event for event in events if event.get("phase") == phase]
    return events


def event_matches_current_launch(event: dict[str, Any]) -> bool:
    session_name = str(event.get("analysis_id") or event.get("session_name") or "")
    return bool(session_name.startswith(f"{ANALYSIS_ID_PREFIX}_{STAMP}_"))


def last_event(
    command_id: str,
    phase: str | None = None,
    status: str | None = None,
    *,
    current_launch_only: bool = False,
) -> dict[str, Any] | None:
    for event in reversed(load_events()):
        if event.get("command_id") != command_id:
            continue
        if phase is not None and event.get("phase") != phase:
            continue
        if status is not None and event.get("status") != status:
            continue
        if current_launch_only and not event_matches_current_launch(event):
            continue
        return event
    return None


def log_path(label: str, suffix: str) -> Path:
    existing = len(list(LOG_ROOT.glob("*.cmd.json"))) + 1
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", label).strip("_")[:140] or "command"
    return LOG_ROOT / f"{existing:05d}_{safe}.{suffix}"


def run_cmd(argv: list[str], *, label: str, timeout: int | None = None) -> subprocess.CompletedProcess[str]:
    LOG_ROOT.mkdir(parents=True, exist_ok=True)
    cmd_log = log_path(label, "cmd.json")
    stdout_log = cmd_log.with_suffix(".stdout.txt")
    stderr_log = cmd_log.with_suffix(".stderr.txt")
    env = os.environ.copy()
    env["AWS_PROFILE"] = PROFILE
    started = utc_now()
    proc = subprocess.run(
        argv,
        cwd=ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
    )
    finished = utc_now()
    stdout_log.write_text(proc.stdout, encoding="utf-8")
    stderr_log.write_text(proc.stderr, encoding="utf-8")
    cmd_log.write_text(
        json.dumps(
            {
                "argv": argv,
                "cwd": str(ROOT),
                "started": started,
                "finished": finished,
                "returncode": proc.returncode,
                "stdout_log": str(stdout_log),
                "stderr_log": str(stderr_log),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return proc


def require_file(path: Path) -> None:
    if not path.is_file():
        raise RuntimeError(f"Required file is missing: {path}")


def safe_command_id(command_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", command_id)


def analysis_id_for(command_id: str, *, dry_run: bool) -> str:
    ordinal = COMMAND_ORDER.index(command_id) + 1
    suffix = "_dryrun" if dry_run else ""
    return f"{ANALYSIS_ID_PREFIX}_{STAMP}_{ordinal:02d}_{safe_command_id(command_id)}{suffix}"


def parse_generated_paths(stdout: str, config_dir: Path) -> tuple[Path, Path]:
    samples_match = re.search(r"samples\.tsv\s*->\s*(\S+)", stdout)
    units_match = re.search(r"units\.tsv\s*->\s*(\S+)", stdout)
    if samples_match and units_match:
        return Path(samples_match.group(1)), Path(units_match.group(1))
    samples_candidates = sorted(config_dir.glob("*_samples.tsv"), key=lambda path: path.stat().st_mtime)
    units_candidates = sorted(config_dir.glob("*_units.tsv"), key=lambda path: path.stat().st_mtime)
    if not samples_candidates or not units_candidates:
        raise RuntimeError(f"Could not find generated samples/units TSVs in {config_dir}")
    return samples_candidates[-1], units_candidates[-1]


def verify_slim_mounted_config(samples_path: Path, units_path: Path) -> None:
    problems: list[str] = []
    for path in (samples_path, units_path):
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.reader(handle, delimiter="\t")
            for row_number, row in enumerate(reader, start=1):
                for cell in row:
                    for match in re.findall(r"/fsx/[^\t,; ]+", cell):
                        cleaned = match.rstrip("/")
                        if cleaned.startswith("/fsx/staging"):
                            problems.append(f"{path}:{row_number}: staging path {cleaned}")
                        elif cleaned.startswith("/fsx/references"):
                            continue
                        elif cleaned.startswith("/fsx/control_data/genomic_data/organism_reads_slim"):
                            continue
                        else:
                            problems.append(f"{path}:{row_number}: non-slim mounted path {cleaned}")
    if problems:
        detail = "\n".join(problems[:40])
        raise RuntimeError(f"Generated config contains disallowed FSx paths:\n{detail}")


def ensure_sample_config(alias: str) -> tuple[Path, Path]:
    prior = last_event(alias, "sample_config", "SUCCESS")
    if prior:
        samples_path = Path(str(prior["samples_tsv"]))
        units_path = Path(str(prior["units_tsv"]))
        if samples_path.is_file() and units_path.is_file():
            verify_slim_mounted_config(samples_path, units_path)
            return samples_path, units_path

    manifest = SOURCE_MANIFESTS[alias]
    require_file(manifest)
    config_dir = GENERATED_CONFIG_ROOT / alias
    config_dir.mkdir(parents=True, exist_ok=True)
    argv = [
        dyec(),
        "samples",
        "stage",
        str(manifest),
        "--reference-s3-uri",
        REFERENCE_S3_URI,
        "--control-data-s3-uri",
        CONTROL_DATA_S3_URI,
        "--stage-s3-uri",
        STAGE_S3_URI,
        "--stage-target",
        STAGE_TARGET,
        "--config-dir",
        str(config_dir),
        "--profile",
        PROFILE,
        "--region",
        REGION,
        "--cluster",
        CLUSTER,
        "--config-only",
    ]
    proc = run_cmd(argv, label=f"{alias}_sample_config", timeout=1800)
    if proc.returncode != 0:
        append_event(
            {
                "command_id": alias,
                "phase": "sample_config",
                "status": "FAILED",
                "returncode": proc.returncode,
                "stderr_tail": proc.stderr[-4000:],
            }
        )
        raise RuntimeError(f"sample config generation failed for {alias}")
    samples_path, units_path = parse_generated_paths(proc.stdout, config_dir)
    verify_slim_mounted_config(samples_path, units_path)
    append_event(
        {
            "command_id": alias,
            "phase": "sample_config",
            "status": "SUCCESS",
            "manifest": str(manifest),
            "samples_tsv": str(samples_path),
            "units_tsv": str(units_path),
        }
    )
    return samples_path, units_path


def read_single_run_context(path: Path) -> dict[str, str]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    if len(rows) != 1:
        raise RuntimeError(f"Expected exactly one run-context row in {path}; got {len(rows)}")
    return {key: value for key, value in rows[0].items()}


def ensure_run_context(group: str) -> Path:
    source = RUN_CONTEXT_SOURCES[group]
    require_file(source)
    RUN_CONTEXT_ROOT.mkdir(parents=True, exist_ok=True)
    dest = RUN_CONTEXT_ROOT / source.name
    if not dest.exists() or dest.read_text(encoding="utf-8") != source.read_text(encoding="utf-8"):
        dest.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    return dest


def cluster_describe() -> subprocess.CompletedProcess[str]:
    return run_cmd(
        [
            dyec(),
            "--json",
            "cluster",
            "describe",
            "--profile",
            PROFILE,
            "--region",
            REGION,
            "--cluster",
            CLUSTER,
        ],
        label="gate0_cluster_describe",
        timeout=300,
    )


def gate0_preflight() -> bool:
    describe = cluster_describe()
    if describe.returncode != 0:
        append_event(
            {
                "command_id": "_gate0",
                "phase": "preflight",
                "status": "BLOCKED",
                "reason": "cluster describe failed",
                "returncode": describe.returncode,
                "stderr_tail": describe.stderr[-4000:],
                "stdout_tail": describe.stdout[-2000:],
            }
        )
        write_report()
        return False

    target = resolve_headnode_instance_id(CLUSTER, REGION, profile=PROFILE)
    wait_for_ssm_online(target.instance_id, REGION, profile=PROFILE, timeout=300, poll_interval=5)
    remote_script = """set -euo pipefail
date -u
id
hostname -f
df -h /fsx
df -B1 /fsx
test -d /fsx/references
test -r /fsx/references
printf '\\n===== references =====\\n'
find /fsx/references -maxdepth 1 -mindepth 1 -type d | sort | head -20
printf '\\n===== slurm =====\\n'
sinfo -o '%P|%a|%l|%D|%t|%N'
squeue -u ubuntu -o '%i|%P|%j|%u|%T|%M|%D|%R'
"""
    try:
        result = run_shell(
            target.instance_id,
            REGION,
            remote_script,
            profile=PROFILE,
            as_user="ubuntu",
            timeout=300,
            poll_interval=5,
            comment="forked command catalog validation Gate 0 preflight",
        )
    except SsmCommandFailedError as exc:
        result = exc.result
        append_event(
            {
                "command_id": "_gate0",
                "phase": "preflight",
                "status": "BLOCKED",
                "reason": "headnode read-only preflight failed",
                "returncode": result.response_code,
                "stdout_tail": result.stdout[-4000:],
                "stderr_tail": result.stderr[-4000:],
            }
        )
        write_report()
        return False

    (LOG_ROOT / "gate0_headnode_preflight.stdout.txt").write_text(result.stdout, encoding="utf-8")
    (LOG_ROOT / "gate0_headnode_preflight.stderr.txt").write_text(result.stderr, encoding="utf-8")
    append_event(
        {
            "command_id": "_gate0",
            "phase": "preflight",
            "status": "SUCCESS",
            "headnode_instance_id": target.instance_id,
            "cluster_describe_stdout": describe.stdout[:20000],
            "headnode_stdout_log": str(LOG_ROOT / "gate0_headnode_preflight.stdout.txt"),
            "headnode_stderr_log": str(LOG_ROOT / "gate0_headnode_preflight.stderr.txt"),
        }
    )
    write_report()
    return True


def ensure_run_mount(group: str) -> Path:
    context_path = ensure_run_context(group)
    context = read_single_run_context(context_path)
    mount_id = context["MOUNT_ID"]
    prior = last_event(mount_id, "mount", "SUCCESS")
    if prior:
        return context_path

    list_proc = run_cmd(
        [
            dyec(),
            "--json",
            "mounts",
            "list",
            "--profile",
            PROFILE,
            "--region",
            REGION,
            "--cluster",
            CLUSTER,
        ],
        label=f"{mount_id}_mounts_list",
        timeout=300,
    )
    if list_proc.returncode != 0:
        append_event(
            {
                "command_id": mount_id,
                "phase": "mount",
                "status": "FAILED",
                "reason": "mounts list failed",
                "returncode": list_proc.returncode,
                "stderr_tail": list_proc.stderr[-4000:],
            }
        )
        raise RuntimeError(f"mounts list failed before verifying {mount_id}")

    if mount_id not in list_proc.stdout:
        create_proc = run_cmd(
            [
                dyec(),
                "--json",
                "mounts",
                "create",
                context["SOURCE_S3_URI"],
                "--profile",
                PROFILE,
                "--region",
                REGION,
                "--cluster",
                CLUSTER,
                "--platform",
                context["PLATFORM"],
                "--mount-id",
                mount_id,
                "--run-id",
                context["RUNID"],
                "--file-system-path",
                f"/run_dir_mounts/{mount_id}",
                "--read-only",
                "--batch-import-metadata-on-create",
                "--auto-import",
                "NEW,CHANGED",
                "--wait",
                "--timeout-seconds",
                "5400",
            ],
            label=f"{mount_id}_mount_create",
            timeout=3000,
        )
        if create_proc.returncode != 0 and "overlaps with existing" not in create_proc.stderr:
            append_event(
                {
                    "command_id": mount_id,
                    "phase": "mount",
                    "status": "FAILED",
                    "reason": "mount create failed",
                    "returncode": create_proc.returncode,
                    "stderr_tail": create_proc.stderr[-4000:],
                }
            )
            raise RuntimeError(f"mount create failed for {mount_id}")

    verify_proc = run_cmd(
        [
            dyec(),
            "--json",
            "mounts",
            "verify",
            "--profile",
            PROFILE,
            "--region",
            REGION,
            "--cluster",
            CLUSTER,
            "--mount-id",
            mount_id,
            "--platform",
            context["PLATFORM"],
            "--timeout-seconds",
            "600",
        ],
        label=f"{mount_id}_mount_verify",
        timeout=900,
    )
    if verify_proc.returncode != 0:
        append_event(
            {
                "command_id": mount_id,
                "phase": "mount",
                "status": "FAILED",
                "reason": "mount verify failed",
                "returncode": verify_proc.returncode,
                "stderr_tail": verify_proc.stderr[-4000:],
            }
        )
        raise RuntimeError(f"mount verify failed for {mount_id}")

    append_event(
        {
            "command_id": mount_id,
            "phase": "mount",
            "status": "SUCCESS",
            "context_file": str(context_path),
            "mount_id": mount_id,
            "source_s3_uri": context["SOURCE_S3_URI"],
            "run_dir": context["RUN_DIR"],
        }
    )
    return context_path


def fsx_free_bytes() -> int:
    target = resolve_headnode_instance_id(CLUSTER, REGION, profile=PROFILE)
    result = run_shell(
        target.instance_id,
        REGION,
        "set -euo pipefail\ndf -B1 /fsx | awk 'NR==2 {print $4}'\n",
        profile=PROFILE,
        as_user="ubuntu",
        timeout=120,
        poll_interval=5,
        comment="Read /fsx free bytes",
    )
    return int(result.stdout.strip().splitlines()[-1])


def force_catalog_flags(rendered: str) -> str:
    if "dy-r" not in rendered:
        raise RuntimeError(f"Rendered command lacks dy-r: {rendered}")
    updated = re.sub(r"(?<!\S)-j\s+\d+", "-j 100", rendered)
    updated = re.sub(r"(?<!\S)-j\d+", "-j 100", updated)
    updated = re.sub(r"(?<!\S)--jobs\s+\d+", "-j 100", updated)
    updated = re.sub(r"(?<!\S)--jobs=\d+", "-j 100", updated)
    updated = re.sub(r"(?<!\S)--cores\s+\d+", "-j 100", updated)
    updated = re.sub(r"(?<!\S)--cores=\d+", "-j 100", updated)
    if not re.search(r"(?<!\S)-j\s+100(?!\S)", updated):
        updated = f"{updated} -j 100"
    if not re.search(r"(?<!\S)-p(?!\S)", updated):
        updated = f"{updated} -p"
    if not re.search(r"(?<!\S)-k(?!\S)", updated):
        updated = f"{updated} -k"
    if not re.search(r"(?<!\S)--sentieon-start-jitter(?!\S)", updated):
        updated = f"{updated} --sentieon-start-jitter"
    updated = re.sub(r"(?<!\S)--rerun-triggers=\S+", "--rerun-triggers mtime", updated)
    updated = re.sub(r"(?<!\S)--rerun-triggers\s+\S+", "--rerun-triggers mtime", updated)
    if not re.search(r"(?<!\S)--rerun-triggers\s+mtime(?!\S)", updated):
        updated = f"{updated} --rerun-triggers mtime"
    if re.search(r"(?<!\S)--conda-prefix(?:=|\s)", updated):
        raise RuntimeError(
            "Catalog command already sets --conda-prefix; cannot force isolated Conda prefix"
        )
    if not re.search(r"(?<!\S)--isolated-conda-prefix(?!\S)", updated):
        updated = f"{updated} --isolated-conda-prefix"
    return updated


def dy_r_command(command: Any, raw_dy_command: str) -> str:
    """Render a DayOA command through dy-r only.

    The catalog still records legacy bin/day_run strings for many commands.
    For this validation run, submit only the supported DayOA alias sequence.
    """
    stripped = raw_dy_command.strip()
    if stripped.startswith("source dyoainit;"):
        if "dy-r" not in stripped:
            raise RuntimeError(f"Catalog command initializes DayOA without dy-r: {command.command_id}")
        dy_r_parts = [part.strip() for part in stripped.split(";") if part.strip().startswith("dy-r ")]
        if len(dy_r_parts) != 1:
            raise RuntimeError(f"Source-initialized catalog command must contain exactly one dy-r segment: {stripped}")
        return force_catalog_flags(
            f"source dyoainit; dy-a slurm {command.genome}; {dy_r_parts[0]}"
        )
    if not stripped.startswith("bin/day_run "):
        raise RuntimeError(
            f"Refusing to submit non-dy-r/non-bin-day-run command for {command.command_id}: {raw_dy_command}"
        )
    dy_r_args = stripped.removeprefix("bin/day_run ").strip()
    return force_catalog_flags(f"source dyoainit; dy-a slurm {command.genome}; dy-r {dy_r_args}")


def force_launch_argv_to_dy_r(command: Any, argv: list[str]) -> tuple[list[str], str]:
    if "--dy-command" not in argv:
        raise RuntimeError(f"Launch argv for {command.command_id} does not include --dy-command")
    dy_idx = argv.index("--dy-command") + 1
    if dy_idx >= len(argv):
        raise RuntimeError(f"Launch argv for {command.command_id} has empty --dy-command")
    rendered = dy_r_command(command, argv[dy_idx])
    if "bin/day_run" in rendered or "snakemake" in rendered:
        raise RuntimeError(f"Rendered command still violates dy-r-only contract: {rendered}")
    argv = list(argv)
    argv[dy_idx] = rendered
    return argv, rendered


def launch_workflow(command: Any, *, dry_run: bool, samples_file: Path | None, units_file: Path | None, run_context_file: Path | None) -> str:
    if not DAYOA_GIT_REF:
        raise RuntimeError("--dayoa-git-ref is required before launching catalog workflows")
    command_id = str(command.command_id)
    phase = "dryrun" if dry_run else "live"
    success = last_event(command_id, phase, "SUCCESS", current_launch_only=True)
    if success:
        return str(success["session_name"])
    running = last_event(
        command_id,
        phase,
        "LIVE_RUNNING" if not dry_run else "DRYRUN_RUNNING",
        current_launch_only=True,
    )
    if running:
        return str(running["session_name"])

    analysis_id = analysis_id_for(command_id, dry_run=dry_run)
    export_uri = None if dry_run else f"{EXPORT_ROOT}/{analysis_id}/"
    argv = [
        dyec(),
        *command.launch_argv(
            analysis_id=analysis_id,
            executing_entity=EXECUTING_ENTITY,
            git_tag=DAYOA_GIT_REF,
            profile=PROFILE,
            region=REGION,
            cluster=CLUSTER,
            session_name=analysis_id,
            run_context_file=str(run_context_file) if run_context_file else None,
            samples_file=str(samples_file) if samples_file else None,
            units_file=str(units_file) if units_file else None,
            dry_run=dry_run,
            skip_project_check=True,
            export_destination_s3_uri=export_uri,
            export_trigger="on-success" if export_uri else "none",
            delete_on_export_success=bool(export_uri),
        ),
    ]
    argv, rendered_dy_command = force_launch_argv_to_dy_r(command, argv)
    proc = run_cmd(argv, label=f"{command_id}_{phase}_launch", timeout=900)
    if proc.returncode != 0:
        append_event(
            {
                "command_id": command_id,
                "phase": phase,
                "status": "FAILED",
                "analysis_id": analysis_id,
                "session_name": analysis_id,
                "returncode": proc.returncode,
                "stderr_tail": proc.stderr[-4000:],
            }
        )
        return ""
    append_event(
        {
            "command_id": command_id,
            "phase": phase,
            "status": "DRYRUN_RUNNING" if dry_run else "LIVE_RUNNING",
            "analysis_id": analysis_id,
            "session_name": analysis_id,
            "git_tag": DAYOA_GIT_REF,
            "genome": str(command.genome),
            "jobs": 100,
            "dy_command": rendered_dy_command,
            "export_uri": export_uri or "",
        }
    )
    return analysis_id


def export_summary(export_uri: str, label: str) -> dict[str, Any]:
    proc = run_cmd(
        ["aws", "s3", "ls", export_uri, "--recursive", "--summarize"],
        label=label,
        timeout=1800,
    )
    payload: dict[str, Any] = {
        "export_uri": export_uri,
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-4000:],
        "stderr_tail": proc.stderr[-4000:],
    }
    if proc.returncode == 0:
        total_objects = re.search(r"Total Objects:\s*(\d+)", proc.stdout)
        total_size = re.search(r"Total Size:\s*(\d+)", proc.stdout)
        if total_objects:
            payload["total_objects"] = int(total_objects.group(1))
        if total_size:
            payload["total_size_bytes"] = int(total_size.group(1))
    return payload


def workflow_status(session_name: str, label: str) -> dict[str, Any] | None:
    proc = run_cmd(
        [
            dyec(),
            "--json",
            "workflow",
            "status",
            "--profile",
            PROFILE,
            "--region",
            REGION,
            "--cluster",
            CLUSTER,
            "--session",
            session_name,
        ],
        label=label,
        timeout=300,
    )
    if proc.returncode != 0:
        return None
    return json.loads(proc.stdout)


def capture_workflow_logs(command_id: str, phase: str, session_name: str) -> None:
    run_cmd(
        [
            dyec(),
            "workflow",
            "logs",
            "--profile",
            PROFILE,
            "--region",
            REGION,
            "--cluster",
            CLUSTER,
            "--session",
            session_name,
            "--lines",
            "240",
        ],
        label=f"{command_id}_{phase}_logs",
        timeout=300,
    )


def wait_for_sessions(
    launched: dict[str, str],
    *,
    phase: str,
    poll_seconds: int,
    timeout_seconds: int,
) -> None:
    deadline = time.monotonic() + timeout_seconds
    pending = dict(launched)
    while pending and time.monotonic() < deadline:
        for command_id, session_name in list(pending.items()):
            status_payload = workflow_status(session_name, f"{command_id}_{phase}_status")
            if not status_payload:
                continue
            exit_code = status_payload.get("exit_code")
            if exit_code is None:
                continue
            capture_workflow_logs(command_id, phase, session_name)
            export_uri = f"{EXPORT_ROOT}/{session_name}/" if phase == "live" else ""
            export_payload = (
                export_summary(export_uri, f"{command_id}_{phase}_export_summary")
                if phase == "live" and int(exit_code) == 0
                else {}
            )
            append_event(
                {
                    "command_id": command_id,
                    "phase": phase,
                    "status": "SUCCESS" if int(exit_code) == 0 else "FAILED",
                    "session_name": session_name,
                    "analysis_id": session_name,
                    "export_uri": export_uri,
                    "export_summary": export_payload,
                    "exit_code": int(exit_code),
                    "status_payload": status_payload,
                }
            )
            pending.pop(command_id, None)
        if pending:
            time.sleep(poll_seconds)
    for command_id, session_name in pending.items():
        append_event(
            {
                "command_id": command_id,
                "phase": phase,
                "status": "BLOCKED",
                "session_name": session_name,
                "analysis_id": session_name,
                "reason": f"{phase} did not reach terminal state within {timeout_seconds}s",
            }
        )


def command_inputs(command_id: str) -> tuple[Path | None, Path | None, Path | None]:
    if command_id in COMMAND_SOURCE_ALIAS:
        return (*ensure_sample_config(COMMAND_SOURCE_ALIAS[command_id]), None)
    if command_id in COMMAND_RUN_CONTEXT:
        context_group = COMMAND_RUN_CONTEXT[command_id]
        return None, None, ensure_run_context(context_group)
    return None, None, None


def command_can_live(command_id: str) -> bool:
    dry = last_event(command_id, "dryrun", "SUCCESS", current_launch_only=True)
    if not dry:
        append_event(
            {
                "command_id": command_id,
                "phase": "live",
                "status": "BLOCKED",
                "reason": "dry-run did not succeed",
            }
        )
        return False
    return True


def run_batch(command_map: dict[str, Any], command_ids: list[str], args: argparse.Namespace) -> None:
    dry_launched: dict[str, str] = {}
    for command_id in command_ids:
        samples, units, context = command_inputs(command_id)
        session = launch_workflow(
            command_map[command_id],
            dry_run=True,
            samples_file=samples,
            units_file=units,
            run_context_file=context,
        )
        if session:
            dry_launched[command_id] = session
    wait_for_sessions(
        dry_launched,
        phase="dryrun",
        poll_seconds=args.poll_seconds,
        timeout_seconds=args.dryrun_timeout_seconds,
    )
    if args.dry_run_only:
        return

    live_launched: dict[str, str] = {}
    for command_id in command_ids:
        if not command_can_live(command_id):
            continue
        samples, units, context = command_inputs(command_id)
        session = launch_workflow(
            command_map[command_id],
            dry_run=False,
            samples_file=samples,
            units_file=units,
            run_context_file=context,
        )
        if session:
            live_launched[command_id] = session
    wait_for_sessions(
        live_launched,
        phase="live",
        poll_seconds=args.poll_seconds,
        timeout_seconds=args.live_timeout_seconds,
    )


def run_single(command_map: dict[str, Any], command_id: str, args: argparse.Namespace) -> None:
    run_batch(command_map, [command_id], args)


def run_bcl_command(command_map: dict[str, Any], command_id: str, args: argparse.Namespace) -> None:
    samples, units, context = command_inputs(command_id)
    dry_session = launch_workflow(
        command_map[command_id],
        dry_run=True,
        samples_file=samples,
        units_file=units,
        run_context_file=context,
    )
    if dry_session:
        wait_for_sessions(
            {command_id: dry_session},
            phase="dryrun",
            poll_seconds=args.poll_seconds,
            timeout_seconds=args.dryrun_timeout_seconds,
        )
    if args.dry_run_only or not command_can_live(command_id):
        return
    free_bytes = fsx_free_bytes()
    append_event(
        {
            "command_id": command_id,
            "phase": "fsx_space_gate",
            "status": "SUCCESS" if free_bytes >= MIN_BCL_FREE_BYTES else "BLOCKED",
            "free_bytes": free_bytes,
            "required_bytes": MIN_BCL_FREE_BYTES,
        }
    )
    if free_bytes < MIN_BCL_FREE_BYTES:
        return
    live_session = launch_workflow(
        command_map[command_id],
        dry_run=False,
        samples_file=samples,
        units_file=units,
        run_context_file=context,
    )
    if live_session:
        wait_for_sessions(
            {command_id: live_session},
            phase="live",
            poll_seconds=args.poll_seconds,
            timeout_seconds=args.live_timeout_seconds,
        )


def run_bcl_batch(command_map: dict[str, Any], command_ids: list[str], args: argparse.Namespace) -> None:
    dry_launched: dict[str, str] = {}
    for command_id in command_ids:
        samples, units, context = command_inputs(command_id)
        session = launch_workflow(
            command_map[command_id],
            dry_run=True,
            samples_file=samples,
            units_file=units,
            run_context_file=context,
        )
        if session:
            dry_launched[command_id] = session
    wait_for_sessions(
        dry_launched,
        phase="dryrun",
        poll_seconds=args.poll_seconds,
        timeout_seconds=args.dryrun_timeout_seconds,
    )
    if args.dry_run_only:
        return
    free_bytes = fsx_free_bytes()
    append_event(
        {
            "command_id": "_bcl_batch",
            "phase": "fsx_space_gate",
            "status": "SUCCESS" if free_bytes >= MIN_BCL_FREE_BYTES else "BLOCKED",
            "free_bytes": free_bytes,
            "required_bytes": MIN_BCL_FREE_BYTES,
            "commands": command_ids,
        }
    )
    if free_bytes < MIN_BCL_FREE_BYTES:
        for command_id in command_ids:
            append_event(
                {
                    "command_id": command_id,
                    "phase": "live",
                    "status": "BLOCKED",
                    "reason": "BCL batch free-space gate failed",
                    "free_bytes": free_bytes,
                    "required_bytes": MIN_BCL_FREE_BYTES,
                }
            )
        return

    live_launched: dict[str, str] = {}
    for command_id in command_ids:
        if not command_can_live(command_id):
            continue
        samples, units, context = command_inputs(command_id)
        session = launch_workflow(
            command_map[command_id],
            dry_run=False,
            samples_file=samples,
            units_file=units,
            run_context_file=context,
        )
        if session:
            live_launched[command_id] = session
    wait_for_sessions(
        live_launched,
        phase="live",
        poll_seconds=args.poll_seconds,
        timeout_seconds=args.live_timeout_seconds,
    )


def parse_requested_commands(command_map: dict[str, Any], raw_commands: str | None) -> list[str] | None:
    if raw_commands is None:
        return None
    requested = [command_id.strip() for command_id in raw_commands.split(",") if command_id.strip()]
    if not requested:
        raise RuntimeError("--commands was provided but no command IDs were parsed")
    unknown = [command_id for command_id in requested if command_id not in command_map]
    if unknown:
        raise RuntimeError("Unknown command IDs for --commands: " + ", ".join(unknown))
    duplicates = sorted({command_id for command_id in requested if requested.count(command_id) > 1})
    if duplicates:
        raise RuntimeError("Duplicate command IDs for --commands: " + ", ".join(duplicates))
    requested_set = set(requested)
    return [command_id for command_id in COMMAND_ORDER if command_id in requested_set]


def run_selected_commands(command_map: dict[str, Any], command_ids: list[str], args: argparse.Namespace) -> None:
    mount_groups = sorted(
        {COMMAND_RUN_CONTEXT[command_id] for command_id in command_ids if command_id in COMMAND_RUN_CONTEXT}
    )
    for group in mount_groups:
        ensure_run_mount(group)

    non_bcl_commands = [command_id for command_id in command_ids if command_id not in BCL_COMMANDS]
    for offset in range(0, len(non_bcl_commands), args.max_active):
        run_batch(command_map, non_bcl_commands[offset : offset + args.max_active], args)

    bcl_commands = [command_id for command_id in command_ids if command_id in BCL_COMMANDS]
    if bcl_commands:
        run_bcl_batch(command_map, bcl_commands, args)


def write_report() -> None:
    events = load_events()
    rows: list[tuple[str, str, str, str, str]] = []
    for command_id in COMMAND_ORDER:
        dry = last_event(command_id, "dryrun", current_launch_only=True)
        live = last_event(command_id, "live", current_launch_only=True)
        status = "PENDING"
        if live and live.get("status") == "SUCCESS":
            status = "SUCCESS"
        elif live and live.get("status") == "FAILED":
            status = "FAILED"
        elif live and live.get("status") == "LIVE_RUNNING":
            status = "LIVE_RUNNING"
        elif live and live.get("status") == "BLOCKED":
            status = "BLOCKED"
        elif dry and dry.get("status") == "SUCCESS":
            status = "DRYRUN_SUCCESS"
        elif dry and dry.get("status") == "FAILED":
            status = "FAILED"
        elif dry and dry.get("status") == "DRYRUN_RUNNING":
            status = "DRYRUN_RUNNING"
        rows.append(
            (
                command_id,
                status,
                str((dry or {}).get("analysis_id", "")),
                str((live or {}).get("analysis_id", "")),
                str((live or dry or {}).get("export_uri", "")),
            )
        )

    gate0 = last_event("_gate0", "preflight")
    lines = [
        "# Forked Command Catalog J100 Jitter Validation Report",
        "",
        f"Updated: {utc_now()}",
        "",
        "## Gate 0",
        "",
    ]
    if gate0:
        lines.extend(
            [
                f"- Status: `{gate0.get('status')}`",
                f"- Reason: `{gate0.get('reason', '')}`",
                f"- Headnode: `{gate0.get('headnode_instance_id', '')}`",
            ]
        )
        if gate0.get("stderr_tail"):
            lines.extend(["", "```text", str(gate0["stderr_tail"])[-4000:], "```"])
    else:
        lines.append("- Status: `PENDING`")

    lines.extend(
        [
            "",
            "## Commands",
            "",
            "| Command | Status | Dry-run analysis | Live analysis | Export URI |",
            "|---|---:|---|---|---|",
        ]
    )
    for command_id, status, dry_analysis, live_analysis, export_uri in rows:
        lines.append(f"| `{command_id}` | `{status}` | `{dry_analysis}` | `{live_analysis}` | `{export_uri}` |")

    lines.extend(
        [
            "",
            "## Artifact Paths",
            "",
            f"- Events: `{EVENTS_PATH}`",
            f"- Logs: `{LOG_ROOT}`",
            f"- Generated sample configs: `{GENERATED_CONFIG_ROOT}`",
            f"- Run contexts: `{RUN_CONTEXT_ROOT}`",
            "",
            "## Event Counts",
            "",
            f"- Total events: `{len(events)}`",
        ]
    )
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def load_command_map() -> dict[str, Any]:
    catalog = load_repository_catalog(CATALOG_PATH)
    command_map = {
        command.command_id: command
        for command in catalog.commands()
        if command.repository == REPOSITORY and command.command_id in COMMAND_ORDER
    }
    missing = [command_id for command_id in COMMAND_ORDER if command_id not in command_map]
    if missing:
        raise RuntimeError("Catalog is missing expected commands: " + ", ".join(missing))
    return command_map


def run_plan(args: argparse.Namespace) -> int:
    command_map = load_command_map()
    requested_commands = parse_requested_commands(command_map, args.commands)
    if not gate0_preflight():
        return 2
    if args.preflight_only:
        write_report()
        return 0

    if requested_commands is not None:
        run_selected_commands(command_map, requested_commands, args)
        write_report()
        failures = [
            row
            for row in requested_commands
            if (last_event(row, "live", current_launch_only=True) or {}).get("status")
            in {"FAILED", "BLOCKED"}
        ]
        return 1 if failures else 0

    run_single(command_map, "simple-test", args)

    for batch in SAMPLE_BATCHES:
        for offset in range(0, len(batch), args.max_active):
            run_batch(command_map, batch[offset : offset + args.max_active], args)

    ensure_run_mount("illumina")
    ensure_run_mount("ont")
    ensure_run_mount("ultima")
    run_batch(command_map, ["illumina_run_qc", "ont_run_qc", "ultima_run_qc"], args)
    run_bcl_batch(command_map, ["illumina_bclconvert", "illumina_run_qc_bclconvert"], args)

    write_report()
    failures = [
        row
        for row in COMMAND_ORDER
        if (last_event(row, "live", current_launch_only=True) or {}).get("status")
        in {"FAILED", "BLOCKED"}
    ]
    return 1 if failures else 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dayoa-git-ref", required=True)
    parser.add_argument(
        "--commands",
        help="Comma-separated catalog command IDs to run instead of the full catalog.",
    )
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--dry-run-only", action="store_true")
    parser.add_argument("--poll-seconds", type=int, default=300)
    parser.add_argument("--dryrun-timeout-seconds", type=int, default=7200)
    parser.add_argument("--live-timeout-seconds", type=int, default=259200)
    parser.add_argument("--max-active", type=int, default=4)
    return parser.parse_args()


def main() -> int:
    global DAYOA_GIT_REF
    args = parse_args()
    DAYOA_GIT_REF = args.dayoa_git_ref
    LOG_ROOT.mkdir(parents=True, exist_ok=True)
    GENERATED_CONFIG_ROOT.mkdir(parents=True, exist_ok=True)
    RUN_CONTEXT_ROOT.mkdir(parents=True, exist_ok=True)
    append_event(
        {
            "command_id": "_driver",
            "phase": "start",
            "status": "RUNNING",
            "preflight_only": args.preflight_only,
            "dry_run_only": args.dry_run_only,
            "max_active": args.max_active,
            "dayoa_git_ref": DAYOA_GIT_REF,
            "commands": args.commands or "",
        }
    )
    try:
        rc = run_plan(args)
    except Exception as exc:
        append_event({"command_id": "_driver", "phase": "error", "status": "FAILED", "error": str(exc)})
        write_report()
        raise
    finally:
        write_report()
    append_event({"command_id": "_driver", "phase": "finish", "status": "SUCCESS", "returncode": rc})
    write_report()
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
