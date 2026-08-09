#!/usr/bin/env python3
"""Read-only discovery of Take222 report, benchmark, and packaging sources."""

from daylily_ec.aws.ssm import resolve_headnode_instance_id, run_shell


CLUSTER = "preval-hiomr2"
PROFILE = "lsmc"
REGION = "us-west-2"
ROOT = "/fsx/analysis_results/preval-hiomr2/take222"


def main() -> int:
    target = resolve_headnode_instance_id(CLUSTER, REGION, profile=PROFILE)
    script = """set -euo pipefail
export DAYOA_AGENT_ID=codex-take222-report-20260804
export DAYOA_AGENT_KIND=codex
export DAYOA_HUMAN_REQUESTOR='John Major'
export DAYOA_TMUX_SESSION=dayoa_take222_hg003_hg004_smn12_20260803
export DAYOA_LEDGER_PATH='/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster/docs/plans/20260804T070646Z_take222_hiomr2_runtime_results_report_ledger.md'
dyec analysis visit --analysis-root __ROOT__ --mode read --intent 'Discover Take222 report evidence sources'
cd __ROOT__/daylily-omics-analysis
/home/ubuntu/miniconda3/envs/DAY-EC/bin/python - <<'PY'
import collections
import json
from pathlib import Path

root = Path('results/day/hg38')
files = [p for p in root.rglob('*') if p.is_file()]
patterns = (
    'bench', 'multiqc', 'mqc', 'rtg', 'giab', 'truvari', 'smn', 'alignstat',
    'coverage', 'fragment', 'package_manifest', 'evidence_manifest', 'treatment',
)
selected = []
for path in files:
    rel = path.as_posix()
    low = rel.lower()
    if any(pattern in low for pattern in patterns):
        selected.append({'path': rel, 'size': path.stat().st_size})

basenames = collections.Counter(p.name for p in files)
suffixes = collections.Counter(''.join(p.suffixes[-2:]) or '<none>' for p in files)
payload = {
    'file_count': len(files),
    'total_bytes': sum(p.stat().st_size for p in files),
    'top_repeated_basenames': basenames.most_common(120),
    'suffix_counts': suffixes.most_common(80),
    'selected_count': len(selected),
    'selected': sorted(selected, key=lambda row: row['path']),
}
print(json.dumps(payload, indent=2, sort_keys=True))
PY
""".replace("__ROOT__", ROOT)
    result = run_shell(
        target.instance_id,
        REGION,
        script,
        profile=PROFILE,
        as_user="ubuntu",
        timeout=300,
        comment="Discover Take222 report sources",
    )
    print(result.stdout)
    if result.stderr:
        print(result.stderr)
    return 0 if result.status == "Success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
