set -euo pipefail
BASE=hg003a_ont_snv_alignstats_1018_191_preservetmp
echo "== date =="
date -u +%Y-%m-%dT%H:%M:%SZ
echo "== run dirs =="
find /home/ubuntu/daylily-runs -maxdepth 1 -type d -name "${BASE}*" | sort || true
echo "== fsx dirs =="
find /fsx/analysis_results/johnm -maxdepth 1 -type d -name "${BASE}*" | sort || true
echo "== statuses =="
for s in "${BASE}" "${BASE}_dryrun"; do
  if [ -f "/home/ubuntu/daylily-runs/${s}/status.json" ]; then
    echo "-- ${s}"
    cat "/home/ubuntu/daylily-runs/${s}/status.json"
    echo
  fi
done
echo "== active slurm jobs =="
squeue -o '%.18i %.9P %.45j %.12u %.12T %.10M %.6D %.25R %.8C %.12m' || true
echo "== recent sent_snv_ont sacct =="
sacct -X -S 2026-05-23T00:00:00 -o JobID,JobName%60,State,ExitCode,NodeList%30,AllocCPUS,ReqMem,Elapsed -P 2>/dev/null | grep -E 'sent_snv_ont|JobID' || true
for s in "${BASE}" "${BASE}_dryrun"; do
  REPO="/fsx/analysis_results/johnm/${s}/daylily-omics-analysis"
  if [ -d "$REPO" ]; then
    echo "== inspect ${s} config =="
    python3 -c "import yaml; c=yaml.safe_load(open('${REPO}/config/day_profiles/slurm/rule_config.yaml')); print({k:c.get('sentdont',{}).get(k) for k in ['threads','use_threads','partition','mem_mb','vcpu']})"
    echo "== inspect ${s} rule capture grep =="
    grep -nE 'TMPDIR|SENTIEON_TMPDIR|trap|capture|ont_tmp_capture|tar -C|rsync|rm -rf' "${REPO}/workflow/rules/sent_snv_ont.smk" | sed -n '1,220p' || true
    echo "== inspect ${s} tmp capture dirs =="
    find "/fsx/analysis_results/johnm/${s}" -maxdepth 3 -path '*ont_tmp_capture*' -print 2>/dev/null | sort || true
  fi
done
