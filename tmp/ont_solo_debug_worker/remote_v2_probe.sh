set -euo pipefail
SESSION=hg003a_ont_snv_alignstats_1018_191_preservetmp_v2
RUN=/home/ubuntu/daylily-runs/${SESSION}
ROOT=/fsx/analysis_results/johnm/${SESSION}
REPO=${ROOT}/daylily-omics-analysis
NODE=i192mem-dy-all-1
echo "utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "== status =="
cat "${RUN}/status.json" 2>/dev/null || true
echo
echo "== sentdont config =="
python3 -c "import yaml; c=yaml.safe_load(open('${REPO}/config/day_profiles/slurm/rule_config.yaml')); s=c.get('sentdont',{}); print({k:s.get(k) for k in ['threads','use_threads','partition','mem_mb','vcpu']})" 2>/dev/null || true
echo "== rule capture grep =="
grep -nE 'capture_sentdont_tmp|ont_tmp_capture|trap .*TMPDIR|tar -C|ONT_TMP_CAPTURE|SENTIEON_TMPDIR|export TMPDIR' "${REPO}/workflow/rules/sent_snv_ont.smk" 2>/dev/null | sed -n '1,220p' || true
echo "== squeue all =="
squeue -o '%.18i %.9P %.55j %.12u %.12T %.10M %.6D %.25R %.8C %.12m' || true
echo "== scontrol 182 =="
scontrol show job 182 2>&1 || true
echo "== sacct 182 =="
sacct -j 182 -o JobID,JobName%80,State,ExitCode,NodeList%30,AllocCPUS,ReqMem,Elapsed,Start,End -P 2>/dev/null || true
echo "== sent_snv log paths =="
find "${REPO}/results" -path '*snv/sentdont/log/*sentdont.snv.log' -type f -print 2>/dev/null | sort || true
echo "== capture dirs =="
find "${ROOT}/ont_tmp_capture" -maxdepth 3 -print 2>/dev/null | sort || true
echo "== live node shm =="
ssh -o BatchMode=yes -o ConnectTimeout=10 "${NODE}" "bash -l -c 'hostname; date -u +%Y-%m-%dT%H:%M:%SZ; df -h /dev/shm || true; df -i /dev/shm || true; find /dev/shm -maxdepth 4 -name \"sentdont_tmp_*\" -printf \"%M\\t%s\\t%p\\n\" 2>/dev/null | sort || true; ps -eo pid,ppid,stat,pcpu,pmem,rss,vsz,cmd | grep -E \"sentieon|DNAscope|dnascope\" | grep -v grep || true'" || true
