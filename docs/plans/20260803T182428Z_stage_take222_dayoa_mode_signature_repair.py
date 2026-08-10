#!/usr/bin/env python3
"""Stage exact Take222 diagnostic-mode signature repair files via DYEC SSM."""

from __future__ import annotations

import base64
import gzip
import hashlib
import json
import shlex
from pathlib import Path

from daylily_ec.aws.ssm import resolve_headnode_instance_id, run_shell, write_remote_text


CLUSTER = "preval-hiomr2"
PROFILE = "lsmc"
REGION = "us-west-2"
WORKTREE = Path("/Users/jmajor/.codex/worktrees/dayoa-13.4.2-take222")
HEADNODE_CHECKOUT = Path("/fsx/analysis_results/preval-hiomr2/take222/daylily-omics-analysis")
REMOTE_ROOT = Path("/home/ubuntu/take222_stage_20260803/mode-signature-repair3")
CHUNK_CHARS = 12_000
EXPECTED_BASE_SHA256 = {
    "workflow/rules/hiomr2_truvari.smk": (
        "39487c7df5d8c26b71ea575235109ef6141d0644bc8e9d69323737c8c34c164c"
    ),
    "tests/test_hiomr2_non_hg002_diagnostics.py": (
        "935ee2a3f4e933baa3d3ce068d5c12a1aa08e122610c0ac9ba00ef1b7c56b567"
    ),
}
EXPECTED_REPAIR_SHA256 = {
    "workflow/rules/hiomr2_truvari.smk": (
        "69f3b5371b30a8597d401c3b8f4ec98ec378271e20d9714ab214cedc822f143d"
    ),
    "tests/test_hiomr2_non_hg002_diagnostics.py": (
        "92c677b739def15df2bf6fe0b15ab63ba1f8bab87d73d6801286281d530be8db"
    ),
}


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _remote(instance_id: str, command: str, comment: str) -> str:
    return run_shell(
        instance_id,
        REGION,
        command,
        profile=PROFILE,
        as_user="ubuntu",
        comment=comment,
    ).stdout


def main() -> None:
    payloads: dict[str, str] = {}
    for relative_path, expected in EXPECTED_REPAIR_SHA256.items():
        payload = (WORKTREE / relative_path).read_bytes()
        actual = _sha256(payload)
        if actual != expected:
            raise RuntimeError(
                f"local mode-signature repair hash mismatch for {relative_path}: {actual}"
            )
        payloads[relative_path] = payload.decode("utf-8")

    target = resolve_headnode_instance_id(CLUSTER, REGION, profile=PROFILE)
    verify_program = """import hashlib,json,sys
from pathlib import Path
root=Path(sys.argv[1])
for relative,expected in json.loads(sys.argv[2]).items():
    actual=hashlib.sha256((root/relative).read_bytes()).hexdigest()
    if actual != expected:
        raise SystemExit("headnode mode-signature base mismatch for "+relative+": "+actual)
    print("base-verified\t"+relative+"\t"+actual)
"""
    print(
        _remote(
            target.instance_id,
            "set -euo pipefail\npython3 -c "
            + shlex.quote(verify_program)
            + " "
            + shlex.quote(str(HEADNODE_CHECKOUT))
            + " "
            + shlex.quote(json.dumps(EXPECTED_BASE_SHA256, separators=(",", ":"))),
            "Verify Take222 mode-signature repair base hashes",
        ),
        end="",
    )

    serialized = json.dumps(payloads, separators=(",", ":")).encode("utf-8")
    archive_sha256 = _sha256(serialized)
    encoded = base64.b64encode(gzip.compress(serialized, compresslevel=9, mtime=0)).decode("ascii")
    remote_parts = []
    for index, offset in enumerate(range(0, len(encoded), CHUNK_CHARS), start=1):
        remote_path = REMOTE_ROOT / f"payload.part{index:04d}"
        result = write_remote_text(
            target.instance_id,
            REGION,
            str(remote_path),
            encoded[offset : offset + CHUNK_CHARS],
            profile=PROFILE,
            as_user="ubuntu",
        )
        remote_parts.append(str(remote_path))
        print(f"staged\t{remote_path}\t{result.command_id}")

    assemble_program = """import base64,gzip,hashlib,json,sys
from pathlib import Path
root=Path(sys.argv[1])
parts=[Path(path) for path in json.loads(sys.argv[2])]
archive_expected=sys.argv[3]
file_expected=json.loads(sys.argv[4])
serialized=gzip.decompress(base64.b64decode("".join(path.read_text(encoding="utf-8") for path in parts)))
if hashlib.sha256(serialized).hexdigest() != archive_expected:
    raise SystemExit("mode-signature repair archive hash mismatch")
payloads=json.loads(serialized.decode("utf-8"))
if set(payloads) != set(file_expected):
    raise SystemExit("mode-signature repair file-set mismatch")
for relative,content in payloads.items():
    payload=content.encode("utf-8")
    actual=hashlib.sha256(payload).hexdigest()
    if actual != file_expected[relative]:
        raise SystemExit("mode-signature repair payload mismatch for "+relative+": "+actual)
    output=root/relative
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(payload)
    print("repair-verified\t"+relative+"\t"+actual)
"""
    print(
        _remote(
            target.instance_id,
            "set -euo pipefail\npython3 -c "
            + shlex.quote(assemble_program)
            + " "
            + shlex.quote(str(REMOTE_ROOT))
            + " "
            + shlex.quote(json.dumps(remote_parts, separators=(",", ":")))
            + " "
            + shlex.quote(archive_sha256)
            + " "
            + shlex.quote(json.dumps(EXPECTED_REPAIR_SHA256, separators=(",", ":"))),
            "Assemble and verify Take222 diagnostic-mode signature repair",
        ),
        end="",
    )


if __name__ == "__main__":
    main()
