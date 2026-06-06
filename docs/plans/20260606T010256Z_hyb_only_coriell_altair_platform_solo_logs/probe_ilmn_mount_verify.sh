#!/usr/bin/env bash
set -euo pipefail
root=/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq
echo "time_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "root=$root"
test -d "$root"
find "$root" -maxdepth 1 -type f -name '*.fastq.gz' | sort | wc -l
find "$root" -maxdepth 1 -type f -name '*.fastq.gz' | sort | sed -n '1,10p'
df -h /fsx
