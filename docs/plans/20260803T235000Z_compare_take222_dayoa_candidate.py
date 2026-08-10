#!/usr/bin/env python3
"""Compare the exact local DayOA candidate file set with Take222 read-only."""

from __future__ import annotations

import hashlib
import shlex
from pathlib import Path

from daylily_ec.aws.ssm import resolve_headnode_instance_id, run_shell


CLUSTER = "preval-hiomr2"
PROFILE = "lsmc"
REGION = "us-west-2"
ROOT = Path("/fsx/analysis_results/preval-hiomr2/take222")
REMOTE = ROOT / "daylily-omics-analysis"
LOCAL = Path("/Users/jmajor/.codex/worktrees/dayoa-13.4.2-take222")
PATHS = (
    "daylily_omics_analysis/hiomr2_jasmine_rtg.py",
    "daylily_omics_analysis/hiomr2_nicu_sv.py",
    "daylily_omics_analysis/hiomr2_truvari.py",
    "tests/test_hiomr2_jasmine_rules.py",
    "tests/test_hiomr2_nicu_rules.py",
    "tests/test_hiomr2_nicu_sv.py",
    "tests/test_hiomr2_non_hg002_diagnostics.py",
    "workflow/rules/hiomr2_nicu_research.smk",
    "workflow/rules/hiomr2_truvari.smk",
    "workflow/rules/multiqc_final_wgs.smk",
)


def main() -> int:
    for relative in PATHS:
        digest = hashlib.sha256((LOCAL / relative).read_bytes()).hexdigest()
        print(f"local\t{relative}\t{digest}")
    target = resolve_headnode_instance_id(CLUSTER, REGION, profile=PROFILE)
    quoted_paths = " ".join(shlex.quote(str(REMOTE / item)) for item in PATHS)
    script = f"""set -euo pipefail
export DAYOA_AGENT_ID=codex-take222-20260803
export DAYOA_AGENT_KIND=codex
export DAYOA_HUMAN_REQUESTOR='John Major'
export DAYOA_TMUX_SESSION=dayoa_take222_hg003_hg004_smn12_20260803
export DAYOA_LEDGER_PATH='/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster/docs/plans/20260803T234000Z_dayoa_13_4_3_dyec_release_slack_ledger.md'
dyec analysis visit --analysis-root {shlex.quote(str(ROOT))} --mode read --intent 'Compare exact local and Take222 DayOA candidate files after controller exit'
sha256sum {quoted_paths}
git -C {shlex.quote(str(REMOTE))} status --short --branch
"""
    result = run_shell(
        target.instance_id,
        REGION,
        script,
        profile=PROFILE,
        as_user="ubuntu",
        timeout=300,
        comment="Compare Take222 DayOA candidate hashes read-only",
    )
    print(result.stdout)
    if result.stderr:
        print(result.stderr)
    return 0 if result.status == "Success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
