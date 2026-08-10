#!/usr/bin/env python3
"""Stage the declared Take15 13.0.87 payload through DYEC SSM text helpers."""

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
REMOTE_ROOT = "/home/ubuntu/t15s_13087"
CHUNK_CHARS = 6000
BATCH_SIZE = 2
PLAN_DIR = Path(__file__).resolve().parent
MANIFEST_DIR = PLAN_DIR / "20260730T082141Z_take15_hg003_na23687_13087_manifests"
LEDGER = PLAN_DIR / "20260730T082141Z_take15_hg003_na23687_13087_execution_ledger.md"
FILES = {
    "specimens.tsv": MANIFEST_DIR / "specimens.tsv",
    "samples.tsv": MANIFEST_DIR / "samples.tsv",
    "libraries.tsv": MANIFEST_DIR / "libraries.tsv",
    "sequencing_inputs.tsv": MANIFEST_DIR / "sequencing_inputs.tsv",
    "analysis_units.tsv": MANIFEST_DIR / "analysis_units.tsv",
    "analysis_unit_inputs.tsv": MANIFEST_DIR / "analysis_unit_inputs.tsv",
    "bjuice_preval_config_receipt.json": MANIFEST_DIR / "bjuice_preval_config_receipt.json",
    "manifest_validation_receipt.json": MANIFEST_DIR / "manifest_validation_receipt.json",
    "hiomr2_take15_hg003_na23687_fullcov.yaml": MANIFEST_DIR
    / "hiomr2_take15_hg003_na23687_fullcov.yaml",
    "take15_13087_execution_ledger.md": LEDGER,
}
EXPECTED_SHA256 = {
    "specimens.tsv": "d3ffea1551f338aaf635f73f01127db0616eadc3b78a626b636f231a56bd6a60",
    "samples.tsv": "ae662279f16e04cc093b2fbc515c9b0e79003a765903d1d31a62f773937e8f95",
    "libraries.tsv": "381ba5aec7a758bd15c480cc6ddf143e2e01efaefc722f02e51b6384688c6fbd",
    "sequencing_inputs.tsv": "c1d5d2d533735b3d92f5f5a69ad7c64930df6b67cbd4a83a65d4eb7d0cfc8667",
    "analysis_units.tsv": "ac945e104b62f4e381c9460b9dbd4942416c88f1d135d20d297db7a764016b09",
    "analysis_unit_inputs.tsv": "28406e29d9efd1093ce34ac61f6816b4cc63b9f63c50bb36d520f22addb0f213",
    "bjuice_preval_config_receipt.json": "2442b4a130615ab5e9725d05543039b72d291a02314821fe54fc474124de4df4",
    "manifest_validation_receipt.json": "007d8f30fc5e2f602963825bdc5c5b8e17bd0972e602caac0c3fef04ba3066c4",
    "hiomr2_take15_hg003_na23687_fullcov.yaml": "c06ab2df7fa7f26c33620ea13d0d45a92717e85c5c4e911e7c9332021577f238",
}


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def read_payload() -> dict[str, str]:
    payload: dict[str, str] = {}
    for name, path in FILES.items():
        if not path.is_file():
            raise FileNotFoundError(f"required staging source is absent: {path}")
        payload[name] = path.read_text(encoding="utf-8")
    for name, expected in EXPECTED_SHA256.items():
        actual = sha256_text(payload[name])
        if actual != expected:
            raise RuntimeError(f"pre-stage hash mismatch for {name}: {actual}")
    return payload


def make_specs(payload: dict[str, str]) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    parts: list[dict[str, object]] = []
    files: list[dict[str, object]] = []
    for name, content in payload.items():
        chunks = [content[i : i + CHUNK_CHARS] for i in range(0, len(content), CHUNK_CHARS)] or [""]
        files.append({"name": name, "parts": len(chunks), "sha256": sha256_text(content)})
        for index, chunk in enumerate(chunks, start=1):
            parts.append({"name": name, "index": index, "content": chunk, "sha256": sha256_text(chunk)})
    return parts, files


def run(instance_id: str, command: str, comment: str) -> str:
    return run_shell(
        instance_id,
        REGION,
        command,
        profile=PROFILE,
        as_user="ubuntu",
        comment=comment,
    ).stdout


def inspect_or_prepare(instance_id: str, prepare: bool) -> None:
    root = shlex.quote(REMOTE_ROOT)
    if prepare:
        command = "\n".join(
            [
                "set -euo pipefail",
                f"test ! -e {root}",
                f"mkdir -p {root}/chunks",
                f"printf 'prepared\\t%s\\n' {root}",
            ]
        )
        print(run(instance_id, command, "Prepare fresh Take15 13.0.87 stage"), end="")
        return
    command = "\n".join(
        [
            "set -euo pipefail",
            f"if test -e {root}; then printf 'present\\t%s\\n' {root}; else printf 'absent\\t%s\\n' {root}; fi",
        ]
    )
    print(run(instance_id, command, "Inspect Take15 13.0.87 stage"), end="")


def part_states(instance_id: str, selected: list[dict[str, object]]) -> dict[str, str]:
    checks = [
        {
            "path": f"{REMOTE_ROOT}/chunks/{part['name']}.part{int(part['index']):04d}",
            "sha256": str(part["sha256"]),
        }
        for part in selected
    ]
    program = """import hashlib,json,sys
from pathlib import Path
for item in json.loads(sys.argv[1]):
    path=Path(item['path'])
    if not path.exists():
        print('missing\\t'+str(path))
        continue
    actual=hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != item['sha256']:
        raise SystemExit('staged chunk hash mismatch for '+str(path)+': '+actual)
    print('matching\\t'+str(path))
"""
    command = "set -euo pipefail\npython3 -c " + shlex.quote(program) + " " + shlex.quote(json.dumps(checks, separators=(",", ":")))
    output = run(instance_id, command, "Verify Take15 13.0.87 stage chunks")
    result: dict[str, str] = {}
    for line in output.splitlines():
        if not line or line == "DAY-EC activated.":
            continue
        state, path = line.split("\t", 1)
        if state not in {"missing", "matching"}:
            raise RuntimeError(f"unexpected stage state: {line!r}")
        result[path] = state
    if set(result) != {item["path"] for item in checks}:
        raise RuntimeError("stage probe did not return every requested chunk")
    return result


def stage_batch(instance_id: str, parts: list[dict[str, object]], batch: int) -> None:
    start = batch * BATCH_SIZE
    selected = parts[start : start + BATCH_SIZE]
    if not selected:
        raise ValueError(f"batch must be between 0 and {(len(parts) - 1) // BATCH_SIZE}")
    states = part_states(instance_id, selected)
    for part in selected:
        name = str(part["name"])
        index = int(part["index"])
        remote_path = f"{REMOTE_ROOT}/chunks/{name}.part{index:04d}"
        if states[remote_path] == "matching":
            print(f"verified\\t{name}\\tpart{index:04d}")
            continue
        result = write_remote_text(
            instance_id,
            REGION,
            remote_path,
            str(part["content"]),
            profile=PROFILE,
            as_user="ubuntu",
        )
        print(f"staged\\t{name}\\tpart{index:04d}\\t{result.command_id}")


def finalize(instance_id: str, files: list[dict[str, object]]) -> None:
    program = """import hashlib,json,sys
from pathlib import Path
root=Path(sys.argv[1])
for item in json.loads(sys.argv[2]):
    output=root/item['name']
    if output.exists():
        actual=hashlib.sha256(output.read_bytes()).hexdigest()
        if actual != item['sha256']:
            raise SystemExit('refusing to replace mismatched staged file: '+str(output)+': '+actual)
        print(item['name']+'\\t'+actual+'\\tpreserved')
        continue
    inputs=[root/'chunks'/f"{item['name']}.part{index:04d}" for index in range(1, int(item['parts'])+1)]
    missing=[str(path) for path in inputs if not path.exists()]
    if missing:
        raise SystemExit('missing staged chunks: '+', '.join(missing))
    payload=b''.join(path.read_bytes() for path in inputs)
    actual=hashlib.sha256(payload).hexdigest()
    if actual != item['sha256']:
        raise SystemExit('hash mismatch after assembly for '+item['name']+': '+actual)
    output.write_bytes(payload)
    print(item['name']+'\\t'+actual)
"""
    command = "set -euo pipefail\npython3 -c " + shlex.quote(program) + " " + shlex.quote(REMOTE_ROOT) + " " + shlex.quote(json.dumps(files, separators=(",", ":")))
    print(run(instance_id, command, "Assemble Take15 13.0.87 stage"), end="")


def main() -> None:
    parser = argparse.ArgumentParser()
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--inspect", action="store_true")
    action.add_argument("--prepare", action="store_true")
    action.add_argument("--batch", type=int)
    action.add_argument("--finalize", action="store_true")
    action.add_argument("--count", action="store_true")
    args = parser.parse_args()
    payload = read_payload()
    parts, files = make_specs(payload)
    if args.count:
        print(len(parts))
        return
    headnode = resolve_headnode_instance_id(CLUSTER, REGION, profile=PROFILE)
    if args.inspect:
        inspect_or_prepare(headnode.instance_id, prepare=False)
    elif args.prepare:
        inspect_or_prepare(headnode.instance_id, prepare=True)
    elif args.batch is not None:
        stage_batch(headnode.instance_id, parts, args.batch)
    else:
        finalize(headnode.instance_id, files)


if __name__ == "__main__":
    main()
