#!/usr/bin/env python3
"""Preflight ILMN 20x downsampling tools and destination on the headnode."""

from __future__ import annotations

import sys

from daylily_ec.aws.ssm import run_shell


SCRIPT = r"""
set -euo pipefail
echo tools
for t in seqtk pigz gzip tmux; do
  printf "%s=" "$t"
  command -v "$t" || true
done
echo dest
ls -ld /fsx/analysis_results/4_nas_ds_to_20x 2>/dev/null || echo missing
find /fsx/analysis_results/4_nas_ds_to_20x -maxdepth 2 -type f 2>/dev/null | sed -n '1,80p' || true
"""


def main() -> int:
    result = run_shell(
        "i-05374380b57fad901",
        "us-west-2",
        SCRIPT,
        profile="lsmc",
        as_user="ubuntu",
        timeout=120,
        comment="preflight ILMN ds20x tools",
    )
    print(result.stdout, end="")
    print(result.stderr, end="", file=sys.stderr)
    return int(result.response_code or 0)


if __name__ == "__main__":
    raise SystemExit(main())
