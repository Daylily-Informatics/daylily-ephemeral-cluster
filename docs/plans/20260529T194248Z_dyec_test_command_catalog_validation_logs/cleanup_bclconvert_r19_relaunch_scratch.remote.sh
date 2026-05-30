set -euo pipefail
target=/fsx/scratch/dayoa_bclconvert/2653.26739
echo "cleanup_target=$target"
if [[ -d "$target" ]]; then
  du -sh "$target" || true
  rm -rf -- "$target"
fi
if [[ -e "$target" ]]; then
  echo "cleanup_failed=$target"
  exit 1
fi
echo "cleanup_absent=$target"
du -sh /fsx/scratch/dayoa_bclconvert 2>/dev/null || true
