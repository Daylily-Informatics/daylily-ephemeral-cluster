#!/usr/bin/env python3
"""Verify hybrid HIOMR source paths exist on the hyb-only headnode."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

from daylily_ec.aws.ssm import run_shell


INSTANCE_ID = "i-05374380b57fad901"
REGION = "us-west-2"
PROFILE = "lsmc"
MANIFEST = Path(
    "/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster/docs/plans/"
    "20260605T000000Z_hyb_only_mounted_fastq_kitchensink_logs/"
    "hybrid_hiomr_na4_config/20260606T105700Z_hybrid_hiomr_na4_source_manifest.tsv"
)
UNITS = Path(
    "/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster/docs/plans/"
    "20260605T000000Z_hyb_only_mounted_fastq_kitchensink_logs/"
    "hybrid_hiomr_na4_config/20260606T105700Z_hybrid_hiomr_na4_units.tsv"
)


def main() -> int:
    paths: list[str] = []
    with MANIFEST.open(newline="") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            paths.extend([row["ilmn_r1"], row["ilmn_r2"], row["ont_cram"], row["ont_crai"]])

    with UNITS.open(newline="") as handle:
        units = list(csv.DictReader(handle, delimiter="\t"))
    bad_stage = [
        path
        for row in units
        for key, path in row.items()
        if path and "/fsx/staging" in path
    ]
    if bad_stage:
        raise SystemExit("unexpected /fsx/staging path(s):\n" + "\n".join(bad_stage))

    unique_paths = sorted(set(paths))
    remote_script = "\n".join(
        [
            "set -euo pipefail",
            "python3 - <<'PY'",
            "from pathlib import Path",
            f"paths = {json.dumps(unique_paths, indent=2)}",
            "missing = []",
            "zero = []",
            "for path in paths:",
            "    p = Path(path)",
            "    if not p.exists():",
            "        missing.append(path)",
            "    elif p.is_file() and p.stat().st_size == 0:",
            "        zero.append(path)",
            "print(f'unique_paths={len(paths)}')",
            "print(f'missing={len(missing)}')",
            "print(f'zero_byte={len(zero)}')",
            "if missing:",
            "    print('MISSING')",
            "    print('\\n'.join(missing))",
            "if zero:",
            "    print('ZERO_BYTE')",
            "    print('\\n'.join(zero))",
            "if missing or zero:",
            "    raise SystemExit(2)",
            "for path in paths:",
            "    p = Path(path)",
            "    print(f'{p.stat().st_size}\\t{path}')",
            "PY",
        ]
    )
    result = run_shell(
        INSTANCE_ID,
        REGION,
        remote_script,
        profile=PROFILE,
        as_user="ubuntu",
        timeout=300,
        comment="verify hybrid HIOMR source paths",
    )
    print(result.stdout, end="")
    print(result.stderr, end="", file=sys.stderr)
    return int(result.response_code or 0)


if __name__ == "__main__":
    raise SystemExit(main())
