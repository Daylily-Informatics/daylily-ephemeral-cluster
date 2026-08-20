from __future__ import annotations

import copy
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
DYEC_RELEASE = "19.0.0"
PREVIOUS_DYEC_RELEASE = "18.0.59"
DAYOA_RELEASE = "16.0.1"
COMMAND_FIELDS = ("dy_command", "dryrun_dy_command")


def _catalog(path: Path = SOURCE_CATALOG) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _tag_catalog(release: str) -> dict:
    source = subprocess.check_output(
        ["git", "show", f"{release}:config/daylily_pipeline_command_catalog.yaml"],
        cwd=REPO_ROOT,
        text=True,
    )
    return yaml.safe_load(source)


def _retargeted(command: dict) -> dict:
    expected = copy.deepcopy(command)
    expected["git_tag"] = DAYOA_RELEASE
    for field in COMMAND_FIELDS:
        expected[field] = expected[field].replace("bin/day_run", "dy-r")
    return expected


def test_19_0_0_remains_frozen_at_the_dayoa_16_0_1_boundary() -> None:
    assert SOURCE_CATALOG.read_bytes() == PACKAGED_CATALOG.read_bytes()

    raw = _catalog()
    release = raw["dyec_builds"][DYEC_RELEASE]
    tagged_release = _tag_catalog(DYEC_RELEASE)["dyec_builds"][DYEC_RELEASE]

    assert release == tagged_release
    assert release["dayoa_git_tags"] == [DAYOA_RELEASE]
    assert {command["git_tag"] for command in release["commands"].values()} == {
        DAYOA_RELEASE
    }
    assert len(release["commands"]) == 31
    for command in release["commands"].values():
        for field in COMMAND_FIELDS:
            assert "bin/day_run" not in command[field]
            assert "dy-r" in command[field]


def test_19_0_0_changes_only_command_pins_and_the_wrapper_boundary() -> None:
    raw = _catalog()
    tagged = _tag_catalog(PREVIOUS_DYEC_RELEASE)
    prior_current = tagged["dyec_builds"]["current"]
    release = raw["dyec_builds"][DYEC_RELEASE]

    assert set(release["commands"]) == set(prior_current["commands"])
    for command_id, command in release["commands"].items():
        assert command == _retargeted(prior_current["commands"][command_id])


def test_19_0_0_preserves_every_published_numeric_snapshot() -> None:
    raw = _catalog()
    tagged = _tag_catalog(PREVIOUS_DYEC_RELEASE)

    for build, snapshot in tagged["dyec_builds"].items():
        if build == "current":
            continue
        assert raw["dyec_builds"][build] == snapshot
