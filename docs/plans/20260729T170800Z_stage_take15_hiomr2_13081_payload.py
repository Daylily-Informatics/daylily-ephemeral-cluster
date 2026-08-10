#!/usr/bin/env python3
"""Stage the explicit Take15 13.0.81 payload through DYEC SSM text helpers.

The outer local terminal is bounded, so this helper stages exactly one declared
text chunk per invocation. It never discovers an alternate staging root and
never overwrites an existing chunk: a known existing chunk must hash-match
before it is accepted.
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
REMOTE_ROOT = "/home/ubuntu/t15s_13081b"
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
    "bjuice_preval_config_receipt.json": MANIFEST_DIR / "bjuice_preval_config_receipt.json",
    "hiomr2_take15_hg003_na23687_fullcov.yaml": PLAN_DIR
    / "20260729T141400Z_take15_hg003_na23687_hiomr2_overlay.yaml",
    "ledger.md": PLAN_DIR
    / "20260729T170800Z_take15_hg003_na23687_hiomr2_13081_execution_ledger.md",
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


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_payloads() -> dict[str, str]:
    payloads: dict[str, str] = {}
    for name, path in FILES.items():
        if not path.is_file():
            raise FileNotFoundError(f"Required Take15 staging file is absent: {path}")
        payloads[name] = path.read_text(encoding="utf-8")
    for name, expected in EXPECTED_STATIC_SHA256.items():
        actual = sha256_text(payloads[name])
        if actual != expected:
            raise RuntimeError(f"Pre-stage hash mismatch for {name}: {actual}")
    return payloads


def prepare_stage_root(instance_id: str) -> None:
    result = run_shell(
        instance_id,
        REGION,
        "\n".join(
            [
                "set -euo pipefail",
                f"if [ -e {shlex.quote(REMOTE_ROOT)} ] && [ ! -d {shlex.quote(REMOTE_ROOT)} ]; then",
                f"  echo 'Staging path is not a directory: {REMOTE_ROOT}' >&2",
                "  exit 64",
                "fi",
                f"if [ -d {shlex.quote(REMOTE_ROOT)} ] && [ ! -d {shlex.quote(REMOTE_ROOT)}/chunks ]; then",
                f"  echo 'Staging root has no chunks directory: {REMOTE_ROOT}' >&2",
                "  exit 64",
                "fi",
                f"mkdir -p {shlex.quote(REMOTE_ROOT)}/chunks",
            ]
        ),
        profile=PROFILE,
        as_user="ubuntu",
        comment="Prepare Take15 13.0.81 staging",
    )
    print(f"prepared\t{result.command_id}", flush=True)


def remote_part_matches(instance_id: str, remote_path: str, expected_sha256: str) -> bool:
    probe = """import hashlib, sys
from pathlib import Path
path = Path(sys.argv[1])
expected = sys.argv[2]
if not path.exists():
    print("missing")
    raise SystemExit(0)
actual = hashlib.sha256(path.read_bytes()).hexdigest()
if actual != expected:
    raise SystemExit(f"Staged part hash mismatch for {path}: {actual}")
print("matching")
"""
    result = run_shell(
        instance_id,
        REGION,
        "set -euo pipefail\n"
        + "python3 -c "
        + shlex.quote(probe)
        + " "
        + shlex.quote(remote_path)
        + " "
        + shlex.quote(expected_sha256),
        profile=PROFILE,
        as_user="ubuntu",
        comment="Check Take15 staging part",
    )
    state = result.stdout.strip()
    if state == "matching":
        return True
    if state == "missing":
        return False
    raise RuntimeError(f"Unexpected stage-part probe output for {remote_path}: {state!r}")


def remote_batch_states(
    instance_id: str, checks: list[dict[str, str]]
) -> dict[str, str]:
    probe = """import hashlib, json, sys
from pathlib import Path
for spec in json.loads(sys.argv[1]):
    path = Path(spec["path"])
    if not path.exists():
        print(f"missing\\t{path}")
        continue
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != spec["sha256"]:
        raise SystemExit(f"Staged part hash mismatch for {path}: {actual}")
    print(f"matching\\t{path}")
"""
    script = "\n".join(
        [
            "set -euo pipefail",
            f"if [ -e {shlex.quote(REMOTE_ROOT)} ] && [ ! -d {shlex.quote(REMOTE_ROOT)} ]; then",
            f"  echo 'Staging path is not a directory: {REMOTE_ROOT}' >&2",
            "  exit 64",
            "fi",
            f"if [ -d {shlex.quote(REMOTE_ROOT)} ] && [ ! -d {shlex.quote(REMOTE_ROOT)}/chunks ]; then",
            f"  echo 'Staging root has no chunks directory: {REMOTE_ROOT}' >&2",
            "  exit 64",
            "fi",
            f"mkdir -p {shlex.quote(REMOTE_ROOT)}/chunks",
            "python3 -c "
            + shlex.quote(probe)
            + " "
            + shlex.quote(json.dumps(checks, separators=(",", ":"))),
        ]
    )
    result = run_shell(
        instance_id,
        REGION,
        script,
        profile=PROFILE,
        as_user="ubuntu",
        comment="Check Take15 staging batch",
    )
    states: dict[str, str] = {}
    for line in result.stdout.splitlines():
        if not line.strip() or line.strip() == "DAY-EC activated.":
            continue
        if "\t" not in line:
            raise RuntimeError(f"Unexpected raw stage state output: {result.stdout!r}")
        state, path = line.split("\t", 1)
        if state not in {"matching", "missing"}:
            raise RuntimeError(f"Unexpected stage-part state: {line!r}")
        states[path] = state
    expected_paths = {item["path"] for item in checks}
    if set(states) != expected_paths:
        raise RuntimeError(
            f"Incomplete stage-part state response: expected={expected_paths!r}, got={states!r}"
        )
    return states


def build_specs(payloads: dict[str, str]) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    parts: list[dict[str, object]] = []
    files: list[dict[str, object]] = []
    for name, content in payloads.items():
        chunks = [
            content[offset : offset + CHUNK_CHARS]
            for offset in range(0, len(content), CHUNK_CHARS)
        ]
        if not chunks:
            chunks = [""]
        files.append({"name": name, "parts": len(chunks), "sha256": sha256_text(content)})
        for index, chunk in enumerate(chunks, start=1):
            parts.append(
                {
                    "name": name,
                    "index": index,
                    "content": chunk,
                    "sha256": sha256_text(chunk),
                }
            )
    return parts, files


def assemble_stage(instance_id: str, specs: list[dict[str, object]]) -> None:
    rebuild = """import hashlib, json, sys
from pathlib import Path
root = Path(sys.argv[1])
for spec in json.loads(sys.argv[2]):
    output = root / spec[\"name\"]
    if output.exists():
        raise SystemExit(f\"Refusing to overwrite staged file: {output}\")
    payload = b\"\".join(
        (root / \"chunks\" / f\"{spec['name']}.part{index:04d}\").read_bytes()
        for index in range(1, int(spec[\"parts\"]) + 1)
    )
    output.write_bytes(payload)
    actual = hashlib.sha256(payload).hexdigest()
    if actual != spec[\"sha256\"]:
        raise SystemExit(f\"Hash mismatch after staging for {spec['name']}: {actual}\")
    print(f\"{spec['name']}\\t{len(payload)}\\t{actual}\")
"""
    result = run_shell(
        instance_id,
        REGION,
        "set -euo pipefail\n"
        + "python3 -c "
        + shlex.quote(rebuild)
        + " "
        + shlex.quote(REMOTE_ROOT)
        + " "
        + shlex.quote(json.dumps(specs, separators=(",", ":"))),
        profile=PROFILE,
        as_user="ubuntu",
        comment="Assemble Take15 13.0.81 staging",
    )
    print(result.stdout, end="", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--batch", type=int)
    action.add_argument("--status", action="store_true")
    action.add_argument("--finalize", action="store_true")
    args = parser.parse_args()

    payloads = load_payloads()
    parts, specs = build_specs(payloads)
    headnode = resolve_headnode_instance_id(CLUSTER, REGION, profile=PROFILE)

    if args.finalize:
        assemble_stage(headnode.instance_id, specs)
        return

    if args.status:
        checks = [
            {
                "path": f"{REMOTE_ROOT}/chunks/{part['name']}.part{int(part['index']):04d}",
                "sha256": str(part["sha256"]),
            }
            for part in parts
        ]
        states = remote_batch_states(headnode.instance_id, checks)
        for part, check in zip(parts, checks, strict=True):
            print(
                f"{states[check['path']]}\t{part['name']}\tpart{int(part['index']):04d}",
                flush=True,
            )
        return

    batch = int(args.batch)
    start = batch * BATCH_SIZE
    if batch < 0 or start >= len(parts):
        max_batch = (len(parts) - 1) // BATCH_SIZE
        raise ValueError(f"Batch must be between 0 and {max_batch}")
    batch_parts = parts[start : start + BATCH_SIZE]
    checks = [
        {
            "path": f"{REMOTE_ROOT}/chunks/{part['name']}.part{int(part['index']):04d}",
            "sha256": str(part["sha256"]),
        }
        for part in batch_parts
    ]
    states = remote_batch_states(headnode.instance_id, checks)

    for part, check in zip(batch_parts, checks, strict=True):
        name = str(part["name"])
        index = int(part["index"])
        content = str(part["content"])
        remote_path = check["path"]
        if states[remote_path] == "matching":
            print(f"verified\t{name}\tpart{index:04d}", flush=True)
            continue
        result = write_remote_text(
            headnode.instance_id,
            REGION,
            remote_path,
            content,
            profile=PROFILE,
            as_user="ubuntu",
        )
        print(f"staged\t{name}\tpart{index:04d}\t{result.command_id}", flush=True)


if __name__ == "__main__":
    main()
