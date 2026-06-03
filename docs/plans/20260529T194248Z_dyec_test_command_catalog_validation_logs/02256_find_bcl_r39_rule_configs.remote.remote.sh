set -euo pipefail
repo=/fsx/analysis_results/ubuntu/ccv20260529r39_illumina_bclconvert/daylily-omics-analysis
cd "$repo"
echo "=== rule_config files with bclconvert scratch settings ==="
for path in $(find . -name rule_config.yaml -type f | sort); do
  if rg -q 'mounted_dev_shm|bclconvert_scratch|scratch_size_multiplier: "1"|scratch_size_multiplier: 1' "$path"; then
    echo "--- $path"
    rg -n 'staging_mode|scratch_root|tmpdir|scratch_size_multiplier|force' "$path"
  fi
done
echo "=== tmux environment hints ==="
tmux show-environment -t ccv20260529r39_illumina_bclconvert 2>/dev/null | rg 'DAY_PROFILE_DIR|BCLCONVERT|DAY_' || true
