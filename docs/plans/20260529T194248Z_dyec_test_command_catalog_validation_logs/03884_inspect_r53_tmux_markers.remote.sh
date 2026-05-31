#!/usr/bin/env bash
set -euo pipefail

log=/home/ubuntu/daylily-runs/ccv20260530r53_complete_genomics_mgi_snv_concordance_dryrun/tmux.log

echo "=== markers ==="
grep -nE 'Building DAG|Job stats|This was a dry-run|Rules claiming more threads|Failed|failed|Error|ERROR|WorkflowError|RuleException|Traceback|Missing|Unlocking|Complete log|removed temporary output|Would remove|Exiting because' "$log" | tail -200 || true

echo "=== last line count and selected tail line numbers ==="
wc -l "$log"
for n in 680 700 710 720 721 722 723 724 725 726; do
  sed -n "${n}p" "$log" | cut -c1-220
done
