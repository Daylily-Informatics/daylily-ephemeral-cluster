#!/usr/bin/env bash
set -euo pipefail

repo=/fsx/analysis_results/ubuntu/ccv20260530r49_hybrid_ultima_ont_snv/daylily-omics-analysis
rule="$repo/workflow/rules/sent_hybrid_ug_ont_modular.refactored.smk"

echo "=== stage2 rule ==="
sed -n '534,592p' "$rule"

echo "=== stage3 rule ==="
sed -n '595,675p' "$rule"

echo "=== subset/final vicinity ==="
sed -n '676,850p' "$rule"
