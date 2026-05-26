set -euo pipefail
SESSION=hg003a_ont_snv_alignstats_1018_191_preservetmp
REPO=/fsx/analysis_results/johnm/${SESSION}/daylily-omics-analysis
echo "== latest snakemake logs =="
find "${REPO}/.snakemake/log" -type f -printf '%T@ %p\n' 2>/dev/null | sort -nr | head -10 || true
find "${REPO}/.snakemake/log" -type f -printf '%T@ %p\n' 2>/dev/null | sort -nr | head -5 | cut -d' ' -f2- | while read -r LOGPATH; do
  echo "== log ${LOGPATH} tail =="
  tail -n 180 "${LOGPATH}" || true
done
echo "== full slurm log tree names =="
find "${REPO}" -path '*logs/slurm*' -print 2>/dev/null | sort | sed -n '1,240p' || true
echo "== pre_prep declared log =="
LOG="${REPO}/results/day/hg38_broad/20260514-LH01106-0009-B23TVLGLT4-HG003-a-20260514-ILMN-Altair-Run-3-0-HG003-a-PF-ILMN-NOVASEQ/align/ont/logs/20260514-LH01106-0009-B23TVLGLT4-HG003-a-20260514-ILMN-Altair-Run-3-0-HG003-a-PF-ILMN-NOVASEQ.cram.log"
ls -l "$LOG" 2>/dev/null || true
[ -f "$LOG" ] && tail -n 120 "$LOG" || true
echo "== scontrol 180 =="
scontrol show job 180 2>&1 || true
echo "== squeue all =="
squeue -o '%.18i %.9P %.45j %.12u %.12T %.10M %.6D %.25R %.8C %.12m' || true
