set -euo pipefail
repo=/fsx/analysis_results/ubuntu/ccv20260529r39_illumina_bclconvert/daylily-omics-analysis
scratch="$repo/.bclconvert_scratch/3310.25321"
echo now=$(date -u +%Y-%m-%dT%H:%M:%SZ)
echo host=$(hostname)
echo bcl_pid=$(pgrep -f '/usr/local/bin/bcl-convert' | tr '\n' ' ')
for pid in $(pgrep -f '/usr/local/bin/bcl-convert' || true); do ps -p "$pid" -o pid,stat,pcpu,pmem,etime,rss,vsz,comm,args --no-headers | cut -c1-320; done
echo scratch_total=$(du -sh "$scratch" 2>/dev/null | awk '{print $1}')
echo scratch_run=$(du -sh "$scratch/run" 2>/dev/null | awk '{print $1}')
echo scratch_fastqs=$(du -sh "$scratch/fastqs" 2>/dev/null | awk '{print $1}')
echo fastq_file_count=$(find "$scratch/fastqs" -type f 2>/dev/null | wc -l || true)
echo fastq_bytes=$(du -sB1 "$scratch/fastqs" 2>/dev/null | awk '{print $1}' || true)
echo newest_fastq_files
find "$scratch/fastqs" -maxdepth 4 -type f -printf '%TY-%Tm-%TdT%TH:%TM:%TS %s %p\n' 2>/dev/null | sort | tail -20 || true
echo log_mtime=$(stat -c '%y %s' "$repo/results/runs/20260514_LH01106_0009_B23TVLGLT4/bclconvert/logs/run_bclconvert.log" || true)
df -h /fsx "$scratch" "$scratch/fastqs" 2>/dev/null || true
