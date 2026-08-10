#!/usr/bin/env python3
"""Read-only evidence for Take222 NICU Truvari diagnostic failures."""

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
dyec analysis visit --analysis-root {ROOT!r} --mode read --intent 'Inspect Take222 NICU Truvari diagnostic failures read-only' || true
printf '%s\n' '== UTC and controller =='
date -u +%Y-%m-%dT%H:%M:%SZ
ps -p 3630051 -o pid=,stat=,etime=,cmd= || true
printf '%s\n' '== controller tail =='
tail -n 70 {LIVE_LOG!r} || true
printf '%s\n' '== lock =='
test -d {ROOT!r}/.dayoa_agent/write.lock && printf '%s\n' present || printf '%s\n' absent
printf '%s\n' '== all NICU Truvari accounting =='
sacct -S 2026-08-03T22:00:00 -u ubuntu -X -n -P \
  -o JobIDRaw,JobName,State,ExitCode,Elapsed,Start,End,NodeList,Reason,StdOut,StdErr \
  | rg 'sentdhiomr2_nicu_truvari' || true
printf '%s\n' '== controller failure and retry lines =='
rg -n 'Error executing rule sentdhiomr2_nicu_truvari|Trying to restart job' {LIVE_LOG!r} | tail -n 40 || true
printf '%s\n' '== recent rule logs =='
find {CHECKOUT!r}/results/day/hg38 -type f \
  -path '*/logs/nicu-research/*.truvari.log' -print0 2>/dev/null \
  | xargs -0 -r -n 1 sh -c 'printf "%s\n" "-- $1 --"; rg -n -i "traceback|error|failed|no such|usage:|exception|invalid" "$1" | tail -n 30; tail -n 12 "$1"' sh \
  | tail -n 220 || true
printf '%s\n' '== latest progress and terminal counts =='
rg -n 'of 807 steps .* done' {LIVE_LOG!r} | tail -n 1 || true
sacct -S 2026-08-03T18:20:00 -u ubuntu -X -n -P -o State | sed 's/|$//' | sort | uniq -c || true
"""
    result = run_shell(
        target.instance_id,
        REGION,
        script,
        profile=PROFILE,
        as_user="ubuntu",
        timeout=300,
        comment="Inspect Take222 NICU Truvari failures read-only",
    )
    print(result.stdout)
    if result.stderr:
        print(result.stderr)
    return 0 if result.status == "Success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
