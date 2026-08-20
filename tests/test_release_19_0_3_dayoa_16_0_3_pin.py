from __future__ import annotations

import copy
import subprocess
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_CATALOG = REPO_ROOT / "config/daylily_pipeline_command_catalog.yaml"
PACKAGED_CATALOG = (
    REPO_ROOT / "daylily_ec/resources/payload/config/daylily_pipeline_command_catalog.yaml"
)
DYEC_RELEASE = "19.0.3"
BASE_DYEC_RELEASE = "19.0.2"
DAYOA_RELEASE = "16.0.3"
PRODUCTION_COMMAND_IDS = {
    "complete_genomics_cg_snv_concordance",
    "hiomr2_slim_kitchensink_mega",
    "illumina_hg002_kitchensink_multiqc",
    "illumina_run_qc",
    "illumina_sentieon_pangenome_kitchensink",
    "inflection-bjuice-product-v0.9",
    "ont_run_qc",
    "ont_snv_alignstats_kitchensink",
    "ultima_run_qc",
    "ultima_sentieon_pangenome_kitchensink",
    "ultima_snv_alignstats_kitchensink",
}


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


def test_19_0_3_is_current_and_uniformly_pins_dayoa_16_0_3() -> None:
    assert SOURCE_CATALOG.read_bytes() == PACKAGED_CATALOG.read_bytes()

    raw = _catalog()
    repository = raw["repositories"]["daylily-omics-analysis"]
    active = {item["command_id"]: item for item in repository["analysis_commands"]}
    current = raw["dyec_builds"]["current"]
    release = raw["dyec_builds"][DYEC_RELEASE]

    assert current == release
    assert repository["default_ref"] == DAYOA_RELEASE
    assert len(active) == len(current["commands"]) == 31
    assert set(active) == set(current["commands"])
    assert {item["git_tag"] for item in active.values()} == {DAYOA_RELEASE}
    assert current["dayoa_git_tags"] == [DAYOA_RELEASE]
    assert {item["git_tag"] for item in current["commands"].values()} == {DAYOA_RELEASE}
    assert {
        item["command_id"] for item in current["commands"].values() if item["type"] == "prod"
    } == PRODUCTION_COMMAND_IDS


def test_19_0_3_changes_only_active_and_current_dayoa_pins() -> None:
    raw = _catalog()
    tagged = _tag_catalog(BASE_DYEC_RELEASE)
    tagged_repository = tagged["repositories"]["daylily-omics-analysis"]
    expected_active = copy.deepcopy(tagged_repository["analysis_commands"])
    for command in expected_active:
        command["git_tag"] = DAYOA_RELEASE

    assert raw["repositories"]["daylily-omics-analysis"] == {
        **tagged_repository,
        "default_ref": DAYOA_RELEASE,
        "analysis_commands": expected_active,
    }
    assert raw["dyec_builds"][DYEC_RELEASE] == _retargeted(tagged["dyec_builds"]["current"])

    for build, snapshot in tagged["dyec_builds"].items():
        if build == "current":
            continue
        assert raw["dyec_builds"][build] == snapshot
