#!/usr/bin/env bash
set -euo pipefail

repo=/fsx/analysis_results/ubuntu/ccv20260530r49_hybrid_ultima_ont_snv/daylily-omics-analysis
cd "$repo"

rule=workflow/rules/sent_hybrid_ug_ont_modular.refactored.smk
log=results/day/hg38_broad/TVBHUO5X5X-HG003-UG5x-ONT5x-1-D0-PF-UG-ULTIMA/align/ug/na/snv/sentdhuomr/log/TVBHUO5X5X-HG003-UG5x-ONT5x-1-D0-PF-UG-ULTIMA.ug.na.1-24.stage1.log
stage2=results/day/hg38_broad/TVBHUO5X5X-HG003-UG5x-ONT5x-1-D0-PF-UG-ULTIMA/align/ug/na/snv/sentdhuomr/log/TVBHUO5X5X-HG003-UG5x-ONT5x-1-D0-PF-UG-ULTIMA.ug.na.1-24.stage2.log

echo "=== rule sentdhuomr_stage1 vicinity ==="
grep -nE 'rule sentdhuomr_stage1|HybridStage1|stage1_hap|quickcheck|DYEC_RUNTIME_REPAIR|kmerSize|set \\+e|stage2' "$rule" | head -120

echo "=== stage1 log markers ==="
grep -nE 'DYEC_RUNTIME_REPAIR|ReadSequenceKmerGraphBuilder|kmerSize|stage1_hap|ERROR|Assertion|failed|Elapsed' "$log" | tail -120 || true

echo "=== stage2 log markers ==="
grep -nE 'DYEC_RUNTIME_REPAIR|failed to find target hap|HapCutAltMap|Assertion|ERROR|Elapsed' "$stage2" | tail -160 || true

echo "=== stage1 outputs ==="
find "$(dirname "$log")/.." -maxdepth 2 -type f \( -name '*stage1*' -o -name '*hap*' \) -printf '%TY-%Tm-%TdT%TH:%TM:%TS %s %p\n' | sort | tail -80
