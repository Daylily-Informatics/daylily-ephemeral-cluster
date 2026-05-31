#!/usr/bin/env bash
set -euo pipefail

analysis_root="/fsx/analysis_results/ubuntu/ccv20260530r42_illumina_bclconvert/daylily-omics-analysis"
units="$analysis_root/config/units.tsv"
backup="$analysis_root/config/units.generated-unsanitized.tsv"

echo "time=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
test -s "$units"
cp -- "$units" "$backup"
python - <<'PY'
import csv
from pathlib import Path

path = Path("/fsx/analysis_results/ubuntu/ccv20260530r42_illumina_bclconvert/daylily-omics-analysis/config/units.tsv")
rows = []
with path.open(newline="", encoding="utf-8") as handle:
    reader = csv.DictReader(handle, delimiter="\t")
    fieldnames = reader.fieldnames or []
    for row in reader:
        for key in ("RUNID", "EXPERIMENTID"):
            row[key] = (row.get(key) or "").replace("_", "-").replace(".", "-")
        rows.append(row)
with path.open("w", newline="", encoding="utf-8") as handle:
    writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t", lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
PY
echo "backup=$backup"
head -5 "$units"
