#!/usr/bin/env bash
set -euo pipefail

analysis="/fsx/analysis_results/hyb-only/hybonly_hybrid_hiomr_na4_ds20x_x8_fullvars_5017_20260607T124257Z/daylily-omics-analysis"
jobs="19470,19471,19472,19473,19474,19475,19476,19477"

echo "DATE $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "SQUEUE"
squeue -j "$jobs" -o "%i|%P|%j|%T|%M|%D|%R" || true

cd "$analysis"

echo "GBA_DONE_COUNT"
find results/day/hg38_broad -path '*/segdup/sentdhiomr/*.segdup.GBA.done' | wc -l

echo "GBA_RESULT_VCFS"
find results/day/hg38_broad -path '*/segdup/sentdhiomr/results/GBA/*.vcf.gz' \
  -printf '%TY-%Tm-%TdT%TH:%TM:%TSZ %s %p\n' | sort | tail -20 || true

echo "GBA_RULE_LOGS_MTIME"
find results/day/hg38_broad -path '*/segdup/sentdhiomr/log/*.GBA.log' \
  -printf '%TY-%Tm-%TdT%TH:%TM:%TSZ %s %p\n' | sort | tail -20 || true

echo "GBA_RULE_LOG_TAILS"
while IFS= read -r log; do
  echo "== ${log} =="
  tail -n 20 "$log" || true
done < <(find results/day/hg38_broad -path '*/segdup/sentdhiomr/log/*.GBA.log' | sort | tail -8)

echo "SLURM_LOG_CANDIDATES"
find logs -type f \( -path '*sentdhiomr_call_segdup_gene*' -o -path '*19470*' -o -path '*19471*' -o -path '*19472*' -o -path '*19473*' -o -path '*19474*' -o -path '*19475*' -o -path '*19476*' -o -path '*19477*' \) \
  -printf '%TY-%Tm-%TdT%TH:%TM:%TSZ %s %p\n' | sort | tail -40 || true

echo "SLURM_RECENT_TAILS"
while IFS= read -r slurm_log; do
  echo "== ${slurm_log} =="
  tail -n 20 "$slurm_log" || true
done < <(find logs -type f \( -path '*sentdhiomr_call_segdup_gene*' -o -path '*19470*' -o -path '*19471*' -o -path '*19472*' -o -path '*19473*' -o -path '*19474*' -o -path '*19475*' -o -path '*19476*' -o -path '*19477*' \) | sort | tail -8)

echo "TMUX_PROGRESS"
tmux capture-pane -t hyb_x8_fullvars_5017_20260607T124257Z -p -S -1200 \
  | grep -E 'Submitted job|Finished job|[0-9]+ of [0-9]+ steps|Error|MissingOutput|WorkflowError|RETURN CODE|Complete log|Exiting' \
  | tail -80 || true
