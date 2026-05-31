#!/usr/bin/env bash
set -euo pipefail

echo "time=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "squeue:"
squeue -h -o '%i %P %C %t %N %m %M %j' || true
echo "processes:"
ps -u ubuntu -o pid,ppid,stat,etime,pcpu,pmem,cmd --sort=start_time | tail -80
echo "direct status:"
cat /home/ubuntu/daylily-runs/ccv20260530r42_bclconvert_rc0_direct/status.json || true
echo
echo "latest snakemake log:"
ls -t /fsx/analysis_results/ubuntu/ccv20260530r42_illumina_bclconvert/daylily-omics-analysis/.snakemake/log/*.snakemake.log 2>/dev/null | head -1 | xargs -r tail -n 120
