set -euo pipefail
SESSION=hg003a_ont_snv_alignstats_1018_191_preservetmp_dryrun
REPO=/fsx/analysis_results/johnm/${SESSION}/daylily-omics-analysis
RUN=/home/ubuntu/daylily-runs/${SESSION}
echo "== status =="
cat "${RUN}/status.json" || true
echo
echo "== config sentdont/sentD =="
python3 -c "import yaml; c=yaml.safe_load(open('${REPO}/config/day_profiles/slurm/rule_config.yaml')); print('sentdont', {k:c.get('sentdont',{}).get(k) for k in ['threads','use_threads','partition','mem_mb','vcpu']}); print('sentD', {k:c.get('sentD',{}).get(k) for k in ['threads','use_threads','partition','mem_mb','vcpu']})"
echo "== rule grep =="
grep -nE 'TMPDIR|SENTIEON_TMPDIR|trap|preserve|DEBUG|rsync|sentieon-cli|dnascope-longread' "${REPO}/workflow/rules/sent_snv_ont.smk" | sed -n '1,220p'
echo "== tmux tail =="
tail -n 120 "${RUN}/tmux.log" || true
echo "== run dirs matching real =="
find /home/ubuntu/daylily-runs -maxdepth 1 -type d -name '*191*preserve*' | sort || true
echo "== fsx dirs matching real =="
find /fsx/analysis_results/johnm -maxdepth 1 -type d -name '*191*preserve*' | sort || true
