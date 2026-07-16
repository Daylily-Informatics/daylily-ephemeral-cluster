#!/usr/bin/env bash
set -euo pipefail

JOBS=(17351 16939 18791 18676 18677 18334)
LIST="$(IFS=,; echo "${JOBS[*]}")"
SCONTROL="/opt/slurm/bin/scontrol"

echo "START $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "BEFORE"
squeue -j "$LIST" -o "%i|%P|%j|%u|%T|%M|%D|%R" || true

echo "WAIT_60_START $(date -u +%Y-%m-%dT%H:%M:%SZ)"
sleep 60

echo "RESUME_START $(date -u +%Y-%m-%dT%H:%M:%SZ)"
idx=0
count="${#JOBS[@]}"
for job_id in "${JOBS[@]}"; do
  idx=$((idx + 1))
  if squeue -h -j "$job_id" >/dev/null 2>&1 && [[ -n "$(squeue -h -j "$job_id" -o "%i" || true)" ]]; then
    echo "RESUME job=${job_id} idx=${idx}/${count} at $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    sudo "$SCONTROL" resume "$job_id" || echo "RESUME_FAILED job=${job_id} rc=$?"
    squeue -j "$job_id" -o "%i|%P|%j|%u|%T|%M|%D|%R" || true
  else
    echo "SKIP_NOT_IN_QUEUE job=${job_id} at $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  fi
  if [[ "$idx" -lt "$count" ]]; then
    sleep 60
  fi
done

echo "FINAL $(date -u +%Y-%m-%dT%H:%M:%SZ)"
squeue -j "$LIST" -o "%i|%P|%j|%u|%T|%M|%D|%R" || true
