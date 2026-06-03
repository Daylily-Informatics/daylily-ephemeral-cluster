set -euo pipefail

for aid in ccv20260529r15_illumina_bclconvert ccv20260529r15_illumina_run_qc_bclconvert; do
  repo="/fsx/analysis_results/ubuntu/${aid}/daylily-omics-analysis"
  echo "=== ${aid} status ==="
  if [[ -f "/home/ubuntu/daylily-runs/${aid}/status.json" ]]; then
    cat "/home/ubuntu/daylily-runs/${aid}/status.json"
  else
    echo "missing status"
  fi
  log="${repo}/results/runs/20260514_LH01106_0009_B23TVLGLT4/bclconvert/logs/run_bclconvert.log"
  echo "=== ${aid} bclconvert log tail ==="
  if [[ -f "${log}" ]]; then
    tail -n 120 "${log}"
  else
    echo "missing ${log}"
  fi
done

echo "=== run mount ls ==="
ls -ld /fsx/run_dir_mounts/20260513_ONT_HG003 /fsx/run_dir_mounts/20260514_LH01106_0009_B23TVLGLT4 2>&1 || true
echo "=== df ==="
df -h /fsx /dev/shm 2>&1 || true
echo "=== slurm ==="
squeue -o '%i %P %C %t %N %m %M %D %j' || true
