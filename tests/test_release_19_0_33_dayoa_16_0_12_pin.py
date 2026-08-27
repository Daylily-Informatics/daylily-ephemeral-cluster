from __future__ import annotations

import copy
import subprocess
from pathlib import Path

import yaml

from daylily_ec.repositories import CURRENT_DYEC_BUILD

ROOT = Path(__file__).resolve().parents[1]
SOURCE_CATALOG = ROOT / "config/daylily_pipeline_command_catalog.yaml"
PACKAGED_CATALOG = (
    ROOT / "daylily_ec/resources/payload/config/daylily_pipeline_command_catalog.yaml"
)
DYEC_RELEASE = "19.0.33"
PREVIOUS_DYEC_RELEASE = "19.0.32"
DAYOA_RELEASE = "16.0.12"
PRODUCT_COMMAND_ID = "inflection-bjuice-product-v0.9"
PRODUCT_TARGETS = [
    "produce_sentdhiomr2_slim_kitchensink_mega",
    "produce_sentdhiomr2_inflection_analytical_package",
]


def _catalog(path: Path = SOURCE_CATALOG) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _tag_catalog(release: str) -> dict:
    source = subprocess.check_output(
        ["git", "show", f"{release}:config/daylily_pipeline_command_catalog.yaml"],
        cwd=ROOT,
        text=True,
    )
    return yaml.safe_load(source)


def _without_pin(command: dict) -> dict:
    value = copy.deepcopy(command)
    value.pop("git_tag")
    return value


def test_19_0_33_is_current_and_uniformly_pins_dayoa_16_0_12() -> None:
    assert CURRENT_DYEC_BUILD == DYEC_RELEASE
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


def test_19_0_33_preserves_history_and_retargets_the_existing_commands() -> None:
    raw = _catalog()
    tagged = _tag_catalog(PREVIOUS_DYEC_RELEASE)
    historical = tagged["dyec_builds"][PREVIOUS_DYEC_RELEASE]
    release = raw["dyec_builds"][DYEC_RELEASE]

    assert raw["dyec_builds"][PREVIOUS_DYEC_RELEASE] == historical
    assert set(release["commands"]) == set(historical["commands"])
    for command_id, command in release["commands"].items():
        assert command["git_tag"] == DAYOA_RELEASE
        assert _without_pin(command) == _without_pin(historical["commands"][command_id])

    # The campaign-specific BloodBridge recovery alias remains historical. The
    # fresh-forward release does not expose a recall or prior-artifact interface.
    assert release["aliases"] == {}


def test_production_bjuice_inflection_command_shape_is_unchanged() -> None:
    raw = _catalog()
    tagged = _tag_catalog(PREVIOUS_DYEC_RELEASE)
    active = {
        item["command_id"]: item
        for item in raw["repositories"]["daylily-omics-analysis"]["analysis_commands"]
    }[PRODUCT_COMMAND_ID]
    release = raw["dyec_builds"][DYEC_RELEASE]["commands"][PRODUCT_COMMAND_ID]
    historical = tagged["dyec_builds"][PREVIOUS_DYEC_RELEASE]["commands"][
        PRODUCT_COMMAND_ID
    ]

    assert active["targets"] == PRODUCT_TARGETS
    assert release["targets"] == PRODUCT_TARGETS
    assert _without_pin(release) == _without_pin(historical)
    assert active["git_tag"] == DAYOA_RELEASE
    assert "recall" not in release["dy_command"].lower()
    assert "reuse" not in release["dy_command"].lower()
