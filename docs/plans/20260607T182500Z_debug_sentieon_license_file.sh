#!/usr/bin/env bash
set -euo pipefail

sentieon="/fsx/references/runtime_assets/cached_envs/sentieon-genomics-202503.02/bin/sentieon"
license="/fsx/references/runtime_assets/cached_envs/Life_Sciences_Manufacturing_Corporation_eval.lic"

echo "HOST $(hostname)"
echo "DATE $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "SENTIEON ${sentieon}"
echo "LICENSE ${license}"

echo "LICENSE_FILE_STAT"
ls -l "$license"

echo "LICENSE_FILE_SERVER_LINES_ONLY"
grep -E '^(SERVER|VENDOR|DAEMON|USE_SERVER)' "$license" || true

echo "LICENSE_FILE_HOST_PORT_HINTS"
grep -Eo '([A-Za-z0-9._-]+:[0-9]{2,5}|[0-9]{1,3}([.][0-9]{1,3}){3}:[0-9]{2,5}|port=[0-9]{2,5})' "$license" | sort -u || true

echo "SENTIEON_VERSION"
"$sentieon" version 2>&1 || true

echo "LICCLNT_HELP"
"$sentieon" licclnt --help 2>&1 | head -120 || true

echo "LICCLNT_PING_DEFAULT"
SENTIEON_LICENSE="$license" timeout 60 "$sentieon" licclnt ping 2>&1 || true

echo "LICCLNT_QUERY_DEFAULT"
SENTIEON_LICENSE="$license" timeout 60 "$sentieon" licclnt query 2>&1 || true

echo "PROCESS_LICENSE_ERRORS_RECENT"
cd /fsx/analysis_results/hyb-only/hybonly_hybrid_hiomr_na4_ds20x_x8_fullvars_5017_20260607T124257Z/daylily-omics-analysis
tail -n 30 results/day/hg38_broad/HYB-4Coriells-chip3-chip4-ds20x-NA03986-DMPK-chip3-chip4-barcode20-chip4-PF-ILMN-NOVASEQ/align/sentmm2ont/dmd/snv/sentdhiomr/log/HYB-4Coriells-chip3-chip4-ds20x-NA03986-DMPK-chip3-chip4-barcode20-chip4-PF-ILMN-NOVASEQ.sentmm2ont.dmd.4.stage3.log || true
