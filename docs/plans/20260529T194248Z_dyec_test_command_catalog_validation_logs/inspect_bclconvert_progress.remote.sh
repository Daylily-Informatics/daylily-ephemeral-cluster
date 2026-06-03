set -euo pipefail
repo=/fsx/analysis_results/ubuntu/ccv20260529r19_illumina_bclconvert/daylily-omics-analysis
cd "$repo"
echo "=== status ==="
cat /home/ubuntu/daylily-runs/ccv20260529r19_illumina_bclconvert/status.json
echo "=== bclconvert log tail ==="
tail -n 80 results/runs/20260514_LH01106_0009_B23TVLGLT4/bclconvert/logs/run_bclconvert.log || true
echo "=== scratch usage ==="
du -sh /fsx/scratch/dayoa_bclconvert /fsx/scratch/dayoa_bclconvert/* 2>/dev/null || true
echo "=== result fastqs ==="
find results/runs/20260514_LH01106_0009_B23TVLGLT4/bclconvert/fastqs -maxdepth 3 -type f 2>/dev/null | head -n 40 || true
