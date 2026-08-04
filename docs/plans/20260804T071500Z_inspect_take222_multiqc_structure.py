#!/usr/bin/env python3
"""Read-only structural inspection of Take222 final MultiQC data."""

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
dyec analysis visit --analysis-root __ROOT__ --mode read --intent 'Inspect Take222 final MultiQC data structure'
cd __ROOT__/daylily-omics-analysis
/home/ubuntu/miniconda3/envs/DAY-EC/bin/python - <<'PY'
import json
from pathlib import Path

path = Path('results/day/hg38/reports/DAY_final_multiqc_data/multiqc_data.json')
data = json.loads(path.read_text(encoding='utf-8'))

def shape(value):
    if isinstance(value, dict):
        return {'type': 'dict', 'length': len(value), 'keys': list(value)[:120]}
    if isinstance(value, list):
        return {'type': 'list', 'length': len(value), 'sample': value[:2]}
    return {'type': type(value).__name__, 'value': value}

print(json.dumps({
    'path': str(path),
    'size': path.stat().st_size,
    'top_level': {key: shape(value) for key, value in data.items()},
}, indent=2, sort_keys=True, default=str))
PY
""".replace("__ROOT__", ROOT)
    result = run_shell(
        target.instance_id,
        REGION,
        script,
        profile=PROFILE,
        as_user="ubuntu",
        timeout=300,
        comment="Inspect Take222 MultiQC structure",
    )
    print(result.stdout)
    if result.stderr:
        print(result.stderr)
    return 0 if result.status == "Success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
