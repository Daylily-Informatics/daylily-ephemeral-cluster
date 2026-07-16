#!/usr/bin/env python3
"""Inspect cached BWA-MEM2-related envs for downsampling tools."""

from __future__ import annotations

import sys

from daylily_ec.aws.ssm import run_shell


SCRIPT = r"""
set -euo pipefail
echo "CACHED_ENV_TOOL_PROBE"
for root in \
  /fsx/references/runtime_assets/cached_envs \
  /fsx/references/runtime_assets/cached_conda_envs \
  /fsx/references/runtime_assets; do
  [ -d "$root" ] || continue
  echo "ROOT=$root"
  find "$root" -maxdepth 4 -type f \( -name seqtk -o -name seqkit -o -name reformat.sh -o -name pigz -o -name bwa-mem2 -o -name bwa-mem2.avx2 \) -print | sort
done
echo "RULE_CONFIG_ENV_REFS"
grep -R "bwamem2\|bwa_mem2\|sent.*env_yaml\|bwa" -n /fsx/analysis_results/ubuntu/hybonly_ont_chipbarcode_limited_live_20260606T090222Z/daylily-omics-analysis/config/day_profiles/slurm/rule_config.yaml | sed -n '1,80p' || true
echo "PATH_CANDIDATES"
find /fsx/references/runtime_assets -maxdepth 5 -type d \( -iname '*bwa*' -o -iname '*sentieon*' -o -iname '*bio*' \) | sort | sed -n '1,120p'
"""


def main() -> int:
    result = run_shell(
        "i-05374380b57fad901",
        "us-west-2",
        SCRIPT,
        profile="lsmc",
        as_user="ubuntu",
        timeout=180,
        comment="inspect cached bwamem2 env tools",
    )
    print(result.stdout, end="")
    print(result.stderr, end="", file=sys.stderr)
    return int(result.response_code or 0)


if __name__ == "__main__":
    raise SystemExit(main())
