set -euo pipefail
SESSION=hg003a_ont_snv_alignstats_1018_191_preservetmp
RUN=/home/ubuntu/daylily-runs/${SESSION}
REPO=/fsx/analysis_results/johnm/${SESSION}/daylily-omics-analysis
echo "== status =="
cat "${RUN}/status.json" || true
echo
echo "== tmux log head =="
sed -n '1,180p' "${RUN}/tmux.log" || true
echo "== tmux log tail =="
tail -n 220 "${RUN}/tmux.log" || true
echo "== config sentdont =="
python3 -c "import yaml; c=yaml.safe_load(open('${REPO}/config/day_profiles/slurm/rule_config.yaml')); print(c.get('sentdont'))"
echo "== active jobs =="
squeue -o '%.18i %.9P %.45j %.12u %.12T %.10M %.6D %.25R %.8C %.12m' || true
echo "== run processes =="
pgrep -af "${SESSION}|snakemake|day_run|sentieon-cli|dnascope" || true
echo "== sent snv log paths =="
find "${REPO}/results" -path '*snv/sentdont/log/*sentdont.snv.log' -maxdepth 12 -type f -print 2>/dev/null | sort || true
