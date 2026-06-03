set -euo pipefail
echo "tmux_sessions:"
tmux ls || true
echo
echo "workflow_processes:"
ps -eo pid,ppid,stat,etime,cmd --forest \
  | grep -E 'ccv20260529r22_ont_run_qc|ccv20260529r24_illumina_bclconvert|dyec|fsx|DataRepository|python|tmux|day_run|snakemake' \
  | grep -v grep || true
echo
echo "slurm_queue:"
squeue -o "%.18i %.9P %.12j %.8u %.2t %.10M %.6D %R" || true
