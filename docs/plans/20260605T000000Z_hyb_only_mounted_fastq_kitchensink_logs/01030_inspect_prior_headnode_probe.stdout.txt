#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from daylily_ec.aws.ssm import run_shell


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--instance-id", default="i-05374380b57fad901")
    parser.add_argument("--region", default="us-west-2")
    parser.add_argument("--profile", default="lsmc")
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--stdout", required=True)
    parser.add_argument("--stderr", required=True)
    parser.add_argument("--script-file")
    parser.add_argument("script", nargs="?")
    args = parser.parse_args()
    if args.script_file:
        script = Path(args.script_file).read_text()
    elif args.script:
        script = args.script
    else:
        parser.error("provide script or --script-file")

    result = run_shell(
        args.instance_id,
        args.region,
        script,
        profile=args.profile,
        as_user="ubuntu",
        timeout=args.timeout,
    )
    Path(args.stdout).write_text(result.stdout)
    Path(args.stderr).write_text(result.stderr)
    return result.response_code


if __name__ == "__main__":
    raise SystemExit(main())
