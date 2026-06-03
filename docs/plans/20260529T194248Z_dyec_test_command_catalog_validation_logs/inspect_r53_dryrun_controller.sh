#!/usr/bin/env bash
set -euo pipefail

analysis_id=ccv20260530r53_complete_genomics_mgi_snv_concordance_dryrun
root=/fsx/analysis_results/ubuntu/${analysis_id}

echo "=== root ==="
printf '%s\n' "$root"

echo "=== top-level files ==="
find "$root" -maxdepth 2 -type f -printf '%TY-%Tm-%TdT%TH:%TM:%TS %s %p\n' | sort | tail -80

echo "=== status ==="
cat "$root/status.json" || true

echo "=== likely controller/log files ==="
find "$root" -maxdepth 5 -type f \
  \( -name '*stdout*' -o -name '*stderr*' -o -name '*.log' -o -name 'status.json' \) \
  -printf '%TY-%Tm-%TdT%TH:%TM:%TS %s %p\n' | sort | tail -120

echo "=== grep errors ==="
grep -RInE 'Traceback|NameError|SyntaxError|WorkflowError|RuleException|Error|ERROR|exited with|returned non-zero|MissingInputException|MissingOutputException|Unlocking working directory|This was a dry-run' "$root" 2>/dev/null | tail -200 || true
