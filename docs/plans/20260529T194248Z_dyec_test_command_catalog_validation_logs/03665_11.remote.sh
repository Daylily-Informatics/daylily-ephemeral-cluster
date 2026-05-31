#!/usr/bin/env bash
set -euo pipefail
cd /fsx/analysis_results/ubuntu/ccv20260530r48_hybrid_ultima_ont_snv/daylily-omics-analysis
sed -n "450,525p" workflow/rules/sent_hybrid_ug_ont_modular.refactored.smk
