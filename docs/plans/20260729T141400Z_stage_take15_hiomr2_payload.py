#!/usr/bin/env python3
"""Stage the explicit Take15 manifests through the DYEC SSM text helpers.

The sequencing-input manifest exceeds one SSM command document.  This helper
uses only ``write_remote_text`` for transport, in fixed-size text chunks, then
uses the paired ``run_shell`` helper to assemble and hash-check the exact files
in Ubuntu home.  It never discovers inputs or starts a workflow controller.
"""

from __future__ import annotations

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
REMOTE_ROOT = "/home/ubuntu/t15s_1420"
CHUNK_CHARS = 12000
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
    "ledger.md": PLAN_DIR / "20260729T141400Z_take15_hg003_na23687_hiomr2_execution_ledger.md",
}
EXPECTED_MANIFEST_SHA256 = {
    "specimens.tsv": "d3ffea1551f338aaf635f73f01127db0616eadc3b78a626b636f231a56bd6a60",
    "samples.tsv": "ae662279f16e04cc093b2fbc515c9b0e79003a765903d1d31a62f773937e8f95",
    "libraries.tsv": "381ba5aec7a758bd15c480cc6ddf143e2e01efaefc722f02e51b6384688c6fbd",
    "sequencing_inputs.tsv": "c1d5d2d533735b3d92f5f5a69ad7c64930df6b67cbd4a83a65d4eb7d0cfc8667",
    "analysis_units.tsv": "ac945e104b62f4e381c9460b9dbd4942416c88f1d135d20d297db7a764016b09",
    "analysis_unit_inputs.tsv": "28406e29d9efd1093ce34ac61f6816b4cc63b9f63c50bb36d520f22addb0f213",
}


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def main() -> None:
    payloads: dict[str, str] = {}
    for name, path in FILES.items():
        if not path.is_file():
            raise FileNotFoundError(f"Required Take15 staging file is absent: {path}")
        payloads[name] = path.read_text(encoding="utf-8")
    for name, expected in EXPECTED_MANIFEST_SHA256.items():
        actual = sha256_text(payloads[name])
        if actual != expected:
            raise RuntimeError(f"Manifest hash mismatch before staging for {name}: {actual}")

    target = resolve_headnode_instance_id(CLUSTER, REGION, profile=PROFILE)
    run_shell(
        target.instance_id,
        REGION,
        "\n".join(
            [
                "set -euo pipefail",
                f"if [ -e {shlex.quote(REMOTE_ROOT)} ]; then",
                f"  echo 'Refusing to overwrite existing staging root {REMOTE_ROOT}' >&2",
                "  exit 64",
                "fi",
                f"mkdir -p {shlex.quote(REMOTE_ROOT)}/chunks",
            ]
        ),
        profile=PROFILE,
        as_user="ubuntu",
        comment="Prepare Take15 staging",
    )

    specs: list[dict[str, object]] = []
    for name, content in payloads.items():
        chunks = [content[offset : offset + CHUNK_CHARS] for offset in range(0, len(content), CHUNK_CHARS)]
        if not chunks:
            chunks = [""]
        for index, chunk in enumerate(chunks, start=1):
            write_remote_text(
                target.instance_id,
                REGION,
                f"{REMOTE_ROOT}/chunks/{name}.part{index:04d}",
                chunk,
                profile=PROFILE,
                as_user="ubuntu",
            )
        specs.append({"name": name, "parts": len(chunks), "sha256": sha256_text(content)})

    rebuild = """import hashlib, json, sys
from pathlib import Path
root = Path(sys.argv[1])
for spec in json.loads(sys.argv[2]):
    target = root / spec[\"name\"]
    if target.exists():
        raise SystemExit(f\"Refusing to overwrite staged file: {target}\")
    payload = b\"\".join(
        (root / \"chunks\" / f\"{spec['name']}.part{index:04d}\").read_bytes()
        for index in range(1, int(spec[\"parts\"]) + 1)
    )
    target.write_bytes(payload)
    actual = hashlib.sha256(payload).hexdigest()
    if actual != spec[\"sha256\"]:
        raise SystemExit(f\"Hash mismatch after staging for {spec['name']}: {actual}\")
    print(f\"{spec['name']}\\t{len(payload)}\\t{actual}\")
"""
    run_shell(
        target.instance_id,
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
        comment="Assemble Take15 staging",
    )


if __name__ == "__main__":
    main()
