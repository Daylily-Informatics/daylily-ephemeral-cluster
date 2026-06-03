#!/usr/bin/env bash
set -u

analysis_root="/fsx/analysis_results/ubuntu/ccv20260530r42_illumina_bclconvert/daylily-omics-analysis"
status_file="/home/ubuntu/daylily-runs/ccv20260530r42_bclconvert_rc0_direct/status.json"
cmd='bin/day_run produce_bclconvert_fastqs_and_metrics -p -j 20 -k --config run_context_file=config/runs.tsv bootstrap_bclconvert=true'
mkdir -p "$(dirname "$status_file")"

write_status() {
  python3 - <<PY
import json
from pathlib import Path
Path("${status_file}").write_text(json.dumps({
  "session_name": "ccv20260530r42_bclconvert_rc0_direct",
  "repo_path": "${analysis_root}",
  "command": "${cmd}",
  "started_at": "${started_at:-}",
  "completed_at": "${completed_at:-}",
  "exit_code": None if "${exit_code:-__PENDING__}" == "__PENDING__" else int("${exit_code:-1}"),
}, indent=2, sort_keys=True) + "\n")
PY
}

started_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
completed_at=""
exit_code="__PENDING__"
write_status

cd "$analysis_root" || exit 2
if [[ -f "$HOME/miniconda3/etc/profile.d/conda.sh" ]]; then
  . "$HOME/miniconda3/etc/profile.d/conda.sh"
  conda activate DAY-EC
fi
set +u
. dyoainit --project dyec-test --skip-project-check
dyo_rc=$?
. bin/day_activate slurm hg38 remote
act_rc=$?
set -u
echo "dyoainit_rc=$dyo_rc"
echo "day_activate_rc=$act_rc"
if [[ "$dyo_rc" != "0" || "$act_rc" != "0" ]]; then
  completed_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  exit_code="97"
  write_status
  exit 97
fi

echo "command=$cmd"
set +e
eval "$cmd"
rc=$?
set -e
completed_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
exit_code="$rc"
write_status
cat "$status_file"
exit "$rc"
