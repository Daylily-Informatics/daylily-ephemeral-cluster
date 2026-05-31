set -euo pipefail

printf 'UTC %s\n' "$(date -u +%FT%TZ)"
root=/fsx/control_data/genomic_data/organism_reads/H_sapiens/complete_genomics

echo "--- complete-genomics root ---"
find "$root" -maxdepth 4 -type f \( -name '*HG003*Read_1*.fq.gz' -o -name '*HG003*Read_2*.fq.gz' \) -printf '%s\t%p\n' | sort -k2

r1="$root/T7plus_WGS_PE150_HG003_PCR_Free_Read_1.fq.gz"
r2="$root/T7plus_WGS_PE150_HG003_PCR_Free_Read_2.fq.gz"
echo "--- selected pair ---"
for f in "$r1" "$r2"; do
  test -s "$f"
  stat -c '%n size=%s mtime=%y' "$f"
done

echo "--- gzip smoke ---"
gzip -t "$r1"
gzip -t "$r2"
echo "selected_pair_ok=true"
