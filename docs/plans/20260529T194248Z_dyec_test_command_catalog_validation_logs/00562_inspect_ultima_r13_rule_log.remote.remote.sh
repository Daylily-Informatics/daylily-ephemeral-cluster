set -euo pipefail
repo=/fsx/analysis_results/ubuntu/ccv20260529r13_ultima_run_qc/daylily-omics-analysis
cd "$repo"
echo "=== ultima rule log ==="
cat results/runs/602221-20260417_2346/run_qc/ultima/logs/ultima_run_qc_report.log
echo "=== metrics path stat ==="
stat /fsx/run_dir_mounts/602221-20260417_2346/602221-S10_B-Z0310-CATGACAGTAATGAT/602221-S10_B-Z0310-CATGACAGTAATGAT.csv || true
echo "=== metrics path head ==="
head -20 /fsx/run_dir_mounts/602221-20260417_2346/602221-S10_B-Z0310-CATGACAGTAATGAT/602221-S10_B-Z0310-CATGACAGTAATGAT.csv || true
