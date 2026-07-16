#!/usr/bin/env python3
"""Summarize a remote workflow tmux log without emitting giant lines."""

from __future__ import annotations

import argparse
import shlex

from daylily_ec.aws.ssm import run_shell


REMOTE_SCRIPT_TEMPLATE = r"""
set -euo pipefail
export DAYLILY_LOG_PATH=__LOG_PATH__
export DAYLILY_CONTEXT=__CONTEXT__
export DAYLILY_WIDTH=__WIDTH__
python3 -c 'import os, re
from pathlib import Path

path = Path(os.environ["DAYLILY_LOG_PATH"])
context = int(os.environ["DAYLILY_CONTEXT"])
width = int(os.environ["DAYLILY_WIDTH"])
patterns = re.compile(r"Error|ERROR|Exception|Traceback|Missing|Ambiguous|RuleException|WorkflowError|InputFunction|KeyError|failed|Failed|exit code|Exiting|Incomplete|SyntaxError", re.I)
if not path.is_file():
    print(f"MISSING_LOG {path}")
    raise SystemExit(2)
lines = path.read_text(errors="replace").splitlines()
print(f"LOG_PATH {path}")
print(f"LINE_COUNT {len(lines)}")
matches = [idx for idx, line in enumerate(lines) if patterns.search(line)]
print(f"MATCH_COUNT {len(matches)}")
windows = set()
for idx in matches:
    for j in range(max(0, idx - context), min(len(lines), idx + context + 1)):
        windows.add(j)
if not windows:
    for j in range(max(0, len(lines) - 80), len(lines)):
        windows.add(j)
for idx in sorted(windows):
    line = lines[idx]
    if len(line) > width:
        line = line[:width] + f"...<truncated len={len(lines[idx])}>"
    print(f"{idx+1:08d} len={len(lines[idx])} {line}")
'
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--instance-id", required=True)
    parser.add_argument("--region", required=True)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--session", required=True)
    parser.add_argument("--context", type=int, default=6)
    parser.add_argument("--width", type=int, default=1000)
    args = parser.parse_args()

    log_path = f"/home/ubuntu/daylily-runs/{args.session}/tmux.log"
    script = (
        REMOTE_SCRIPT_TEMPLATE.replace("__LOG_PATH__", shlex.quote(log_path))
        .replace("__CONTEXT__", shlex.quote(str(args.context)))
        .replace("__WIDTH__", shlex.quote(str(args.width)))
    )
    result = run_shell(
        args.instance_id,
        args.region,
        script,
        profile=args.profile,
        as_user="ubuntu",
        comment=f"summarize tmux {args.session[:50]}",
    )
    print(result.stdout)
    if result.stderr.strip():
        print(result.stderr)
    return result.response_code


if __name__ == "__main__":
    raise SystemExit(main())
