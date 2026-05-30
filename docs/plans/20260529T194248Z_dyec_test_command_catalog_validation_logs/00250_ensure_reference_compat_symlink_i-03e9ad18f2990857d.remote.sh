set -euo pipefail
echo USER=$(id -un)
hostname -f || hostname
if [[ -e /fsx/data && ! -L /fsx/data ]]; then
  if [[ "$(readlink -f /fsx/data)" != /fsx/references ]]; then
    echo 'ERROR: /fsx/data exists but does not resolve to /fsx/references' >&2
    exit 1
  fi
else
  sudo ln -sfn /fsx/references /fsx/data
fi
test -L /fsx/data
test "$(readlink -f /fsx/data)" = /fsx/references
ls -ld /fsx/data