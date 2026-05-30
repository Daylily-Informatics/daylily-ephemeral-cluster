set -euo pipefail

mount_dir="/fsx/run_dir_mounts/20260513_ONT_HG003"
echo "=== mount dir ==="
ls -ld "${mount_dir}" || true
echo "=== top level ==="
find "${mount_dir}" -maxdepth 3 -mindepth 1 -printf '%y %p\n' 2>&1 | head -n 120 || true
echo "=== fastq count sample ==="
find "${mount_dir}" -type f -name '*.fastq.gz' -printf '%s %p\n' 2>&1 | head -n 40 || true
echo "=== sample reads ==="
first_fastq="$(find "${mount_dir}" -type f -name '*.fastq.gz' -print -quit 2>/dev/null || true)"
if [[ -n "${first_fastq}" ]]; then
  echo "first_fastq=${first_fastq}"
  gzip -cd "${first_fastq}" | head -n 8
else
  echo "no fastq file visible"
fi
