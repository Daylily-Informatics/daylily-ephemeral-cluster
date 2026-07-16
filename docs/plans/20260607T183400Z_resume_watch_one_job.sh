#!/usr/bin/env bash
set -euo pipefail

: "${JOB:?JOB is required}"
: "${LOG:?LOG is required}"

SCONTROL="/opt/slurm/bin/scontrol"
JOB_LIST="17351,16939,18791,18676,18677,18334"

err_count() {
  grep -Ec 'License server down|License server not responding|Failed to connect: Connection refused' "$1" || true
}

echo "WAIT_BEFORE_LAUNCH $(date -u +%Y-%m-%dT%H:%M:%SZ)"
sleep 60
echo "START $(date -u +%Y-%m-%dT%H:%M:%SZ) JOB=${JOB}"
squeue -j "$JOB_LIST" -o "%i|%T|%M|%R"

before="$(err_count "$LOG")"
echo "BEFORE_LICENSE_ERROR_COUNT ${before}"

echo "RESUME ${JOB}"
sudo "$SCONTROL" resume "$JOB"
squeue -j "$JOB_LIST" -o "%i|%T|%M|%R"

sleep 60
after1="$(err_count "$LOG")"
echo "CHECK1 $(date -u +%Y-%m-%dT%H:%M:%SZ) COUNT ${after1}"
tail -n 20 "$LOG"
if (( after1 > before )); then
  echo "NEW_LICENSE_ERRORS check=1 before=${before} after=${after1}; SUSPEND ${JOB}"
  sudo "$SCONTROL" suspend "$JOB"
  squeue -j "$JOB_LIST" -o "%i|%T|%M|%R"
  exit 0
fi

echo "NO_NEW_LICENSE_ERRORS_AFTER_60S"
sleep 60
after2="$(err_count "$LOG")"
echo "CHECK2 $(date -u +%Y-%m-%dT%H:%M:%SZ) COUNT ${after2}"
tail -n 20 "$LOG"
if (( after2 > after1 )); then
  echo "NEW_LICENSE_ERRORS check=2 after1=${after1} after2=${after2}; SUSPEND ${JOB}"
  sudo "$SCONTROL" suspend "$JOB"
  squeue -j "$JOB_LIST" -o "%i|%T|%M|%R"
  exit 0
fi

echo "NO_NEW_LICENSE_ERRORS_AFTER_120S"
squeue -j "$JOB_LIST" -o "%i|%T|%M|%R"
echo "DONE $(date -u +%Y-%m-%dT%H:%M:%SZ) JOB=${JOB}"
