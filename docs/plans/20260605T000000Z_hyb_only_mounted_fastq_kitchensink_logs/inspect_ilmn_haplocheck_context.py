#!/usr/bin/env python3
"""Show Haplocheck rule/config context from the existing ILMN checkout."""

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
echo "contam_identity_context:"
nl -ba workflow/rules/contam_identity.smk | sed -n '300,455p'
echo "rule_config_haplocheck_context:"
grep -n -A12 -B4 '^haplocheck:' config/day_profiles/slurm/templates/rule_config.yaml
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
            comment="inspect ILMN haplocheck context before additive patch",
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
