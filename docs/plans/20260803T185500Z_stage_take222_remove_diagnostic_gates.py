#!/usr/bin/env python3
"""Stage the exact Take222 diagnostic-gate removal without touching active FSx."""

from __future__ import annotations

import base64
import gzip
import hashlib
import json
import shlex
from pathlib import Path

from daylily_ec.aws.ssm import (
    SsmCommandFailedError,
    resolve_headnode_instance_id,
    run_shell,
    write_remote_text,
)


CLUSTER = "preval-hiomr2"
PROFILE = "lsmc"
REGION = "us-west-2"
DAYOA_WORKTREE = Path("/Users/jmajor/.codex/worktrees/dayoa-13.4.2-take222")
DYEC_ROOT = Path("/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster")
HEADNODE_CHECKOUT = Path(
    "/fsx/analysis_results/preval-hiomr2/take222/daylily-omics-analysis"
)
REMOTE_STAGE = Path("/home/ubuntu/take222_stage_20260803/remove-diagnostic-gates")
CHUNK_CHARS = 12_000
SOURCE_PATHS = {
    "workflow/rules/hiomr2_truvari.smk": (
        DAYOA_WORKTREE / "workflow/rules/hiomr2_truvari.smk"
    ),
    "workflow/rules/multiqc_final_wgs.smk": (
        DAYOA_WORKTREE / "workflow/rules/multiqc_final_wgs.smk"
    ),
    "tests/test_hiomr2_non_hg002_diagnostics.py": (
        DAYOA_WORKTREE / "tests/test_hiomr2_non_hg002_diagnostics.py"
    ),
    "take222_run_command_13.4.2.sh": (
        DYEC_ROOT
        / "docs/plans/20260803T173159Z_take222_hg003_hg004_na19235_na20775_fullcov_manifests"
        / "take222_run_command_13.4.2.sh"
    ),
}
EXPECTED_BASE_SHA256 = {
    "workflow/rules/hiomr2_truvari.smk": (
        "69f3b5371b30a8597d401c3b8f4ec98ec378271e20d9714ab214cedc822f143d"
    ),
    "workflow/rules/multiqc_final_wgs.smk": (
        "1c31f4e2ecc6623a17f4eff6453f8c5beba2e5de013b5bbec14a8f9bc2120978"
    ),
    "tests/test_hiomr2_non_hg002_diagnostics.py": (
        "92c677b739def15df2bf6fe0b15ab63ba1f8bab87d73d6801286281d530be8db"
    ),
    "take222_run_command_13.4.2.sh": (
        "4968edb7bd1699f50e0e5aeea14a6b12bf56568d4d48faefe2cdd5700642fd17"
    ),
}
EXPECTED_REPAIR_SHA256 = {
    "workflow/rules/hiomr2_truvari.smk": (
        "cf325fb7736d07edffd9eb5ac24b31e8ae051760e9688e2e0ec316e913c556e3"
    ),
    "workflow/rules/multiqc_final_wgs.smk": (
        "70d2d75d8f22beee200760888a05ac5d02c4db1309c9faf75b799f931d3b2157"
    ),
    "tests/test_hiomr2_non_hg002_diagnostics.py": (
        "6410c366fd8f80e6f7764fc9708685cee40a9cb51b87e6eb6f456aee14408670"
    ),
    "take222_run_command_13.4.2.sh": (
        "8bcdf42fbed7898aa48cbc3b53d596f1bab3db047706fcef420b9e72ae80ce9a"
    ),
}


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _remote(instance_id: str, command: str, comment: str) -> str:
    try:
        result = run_shell(
            instance_id,
            REGION,
            command,
            profile=PROFILE,
            as_user="ubuntu",
            comment=comment,
        )
    except SsmCommandFailedError as exc:
        if exc.result.stdout:
            print(exc.result.stdout, end="")
        if exc.result.stderr:
            print(exc.result.stderr, end="")
        raise
    return result.stdout


def main() -> None:
    payloads: dict[str, str] = {}
    for relative_path, source in SOURCE_PATHS.items():
        payload = source.read_bytes()
        actual = _sha256(payload)
        expected = EXPECTED_REPAIR_SHA256[relative_path]
        if actual != expected:
            raise RuntimeError(
                f"local diagnostic-gate removal hash mismatch for "
                f"{relative_path}: {actual}"
            )
        payloads[relative_path] = payload.decode("utf-8")

    target = resolve_headnode_instance_id(CLUSTER, REGION, profile=PROFILE)
    verify_program = """import hashlib,json,sys
from pathlib import Path
root=Path(sys.argv[1])
for relative,expected in json.loads(sys.argv[2]).items():
    actual=hashlib.sha256((root/relative).read_bytes()).hexdigest()
    if actual != expected:
        raise SystemExit("headnode diagnostic-gate base mismatch for "+relative+": "+actual)
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
            "Verify active Take222 diagnostic-gate base hashes read-only",
        ),
        end="",
    )

    serialized = json.dumps(payloads, separators=(",", ":")).encode("utf-8")
    archive_sha256 = _sha256(serialized)
    encoded = base64.b64encode(
        gzip.compress(serialized, compresslevel=9, mtime=0)
    ).decode("ascii")
    remote_parts = []
    for index, offset in enumerate(range(0, len(encoded), CHUNK_CHARS), start=1):
        remote_path = REMOTE_STAGE / f"payload.part{index:04d}"
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
    raise SystemExit("diagnostic-gate removal archive hash mismatch")
payloads=json.loads(serialized.decode("utf-8"))
if set(payloads) != set(file_expected):
    raise SystemExit("diagnostic-gate removal file-set mismatch")
for relative,content in payloads.items():
    payload=content.encode("utf-8")
    actual=hashlib.sha256(payload).hexdigest()
    if actual != file_expected[relative]:
        raise SystemExit("diagnostic-gate removal payload mismatch for "+relative+": "+actual)
    output=root/relative
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(payload)
    print("repair-verified\t"+relative+"\t"+actual)
manifest=root/"payload_manifest.json"
manifest.write_text(json.dumps({"schema":"dayoa.take222_remove_diagnostic_gates/1.0","files":file_expected},sort_keys=True,indent=2)+"\\n",encoding="utf-8")
print("manifest\t"+str(manifest))
"""
    print(
        _remote(
            target.instance_id,
            "set -euo pipefail\npython3 -c "
            + shlex.quote(assemble_program)
            + " "
            + shlex.quote(str(REMOTE_STAGE))
            + " "
            + shlex.quote(json.dumps(remote_parts, separators=(",", ":")))
            + " "
            + shlex.quote(archive_sha256)
            + " "
            + shlex.quote(json.dumps(EXPECTED_REPAIR_SHA256, separators=(",", ":"))),
            "Assemble and verify staged Take222 diagnostic-gate removal",
        ),
        end="",
    )


if __name__ == "__main__":
    main()
