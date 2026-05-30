set -euo pipefail
repo=/fsx/analysis_results/ubuntu/ccv20260529r39_illumina_bclconvert/daylily-omics-analysis
cd "$repo"
echo "=== bclconvert rule patch ==="
rg -n 'Moving BCLConvert outputs|Removing staged BCL input scratch|scratch_run_dir' workflow/rules/bclconvert.smk
echo "=== active profile bclconvert block ==="
python3 - <<'PY'
from pathlib import Path

path = Path(".daylily/daylily_profile/rule_config.yaml")
if not path.is_file():
    path = Path("profiles/default/rule_config.yaml")
lines = path.read_text(encoding="utf-8").splitlines()
for index, line in enumerate(lines):
    if line.strip() == "bclconvert:":
        for out_line in lines[index : index + 60]:
            if out_line and not out_line.startswith(" ") and out_line != "bclconvert:":
                break
            print(out_line)
        break
PY
