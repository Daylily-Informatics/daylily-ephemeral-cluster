set -euo pipefail

echo "=== timestamp ==="
date -u +%Y-%m-%dT%H:%M:%SZ
echo "=== filesystem ==="
df -h /fsx
echo "=== largest validation analysis dirs ==="
du -sh /fsx/analysis_results/ubuntu/ccv20260529* 2>/dev/null | sort -h | tail -n 40 || true
echo "=== largest bcl scratch dirs ==="
du -sh /fsx/analysis_results/ubuntu/ccv20260529*/daylily-omics-analysis/.bclconvert_scratch 2>/dev/null | sort -h | tail -n 20 || true
