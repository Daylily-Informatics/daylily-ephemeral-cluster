#!/usr/bin/env python3
"""Bounded read-only health snapshot for Take222 integrated Jasmine job 4338."""

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
dyec analysis visit --analysis-root {ROOT!r} --mode read --intent 'Inspect Take222 integrated Jasmine job 4338 health read-only' || true
printf '%s\n' '== UTC and accounting =='
date -u +%Y-%m-%dT%H:%M:%SZ
sacct -j 4338 -X -P -o JobIDRaw,JobName,State,ExitCode,Elapsed,Start,NodeList,AllocCPUS,ReqMem,MaxRSS,StdOut,StdErr || true
printf '%s\n' '== live resource sample =='
sstat -j 4338.batch -P -o JobID,AveCPU,AveRSS,MaxRSS,AveVMSize,MaxVMSize 2>/dev/null || true
printf '%s\n' '== controller submission context =='
rg -n -B 12 -A 8 "external jobid '4338'" {LIVE_LOG!r} | tail -n 80 || true
printf '%s\n' '== recent integrated Jasmine logs =='
find {CHECKOUT!r}/results/day/hg38 -type f -mmin -90 \
  \( -iname '*jasmine*integrated*.log' -o -iname '*integrated*jasmine*.log' \) -print0 2>/dev/null \
  | xargs -0 -r -n 1 sh -c 'printf "%s\n" "-- $1 --"; stat -c "%s|%y" "$1"; tail -n 120 "$1"' sh \
  | tail -n 400 || true
"""
    result = run_shell(
        target.instance_id,
        REGION,
        script,
        profile=PROFILE,
        as_user="ubuntu",
        timeout=300,
        comment="Inspect Take222 integrated Jasmine job 4338 read-only",
    )
    print(result.stdout)
    if result.stderr:
        print(result.stderr)
    return 0 if result.status == "Success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
