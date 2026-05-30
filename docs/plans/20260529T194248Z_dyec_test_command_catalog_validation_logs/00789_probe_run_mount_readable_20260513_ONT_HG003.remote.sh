set -euo pipefail
mount_dir=/fsx/run_dir_mounts/20260513_ONT_HG003
test -d "$mount_dir"
first_file=$(find "$mount_dir" -mindepth 1 -maxdepth 6 -type f -print -quit)
test -n "$first_file"
test -r "$first_file"
head -c 1 "$first_file" >/dev/null
echo "readable_projection=$first_file"