#!/usr/bin/env bash
set -euo pipefail

sentieon_root="/fsx/references/runtime_assets/cached_envs/sentieon-genomics-202503.02"
license="/fsx/references/runtime_assets/cached_envs/Life_Sciences_Manufacturing_Corporation_eval.lic"

echo "HOST $(hostname)"
echo "DATE $(date -u +%Y-%m-%dT%H:%M:%SZ)"

echo "LICSRVR_HELP"
"${sentieon_root}/libexec/licsrvr" --help 2>&1 | head -120 || true

echo "LICSRVR_VERSION_OR_USAGE"
"${sentieon_root}/libexec/licsrvr" 2>&1 | head -80 || true

echo "LICCLNT_PING_EXPLICIT_LOCALHOST"
"${sentieon_root}/libexec/licclnt" ping --server localhost:8990 2>&1 || true

echo "LICENSE_SERVER_HINTS"
grep -Eo '([A-Za-z0-9._-]+:[0-9]{2,5}|[0-9]{1,3}([.][0-9]{1,3}){3}:[0-9]{2,5}|port=[0-9]{2,5})' "$license" | sort -u || true

echo "LISTENERS_8990"
sudo ss -lntp | grep -E '(:8990|Local Address)' || true
