set -euo pipefail
repo=/fsx/analysis_results/ubuntu/ccv20260529r21_ont_run_qc/daylily-omics-analysis
cd "$repo"
echo "=== pycoqc log ==="
sed -n '1,120p' results/runs/20260513_ONT_HG003/run_qc/ont/logs/pycoqc.log || true
echo "=== patched source ==="
plot=/fsx/resources/environments/conda/ubuntu/ip-10-0-0-88/a99ea18d415639f67a6e85afdbe2fe1b_/lib/python3.13/site-packages/pycoQC/pycoQC_plot.py
sed -n '1460,1475p' "$plot" || true
