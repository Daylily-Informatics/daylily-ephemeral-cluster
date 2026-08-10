#!/usr/bin/env python3
"""Resume-safe staging for the exact Take222 payload via DYEC SSM helpers."""

from __future__ import annotations

import argparse
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
REMOTE_ROOT = "/home/ubuntu/take222_stage_20260803"
CHUNK_CHARS = 12000
BATCH_SIZE = 2
PLAN_DIR = Path(__file__).resolve().parent
MANIFEST_DIR = (
    PLAN_DIR
    / "20260803T173159Z_take222_hg003_hg004_na19235_na20775_fullcov_manifests"
)
FILE_NAMES = (
    "specimens.tsv",
    "samples.tsv",
    "libraries.tsv",
    "sequencing_inputs.tsv",
    "analysis_units.tsv",
    "analysis_unit_inputs.tsv",
    "bjuice_preval_config_receipt.json",
    "manifest_validation_receipt.json",
    "hiomr2_take222_hg003_hg004_na19235_na20775_fullcov.yaml",
    "take222_run_command_13.4.2.sh",
)
FILES = {name: MANIFEST_DIR / name for name in FILE_NAMES}
EXPECTED_SHA256 = {
    "specimens.tsv": "238c053e34c327ddafed3df8cf5c45561b33161cbfc9c83ad5c7810d0092547c",
    "samples.tsv": "361f7ed2250e6d575cbe534ad5d6a5c382fbb0bc647e1be50cd25b4dc3db5ec1",
    "libraries.tsv": "6745bd38be00db837bccda151de767a03f545305794d17139b0cc99f4bcb33e0",
    "sequencing_inputs.tsv": "bb85afec7f2ce0c0ef93b179150d475ecebf36c8162e3cc7a4e3721d4ebb26b0",
    "analysis_units.tsv": "a021e4b3c727c942b44e662bd6189de9b98a37b72a91e98e7866b1e8058d1129",
    "analysis_unit_inputs.tsv": "d4bbac9a4cbafa59de0d06b6d3a688bbff7c67ddbbdafabb5c6f963e2015e924",
    "bjuice_preval_config_receipt.json": "f8e8edc6417463f44754bfdddd1abc95f60987a5c4bc301a711a8290e1279690",
    "manifest_validation_receipt.json": "b87abf99a422a6853073a4c1a098bf9ea66aa33be7f731aeb0398f35dbfd4b4c",
    "hiomr2_take222_hg003_hg004_na19235_na20775_fullcov.yaml": "7a5def761657c5f4a9c78e51e97518382580f4811e9f1320597ecb261fbcd1e0",
    "take222_run_command_13.4.2.sh": "4968edb7bd1699f50e0e5aeea14a6b12bf56568d4d48faefe2cdd5700642fd17",
}


def digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def read_payloads() -> dict[str, str]:
    payloads: dict[str, str] = {}
    for name, path in FILES.items():
        if not path.is_file():
            raise FileNotFoundError(f"Required Take222 file is absent: {path}")
        payload = path.read_bytes()
        actual = digest(payload)
        if actual != EXPECTED_SHA256[name]:
            raise RuntimeError(f"Take222 pre-stage hash mismatch for {name}: {actual}")
        payloads[name] = payload.decode("utf-8")
    return payloads


def make_specs(
    payloads: dict[str, str],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    parts: list[dict[str, object]] = []
    files: list[dict[str, object]] = []
    for name, content in payloads.items():
        chunks = [
            content[offset : offset + CHUNK_CHARS]
            for offset in range(0, len(content), CHUNK_CHARS)
        ] or [""]
        files.append(
            {
                "name": name,
                "parts": len(chunks),
                "sha256": digest(content.encode("utf-8")),
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
        "Verify Take222 stage chunks",
    )
    states: dict[str, str] = {}
    for line in output.splitlines():
        if not line or line == "DAY-EC activated.":
            continue
        state, path = line.split("\t", 1)
        if state not in {"missing", "matching"}:
            raise RuntimeError(f"Unexpected Take222 stage probe: {line!r}")
        states[path] = state
    return states


def stage_batch(
    instance_id: str, parts: list[dict[str, object]], batch: int
) -> None:
    selected = parts[batch * BATCH_SIZE : (batch + 1) * BATCH_SIZE]
    if not selected:
        raise ValueError(f"Batch {batch} is outside the Take222 part range")
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
root.mkdir(parents=True, exist_ok=True)
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
            "Assemble Take222 stage",
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
            "Verify Take222 stage",
        ),
        end="",
    )


def compressed_stage(
    instance_id: str,
    payloads: dict[str, str],
    files: list[dict[str, object]],
) -> None:
    serialized = json.dumps(payloads, separators=(",", ":")).encode("utf-8")
    encoded = base64.b64encode(gzip.compress(serialized, compresslevel=9, mtime=0)).decode(
        "ascii"
    )
    chunks = [
        encoded[offset : offset + CHUNK_CHARS]
        for offset in range(0, len(encoded), CHUNK_CHARS)
    ]
    archive_paths = []
    for index, chunk in enumerate(chunks, start=1):
        destination = f"{REMOTE_ROOT}/archive/payload.part{index:04d}"
        result = write_remote_text(
            instance_id,
            REGION,
            destination,
            chunk,
            profile=PROFILE,
            as_user="ubuntu",
        )
        archive_paths.append(destination)
        print(f"staged\tcompressed_payload\tpart{index:04d}\t{result.command_id}")

    program = '''import base64,gzip,hashlib,json,sys
from pathlib import Path
root=Path(sys.argv[1])
parts=[Path(path) for path in json.loads(sys.argv[2])]
files=json.loads(sys.argv[3])
expected={item["name"]:item["sha256"] for item in files}
encoded="".join(path.read_text(encoding="utf-8") for path in parts)
payloads=json.loads(gzip.decompress(base64.b64decode(encoded)).decode("utf-8"))
if set(payloads) != set(expected):
    raise SystemExit("compressed payload file set mismatch")
root.mkdir(parents=True, exist_ok=True)
for name in expected:
    content=payloads[name].encode("utf-8")
    actual=hashlib.sha256(content).hexdigest()
    if actual != expected[name]:
        raise SystemExit("compressed payload hash mismatch for "+name+": "+actual)
    output=root/name
    if output.exists() and hashlib.sha256(output.read_bytes()).hexdigest() != actual:
        raise SystemExit("refusing to replace mismatched staged file: "+str(output))
    output.write_bytes(content)
    if name.endswith(".sh"):
        output.chmod(0o755)
    print("assembled\\t"+name+"\\t"+actual)
'''
    print(
        remote(
            instance_id,
            "set -euo pipefail\npython3 -c "
            + shlex.quote(program)
            + " "
            + shlex.quote(REMOTE_ROOT)
            + " "
            + shlex.quote(json.dumps(archive_paths, separators=(",", ":")))
            + " "
            + shlex.quote(json.dumps(files, separators=(",", ":"))),
            "Assemble compressed Take222 stage",
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
    action.add_argument("--compressed-stage", action="store_true")
    args = parser.parse_args()

    payloads = read_payloads()
    parts, files = make_specs(payloads)
    if args.count:
        print((len(parts) + BATCH_SIZE - 1) // BATCH_SIZE)
        return

    target = resolve_headnode_instance_id(CLUSTER, REGION, profile=PROFILE)
    if args.batch is not None:
        stage_batch(target.instance_id, parts, args.batch)
    elif args.finalize:
        finalize(target.instance_id, files)
    elif args.compressed_stage:
        compressed_stage(target.instance_id, payloads, files)
    else:
        verify(target.instance_id, files)


if __name__ == "__main__":
    main()
