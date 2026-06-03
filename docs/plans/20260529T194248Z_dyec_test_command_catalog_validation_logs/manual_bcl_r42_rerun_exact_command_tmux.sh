#!/usr/bin/env bash
set -euo pipefail

analysis_root="/fsx/analysis_results/ubuntu/ccv20260530r42_illumina_bclconvert/daylily-omics-analysis"
session="ccv20260530r42_bclconvert_rc0_recheck"
run_dir="/home/ubuntu/daylily-runs/${session}"
status_file="${run_dir}/status.json"
tmux_log="${run_dir}/tmux.log"

mkdir -p "$run_dir"
cd "$analysis_root"

python - <<'PY'
from pathlib import Path
path = Path("workflow/rules/bclconvert.smk")
text = path.read_text()
marker = "localrules:\n    bclconvert_validate_inputs,\n"
patch = (
    "localrules:\n"
    "    bclconvert_validate_inputs,\n"
    "    run_bclconvert,\n"
    "    bclconvert_metrics_summary,\n"
    "    bclconvert_generate_units_tsv,\n"
)
if "run_bclconvert,\n    bclconvert_metrics_summary" not in text:
    if marker not in text:
        raise SystemExit("ERROR: localrules marker missing")
    text = text.replace(marker, patch, 1)
    path.write_text(text)
PY

cat >"${run_dir}/rerun.sh" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
status_file="/home/ubuntu/daylily-runs/ccv20260530r42_bclconvert_rc0_recheck/status.json"
repo="/fsx/analysis_results/ubuntu/ccv20260530r42_illumina_bclconvert/daylily-omics-analysis"
cmd='bin/day_run produce_bclconvert_fastqs_and_metrics -p -j 20 -k --config run_context_file=config/runs.tsv bootstrap_bclconvert=true'
write_status() {
  python3 - <<PY
import json
from pathlib import Path
Path("${status_file}").write_text(json.dumps({
  "session_name": "ccv20260530r42_bclconvert_rc0_recheck",
  "repo_path": "${repo}",
  "command": "${cmd}",
  "started_at": "${started_at:-}",
  "completed_at": "${completed_at:-}",
  "exit_code": None if "${exit_code:-__PENDING__}" == "__PENDING__" else int("${exit_code:-1}"),
}, indent=2, sort_keys=True) + "\n")
PY
}
started_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
exit_code="__PENDING__"
completed_at=""
write_status
cd "$repo"
if [[ -f "$HOME/miniconda3/etc/profile.d/conda.sh" ]]; then
  . "$HOME/miniconda3/etc/profile.d/conda.sh"
  conda activate DAY-EC
fi
unset PROJECT || true
set +u
. dyoainit --project dyec-test --skip-project-check
. bin/day_activate slurm hg38 remote
set -u
set +e
eval "$cmd"
rc=$?
set -e
completed_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
exit_code="$rc"
write_status
exit "$rc"
SH
chmod +x "${run_dir}/rerun.sh"

tmux_session_name="${session//[^A-Za-z0-9_-]/_}"
if tmux has-session -t "=${tmux_session_name}" 2>/dev/null; then
  tmux kill-session -t "=${tmux_session_name}"
fi
tmux new-session -d -s "$tmux_session_name" "bash -il '${run_dir}/rerun.sh' > '${tmux_log}' 2>&1"
echo "started_session=$tmux_session_name"
echo "run_dir=$run_dir"
echo "status_file=$status_file"
echo "tmux_log=$tmux_log"
