set -euo pipefail

printf 'UTC %s\n' "$(date -u +%FT%TZ)"
root=/fsx/control_data/genomic_data/organism_reads/H_sapiens/complete_genomics

echo "--- complete-genomics HG003 candidates ---"
find "$root" -maxdepth 4 -type f \( -name '*HG003*Read_1*.fq.gz' -o -name '*HG003*Read_2*.fq.gz' \) -printf '%TY-%Tm-%TdT%TH:%TM:%TS\t%s\t%p\n' | sort -k1,1 -k3,3

r1="$root/T7plus_WGS_PE150_HG003_PCR_Free_Read_1.fq.gz"
r2="$root/T7plus_WGS_PE150_HG003_PCR_Free_Read_2.fq.gz"
echo "--- selected pair stat ---"
for f in "$r1" "$r2"; do
  test -s "$f"
  stat -c '%n size=%s mtime=%y' "$f"
done

echo "--- selected pair gzip-header smoke ---"
set +o pipefail
gzip -cd "$r1" | head -n 4
gzip -cd "$r2" | head -n 4
set -o pipefail
echo "selected_pair_light_check_ok=true"
