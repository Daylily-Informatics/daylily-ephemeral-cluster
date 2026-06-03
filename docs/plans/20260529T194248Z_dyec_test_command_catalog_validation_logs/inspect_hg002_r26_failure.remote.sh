#!/usr/bin/env bash
set -euo pipefail

session="ccv20260529r26_illumina_hg002_kitchensink_multiqc"
repo="/fsx/analysis_results/ubuntu/${session}/daylily-omics-analysis"

echo "## session"
printf 'session=%s\nrepo=%s\n' "$session" "$repo"
test -d "$repo"

echo "## newest files"
find "$repo" -type f -printf '%T@ %s %p\n' | sort -nr | head -n 40 || true

echo "## snakemake logs"
find "$repo/.snakemake/log" -maxdepth 1 -type f -printf '%T@ %s %p\n' 2>/dev/null | sort -nr | head -n 20 || true

echo "## failure markers"
set +o pipefail
grep -RInE 'Error in rule|WorkflowError|RuleException|MissingInputException|InputFunctionException|Traceback|failed|error:|Error:|returned non-zero|exit code|Killed|Cannot|Unable' \
  "$repo/.snakemake/log" \
  "$repo/logs" \
  "$repo/sbatch_errs.log" \
  "$repo/unlock_fails.log" \
  "$repo/daylily.failed_run" \
  "$repo/pipeline_workflow_final_failed.mmd" \
  "$repo/results/day/hg38" \
  2>/dev/null | tail -n 220 || true
set -o pipefail

echo "## final snakemake log tails"
for log in $(find "$repo/.snakemake/log" -maxdepth 1 -type f -printf '%T@ %p\n' 2>/dev/null | sort -nr | head -n 4 | awk '{print $2}'); do
  echo "### $log"
  tail -n 180 "$log" | cut -c1-320
done

echo "## selected rule log tails"
find "$repo/results/day/hg38" -type f \
  \( -name '*.log' -o -name '*.err' -o -name '*.out' \) \
  -printf '%T@ %p\n' 2>/dev/null | sort -nr | head -n 16 | awk '{print $2}' | while read -r log; do
    echo "### $log"
    tail -n 80 "$log" | cut -c1-320
  done
