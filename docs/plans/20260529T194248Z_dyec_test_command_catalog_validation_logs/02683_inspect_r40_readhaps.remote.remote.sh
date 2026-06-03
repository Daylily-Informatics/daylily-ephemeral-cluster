set -euo pipefail
repo=/fsx/analysis_results/ubuntu/ccv20260529r40_illumina_hg002_kitchensink_multiqc/daylily-omics-analysis
cd "$repo"
log=results/day/hg38/JEMILMN0P1-HG002-0p1x-1-D0-PF-ILMN-NOVASEQ/align/sent/dmd/snv/sentd/contam_identity/read_haps/logs/JEMILMN0P1-HG002-0p1x-1-D0-PF-ILMN-NOVASEQ.sent.dmd.sentd.read_haps.log
out=results/day/hg38/JEMILMN0P1-HG002-0p1x-1-D0-PF-ILMN-NOVASEQ/align/sent/dmd/snv/sentd/contam_identity/read_haps/JEMILMN0P1-HG002-0p1x-1-D0-PF-ILMN-NOVASEQ.sent.dmd.sentd.read_haps.txt
echo '=== read_haps log ==='
ls -l "$log" "$out" || true
cat "$log" || true
echo '=== read_haps out ==='
cat "$out" || true
echo '=== vcf record count ==='
gzip -cd results/day/hg38/JEMILMN0P1-HG002-0p1x-1-D0-PF-ILMN-NOVASEQ/align/sent/dmd/snv/sentd/JEMILMN0P1-HG002-0p1x-1-D0-PF-ILMN-NOVASEQ.sent.dmd.sentd.snv.sort.vcf.gz | awk 'BEGIN{n=0}!/^#/{n++}END{print n}'
echo '=== read_haps rule patch snippet ==='
python3 - <<'PY'
from pathlib import Path
text=Path('workflow/rules/contam_identity.smk').read_text()
idx=text.find('rule read_haps_contam_identity')
print(text[idx:idx+2800])
PY
