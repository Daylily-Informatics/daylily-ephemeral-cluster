#!/usr/bin/env bash
set -euo pipefail
echo === tmux ===
tmux list-sessions || true
echo === r49 ps ===
ps -eo pid,ppid,stat,etime,cmd | grep ccv20260530r49 | grep -v grep || true
echo === run state ===
find /home/ubuntu/daylily-runs -maxdepth 2 -path "*ccv20260530r49*" -type f -printf "%TY-%Tm-%TdT%TH:%TM:%TS %p\n" 2>/dev/null | sort | tail -40
echo === repo files ===
find /fsx/analysis_results/ubuntu -maxdepth 2 -path "*ccv20260530r49*" -printf "%TY-%Tm-%TdT%TH:%TM:%TS %p\n" 2>/dev/null | sort | tail -40
