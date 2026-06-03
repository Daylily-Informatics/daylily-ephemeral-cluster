set -euo pipefail

analysis_id=ccv20260529r26_illumina_bclconvert
repo=/fsx/analysis_results/ubuntu/${analysis_id}/daylily-omics-analysis
cd "${repo}"

echo "=== analysis ==="
pwd
echo "=== workflow status files ==="
find . -maxdepth 3 -type f \( -name '*bcl*' -o -name '*BCL*' -o -name '*.log' \) \
  -printf '%TY-%Tm-%TdT%TH:%TM:%TS %s %p\n' 2>/dev/null | sort | tail -n 120 || true

echo "=== slurm bcl logs ==="
for log in logs/slurm/*bcl*/* logs/slurm/*BCL*/*; do
  test -e "${log}" || continue
  echo "--- ${log} ---"
  tail -n 120 "${log}" || true
done

echo "=== result bcl logs ==="
for log in $(find results logs -type f \( -iname '*bcl*.log' -o -iname '*bcl*.err' -o -iname '*bcl*.out' \) 2>/dev/null | sort); do
  echo "--- ${log} ---"
  tail -n 120 "${log}" || true
done

echo "=== scratch summary ==="
find .bclconvert_scratch -maxdepth 3 -type f -printf '%TY-%Tm-%TdT%TH:%TM:%TS %s %p\n' 2>/dev/null | sort | tail -n 80 || true

echo "=== output summary ==="
find results -maxdepth 5 -type f -printf '%TY-%Tm-%TdT%TH:%TM:%TS %s %p\n' 2>/dev/null | sort | tail -n 120 || true
