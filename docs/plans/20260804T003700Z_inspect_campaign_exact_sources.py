#!/usr/bin/env python3
"""Read-only exact source and capacity inspection for the two new runs."""

from daylily_ec.aws.ssm import resolve_headnode_instance_id, run_shell

CLUSTER = "preval-hiomr2"
PROFILE = "lsmc"
REGION = "us-west-2"


def main() -> int:
    target = resolve_headnode_instance_id(CLUSTER, REGION, profile=PROFILE)
    script = r"""set -euo pipefail
printf '%s\n' '== available bytes =='
df -B1 --output=avail /fsx | tail -1
printf '%s\n' '== prior-root bytes =='
du -sx --block-size=1 /fsx/analysis_results/preval-hiomr2/13-4-0 /fsx/analysis_results/preval-hiomr2/take222
printf '%s\n' '== source configs =='
for path in \
  /fsx/analysis_results/preval-hiomr2/13-4-0/daylily-omics-analysis/config/hg002_bjuice_true5x5x_hiomr2_13_4_0.yaml \
  /fsx/analysis_results/preval-hiomr2/13-4-0/daylily-omics-analysis/config/hg002_bjuice_5x5x_hiomr2.yaml \
  /fsx/analysis_results/preval-hiomr2/13-4-0/daylily-omics-analysis/config/sequencing_inputs.tsv \
  /fsx/analysis_results/preval-hiomr2/13-4-0/daylily-omics-analysis/config/samples.tsv \
  /fsx/analysis_results/preval-hiomr2/13-4-0/daylily-omics-analysis/config/libraries.tsv \
  /fsx/analysis_results/preval-hiomr2/take222/daylily-omics-analysis/config/hiomr2_take222_hg003_hg004_na19235_na20775_fullcov.yaml \
  /fsx/analysis_results/preval-hiomr2/take222/daylily-omics-analysis/config/sequencing_inputs.tsv \
  /fsx/analysis_results/preval-hiomr2/take222/daylily-omics-analysis/config/analysis_units.tsv \
  /fsx/analysis_results/preval-hiomr2/take222/daylily-omics-analysis/config/samples.tsv \
  /fsx/analysis_results/preval-hiomr2/take222/daylily-omics-analysis/config/libraries.tsv; do
  printf '%s\n' "--- $path"
  if test -f "$path"; then sed -n '1,120p' "$path"; else printf '%s\n' MISSING; fi
done
printf '%s\n' '== source files exist and total logical bytes =='
python - <<'PY'
from pathlib import Path
import csv
for manifest in [
    Path('/fsx/analysis_results/preval-hiomr2/13-4-0/daylily-omics-analysis/config/sequencing_inputs.tsv'),
    Path('/fsx/analysis_results/preval-hiomr2/take222/daylily-omics-analysis/config/sequencing_inputs.tsv'),
]:
    total = missing = count = 0
    with manifest.open() as fh:
        for row in csv.DictReader(fh, delimiter='\t'):
            for key, value in row.items():
                if key and ('FQ' in key or 'FASTQ' in key) and value:
                    for raw in value.split(','):
                        p = Path(raw.strip())
                        count += 1
                        if p.exists(): total += p.stat().st_size
                        else: missing += 1
    print(manifest, 'paths=', count, 'missing=', missing, 'bytes=', total)
PY
printf '%s\n' '== active =='
squeue -u ubuntu
ps -fu ubuntu | awk '/dy-r|bin\/day_run|snakemake/ && !/awk/ {print}'
"""
    result = run_shell(target.instance_id, REGION, script, profile=PROFILE, as_user="ubuntu", timeout=600, comment="Inspect exact two-run campaign sources")
    print(result.stdout)
    if result.stderr:
        print(result.stderr)
    return 0 if result.status == "Success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
