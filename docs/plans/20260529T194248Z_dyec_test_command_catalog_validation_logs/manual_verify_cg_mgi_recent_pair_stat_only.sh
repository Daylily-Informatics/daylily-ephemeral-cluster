set -euo pipefail

printf 'UTC %s\n' "$(date -u +%FT%TZ)"
root=/fsx/control_data/genomic_data/organism_reads/H_sapiens/complete_genomics
r1="$root/T7plus_WGS_PE150_HG003_PCR_Free_Read_1.fq.gz"
r2="$root/T7plus_WGS_PE150_HG003_PCR_Free_Read_2.fq.gz"

echo "--- selected pair stat-only verification ---"
for f in "$r1" "$r2"; do
  test -s "$f"
  stat -c '%n size=%s mtime=%y' "$f"
done
echo "selected_pair_stat_check_ok=true"
