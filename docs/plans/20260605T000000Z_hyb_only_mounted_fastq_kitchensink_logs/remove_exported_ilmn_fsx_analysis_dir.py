#!/usr/bin/env python3
"""Remove the already-exported ILMN analysis directory from FSx."""

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
case "$target" in
  /fsx/analysis_results/ubuntu/hybonly_ilmn_kitchensink_mounted_20260606T053415Z) ;;
  *) echo "refusing unexpected target: $target"; exit 20 ;;
esac
echo "deleting=$target"
if [[ -d "$target" ]]; then
  rm -rf -- "$target"
fi
if [[ -d "$target" ]]; then
  echo "delete_status=still_exists"
  exit 21
fi
echo "delete_status=removed_or_absent"
df -h /fsx
"""


def main() -> int:
    try:
        result = run_shell(
            "i-05374380b57fad901",
            "us-west-2",
            SCRIPT,
            profile="lsmc",
            as_user="ubuntu",
            timeout=1800,
            comment="remove exported ILMN FSx analysis dir",
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
