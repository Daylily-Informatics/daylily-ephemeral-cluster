set -euo pipefail
NODE=i192-dy-all-1
echo "== headnode date =="
date -u +%Y-%m-%dT%H:%M:%SZ
echo "== ssh node shm =="
ssh -o BatchMode=yes -o ConnectTimeout=10 "${NODE}" "bash -l -c 'hostname; date -u +%Y-%m-%dT%H:%M:%SZ; df -h /dev/shm || true; df -i /dev/shm || true; find /dev/shm -maxdepth 2 -name \"sentdont_tmp_*\" -printf \"%M\\t%s\\t%p\\n\" 2>/dev/null | sort || true; ps -eo pid,ppid,stat,pcpu,pmem,rss,vsz,cmd | grep -E \"sentieon|dnascope|snakemake|pre_prep_ont\" | grep -v grep || true'" || true
