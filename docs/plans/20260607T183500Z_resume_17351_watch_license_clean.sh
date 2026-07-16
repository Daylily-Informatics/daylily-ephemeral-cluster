#!/usr/bin/env bash
set -euo pipefail

SCONTROL="/opt/slurm/bin/scontrol"
ANALYSIS="/fsx/analysis_results/hyb-only/hybonly_hybrid_hiomr_na4_ds20x_x8_fullvars_5017_20260607T124257Z/daylily-omics-analysis"
JOB_LIST="17351,16939,18791,18676,18677,18334"
JOB="17351"
LOG="${ANALYSIS}/results/day/hg38_broad/HYB-4Coriells-chip3-chip4-ds20x-NA03986-DMPK-chip3-chip4-barcode20-chip4-PF-ILMN-NOVASEQ/align/sentmm2ont/dmd/snv/sentdhiomr/log/HYB-4Coriells-chip3-chip4-ds20x-NA03986-DMPK-chip3-chip4-barcode20-chip4-PF-ILMN-NOVASEQ.sentmm2ont.dmd.4.stage3.log"

err_count() {
  grep -Ec 'License server down|License server not responding|Failed to connect: Connection refused' "$1" || true
}

echo "START $(date -u +%Y-%m-%dT%H:%M:%SZ)"
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
echo "DONE $(date -u +%Y-%m-%dT%H:%M:%SZ)"
