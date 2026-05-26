set -euo pipefail
SESSION=hg003a_ont_snv_alignstats_1018_191_preservetmp
RUN=/home/ubuntu/daylily-runs/${SESSION}
REPO=/fsx/analysis_results/johnm/${SESSION}/daylily-omics-analysis
echo "== status =="
cat "${RUN}/status.json" || true
echo
echo "== tmux failure markers =="
grep -nE 'Traceback|NameError|Error in rule|RuleException|Missing|failed|Failed|ERROR|RETURN CODE|Workflow exited|LockException|exception|Exiting' "${RUN}/tmux.log" | tail -n 120 || true
echo "== tmux final 260 =="
tail -n 260 "${RUN}/tmux.log" || true
echo "== slurm files =="
find "${REPO}" -path '*logs/slurm*' -type f -maxdepth 12 -print 2>/dev/null | sort | tail -n 80 || true
echo "== pre_prep logs =="
find "${REPO}" -path '*logs/slurm/pre_prep_ont_cram*' -type f -print 2>/dev/null | sort | while read -r f; do echo "-- $f"; tail -n 80 "$f"; done
echo "== sent_snv logs =="
find "${REPO}/results" -path '*snv/sentdont/log/*sentdont.snv.log' -type f -print 2>/dev/null | sort | while read -r f; do echo "-- $f"; tail -n 120 "$f"; done
echo "== sacct relevant =="
sacct -X -S 2026-05-23T08:50:00 -o JobID,JobName%80,State,ExitCode,NodeList%30,AllocCPUS,ReqMem,Elapsed -P 2>/dev/null | grep -E 'pre_prep_ont_cram|sent_snv_ont|JobID' || true
echo "== capture dirs =="
find "/fsx/analysis_results/johnm/${SESSION}" -maxdepth 4 -path '*ont_tmp_capture*' -print 2>/dev/null | sort || true
