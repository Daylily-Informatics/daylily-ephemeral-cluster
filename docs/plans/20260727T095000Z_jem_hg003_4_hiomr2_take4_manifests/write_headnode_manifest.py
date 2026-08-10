"""Copy one validated manifest through the prescribed DYEC SSM text helper."""

from __future__ import annotations

import argparse
import base64
import gzip
from pathlib import Path
import shlex

from daylily_ec.aws.ssm import run_shell


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gzip", action="store_true")
    parser.add_argument("local_path", type=Path)
    parser.add_argument("remote_path")
    args = parser.parse_args()
    content = args.local_path.read_bytes()
    if args.gzip:
        content = gzip.compress(content)
    encoded = base64.b64encode(content).decode("ascii")
    remote_writer = (
        "import base64, gzip, os, pathlib; "
        "path = pathlib.Path(os.environ['DAYLILY_REMOTE_PATH']); "
        "path.parent.mkdir(parents=True, exist_ok=True); "
        "payload = base64.b64decode(os.environ['DAYLILY_REMOTE_B64']); "
        + ("payload = gzip.decompress(payload); " if args.gzip else "")
        + "path.write_bytes(payload)"
    )
    script = "\n".join(
        [
            "set -euo pipefail",
            f"export DAYLILY_REMOTE_B64={shlex.quote(encoded)}",
            f"export DAYLILY_REMOTE_PATH={shlex.quote(args.remote_path)}",
            f"python3 -c {shlex.quote(remote_writer)}",
        ]
    )
    result = run_shell(
        "i-0b70541bdad454c76",
        "us-west-2",
        script,
        profile="lsmc",
        as_user="ubuntu",
        comment="Write validated DayOA manifest",
    )
    print(result.command_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
