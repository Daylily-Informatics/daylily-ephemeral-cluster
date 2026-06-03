#!/usr/bin/env bash
set -euo pipefail

WORK_BASE=/home/ubuntu/daylily-runs/bcl2fq_scratch_to_dra_20260603T011121Z
JOB_SCRIPT="${WORK_BASE}/bclconvert_scratch_to_dra.job.sh"
DEST=/fsx/run_dir_mounts/20260514_LH01106_0009_B23TVLGLT4/fasts_from_bclconvert

cd "${WORK_BASE}"
test -s "${JOB_SCRIPT}"
if [[ ! -d "${DEST}" ]]; then
  echo "destination missing: ${DEST}" >&2
  exit 12
fi
if find "${DEST}" -mindepth 1 -print -quit | grep -q .; then
  echo "destination is not empty; refusing to overwrite: ${DEST}" >&2
  exit 13
fi

job_id="$(sbatch --parsable "${JOB_SCRIPT}")"
printf '%s\n' "${job_id}" | tee "${WORK_BASE}/job_id.txt"
squeue -j "${job_id}" -o "%.18i %.12P %.24j %.8u %.2t %.10M %.6D %R" | tee "${WORK_BASE}/squeue_initial.txt"
