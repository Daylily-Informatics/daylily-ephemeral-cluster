#!/usr/bin/env python3
"""Read-only evidence for Take222 failed external Slurm job 3919."""

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
dyec analysis visit --analysis-root {ROOT!r} --mode read --intent 'Inspect Take222 failed external Slurm job 3919 read-only' || true
printf '%s\n' '== UTC =='
date -u +%Y-%m-%dT%H:%M:%SZ
printf '%s\n' '== accounting =='
sacct -j 3919 -X -P -o JobIDRaw,JobName,State,ExitCode,DerivedExitCode,Elapsed,Start,End,NodeList,Reason,Comment,StdOut,StdErr || true
printf '%s\n' '== controller retry context =='
rg -n -A 35 "Error executing rule sentdhiomr2_segdup_gene on cluster \(jobid: 262, external: 3919" {LIVE_LOG!r} || true
printf '%s\n' '== failed stdout =='
tail -n 120 {CHECKOUT!r}/logs/slurm/sentdhiomr2_segdup_gene/sentdhiomr2_segdup_gene.NA20775-qhyxr5gkfymvhd.262.out 2>/dev/null || true
printf '%s\n' '== failed stderr =='
tail -n 120 {CHECKOUT!r}/logs/slurm/sentdhiomr2_segdup_gene/sentdhiomr2_segdup_gene.NA20775-qhyxr5gkfymvhd.262.err 2>/dev/null || true
printf '%s\n' '== CYP11B1 rule log =='
tail -n 180 {CHECKOUT!r}/results/day/hg38/NA20775-qhyxr5gkfymvhd/align/sentmm2ont/na/snv/sentdhiomr2/logs/NA20775-qhyxr5gkfymvhd.sentdhiomr2.segdup.CYP11B1.log 2>/dev/null || true
printf '%s\n' '== replacement candidates =='
sacct -S 2026-08-03T19:20:00 -u ubuntu -X -n -P -o JobIDRaw,JobName,State,ExitCode,Elapsed,NodeList \
  | rg 'sentdhiomr2_segdup_gene-NA20775' || true
"""
    result = run_shell(
        target.instance_id,
        REGION,
        script,
        profile=PROFILE,
        as_user="ubuntu",
        timeout=300,
        comment="Inspect Take222 failed Slurm job 3919 read-only",
    )
    print(result.stdout)
    if result.stderr:
        print(result.stderr)
    return 0 if result.status == "Success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
