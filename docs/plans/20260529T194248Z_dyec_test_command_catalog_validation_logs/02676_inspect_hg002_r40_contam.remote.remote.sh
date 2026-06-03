set -euo pipefail
repo=/fsx/analysis_results/ubuntu/ccv20260529r40_illumina_hg002_kitchensink_multiqc/daylily-omics-analysis
cd "$repo"
echo '=== contam_identity.smk haplocheck block ==='
python3 - <<'PY'
from pathlib import Path
p=Path('workflow/rules/contam_identity.smk')
text=p.read_text()
idx=text.find('haplocheck_rc')
if idx == -1:
    idx=text.find('params.command:q')
print(text[max(0,idx-1200):idx+2200])
PY
echo '=== haplocheck log tail ==='
tail -80 results/day/hg38/JEMILMN0P1-HG002-0p1x-1-D0-PF-ILMN-NOVASEQ/align/sent/dmd/snv/sentd/contam_identity/haplocheck/vcf/logs/JEMILMN0P1-HG002-0p1x-1-D0-PF-ILMN-NOVASEQ.sent.dmd.sentd.haplocheck.vcf.log || true
echo '=== outputs ==='
ls -l results/day/hg38/JEMILMN0P1-HG002-0p1x-1-D0-PF-ILMN-NOVASEQ/align/sent/dmd/snv/sentd/contam_identity/haplocheck/vcf/ || true
