#!/usr/bin/env python3
"""Run the remaining ONT kitchen-sink targets in the existing DayOA checkout."""

from __future__ import annotations

import argparse
import json
import shlex
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from daylily_ec.aws.ssm import SsmCommandFailedError, run_shell  # noqa: E402


DEFAULT_REPO_PATH = (
    "/fsx/analysis_results/ubuntu/"
    "hybonly_ont_chipbarcode_limited_live_20260606T090222Z/"
    "daylily-omics-analysis"
)

DY_COMMAND = (
    "dy-r "
    "produce_sentmm2ont_align "
    "produce_alignstats "
    "produce_na_dedup_cram "
    "produce_sentdont_snv_vcf "
    "produce_snv_concordances "
    "produce_relatedness "
    "produce_vep "
    "produce_multiqc_all "
    "results/day/hg38_broad/reports/DAY_final_multiqc.html "
    "results/day/hg38_broad/reports/dayoa_evidence_manifest.json "
    "--config "
    "'multiqc_qc={\"enable_tools\":[\"vep\"]}' "
    "-p -j 5 -k --rerun-triggers mtime"
)


def _remote_script(session: str, repo_path: str) -> str:
    quoted_session = shlex.quote(session)
    quoted_repo = shlex.quote(repo_path)
    quoted_dy_command = shlex.quote(DY_COMMAND)
    tmux_log = f"/home/ubuntu/daylily-runs/{session}/tmux.log"
    payload = {
        "session": session,
        "repo_path": repo_path,
        "tmux_log": tmux_log,
        "genome": "hg38_broad",
        "dy_command": DY_COMMAND,
    }
    return f"""
set -euo pipefail
session={quoted_session}
repo_path={quoted_repo}
dy_command={quoted_dy_command}
run_dir="/home/ubuntu/daylily-runs/$session"
tmux_log="$run_dir/tmux.log"
mkdir -p "$run_dir"
: > "$tmux_log"
if [[ ! -d "$repo_path/.git" ]]; then
  echo "__DAYLILY_ERROR__=missing_repo $repo_path"
  exit 11
fi
if tmux has-session -t "$session" 2>/dev/null; then
  echo "__DAYLILY_ERROR__=session_exists $session"
  exit 12
fi
tmux new-session -d -s "$session" 'bash -il'
tmux pipe-pane -t "$session" -o "cat >> $tmux_log"
tmux send-keys -t "$session" "cd $repo_path" C-m
tmux send-keys -t "$session" "git status --short --branch" C-m
tmux send-keys -t "$session" "git rev-parse HEAD" C-m
tmux send-keys -t "$session" "source dyoainit" C-m
tmux send-keys -t "$session" "dy-a slurm hg38_broad" C-m
tmux send-keys -t "$session" "$dy_command" C-m
python3 -c {shlex.quote("import json; print(" + repr(json.dumps(payload, sort_keys=True)) + ")")}
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--session", required=True)
    parser.add_argument("--instance-id", default="i-05374380b57fad901")
    parser.add_argument("--region", default="us-west-2")
    parser.add_argument("--profile", default="lsmc")
    parser.add_argument("--repo-path", default=DEFAULT_REPO_PATH)
    args = parser.parse_args()

    try:
        result = run_shell(
            args.instance_id,
            args.region,
            _remote_script(args.session, args.repo_path),
            profile=args.profile,
            as_user="ubuntu",
            timeout=120,
            comment=f"run ONT kitchen-sink rest {args.session[:32]}",
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
