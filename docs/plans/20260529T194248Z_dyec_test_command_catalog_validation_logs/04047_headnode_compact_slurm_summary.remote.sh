#!/usr/bin/env bash
set -euo pipefail
echo "=== identity ==="
date -u +"%Y-%m-%dT%H:%M:%SZ"
hostname -f
echo "=== queue counts ==="
squeue -h -o "%T|%P|%j" | awk -F'|' '
  { state[$1]++; part[$2]++; name[$3]++; total++ }
  END {
    print "total_jobs=" (total+0)
    for (s in state) print "state." s "=" state[s]
    for (p in part) print "partition." p "=" part[p]
  }
'
echo "=== job family counts ==="
squeue -h -o "%j" | sed 's/-.*//' | sort | uniq -c | sort -nr | head -n 30
echo "=== oldest jobs ==="
squeue -h -o "%i|%P|%T|%M|%D|%R|%j" | sort -t'|' -k4,4r | head -n 20
echo "=== fsx ==="
df -hT /fsx /dev/shm /
