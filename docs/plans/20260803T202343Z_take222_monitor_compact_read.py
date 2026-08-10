#!/usr/bin/env python3
"""Compact read-only status collector for the active Take222 monitor."""

from __future__ import annotations

from daylily_ec.aws.ssm import resolve_headnode_instance_id, run_shell


CLUSTER = "preval-hiomr2"
PROFILE = "lsmc"
REGION = "us-west-2"
ROOT = "/fsx/analysis_results/preval-hiomr2/take222"
CHECKOUT = f"{ROOT}/daylily-omics-analysis"
LIVE_LOG = f"{CHECKOUT}/take222_hg003_hg004_na19235_na20775_fullcov_13.4.2_live_20260803.log"


def main() -> int:
    target = resolve_headnode_instance_id(CLUSTER, REGION, profile=PROFILE)
    script = rf"""set -uo pipefail
export DAYOA_AGENT_ID=codex-take222-20260803
export DAYOA_AGENT_KIND=codex
export DAYOA_HUMAN_REQUESTOR='John Major'
export DAYOA_TMUX_SESSION=dayoa_take222_hg003_hg004_smn12_20260803
export DAYOA_LEDGER_PATH='/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster/docs/plans/20260803T082714Z_take101_export_take222_fullcov_ledger.md'
dyec analysis visit --analysis-root {ROOT!r} --mode read --intent 'Take222 compact heartbeat monitor read' || true
printf '%s\n' '== UTC =='
date -u +%Y-%m-%dT%H:%M:%SZ
printf '%s\n' '== tmux and controller =='
tmux list-panes -t dayoa_take222_hg003_hg004_smn12_20260803 -F '#{{session_name}}|#{{window_panes}}|#{{pane_pid}}|#{{pane_current_command}}|#{{pane_dead}}' 2>/dev/null || true
ps -p 3630051 -o pid=,ppid=,stat=,etime=,cmd= || true
pgrep -a -P 3630051 || true
printf '%s\n' '== progress =='
rg -n 'of 807 steps .* done' {LIVE_LOG!r} | tail -n 1 || true
printf '%s\n' '== SegDup retry 4037 =='
sacct -j 4037 -X -n -P -o JobIDRaw,JobName,State,ExitCode,Elapsed,Start,End,NodeList,Reason || true
printf '%s\n' '== queue and accounting =='
squeue -h -u ubuntu -o '%T' | sort | uniq -c || true
squeue -h -u ubuntu -o '%i|%j|%T|%M|%N' || true
sacct -S 2026-08-03T18:20:00 -u ubuntu -X -n -P -o State | sed 's/|$//' | sort | uniq -c || true
printf '%s\n' '== new terminal non-success after 3919 =='
sacct -S 2026-08-03T19:33:18 -u ubuntu -X -n -P -o JobIDRaw,JobName,State,ExitCode,Elapsed,NodeList \
  | awk -F'|' '$3 !~ /^(COMPLETED|RUNNING|PENDING|CONFIGURING|COMPLETING|REQUEUED|RESIZING|SUSPENDED)$/ {{print}}' || true
printf '%s\n' '== recent Jasmine NICU error markers =='
find {CHECKOUT!r}/results/day/hg38 -type f -mmin -25 \
  \( -iname '*jasmine*.log' -o -iname '*nicu*.log' \) -print0 2>/dev/null \
  | xargs -0 -r rg -n -i 'traceback|workflowerror|ruleexception|missingoutputexception|(^|[^a-z])error([^a-z]|$)' 2>/dev/null \
  | head -n 40 || true
printf '%s\n' '== warning and failure receipt statuses =='
find {CHECKOUT!r}/results/day/hg38 -type f \
  \( -name 'terminal_receipt.json' -o -name 'complete.json' \) -print0 2>/dev/null \
  | xargs -0 -r rg -l '"status"[[:space:]]*:[[:space:]]*"(WARNING|FAILED|ERROR)"' 2>/dev/null \
  | sort | head -n 100 || true
printf '%s\n' '== FSx capacity =='
df -B1 --output=size,used,avail,pcent,target /fsx | tail -n 1 || true
df -i /fsx | tail -n 1 || true
printf '%s\n' '== write lock =='
test -d {ROOT!r}/.dayoa_agent/write.lock && printf '%s\n' present || printf '%s\n' absent
"""
    result = run_shell(
        target.instance_id,
        REGION,
        script,
        profile=PROFILE,
        as_user="ubuntu",
        timeout=300,
        comment="Take222 compact heartbeat read-only status",
    )
    print(result.stdout)
    if result.stderr:
        print(result.stderr)
    return 0 if result.status == "Success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
