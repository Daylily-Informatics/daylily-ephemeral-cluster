#!/usr/bin/env python3
"""Compact read-only monitor for the Take222 five-target repair-live proof."""

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
export DAYOA_AGENT_ID=codex-take222-release-20260803
export DAYOA_AGENT_KIND=codex
export DAYOA_HUMAN_REQUESTOR='John Major'
export DAYOA_TMUX_SESSION={SESSION!r}
export DAYOA_LEDGER_PATH='/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster/docs/plans/20260803T082714Z_take101_export_take222_fullcov_ledger.md'
dyec analysis visit --analysis-root {ROOT!r} --mode read --intent 'Take222 five-target repair-live controller jobs receipts packages MultiQC capacity heartbeat' || true
printf '%s\n' '== UTC =='
date -u +%Y-%m-%dT%H:%M:%SZ
printf '%s\n' '== tmux =='
tmux list-windows -t {SESSION!r} -F '#{{window_index}}|#{{window_panes}}|#{{window_name}}|#{{window_active}}' || true
tmux list-panes -t {SESSION!r} -F '#{{pane_id}}|#{{pane_pid}}|#{{pane_current_command}}|#{{pane_dead}}|#{{pane_dead_status}}' || true
printf '%s\n' '== controller =='
ps -fu ubuntu | awk '/dy-r|bin\/day_run|snakemake/ && !/awk/ {{print}}' || true
printf '%s\n' '== squeue =='
squeue -h -u ubuntu -o '%i|%j|%T|%M|%N|%R' || true
printf '%s\n' '== repair-live accounting =='
sacct -S 2026-08-04T00:04:00 -u ubuntu -X -n -P -o JobIDRaw,JobName,State,ExitCode,Elapsed,NodeList | sed '/^$/d' || true
printf '%s\n' '== live markers =='
rg -n 'allowed write|Job stats:|Total jobs:|Submitted job|Finished job|Trying to restart|RETURN CODE|Womp Womp|^[0-9]+ of [0-9]+ steps|ERROR:|requires a write lock' {LIVE_LOG!r} 2>/dev/null | tail -n 120 || true
printf '%s\n' '== NICU Truvari receipts =='
find {CHECKOUT!r}/results/day/hg38 -type f -path '*/nicu-research/*' -name '*receipt*.json' -printf '%TY-%Tm-%TdT%TH:%TM:%TSZ|%s|%p\n' 2>/dev/null | sort || true
find {CHECKOUT!r}/results/day/hg38 -type f -path '*/nicu-research/*' -name '*receipt*.json' -print0 2>/dev/null \
  | xargs -0 -r rg -n '"status"|"reason"|"query_vcf_sha256"|"truth_vcf_sha256"|"command_attempted"' 2>/dev/null || true
for receipt in $(find {CHECKOUT!r}/results/day/hg38 -type f -path '*/nicu-research/*' -name '*receipt*.json' 2>/dev/null | sort); do
  printf '%s\n' "== $receipt =="
  sed -n '1,120p' "$receipt"
done
printf '%s\n' '== NICU Truvari summaries =='
find {CHECKOUT!r}/results/day/hg38 -type f -path '*/nicu-research/*' -name '*.truvari.summary.tsv' -print -exec sed -n '1,10p' {{}} \; 2>/dev/null | sort || true
printf '%s\n' '== MultiQC =='
stat -c '%y|%s|%n' {CHECKOUT!r}/results/day/hg38/reports/DAY_final_multiqc.html 2>/dev/null || true
stat -c '%y|%s|%n' {CHECKOUT!r}/results/day/hg38/reports/DAY_final_multiqc_data/multiqc_data.json 2>/dev/null || true
printf '%s\n' '== Inflection package manifests =='
find {CHECKOUT!r}/results/day/hg38 -type f \( -path '*inflection*' -o -path '*analytical-package*' \) \
  \( -name '*manifest*.json' -o -name 'complete.json' \) -printf '%TY-%Tm-%TdT%TH:%TM:%TSZ|%s|%p\n' 2>/dev/null | sort | tail -n 40 || true
printf '%s\n' '== FSx =='
df -B1 --output=size,used,avail,pcent,target /fsx | tail -n 1 || true
df -i /fsx | tail -n 1 || true
printf '%s\n' '== lock =='
if test -d {ROOT!r}/.dayoa_agent/write.lock; then
  sed -n '1,120p' {ROOT!r}/.dayoa_agent/write.lock/owner.json
else
  printf '%s\n' 'write-lock-absent'
fi
"""
    result = run_shell(
        target.instance_id,
        REGION,
        script,
        profile=PROFILE,
        as_user="ubuntu",
        timeout=300,
        comment="Compact Take222 five-target repair-live heartbeat",
    )
    print(result.stdout)
    if result.stderr:
        print(result.stderr)
    return 0 if result.status == "Success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
