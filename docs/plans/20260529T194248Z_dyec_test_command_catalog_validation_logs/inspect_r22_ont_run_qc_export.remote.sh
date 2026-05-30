set -euo pipefail
aid=ccv20260529r22_ont_run_qc
run_dir="/home/ubuntu/daylily-runs/${aid}"
repo="/fsx/analysis_results/ubuntu/${aid}/daylily-omics-analysis"
export_prefix="s3://lsmc-ssf-sequencing-data/derived/validation/dyec-test/ubuntu/${aid}/"

echo "status_json:"
cat "${run_dir}/status.json" || true
echo

echo "tmux_tail:"
tail -n 240 "${run_dir}/tmux.log" || true
echo

echo "tmux_export_lines:"
grep -nE 'RETURN CODE|export|Export|fsx_export|DataRepository|analysis_results|aws s3|dyec' "${run_dir}/tmux.log" || true
echo

echo "repo_status_files:"
find "${repo}" -maxdepth 4 \( -name 'status.json' -o -name 'fsx_export.yaml' -o -name '*.receipt*' -o -name '*export*' \) -print -exec ls -l {} \; 2>/dev/null | head -n 240 || true
echo

echo "analysis_root:"
ls -lah "/fsx/analysis_results/ubuntu/${aid}" || true
echo

echo "export_s3_prefix:"
aws s3 ls "${export_prefix}" --recursive --summarize | tail -n 80 || true
