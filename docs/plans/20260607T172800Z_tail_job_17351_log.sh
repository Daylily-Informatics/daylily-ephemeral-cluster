#!/usr/bin/env bash
set -euo pipefail

cd /fsx/analysis_results/hyb-only/hybonly_hybrid_hiomr_na4_ds20x_x8_fullvars_5017_20260607T124257Z/daylily-omics-analysis

log="results/day/hg38_broad/HYB-4Coriells-chip3-chip4-ds20x-NA03986-DMPK-chip3-chip4-barcode20-chip4-PF-ILMN-NOVASEQ/align/sentmm2ont/dmd/snv/sentdhiomr/log/HYB-4Coriells-chip3-chip4-ds20x-NA03986-DMPK-chip3-chip4-barcode20-chip4-PF-ILMN-NOVASEQ.sentmm2ont.dmd.4.stage3.log"

echo "DATE $(date -u +%Y-%m-%dT%H:%M:%SZ)"
squeue -j 17351,16939,18791,18676,18677,18334 -o "%i|%T|%M|%R"
stat -c "size=%s mtime=%y" "$log"
tail -n 40 "$log"
