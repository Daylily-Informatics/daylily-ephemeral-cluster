#!/usr/bin/env python3
"""Stage only the declared Take15 13.0.82 payload via DYEC SSM helpers.

The target is a fresh, named Ubuntu-home staging root.  Each chunk is checked
before it is written, and a known existing chunk is accepted only when its
digest matches.  Final files are assembled once and never overwritten.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shlex
from pathlib import Path

from daylily_ec.aws.ssm import (
    resolve_headnode_instance_id,
    run_shell,
    write_remote_text,
)


CLUSTER = "preval-hiomr2"
PROFILE = "lsmc"
REGION = "us-west-2"
REMOTE_ROOT = "/home/ubuntu/t15s_13082"
CHUNK_CHARS = 6000
BATCH_SIZE = 2
PLAN_DIR = Path(__file__).resolve().parent
MANIFEST_DIR = PLAN_DIR / "20260729T141400Z_take15_hg003_na23687_hiomr2_manifests"
FILES = {
    "specimens.tsv": MANIFEST_DIR / "specimens.tsv",
    "samples.tsv": MANIFEST_DIR / "samples.tsv",
    "libraries.tsv": MANIFEST_DIR / "libraries.tsv",
    "sequencing_inputs.tsv": MANIFEST_DIR / "sequencing_inputs.tsv",
    "analysis_units.tsv": MANIFEST_DIR / "analysis_units.tsv",
    "analysis_unit_inputs.tsv": MANIFEST_DIR / "analysis_unit_inputs.tsv",
    "bjuice_preval_config_receipt.json": MANIFEST_DIR
    / "bjuice_preval_config_receipt.json",
    "hiomr2_take15_hg003_na23687_fullcov.yaml": PLAN_DIR
    / "20260729T141400Z_take15_hg003_na23687_hiomr2_overlay.yaml",
    "ledger.md": PLAN_DIR
    / "20260729T173700Z_take15_hg003_na23687_hiomr2_13082_execution_ledger.md",
}
EXPECTED_STATIC_SHA256 = {
    "specimens.tsv": "d3ffea1551f338aaf635f73f01127db0616eadc3b78a626b636f231a56bd6a60",
    "samples.tsv": "ae662279f16e04cc093b2fbc515c9b0e79003a765903d1d31a62f773937e8f95",
    "libraries.tsv": "381ba5aec7a758bd15c480cc6ddf143e2e01efaefc722f02e51b6384688c6fbd",
    "sequencing_inputs.tsv": "c1d5d2d533735b3d92f5f5a69ad7c64930df6b67cbd4a83a65d4eb7d0cfc8667",
    "analysis_units.tsv": "ac945e104b62f4e381c9460b9dbd4942416c88f1d135d20d297db7a764016b09",
    "analysis_unit_inputs.tsv": "28406e29d9efd1093ce34ac61f6816b4cc63b9f63c50bb36d520f22addb0f213",
    "bjuice_preval_config_receipt.json": "cc227ea921f95615e8f911f837ad92ca0861e5b7f64b6edab66ddfb5357b412e",
    "hiomr2_take15_hg003_na23687_fullcov.yaml": "c06ab2df7fa7f26c33620ea13d0d45a92717e85c5c4e911e7c9332021577f238",
}


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def payloads() -> dict[str, str]:
    result: dict[str, str] = {}
    for name, path in FILES.items():
        if not path.is_file():
            raise FileNotFoundError(f"Required staging input is absent: {path}")
        result[name] = path.read_text(encoding="utf-8")
    for name, expected in EXPECTED_STATIC_SHA256.items():
        actual = digest(result[name])
        if actual != expected:
            raise RuntimeError(f"Pre-stage hash mismatch for {name}: {actual}")
    return result


def specifications(contents: dict[str, str]) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    parts: list[dict[str, object]] = []
    files: list[dict[str, object]] = []
    for name, content in contents.items():
        chunks = [content[offset : offset + CHUNK_CHARS] for offset in range(0, len(content), CHUNK_CHARS)] or [""]
        files.append({"name": name, "parts": len(chunks), "sha256": digest(content)})
        parts.extend(
            {
                "name": name,
                "index": index,
                "content": chunk,
                "sha256": digest(chunk),
            }
            for index, chunk in enumerate(chunks, start=1)
        )
    return parts, files


def shell(instance_id: str, script: str, comment: str) -> str:
    return run_shell(
        instance_id,
        REGION,
        script,
        profile=PROFILE,
        as_user="ubuntu",
        comment=comment,
    ).stdout


def inspect_or_prepare(instance_id: str, prepare: bool) -> None:
    quoted = shlex.quote(REMOTE_ROOT)
    if prepare:
        script = "\n".join(
            [
                "set -euo pipefail",
                f"if [ -e {quoted} ]; then",
                f"  echo 'Refusing to reuse existing staging root: {REMOTE_ROOT}' >&2",
                "  exit 64",
                "fi",
                f"mkdir -p {quoted}/chunks",
                f"printf 'prepared\\t%s\\n' {quoted}",
            ]
        )
        print(shell(instance_id, script, "Prepare fresh Take15 13.0.82 staging"), end="")
        return
    script = "\n".join(
        [
            "set -euo pipefail",
            f"if [ -e {quoted} ]; then printf 'present\\t%s\\n' {quoted}; else printf 'absent\\t%s\\n' {quoted}; fi",
        ]
    )
    print(shell(instance_id, script, "Inspect Take15 13.0.82 staging path"), end="")


def part_state(instance_id: str, selected: list[dict[str, object]]) -> dict[str, str]:
    checks = [
        {
            "path": f"{REMOTE_ROOT}/chunks/{part['name']}.part{int(part['index']):04d}",
            "sha256": str(part["sha256"]),
        }
        for part in selected
    ]
    probe = """import hashlib, json, sys
from pathlib import Path
for spec in json.loads(sys.argv[1]):
    path = Path(spec["path"])
    if not path.exists():
        print("missing\\t" + str(path))
        continue
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != spec["sha256"]:
        raise SystemExit(f"Staged chunk hash mismatch for {path}: {actual}")
    print("matching\\t" + str(path))
"""
    script = "set -euo pipefail\npython3 -c " + shlex.quote(probe) + " " + shlex.quote(json.dumps(checks, separators=(",", ":")))
    output = shell(instance_id, script, "Check Take15 13.0.82 staging chunks")
    states: dict[str, str] = {}
    for line in output.splitlines():
        if not line or line == "DAY-EC activated.":
            continue
        state, path = line.split("\t", 1)
        if state not in {"missing", "matching"}:
            raise RuntimeError(f"Unexpected staging state: {line!r}")
        states[path] = state
    expected = {check["path"] for check in checks}
    if set(states) != expected:
        raise RuntimeError(f"Incomplete staging state: expected={expected!r}, got={states!r}")
    return states


def stage_batch(instance_id: str, parts: list[dict[str, object]], batch: int) -> None:
    start = batch * BATCH_SIZE
    if batch < 0 or start >= len(parts):
        raise ValueError(f"Batch must be between 0 and {(len(parts) - 1) // BATCH_SIZE}")
    selected = parts[start : start + BATCH_SIZE]
    states = part_state(instance_id, selected)
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


def report_status(instance_id: str, parts: list[dict[str, object]]) -> None:
    for start in range(0, len(parts), BATCH_SIZE):
        selected = parts[start : start + BATCH_SIZE]
        states = part_state(instance_id, selected)
        for part in selected:
            name = str(part["name"])
            index = int(part["index"])
            remote_path = f"{REMOTE_ROOT}/chunks/{name}.part{index:04d}"
            print(f"{states[remote_path]}\\t{name}\\tpart{index:04d}")


def finalize(instance_id: str, files: list[dict[str, object]]) -> None:
    rebuild = """import hashlib, json, sys
from pathlib import Path
root = Path(sys.argv[1])
for spec in json.loads(sys.argv[2]):
    output = root / spec["name"]
    if output.exists():
        actual = hashlib.sha256(output.read_bytes()).hexdigest()
        if actual != spec["sha256"]:
            raise SystemExit(f"Refusing to replace mismatched staged file: {output}: {actual}")
        print(f"{spec['name']}\t{output.stat().st_size}\t{actual}\tpreserved")
        continue
    inputs = [root / "chunks" / f"{spec['name']}.part{index:04d}" for index in range(1, int(spec["parts"]) + 1)]
    missing = [str(path) for path in inputs if not path.exists()]
    if missing:
        raise SystemExit("Missing staged chunks: " + ", ".join(missing))
    payload = b"".join(path.read_bytes() for path in inputs)
    actual = hashlib.sha256(payload).hexdigest()
    if actual != spec["sha256"]:
        raise SystemExit(f"Hash mismatch after assembly for {spec['name']}: {actual}")
    output.write_bytes(payload)
    print(f"{spec['name']}\\t{len(payload)}\\t{actual}")
"""
    script = "set -euo pipefail\npython3 -c " + shlex.quote(rebuild) + " " + shlex.quote(REMOTE_ROOT) + " " + shlex.quote(json.dumps(files, separators=(",", ":")))
    print(shell(instance_id, script, "Assemble Take15 13.0.82 staging payload"), end="")


def main() -> None:
    parser = argparse.ArgumentParser()
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--inspect", action="store_true")
    action.add_argument("--prepare", action="store_true")
    action.add_argument("--batch", type=int)
    action.add_argument("--status", action="store_true")
    action.add_argument("--finalize", action="store_true")
    args = parser.parse_args()
    contents = payloads()
    parts, files = specifications(contents)
    headnode = resolve_headnode_instance_id(CLUSTER, REGION, profile=PROFILE)
    if args.inspect:
        inspect_or_prepare(headnode.instance_id, prepare=False)
    elif args.prepare:
        inspect_or_prepare(headnode.instance_id, prepare=True)
    elif args.batch is not None:
        stage_batch(headnode.instance_id, parts, args.batch)
    elif args.status:
        report_status(headnode.instance_id, parts)
    else:
        finalize(headnode.instance_id, files)


if __name__ == "__main__":
    main()
