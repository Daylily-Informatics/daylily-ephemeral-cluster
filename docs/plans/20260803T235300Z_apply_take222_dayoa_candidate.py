#!/usr/bin/env python3
"""Apply the exact verified DayOA 13.4.3 candidate to Take222 under its lock."""

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
ROOT = Path("/fsx/analysis_results/preval-hiomr2/take222")
REMOTE = ROOT / "daylily-omics-analysis"
LOCAL = Path("/Users/jmajor/.codex/worktrees/dayoa-13.4.2-take222")
STAGE = Path("/home/ubuntu/take222_stage_20260803/dayoa-13.4.3-final")
CHUNK_CHARS = 12_000
BASE_HASHES = {
    "daylily_omics_analysis/hiomr2_jasmine_rtg.py": "7ad0bfe04cdb616f203ac46b304f2ec807df376807398e5d19963d42f79cba94",
    "daylily_omics_analysis/hiomr2_nicu_sv.py": "265889611c72ff7d0237ff5715da0a1051b8df72fab256fc7563529677fc2e3f",
    "daylily_omics_analysis/hiomr2_truvari.py": "b998d6f101da5ba63336a8aa350fe77a2451d5cc51b5acbccd109f541ebcf18f",
    "tests/test_hiomr2_jasmine_rules.py": "d9e165bffd59dc5ac8d417c92970400f97234210377923843b362683b0c4c332",
    "tests/test_hiomr2_nicu_rules.py": "66644b80153706d1e1d1f8ec9b512fe41432bf4110c394cc74b2036b3b02783d",
    "tests/test_hiomr2_nicu_sv.py": "99a9de00b4832d33709cee103997ca302d3ff6571b8cde529ca90ba5d0646c2f",
    "tests/test_hiomr2_non_hg002_diagnostics.py": "92c677b739def15df2bf6fe0b15ab63ba1f8bab87d73d6801286281d530be8db",
    "workflow/rules/hiomr2_nicu_research.smk": "992b10dc73f9f1c59113dcc4c9239f982fb090b69f5de0dd5f4db987862c76df",
    "workflow/rules/hiomr2_truvari.smk": "69f3b5371b30a8597d401c3b8f4ec98ec378271e20d9714ab214cedc822f143d",
    "workflow/rules/multiqc_final_wgs.smk": "1c31f4e2ecc6623a17f4eff6453f8c5beba2e5de013b5bbec14a8f9bc2120978",
}


def sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def remote(instance_id: str, command: str, comment: str) -> str:
    try:
        result = run_shell(
            instance_id,
            REGION,
            command,
            profile=PROFILE,
            as_user="ubuntu",
            timeout=300,
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
    payloads = {relative: (LOCAL / relative).read_text(encoding="utf-8") for relative in BASE_HASHES}
    target_hashes = {
        relative: sha256(content.encode("utf-8")) for relative, content in payloads.items()
    }
    serialized = json.dumps(payloads, separators=(",", ":")).encode("utf-8")
    encoded = base64.b64encode(gzip.compress(serialized, compresslevel=9, mtime=0)).decode("ascii")
    target = resolve_headnode_instance_id(CLUSTER, REGION, profile=PROFILE)
    parts: list[str] = []
    for index, offset in enumerate(range(0, len(encoded), CHUNK_CHARS), start=1):
        path = STAGE / f"payload.part{index:04d}"
        result = write_remote_text(
            target.instance_id,
            REGION,
            str(path),
            encoded[offset : offset + CHUNK_CHARS],
            profile=PROFILE,
            as_user="ubuntu",
        )
        parts.append(str(path))
        print(f"staged\t{path}\t{result.command_id}")

    apply_program = """import base64,gzip,hashlib,json,sys
from pathlib import Path
root=Path(sys.argv[1])
parts=json.loads(sys.argv[2])
base=json.loads(sys.argv[3])
target=json.loads(sys.argv[4])
for relative,expected in base.items():
    actual=hashlib.sha256((root/relative).read_bytes()).hexdigest()
    if actual != expected:
        raise SystemExit(f"refusing unexpected Take222 base for {relative}: {actual}")
payloads=json.loads(gzip.decompress(base64.b64decode("".join(Path(p).read_text() for p in parts))))
if set(payloads) != set(target):
    raise SystemExit("candidate file-set mismatch")
for relative,content in payloads.items():
    actual=hashlib.sha256(content.encode()).hexdigest()
    if actual != target[relative]:
        raise SystemExit(f"candidate payload mismatch for {relative}: {actual}")
for relative,content in payloads.items():
    (root/relative).write_text(content,encoding="utf-8")
for relative,expected in target.items():
    actual=hashlib.sha256((root/relative).read_bytes()).hexdigest()
    if actual != expected:
        raise SystemExit(f"post-write mismatch for {relative}: {actual}")
    print(f"applied\\t{relative}\\t{actual}")
"""
    env = """export DAYOA_AGENT_ID=codex-take222-release-20260803
export DAYOA_AGENT_KIND=codex
export DAYOA_HUMAN_REQUESTOR='John Major'
export DAYOA_TMUX_SESSION=dayoa_take222_hg003_hg004_smn12_20260803
export DAYOA_LEDGER_PATH='/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster/docs/plans/20260803T234000Z_dayoa_13_4_3_dyec_release_slack_ledger.md'
"""
    preflight = env + f"""set -euo pipefail
test -z "$(squeue -h -u ubuntu)"
test ! -e {shlex.quote(str(ROOT / '.dayoa_agent/write.lock'))}
dyec analysis lock acquire --analysis-root {shlex.quote(str(ROOT))} --operation write --intent 'Apply exact live-proven DayOA 13.4.3 candidate after natural controller exit'
"""
    print(remote(target.instance_id, preflight, "Acquire Take222 lock for exact DayOA candidate"), end="")
    apply_command = (
        env
        + "set -euo pipefail\n"
        + f"dyec analysis guard --analysis-root {shlex.quote(str(ROOT))} --operation write --intent 'Apply exact DayOA 13.4.3 candidate files' -- "
        + "python3 -c "
        + shlex.quote(apply_program)
        + " "
        + shlex.quote(str(REMOTE))
        + " "
        + shlex.quote(json.dumps(parts, separators=(",", ":")))
        + " "
        + shlex.quote(json.dumps(BASE_HASHES, separators=(",", ":")))
        + " "
        + shlex.quote(json.dumps(target_hashes, separators=(",", ":")))
    )
    try:
        print(remote(target.instance_id, apply_command, "Apply exact Take222 DayOA candidate under guard"), end="")
    except SsmCommandFailedError:
        raise
    finally:
        release = env + f"dyec analysis lock release --analysis-root {shlex.quote(str(ROOT))}\n"
        print(remote(target.instance_id, release, "Release Take222 DayOA candidate lock"), end="")


if __name__ == "__main__":
    main()
