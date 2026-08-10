#!/usr/bin/env python3
"""Read-only root-cause evidence for Take222 NICU Truvari failures."""

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
export DAYOA_LEDGER_PATH='/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster/docs/plans/20260803T234000Z_dayoa_13_4_3_dyec_release_slack_ledger.md'
dyec analysis visit --analysis-root {ROOT!r} --mode read --intent 'Read exact Take222 NICU Truvari failure logs after natural controller exit' || true
printf '%s\n' '== exact NICU Truvari logs =='
for sample in HG004-9zznm9yqnkwtjr HG003-cqp3zghjfqgykp NA19235-p9yktjchebvwjf NA20775-qhyxr5gkfymvhd; do
  log={CHECKOUT!r}/results/day/hg38/$sample/align/sentmm2ont/na/snv/sentdhiomr2/logs/nicu-research/$sample.truvari.log
  printf '%s\n' "-- $log --"
  if test -f "$log"; then tail -n 160 "$log"; else printf '%s\n' MISSING; fi
done
printf '%s\n' '== exact Slurm stderr/stdout tails =='
for job in 4442 4445 4451 4452 4463 4464 4483 4484; do
  sacct -j "$job" -X -n -P -o StdOut,StdErr | head -n 1 | while IFS='|' read -r stdout stderr _; do
    printf '%s\n' "-- job $job stdout $stdout --"
    test -f "$stdout" && tail -n 80 "$stdout" || true
    printf '%s\n' "-- job $job stderr $stderr --"
    test -f "$stderr" && tail -n 80 "$stderr" || true
  done
done
printf '%s\n' '== lock and queue =='
ls -ld {ROOT!r}/.dayoa_agent/write.lock 2>&1 || true
squeue -u ubuntu || true
"""
    result = run_shell(
        target.instance_id,
        REGION,
        script,
        profile=PROFILE,
        as_user="ubuntu",
        timeout=300,
        comment="Read Take222 NICU Truvari root-cause logs after controller exit",
    )
    print(result.stdout)
    if result.stderr:
        print(result.stderr)
    return 0 if result.status == "Success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
