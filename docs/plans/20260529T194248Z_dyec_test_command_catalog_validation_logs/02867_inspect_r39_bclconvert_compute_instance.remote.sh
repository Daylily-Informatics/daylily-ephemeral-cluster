set -euo pipefail
date -u +%Y-%m-%dT%H:%M:%SZ
hostname -f || hostname
repo=/fsx/analysis_results/ubuntu/ccv20260529r39_illumina_bclconvert/daylily-omics-analysis
echo '=== ps top ==='
ps -eo pid,ppid,stat,pcpu,pmem,etime,args --sort=-pcpu | head -40
echo '=== bcl/singularity ==='
ps -eo pid,ppid,stat,pcpu,pmem,etime,args | egrep 'bcl-convert|singularity|run_bclconvert|cp -L' | grep -v egrep || true
echo '=== scratch sizes ==='
du -sh "$repo/.bclconvert_scratch" "$repo/.bclconvert_scratch"/* 2>/dev/null || true
echo '=== recent scratch files ==='
find "$repo/.bclconvert_scratch" -maxdepth 5 -type f -printf '%TY-%Tm-%TdT%TH:%TM:%TS %s %p\n' 2>/dev/null | sort | tail -60 || true
echo '=== df ==='
df -h /fsx "$repo/.bclconvert_scratch" || true
