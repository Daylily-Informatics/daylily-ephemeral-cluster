#!/usr/bin/env python3
"""Read-only headnode inspection for DayOA runtime cache linkage."""

from __future__ import annotations

from daylily_ec.aws.ssm import run_shell


SCRIPT = r"""
set -euo pipefail
echo "USER=$(id -un)"
echo "HOST=$(hostname)"
echo "PWD=$(pwd)"
echo "FSX_RESOURCES=$(readlink -f /fsx/resources 2>/dev/null || true)"
echo "FSX_REFERENCES=$(readlink -f /fsx/references 2>/dev/null || true)"
echo "--- selected fsx dirs ---"
find /fsx -maxdepth 4 -type d \( \
  -path /fsx/resources \
  -o -path /fsx/resources/environments \
  -o -path /fsx/resources/environments/conda \
  -o -path /fsx/references/runtime_assets \
  -o -path /fsx/references/runtime_assets/cached_envs \
  -o -path /fsx/references/runtime_assets/cluster_boot_config \
\) -print -exec ls -ld {} \; 2>/dev/null || true
echo "--- fsx mount ---"
mount | grep -E "/fsx|lustre" || true
echo "--- daylily cfg grep ---"
grep -RInE "s3://|cache|conda|environment|runtime|resources|artifact" /home/ubuntu/.config/daylily 2>/dev/null || true
echo "--- env cache listing ---"
find /fsx/resources/environments/conda/ubuntu -maxdepth 3 -type d 2>/dev/null | sed -n '1,80p' || true
echo "--- references runtime listing ---"
find /fsx/references/runtime_assets -maxdepth 3 -type d 2>/dev/null | sed -n '1,120p' || true
"""


def main() -> int:
    result = run_shell(
        "i-05374380b57fad901",
        "us-west-2",
        SCRIPT,
        profile="lsmc",
        as_user="ubuntu",
        comment="inspect cache prefix",
    )
    print(result.stdout)
    if result.stderr.strip():
        print(result.stderr)
    return result.response_code


if __name__ == "__main__":
    raise SystemExit(main())
