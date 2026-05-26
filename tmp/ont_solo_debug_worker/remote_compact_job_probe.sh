set -euo pipefail
SESSION=hg003a_ont_snv_alignstats_1018_191_preservetmp
RUN=/home/ubuntu/daylily-runs/${SESSION}
REPO=/fsx/analysis_results/johnm/${SESSION}/daylily-omics-analysis
echo "utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "status=$(python3 -c "import json; p='${RUN}/status.json'; d=json.load(open(p)); print(d.get('exit_code'), d.get('started_at'), d.get('completed_at'))" 2>/dev/null || true)"
echo "sentdont_config=$(python3 -c "import yaml; c=yaml.safe_load(open('${REPO}/config/day_profiles/slurm/rule_config.yaml')); s=c.get('sentdont',{}); print(s.get('threads'), s.get('use_threads'), s.get('partition'), s.get('mem_mb'))" 2>/dev/null || true)"
echo "rule_trap=$(grep -nE 'trap .*TMPDIR|capture_sentdont_tmp|ont_tmp_capture' "${REPO}/workflow/rules/sent_snv_ont.smk" 2>/dev/null | tr '\n' ';' || true)"
echo "squeue_all="
squeue -o '%.18i %.9P %.45j %.12u %.12T %.10M %.6D %.25R %.8C %.12m' || true
echo "sacct_sent_snv_today="
sacct -X -S 2026-05-23T00:00:00 -o JobID,JobName%60,State,ExitCode,NodeList%30,AllocCPUS,ReqMem,Elapsed -P 2>/dev/null | grep -E 'sent_snv_ont|JobID' || true
echo "sent_snv_logs="
find "${REPO}/results" -path '*snv/sentdont/log/*sentdont.snv.log' -type f -print 2>/dev/null | sort || true
echo "capture_dirs="
find "/fsx/analysis_results/johnm/${SESSION}" -maxdepth 3 -path '*ont_tmp_capture*' -print 2>/dev/null | sort || true
