from __future__ import annotations

from pathlib import Path

import yaml

from daylily_ec.repositories import CURRENT_DYEC_BUILD
from daylily_ec.workflow_observability import MAX_TRANSPORT_COLLECTION_RECORDS

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_CATALOG = REPO_ROOT / "config/daylily_pipeline_command_catalog.yaml"
PACKAGED_CATALOG = (
    REPO_ROOT / "daylily_ec/resources/payload/config/daylily_pipeline_command_catalog.yaml"
)
DYEC_RELEASE = "19.0.27"
PREVIOUS_DYEC_RELEASE = "19.0.26"


def test_19_0_27_preserves_the_19_0_26_catalog_snapshot() -> None:
    assert CURRENT_DYEC_BUILD == DYEC_RELEASE
    assert SOURCE_CATALOG.read_bytes() == PACKAGED_CATALOG.read_bytes()
    builds = yaml.safe_load(SOURCE_CATALOG.read_text(encoding="utf-8"))["dyec_builds"]
    assert builds[DYEC_RELEASE] == builds[PREVIOUS_DYEC_RELEASE]


def test_19_0_27_bounds_workflow_status_transport_and_documents_totals() -> None:
    guide = (REPO_ROOT / "docs/agent_cli_guide.md").read_text(encoding="utf-8")
    reference = (REPO_ROOT / "docs/cli_reference.md").read_text(encoding="utf-8")
    assert MAX_TRANSPORT_COLLECTION_RECORDS == 20
    assert "complete job totals" in guide
    assert "Authoritative `submitted_count`" in reference
