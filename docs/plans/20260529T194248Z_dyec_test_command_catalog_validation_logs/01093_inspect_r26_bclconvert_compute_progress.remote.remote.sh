set -euo pipefail
aid=ccv20260529r26_illumina_bclconvert
repo="/fsx/analysis_results/ubuntu/${aid}/daylily-omics-analysis"
scratch="$repo/.bclconvert_scratch"
run_log="$repo/results/runs/20260514_LH01106_0009_B23TVLGLT4/bclconvert/logs/run_bclconvert.log"
echo "host:"
hostname
date -u
echo
echo "job_processes:"
pids="$(pgrep -f 'run_bclconvert|bcl-convert|snakemake|xargs -0 -r -P|cp -L --sparse=always' || true)"
if [[ -n "$pids" ]]; then
  ps -o pid,ppid,stat,etime,pcpu,pmem,comm -p "$(printf '%s' "$pids" | tr '\n' ',' | sed 's/,$//')" || true
else
  echo "no matching processes"
fi
echo
echo "scratch_summary:"
du -sh "$scratch" 2>/dev/null || true
find "$scratch" -type f 2>/dev/null | wc -l || true
find "$scratch" -type f -mmin -2 2>/dev/null | wc -l || true
find "$scratch" -type f -printf '%T@ %p\n' 2>/dev/null | sort -n | tail -n 20 || true
echo
echo "rsync_logs:"
find "$scratch" -path '*/rsync_logs/*' -maxdepth 5 -type f -print -exec wc -l {} \; 2>/dev/null || true
echo
echo "run_log_tail:"
tail -n 260 "$run_log" 2>/dev/null || true
echo
echo "slurm:"
squeue -o "%.18i %.9P %.12j %.8u %.2t %.10M %.6D %R" || true
sacct -j 2660 --format=JobID,JobName%40,State,ExitCode,Elapsed,AllocCPUS,NodeList -P 2>/dev/null || true
