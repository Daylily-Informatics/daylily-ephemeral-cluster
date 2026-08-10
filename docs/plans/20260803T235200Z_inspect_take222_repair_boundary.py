#!/usr/bin/env python3
"""Inspect the terminal Take222 checkout before the scoped repair deployment."""

from __future__ import annotations

from daylily_ec.aws.ssm import resolve_headnode_instance_id, run_shell


CLUSTER = "preval-hiomr2"
PROFILE = "lsmc"
REGION = "us-west-2"
ROOT = "/fsx/analysis_results/preval-hiomr2/take222"
CHECKOUT = f"{ROOT}/daylily-omics-analysis"
SESSION = "dayoa_take222_hg003_hg004_smn12_20260803"
FILES = (
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
    target = resolve_headnode_instance_id(CLUSTER, REGION, profile=PROFILE)
    quoted_files = " ".join(repr(path) for path in FILES)
    script = rf"""set -euo pipefail
export DAYOA_AGENT_ID=codex-take222-20260803
export DAYOA_AGENT_KIND=codex
export DAYOA_HUMAN_REQUESTOR='John Major'
export DAYOA_TMUX_SESSION={SESSION!r}
export DAYOA_LEDGER_PATH='/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster/docs/plans/20260803T082714Z_take101_export_take222_fullcov_ledger.md'
dyec analysis visit --analysis-root {ROOT!r} --mode read --intent 'Verify Take222 terminal boundary and scoped repair hashes'
printf '%s\n' '== boundary =='
date -u +%Y-%m-%dT%H:%M:%SZ
tmux list-windows -t {SESSION!r} -F '#{{window_index}}|#{{window_panes}}|#{{window_name}}|#{{window_active}}'
tmux list-panes -t {SESSION!r} -F '#{{pane_id}}|#{{pane_pid}}|#{{pane_current_command}}|#{{pane_dead}}|#{{pane_dead_status}}'
ps -fu ubuntu | awk '/dy-r|bin\/day_run|snakemake/ && !/awk/ {{print}}' || true
squeue -h -u ubuntu -o '%i|%j|%T'
if test -d {ROOT!r}/.dayoa_agent/write.lock; then
  printf '%s\n' 'write-lock-present'
  find {ROOT!r}/.dayoa_agent/write.lock -maxdepth 2 -type f -print -exec sed -n '1,120p' {{}} \;
else
  printf '%s\n' 'write-lock-absent'
fi
printf '%s\n' '== git =='
git -C {CHECKOUT!r} status --short --branch
printf '%s\n' '== active hashes =='
cd {CHECKOUT!r}
sha256sum {quoted_files}
sha256sum {CHECKOUT!r}/take222_run_command_13.4.2.sh
printf '%s\n' '== staged manifest =='
sed -n '1,160p' /home/ubuntu/take222_stage_20260803/remove-diagnostic-gates/payload_manifest.json
printf '%s\n' '== staged hashes =='
cd /home/ubuntu/take222_stage_20260803/remove-diagnostic-gates
find . -type f ! -name 'payload.part*' -print0 | sort -z | xargs -0 sha256sum
"""
    result = run_shell(
        target.instance_id,
        REGION,
        script,
        profile=PROFILE,
        as_user="ubuntu",
        timeout=300,
        comment="Inspect Take222 terminal repair boundary",
    )
    print(result.stdout)
    if result.stderr:
        print(result.stderr)
    return 0 if result.status == "Success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
