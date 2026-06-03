set -euo pipefail
printf '=== time ===\n'; date -Is
printf '=== tmux sessions ===\n'; tmux list-sessions 2>/dev/null || true
printf '=== daylily run dirs recent ===\n'; find /home/ubuntu/daylily-runs -maxdepth 2 -name status.json -printf '%T@ %p\n' 2>/dev/null | sort -nr | head -n 12 | while read -r _ p; do echo "--- $p"; cat "$p"; done
printf '=== snakemake/controller processes ===\n'; ps -eo pid,ppid,stat,etime,pcpu,pmem,cmd --sort=start_time | grep -E 'snakemake|day_run|tmux|bcl-convert|dyec_run_bclconvert_lane' | grep -v grep || true
printf '=== slurm ===\n'; squeue -o '%i %P %C %t %N %m %M %D %j' || true
