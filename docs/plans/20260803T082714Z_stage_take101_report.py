#!/usr/bin/env python3
"""Stage and install the verified Take101 report bundle under its FSx root."""

from __future__ import annotations

import hashlib
import json
import shlex
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from daylily_ec.aws.ssm import resolve_headnode_instance_id, run_shell, write_remote_text


CLUSTER = "preval-hiomr2"
PROFILE = "lsmc"
REGION = "us-west-2"
ANALYSIS_ROOT = "/fsx/analysis_results/preval-hiomr2/take101"
REPORT_DIR = Path(__file__).resolve().parent / "20260803T082714Z_take101_export_take222_report"
REMOTE_STAGE = "/home/ubuntu/t101r_085604"
CHUNK_CHARS = 15000
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
    if not REPORT_DIR.is_dir():
        raise FileNotFoundError(REPORT_DIR)
    files = sorted(path for path in REPORT_DIR.iterdir() if path.is_file())
    if not files:
        raise RuntimeError("Take101 report bundle is empty")

    specs: list[dict[str, object]] = []
    chunks: list[tuple[str, str]] = []
    for file_index, path in enumerate(files, start=1):
        content = path.read_text(encoding="utf-8")
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        parts = [content[offset : offset + CHUNK_CHARS] for offset in range(0, len(content), CHUNK_CHARS)] or [""]
        chunk_key = f"f{file_index:03d}"
        specs.append({"name": path.name, "chunk_key": chunk_key, "parts": len(parts), "bytes": len(content.encode("utf-8")), "sha256": digest})
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
                f"if [ -e {shlex.quote(REMOTE_STAGE)} ]; then echo 'report staging root already exists' >&2; exit 64; fi",
                f"mkdir -p {shlex.quote(REMOTE_STAGE)}/chunks",
            ]
        ),
        profile=PROFILE,
        as_user="ubuntu",
        comment="Prepare Take101 report staging",
    )

    def write_chunk(item: tuple[str, str]) -> None:
        remote_path, content = item
        write_remote_text(
            target.instance_id,
            REGION,
            remote_path,
            content,
            profile=PROFILE,
            as_user="ubuntu",
        )

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(write_chunk, chunks))

    assemble = """import hashlib, json, sys
from pathlib import Path
root = Path(sys.argv[1])
for spec in json.loads(sys.argv[2]):
    target = root / spec["name"]
    if target.exists():
        raise SystemExit(f"Refusing to overwrite staged file: {target}")
    payload = b"".join(
        (root / "chunks" / f"{spec['chunk_key']}.p{index:04d}").read_bytes()
        for index in range(1, int(spec["parts"]) + 1)
    )
    actual = hashlib.sha256(payload).hexdigest()
    if len(payload) != int(spec["bytes"]) or actual != spec["sha256"]:
        raise SystemExit(f"Staging verification failed for {spec['name']}: {len(payload)} {actual}")
    target.write_bytes(payload)
    print(f"STAGED\t{spec['name']}\t{len(payload)}\t{actual}")
"""
    run_shell(
        target.instance_id,
        REGION,
        "set -euo pipefail\npython3 -c "
        + shlex.quote(assemble)
        + " "
        + shlex.quote(REMOTE_STAGE)
        + " "
        + shlex.quote(json.dumps(specs, separators=(",", ":"))),
        profile=PROFILE,
        as_user="ubuntu",
        comment="Assemble Take101 report staging",
    )

    lock_script = "\n".join(
        [
            "set -euo pipefail",
            *env_exports(),
            f"dyec analysis visit --analysis-root {shlex.quote(ANALYSIS_ROOT)} --mode write --intent 'Install verified Take101 technical report before full-root export'",
            f"dyec analysis lock acquire --analysis-root {shlex.quote(ANALYSIS_ROOT)} --operation write --intent 'Install verified Take101 technical report before full-root export'",
        ]
    )
    run_shell(
        target.instance_id,
        REGION,
        lock_script,
        profile=PROFILE,
        as_user="ubuntu",
        comment="Acquire Take101 report-install lock",
    )

    install = """import hashlib, json, sys
from pathlib import Path
source = Path(sys.argv[1])
destination = Path(sys.argv[2])
for spec in json.loads(sys.argv[3]):
    src = source / spec["name"]
    dst = destination / spec["name"]
    if dst.exists():
        raise SystemExit(f"Refusing to overwrite analysis artifact: {dst}")
    payload = src.read_bytes()
    actual = hashlib.sha256(payload).hexdigest()
    if len(payload) != int(spec["bytes"]) or actual != spec["sha256"]:
        raise SystemExit(f"Pre-install verification failed for {spec['name']}: {len(payload)} {actual}")
    dst.write_bytes(payload)
    dst.chmod(0o644)
    final = dst.read_bytes()
    final_sha = hashlib.sha256(final).hexdigest()
    if len(final) != int(spec["bytes"]) or final_sha != spec["sha256"]:
        raise SystemExit(f"Post-install verification failed for {spec['name']}: {len(final)} {final_sha}")
    print(f"INSTALLED\t{spec['name']}\t{len(final)}\t{final_sha}")
"""
    install_command = (
        "python3 -c "
        + shlex.quote(install)
        + " "
        + shlex.quote(REMOTE_STAGE)
        + " "
        + shlex.quote(ANALYSIS_ROOT)
        + " "
        + shlex.quote(json.dumps(specs, separators=(",", ":")))
    )
    guarded_script = "\n".join(
        [
            "set -euo pipefail",
            *env_exports(),
            f"dyec analysis guard --analysis-root {shlex.quote(ANALYSIS_ROOT)} --operation write --intent 'Install verified Take101 technical report before full-root export' -- {install_command}",
        ]
    )
    try:
        result = run_shell(
            target.instance_id,
            REGION,
            guarded_script,
            profile=PROFILE,
            as_user="ubuntu",
            timeout=600,
            poll_interval=2,
            comment="Install Take101 technical report",
        )
        print(result.stdout)
    finally:
        release_script = "\n".join(
            [
                "set -euo pipefail",
                *env_exports(),
                f"dyec analysis lock release --analysis-root {shlex.quote(ANALYSIS_ROOT)}",
            ]
        )
        run_shell(
            target.instance_id,
            REGION,
            release_script,
            profile=PROFILE,
            as_user="ubuntu",
            comment="Release Take101 report-install lock",
        )


if __name__ == "__main__":
    main()
