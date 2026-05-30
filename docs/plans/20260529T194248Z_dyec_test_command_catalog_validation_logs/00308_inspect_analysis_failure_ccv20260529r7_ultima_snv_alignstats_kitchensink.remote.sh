set -euo pipefail
analysis_dir=/fsx/analysis_results/ubuntu/ccv20260529r7_ultima_snv_alignstats_kitchensink
repo_dir=/fsx/analysis_results/ubuntu/ccv20260529r7_ultima_snv_alignstats_kitchensink/daylily-omics-analysis
echo '=== status ==='
status_file=/home/ubuntu/daylily-runs/$(basename "$analysis_dir")/status.json
if [[ -f "$status_file" ]]; then cat "$status_file"; else echo "missing $status_file"; fi
echo '=== repo ==='
test -d "$repo_dir"
cd "$repo_dir"
pwd
echo '=== latest snakemake logs ==='
find .snakemake/log -maxdepth 1 -type f -printf '%T@ %p\n' 2>/dev/null | sort -n | tail -n 5 || true
latest_log=$(find .snakemake/log -maxdepth 1 -type f -printf '%T@ %p\n' 2>/dev/null | sort -n | tail -n 1 | cut -d' ' -f2- || true)
if [[ -n "$latest_log" && -f "$latest_log" ]]; then
  echo "=== latest log path: $latest_log ==="
  grep -nEi 'error|exception|traceback|missingoutput|ruleexception|failed|non-zero|killed|oom|out.of.memory|slurmstepd' "$latest_log" || true
  echo '=== latest log tail ==='
  tail -n 260 "$latest_log"
fi
echo '=== rule logs with errors ==='
find results logs -type f \( -name '*.log' -o -name '*.err' -o -name '*.out' \) 2>/dev/null | xargs grep -nEi 'error|exception|traceback|missingoutput|ruleexception|failed|non-zero|killed|oom|out.of.memory|slurmstepd' 2>/dev/null | tail -n 220 || true