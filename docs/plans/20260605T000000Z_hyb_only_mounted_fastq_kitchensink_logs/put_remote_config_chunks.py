#!/usr/bin/env python3
"""Copy generated samples/units TSVs to the headnode in SSM-safe chunks."""

from __future__ import annotations

import argparse
import base64
import hashlib
import os
from pathlib import Path

from daylily_ec.aws.ssm import run_shell


CHUNK_SIZE = 24_000


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _remote_python(payload: str) -> str:
    return "python3 -c " + repr(payload)


def _run(instance_id: str, region: str, profile: str, script: str, comment: str) -> None:
    result = run_shell(
        instance_id,
        region,
        script,
        profile=profile,
        as_user="ubuntu",
        comment=comment,
    )
    print(f"SSM {comment}: {result.command_id} rc={result.response_code} status={result.status}")
    if result.stdout.strip():
        print(result.stdout.strip())


def put_file(
    instance_id: str,
    region: str,
    profile: str,
    local_path: Path,
    remote_path: str,
) -> None:
    local_path = local_path.expanduser().resolve()
    data = local_path.read_bytes()
    local_sha = _sha256(local_path)
    tmp_path = f"{remote_path}.tmp"
    init_script = "\n".join(
        [
            "set -euo pipefail",
            f"export DAYLILY_REMOTE_PATH={tmp_path!r}",
            _remote_python(
                "import os, pathlib; "
                "path = pathlib.Path(os.environ['DAYLILY_REMOTE_PATH']); "
                "path.parent.mkdir(parents=True, exist_ok=True); "
                "path.unlink(missing_ok=True); "
                "path.touch(mode=0o644)"
            ),
        ]
    )
    remote_name = Path(remote_path).name
    _run(instance_id, region, profile, init_script, f"cfg init {remote_name}")

    for index, offset in enumerate(range(0, len(data), CHUNK_SIZE), start=1):
        encoded = base64.b64encode(data[offset : offset + CHUNK_SIZE]).decode("ascii")
        append_script = "\n".join(
            [
                "set -euo pipefail",
                f"export DAYLILY_REMOTE_PATH={tmp_path!r}",
                f"export DAYLILY_CHUNK_B64={encoded!r}",
                _remote_python(
                    "import base64, os, pathlib; "
                    "path = pathlib.Path(os.environ['DAYLILY_REMOTE_PATH']); "
                    "path.open('ab').write(base64.b64decode(os.environ['DAYLILY_CHUNK_B64']))"
                ),
            ]
        )
        _run(
            instance_id,
            region,
            profile,
            append_script,
            f"cfg append {remote_name} {index}",
        )

    finalize_script = "\n".join(
        [
            "set -euo pipefail",
            f"tmp={tmp_path!r}",
            f"target={remote_path!r}",
            "mv -- \"$tmp\" \"$target\"",
            f"test \"$(wc -c < \"$target\")\" = {len(data)!r}",
            f"test \"$(sha256sum \"$target\" | awk '{{print $1}}')\" = {local_sha!r}",
            "ls -l -- \"$target\"",
            "sha256sum -- \"$target\"",
        ]
    )
    _run(instance_id, region, profile, finalize_script, f"cfg final {remote_name}")
    print(f"PUT {local_path} -> {remote_path} bytes={len(data)} sha256={local_sha}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--instance-id", required=True)
    parser.add_argument("--region", required=True)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--remote-dir", required=True)
    parser.add_argument("paths", nargs=2, type=Path)
    args = parser.parse_args()
    names = [path.name for path in args.paths]
    for local_path, name in zip(args.paths, names):
        put_file(
            args.instance_id,
            args.region,
            args.profile,
            local_path,
            os.path.join(args.remote_dir.rstrip("/"), name),
        )
    print(f"REMOTE_STAGE_DIR={args.remote_dir.rstrip('/')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
