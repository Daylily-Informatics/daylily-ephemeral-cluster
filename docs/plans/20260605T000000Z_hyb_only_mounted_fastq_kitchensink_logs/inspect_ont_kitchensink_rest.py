#!/usr/bin/env python3
"""Inspect the ONT kitchen-sink-rest tmux session and report files."""

from __future__ import annotations

import argparse
import shlex
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from daylily_ec.aws.ssm import SsmCommandFailedError, run_shell  # noqa: E402


DEFAULT_ANALYSIS = (
    "/fsx/analysis_results/ubuntu/"
    "hybonly_ont_chipbarcode_limited_live_20260606T090222Z"
)


def _remote_script(session: str, analysis_dir: str) -> str:
    q_session = shlex.quote(session)
    q_analysis = shlex.quote(analysis_dir)
    return f"""
set -euo pipefail
session={q_session}
analysis_dir={q_analysis}
repo="$analysis_dir/daylily-omics-analysis"
report="$repo/results/day/hg38_broad/reports/DAY_final_multiqc.html"
data="$repo/results/day/hg38_broad/reports/DAY_final_multiqc_data/multiqc_data.json"
manifest="$repo/results/day/hg38_broad/reports/dayoa_evidence_manifest.json"
multiqc_log="$repo/results/day/hg38_broad/logs/produce_multiqc_all.log"
snakemake_log_dir="$repo/.snakemake/log"
tmux_log="/home/ubuntu/daylily-runs/$session/tmux.log"
echo "session=$session"
if tmux has-session -t "$session" 2>/dev/null; then
  echo "tmux=present"
  tmux list-windows -t "$session" || true
  tmux list-panes -t "$session" || true
  echo "capture_tail:"
  tmux capture-pane -pt "$session" -S -100 || true
else
  echo "tmux=missing"
fi
echo "tmux_log=$tmux_log"
if [[ -f "$tmux_log" ]]; then
  echo "tmux_log_tail:"
  tail -n 140 "$tmux_log"
fi
echo "reports:"
for f in "$report" "$data" "$manifest" "$multiqc_log"; do
  if [[ -e "$f" ]]; then
    ls -lh "$f"
  else
    echo "MISSING $f"
  fi
done
echo "latest_snakemake_log:"
latest="$(ls -1t "$snakemake_log_dir"/*.log 2>/dev/null | head -n 1 || true)"
if [[ -n "$latest" ]]; then
  echo "$latest"
  grep -E "^(\\[[^]]+\\]|[0-9]+ of [0-9]+ steps|Finished job|Error|WorkflowError|Complete log|Building DAG|Provided cores|Select jobs|Job stats)" "$latest" | tail -n 80 || true
fi
echo "controllers:"
ps -fu ubuntu | awk '/dy-r|day_run|snakemake/ && !/awk/ {{print}}' || true
echo "slurm:"
squeue -u ubuntu -o "%.18i %.9P %.8j %.8T %.10M %.6D %.20R" || true
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--session", required=True)
    parser.add_argument("--analysis-dir", default=DEFAULT_ANALYSIS)
    parser.add_argument("--instance-id", default="i-05374380b57fad901")
    parser.add_argument("--region", default="us-west-2")
    parser.add_argument("--profile", default="lsmc")
    args = parser.parse_args()

    try:
        result = run_shell(
            args.instance_id,
            args.region,
            _remote_script(args.session, args.analysis_dir),
            profile=args.profile,
            as_user="ubuntu",
            timeout=120,
            comment=f"inspect ONT kitchen-sink rest {args.session[:32]}",
        )
    except SsmCommandFailedError as exc:
        print(exc.result.stdout, end="")
        print(exc.result.stderr, end="", file=sys.stderr)
        return exc.result.response_code or 1

    print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    return result.response_code


if __name__ == "__main__":
    raise SystemExit(main())
