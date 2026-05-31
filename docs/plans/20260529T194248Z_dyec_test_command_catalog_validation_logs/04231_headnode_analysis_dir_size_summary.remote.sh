#!/usr/bin/env bash
set -euo pipefail

root="/fsx/analysis_results/ubuntu"
active="ccv20260530r56_illumina_bclconvert"

echo "=== now ==="
date -u +%Y-%m-%dT%H:%M:%SZ

echo "=== fsx ==="
df -hT /fsx

echo "=== largest validation analysis dirs ==="
if [ -d "$root" ]; then
  du -sh "$root"/ccv* 2>/dev/null | sort -h | tail -40
fi

echo "=== active guard ==="
du -sh "$root/$active" 2>/dev/null || true

echo "=== successful-export marker candidates ==="
find "$root" -maxdepth 2 -mindepth 1 -type d -name 'ccv*' -printf '%f\n' 2>/dev/null | sort | tail -80
