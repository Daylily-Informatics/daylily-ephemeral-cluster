set -euo pipefail
SESSION=hg003a_ont_snv_alignstats_1018_191_preservetmp_v2
RUN=/home/ubuntu/daylily-runs/${SESSION}
ROOT=/fsx/analysis_results/johnm/${SESSION}
REPO=${ROOT}/daylily-omics-analysis
NODE=i192mem-dy-all-1
JOB=185
echo "monitor_start=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
for i in $(seq 1 80); do
  now=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  state=$(squeue -h -j "${JOB}" -o '%T' 2>/dev/null || true)
  elapsed=$(squeue -h -j "${JOB}" -o '%M' 2>/dev/null || true)
  status=$(python3 -c "import json; d=json.load(open('${RUN}/status.json')); print(d.get('exit_code'), d.get('completed_at'))" 2>/dev/null || true)
  shm=$(ssh -o BatchMode=yes -o ConnectTimeout=5 "${NODE}" "bash -l -c 'df -h /dev/shm | tail -1; find /dev/shm -maxdepth 2 -type d -name \"sentdont_tmp_*\" -printf \"%p \" 2>/dev/null || true'" 2>/dev/null || true)
  echo "tick=${i} utc=${now} state=${state:-NONE} elapsed=${elapsed:-NA} status=${status:-NA} shm=${shm}"
  if [ -z "${state}" ]; then
    break
  fi
  sleep 10
done
echo "monitor_end=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "== final status =="
cat "${RUN}/status.json" 2>/dev/null || true
echo
echo "== squeue final =="
squeue -o '%.18i %.9P %.55j %.12u %.12T %.10M %.6D %.25R %.8C %.12m' || true
echo "== scontrol 185 final =="
scontrol show job "${JOB}" 2>&1 || true
echo "== sacct sent_snv final =="
sacct -X -S 2026-05-23T09:00:00 -o JobID,JobName%80,State,ExitCode,NodeList%30,AllocCPUS,ReqMem,Elapsed,Start,End -P 2>/dev/null | grep -E 'sent_snv_ont|JobID' || true
echo "== sentdont log tail =="
find "${REPO}/results" -path '*snv/sentdont/log/*sentdont.snv.log' -type f -print 2>/dev/null | sort | while read -r f; do echo "-- $f"; tail -n 140 "$f"; done
echo "== capture tree =="
find "${ROOT}/ont_tmp_capture" -maxdepth 4 -printf '%M\t%s\t%p\n' 2>/dev/null | sort || true
echo "== capture summaries =="
find "${ROOT}/ont_tmp_capture" -name summary.txt -type f -print 2>/dev/null | sort | while read -r f; do echo "-- $f"; sed -n '1,220p' "$f"; done
echo "== live node final shm =="
ssh -o BatchMode=yes -o ConnectTimeout=10 "${NODE}" "bash -l -c 'hostname; date -u +%Y-%m-%dT%H:%M:%SZ; df -h /dev/shm || true; df -i /dev/shm || true; find /dev/shm -maxdepth 5 -name \"sentdont_tmp_*\" -printf \"%M\\t%s\\t%p\\n\" 2>/dev/null | sort || true; ps -eo pid,ppid,stat,pcpu,pmem,rss,vsz,cmd | grep -E \"sentieon|DNAscope|dnascope\" | grep -v grep || true'" || true
