#!/usr/bin/env python3
"""Launch NA4 ds20x split-chip hybrid HioMR variant + alignstats workflow."""

from __future__ import annotations

import argparse
import os
import shlex
import subprocess
import sys


DYEC = "/Users/jmajor/miniconda3/envs/DAY-EC/bin/dyec"
DEFAULT_STAGE_DIR = (
    "/home/ubuntu/daylily-staged-configs/"
    "hybonly_hybrid_hiomr_na4_ds20x_split_20260606T153500Z_config"
)

TARGETS = [
    "produce_sent_align",
    "produce_dmd_dedup_cram",
    "produce_sentdhiomr_snv_vcf",
    "produce_sentdhiomr_sv",
    "produce_sentdhiomr_cnv",
    "produce_sentdhiomr_segdup",
    "produce_sentdhiomr_mito",
    "produce_expansionhunter",
    "produce_alignstats",
]

CONFIG = [
    'aligners=["sent"]',
    'dedupers=["dmd"]',
    'snv_callers=["sentdhiomr"]',
    'sv_callers=["sentdhiomr"]',
    'sentdhiomr={"segdup_genes":"CYP11B1,NCF1,SMN1"}',
]


def dy_command(*, dry_run: bool, jobs: int) -> str:
    parts = [
        "bin/day_run",
        *TARGETS,
        "--config",
        *(shlex.quote(item) for item in CONFIG),
        "-j",
        str(jobs),
        "-p",
        "-k",
        "--rerun-triggers",
        "mtime",
    ]
    if dry_run:
        parts.append("-n")
    return " ".join(parts)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage-dir", default=DEFAULT_STAGE_DIR)
    parser.add_argument("--session-name", required=True)
    parser.add_argument("--analysis-id", required=True)
    parser.add_argument("--jobs", type=int, default=125)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    cmd = [
        DYEC,
        "workflow",
        "launch",
        "--profile",
        "lsmc",
        "--region",
        "us-west-2",
        "--cluster",
        "hyb-only",
        "--stage-dir",
        args.stage_dir,
        "--session-name",
        args.session_name,
        "--analysis-id",
        args.analysis_id,
        "--executing-entity",
        "ubuntu",
        "--git-tag",
        "jem-dev",
        "--genome",
        "hg38_broad",
        "--dy-command",
        dy_command(dry_run=args.dry_run, jobs=args.jobs),
    ]
    if args.dry_run:
        cmd.append("--dry-run")

    print("DYEC_COMMAND=" + shlex.join(cmd))
    env = {**os.environ, "AWS_PROFILE": "lsmc"}
    result = subprocess.run(cmd, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    print(result.stdout, end="")
    print(result.stderr, end="", file=sys.stderr)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
