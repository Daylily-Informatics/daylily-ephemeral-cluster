#!/usr/bin/env bash
set -euo pipefail

link="/fsx/analysis_results/ubuntu/ccv20260530r56_illumina_bclconvert/daylily-omics-analysis/config/run_dir_links/20260514_LH01106_0009_B23TVLGLT4"

echo "=== now ==="
date -u +%Y-%m-%dT%H:%M:%SZ

echo "=== before ==="
if [ -L "$link" ] || [ -e "$link" ]; then
  stat -c '%F %N' "$link" || true
else
  echo "absent: $link"
fi

if [ -L "$link" ]; then
  rm "$link"
  echo "removed symlink: $link"
elif [ -e "$link" ]; then
  echo "refusing to remove non-symlink path: $link"
  exit 2
else
  echo "already absent"
fi

echo "=== after ==="
if [ -L "$link" ] || [ -e "$link" ]; then
  stat -c '%F %N' "$link" || true
else
  echo "absent: $link"
fi

echo "=== parent ==="
find "$(dirname "$link")" -maxdepth 1 -mindepth 1 -printf '%M %p -> %l\n' 2>/dev/null | sort || true
