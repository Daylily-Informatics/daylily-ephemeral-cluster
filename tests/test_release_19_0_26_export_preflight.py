from __future__ import annotations

from pathlib import Path

import yaml

from daylily_ec.cli import app
from daylily_ec.repositories import CURRENT_DYEC_BUILD

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_CATALOG = REPO_ROOT / "config/daylily_pipeline_command_catalog.yaml"
PACKAGED_CATALOG = (
    REPO_ROOT / "daylily_ec/resources/payload/config/daylily_pipeline_command_catalog.yaml"
)
DYEC_RELEASE = "19.0.26"
PREVIOUS_DYEC_RELEASE = "19.0.25"


def test_19_0_26_preserves_the_19_0_25_catalog_snapshot() -> None:
    assert SOURCE_CATALOG.read_bytes() == PACKAGED_CATALOG.read_bytes()
    builds = yaml.safe_load(SOURCE_CATALOG.read_text(encoding="utf-8"))["dyec_builds"]
    assert CURRENT_DYEC_BUILD in builds
    assert builds[DYEC_RELEASE] == builds[PREVIOUS_DYEC_RELEASE]


def test_19_0_26_exposes_read_only_export_preflight() -> None:
    command = app._cli_core_yo_registry.get_command(("exports", "preflight"))
    assert command is not None
    assert command.policy.supports_json is True
    assert command.policy.mutates_state is False
    assert command.policy.long_running is False


def test_19_0_26_documents_preflight_before_destructive_approval() -> None:
    guide = (REPO_ROOT / "docs/agent_cli_guide.md").read_text(encoding="utf-8")
    reference = (REPO_ROOT / "docs/cli_reference.md").read_text(encoding="utf-8")
    assert "dyec --json exports preflight" in guide
    assert "Run it before seeking approval for a destructive export" in guide
    assert "dyec.exports.preflight.v1" in reference
