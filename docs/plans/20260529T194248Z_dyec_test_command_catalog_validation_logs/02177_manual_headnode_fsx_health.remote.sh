set -euo pipefail
echo '=== identity ==='
date -u +%Y-%m-%dT%H:%M:%SZ
hostname -f || hostname
id
uptime
echo '=== memory ==='
free -h
echo '=== filesystems ==='
df -hT /fsx /dev/shm /tmp
df -i /fsx /dev/shm /tmp
echo '=== /fsx mount ==='
findmnt /fsx || true
mount | grep ' /fsx ' || true
echo '=== lustre df ==='
if command -v lfs >/dev/null 2>&1; then lfs df -h /fsx; lfs df -i /fsx; else echo 'lfs not installed'; fi
echo '=== validation analysis dirs ==='
find /fsx/analysis_results/ubuntu -maxdepth 1 -type d -name 'ccv20260529*' -printf '%f\n' | sort | wc -l
find /fsx/analysis_results/ubuntu -maxdepth 1 -type d -name 'ccv20260529*' -printf '%TY-%Tm-%TdT%TH:%TM:%TS %f\n' | sort | tail -n 40
echo '=== validation active dirs file-count sample ==='
for d in /fsx/analysis_results/ubuntu/ccv20260529r6_ont_snv_alignstats_kitchensink /fsx/analysis_results/ubuntu/ccv20260529r6_pacbio_snv_alignstats; do [[ -d "$d" ]] && echo "$(find "$d" -xdev -type f | wc -l) files $d"; done
echo '=== daylily run statuses ==='
find /home/ubuntu/daylily-runs -maxdepth 2 -name status.json -path '*/ccv20260529*/*' -print | sort | tail -n 40 | while read -r f; do echo "--- $f"; cat "$f"; done
echo '=== process sample ==='
ps -eo pid,ppid,stat,pcpu,pmem,etime,cmd --sort=-pcpu | head -n 35