#!/usr/bin/env python3
"""Stage exact NICU no-HG002 repair files through the supported SSM helpers."""

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
REMOTE_ROOT = Path("/home/ubuntu/take222_stage_20260803/nicu-nohg002-repair2")
CHUNK_CHARS = 12_000
EXPECTED_BASE_SHA256 = {
    "daylily_omics_analysis/hiomr2_nicu_sv.py": (
        "d066093f28413d1d9c2ede4c222573a2eff9f6453b6868d30840ef94b1087ed5"
    ),
    "workflow/rules/hiomr2_nicu_research.smk": (
        "4102702020f974572eceebaeaa22a4c65cae01e3d3d052ed1deb50358fb45d3d"
    ),
    "tests/test_hiomr2_nicu_rules.py": (
        "bd82037dded004eb31c60a2ac5fd5ff7cfed7b4045b082921f145a020d4f9f60"
    ),
    "tests/test_hiomr2_nicu_sv.py": (
        "316ff9546a23726508e877628996e5e593606ac717ef1cf3a8495ab92465471c"
    ),
}
EXPECTED_REPAIR_SHA256 = {
    "daylily_omics_analysis/hiomr2_nicu_sv.py": (
        "265889611c72ff7d0237ff5715da0a1051b8df72fab256fc7563529677fc2e3f"
    ),
    "workflow/rules/hiomr2_nicu_research.smk": (
        "992b10dc73f9f1c59113dcc4c9239f982fb090b69f5de0dd5f4db987862c76df"
    ),
    "tests/test_hiomr2_nicu_rules.py": (
        "66644b80153706d1e1d1f8ec9b512fe41432bf4110c394cc74b2036b3b02783d"
    ),
    "tests/test_hiomr2_nicu_sv.py": (
        "99a9de00b4832d33709cee103997ca302d3ff6571b8cde529ca90ba5d0646c2f"
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
            raise RuntimeError(f"local NICU repair hash mismatch for {relative_path}: {actual}")
        payloads[relative_path] = payload.decode("utf-8")

    target = resolve_headnode_instance_id(CLUSTER, REGION, profile=PROFILE)
    verify_program = """import hashlib,json,sys
from pathlib import Path
root=Path(sys.argv[1])
for relative,expected in json.loads(sys.argv[2]).items():
    path=root/relative
    actual=hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected:
        raise SystemExit("headnode base hash mismatch for "+relative+": "+actual)
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
            "Verify Take222 NICU repair base hashes",
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
    raise SystemExit("NICU repair archive hash mismatch")
payloads=json.loads(serialized.decode("utf-8"))
if set(payloads) != set(file_expected):
    raise SystemExit("NICU repair file-set mismatch")
for relative,content in payloads.items():
    payload=content.encode("utf-8")
    actual=hashlib.sha256(payload).hexdigest()
    if actual != file_expected[relative]:
        raise SystemExit("NICU repair payload hash mismatch for "+relative+": "+actual)
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
            "Assemble and verify Take222 NICU no-HG002 repair files",
        ),
        end="",
    )


if __name__ == "__main__":
    main()
