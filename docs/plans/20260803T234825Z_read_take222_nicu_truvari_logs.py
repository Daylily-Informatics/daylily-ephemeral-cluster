#!/usr/bin/env python3
"""Read the four terminal Take222 NICU Truvari rule logs without mutation."""

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
dyec analysis visit --analysis-root {ROOT!r} --mode read --intent 'Read terminal Take222 NICU Truvari logs' || true
for sample in HG003-cqp3zghjfqgykp HG004-9zznm9yqnkwtjr NA19235-p9yktjchebvwjf NA20775-qhyxr5gkfymvhd; do
  path={CHECKOUT!r}/results/day/hg38/$sample/align/sentmm2ont/na/snv/sentdhiomr2/logs/nicu-research/$sample.truvari.log
  printf '%s\n' "== $path =="
  stat -c '%s|%y' "$path" 2>/dev/null || true
  tail -n 80 "$path" 2>/dev/null || true
done
printf '%s\n' '== rendered conditionals =='
rg -n -C 3 'truth_analysis_unit=|if \[\[.*not_applicable' {LIVE_LOG!r} | tail -n 100 || true
printf '%s\n' '== final rendered shell block =='
sed -n '49080,49128p' {LIVE_LOG!r} || true
"""
    result = run_shell(
        target.instance_id,
        REGION,
        script,
        profile=PROFILE,
        as_user="ubuntu",
        timeout=300,
        comment="Read Take222 NICU Truvari logs",
    )
    print(result.stdout)
    if result.stderr:
        print(result.stderr)
    return 0 if result.status == "Success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
