#!/usr/bin/env python3
"""Read dirty git state from the existing ILMN DayOA checkout."""

from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from daylily_ec.aws.ssm import SsmCommandFailedError, run_shell  # noqa: E402


SCRIPT = r"""
set -euo pipefail
repo=/fsx/analysis_results/ubuntu/hybonly_ilmn_kitchensink_mounted_20260606T053415Z/daylily-omics-analysis
cd "$repo"
echo "repo=$PWD"
echo "head=$(git rev-parse HEAD)"
echo "branch=$(git rev-parse --abbrev-ref HEAD)"
echo "status:"
git status --short --branch
echo "diff_stat:"
git diff --stat
echo "diff_target:"
git diff -- workflow/rules/contam_identity.smk config/day_profiles/slurm/templates/rule_config.yaml | sed -n '1,260p'
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
            comment="record ILMN dirty diff before restart",
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
