#!/usr/bin/env python3
"""Inspect cached seqkit flags on hyb-only."""

from __future__ import annotations

import sys

from daylily_ec.aws.ssm import run_shell


ENV = "/fsx/references/runtime_assets/cached_envs/conda/4ccf662e3c47c1d194250b668a918cb0_"
SCRIPT = f"""
set -euo pipefail
env={ENV!r}
test -x "$env/bin/seqkit"
"$env/bin/seqkit" version
"$env/bin/seqkit" sample --help | sed -n '1,180p'
"""


def main() -> int:
    result = run_shell(
        "i-05374380b57fad901",
        "us-west-2",
        SCRIPT,
        profile="lsmc",
        as_user="ubuntu",
        timeout=120,
        comment="inspect seqkit sample flags",
    )
    print(result.stdout, end="")
    print(result.stderr, end="", file=sys.stderr)
    return int(result.response_code or 0)


if __name__ == "__main__":
    raise SystemExit(main())
