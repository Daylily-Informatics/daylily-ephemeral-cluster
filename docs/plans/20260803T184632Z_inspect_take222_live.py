#!/usr/bin/env python3
"""Read-only Take222 controller, queue, and failure inspection via DYEC SSM."""

from __future__ import annotations

from daylily_ec.aws.ssm import resolve_headnode_instance_id, run_shell


CLUSTER = "preval-hiomr2"
PROFILE = "lsmc"
REGION = "us-west-2"
ROOT = "/fsx/analysis_results/preval-hiomr2/take222"
CHECKOUT = f"{ROOT}/daylily-omics-analysis"
SESSION = "dayoa_take222_hg003_hg004_smn12_20260803"
LIVE_LOG = f"{CHECKOUT}/take222_hg003_hg004_na19235_na20775_fullcov_13.4.2_live_20260803.log"


def main() -> int:
    target = resolve_headnode_instance_id(CLUSTER, REGION, profile=PROFILE)
    script = rf"""set -uo pipefail
export DAYOA_AGENT_ID=codex-take222-20260803
export DAYOA_AGENT_KIND=codex
export DAYOA_HUMAN_REQUESTOR='John Major'
export DAYOA_TMUX_SESSION={SESSION!r}
export DAYOA_LEDGER_PATH={('/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster/docs/plans/20260803T082714Z_take101_export_take222_fullcov_ledger.md')!r}
dyec analysis visit --analysis-root {ROOT!r} --mode read --intent 'Inspect Take222 live terminal state before scoped Jasmine NICU removal' || true
printf '%s\n' '== UTC =='
date -u +%Y-%m-%dT%H:%M:%SZ
printf '%s\n' '== post-direction base hashes =='
sha256sum \
  {CHECKOUT!r}/workflow/rules/hiomr2_truvari.smk \
  {CHECKOUT!r}/workflow/rules/multiqc_final_wgs.smk \
  {CHECKOUT!r}/tests/test_hiomr2_non_hg002_diagnostics.py \
  {CHECKOUT!r}/take222_run_command_13.4.2.sh || true
printf '%s\n' '== tmux shape =='
tmux list-windows -t {SESSION!r} -F '#{{window_index}} #{{window_panes}} #{{window_name}} #{{window_active}}' || true
tmux list-panes -t {SESSION!r} -F '#{{pane_id}} #{{pane_pid}} #{{pane_current_command}} #{{pane_dead}} #{{pane_dead_status}}' || true
printf '%s\n' '== tmux tail =='
tmux capture-pane -pt {SESSION!r} -S -260 || true
printf '%s\n' '== controller processes =='
ps -fu ubuntu | awk '/dy-r|bin\/day_run|snakemake/ && !/awk/ {{print}}' || true
printf '%s\n' '== queue =='
squeue -u ubuntu -o '%.18i %.40j %.9T %.10M %.6D %R' || true
printf '%s\n' '== recent accounting =='
sacct -S 2026-08-03T17:30:00 -u ubuntu -X -n -P -o JobIDRaw,JobName,State,ExitCode,Elapsed,NodeList | tail -n 180 || true
printf '%s\n' '== live log tail =='
tail -n 420 {LIVE_LOG!r} || true
printf '%s\n' '== latest workflow log tails =='
find {CHECKOUT!r}/.snakemake/log -maxdepth 1 -type f -print0 2>/dev/null | xargs -0 ls -1t 2>/dev/null | head -n 3 | while read -r path; do
  printf '%s\n' "-- $path --"
  tail -n 220 "$path"
done
printf '%s\n' '== take222 failure markers =='
rg -n -i 'error|failed|exception|traceback|missingoutput|workflowerror|ruleexception|not all output|exited with non-zero' {LIVE_LOG!r} {CHECKOUT!r}/.snakemake/log 2>/dev/null | tail -n 260 || true
printf '%s\n' '== root lock =='
find {ROOT!r}/.dayoa_agent/write.lock -maxdepth 2 -type f -print -exec sed -n '1,160p' {{}} \; 2>/dev/null || true
"""
    result = run_shell(
        target.instance_id,
        REGION,
        script,
        profile=PROFILE,
        as_user="ubuntu",
        timeout=300,
        comment="Inspect Take222 live controller and terminal failures",
    )
    print(result.stdout)
    if result.stderr:
        print(result.stderr)
    return 0 if result.status == "Success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
