set -euo pipefail
analysis_dir=/fsx/analysis_results/ubuntu/ccv20260529r26_illumina_bclconvert
case "$analysis_dir" in
  /fsx/analysis_results/ubuntu/ccv20260529*) ;;
  *) echo "unsafe validation analysis dir: $analysis_dir" >&2; exit 2 ;;
esac
if [[ -d "$analysis_dir" ]]; then rm -rf -- "$analysis_dir"; fi
if [[ -e "$analysis_dir" ]]; then echo "cleanup failed: $analysis_dir remains" >&2; exit 1; fi
echo "deleted_or_absent=$analysis_dir"