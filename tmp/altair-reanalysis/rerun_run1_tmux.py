#!/usr/bin/env python3
from __future__ import annotations

import shlex

from daylily_ec.aws.ssm import run_shell, write_remote_text


INSTANCE_ID = "i-07ec9d66e9a88e538"
REGION = "us-west-2"
PROFILE = "lsmc"
SESSION = "re-ana-20260512_LH01106_0006_A23K3H2LT4"
RUN_DIR = f"/home/ubuntu/daylily-runs/{SESSION}"
REPO = f"/fsx/analysis_results/johnm/{SESSION}/daylily-omics-analysis"
STAGE = "/fsx/data/staged_sample_data/remote_stage_20260520T072438Z"
STEM = "20260520T072438Z"
REMOTE_SCRIPT = "/home/ubuntu/rerun_run1_altair.sh"

BASE_COMMAND = (
    "bin/day_run produce_sent_align produce_dmd_dedup_cram produce_sentd_snv_vcf "
    "produce_snv_concordances produce_alignstats produce_relatedness produce_contam_estimate "
    "produce_verifybamid2_panel_comparison produce_mosdepth produce_multiqc_cram "
    "--config 'aligners=[\"sent\"]' 'dedupers=[\"dmd\"]' 'snv_callers=[\"sentd\"]' "
    "'multiqc_qc={\"include_no_dedup_alignment_qc\":false}' -p -j 100 -k -T 1"
)
DY_COMMAND = f"{BASE_COMMAND} -n && {BASE_COMMAND}"


script = f"""#!/usr/bin/env bash
set -uo pipefail
RUN_DIR={shlex.quote(RUN_DIR)}
REPO={shlex.quote(REPO)}
STAGE={shlex.quote(STAGE)}
STEM={shlex.quote(STEM)}
LOG="$RUN_DIR/tmux.log"
DY_COMMAND={shlex.quote(DY_COMMAND)}

{{
  echo "[INFO] Restaging config from $STAGE at $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  cp "$STAGE/${{STEM}}_samples.tsv" "$REPO/config/samples.tsv"
  cp "$STAGE/${{STEM}}_units.tsv" "$REPO/config/units.tsv"
  awk -F'\\t' 'NR<=5{{print "[CONFIG]", NR, $2, length($9), length($10), substr($9,1,60), substr($10,1,60)}}' "$REPO/config/units.tsv"
  cd "$REPO"
  started_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  . "$HOME/miniconda3/etc/profile.d/conda.sh"
  set +u
  . dyoainit --skip-project-check
  set -u
  set +e
  set +u
  . bin/day_activate slurm hg38 remote
  activate_status=$?
  set -u
  if [[ "$activate_status" != "0" ]]; then
    echo "[ERROR] day_activate failed with status $activate_status"
    workflow_status=$activate_status
  else
    eval "$DY_COMMAND"
    workflow_status=$?
  fi
  completed_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  printf '{{"session_name":"%s","repo_path":"%s","stage_dir":"%s","started_at":"%s","completed_at":"%s","exit_code":%s}}\\n' \
    "$SESSION" "$REPO" "$STAGE" "$started_at" "$completed_at" "$workflow_status" > "$RUN_DIR/status.rerun.json"
  echo "[INFO] Rerun workflow exited with status $workflow_status"
}} >>"$LOG" 2>&1
"""

write_remote_text(INSTANCE_ID, REGION, REMOTE_SCRIPT, script, profile=PROFILE)
cmd = f"chmod 700 {shlex.quote(REMOTE_SCRIPT)} && tmux send-keys -t {shlex.quote(SESSION)} {shlex.quote('bash ' + REMOTE_SCRIPT)} C-m && echo sent"
result = run_shell(
    INSTANCE_ID,
    REGION,
    cmd,
    profile=PROFILE,
    timeout=120,
    comment="Start Run1 rerun in tmux",
)
print(result.stdout)
print(result.stderr)
