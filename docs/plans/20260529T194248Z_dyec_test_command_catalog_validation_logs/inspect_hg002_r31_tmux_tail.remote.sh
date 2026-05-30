#!/usr/bin/env bash
set -euo pipefail

session=ccv20260529r31_illumina_hg002_kitchensink_multiqc_dryrun
run_dir="/home/ubuntu/daylily-runs/${session}"

echo "## ${run_dir}/tmux.log tail"
tail -n 90 "${run_dir}/tmux.log" | cut -c1-500

echo "## launch exit/status handling"
grep -nE 'exit_code|status|set \\+e|set -e|day_run|snakemake|unlock|trap|completed_at' "${run_dir}/launch.sh" | tail -n 120
