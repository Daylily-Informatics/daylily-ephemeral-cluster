#!/usr/bin/env bash
#SBATCH --job-name=bcl2fq_scratch_to_dra
#SBATCH --partition=bcl2fq
#SBATCH --constraint=nvme48
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=48
#SBATCH --mem=300G
#SBATCH --exclusive
#SBATCH --comment=dyec0602bcl
#SBATCH --output=/home/ubuntu/daylily-runs/bcl2fq_scratch_to_dra_20260603T011121Z/slurm-%j.out
#SBATCH --error=/home/ubuntu/daylily-runs/bcl2fq_scratch_to_dra_20260603T011121Z/slurm-%j.err

set -euo pipefail

RUN_DIR=/fsx/run_dir_mounts/20260514_LH01106_0009_B23TVLGLT4
SAMPLE_SHEET="${RUN_DIR}/SampleSheet.csv"
DEST="${RUN_DIR}/fasts_from_bclconvert"
WORK_BASE=/home/ubuntu/daylily-runs/bcl2fq_scratch_to_dra_20260603T011121Z
LOG_DIR="${WORK_BASE}/logs"
SCRATCH_ROOT=/scratch
SCRATCH_WORK="${SCRATCH_ROOT}/bcl2fq_scratch_to_dra_${SLURM_JOB_ID:-manual}"
SCRATCH_OUT="${SCRATCH_WORK}/fastqs"
CONTAINER_URI=docker://nfcore/bclconvert:4.0.3

mkdir -p "${LOG_DIR}"
LOG="${LOG_DIR}/bclconvert_${SLURM_JOB_ID:-manual}.log"
: > "${LOG}"

log() {
  printf '%s %s\n' "$(date -Is)" "$*" | tee -a "${LOG}"
}

log "starting bcl2fq scratch-to-DRA test"
log "host=$(hostname)"
log "slurm_job_id=${SLURM_JOB_ID:-}"
log "slurm_cpus_per_task=${SLURM_CPUS_PER_TASK:-}"
log "run_dir=${RUN_DIR}"
log "sample_sheet=${SAMPLE_SHEET}"
log "dest=${DEST}"
log "scratch_work=${SCRATCH_WORK}"

test -d "${RUN_DIR}"
test -s "${SAMPLE_SHEET}"
test -d "${SCRATCH_ROOT}"
if [[ ! -d "${DEST}" ]]; then
  log "destination directory is missing: ${DEST}"
  exit 12
fi
if find "${DEST}" -mindepth 1 -print -quit | grep -q .; then
  log "destination is not empty; refusing to overwrite: ${DEST}"
  exit 13
fi

mkdir -p "${SCRATCH_OUT}"
df -h "${RUN_DIR}" "${SCRATCH_ROOT}" "${DEST}" | tee -a "${LOG}"

log "checking bcl-convert container"
singularity exec --bind /fsx:/fsx --bind /scratch:/scratch "${CONTAINER_URI}" bcl-convert --version | tee -a "${LOG}"

BCL_FLAGS=(
  --bcl-input-directory "${RUN_DIR}"
  --output-directory "${SCRATCH_OUT}"
  --sample-sheet "${SAMPLE_SHEET}"
  --strict-mode false
  --first-tile-only false
  --bcl-sampleproject-subdirectories false
  --fastq-gzip-compression-level 1
  --bcl-num-parallel-tiles 8
  --bcl-num-conversion-threads 2
  --bcl-num-compression-threads 24
  --bcl-num-decompression-threads 8
  --shared-thread-odirect-output false
  --output-legacy-stats true
  --num-unknown-barcodes-reported 1000
  -f
)

printf 'bcl-convert command:' | tee -a "${LOG}"
printf ' %q' singularity exec --bind /fsx:/fsx --bind /scratch:/scratch "${CONTAINER_URI}" bcl-convert "${BCL_FLAGS[@]}" | tee -a "${LOG}"
printf '\n' | tee -a "${LOG}"

log "running bcl-convert with scratch output"
singularity exec --bind /fsx:/fsx --bind /scratch:/scratch "${CONTAINER_URI}" bcl-convert "${BCL_FLAGS[@]}" >> "${LOG}" 2>&1

test -s "${SCRATCH_OUT}/Reports/fastq_list.csv"
test -s "${SCRATCH_OUT}/Reports/Demultiplex_Stats.csv"
log "bcl-convert completed; moving output from scratch to DRA"
du -sh "${SCRATCH_OUT}" | tee -a "${LOG}"

rsync -a --remove-source-files --human-readable --stats "${SCRATCH_OUT}/" "${DEST}/" | tee -a "${LOG}"
find "${SCRATCH_OUT}" -depth -type d -empty -delete || true
find "${SCRATCH_WORK}" -depth -type d -empty -delete || true

test -s "${DEST}/Reports/fastq_list.csv"
test -s "${DEST}/Reports/Demultiplex_Stats.csv"
log "DRA destination populated"
du -sh "${DEST}" | tee -a "${LOG}"
df -h "${RUN_DIR}" "${SCRATCH_ROOT}" "${DEST}" | tee -a "${LOG}"
log "finished bcl2fq scratch-to-DRA test"
