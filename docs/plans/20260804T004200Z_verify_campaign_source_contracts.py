#!/usr/bin/env python3
"""Read-only exact campaign source contract verification."""

from daylily_ec.aws.ssm import resolve_headnode_instance_id, run_shell

CLUSTER = "preval-hiomr2"
PROFILE = "lsmc"
REGION = "us-west-2"


def main() -> int:
    target = resolve_headnode_instance_id(CLUSTER, REGION, profile=PROFILE)
    script = r"""set -euo pipefail
for root in \
  /fsx/analysis_results/preval-hiomr2/13-4-0/daylily-omics-analysis \
  /fsx/analysis_results/preval-hiomr2/take222/daylily-omics-analysis; do
  printf 'ROOT=%s\n' "$root"
  for name in specimens.tsv samples.tsv libraries.tsv sequencing_inputs.tsv analysis_units.tsv analysis_unit_inputs.tsv; do
    path="$root/config/$name"
    test -s "$path"
    printf '%s|' "$name"
    wc -l < "$path"
    sha256sum "$path"
  done
done
python - <<'PY'
from pathlib import Path
import csv
for manifest in [
    Path('/fsx/analysis_results/preval-hiomr2/13-4-0/daylily-omics-analysis/config/sequencing_inputs.tsv'),
    Path('/fsx/analysis_results/preval-hiomr2/take222/daylily-omics-analysis/config/sequencing_inputs.tsv'),
]:
    paths = []
    with manifest.open() as fh:
        for row in csv.DictReader(fh, delimiter='\t'):
            for key, value in row.items():
                if key and (key.endswith('_PATH') or key.endswith('_R1_PATH') or key.endswith('_R2_PATH')) and value:
                    paths.extend(p.strip() for p in value.split(',') if p.strip())
    missing = [p for p in paths if not Path(p).is_file()]
    logical = sum(Path(p).stat().st_size for p in paths if Path(p).is_file())
    print(manifest, 'paths=', len(paths), 'missing=', len(missing), 'logical_bytes=', logical)
    for p in missing[:10]: print('MISSING', p)
for root in [Path('/fsx/analysis_results/preval-hiomr2/take333lc'), Path('/fsx/analysis_results/preval-hiomr2/remaining-giab')]:
    print(root, 'exists=', root.exists())
PY
"""
    result = run_shell(target.instance_id, REGION, script, profile=PROFILE, as_user="ubuntu", timeout=600, comment="Verify exact campaign source contracts")
    print(result.stdout)
    if result.stderr:
        print(result.stderr)
    return 0 if result.status == "Success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
