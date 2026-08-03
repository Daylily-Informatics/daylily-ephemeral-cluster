#!/usr/bin/env python3
"""Resume-safe staging for the exact Take101 payload via DYEC SSM helpers."""

from __future__ import annotations

import argparse
import hashlib
import json
import shlex
from pathlib import Path

from daylily_ec.aws.ssm import resolve_headnode_instance_id, run_shell, write_remote_text


CLUSTER = "preval-hiomr2"
PROFILE = "lsmc"
REGION = "us-west-2"
REMOTE_ROOT = "/home/ubuntu/t101s_1341_2304"
CHUNK_CHARS = 12000
BATCH_SIZE = 2
PLAN_DIR = Path(__file__).resolve().parent
MANIFEST_DIR = PLAN_DIR / "20260802T221250Z_take101_hg002_na23687_fullcov_manifests"
FILES = {
    name: MANIFEST_DIR / name
    for name in (
        "specimens.tsv",
        "samples.tsv",
        "libraries.tsv",
        "sequencing_inputs.tsv",
        "analysis_units.tsv",
        "analysis_unit_inputs.tsv",
        "bjuice_preval_config_receipt.json",
        "manifest_validation_receipt.json",
        "hiomr2_take101_hg002_na23687_fullcov.yaml",
        "take101_run_command.sh",
    )
}
FILES["hiomr2_take101_hg002_na23687_fullcov_v2.yaml"] = FILES.pop(
    "hiomr2_take101_hg002_na23687_fullcov.yaml"
)
EXPECTED_SHA256 = {
    "specimens.tsv": "da22e23cff11bd55f2885a8850993324a1efc927607f3bea7153b7da7db5f6de",
    "samples.tsv": "b673dba16ec9d28723a99ef492c3307f1ad55c5e20b644e7d7772361b8322f76",
    "libraries.tsv": "4e835d2f80eb69a54f82cc8c4cefe1dbd97639116038295514ac728e7830768a",
    "sequencing_inputs.tsv": "b128e3576635c9bc6a545c416ef9cc806fe3228e08aaaecc3269ff34560431ec",
    "analysis_units.tsv": "a709bca2cd36252d4df3f12bc921196c52de0dd368d92547c0a68204e7941620",
    "analysis_unit_inputs.tsv": "2ffd5038920b40d05b5766518b6a069985de85d53ad1287cef7a3ab57949b1eb",
    "bjuice_preval_config_receipt.json": "8aa479f2903026d79116f1ff94047b134ab2e5723f2284fe0424fee731a151c7",
    "manifest_validation_receipt.json": "d3f823d71ec14edccec755f21d161826a032aea9029de9808ef3f6e82335e800",
    "hiomr2_take101_hg002_na23687_fullcov_v2.yaml": "2b204bae7f87e1057a421dfaa79f7729a514c0306804978513b42efb7caf23f5",
    "take101_run_command.sh": "bf5e85d77d1f0b54d25e820e546cdf7ffbb4fae210d01f738eb6906b7d558a23",
}


def digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def read_payloads() -> dict[str, str]:
    payloads: dict[str, str] = {}
    for name, path in FILES.items():
        if not path.is_file():
            raise FileNotFoundError(f"Required Take101 file is absent: {path}")
        payload = path.read_bytes()
        actual = digest(payload)
        if actual != EXPECTED_SHA256[name]:
            raise RuntimeError(f"Take101 pre-stage hash mismatch for {name}: {actual}")
        payloads[name] = payload.decode("utf-8")
    return payloads


def make_specs(
    payloads: dict[str, str],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    parts: list[dict[str, object]] = []
    files: list[dict[str, object]] = []
    for name, text in payloads.items():
        chunks = [
            text[offset : offset + CHUNK_CHARS]
            for offset in range(0, len(text), CHUNK_CHARS)
        ] or [""]
        files.append(
            {
                "name": name,
                "parts": len(chunks),
                "sha256": digest(text.encode("utf-8")),
            }
        )
        for index, chunk in enumerate(chunks, start=1):
            parts.append(
                {
                    "name": name,
                    "index": index,
                    "content": chunk,
                    "sha256": digest(chunk.encode("utf-8")),
                }
            )
    return parts, files


def remote(instance_id: str, command: str, comment: str) -> str:
    return run_shell(
        instance_id,
        REGION,
        command,
        profile=PROFILE,
        as_user="ubuntu",
        comment=comment,
    ).stdout


def part_states(
    instance_id: str, selected: list[dict[str, object]]
) -> dict[str, str]:
    expected = [
        {
            "path": f"{REMOTE_ROOT}/chunks/{part['name']}.part{int(part['index']):04d}",
            "sha256": str(part["sha256"]),
        }
        for part in selected
    ]
    program = '''import hashlib,json,sys
from pathlib import Path
for item in json.loads(sys.argv[1]):
    path=Path(item["path"])
    if not path.exists():
        print("missing\\t"+str(path))
        continue
    actual=hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != item["sha256"]:
        raise SystemExit("staged chunk hash mismatch for "+str(path)+": "+actual)
    print("matching\\t"+str(path))
'''
    output = remote(
        instance_id,
        "set -euo pipefail\npython3 -c "
        + shlex.quote(program)
        + " "
        + shlex.quote(json.dumps(expected, separators=(",", ":"))),
        "Verify Take101 stage chunks",
    )
    states: dict[str, str] = {}
    for line in output.splitlines():
        if not line or line == "DAY-EC activated.":
            continue
        state, path = line.split("\t", 1)
        if state not in {"missing", "matching"}:
            raise RuntimeError(f"Unexpected Take101 stage probe: {line!r}")
        states[path] = state
    return states


def stage_batch(
    instance_id: str, parts: list[dict[str, object]], batch: int
) -> None:
    selected = parts[batch * BATCH_SIZE : (batch + 1) * BATCH_SIZE]
    if not selected:
        raise ValueError(f"Batch {batch} is outside the Take101 part range")
    states = part_states(instance_id, selected)
    for part in selected:
        name = str(part["name"])
        index = int(part["index"])
        destination = f"{REMOTE_ROOT}/chunks/{name}.part{index:04d}"
        if states.get(destination) == "matching":
            print(f"verified\t{name}\tpart{index:04d}")
            continue
        result = write_remote_text(
            instance_id,
            REGION,
            destination,
            str(part["content"]),
            profile=PROFILE,
            as_user="ubuntu",
        )
        print(f"staged\t{name}\tpart{index:04d}\t{result.command_id}")


def finalize(instance_id: str, files: list[dict[str, object]]) -> None:
    program = '''import hashlib,json,sys
from pathlib import Path
root=Path(sys.argv[1])
for item in json.loads(sys.argv[2]):
    output=root/item["name"]
    if output.exists():
        actual=hashlib.sha256(output.read_bytes()).hexdigest()
        if actual != item["sha256"]:
            raise SystemExit("refusing to replace mismatched staged file: "+str(output))
        print(item["name"]+"\\t"+actual+"\\tpreserved")
        continue
    inputs=[root/"chunks"/f"{item['name']}.part{index:04d}" for index in range(1, int(item["parts"])+1)]
    missing=[str(path) for path in inputs if not path.exists()]
    if missing:
        raise SystemExit("missing staged chunks: "+", ".join(missing))
    content=b"".join(path.read_bytes() for path in inputs)
    actual=hashlib.sha256(content).hexdigest()
    if actual != item["sha256"]:
        raise SystemExit("assembled hash mismatch for "+item["name"]+": "+actual)
    output.write_bytes(content)
    print(item["name"]+"\\t"+actual)
'''
    print(
        remote(
            instance_id,
            "set -euo pipefail\npython3 -c "
            + shlex.quote(program)
            + " "
            + shlex.quote(REMOTE_ROOT)
            + " "
            + shlex.quote(json.dumps(files, separators=(",", ":"))),
            "Assemble Take101 stage",
        ),
        end="",
    )


def verify(instance_id: str, files: list[dict[str, object]]) -> None:
    program = '''import hashlib,json,sys
from pathlib import Path
root=Path(sys.argv[1])
for item in json.loads(sys.argv[2]):
    path=root/item["name"]
    if not path.is_file():
        raise SystemExit("missing staged file: "+str(path))
    actual=hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != item["sha256"]:
        raise SystemExit("staged file hash mismatch for "+str(path)+": "+actual)
    print("verified\\t"+item["name"]+"\\t"+actual)
'''
    print(
        remote(
            instance_id,
            "set -euo pipefail\npython3 -c "
            + shlex.quote(program)
            + " "
            + shlex.quote(REMOTE_ROOT)
            + " "
            + shlex.quote(json.dumps(files, separators=(",", ":"))),
            "Verify Take101 stage",
        ),
        end="",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--batch", type=int)
    action.add_argument("--count", action="store_true")
    action.add_argument("--finalize", action="store_true")
    action.add_argument("--verify", action="store_true")
    args = parser.parse_args()

    parts, files = make_specs(read_payloads())
    if args.count:
        print(len(parts))
        return

    target = resolve_headnode_instance_id(CLUSTER, REGION, profile=PROFILE)
    if args.batch is not None:
        stage_batch(target.instance_id, parts, args.batch)
    elif args.finalize:
        finalize(target.instance_id, files)
    else:
        verify(target.instance_id, files)


if __name__ == "__main__":
    main()
