#!/usr/bin/env bash
set -euo pipefail

REPO="/fsx/analysis_results/hyb-only/hybonly_hybrid_hiomr_na4_ds20x_x8_fullvars_5017_20260607T124257Z/daylily-omics-analysis"
cd "${REPO}"

paths=(
"results/day/hg38_broad/HYB-4Coriells-chip3-chip4-ds20x-NA03986-DMPK-chip3-chip4-barcode20-chip4-PF-ILMN-NOVASEQ/align/sentmm2ont/dmd/snv/sentdhiomr/log/HYB-4Coriells-chip3-chip4-ds20x-NA03986-DMPK-chip3-chip4-barcode20-chip4-PF-ILMN-NOVASEQ.sentmm2ont.dmd.4.stage3.log"
"results/day/hg38_broad/HYB-4Coriells-chip3-chip4-ds20x-NA03986-DMPK-chip3-chip4-barcode20-chip4-PF-ILMN-NOVASEQ/align/sentmm2ont/dmd/snv/sentdhiomr/log/HYB-4Coriells-chip3-chip4-ds20x-NA03986-DMPK-chip3-chip4-barcode20-chip4-PF-ILMN-NOVASEQ.sentmm2ont.dmd.7.pass2.log"
"results/day/hg38_broad/HYB-4Coriells-chip1-chip2-ds20x-NA03986-DMPK-chip1-chip2-barcode20-chip1-chip2-PF-ILMN-NOVASEQ/align/sentmm2ont/dmd/snv/sentdhiomr/log/HYB-4Coriells-chip1-chip2-ds20x-NA03986-DMPK-chip1-chip2-barcode20-chip1-chip2-PF-ILMN-NOVASEQ.sentmm2ont.dmd.17-19.pass2.log"
"results/day/hg38_broad/HYB-4Coriells-chip1-chip2-ds20x-NA03986-DMPK-chip1-chip2-barcode20-chip1-chip2-PF-ILMN-NOVASEQ/align/sentmm2ont/dmd/snv/sentdhiomr/log/HYB-4Coriells-chip1-chip2-ds20x-NA03986-DMPK-chip1-chip2-barcode20-chip1-chip2-PF-ILMN-NOVASEQ.sentmm2ont.dmd.20-25.pass2.log"
"results/day/hg38_broad/HYB-4Coriells-chip1-chip2-ds20x-NA03986-DMPK-chip1-chip2-barcode20-chip1-chip2-PF-ILMN-NOVASEQ/align/sentmm2ont/dmd/snv/sentdhiomr/log/HYB-4Coriells-chip1-chip2-ds20x-NA03986-DMPK-chip1-chip2-barcode20-chip1-chip2-PF-ILMN-NOVASEQ.sentmm2ont.dmd.2.pass2.log"
"results/day/hg38_broad/HYB-4Coriells-chip1-chip2-ds20x-NA03986-DMPK-chip1-chip2-barcode20-chip1-chip2-PF-ILMN-NOVASEQ/align/sentmm2ont/dmd/snv/sentdhiomr/log/HYB-4Coriells-chip1-chip2-ds20x-NA03986-DMPK-chip1-chip2-barcode20-chip1-chip2-PF-ILMN-NOVASEQ.sentmm2ont.dmd.16.pass2.log"
)

echo "__TAILS__"
for p in "${paths[@]}"; do
    echo "===${p}==="
    stat -c 'mtime=%y size=%s path=%n' "${p}" || true
    tail -25 "${p}" || true
    shard_dir="$(dirname "${p}")"
    shard_dir="${shard_dir%/log}/vcfs"
    shard="$(basename "${p}" | sed -E 's/.*\\.dmd\\.([0-9]+(-[0-9]+)?)\\.(pass2|stage3)\\.log/\\1/')"
    tmp_dir="${shard_dir}/${shard}/tmp"
    echo "---TMP:${tmp_dir}---"
    find "${tmp_dir}" -maxdepth 1 -type f -printf '%TY-%Tm-%Td %TH:%TM:%TS %s %p\n' 2>/dev/null | sort | tail -40 || true
done

echo "__SQUEUE__"
squeue -j 17351,16939,18791,18676,18677,18334 -o "%.18i %.12P %.80j %.10T %.12M %.6D %R"
