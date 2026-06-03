#!/usr/bin/env bash
set -euo pipefail

echo "=== squeue detail ==="
squeue -o '%i|%P|%T|%M|%D|%R|%j'

echo "=== scontrol configuring/running ==="
for jid in $(squeue -h -t CONFIGURING,RUNNING -o '%i'); do
  echo "--- job $jid ---"
  scontrol show job "$jid" | tr ' ' '\n' | grep -E '^(JobId|JobName|JobState|Reason|RunTime|StartTime|BatchHost|NodeList|NumNodes|NumCPUs|Partition|Command|WorkDir)=' || true
done
