set -euo pipefail

analysis_id=ccv20260529r34_illumina_hg002_kitchensink_multiqc
repo=/fsx/analysis_results/ubuntu/${analysis_id}/daylily-omics-analysis
cd "${repo}"

echo "=== snakemake error windows ==="
sed -n '350,430p' .snakemake/log/2026-05-30T083659.176153.snakemake.log || true
sed -n '455,510p' .snakemake/log/2026-05-30T083659.176153.snakemake.log || true

echo "=== fastqc and seqfu files ==="
find results logs .snakemake -type f \( -iname '*fastqc*' -o -iname '*seqfu*' \) \
  -printf '%TY-%Tm-%TdT%TH:%TM:%TS %s %p\n' 2>/dev/null | sort | tail -n 120 || true

echo "=== fastqc and seqfu log tails ==="
while IFS= read -r path; do
  echo "--- ${path} ---"
  tail -n 80 "${path}" || true
done < <(
  find results logs .snakemake -type f \( -iname '*fastqc*.log' -o -iname '*seqfu*.log' -o -iname '*fastqc*.err' -o -iname '*seqfu*.err' -o -path '*/snakejob.fastqc_subsampled.44.sh' -o -path '*/snakejob.seqfu.*.sh' \) 2>/dev/null | sort
)

echo "=== done ==="
