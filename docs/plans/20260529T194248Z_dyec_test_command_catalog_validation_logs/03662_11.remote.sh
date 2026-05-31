#!/usr/bin/env bash
set -euo pipefail
cd /fsx/analysis_results/ubuntu/ccv20260530r48_hybrid_ultima_ont_snv/daylily-omics-analysis
grep -R -n "rule sentdhuomr_stage1\|stage1_hap.bam failed integrity\|samtools quickcheck.*stage1_hap" workflow/rules workflow | head -80
