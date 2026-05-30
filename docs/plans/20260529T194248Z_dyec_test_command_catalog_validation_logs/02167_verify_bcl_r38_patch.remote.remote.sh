set -euo pipefail
repo=/fsx/analysis_results/ubuntu/ccv20260529r38_illumina_bclconvert/daylily-omics-analysis
cd "$repo"
rg -n 'Moving BCLConvert outputs|Removing staged BCL input scratch|cp -a "\$effective_output_dir"|scratch_run_dir' workflow/rules/bclconvert.smk
