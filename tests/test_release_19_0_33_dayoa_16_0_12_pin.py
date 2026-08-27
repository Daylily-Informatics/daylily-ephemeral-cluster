from __future__ import annotations

import copy
import subprocess
from pathlib import Path

import yaml

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
    "bjuice_manifest",
]

MANIFEST_TARGETS = {
    "illumina_run_qc": "ilmn_seqqc_manifest",
    "ont_run_qc": "ont_seqqc_manifest",
    "ultima_run_qc": "ultima_seqqc_manifest",
    "illumina_hg002_kitchensink_multiqc": "ilmn_solo_kitchensink_manifest",
    "ultima_snv_alignstats_kitchensink": "ultima_solo_kitchensink_manifest",
    "ont_snv_alignstats_kitchensink": "ont_solo_kitchensink_manifest",
    "complete_genomics_cg_snv_concordance": "cg_solo_kitchensink_manifest",
    "hiomr2_slim_kitchensink_mega": "bjuice_manifest",
    "inflection-bjuice-product-v0.9": "bjuice_manifest",
    "inflection-bjuice-product-v0.9-slim-5x5x-validation": "bjuice_manifest",
}


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


def _expected_19_0_33_commands(commands: dict) -> dict:
    expected = copy.deepcopy(commands)
    for command in expected.values():
        command["git_tag"] = DAYOA_RELEASE
        for key in ("dy_command", "dryrun_dy_command"):
            value = command[key]
            for option in (
                "--produce-analysis-artifact-manifest true",
                "--produce-rulegraph true",
                "--produce-rulegraph false",
                "--produce-filegraph true",
                "--produce-filegraph false",
                "--produce-dag true",
                "--produce-dag false",
            ):
                value = value.replace(f" {option}", "")
            command[key] = value

    for command_id, manifest_target in MANIFEST_TARGETS.items():
        if command_id not in expected:
            continue
        command = expected[command_id]
        command["targets"].append(manifest_target)
        for key in ("dy_command", "dryrun_dy_command"):
            value = command[key]
            last_target = command["targets"][-2]
            command[key] = value.replace(
                last_target,
                f"{last_target} {manifest_target}",
                1,
            )
    return expected


def test_19_0_33_tag_uniformly_pins_dayoa_16_0_12() -> None:
    raw = _tag_catalog(DYEC_RELEASE)
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
    assert release["commands"] == _expected_19_0_33_commands(historical["commands"])

    # The campaign-specific BloodBridge recovery alias remains historical. The
    # fresh-forward release does not expose a recall or prior-artifact interface.
    assert release["aliases"] == {}


def test_production_bjuice_inflection_command_adds_only_the_product_manifest_target() -> None:
    raw = _tag_catalog(DYEC_RELEASE)
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
    expected = _expected_19_0_33_commands({PRODUCT_COMMAND_ID: historical})[
        PRODUCT_COMMAND_ID
    ]
    assert release == expected
    assert active["git_tag"] == DAYOA_RELEASE
    assert "recall" not in release["dy_command"].lower()
    assert "reuse" not in release["dy_command"].lower()


def test_19_0_33_uses_scoped_manifest_targets_and_no_global_manifest_switch() -> None:
    raw = _catalog()
    active = {
        item["command_id"]: item
        for item in raw["repositories"]["daylily-omics-analysis"]["analysis_commands"]
    }
    release = raw["dyec_builds"][DYEC_RELEASE]["commands"]

    for commands in (active, release):
        for command_id, target in MANIFEST_TARGETS.items():
            assert commands[command_id]["targets"].count(target) == 1
            assert commands[command_id]["dy_command"].count(target) == 1
            assert commands[command_id]["dryrun_dy_command"].count(target) == 1
        assert all(
            "--produce-analysis-artifact-manifest" not in command["dy_command"]
            for command in commands.values()
        )
