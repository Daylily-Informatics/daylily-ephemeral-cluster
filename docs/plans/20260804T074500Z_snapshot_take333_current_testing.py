#!/usr/bin/env python3
"""Capture a bounded read-only snapshot of the current Take333 campaigns."""

from daylily_ec.aws.ssm import resolve_headnode_instance_id, run_shell


CLUSTER = "preval-hiomr2"
PROFILE = "lsmc"
REGION = "us-west-2"


def main() -> int:
    target = resolve_headnode_instance_id(CLUSTER, REGION, profile=PROFILE)
    script = r"""set -u
export DAYOA_AGENT_ID=codex-take222-report-current-snapshot-20260804
export DAYOA_AGENT_KIND=codex
export DAYOA_HUMAN_REQUESTOR='John Major'
export DAYOA_LEDGER_PATH='/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster/docs/plans/20260804T070646Z_take222_hiomr2_runtime_results_report_ledger.md'
for root in /fsx/analysis_results/preval-hiomr2/take333lc /fsx/analysis_results/preval-hiomr2/remaining-giab; do
  export DAYOA_TMUX_SESSION=$(basename "$root")
  dyec analysis visit --analysis-root "$root" --mode read --intent 'Capture current testing snapshot for Take222 technical report'
done
printf 'SNAPSHOT_UTC=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
for session in dayoa_take333lc_hg002_5x5x_20260804 dayoa_remaining_giab_20260804; do
  printf 'SESSION=%s\n' "$session"
  if tmux has-session -t "=$session" 2>/dev/null; then
    echo 'TMUX=present'
    tmux list-panes -t "=$session" -F 'PANE=#{pane_id} PID=#{pane_pid} CMD=#{pane_current_command} DEAD=#{pane_dead}'
    tmux capture-pane -pt "=$session" -S -180 2>/dev/null \
      | grep -E '([0-9]+ of [0-9]+ steps|LIVE.*RC=|WorkflowError|Error in rule|Nothing to be done|Complete log|Finished job|Exiting because)' \
      | tail -n 20 || true
    echo 'PANE_TAIL'
    tmux capture-pane -pt "=$session" -S -140 2>/dev/null | tail -n 140 | cut -c1-500 || true
  else
    echo 'TMUX=absent'
  fi
done
echo 'CONTROLLERS'
ps -u ubuntu -o pid=,ppid=,stat=,etime=,cmd= \
  | grep -E 'take333lc|remaining-giab|snakemake|daylily_run_omics_analysis_headnode' \
  | grep -v grep | cut -c1-500 || true
echo 'SQUEUE'
squeue -u ubuntu -h -o '%i|%T|%M|%j|%R' | tail -n 80 || true
echo 'SACCT_TERMINAL_SINCE_0600Z'
sacct -u ubuntu -S 2026-08-04T06:00:00 -X -n -P -o JobIDRaw,State,ExitCode,JobName \
  | grep -E 'FAILED|CANCELLED|TIMEOUT|OUT_OF_MEMORY|NODE_FAIL|PREEMPTED' | tail -n 80 || true
echo 'FSX'
df -B1 --output=size,used,avail,pcent,target /fsx | tail -n 1 || true
for root in take333lc remaining-giab; do
  base="/fsx/analysis_results/preval-hiomr2/$root/daylily-omics-analysis/results/day/hg38"
  printf 'ARTIFACTS=%s|' "$root"
  test -s "$base/reports/DAY_final_multiqc.html" && printf 'multiqc=present|' || printf 'multiqc=absent|'
  count=$(find "$base/deliveries/inflection_hiomr2_analytical_callsets_vcf_gvcf" -name package_manifest.json -type f 2>/dev/null | wc -l | tr -d ' ')
  printf 'package_manifests=%s\n' "$count"
  repo="/fsx/analysis_results/preval-hiomr2/$root/daylily-omics-analysis"
  echo "ROOT_FILES=$root"
  find "$repo" -maxdepth 1 -type f -printf '%T@|%f|%s\n' 2>/dev/null | sort -nr | head -n 30 | cut -d'|' -f2-
  for marker in daylily.successful_run daylily.failed_run; do
    if test -f "$repo/$marker"; then
      printf 'RUN_MARKER=%s|' "$marker"
      tr '\n' ' ' < "$repo/$marker"
      echo
    fi
  done
  for graph in "$repo"/pipeline_workflow_final_success.mmd "$repo"/pipeline_workflow_final_failed.mmd; do
    if test -f "$graph"; then
      printf 'FINAL_GRAPH=%s\n' "$graph"
      grep -E '([0-9]+ of [0-9]+|[0-9]+/[0-9]+|success|failed)' "$graph" | tail -n 12 | cut -c1-500 || true
    fi
  done
  echo "DELIVERY_FILES=$root"
  find "$base/deliveries" -maxdepth 7 -type f -printf '%p|%s\n' 2>/dev/null | tail -n 80
  echo "RECENT_LOGS=$root"
  find "$repo" -maxdepth 2 -type f \( -name '*.log' -o -name '*.rc' -o -name '*status*.json' \) -printf '%T@|%p\n' 2>/dev/null \
    | sort -nr | head -n 12 | cut -d'|' -f2-
  while IFS= read -r log; do
    test -n "$log" || continue
    printf 'MARKERS=%s\n' "$log"
    grep -E 'LIVE.*RC=|WorkflowError|Error in rule|Complete log|Nothing to be done|Exiting because|of [0-9]+ steps' "$log" 2>/dev/null | tail -n 16 || true
  done < <(find "$repo" -maxdepth 2 -type f -name '*.log' -printf '%T@|%p\n' 2>/dev/null | sort -nr | head -n 4 | cut -d'|' -f2-)
done
"""
    result = run_shell(
        target.instance_id,
        REGION,
        script,
        profile=PROFILE,
        as_user="ubuntu",
        timeout=300,
        comment="Capture current Take333 report snapshot",
    )
    print(result.stdout)
    if result.stderr:
        print(result.stderr)
    return 0 if result.status == "Success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
