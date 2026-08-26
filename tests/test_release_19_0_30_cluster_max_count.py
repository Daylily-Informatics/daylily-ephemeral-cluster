from __future__ import annotations

from pathlib import Path

import yaml

from daylily_ec.cli import app
from daylily_ec.workflow.cluster_max_count import CLUSTER_MAX_COUNT_SCHEMA

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_CATALOG = REPO_ROOT / "config/daylily_pipeline_command_catalog.yaml"
PACKAGED_CATALOG = (
    REPO_ROOT / "daylily_ec/resources/payload/config/daylily_pipeline_command_catalog.yaml"
)
DYEC_RELEASE = "19.0.30"
PREVIOUS_DYEC_RELEASE = "19.0.29"


def test_19_0_30_preserves_the_19_0_29_catalog_snapshot() -> None:
    assert SOURCE_CATALOG.read_bytes() == PACKAGED_CATALOG.read_bytes()
    builds = yaml.safe_load(SOURCE_CATALOG.read_text(encoding="utf-8"))["dyec_builds"]
    assert DYEC_RELEASE in builds
    assert builds[DYEC_RELEASE] == builds[PREVIOUS_DYEC_RELEASE]


def test_19_0_30_exposes_guarded_cluster_max_count_command() -> None:
    command = app._cli_core_yo_registry.get_command(("cluster", "max-count"))
    assert command is not None
    assert command.policy.supports_json is True
    assert command.policy.mutates_state is True
    assert command.policy.long_running is True
    assert CLUSTER_MAX_COUNT_SCHEMA == "dyec.cluster_max_count.v1"


def test_19_0_30_documents_per_resource_semantics_and_guardrails() -> None:
    guide = (REPO_ROOT / "docs/agent_cli_guide.md").read_text(encoding="utf-8")
    reference = (REPO_ROOT / "docs/cli_reference.md").read_text(encoding="utf-8")
    assert "dyec --json cluster max-count" in guide
    assert "`MaxCount` is per compute resource" in reference
    assert "zero DayOA controllers and zero Slurm jobs" in reference
