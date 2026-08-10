#!/usr/bin/env python3
"""Read-only Take222 13.4.3 release-proof status."""

from daylily_ec.aws.ssm import resolve_headnode_instance_id, run_shell

CLUSTER = "preval-hiomr2"
PROFILE = "lsmc"
REGION = "us-west-2"
ROOT = "/fsx/analysis_results/preval-hiomr2/take222"
SESSION = "dayoa_take222_hg003_hg004_smn12_20260803"


def main() -> int:
    target = resolve_headnode_instance_id(CLUSTER, REGION, profile=PROFILE)
    script = f"""set -uo pipefail
export DAYOA_AGENT_ID=codex-take222-release-20260803
export DAYOA_AGENT_KIND=codex
export DAYOA_HUMAN_REQUESTOR='John Major'
export DAYOA_TMUX_SESSION={SESSION}
export DAYOA_LEDGER_PATH='/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster/docs/plans/20260803T234000Z_dayoa_13_4_3_dyec_release_slack_ledger.md'
dyec analysis visit --analysis-root {ROOT} --mode read --intent 'Inspect Take222 DayOA 13.4.3 release-proof status' || true
date -u +%Y-%m-%dT%H:%M:%SZ
for path in /home/ubuntu/take222_13.4.3_release_tests.rc /home/ubuntu/take222_hg003_hg004_na19235_na20775_fullcov_13.4.2_dry_20260803.rc /home/ubuntu/take222_hg003_hg004_na19235_na20775_fullcov_13.4.2_live_20260803.rc; do
  test -f "$path" && printf '%s=' "$path" && cat "$path" || true
  test -f "$path" && stat -c 'mtime=%y' "$path" || true
done
printf '%s\n' '== tests =='
tail -n 40 /home/ubuntu/take222_13.4.3_release_tests.log 2>/dev/null || true
printf '%s\n' '== dry/live log =='
rg -n 'Building DAG|Job stats:|Total jobs:|Dry run|Nothing to be done|RETURN CODE|Womp Womp|^[0-9]+ of [0-9]+ steps' {ROOT}/daylily-omics-analysis/take222_hg003_hg004_na19235_na20775_fullcov_13.4.2_dry_20260803.log 2>/dev/null | tail -n 60 || true
printf '%s\n' '== live log =='
rg -n 'allowed write|Building DAG|Job stats:|Total jobs:|Submitted job|Finished job|Trying to restart|RETURN CODE|Womp Womp|^[0-9]+ of [0-9]+ steps|ERROR:|requires a write lock' {ROOT}/daylily-omics-analysis/take222_hg003_hg004_na19235_na20775_fullcov_13.4.2_live_20260803.log 2>/dev/null | tail -n 100 || true
printf '%s\n' '== controllers =='
ps -fu ubuntu | awk '/dy-r|bin\/day_run|snakemake/ && !/awk/ {{print}}' || true
printf '%s\n' '== dry evidence =='
stat -c '%y|%s|%n' /home/ubuntu/take222_hg003_hg004_na19235_na20775_fullcov_13.4.2_dry_20260803.rc 2>/dev/null || true
stat -c '%y|%s|%n' {ROOT}/daylily-omics-analysis/take222_hg003_hg004_na19235_na20775_fullcov_13.4.2_dry_20260803.log 2>/dev/null || true
printf '%s\n' '== tmux =='
tmux capture-pane -pt {SESSION} -S -80 2>/dev/null || true
printf '%s\n' '== queue =='
squeue -u ubuntu || true
printf '%s\n' '== lock =='
ls -ld {ROOT}/.dayoa_agent/write.lock 2>&1 || true
"""
    result = run_shell(target.instance_id, REGION, script, profile=PROFILE, as_user="ubuntu", timeout=300, comment="Inspect Take222 13.4.3 release proof")
    print(result.stdout)
    if result.stderr:
        print(result.stderr)
    return 0 if result.status == "Success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
