#!/usr/bin/env bash
set -euo pipefail

session=ccv20260530r53_complete_genomics_mgi_snv_concordance_dryrun

echo "=== run dirs ==="
find /home/ubuntu -maxdepth 4 -type d -name "$session" -print 2>/dev/null || true
find /tmp -maxdepth 4 -type d -name "$session" -print 2>/dev/null || true

echo "=== files named for session ==="
find /home/ubuntu /tmp -maxdepth 6 -type f -name "*${session}*" -printf '%TY-%Tm-%TdT%TH:%TM:%TS %s %p\n' 2>/dev/null | sort | tail -100 || true

for dir in /home/ubuntu/daylily-runs/"$session" /home/ubuntu/.daylily/runs/"$session" /tmp/daylily-runs/"$session"; do
  if [ -d "$dir" ]; then
    echo "=== $dir files ==="
    find "$dir" -maxdepth 3 -type f -printf '%TY-%Tm-%TdT%TH:%TM:%TS %s %p\n' | sort
    for f in "$dir"/*; do
      [ -f "$f" ] || continue
      echo "--- $f ---"
      tail -200 "$f" || true
    done
  fi
done
