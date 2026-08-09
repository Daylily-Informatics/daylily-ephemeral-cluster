#!/usr/bin/env python3
"""Install the already verified Take101 report staging root under FSx."""

from __future__ import annotations

import hashlib
import json
import shlex
from pathlib import Path

from daylily_ec.aws.ssm import resolve_headnode_instance_id, run_shell


CLUSTER = "preval-hiomr2"
PROFILE = "lsmc"
REGION = "us-west-2"
ANALYSIS_ROOT = "/fsx/analysis_results/preval-hiomr2/take101"
REMOTE_STAGE = "/home/ubuntu/t101r_085604"
REPORT_DIR = Path(__file__).resolve().parent / "20260803T082714Z_take101_export_take222_report"
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
    for path in sorted(item for item in REPORT_DIR.iterdir() if item.is_file()):
        payload = path.read_bytes()
        specs.append({"name": path.name, "bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()})

    target = resolve_headnode_instance_id(CLUSTER, REGION, profile=PROFILE)
    acquire = "\n".join(
        [
            "set -euo pipefail",
            *env_exports(),
            f"dyec analysis visit --analysis-root {shlex.quote(ANALYSIS_ROOT)} --mode write --intent 'Install verified Take101 technical report before full-root export'",
            f"dyec analysis lock acquire --analysis-root {shlex.quote(ANALYSIS_ROOT)} --operation write --intent 'Install verified Take101 technical report before full-root export'",
        ]
    )
    run_shell(target.instance_id, REGION, acquire, profile=PROFILE, as_user="ubuntu", comment="Acquire Take101 report lock retry")

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
        raise SystemExit(f"Staging verification failed for {spec['name']}: {len(payload)} {actual}")
    dst.write_bytes(payload)
    dst.chmod(0o644)
    final = dst.read_bytes()
    final_sha = hashlib.sha256(final).hexdigest()
    if len(final) != int(spec["bytes"]) or final_sha != spec["sha256"]:
        raise SystemExit(f"Post-install verification failed for {spec['name']}: {len(final)} {final_sha}")
    print(f"INSTALLED\t{spec['name']}\t{len(final)}\t{final_sha}")
"""
    command = (
        "python3 -c "
        + shlex.quote(install)
        + " "
        + shlex.quote(REMOTE_STAGE)
        + " "
        + shlex.quote(ANALYSIS_ROOT)
        + " "
        + shlex.quote(json.dumps(specs, separators=(",", ":")))
    )
    guarded = "\n".join(
        [
            "set -euo pipefail",
            *env_exports(),
            f"dyec analysis guard --analysis-root {shlex.quote(ANALYSIS_ROOT)} --operation write --intent 'Install verified Take101 technical report before full-root export' -- {command}",
        ]
    )
    try:
        result = run_shell(
            target.instance_id,
            REGION,
            guarded,
            profile=PROFILE,
            as_user="ubuntu",
            timeout=600,
            poll_interval=2,
            comment="Install Take101 report retry",
        )
        print(result.stdout)
    finally:
        release = "\n".join(
            [
                "set -euo pipefail",
                *env_exports(),
                f"dyec analysis lock release --analysis-root {shlex.quote(ANALYSIS_ROOT)}",
            ]
        )
        run_shell(target.instance_id, REGION, release, profile=PROFILE, as_user="ubuntu", comment="Release Take101 report lock retry")


if __name__ == "__main__":
    main()
