from __future__ import annotations

import copy
import subprocess
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_CATALOG = REPO_ROOT / "config/daylily_pipeline_command_catalog.yaml"
PACKAGED_CATALOG = (
    REPO_ROOT
    / "daylily_ec/resources/payload/config/daylily_pipeline_command_catalog.yaml"
)
DYEC_RELEASE = "19.0.24"
PREVIOUS_DYEC_RELEASE = "19.0.22"
DAYOA_RELEASE = "16.0.6"


def _catalog(path: Path = SOURCE_CATALOG) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _tag_catalog(release: str) -> dict:
    source = subprocess.check_output(
        ["git", "show", f"{release}:config/daylily_pipeline_command_catalog.yaml"],
        cwd=REPO_ROOT,
        text=True,
    )
    return yaml.safe_load(source)


def _retargeted(snapshot: dict) -> dict:
    expected = copy.deepcopy(snapshot)
    expected["dayoa_git_tags"] = [DAYOA_RELEASE]
    for command in expected["commands"].values():
        command["git_tag"] = DAYOA_RELEASE
    return expected


def test_19_0_24_uniformly_pins_dayoa_16_0_6() -> None:
    assert SOURCE_CATALOG.read_bytes() == PACKAGED_CATALOG.read_bytes()

    raw = _catalog()
    repository = raw["repositories"]["daylily-omics-analysis"]
    release = raw["dyec_builds"][DYEC_RELEASE]

    assert repository["default_ref"] == DAYOA_RELEASE
    assert {item["git_tag"] for item in repository["analysis_commands"]} == {
        DAYOA_RELEASE
    }
    assert release["dayoa_git_tags"] == [DAYOA_RELEASE]
    assert {item["git_tag"] for item in release["commands"].values()} == {
        DAYOA_RELEASE
    }


def test_19_0_24_preserves_19_0_22_and_retargets_only_new_snapshot() -> None:
    raw = _catalog()
    tagged = _tag_catalog(PREVIOUS_DYEC_RELEASE)

    assert raw["dyec_builds"][PREVIOUS_DYEC_RELEASE] == tagged["dyec_builds"][
        PREVIOUS_DYEC_RELEASE
    ]
    assert raw["dyec_builds"][DYEC_RELEASE] == _retargeted(
        tagged["dyec_builds"][PREVIOUS_DYEC_RELEASE]
    )
