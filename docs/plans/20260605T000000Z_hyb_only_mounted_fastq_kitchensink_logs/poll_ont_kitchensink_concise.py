#!/usr/bin/env python3
"""Concise ONT kitchen-sink-rest status poll."""

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
tmux_log="/home/ubuntu/daylily-runs/$session/tmux.log"
report="$repo/results/day/hg38_broad/reports/DAY_final_multiqc.html"
data="$repo/results/day/hg38_broad/reports/DAY_final_multiqc_data/multiqc_data.json"
manifest="$repo/results/day/hg38_broad/reports/dayoa_evidence_manifest.json"
latest="$(ls -1t "$repo"/.snakemake/log/*.log 2>/dev/null | head -n 1 || true)"
echo "session=$session"
if tmux has-session -t "$session" 2>/dev/null; then echo "tmux=present"; else echo "tmux=missing"; fi
echo "controllers=$(ps -fu ubuntu | awk '/dy-r|day_run|snakemake/ && !/awk/ {{n++}} END {{print n+0}}')"
echo "slurm_summary:"
squeue -u ubuntu -h -o "%T" | sort | uniq -c || true
echo "slurm_jobs:"
squeue -u ubuntu -o "%.18i %.9P %.8j %.8T %.10M %.6D %.25R" | sed -n '1,12p' || true
echo "reports:"
for f in "$report" "$data" "$manifest"; do
  if [[ -e "$f" ]]; then
    stat -c "%n|%s|%y" "$f"
  else
    echo "$f|MISSING|"
  fi
done
echo "latest_snakemake_log=$latest"
if [[ -n "$latest" ]]; then
  echo "snakemake_progress:"
  grep -E "([0-9]+ of [0-9]+ steps|Finished job|Error in rule|WorkflowError|Complete log|Building DAG|Provided cores|Select jobs|Submitted job|Failed|Workflow|Nothing to be done)" "$latest" | tail -n 40 || true
fi
if [[ -f "$tmux_log" ]]; then
  echo "tmux_markers:"
  grep -E "(Workflow exited|Complete log|Finished job|Error in rule|WorkflowError|Waiting at most|Submitted job|Nothing to be done)" "$tmux_log" | tail -n 40 || true
fi
df -h /fsx
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
            comment=f"poll ONT kitchen-sink concise {args.session[:32]}",
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
