set -euo pipefail

analysis_id=ccv20260529r34_illumina_hg002_kitchensink_multiqc
repo=/fsx/analysis_results/ubuntu/${analysis_id}/daylily-omics-analysis
sample=JEMILMN0P1-HG002-0p1x-1-D0-PF-ILMN-NOVASEQ
snv_dir=results/day/hg38/${sample}/align/sent/dmd/snv/sentd
concordance_dir=${snv_dir}/concordance

cd "${repo}"

echo "=== analysis ==="
pwd
echo "=== top-level result files ==="
find results/day/hg38/other_reports -maxdepth 1 -type f -printf '%TY-%Tm-%TdT%TH:%TM:%TS %s %p\n' 2>/dev/null | sort || true

echo "=== snakemake logs tail ==="
for log in .snakemake/log/*.snakemake.log; do
  test -e "${log}" || continue
  echo "--- ${log} ---"
  tail -n 160 "${log}"
done

echo "=== recent error lines ==="
grep -RInE 'Error|Traceback|Exception|MissingOutput|MissingInput|RuleException|WorkflowError|No such file|command not found|failed|non-zero|KeyError|ValueError|AssertionError|returned non-zero' \
  .snakemake/log "${concordance_dir}" results/day/hg38/other_reports logs 2>/dev/null | tail -n 240 || true

echo "=== concordance outputs ==="
find "${concordance_dir}" -maxdepth 3 -type f -printf '%TY-%Tm-%TdT%TH:%TM:%TS %s %p\n' | sort | tail -n 120 || true

echo "=== concordance aggregate target ==="
ls -l results/day/hg38/other_reports/giab_concordance_mqc.tsv 2>/dev/null || true

echo "=== concordance log tails ==="
for log in "${concordance_dir}"/logs/*.log "${concordance_dir}"/*/logs/*.log; do
  test -e "${log}" || continue
  echo "--- ${log} ---"
  tail -n 80 "${log}"
done

echo "=== first lines of ROI MQC files ==="
for mqc in "${concordance_dir}"/*/*.mqc.tsv; do
  test -e "${mqc}" || continue
  echo "--- ${mqc} ---"
  sed -n '1,8p' "${mqc}"
done
