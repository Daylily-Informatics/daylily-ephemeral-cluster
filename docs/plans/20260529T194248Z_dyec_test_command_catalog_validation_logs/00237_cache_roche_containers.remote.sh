set -euo pipefail
host_name=$(hostname)
cache_dir=/fsx/resources/environments/containers/ubuntu/${host_name}
install -d -m 1777 "$cache_dir"
command -v singularity
declare -A images
images[7a424a40c6fd659f4d052893dd3554fa]='docker://roche/sbxd-small-variant-caller:latest'
images[49599841644a581df7ed78059707ff95]='docker://broadinstitute/gatk-nightly:2025-08-19-4.6.2.0-17-g2a1f41bf3-NIGHTLY-SNAPSHOT'
for hash in "${!images[@]}"; do
  uri=${images[$hash]}
  image_path=${cache_dir}/${hash}.simg
  echo "=== $hash $uri ==="
  if [[ ! -s "$image_path" ]]; then
    tmp=${image_path}.tmp.$$
    rm -f "$tmp"
    singularity pull --disable-cache "$tmp" "$uri"
    mv "$tmp" "$image_path"
  fi
  test -s "$image_path"
  ls -lh "$image_path"
  sha256sum "$image_path"
done