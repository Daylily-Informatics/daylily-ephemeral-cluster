from __future__ import annotations

from pathlib import Path

import yaml

from daylily_ec.repositories import CURRENT_DYEC_BUILD
from daylily_ec.workflow_observability import MAX_SNAKEMAKE_MATCHES

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_CATALOG = REPO_ROOT / "config/daylily_pipeline_command_catalog.yaml"
PACKAGED_CATALOG = (
    REPO_ROOT / "daylily_ec/resources/payload/config/daylily_pipeline_command_catalog.yaml"
)
DYEC_RELEASE = "19.0.28"
PREVIOUS_DYEC_RELEASE = "19.0.27"


def test_19_0_28_preserves_the_19_0_27_catalog_snapshot() -> None:
    assert CURRENT_DYEC_BUILD == DYEC_RELEASE
    assert SOURCE_CATALOG.read_bytes() == PACKAGED_CATALOG.read_bytes()
    builds = yaml.safe_load(SOURCE_CATALOG.read_text(encoding="utf-8"))["dyec_builds"]
    assert builds[DYEC_RELEASE] == builds[PREVIOUS_DYEC_RELEASE]


def test_19_0_28_documents_bounded_literal_workflow_log_search() -> None:
    guide = (REPO_ROOT / "docs/agent_cli_guide.md").read_text(encoding="utf-8")
    reference = (REPO_ROOT / "docs/cli_reference.md").read_text(encoding="utf-8")
    assert MAX_SNAKEMAKE_MATCHES == 10
    assert '--match "Error in rule"' in guide
    assert "literal full-log search" in reference
