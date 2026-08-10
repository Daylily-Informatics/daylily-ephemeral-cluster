#!/usr/bin/env python3
"""Stage the generated remaining-BJuice six-manifest set on the headnode."""

from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import shlex
from pathlib import Path

from daylily_ec.aws.ssm import resolve_headnode_instance_id, run_shell, write_remote_text


CLUSTER = "preval-hiomr2"
PROFILE = "lsmc"
REGION = "us-west-2"
REMOTE_DIR = Path("/home/ubuntu/remaining-bjuice-1345-manifests")
NAMES = (
    "specimens",
    "samples",
    "libraries",
    "sequencing_inputs",
    "analysis_units",
    "analysis_unit_inputs",
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest_dir", type=Path)
    args = parser.parse_args()
    target = resolve_headnode_instance_id(CLUSTER, REGION, profile=PROFILE)
    for name in NAMES:
        source = args.manifest_dir / f"{name}.tsv"
        content = source.read_text(encoding="utf-8")
        remote = REMOTE_DIR / source.name
        if len(content.encode()) <= 60_000:
            result = write_remote_text(
                target.instance_id,
                REGION,
                str(remote),
                content,
                profile=PROFILE,
                as_user="ubuntu",
            )
        else:
            encoded = base64.b64encode(
                gzip.compress(content.encode("utf-8"), mtime=0)
            ).decode("ascii")
            encoded_remote = remote.with_suffix(remote.suffix + ".gz.b64")
            result = write_remote_text(
                target.instance_id,
                REGION,
                str(encoded_remote),
                encoded,
                profile=PROFILE,
                as_user="ubuntu",
            )
            expected_hash = hashlib.sha256(content.encode()).hexdigest()
            temporary = remote.with_suffix(remote.suffix + ".partial")
            command = (
                "set -euo pipefail\n"
                f"base64 -d {shlex.quote(str(encoded_remote))} | gzip -dc > "
                f"{shlex.quote(str(temporary))}\n"
                f"test \"$(sha256sum {shlex.quote(str(temporary))} | awk '{{print $1}}')\" "
                f"= {shlex.quote(expected_hash)}\n"
                f"mv {shlex.quote(str(temporary))} {shlex.quote(str(remote))}\n"
                f"rm -f {shlex.quote(str(encoded_remote))}\n"
            )
            run_shell(
                target.instance_id,
                REGION,
                command,
                profile=PROFILE,
                as_user="ubuntu",
                timeout=300,
                comment=f"Materialize staged {source.name}",
            )
        print(f"staged\t{source.name}\t{result.command_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
