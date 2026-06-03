#!/usr/bin/env bash
set -euo pipefail

echo "=== utc ==="
date -u +"%Y-%m-%dT%H:%M:%SZ"
echo "=== r49 processes ==="
ps -eo pid,ppid,stat,etime,cmd | grep 'ccv20260530r49' | grep -v grep || true
echo "=== r49 run dirs ==="
for d in /home/ubuntu/daylily-runs/ccv20260530r49_*; do
  [[ -e "$d" ]] || continue
  echo "--- $d"
  find "$d" -maxdepth 1 -type f -printf '%s %TY-%Tm-%TdT%TH:%TM:%TS %p\n' | sort || true
  for f in status.json tmux-bootstrap.log tmux.log launch.sh; do
    [[ -f "$d/$f" ]] || continue
    echo "--- $d/$f"
    tail -n 80 "$d/$f" || true
  done
done
echo "=== r49 repos ==="
find /fsx/analysis_results/ubuntu -maxdepth 2 -path '*ccv20260530r49*' -printf '%TY-%Tm-%TdT%TH:%TM:%TS %p\n' 2>/dev/null | sort || true
echo "=== queue ==="
squeue -h -o "%i|%P|%T|%M|%R|%j" | sort || true
echo "=== fsx ==="
df -hT /fsx /
