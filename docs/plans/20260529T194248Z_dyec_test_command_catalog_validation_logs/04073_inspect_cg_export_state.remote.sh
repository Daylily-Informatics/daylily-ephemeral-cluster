#!/usr/bin/env bash
set -euo pipefail

echo "=== now ==="
date -u +%Y-%m-%dT%H:%M:%SZ

echo "=== relevant processes ==="
ps -eo pid,ppid,stat,etime,cmd | grep -E 'ccv20260530r54|dyec export|fsx_export|data-repository|snakemake|day_run' | grep -v grep || true

echo "=== tmux sessions ==="
tmux list-sessions 2>/dev/null || true

echo "=== analysis export dir ==="
find /home/ubuntu/daylily-runs/ccv20260530r54_complete_genomics_mgi_snv_concordance -maxdepth 4 -type f -printf '%TY-%Tm-%TdT%TH:%TM:%TSZ %s %p\n' 2>/dev/null | sort | tail -50 || true

echo "=== fsx export yaml ==="
find /home/ubuntu/daylily-runs/ccv20260530r54_complete_genomics_mgi_snv_concordance -name 'fsx_export.yaml' -print -exec sed -n '1,220p' {} \; 2>/dev/null || true

echo "=== dyec status jsons ==="
find /home/ubuntu/daylily-runs/ccv20260530r54_complete_genomics_mgi_snv_concordance -maxdepth 4 \( -name 'status.json' -o -name '*status*.json' \) -print -exec sed -n '1,160p' {} \; 2>/dev/null || true
