set -euo pipefail
SESSION=hg003a_ont_snv_alignstats_1018_191_preservetmp
RUN=/home/ubuntu/daylily-runs/${SESSION}
REPO=/fsx/analysis_results/johnm/${SESSION}/daylily-omics-analysis
echo "== status compact =="
python3 -c "import json; d=json.load(open('${RUN}/status.json')); print(d)"
echo "== final tmux lines =="
tail -n 90 "${RUN}/tmux.log" || true
echo "== error grep compact =="
grep -nE 'Submitted job|external jobid|Error in rule|RuleException|Shell command|returned non-zero|Failed|failed|Traceback|NameError|RETURN CODE|Workflow exited|Exiting|srun|sbatch' "${RUN}/tmux.log" | tail -n 160 || true
echo "== slurm pre_prep files compact =="
find "${REPO}" -path '*logs/slurm/pre_prep_ont_cram*' -type f -print 2>/dev/null | sort | while read -r f; do echo "-- $f"; tail -n 40 "$f"; done
echo "== rule output existence =="
find "${REPO}/results/day/hg38_broad" -path '*align/ont/*cram*' -maxdepth 8 -printf '%p %s\n' 2>/dev/null | sort | tail -n 40 || true
echo "== sacct 180 =="
sacct -j 180 -o JobID,JobName%80,State,ExitCode,NodeList%30,AllocCPUS,ReqMem,Elapsed,Start,End -P 2>/dev/null || true
