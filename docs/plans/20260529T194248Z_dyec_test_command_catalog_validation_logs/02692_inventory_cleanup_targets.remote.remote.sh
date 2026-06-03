set -euo pipefail
echo '=== fsx capacity ==='
df -h /fsx || true
echo '=== analysis dirs ccv20260529 ==='
if [ -d /fsx/analysis_results/ubuntu ]; then
  find /fsx/analysis_results/ubuntu -maxdepth 1 -mindepth 1 -type d -name 'ccv20260529*' -printf '%f\n' | sort | while read -r d; do
    status=/fsx/analysis_results/ubuntu/$d/daylily-run/status.json
    if [ -f "$status" ]; then
      ec=$(python3 -c 'import json,sys; p=json.load(open(sys.argv[1])); print(p.get("exit_code"));' "$status" 2>/dev/null || echo unknown)
      done_at=$(python3 -c 'import json,sys; p=json.load(open(sys.argv[1])); print(p.get("completed_at"));' "$status" 2>/dev/null || echo unknown)
    else
      ec=no_status
      done_at=no_status
    fi
    size=$(du -sh "/fsx/analysis_results/ubuntu/$d" 2>/dev/null | awk '{print $1}' || echo '?')
    printf '%s\t%s\t%s\t%s\n' "$d" "$size" "$ec" "$done_at"
  done
fi
echo '=== staging dirs ==='
if [ -d /fsx/staging/staged_external_sequencing_data ]; then
  find /fsx/staging/staged_external_sequencing_data -maxdepth 1 -mindepth 1 -type d -name 'remote_stage_20260530*' -printf '%f\n' | sort | while read -r d; do
    size=$(du -sh "/fsx/staging/staged_external_sequencing_data/$d" 2>/dev/null | awk '{print $1}' || echo '?')
    printf '%s\t%s\n' "$d" "$size"
  done
fi
