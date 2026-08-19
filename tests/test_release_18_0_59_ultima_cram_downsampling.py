from __future__ import annotations

import subprocess
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_CATALOG = REPO_ROOT / "config/daylily_pipeline_command_catalog.yaml"
PACKAGED_CATALOG = (
    REPO_ROOT
    / "daylily_ec"
    / "resources"
    / "payload"
    / "config"
    / "daylily_pipeline_command_catalog.yaml"
)
DYEC_RELEASE = "18.0.59"
PREVIOUS_DYEC_RELEASE = "18.0.58"
DEFAULT_DAYOA_RELEASE = "15.0.37"
ULTIMA_DOWNSAMPLE_DAYOA_RELEASE = "15.0.38"
ULTIMA_DOWNSAMPLE_COMMAND_IDS = {
    "ultima_snv_alignstats_kitchensink",
    "ultima_sentieon_pangenome_kitchensink",
}


def _raw_catalog() -> dict:
    return yaml.safe_load(SOURCE_CATALOG.read_text(encoding="utf-8"))


def _tag_catalog(release: str) -> dict:
    source = subprocess.check_output(
        ["git", "show", f"{release}:config/daylily_pipeline_command_catalog.yaml"],
        cwd=REPO_ROOT,
        text=True,
    )
    return yaml.safe_load(source)


def test_18_0_59_is_current_and_preserves_every_historical_snapshot() -> None:
    assert SOURCE_CATALOG.read_bytes() == PACKAGED_CATALOG.read_bytes()

    raw = _raw_catalog()
    previous = _tag_catalog(PREVIOUS_DYEC_RELEASE)
    current = raw["dyec_builds"]["current"]

    assert current == raw["dyec_builds"][DYEC_RELEASE]
    assert raw["repositories"]["daylily-omics-analysis"]["default_ref"] == (
        DEFAULT_DAYOA_RELEASE
    )
    assert current["dayoa_git_tags"] == [
        DEFAULT_DAYOA_RELEASE,
        ULTIMA_DOWNSAMPLE_DAYOA_RELEASE,
    ]

    for build, frozen_snapshot in previous["dyec_builds"].items():
        if build == "current":
            continue
        assert raw["dyec_builds"][build] == frozen_snapshot


def test_18_0_59_changes_only_the_two_ultima_command_records() -> None:
    raw = _raw_catalog()
    previous = _tag_catalog(PREVIOUS_DYEC_RELEASE)["dyec_builds"]["current"]
    current = raw["dyec_builds"]["current"]

    assert set(current["commands"]) == set(previous["commands"])
    changed_command_ids = {
        command_id
        for command_id, command in current["commands"].items()
        if command != previous["commands"][command_id]
    }
    assert changed_command_ids == ULTIMA_DOWNSAMPLE_COMMAND_IDS

    for command_id, command in current["commands"].items():
        if command_id in ULTIMA_DOWNSAMPLE_COMMAND_IDS:
            continue
        assert command == previous["commands"][command_id]
        assert command["git_tag"] == DEFAULT_DAYOA_RELEASE


def test_18_0_59_pins_only_the_two_ultima_commands_without_command_drift() -> None:
    raw = _raw_catalog()
    previous = _tag_catalog(PREVIOUS_DYEC_RELEASE)["dyec_builds"]["current"]
    current = raw["dyec_builds"]["current"]

    assert {
        command_id
        for command_id, command in current["commands"].items()
        if command["git_tag"] == ULTIMA_DOWNSAMPLE_DAYOA_RELEASE
    } == ULTIMA_DOWNSAMPLE_COMMAND_IDS

    immutable_fields = (
        "targets",
        "dy_command",
        "dryrun_dy_command",
        "input_contract",
        "input_requirements",
        "runtime_parameters",
        "genome",
        "jobs",
        "aligners",
        "dedupers",
        "snv_callers",
        "sv_callers",
    )
    for command_id in ULTIMA_DOWNSAMPLE_COMMAND_IDS:
        command = current["commands"][command_id]
        frozen_command = previous["commands"][command_id]

        assert command["git_tag"] == ULTIMA_DOWNSAMPLE_DAYOA_RELEASE
        assert command["runtime_parameters"] == {}
        assert command["dryrun_dy_command"] == f'{command["dy_command"]} -n'
        assert "ULTIMA_SUBSAMPLE_PCT" in command["description"]
        assert "seed 33" in command["description"]
        for field in immutable_fields:
            assert command[field] == frozen_command[field]
