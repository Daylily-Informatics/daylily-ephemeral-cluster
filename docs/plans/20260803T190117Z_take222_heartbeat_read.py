#!/usr/bin/env python3
"""Compact read-only Take222 heartbeat through the supported DYEC SSM helper."""

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
export DAYOA_LEDGER_PATH='/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster/docs/plans/20260803T082714Z_take101_export_take222_fullcov_ledger.md'
dyec analysis visit --analysis-root {ROOT!r} --mode read --intent 'Take222 20-minute compact controller jobs logs receipts and capacity heartbeat' || true
printf '%s\n' '== UTC =='
date -u +%Y-%m-%dT%H:%M:%SZ
printf '%s\n' '== tmux =='
tmux list-windows -t {SESSION!r} -F '#{{window_index}}|#{{window_panes}}|#{{window_name}}|#{{window_active}}' || true
tmux list-panes -t {SESSION!r} -F '#{{pane_id}}|#{{pane_pid}}|#{{pane_current_command}}|#{{pane_dead}}|#{{pane_dead_status}}' || true
printf '%s\n' '== controller =='
ps -fu ubuntu | awk '/dy-r|bin\/day_run|snakemake/ && !/awk/ {{print}}' || true
printf '%s\n' '== squeue state counts =='
squeue -h -u ubuntu -o '%T' | sort | uniq -c || true
printf '%s\n' '== active rule counts =='
squeue -h -u ubuntu -o '%j|%T' | awk -F'|' '{{sub(/-[^-]+$/, "", $1); print $1"|"$2}}' | sort | uniq -c | sort -nr | head -n 60 || true
printf '%s\n' '== sacct state counts =='
sacct -S 2026-08-03T18:20:00 -u ubuntu -X -n -P -o State | sed '/^$/d' | sort | uniq -c || true
printf '%s\n' '== terminal non-success jobs =='
sacct -S 2026-08-03T18:20:00 -u ubuntu -X -n -P -o JobIDRaw,JobName,State,ExitCode,Elapsed,NodeList | awk -F'|' '$3 !~ /^(COMPLETED|RUNNING|PENDING|CONFIGURING|COMPLETING|REQUEUED|RESIZING|SUSPENDED)$/ {{print}}' || true
printf '%s\n' '== latest controller progress =='
rg -n '^[0-9]+ of 807 steps' {LIVE_LOG!r} | tail -n 1 || true
printf '%s\n' '== live tail =='
tail -n 90 {LIVE_LOG!r} || true
printf '%s\n' '== recent Jasmine NICU log markers =='
find {CHECKOUT!r}/results/day/hg38 -type f -mmin -45 \
  \( -iname '*jasmine*.log' -o -iname '*nicu*.log' \) -print0 2>/dev/null \
  | xargs -0 -r rg -n -i 'traceback|workflowerror|ruleexception|missingoutput|failed|error:' 2>/dev/null \
  | tail -n 100 || true
printf '%s\n' '== recent Jasmine NICU logs =='
find {CHECKOUT!r}/results/day/hg38 -type f -mmin -45 \
  \( -iname '*jasmine*.log' -o -iname '*nicu*.log' \) -printf '%TY-%Tm-%TdT%TH:%TM:%TSZ|%s|%p\n' 2>/dev/null \
  | sort -r | head -n 40 || true
printf '%s\n' '== receipt counts =='
find {CHECKOUT!r}/results/day/hg38 -type f \
  \( -name 'terminal_receipt.json' -o -name '*.done' -o -name 'complete.json' \) \
  -printf '%f\n' 2>/dev/null | sort | uniq -c || true
printf '%s\n' '== warning and failure receipt statuses =='
find {CHECKOUT!r}/results/day/hg38 -type f \
  \( -name 'terminal_receipt.json' -o -name 'complete.json' \) -print0 2>/dev/null \
  | xargs -0 -r rg -l '"status"[[:space:]]*:[[:space:]]*"(WARNING|FAILED|ERROR)"' 2>/dev/null \
  | head -n 100 || true
printf '%s\n' '== FSx capacity =='
df -B1 --output=size,used,avail,pcent,target /fsx | tail -n 1 || true
df -i /fsx | tail -n 1 || true
printf '%s\n' '== write lock =='
find {ROOT!r}/.dayoa_agent/write.lock -maxdepth 2 -type f -print -exec sed -n '1,120p' {{}} \; 2>/dev/null || true
"""
    result = run_shell(
        target.instance_id,
        REGION,
        script,
        profile=PROFILE,
        as_user="ubuntu",
        timeout=300,
        comment="Compact Take222 20-minute read heartbeat",
    )
    print(result.stdout)
    if result.stderr:
        print(result.stderr)
    return 0 if result.status == "Success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
