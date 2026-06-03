#!/usr/bin/env bash
set -euo pipefail

analysis_root="/fsx/analysis_results/ubuntu/ccv20260530r42_illumina_bclconvert/daylily-omics-analysis"
cd "$analysis_root"
echo "time=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
python - <<'PY'
from pathlib import Path
text = Path("workflow/rules/bclconvert.smk").read_text()
idx = text.find("localrules:")
print(text[idx:idx+500])
PY
