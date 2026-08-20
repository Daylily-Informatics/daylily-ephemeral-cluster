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
DYEC_RELEASE = "19.0.1"
PREVIOUS_DYEC_RELEASE = "19.0.0"
DAYOA_RELEASE = "16.0.2"
PANGENOME_COMMAND_IDS = {
    "illumina_sentieon_pangenome_kitchensink",
    "ultima_sentieon_pangenome_kitchensink",
}
PRODUCTION_COMMAND_IDS = {
    "illumina_hg002_kitchensink_multiqc",
    "ultima_snv_alignstats_kitchensink",
    "ont_snv_alignstats_kitchensink",
    "hiomr2_slim_kitchensink_mega",
    "complete_genomics_cg_snv_concordance",
    "illumina_run_qc",
    "ont_run_qc",
    "ultima_run_qc",
    "inflection-bjuice-product-v0.9",
    *PANGENOME_COMMAND_IDS,
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


def test_19_0_1_is_current_and_reconciles_active_membership() -> None:
    assert SOURCE_CATALOG.read_bytes() == PACKAGED_CATALOG.read_bytes()

    raw = _catalog()
    repository = raw["repositories"]["daylily-omics-analysis"]
    active = {item["command_id"]: item for item in repository["analysis_commands"]}
    current = raw["dyec_builds"]["current"]

    assert current == raw["dyec_builds"][DYEC_RELEASE]
    assert repository["default_ref"] == DAYOA_RELEASE
    assert len(active) == len(current["commands"]) == 31
    assert set(active) == set(current["commands"])
    assert "inflection-bjuice-product-v0.2" not in active
    assert PANGENOME_COMMAND_IDS <= set(active)
    assert {item["git_tag"] for item in active.values()} == {DAYOA_RELEASE}
    assert current["dayoa_git_tags"] == [DAYOA_RELEASE]
    assert {item["git_tag"] for item in current["commands"].values()} == {
        DAYOA_RELEASE
    }
    assert {
        item["command_id"]
        for item in current["commands"].values()
        if item["type"] == "prod"
    } == PRODUCTION_COMMAND_IDS

    for command_id in PANGENOME_COMMAND_IDS:
        expected = copy.deepcopy(current["commands"][command_id])
        expected.pop("repository")
        assert active[command_id] == expected


def test_19_0_1_only_retargets_the_frozen_19_0_0_commands() -> None:
    raw = _catalog()
    tagged = _tag_catalog(PREVIOUS_DYEC_RELEASE)

    assert raw["dyec_builds"][PREVIOUS_DYEC_RELEASE] == tagged["dyec_builds"][
        PREVIOUS_DYEC_RELEASE
    ]
    assert raw["dyec_builds"][DYEC_RELEASE] == _retargeted(
        raw["dyec_builds"][PREVIOUS_DYEC_RELEASE]
    )

    for build, snapshot in tagged["dyec_builds"].items():
        if build == "current":
            continue
        assert raw["dyec_builds"][build] == snapshot
