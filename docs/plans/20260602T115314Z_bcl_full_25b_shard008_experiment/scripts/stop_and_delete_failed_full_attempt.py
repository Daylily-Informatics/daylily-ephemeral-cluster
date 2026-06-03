#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path

from daylily_ec.aws.ssm import resolve_headnode_instance_id, run_shell, wait_for_ssm_online


PROFILE = os.environ.get("PROFILE", "lsmc")
REGION = os.environ.get("REGION", "us-west-2")
CLUSTER = os.environ.get("CLUSTER", "dyec5117")
EXP_DIR = Path(
    os.environ.get(
        "EXP_DIR",
        "docs/plans/20260602T115314Z_bcl_full_25b_shard008_experiment",
    )
)
ANALYSIS = "bcl25b_full_shard008_retry1_20260602T115314Z"
RUN_DIR = f"/home/ubuntu/daylily-runs/{ANALYSIS}"
ANALYSIS_DIR = f"/fsx/analysis_results/ubuntu/{ANALYSIS}"
REPO = f"{ANALYSIS_DIR}/daylily-omics-analysis"


REMOTE_SCRIPT = f"""set -euo pipefail
ANALYSIS={ANALYSIS!r}
RUN_DIR={RUN_DIR!r}
ANALYSIS_DIR={ANALYSIS_DIR!r}
REPO={REPO!r}

echo "timestamp_utc $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "analysis $ANALYSIS"
echo "run_dir $RUN_DIR"
echo "analysis_dir $ANALYSIS_DIR"
echo "repo $REPO"
echo

echo "== before df =="
df -h /fsx || true
echo

echo "== stop tmux controller =="
if tmux has-session -t "$ANALYSIS" 2>/dev/null; then
  tmux kill-session -t "$ANALYSIS"
  echo "killed_tmux $ANALYSIS"
else
  echo "tmux_session_absent $ANALYSIS"
fi
echo

echo "== identify slurm jobs for exact repo workdir =="
job_ids=""
while read -r jobid workdir name state; do
  [ -n "$jobid" ] || continue
  if [ "$workdir" = "$REPO" ]; then
    echo "matched_job $jobid $state $name $workdir"
    job_ids="$job_ids $jobid"
  fi
done < <(squeue -h -o '%i %Z %j %T' || true)

echo
echo "== cancel matched jobs =="
if [ -n "${{job_ids// /}}" ]; then
  scancel $job_ids
  echo "scancelled$job_ids"
else
  echo "no_matched_jobs"
fi
echo

echo "== wait matched jobs absent =="
for i in $(seq 1 30); do
  remaining=""
  while read -r jobid workdir name state; do
    [ -n "$jobid" ] || continue
    if [ "$workdir" = "$REPO" ]; then
      remaining="$remaining $jobid"
    fi
  done < <(squeue -h -o '%i %Z %j %T' || true)
  if [ -z "${{remaining// /}}" ]; then
    echo "matched_jobs_absent"
    break
  fi
  echo "still_present$remaining"
  sleep 2
done
if squeue -h -o '%i %Z %j %T' | awk -v repo="$REPO" '$2==repo {{found=1}} END {{exit found?0:1}}'; then
  echo "ERROR matched jobs still present for $REPO" >&2
  exit 2
fi
echo

echo "== delete analysis dir =="
if [ -d "$ANALYSIS_DIR" ]; then
  du -sh "$ANALYSIS_DIR" || true
  rm -rf --one-file-system "$ANALYSIS_DIR"
  echo "deleted $ANALYSIS_DIR"
else
  echo "analysis_dir_absent $ANALYSIS_DIR"
fi
if [ -e "$ANALYSIS_DIR" ]; then
  echo "ERROR analysis dir still exists $ANALYSIS_DIR" >&2
  exit 3
fi
echo

echo "== after df =="
df -h /fsx || true
echo
echo "done"
"""


def main() -> int:
    out_dir = EXP_DIR / "command_logs"
    out_dir.mkdir(parents=True, exist_ok=True)
    target = resolve_headnode_instance_id(CLUSTER, REGION, profile=PROFILE)
    wait_for_ssm_online(target.instance_id, REGION, profile=PROFILE, timeout=180)
    result = run_shell(
        target.instance_id,
        REGION,
        REMOTE_SCRIPT,
        profile=PROFILE,
        timeout=300,
        comment="Stop and delete failed full-flowcell BCL attempt",
    )
    (out_dir / "stop_and_delete_failed_full_attempt.stdout.txt").write_text(
        result.stdout, encoding="utf-8"
    )
    (out_dir / "stop_and_delete_failed_full_attempt.stderr.txt").write_text(
        result.stderr, encoding="utf-8"
    )
    (out_dir / "stop_and_delete_failed_full_attempt.ssm.json").write_text(
        json.dumps(
            {
                "command_id": result.command_id,
                "instance_id": result.instance_id,
                "status": result.status,
                "response_code": result.response_code,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    print(result.stdout, end="")
    print(result.stderr, end="")
    return result.response_code


if __name__ == "__main__":
    raise SystemExit(main())
