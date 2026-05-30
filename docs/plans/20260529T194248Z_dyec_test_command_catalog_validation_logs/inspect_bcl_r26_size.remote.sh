set -euo pipefail

analysis_id=ccv20260529r26_illumina_bclconvert
repo=/fsx/analysis_results/ubuntu/${analysis_id}/daylily-omics-analysis
cd "${repo}"

echo "=== timestamp ==="
date -u +%Y-%m-%dT%H:%M:%SZ
echo "=== filesystem ==="
df -h /fsx
echo "=== scratch sizes ==="
du -sh .bclconvert_scratch 2>/dev/null || true
du -sh .bclconvert_scratch/2660.35306 2>/dev/null || true
du -sh .bclconvert_scratch/2660.35306/run 2>/dev/null || true
du -sh .bclconvert_scratch/2660.35306/fastqs 2>/dev/null || true
echo "=== result sizes ==="
du -sh results/runs/20260514_LH01106_0009_B23TVLGLT4/bclconvert 2>/dev/null || true
du -sh results/runs/20260514_LH01106_0009_B23TVLGLT4/bclconvert/fastqs 2>/dev/null || true
echo "=== newest scratch fastqs ==="
find .bclconvert_scratch/2660.35306/fastqs -maxdepth 1 -type f -printf '%TY-%Tm-%TdT%TH:%TM:%TS %s %p\n' 2>/dev/null | sort | tail -n 40 || true
echo "=== bcl log tail ==="
tail -n 80 results/runs/20260514_LH01106_0009_B23TVLGLT4/bclconvert/logs/run_bclconvert.log 2>/dev/null || true
