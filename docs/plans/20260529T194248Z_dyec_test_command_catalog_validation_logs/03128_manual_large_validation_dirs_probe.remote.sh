#!/usr/bin/env bash
set -euo pipefail

base=/fsx/analysis_results/ubuntu
echo "=== time ==="
date -Is
echo "=== fsx ==="
df -h /fsx
echo "=== largest validation dirs ==="
du -sh "$base"/ccv20260529* "$base"/ccv20260530* 2>/dev/null | sort -h | tail -n 35
