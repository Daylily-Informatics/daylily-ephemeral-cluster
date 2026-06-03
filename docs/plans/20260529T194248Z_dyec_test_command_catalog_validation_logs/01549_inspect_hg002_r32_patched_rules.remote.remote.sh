#!/usr/bin/env bash
set -euo pipefail

repo="/fsx/analysis_results/ubuntu/ccv20260529r32_illumina_hg002_kitchensink_multiqc/daylily-omics-analysis"
cd "${repo}"

echo "## go_left.smk"
nl -ba workflow/rules/go_left.smk | sed -n '1,220p'

echo "## alignstats mosdepth references"
grep -R -n "rule mosdepth\\|mosdepth --\\|global.dist\\|region.dist\\|mosdepth.summary" workflow/rules workflow/Snakefile 2>/dev/null | head -n 80

echo "## contam_identity.smk"
nl -ba workflow/rules/contam_identity.smk | sed -n '1,260p'
