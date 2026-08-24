from __future__ import annotations

from pathlib import Path

import yaml

from daylily_ec.repositories import CURRENT_DYEC_BUILD
from daylily_ec.workflow_observability import MAX_RULE_STATUS_ANALYSIS_UNIT_NAMES

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_CATALOG = REPO_ROOT / "config/daylily_pipeline_command_catalog.yaml"
PACKAGED_CATALOG = (
    REPO_ROOT / "daylily_ec/resources/payload/config/daylily_pipeline_command_catalog.yaml"
)
DYEC_RELEASE = "19.0.29"
PREVIOUS_DYEC_RELEASE = "19.0.28"


def test_19_0_29_preserves_the_19_0_28_catalog_snapshot() -> None:
    assert CURRENT_DYEC_BUILD in builds_from_catalog()
    assert SOURCE_CATALOG.read_bytes() == PACKAGED_CATALOG.read_bytes()
    builds = yaml.safe_load(SOURCE_CATALOG.read_text(encoding="utf-8"))["dyec_builds"]
    assert builds[DYEC_RELEASE] == builds[PREVIOUS_DYEC_RELEASE]


def builds_from_catalog() -> dict[str, object]:
    return yaml.safe_load(SOURCE_CATALOG.read_text(encoding="utf-8"))["dyec_builds"]


def test_19_0_29_documents_exact_rule_analysis_unit_status() -> None:
    guide = (REPO_ROOT / "docs/agent_cli_guide.md").read_text(encoding="utf-8")
    reference = (REPO_ROOT / "docs/cli_reference.md").read_text(encoding="utf-8")
    assert MAX_RULE_STATUS_ANALYSIS_UNIT_NAMES == 50
    assert "--rule sentdhiomr2_hybrid_cli172i_core" in guide
    assert "unique analysis-unit counts" in reference
