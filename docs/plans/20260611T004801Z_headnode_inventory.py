#!/usr/bin/env python3
"""Read-only dyecX4 headnode inventory for the 4NA export cleanup ledger."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from daylily_ec.aws.ssm import resolve_headnode_instance_id, run_shell


REMOTE_SCRIPT = r"""
set -euo pipefail
echo "SECTION identity"
id -un
hostname
date -u +%Y-%m-%dT%H:%M:%SZ

echo "SECTION df"
df -h /fsx

echo "SECTION analysis_dirs"
if [ -d /fsx/analysis_results/ubuntu ]; then
  find /fsx/analysis_results/ubuntu -mindepth 1 -maxdepth 1 -type d -printf '%f\t%p\n' | sort
else
  echo "MISSING /fsx/analysis_results/ubuntu"
fi

echo "SECTION analysis_sizes_kib"
if [ -d /fsx/analysis_results/ubuntu ]; then
  find /fsx/analysis_results/ubuntu -mindepth 1 -maxdepth 1 -type d -print0 \
    | sort -z \
    | xargs -0 -r du -sk
fi

echo "SECTION tmux"
tmux list-sessions 2>/dev/null || true

echo "SECTION slurm"
if ! command -v squeue >/dev/null 2>&1; then
  echo "ERROR: squeue not found on PATH" >&2
  exit 70
fi
squeue -u ubuntu || true

echo "SECTION dayoa_checkouts"
if [ -d /fsx/analysis_results/ubuntu ]; then
  find /fsx/analysis_results/ubuntu -mindepth 2 -maxdepth 2 -type d -name daylily-omics-analysis -printf '%p\n' | sort
fi
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", default="lsmc")
    parser.add_argument("--region", default="us-west-2")
    parser.add_argument("--cluster", default="dyecX4")
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    target = resolve_headnode_instance_id(
        args.cluster,
        args.region,
        profile=args.profile,
    )
    result = run_shell(
        target.instance_id,
        args.region,
        REMOTE_SCRIPT,
        profile=args.profile,
        as_user="ubuntu",
        timeout=900,
        comment="dyecX4 inventory",
    )

    (output_dir / "headnode_inventory.stdout.txt").write_text(result.stdout, encoding="utf-8")
    (output_dir / "headnode_inventory.stderr.txt").write_text(result.stderr, encoding="utf-8")
    (output_dir / "headnode_inventory.result.json").write_text(
        json.dumps(
            {
                "command_id": result.command_id,
                "instance_id": result.instance_id,
                "status": result.status,
                "response_code": result.response_code,
                "cluster": args.cluster,
                "region": args.region,
                "profile": args.profile,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    print(output_dir / "headnode_inventory.stdout.txt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
