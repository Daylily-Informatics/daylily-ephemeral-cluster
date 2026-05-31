#!/usr/bin/env bash
set -euo pipefail

analysis_root="/fsx/analysis_results/ubuntu/ccv20260530r42_illumina_bclconvert/daylily-omics-analysis"
links_dir="$analysis_root/config/run_dir_links"

echo "time=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "analysis_root=$analysis_root"
echo "links_dir=$links_dir"

if [[ ! -d "$analysis_root" ]]; then
  echo "ERROR: analysis root is missing: $analysis_root" >&2
  exit 2
fi

if [[ ! -e "$links_dir" ]]; then
  echo "no run_dir_links path exists"
  exit 0
fi

if [[ ! -d "$links_dir" ]]; then
  echo "ERROR: run_dir_links exists but is not a directory: $links_dir" >&2
  ls -ld "$links_dir" >&2
  exit 3
fi

echo "before:"
find "$links_dir" -maxdepth 1 -mindepth 1 -printf '%y %p -> %l\n' | sort || true

while IFS= read -r link_path; do
  target="$(readlink "$link_path")"
  echo "removing_symlink=$link_path target=$target"
  rm -- "$link_path"
done < <(find "$links_dir" -maxdepth 1 -mindepth 1 -type l -print | sort)

if find "$links_dir" -maxdepth 1 -mindepth 1 -print -quit | grep -q .; then
  echo "after:"
  find "$links_dir" -maxdepth 1 -mindepth 1 -printf '%y %p -> %l\n' | sort || true
else
  rmdir "$links_dir"
  echo "removed_empty_links_dir=$links_dir"
fi

echo "remaining symlink projections under analysis config:"
find "$analysis_root/config" -maxdepth 3 -type l -printf '%p -> %l\n' | sort || true
