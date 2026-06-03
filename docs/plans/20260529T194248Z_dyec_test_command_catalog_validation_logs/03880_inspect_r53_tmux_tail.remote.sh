#!/usr/bin/env bash
set -euo pipefail

run=/home/ubuntu/daylily-runs/ccv20260530r53_complete_genomics_mgi_snv_concordance_dryrun

echo "=== status.json ==="
cat "$run/status.json"

echo "=== tmux.log size ==="
wc -c "$run/tmux.log"
wc -l "$run/tmux.log"

echo "=== tmux.log last 220 lines ==="
tail -220 "$run/tmux.log"

echo "=== tmux.log last 4000 bytes ==="
tail -c 4000 "$run/tmux.log"
