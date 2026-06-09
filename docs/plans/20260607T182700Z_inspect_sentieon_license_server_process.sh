#!/usr/bin/env bash
set -euo pipefail

echo "HOST $(hostname)"
echo "DATE $(date -u +%Y-%m-%dT%H:%M:%SZ)"

echo "LISTENERS_8990"
sudo ss -lntp | grep -E '(:8990|Local Address)' || true

echo "PROCESSES_LICENSE"
ps -ef | grep -Ei 'sentieon|licsrvr|licsrv|license' | grep -Ev 'grep|HybridStage|sentdhiomr|libexec/driver|dayoa_sentieon' || true

echo "SYSTEMD_CANDIDATES"
systemctl list-units --type=service --all | grep -Ei 'sentieon|licsrvr|license' || true

echo "FILES_CANDIDATES"
find /fsx/references/runtime_assets/cached_envs/sentieon-genomics-202503.02 -maxdepth 3 -type f -perm -111 \
  | grep -Ei '/(licsrvr|licsrv|licclnt|sentieon)$' || true

echo "LIBEXEC"
ls -l /fsx/references/runtime_assets/cached_envs/sentieon-genomics-202503.02/libexec | grep -Ei 'lic|server|daemon|sentieon' || true

echo "TCP_LOCALHOST_8990"
if timeout 5 bash -c 'cat < /dev/null > /dev/tcp/127.0.0.1/8990'; then
  echo "TCP_127_OK"
else
  echo "TCP_127_FAIL rc=$?"
fi
if timeout 5 bash -c 'cat < /dev/null > /dev/tcp/localhost/8990'; then
  echo "TCP_LOCALHOST_OK"
else
  echo "TCP_LOCALHOST_FAIL rc=$?"
fi
