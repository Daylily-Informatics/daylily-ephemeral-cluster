#!/usr/bin/env bash
set -euo pipefail
printf 'FIND_SLIM_CONTROL\n'
find /fsx/references /fsx/control_data -maxdepth 6 \( -iname '*slim*' -o -iname '*control*' \) -print 2>/dev/null | head -400
printf 'FIND_READS_SLIM_SAMPLE\n'
find /fsx/references/genomic_data/organism_reads_slim -maxdepth 5 -type d 2>/dev/null | head -200
printf 'REF_GENOMIC_TOP\n'
find /fsx/references/genomic_data -maxdepth 3 -type d 2>/dev/null | sed -n '1,200p'
