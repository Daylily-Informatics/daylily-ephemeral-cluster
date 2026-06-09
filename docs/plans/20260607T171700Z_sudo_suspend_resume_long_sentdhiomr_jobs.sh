#!/usr/bin/env bash
set -euo pipefail

JOBS=(17351 16939 18791 18676 18677 18334)
LIST="$(IFS=,; echo "${JOBS[*]}")"

echo "START $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "BEFORE"
squeue -j "$LIST" -o "%i|%P|%j|%u|%T|%M|%D|%R" || true

ACTIVE=()
for job_id in "${JOBS[@]}"; do
  if squeue -h -j "$job_id" >/dev/null 2>&1 && [[ -n "$(squeue -h -j "$job_id" -o "%i" || true)" ]]; then
    ACTIVE+=("$job_id")
  else
    echo "SKIP_NOT_IN_QUEUE job=${job_id}"
  fi
done

echo "SUSPENDING_WITH_SUDO ${ACTIVE[*]:-none} $(date -u +%Y-%m-%dT%H:%M:%SZ)"
for job_id in "${ACTIVE[@]}"; do
  echo "sudo scontrol suspend ${job_id}"
  sudo scontrol suspend "$job_id" || echo "SUSPEND_FAILED job=${job_id} rc=$?"
done

echo "AFTER_SUSPEND"
squeue -j "$LIST" -o "%i|%P|%j|%u|%T|%M|%D|%R" || true

echo "WAIT_60_START $(date -u +%Y-%m-%dT%H:%M:%SZ)"
sleep 60

echo "RESUME_START $(date -u +%Y-%m-%dT%H:%M:%SZ)"
idx=0
count="${#ACTIVE[@]}"
for job_id in "${ACTIVE[@]}"; do
  idx=$((idx + 1))
  echo "RESUME_WITH_SUDO job=${job_id} idx=${idx}/${count} at $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  sudo scontrol resume "$job_id" || echo "RESUME_FAILED job=${job_id} rc=$?"
  squeue -j "$job_id" -o "%i|%P|%j|%u|%T|%M|%D|%R" || true
  if [[ "$idx" -lt "$count" ]]; then
    sleep 60
  fi
done

echo "FINAL $(date -u +%Y-%m-%dT%H:%M:%SZ)"
squeue -j "$LIST" -o "%i|%P|%j|%u|%T|%M|%D|%R" || true
