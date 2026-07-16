#!/usr/bin/env bash
set -euo pipefail

echo "HOST $(hostname)"
echo "DATE $(date -u +%Y-%m-%dT%H:%M:%SZ)"

echo "PROCESSES"
pgrep -af 'sentieon.*driver' | head -20 || true

pid="$(pgrep -f 'sentieon.*driver' | head -1 || true)"
if [[ -z "$pid" ]]; then
  echo "NO_SENTIEON_DRIVER_PID"
  exit 0
fi

echo "PID $pid"
sentieon_exe="$(readlink -f "/proc/${pid}/exe" || true)"
echo "EXE ${sentieon_exe}"
echo "CWD $(readlink -f "/proc/${pid}/cwd" || true)"

env_file="/tmp/sentieon_env_${pid}.txt"
tr '\0' '\n' <"/proc/${pid}/environ" >"$env_file"

echo "ENV_RELEVANT"
grep -E '^(SENTIEON|LM_|PATH=|LD_LIBRARY_PATH=)' "$env_file" || true

license="$(awk -F= '$1 == "SENTIEON_LICENSE" {print $2; exit}' "$env_file")"
if [[ -z "$license" ]]; then
  echo "NO_SENTIEON_LICENSE_IN_PROCESS_ENV"
  exit 0
fi

echo "LICENSE ${license}"
host="${license%:*}"
port="${license##*:}"
if [[ "$host" == "$license" || "$port" == "$license" ]]; then
  echo "UNPARSEABLE_HOST_PORT license=${license}"
  exit 0
fi

echo "HOST_PORT host=${host} port=${port}"
echo "DNS"
getent hosts "$host" || true

echo "TCP_TEST"
if timeout 10 bash -c "cat < /dev/null > /dev/tcp/${host}/${port}"; then
  echo "TCP_OK"
else
  echo "TCP_FAIL rc=$?"
fi

if [[ -x "$sentieon_exe" ]]; then
  echo "SENTIEON_HELP"
  timeout 20 "$sentieon_exe" licclnt --help 2>&1 | head -80 || true

  echo "LICCLNT_PING"
  timeout 30 "$sentieon_exe" licclnt ping --server "$license" 2>&1 || true

  echo "LICCLNT_QUERY_KLIB"
  timeout 30 "$sentieon_exe" licclnt query --server "$license" klib 2>&1 || true
else
  echo "SENTIEON_EXE_NOT_EXECUTABLE ${sentieon_exe}"
fi
