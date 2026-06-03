set -euo pipefail

analysis_dir=/fsx/analysis_results/ubuntu/ccv20260530r42_illumina_bclconvert

printf 'UTC %s\n' "$(date -u +%FT%TZ)"
echo '--- before ---'
df -h /fsx || true
if [[ -d "$analysis_dir" ]]; then
  du -sh "$analysis_dir" || true
else
  echo "already_absent=$analysis_dir"
fi

case "$analysis_dir" in
  /fsx/analysis_results/ubuntu/ccv20260530r42_illumina_bclconvert) ;;
  *) echo "unsafe analysis dir: $analysis_dir" >&2; exit 2 ;;
esac

rm -rf -- "$analysis_dir"

if [[ -e "$analysis_dir" ]]; then
  echo "cleanup failed: $analysis_dir remains" >&2
  exit 1
fi

echo "deleted=$analysis_dir"
echo '--- after ---'
df -h /fsx || true
