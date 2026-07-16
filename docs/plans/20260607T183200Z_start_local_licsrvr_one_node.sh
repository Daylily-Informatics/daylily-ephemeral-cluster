#!/usr/bin/env bash
set -euo pipefail

sentieon_root="/fsx/references/runtime_assets/cached_envs/sentieon-genomics-202503.02"
license="/fsx/references/runtime_assets/cached_envs/Life_Sciences_Manufacturing_Corporation_eval.lic"
log="/tmp/sentieon_licsrvr_8990.log"

echo "HOST $(hostname)"
echo "DATE $(date -u +%Y-%m-%dT%H:%M:%SZ)"

echo "BEFORE_LISTENER"
sudo ss -lntp | grep -E '(:8990|Local Address)' || true

echo "START_LICSRVR"
SENTIEON_LICENSE="$license" "${sentieon_root}/libexec/licsrvr" --start -l "$log" "$license" 2>&1 || true

sleep 5

echo "AFTER_LISTENER"
sudo ss -lntp | grep -E '(:8990|Local Address)' || true

echo "LICSRVR_PROCESS"
ps -ef | grep -Ei 'licsrvr|8990' | grep -v grep || true

echo "LICSRVR_LOG"
tail -n 80 "$log" 2>&1 || true

echo "LICCLNT_PING"
SENTIEON_LICENSE="$license" timeout 60 "${sentieon_root}/libexec/licclnt" ping --server localhost:8990 2>&1 || true

echo "LICCLNT_QUERY_KLIB"
SENTIEON_LICENSE="$license" timeout 60 "${sentieon_root}/libexec/licclnt" query --server localhost:8990 klib 2>&1 || true

echo "END $(date -u +%Y-%m-%dT%H:%M:%SZ)"
