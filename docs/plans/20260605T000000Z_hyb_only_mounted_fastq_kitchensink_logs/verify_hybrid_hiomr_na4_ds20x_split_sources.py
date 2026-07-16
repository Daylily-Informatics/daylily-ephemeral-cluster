#!/usr/bin/env python3
"""Verify NA4 ds20x hybrid HioMR source paths on hyb-only headnode."""

from __future__ import annotations

import sys

from daylily_ec.aws.ssm import run_shell


INSTANCE_ID = "i-05374380b57fad901"
REGION = "us-west-2"
PROFILE = "lsmc"
REMOTE_STAGE_DIR = (
    "/home/ubuntu/daylily-staged-configs/"
    "hybonly_hybrid_hiomr_na4_ds20x_split_20260606T153500Z_config"
)
REMOTE_SAMPLES = f"{REMOTE_STAGE_DIR}/20260606T153500Z_hybrid_hiomr_na4_ds20x_split_samples.tsv"
REMOTE_UNITS = f"{REMOTE_STAGE_DIR}/20260606T153500Z_hybrid_hiomr_na4_ds20x_split_units.tsv"


def main() -> int:
    remote_script = "\n".join(
        [
            "set -euo pipefail",
            "python3 - <<'PY'",
            "import csv",
            "from pathlib import Path",
            f"samples_path = Path({REMOTE_SAMPLES!r})",
            f"units_path = Path({REMOTE_UNITS!r})",
            "for required in (samples_path, units_path):",
            "    if not required.exists() or required.stat().st_size == 0:",
            "        raise SystemExit(f'missing remote config: {required}')",
            "with samples_path.open(newline='') as handle:",
            "    samples = list(csv.DictReader(handle, delimiter='\\t'))",
            "with units_path.open(newline='') as handle:",
            "    units = list(csv.DictReader(handle, delimiter='\\t'))",
            "if len(samples) != 4:",
            "    raise SystemExit(f'unexpected sample row count: {len(samples)}')",
            "if len(units) != 8:",
            "    raise SystemExit(f'unexpected unit row count: {len(units)}')",
            "paths = []",
            "bad_stage = []",
            "for row in units:",
            "    for key in ('ILMN_R1_PATH', 'ILMN_R2_PATH'):",
            "        paths.append(row[key])",
            "    paths.extend(part for part in row.get('ONT_R1_PATH', '').split(',') if part and part != 'na')",
            "    bad_stage.extend(path for path in row.values() if path and '/fsx/staging' in path)",
            "if bad_stage:",
            "    print('BAD_STAGE')",
            "    print('\\n'.join(bad_stage))",
            "    raise SystemExit(3)",
            "paths = sorted(set(paths))",
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
            "by_unit = []",
            "for row in units:",
            "    fastq_count = len([p for p in row.get('ONT_R1_PATH', '').split(',') if p and p != 'na'])",
            "    by_unit.append((row['SAMPLEID'], row['LANEID'], row['BARCODEID'], fastq_count, row['ILMN_R1_PATH'], row['ILMN_R2_PATH']))",
            "print('UNIT_SUMMARY')",
            "for item in by_unit:",
            "    print('\\t'.join(map(str, item)))",
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
        comment="verify NA4 ds20x hybrid HIOMR source paths",
    )
    print(result.stdout, end="")
    print(result.stderr, end="", file=sys.stderr)
    return int(result.response_code or 0)


if __name__ == "__main__":
    raise SystemExit(main())
