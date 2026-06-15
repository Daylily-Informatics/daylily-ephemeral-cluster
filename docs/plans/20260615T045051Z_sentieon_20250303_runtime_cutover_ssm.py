#!/usr/bin/env python3
"""Verify/sync the mounted Sentieon 202503.03 runtime from a DYEC headnode."""

from __future__ import annotations

import argparse
import shlex
import sys

from daylily_ec.aws.ssm import (
    SsmCommandFailedError,
    resolve_headnode_instance_id,
    run_shell,
    wait_for_ssm_online,
)


SRC = "/fsx/references/runtime_assets/cached_envs/sentieon-genomics-202503.03"
DEST = "s3://lsmc-dayoa-references-usw2/runtime_assets/cached_envs/sentieon-genomics-202503.03/"

ACTIVE_PATHS = [
    f"{SRC}/bin/sentieon",
    f"{SRC}/bin/minimap2",
    f"{SRC}/bundles/DNAscopeMGIWGS2.1.bundle",
    f"{SRC}/bundles/DNAscopeONT2.3.bundle",
    f"{SRC}/bundles/DNAscopePacBio2.1.bundle",
    f"{SRC}/bundles/DNAscopePacBio2.3.bundle",
    f"{SRC}/bundles/HybridIlluminaONT1.1.bundle",
    f"{SRC}/bundles/HybridIlluminaONT2.0.bundle",
    f"{SRC}/bundles/HybridIlluminaPacBio1.1.bundle",
    f"{SRC}/bundles/HybridUltimaONT1.1.bundle",
    f"{SRC}/bundles/HybridUltimaPacBio1.0.bundle",
    f"{SRC}/bundles/SentieonIlluminaPangenomeRealignWGS1.0.bundle/SentieonIlluminaPangenomeRealignWGS1.0.bundle",
    f"{SRC}/bundles/SentieonIlluminaPangenomeRealignWGS1.2.bundle",
    f"{SRC}/bundles/SentieonIlluminaWGS2.2.bundle",
    f"{SRC}/bundles/SentieonUltima1.1.bundle",
    f"{SRC}/bundles/SentieonUltimaPangenomeRealignWGS1.3.bundle",
]


def _path_loop() -> str:
    quoted = " ".join(shlex.quote(path) for path in ACTIVE_PATHS)
    return f"""
missing=0
for path in {quoted}; do
  if [ -e "$path" ]; then
    stat -Lc 'PRESENT\t%n\t%F\t%s\t%Y' "$path"
  else
    echo "MISSING\t$path"
    missing=$((missing + 1))
  fi
done
echo "__MISSING_ACTIVE_PATHS__=$missing"
"""


def build_script(*, sync: bool) -> str:
    sync_block = ""
    if sync:
        sync_block = f"""
echo "__SYNC_START__"
aws s3 sync {shlex.quote(SRC + "/")} {shlex.quote(DEST)} --exact-timestamps --only-show-errors
echo "__SYNC_DONE__"
aws s3api head-object --bucket lsmc-dayoa-references-usw2 --key runtime_assets/cached_envs/sentieon-genomics-202503.03/bin/sentieon --query '{{ContentLength:ContentLength,ETag:ETag,LastModified:LastModified}}' --output json
"""

    return f"""
set -euo pipefail
echo "__USER__=$(id -un)"
echo "__HOST__=$(hostname)"
echo "__SRC__={SRC}"
echo "__DEST__={DEST}"
test -d {shlex.quote(SRC)}
find {shlex.quote(SRC)} -type f | wc -l | awk '{{print "__SOURCE_FILE_COUNT__="$1}}'
du -sk {shlex.quote(SRC)} | awk '{{print "__SOURCE_DU_KB__="$1}}'
{_path_loop()}
{sync_block}
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", default="lsmc")
    parser.add_argument("--region", default="us-west-2")
    parser.add_argument("--cluster", default="dyecX4")
    parser.add_argument("--sync", action="store_true")
    args = parser.parse_args()

    target = resolve_headnode_instance_id(args.cluster, args.region, profile=args.profile)
    wait_for_ssm_online(target.instance_id, args.region, profile=args.profile, timeout=120)
    try:
        result = run_shell(
            target.instance_id,
            args.region,
            build_script(sync=args.sync),
            profile=args.profile,
            timeout=7200 if args.sync else 300,
            comment="Sentieon 202503.03 runtime verification/sync",
        )
    except SsmCommandFailedError as exc:
        sys.stdout.write(exc.result.stdout)
        sys.stderr.write(exc.result.stderr)
        raise

    sys.stdout.write(result.stdout)
    sys.stderr.write(result.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
