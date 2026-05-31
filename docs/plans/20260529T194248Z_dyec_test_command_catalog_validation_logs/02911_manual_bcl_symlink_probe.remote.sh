#!/usr/bin/env bash
set -euo pipefail

analysis=/fsx/analysis_results/ubuntu/ccv20260530r41_illumina_bclconvert/daylily-omics-analysis
run_id=20260514_LH01106_0009_B23TVLGLT4
projected="$analysis/config/run_dir_links/$run_id"
mounted="/fsx/run_dir_mounts/$run_id"

echo "=== headnode projection ==="
hostname
ls -ld "$analysis/config" "$analysis/config/run_dir_links" "$projected" "$mounted" || true
readlink "$projected" || true
test -d "$projected" && echo "projected_dir=yes" || echo "projected_dir=no"
test -d "$mounted" && echo "mounted_dir=yes" || echo "mounted_dir=no"
find -L "$projected" -maxdepth 1 -mindepth 1 | head -n 12 || true

echo "=== compute projection ==="
node="${1:-i192mem-dy-all-1}"
ssh -o BatchMode=yes -o StrictHostKeyChecking=no "$node" "set -euo pipefail; hostname; ls -ld '$analysis/config' '$analysis/config/run_dir_links' '$projected' '$mounted' || true; readlink '$projected' || true; test -d '$projected' && echo projected_dir=yes || echo projected_dir=no; test -d '$mounted' && echo mounted_dir=yes || echo mounted_dir=no; find -L '$projected' -maxdepth 1 -mindepth 1 | head -n 12 || true"
