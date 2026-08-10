#!/usr/bin/env python3
"""Stage the exact local Take222 DayOA repair patch through DYEC SSM helpers."""

from __future__ import annotations

import base64
import gzip
import hashlib
import json
import shlex
import subprocess
from pathlib import Path

from daylily_ec.aws.ssm import resolve_headnode_instance_id, run_shell, write_remote_text


CLUSTER = "preval-hiomr2"
PROFILE = "lsmc"
REGION = "us-west-2"
EXPECTED_BASE = "53b43186f0b840a756c9151df1ff1b830033c139"
WORKTREE = Path("/Users/jmajor/.codex/worktrees/dayoa-13.4.2-take222")
REMOTE_ROOT = Path("/home/ubuntu/take222_stage_20260803")
REMOTE_PATCH = REMOTE_ROOT / "dayoa_13.4.3_nonhg002_diagnostics.patch"
CHUNK_CHARS = 12_000
TRACKED_FILES = (
    "daylily_omics_analysis/hiomr2_jasmine_rtg.py",
    "daylily_omics_analysis/hiomr2_truvari.py",
    "tests/test_hiomr2_jasmine_rules.py",
    "workflow/rules/hiomr2_truvari.smk",
    "workflow/rules/multiqc_final_wgs.smk",
)
NEW_FILES = ("tests/test_hiomr2_non_hg002_diagnostics.py",)


def _run_git(*arguments: str, accepted: tuple[int, ...] = (0,)) -> bytes:
    result = subprocess.run(
        ("git", *arguments),
        cwd=WORKTREE,
        check=False,
        capture_output=True,
    )
    if result.returncode not in accepted:
        raise RuntimeError(
            f"git {' '.join(arguments)} failed RC {result.returncode}: "
            + result.stderr.decode("utf-8", errors="replace")
        )
    return result.stdout


def build_patch() -> bytes:
    head = _run_git("rev-parse", "HEAD").decode("utf-8").strip()
    if head != EXPECTED_BASE:
        raise RuntimeError(f"unexpected Take222 DayOA base: {head}")
    patch = _run_git("diff", "--binary", "--", *TRACKED_FILES)
    for path in NEW_FILES:
        if not (WORKTREE / path).is_file():
            raise FileNotFoundError(f"required new repair file is absent: {path}")
        patch += _run_git(
            "diff",
            "--no-index",
            "--binary",
            "--",
            "/dev/null",
            path,
            accepted=(0, 1),
        )
    expected_paths = set(TRACKED_FILES + NEW_FILES)
    observed_paths = {
        line.split(" b/", 1)[1]
        for line in patch.decode("utf-8").splitlines()
        if line.startswith("diff --git a/") and " b/" in line
    }
    if observed_paths != expected_paths:
        raise RuntimeError(
            "repair patch path mismatch: "
            f"expected={sorted(expected_paths)!r} observed={sorted(observed_paths)!r}"
        )
    return patch


def main() -> None:
    patch = build_patch()
    patch_sha256 = hashlib.sha256(patch).hexdigest()
    encoded = base64.b64encode(gzip.compress(patch, compresslevel=9, mtime=0)).decode("ascii")
    chunks = [
        encoded[offset : offset + CHUNK_CHARS] for offset in range(0, len(encoded), CHUNK_CHARS)
    ]
    target = resolve_headnode_instance_id(CLUSTER, REGION, profile=PROFILE)
    stage_root = REMOTE_ROOT / f"patch-{patch_sha256[:16]}"
    remote_parts = []
    for index, chunk in enumerate(chunks, start=1):
        remote_path = stage_root / f"payload.part{index:04d}"
        result = write_remote_text(
            target.instance_id,
            REGION,
            str(remote_path),
            chunk,
            profile=PROFILE,
            as_user="ubuntu",
        )
        remote_parts.append(str(remote_path))
        print(f"staged\t{remote_path}\t{result.command_id}")

    program = """import base64,gzip,hashlib,json,sys
from pathlib import Path
parts=[Path(path) for path in json.loads(sys.argv[1])]
expected=sys.argv[2]
output=Path(sys.argv[3])
encoded="".join(path.read_text(encoding="utf-8") for path in parts)
payload=gzip.decompress(base64.b64decode(encoded))
actual=hashlib.sha256(payload).hexdigest()
if actual != expected:
    raise SystemExit("assembled repair patch hash mismatch: "+actual)
if output.exists() and hashlib.sha256(output.read_bytes()).hexdigest() != actual:
    raise SystemExit("refusing to replace mismatched repair patch: "+str(output))
output.parent.mkdir(parents=True, exist_ok=True)
output.write_bytes(payload)
print("verified\t"+str(output)+"\t"+actual+"\t"+str(len(payload)))
"""
    command = (
        "set -euo pipefail\npython3 -c "
        + shlex.quote(program)
        + " "
        + shlex.quote(json.dumps(remote_parts, separators=(",", ":")))
        + " "
        + shlex.quote(patch_sha256)
        + " "
        + shlex.quote(str(REMOTE_PATCH))
    )
    result = run_shell(
        target.instance_id,
        REGION,
        command,
        profile=PROFILE,
        as_user="ubuntu",
        comment="Assemble and verify Take222 DayOA non-HG002 repair patch",
    )
    print(result.stdout, end="")


if __name__ == "__main__":
    main()
