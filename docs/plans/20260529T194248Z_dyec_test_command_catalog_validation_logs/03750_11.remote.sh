#!/usr/bin/env bash
set -euo pipefail
cd /fsx/analysis_results/ubuntu/ccv20260530r48_complete_genomics_mgi_snv_concordance/daylily-omics-analysis
echo === rtg err ===
sed -n "1,120p" logs/slurm/rtg_vcfeval_roi/rtg_vcfeval_roi.TVBCG5X-HG003-5x-1-D0-PF-CG-MGI.30.err || true
echo === rtg log ===
cat results/day/hg38_broad/TVBCG5X-HG003-5x-1-D0-PF-CG-MGI/align/sentcg/dmd/snv/cgt7p/concordance/logs/TVBCG5X-HG003-5x-1-D0-PF-CG-MGI.sentcg.dmd.cgt7p.giabHC_x_clinvar_genes.rtg_vcfeval.log || true
echo === rule config snippets ===
grep -R -n "rtg_vcfeval\|RTG\|mem_mb\|partition" workflow/rules/rtg_vcfeval.smk config/day_profiles/slurm/rule_config.yaml config/global_AWSPC.yaml | head -120
