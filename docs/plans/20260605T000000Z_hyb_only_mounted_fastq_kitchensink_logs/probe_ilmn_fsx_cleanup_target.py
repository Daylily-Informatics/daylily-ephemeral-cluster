#!/usr/bin/env python3
"""Read-only probe of the exported ILMN FSx analysis directory before removal."""

from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from daylily_ec.aws.ssm import SsmCommandFailedError, run_shell  # noqa: E402


TARGET = "/fsx/analysis_results/ubuntu/hybonly_ilmn_kitchensink_mounted_20260606T053415Z"

SCRIPT = f"""
set -euo pipefail
target={TARGET!r}
echo "target=$target"
if [[ -d "$target" ]]; then
  echo "exists=yes"
  du -sh "$target" || true
  echo "top_level:"
  find "$target" -maxdepth 2 -type f | sed -n '1,40p'
  echo "required_local_files:"
  for f in \
    "$target/daylily-omics-analysis/results/day/hg38/reports/DAY_final_multiqc.html" \
    "$target/daylily-omics-analysis/results/day/hg38/reports/DAY_final_multiqc_data/multiqc_data.json" \
    "$target/daylily-omics-analysis/results/day/hg38/reports/dayoa_evidence_manifest.json"
  do
    if [[ -e "$f" ]]; then
      ls -lh "$f"
    else
      echo "MISSING $f"
    fi
  done
else
  echo "exists=no"
fi
"""


def main() -> int:
    try:
        result = run_shell(
            "i-05374380b57fad901",
            "us-west-2",
            SCRIPT,
            profile="lsmc",
            as_user="ubuntu",
            timeout=120,
            comment="probe ILMN FSx cleanup target",
        )
    except SsmCommandFailedError as exc:
        print(exc.result.stdout, end="")
        print(exc.result.stderr, end="", file=sys.stderr)
        return exc.result.response_code or 1

    print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    return result.response_code


if __name__ == "__main__":
    raise SystemExit(main())
