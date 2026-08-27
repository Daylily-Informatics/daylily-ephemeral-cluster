from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SOURCE_CATALOG = ROOT / "config/daylily_pipeline_command_catalog.yaml"
PACKAGED_CATALOG = (
    ROOT / "daylily_ec/resources/payload/config/daylily_pipeline_command_catalog.yaml"
)


def test_19_0_32_preserves_the_19_0_31_catalog() -> None:
    assert SOURCE_CATALOG.read_bytes() == PACKAGED_CATALOG.read_bytes()
    builds = yaml.safe_load(SOURCE_CATALOG.read_text(encoding="utf-8"))["dyec_builds"]
    assert builds["19.0.32"] == builds["19.0.31"]
