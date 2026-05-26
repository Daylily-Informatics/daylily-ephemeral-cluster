#!/usr/bin/env python3
"""Run a bash script on the hyb-hg003 headnode through supported Daylily SSM."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from daylily_ec.aws.ssm import resolve_headnode_instance_id, run_shell


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("script", type=Path)
    parser.add_argument("--profile", default="lsmc")
    parser.add_argument("--region", default="us-west-2")
    parser.add_argument("--cluster", default="hyb-hg003")
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--comment", default="ONT solo debug worker")
    args = parser.parse_args()

    script = args.script.read_text(encoding="utf-8")
    target = resolve_headnode_instance_id(args.cluster, args.region, profile=args.profile)
    print(f"headnode={target.instance_id}", file=sys.stderr)
    result = run_shell(
        target.instance_id,
        args.region,
        script,
        profile=args.profile,
        timeout=args.timeout,
        comment=args.comment,
    )
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, file=sys.stderr, end="")
    print(f"ssm_command_id={result.command_id}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
