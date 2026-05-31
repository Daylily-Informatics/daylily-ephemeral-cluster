#!/usr/bin/env bash
set -euo pipefail

echo "== runtime commands =="
command -v bcl-convert || true
command -v singularity || true
command -v apptainer || true

echo "== cached bclconvert images =="
find /fsx /home/ubuntu -maxdepth 5 \( -iname '*bclconvert*' -o -iname '*bcl-convert*' \) -print 2>/dev/null | head -n 100 || true

if command -v bcl-convert >/dev/null 2>&1; then
  echo "== bcl-convert --help from PATH =="
  bcl-convert --help || true
  exit 0
fi

runtime=""
if command -v singularity >/dev/null 2>&1; then
  runtime=singularity
elif command -v apptainer >/dev/null 2>&1; then
  runtime=apptainer
else
  echo "ERROR_no_singularity_or_apptainer"
  exit 10
fi

echo "== bcl-convert --help from docker://nfcore/bclconvert:4.0.3 =="
$runtime exec docker://nfcore/bclconvert:4.0.3 bcl-convert --help
