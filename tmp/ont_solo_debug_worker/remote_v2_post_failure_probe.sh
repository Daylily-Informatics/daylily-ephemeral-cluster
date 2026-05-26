set -euo pipefail
SESSION=hg003a_ont_snv_alignstats_1018_191_preservetmp_v2
RUN=/home/ubuntu/daylily-runs/${SESSION}
ROOT=/fsx/analysis_results/johnm/${SESSION}
REPO=${ROOT}/daylily-omics-analysis
echo "utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "== status =="
cat "${RUN}/status.json" 2>/dev/null || true
echo
echo "== squeue all =="
squeue -o '%.18i %.9P %.55j %.12u %.12T %.10M %.6D %.25R %.8C %.12m' || true
echo "== recent sent_snv sacct =="
sacct -X -S 2026-05-23T09:00:00 -o JobID,JobName%80,State,ExitCode,NodeList%30,AllocCPUS,ReqMem,Elapsed,Start,End -P 2>/dev/null | grep -E 'sent_snv_ont|JobID' || true
echo "== tmux tail markers =="
grep -nE 'Submitted job|Trying to restart|Error in rule|sent_snv_ont|Return code|Failed to open|Workflow exited|RETURN CODE|Exiting' "${RUN}/tmux.log" | tail -n 160 || true
echo "== capture tree =="
find "${ROOT}/ont_tmp_capture" -maxdepth 4 -printf '%M\t%s\t%p\n' 2>/dev/null | sort || true
echo "== sentdont log last 80 =="
find "${REPO}/results" -path '*snv/sentdont/log/*sentdont.snv.log' -type f -print 2>/dev/null | sort | while read -r f; do echo "-- $f"; tail -n 80 "$f"; done
