set -euo pipefail

analysis_id=ccv20260529r39_illumina_bclconvert
repo=/fsx/analysis_results/ubuntu/${analysis_id}/daylily-omics-analysis
cd "${repo}"

echo "=== timestamp ==="
date -u +%Y-%m-%dT%H:%M:%SZ
echo "=== filesystem ==="
df -h /fsx
echo "=== scratch roots ==="
find .bclconvert_scratch -mindepth 1 -maxdepth 1 -type d -printf '%TY-%Tm-%TdT%TH:%TM:%TS %p\n' 2>/dev/null | sort || true
echo "=== scratch sizes ==="
du -sh .bclconvert_scratch 2>/dev/null || true
for scratch_dir in .bclconvert_scratch/*; do
  [ -d "$scratch_dir" ] || continue
  du -sh "$scratch_dir" 2>/dev/null || true
  du -sh "$scratch_dir/run" 2>/dev/null || true
  du -sh "$scratch_dir/fastqs" 2>/dev/null || true
done
echo "=== result sizes ==="
du -sh results/runs/20260514_LH01106_0009_B23TVLGLT4/bclconvert 2>/dev/null || true
du -sh results/runs/20260514_LH01106_0009_B23TVLGLT4/bclconvert/fastqs 2>/dev/null || true
echo "=== newest scratch fastqs ==="
find .bclconvert_scratch -path '*/fastqs/*' -type f -printf '%TY-%Tm-%TdT%TH:%TM:%TS %s %p\n' 2>/dev/null | sort | tail -n 40 || true
echo "=== bcl log tail ==="
tail -n 120 results/runs/20260514_LH01106_0009_B23TVLGLT4/bclconvert/logs/run_bclconvert.log 2>/dev/null || true
