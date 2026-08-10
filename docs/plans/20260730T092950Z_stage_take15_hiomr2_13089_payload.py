#!/usr/bin/env python3
"""Stage the declared Take15 13.0.89 payload through DYEC SSM helpers only."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


PLAN_DIR = Path(__file__).resolve().parent
IMPLEMENTATION = PLAN_DIR / "20260730T085157Z_stage_take15_hiomr2_13088_payload.py"
MANIFEST_DIR = PLAN_DIR / "20260730T085157Z_take15_hg003_na23687_13088_manifests"
LEDGER = PLAN_DIR / "20260730T092950Z_take15_hg003_na23687_13089_execution_ledger.md"

spec = importlib.util.spec_from_file_location("take15_13089_stage_impl", IMPLEMENTATION)
if spec is None or spec.loader is None:
    raise RuntimeError(f"cannot load supported stage implementation: {IMPLEMENTATION}")
stage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stage)

stage.REMOTE_ROOT = "/home/ubuntu/t15s_13089"
stage.MANIFEST_DIR = MANIFEST_DIR
stage.LEDGER = LEDGER
stage.FILES = {
    "specimens.tsv": MANIFEST_DIR / "specimens.tsv",
    "samples.tsv": MANIFEST_DIR / "samples.tsv",
    "libraries.tsv": MANIFEST_DIR / "libraries.tsv",
    "sequencing_inputs.tsv": MANIFEST_DIR / "sequencing_inputs.tsv",
    "analysis_units.tsv": MANIFEST_DIR / "analysis_units.tsv",
    "analysis_unit_inputs.tsv": MANIFEST_DIR / "analysis_unit_inputs.tsv",
    "bjuice_preval_config_receipt.json": MANIFEST_DIR / "bjuice_preval_config_receipt.json",
    "manifest_validation_receipt.json": MANIFEST_DIR / "manifest_validation_receipt.json",
    "hiomr2_take15_hg003_na23687_fullcov.yaml": (
        MANIFEST_DIR / "hiomr2_take15_hg003_na23687_fullcov.yaml"
    ),
    "take15_13089_execution_ledger.md": LEDGER,
}
stage.EXPECTED_SHA256 = {
    "specimens.tsv": "d3ffea1551f338aaf635f73f01127db0616eadc3b78a626b636f231a56bd6a60",
    "samples.tsv": "ae662279f16e04cc093b2fbc515c9b0e79003a765903d1d31a62f773937e8f95",
    "libraries.tsv": "381ba5aec7a758bd15c480cc6ddf143e2e01efaefc722f02e51b6384688c6fbd",
    "sequencing_inputs.tsv": "c1d5d2d533735b3d92f5f5a69ad7c64930df6b67cbd4a83a65d4eb7d0cfc8667",
    "analysis_units.tsv": "ac945e104b62f4e381c9460b9dbd4942416c88f1d135d20d297db7a764016b09",
    "analysis_unit_inputs.tsv": "28406e29d9efd1093ce34ac61f6816b4cc63b9f63c50bb36d520f22addb0f213",
    "bjuice_preval_config_receipt.json": (
        "689b79237878e172cadd1628796a857e30bba4d327ada0e2a1843466d36d1f44"
    ),
    "manifest_validation_receipt.json": (
        "bf1e918ebeb55585db4e0ec0f1489bbf4e8c6a3916ae9596cd15fd12aab34a62"
    ),
    "hiomr2_take15_hg003_na23687_fullcov.yaml": (
        "c06ab2df7fa7f26c33620ea13d0d45a92717e85c5c4e911e7c9332021577f238"
    ),
    "take15_13089_execution_ledger.md": (
        "3e9b53a5cc67ca5171b1eee601901b9cd8d27cffcdc95340da6c08441ac32b2c"
    ),
}


def print_chunk_states() -> None:
    payload = stage.read_payload()
    parts, _ = stage.make_specs(payload)
    headnode = stage.resolve_headnode_instance_id(
        stage.CLUSTER, stage.REGION, profile=stage.PROFILE
    )
    states = stage.part_states(headnode.instance_id, parts)
    for path, state in sorted(states.items()):
        print(f"{state}\t{path}")


if __name__ == "__main__":
    if sys.argv[1:] == ["--states"]:
        print_chunk_states()
    else:
        stage.main()
