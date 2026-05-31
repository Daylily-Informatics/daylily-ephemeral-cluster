#!/usr/bin/env bash
set -euo pipefail
cd /fsx/analysis_results/ubuntu/ccv20260530r48_complete_genomics_mgi_snv_concordance/daylily-omics-analysis
envpath=/fsx/resources/environments/conda/ubuntu/ip-10-0-0-88/2dc9c608977f6d7c6253f8d381138ed4_
echo === rtg wrapper memory vars ===
grep -n "RTG_MEM\|RTG_JAVA_OPTS\|Xmx\|mem" "$envpath/bin/rtg" | head -100 || true
echo === rtg version usage ===
$envpath/bin/rtg vcfeval --help | grep -i -E "memory|Xmx|threads|java" | head -80 || true
echo === config rtg block ===
awk "/^rtg_vcfeval:/{flag=1} flag{print} /^global_contam|^vep|^relatedness|^[A-Za-z0-9_]+:/{if(flag && NR>1 && $0 !~ /^rtg_vcfeval:/ && $0 ~ /^[A-Za-z0-9_]+:/) exit}" config/day_profiles/slurm/rule_config.yaml
