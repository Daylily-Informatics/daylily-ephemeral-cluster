#!/usr/bin/env bash
set -euo pipefail

repo=/fsx/analysis_results/ubuntu/ccv20260529r17_ont_run_qc/daylily-omics-analysis
cd "$repo"

echo "=== repo ==="
pwd
echo "=== run context ==="
sed -n '1,20p' config/runs.tsv || true
echo "=== summary list ==="
wc -l results/runs/20260513_ONT_HG003/run_qc/ont/tables/sequencing_summary_files.txt || true
sed -n '1,20p' results/runs/20260513_ONT_HG003/run_qc/ont/tables/sequencing_summary_files.txt || true
echo "=== pycoqc log ==="
sed -n '1,180p' results/runs/20260513_ONT_HG003/run_qc/ont/logs/pycoqc.log || true
echo "=== nanoplot log tail ==="
tail -n 80 results/runs/20260513_ONT_HG003/run_qc/ont/logs/nanoplot.log || true
echo "=== conda env package versions ==="
env_path=$(find /fsx/resources/environments/conda/ubuntu -maxdepth 2 -type d -name 'a99ea18d415639f67a6e85afdbe2fe1b_' | head -n 1)
if [ -n "$env_path" ]; then
  "$env_path/bin/python" - <<'PY'
import importlib.metadata as md
for name in ["pycoQC", "numpy", "pandas", "bokeh"]:
    try:
        print(f"{name}={md.version(name)}")
    except Exception as exc:
        print(f"{name}=<missing> {exc}")
PY
  "$env_path/bin/pycoQC" --version || true
fi
