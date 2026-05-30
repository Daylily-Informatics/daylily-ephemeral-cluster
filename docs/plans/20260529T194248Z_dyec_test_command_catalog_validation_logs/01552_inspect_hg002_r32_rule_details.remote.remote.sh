#!/usr/bin/env bash
set -euo pipefail

repo="/fsx/analysis_results/ubuntu/ccv20260529r32_illumina_hg002_kitchensink_multiqc/daylily-omics-analysis"
cd "${repo}"

echo "## mosdepth.smk"
nl -ba workflow/rules/mosdepth.smk | sed -n '1,100p'

echo "## contam_identity read_haps/haplocheck rules"
nl -ba workflow/rules/contam_identity.smk | sed -n '300,520p'

echo "## local failing job scripts"
for job in snakejob.goleft.148.sh snakejob.goleft.149.sh snakejob.mosdepth.146.sh snakejob.read_haps_contam_identity.63.sh; do
  path=$(find .snakemake -name "${job}" -type f | head -n 1 || true)
  if [[ -n "${path}" ]]; then
    echo "### ${path}"
    sed -n '1,220p' "${path}" | cut -c1-420
  else
    echo "MISSING ${job}"
  fi
done
