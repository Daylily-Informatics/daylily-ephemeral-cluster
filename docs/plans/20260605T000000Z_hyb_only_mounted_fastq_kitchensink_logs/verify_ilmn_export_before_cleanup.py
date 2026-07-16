#!/usr/bin/env python3
"""Verify exported ILMN analysis artifacts before FSx cleanup."""

from __future__ import annotations

import subprocess
import sys
import os


PREFIX = (
    "s3://lsmc-ssf-sequencing-data/derived/analysis_results/hyb-only/ubuntu/"
    "hybonly_ilmn_kitchensink_mounted_20260606T053415Z/"
)
REQUIRED_KEYS = [
    "daylily-omics-analysis/results/day/hg38/reports/DAY_final_multiqc.html",
    "daylily-omics-analysis/results/day/hg38/reports/DAY_final_multiqc_data/multiqc_data.json",
    "daylily-omics-analysis/results/day/hg38/reports/dayoa_evidence_manifest.json",
]


def run(args: list[str]) -> str:
    env = os.environ.copy()
    env["AWS_PROFILE"] = "lsmc"
    result = subprocess.run(
        args,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    return result.stdout


def main() -> int:
    print(f"prefix={PREFIX}")
    print("required:")
    for key in REQUIRED_KEYS:
        output = run(["aws", "s3", "ls", f"{PREFIX}{key}"])
        print(output, end="")

    print("summary:")
    summary = run(["aws", "s3", "ls", "--recursive", PREFIX, "--summarize"])
    tail = "\n".join(summary.splitlines()[-20:])
    print(tail)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
