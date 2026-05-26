#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys

from daylily_ec.aws.ssm import SsmCommandFailedError, run_shell


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--instance-id", default="i-07ec9d66e9a88e538")
    parser.add_argument("--region", default="us-west-2")
    parser.add_argument("--profile", default="lsmc")
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("script")
    args = parser.parse_args()

    try:
        result = run_shell(
            args.instance_id,
            args.region,
            args.script,
            profile=args.profile,
            timeout=args.timeout,
            comment="Altair reanalysis headnode check",
        )
        rc = 0
    except SsmCommandFailedError as exc:
        result = exc.result
        rc = result.response_code

    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, file=sys.stderr, end="")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
