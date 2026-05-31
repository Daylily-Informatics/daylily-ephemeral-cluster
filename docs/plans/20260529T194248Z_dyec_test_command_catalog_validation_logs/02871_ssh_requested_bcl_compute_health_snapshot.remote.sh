set -euo pipefail
repo=/fsx/analysis_results/ubuntu/ccv20260529r39_illumina_bclconvert/daylily-omics-analysis
run=20260514_LH01106_0009_B23TVLGLT4
scratch="$repo/.bclconvert_scratch/3310.25321"
out="$scratch/fastqs"
log="$repo/results/runs/$run/bclconvert/logs/run_bclconvert.log"
echo "=== identity ==="
date -u +%Y-%m-%dT%H:%M:%SZ
hostname -f || hostname
id
uptime
printf 'instance_id='; curl -s --max-time 2 http://169.254.169.254/latest/meta-data/instance-id || true; echo
printf 'instance_type='; curl -s --max-time 2 http://169.254.169.254/latest/meta-data/instance-type || true; echo

echo "=== bcl process ==="
bcl_pid=$(pgrep -f '^/usr/local/bin/bcl-convert ' | head -1 || true)
echo "bcl_pid=$bcl_pid"
if [[ -n "$bcl_pid" ]]; then
  ps -p "$bcl_pid" -o pid,ppid,stat,pcpu,pmem,etime,nlwp,rss,vsz,comm,args --no-headers | cut -c1-500
  echo "--- /proc/$bcl_pid/status ---"
  egrep '^(Name|State|Pid|PPid|Threads|VmRSS|VmSize|VmHWM|voluntary_ctxt_switches|nonvoluntary_ctxt_switches):' "/proc/$bcl_pid/status" || true
  echo "--- /proc/$bcl_pid/io ---"
  cat "/proc/$bcl_pid/io" || true
  echo "--- hottest bcl threads ---"
  ps -L -p "$bcl_pid" -o pid,tid,stat,pcpu,pmem,etime,comm --sort=-pcpu | head -25 || true
fi

echo "=== slurm/snakemake processes ==="
ps -eo pid,ppid,stat,pcpu,pmem,etime,args | egrep 'snakemake|bcl-convert|singularity|slurmstepd' | grep -v egrep | cut -c1-500 || true

echo "=== memory/cpu ==="
free -h
vmstat 1 5

echo "=== filesystems ==="
df -h / /tmp /dev/shm /fsx "$scratch" "$out" 2>/dev/null || true
df -i /fsx "$scratch" "$out" 2>/dev/null || true
if command -v lfs >/dev/null 2>&1; then lfs df -h /fsx || true; lfs df -i /fsx || true; fi

echo "=== progress sample before ==="
count1=$(find "$out" -type f 2>/dev/null | wc -l | tr -d ' ' || echo 0)
bytes1=$(du -sB1 "$out" 2>/dev/null | awk '{print $1}' || echo 0)
mtime1=$(find "$out" -type f -printf '%T@\n' 2>/dev/null | sort -n | tail -1 || echo 0)
echo "count=$count1 bytes=$bytes1 newest_epoch=$mtime1"
find "$out" -maxdepth 2 -type f -printf '%TY-%Tm-%TdT%TH:%TM:%TS %s %p\n' 2>/dev/null | sort | tail -12 || true
sleep 20
echo "=== progress sample after 20s ==="
count2=$(find "$out" -type f 2>/dev/null | wc -l | tr -d ' ' || echo 0)
bytes2=$(du -sB1 "$out" 2>/dev/null | awk '{print $1}' || echo 0)
mtime2=$(find "$out" -type f -printf '%T@\n' 2>/dev/null | sort -n | tail -1 || echo 0)
echo "count=$count2 bytes=$bytes2 newest_epoch=$mtime2"
echo "delta_count=$((count2-count1)) delta_bytes=$((bytes2-bytes1))"
find "$out" -maxdepth 2 -type f -printf '%TY-%Tm-%TdT%TH:%TM:%TS %s %p\n' 2>/dev/null | sort | tail -12 || true

echo "=== run log tail ==="
stat -c 'log_mtime=%y log_bytes=%s' "$log" || true
tail -n 80 "$log" || true

echo "=== kernel/system warnings ==="
sudo dmesg -T 2>/dev/null | egrep -i 'oom|killed process|lustre|i/o error|ext4|nvme|xfs|nfs|fsx|blocked for more than|hung task' | tail -80 || true
