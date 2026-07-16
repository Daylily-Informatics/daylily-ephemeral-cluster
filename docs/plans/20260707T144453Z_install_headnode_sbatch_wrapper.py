#!/usr/bin/env python3
"""Install the patched budget-aware sbatch wrapper on the live catalog headnode."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import shlex
from pathlib import Path

from daylily_ec.aws.ssm import resolve_headnode_instance_id, run_shell


REPO_ROOT = Path(__file__).resolve().parents[2]
WRAPPER_PATH = REPO_ROOT / "config" / "day_cluster" / "sbatch"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cluster", default="cmdcat-103-all-20260707")
    parser.add_argument("--region", default="us-west-2")
    parser.add_argument("--profile", default="lsmc")
    parser.add_argument("--remote-user", default="ubuntu")
    parser.add_argument("--target", default="/opt/slurm/bin/sbatch")
    args = parser.parse_args()

    wrapper = WRAPPER_PATH.read_bytes()
    expected_sha = hashlib.sha256(wrapper).hexdigest()
    encoded = base64.b64encode(wrapper).decode("ascii")
    target = resolve_headnode_instance_id(args.cluster, args.region, profile=args.profile)
    remote_tmp = "/tmp/daylily-sbatch-wrapper-patched"
    script = "\n".join(
        [
            "set -euo pipefail",
            f"export DAYLILY_SBATCH_B64={shlex.quote(encoded)}",
            f"export DAYLILY_SBATCH_TMP={shlex.quote(remote_tmp)}",
            "python3 -c "
            + shlex.quote(
                "import base64, os, pathlib; "
                "path = pathlib.Path(os.environ['DAYLILY_SBATCH_TMP']); "
                "path.write_bytes(base64.b64decode(os.environ['DAYLILY_SBATCH_B64']))"
            ),
            f"sudo install -m 0755 -o root -g root {shlex.quote(remote_tmp)} {shlex.quote(args.target)}",
            f"rm -f {shlex.quote(remote_tmp)}",
            f"actual_sha=$(sha256sum {shlex.quote(args.target)} | awk '{{print $1}}')",
            f"test \"$actual_sha\" = {shlex.quote(expected_sha)}",
            f"ls -l {shlex.quote(args.target)}",
            "printf 'installed_sha256=%s\\n' \"$actual_sha\"",
        ]
    )
    result = run_shell(
        target.instance_id,
        args.region,
        script,
        profile=args.profile,
        as_user=args.remote_user,
        timeout=180,
        comment="Install patched Daylily sbatch wrapper",
    )
    print(
        json.dumps(
            {
                "cluster": args.cluster,
                "instance_id": target.instance_id,
                "target": args.target,
                "expected_sha256": expected_sha,
                "ssm_command_id": result.command_id,
                "stdout": result.stdout.strip(),
                "stderr": result.stderr.strip(),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
