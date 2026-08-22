from __future__ import annotations

from pathlib import Path

import yaml

from daylily_ec.repositories import CURRENT_DYEC_BUILD


REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_CATALOG = REPO_ROOT / "config/daylily_pipeline_command_catalog.yaml"
PACKAGED_CATALOG = (
    REPO_ROOT / "daylily_ec/resources/payload/config/daylily_pipeline_command_catalog.yaml"
)


def test_19_0_19_keeps_the_19_0_18_catalog_snapshot() -> None:
    assert CURRENT_DYEC_BUILD == "19.0.19"
    assert SOURCE_CATALOG.read_bytes() == PACKAGED_CATALOG.read_bytes()
    builds = yaml.safe_load(SOURCE_CATALOG.read_text(encoding="utf-8"))["dyec_builds"]

    assert builds["19.0.19"] == builds["19.0.18"]
