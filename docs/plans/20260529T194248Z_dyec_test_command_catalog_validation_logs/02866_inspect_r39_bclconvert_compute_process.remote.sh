set -euo pipefail
export PROJECT=dyec-test
node=i192mem-dy-all-1
partition=i192mem
echo "=== srun compute process snapshot ==="
srun --overlap --partition="$partition" --nodelist="$node" --nodes=1 --ntasks=1 bash -lc 'set -euo pipefail; date -u +%Y-%m-%dT%H:%M:%SZ; hostname -f || hostname; echo === ps ===; ps -eo pid,ppid,stat,pcpu,pmem,etime,args --sort=-pcpu | head -35; echo === bcl/singularity only ===; ps -eo pid,ppid,stat,pcpu,pmem,etime,args | egrep "bcl-convert|singularity|run_bclconvert|cp -L" | grep -v egrep || true; echo === scratch/result ===; repo=/fsx/analysis_results/ubuntu/ccv20260529r39_illumina_bclconvert/daylily-omics-analysis; du -sh "$repo/.bclconvert_scratch" "$repo/.bclconvert_scratch"/* 2>/dev/null || true; find "$repo/.bclconvert_scratch" -maxdepth 4 -type f -printf "%TY-%Tm-%TdT%TH:%TM:%TS %s %p\n" 2>/dev/null | sort | tail -80; echo === df ===; df -h /fsx "$repo/.bclconvert_scratch"; echo === iostat-ish ===; if command -v iostat >/dev/null; then iostat -xz 1 2; fi'
