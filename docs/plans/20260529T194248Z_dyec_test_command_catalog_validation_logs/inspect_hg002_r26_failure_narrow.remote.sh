#!/usr/bin/env bash
set -euo pipefail

session="ccv20260529r26_illumina_hg002_kitchensink_multiqc"
repo="/fsx/analysis_results/ubuntu/${session}/daylily-omics-analysis"
main_log="$repo/.snakemake/log/2026-05-30T065050.641034.snakemake.log"

echo "## session"
printf 'session=%s\nrepo=%s\nmain_log=%s\n' "$session" "$repo" "$main_log"

echo "## failed sentinel"
cat "$repo/daylily.failed_run" 2>/dev/null || true
echo

echo "## main snakemake failure markers"
grep -nE 'Error in rule|WorkflowError|RuleException|MissingInputException|InputFunctionException|Traceback|Exiting because|failed|returned non-zero|exit code|Killed|Cannot|Unable|Error:' "$main_log" | tail -n 80 || true

echo "## main snakemake tail"
tail -n 220 "$main_log" | cut -c1-360

echo "## sbatch error tail"
tail -n 220 "$repo/sbatch_errs.log" | cut -c1-360 || true

echo "## recent slurm error files"
find "$repo/logs/slurm" -type f -name '*.err' -printf '%T@ %s %p\n' 2>/dev/null | sort -nr | head -n 20 || true

echo "## recent slurm error tails"
find "$repo/logs/slurm" -type f -name '*.err' -printf '%T@ %p\n' 2>/dev/null | sort -nr | head -n 8 | awk '{print $2}' | while read -r err; do
  echo "### $err"
  tail -n 60 "$err" | cut -c1-360
done
