#!/usr/bin/env python3
"""Atomically update the four regenerated Take101 report files on FSx."""

from __future__ import annotations

import hashlib
import json
import shlex
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from daylily_ec.aws.ssm import resolve_headnode_instance_id, run_shell, write_remote_text


PROFILE = "lsmc"
REGION = "us-west-2"
CLUSTER = "preval-hiomr2"
ANALYSIS_ROOT = "/fsx/analysis_results/preval-hiomr2/take101"
REMOTE_STAGE = "/home/ubuntu/t101r2_090639"
REPORT_DIR = Path(__file__).resolve().parent / "20260803T082714Z_take101_export_take222_report"
CHUNK_CHARS = 15000
EXPECTED_OLD = {
    "TAKE101_COVERAGE_FRAGMENT_STATS.tsv": "bb2e2424e107f61f1493918cb747115725f95f77b50de7b992a0efc91aae7f5e",
    "TAKE101_HG002_NA23687_FULLCOV_HIOMR2_13.4.2_VALIDATION_REPORT.artifact.json": "a08cccce8b1e81409af8ec030ea2eadf35d89223b93b0f6ade4c86bf56e057fc",
    "TAKE101_HG002_NA23687_FULLCOV_HIOMR2_13.4.2_VALIDATION_REPORT.html": "1f69900a5c00766c52c820a075da4290cdffdc57a602a63477903c44d9f71e97",
    "TAKE101_REPORT_DELIVERY_RECEIPT.json": "3d1c039f0e24c1f586517d869dfe4795c02e64da8718c01e8e0a65a9706ca55d",
}
ENV = {
    "DAYOA_AGENT_ID": "codex-take101-export-take222-20260803",
    "DAYOA_AGENT_KIND": "codex",
    "DAYOA_HUMAN_REQUESTOR": "John Major",
    "DAYOA_TMUX_SESSION": "dayoa_take222_hg003_hg004_smn12_20260803",
    "DAYOA_LEDGER_PATH": "/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster/docs/plans/20260803T082714Z_take101_export_take222_fullcov_ledger.md",
}


def env_exports() -> list[str]:
    return [f"export {key}={shlex.quote(value)}" for key, value in ENV.items()]


def main() -> None:
    specs = []
    chunks = []
    for file_index, (name, old_sha) in enumerate(sorted(EXPECTED_OLD.items()), start=1):
        path = REPORT_DIR / name
        payload = path.read_text(encoding="utf-8")
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        parts = [payload[offset : offset + CHUNK_CHARS] for offset in range(0, len(payload), CHUNK_CHARS)] or [""]
        chunk_key = f"f{file_index:03d}"
        specs.append(
            {
                "name": name,
                "old_sha256": old_sha,
                "new_sha256": digest,
                "bytes": len(payload.encode("utf-8")),
                "parts": len(parts),
                "chunk_key": chunk_key,
            }
        )
        chunks.extend(
            (f"{REMOTE_STAGE}/chunks/{chunk_key}.p{index:04d}", part)
            for index, part in enumerate(parts, start=1)
        )

    target = resolve_headnode_instance_id(CLUSTER, REGION, profile=PROFILE)
    run_shell(
        target.instance_id,
        REGION,
        "\n".join(
            [
                "set -euo pipefail",
                f"if [ -e {shlex.quote(REMOTE_STAGE)} ]; then echo 'update staging root already exists' >&2; exit 64; fi",
                f"mkdir -p {shlex.quote(REMOTE_STAGE)}/chunks",
            ]
        ),
        profile=PROFILE,
        as_user="ubuntu",
        comment="Prepare Take101 report update staging",
    )

    def write_chunk(item: tuple[str, str]) -> None:
        remote_path, content = item
        write_remote_text(target.instance_id, REGION, remote_path, content, profile=PROFILE, as_user="ubuntu")

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(write_chunk, chunks))

    assemble = """import hashlib, json, sys
from pathlib import Path
root = Path(sys.argv[1])
for spec in json.loads(sys.argv[2]):
    payload = b"".join(
        (root / "chunks" / f"{spec['chunk_key']}.p{index:04d}").read_bytes()
        for index in range(1, int(spec["parts"]) + 1)
    )
    actual = hashlib.sha256(payload).hexdigest()
    if len(payload) != int(spec["bytes"]) or actual != spec["new_sha256"]:
        raise SystemExit(f"Staging verification failed for {spec['name']}: {len(payload)} {actual}")
    (root / spec["name"]).write_bytes(payload)
"""
    run_shell(
        target.instance_id,
        REGION,
        "set -euo pipefail\npython3 -c " + shlex.quote(assemble) + " " + shlex.quote(REMOTE_STAGE) + " " + shlex.quote(json.dumps(specs, separators=(",", ":"))),
        profile=PROFILE,
        as_user="ubuntu",
        comment="Assemble Take101 report update",
    )

    acquire = "\n".join(
        [
            "set -euo pipefail",
            *env_exports(),
            f"dyec analysis visit --analysis-root {shlex.quote(ANALYSIS_ROOT)} --mode write --intent 'Atomically update verified Take101 report files before export'",
            f"dyec analysis lock acquire --analysis-root {shlex.quote(ANALYSIS_ROOT)} --operation write --intent 'Atomically update verified Take101 report files before export'",
        ]
    )
    run_shell(target.instance_id, REGION, acquire, profile=PROFILE, as_user="ubuntu", comment="Acquire Take101 report update lock")

    update = """import hashlib, json, os, sys
from pathlib import Path
source = Path(sys.argv[1])
destination = Path(sys.argv[2])
specs = json.loads(sys.argv[3])
for spec in specs:
    dst = destination / spec["name"]
    if not dst.is_file():
        raise SystemExit(f"Required existing report file is absent: {dst}")
    old_payload = dst.read_bytes()
    old_sha = hashlib.sha256(old_payload).hexdigest()
    if old_sha != spec["old_sha256"]:
        raise SystemExit(f"Existing report hash mismatch for {spec['name']}: {old_sha}")
for spec in specs:
    src = source / spec["name"]
    payload = src.read_bytes()
    new_sha = hashlib.sha256(payload).hexdigest()
    if len(payload) != int(spec["bytes"]) or new_sha != spec["new_sha256"]:
        raise SystemExit(f"New report hash mismatch for {spec['name']}: {len(payload)} {new_sha}")
    dst = destination / spec["name"]
    temporary = destination / f".{spec['name']}.codex-update"
    if temporary.exists():
        raise SystemExit(f"Refusing to reuse temporary path: {temporary}")
    temporary.write_bytes(payload)
    temporary.chmod(0o644)
    os.replace(temporary, dst)
    final = dst.read_bytes()
    final_sha = hashlib.sha256(final).hexdigest()
    if len(final) != int(spec["bytes"]) or final_sha != spec["new_sha256"]:
        raise SystemExit(f"Post-update verification failed for {spec['name']}: {len(final)} {final_sha}")
    print(f"UPDATED\t{spec['name']}\t{len(final)}\t{final_sha}")
"""
    command = "python3 -c " + shlex.quote(update) + " " + shlex.quote(REMOTE_STAGE) + " " + shlex.quote(ANALYSIS_ROOT) + " " + shlex.quote(json.dumps(specs, separators=(",", ":")))
    guarded = "\n".join(
        [
            "set -euo pipefail",
            *env_exports(),
            f"dyec analysis guard --analysis-root {shlex.quote(ANALYSIS_ROOT)} --operation write --intent 'Atomically update verified Take101 report files before export' -- {command}",
        ]
    )
    try:
        result = run_shell(target.instance_id, REGION, guarded, profile=PROFILE, as_user="ubuntu", timeout=600, poll_interval=2, comment="Update Take101 report files")
        print(result.stdout)
    finally:
        release = "\n".join(["set -euo pipefail", *env_exports(), f"dyec analysis lock release --analysis-root {shlex.quote(ANALYSIS_ROOT)}"])
        run_shell(target.instance_id, REGION, release, profile=PROFILE, as_user="ubuntu", comment="Release Take101 report update lock")


if __name__ == "__main__":
    main()
