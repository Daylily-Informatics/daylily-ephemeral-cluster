#!/usr/bin/env bash
set -euo pipefail

repo=/fsx/analysis_results/ubuntu/ccv20260530r42_illumina_bclconvert/daylily-omics-analysis
root="$repo/results/runs/20260514_LH01106_0009_B23TVLGLT4/bclconvert"
echo "=== time ==="
date -Is
echo "=== fsx ==="
df -h /fsx
echo "=== lane output sizes ==="
for lane in L001 L002 L003 L004 L005 L006 L007 L008; do
  lane_dir="$root/lane_fastqs/$lane"
  size=$(du -sh "$lane_dir" 2>/dev/null | awk '{print $1}' || true)
  files=$(find "$lane_dir" -type f 2>/dev/null | wc -l | tr -d " ")
  done_file="$root/lane_reports/$lane/bclconvert.done"
  if [[ -e "$done_file" ]]; then state=done; else state=running; fi
  echo "$lane size=${size:-missing} files=$files state=$state"
done
echo "=== recent log tails ==="
for lane in L001 L006; do
  log="$root/logs/run_bclconvert.$lane.log"
  echo "--- $lane ---"
  if [[ -f "$log" ]]; then tail -n 30 "$log"; else echo missing; fi
done
