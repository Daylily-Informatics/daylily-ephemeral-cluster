set -euo pipefail
if [[ "$(id -un)" != "ubuntu" ]]; then
  echo "wrong_user=$(id -un)"
  exit 5
fi
repo=/fsx/analysis_results/ubuntu/ccv20260529r11_illumina_bclconvert/daylily-omics-analysis
run=/fsx/run_dir_mounts/20260514_LH01106_0009_B23TVLGLT4
echo "repo=$repo"
echo "run=$run"
echo "=== repo config ==="
for path in \
  "$repo/config/runs.tsv" \
  "$repo/config/samples.tsv" \
  "$repo/config/units.tsv" \
  "$repo/.test_data/data/bclconvert/samples.tsv" \
  "$repo/.test_data/data/bclconvert/units.tsv" \
  "$repo/.test_data/data/samples.tsv" \
  "$repo/.test_data/data/units.tsv"
do
  echo "--- $path"
  if [[ -f "$path" ]]; then
    wc -l "$path"
    sed -n '1,12p' "$path"
  else
    echo "missing"
  fi
done
echo "=== run sample sheet candidates ==="
find "$run" -maxdepth 3 -iname '*sample*sheet*.csv' -o -iname 'SampleSheet.csv' | sort
sample_sheet=$(find "$run" -maxdepth 3 -iname '*sample*sheet*.csv' -o -iname 'SampleSheet.csv' | sort | head -n 1)
if [[ -n "$sample_sheet" ]]; then
  echo "--- $sample_sheet"
  sed -n '1,120p' "$sample_sheet"
fi
echo "=== bclconvert input log ==="
log="$repo/results/runs/20260514_LH01106_0009_B23TVLGLT4/bclconvert/logs/bclconvert_validate_inputs.log"
if [[ -f "$log" ]]; then
  sed -n '1,120p' "$log"
fi
