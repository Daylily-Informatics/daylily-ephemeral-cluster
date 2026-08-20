from __future__ import annotations

import subprocess
from pathlib import Path

import yaml

from daylily_ec.repositories import load_repository_catalog


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
DYEC_RELEASE = "18.0.56"
PREVIOUS_DYEC_RELEASE = "18.0.55"
DAYOA_RELEASE = "15.0.37"
CURRENT_DAYOA_RELEASE = "16.0.2"
PRODUCTION_COMMAND_IDS = {
    "illumina_run_qc",
    "ont_run_qc",
    "ultima_run_qc",
    "hiomr2_slim_kitchensink_mega",
    "inflection-bjuice-product-v0.9",
    "illumina_hg002_kitchensink_multiqc",
    "ont_snv_alignstats_kitchensink",
    "ultima_snv_alignstats_kitchensink",
    "complete_genomics_cg_snv_concordance",
    "illumina_sentieon_pangenome_kitchensink",
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


def test_18_0_56_remains_frozen_at_dayoa_15_0_37() -> None:
    assert SOURCE_CATALOG.read_bytes() == PACKAGED_CATALOG.read_bytes()

    raw = _raw_catalog()
    current = raw["dyec_builds"]["current"]
    release = raw["dyec_builds"][DYEC_RELEASE]
    tagged_release = _tag_catalog(DYEC_RELEASE)
    previous = _tag_catalog(PREVIOUS_DYEC_RELEASE)

    assert release == tagged_release["dyec_builds"][DYEC_RELEASE]
    assert release != current
    assert raw["repositories"]["daylily-omics-analysis"]["default_ref"] == (
        CURRENT_DAYOA_RELEASE
    )
    assert release["dayoa_git_tags"] == [DAYOA_RELEASE]
    assert {command["git_tag"] for command in release["commands"].values()} == {
        DAYOA_RELEASE
    }
    assert raw["dyec_builds"][PREVIOUS_DYEC_RELEASE] == previous["dyec_builds"][
        PREVIOUS_DYEC_RELEASE
    ]


def test_18_0_56_preserves_the_complete_rc0_production_catalog() -> None:
    catalog = load_repository_catalog(SOURCE_CATALOG)
    production_commands = {
        command.command_id
        for command in catalog.commands_for_dyec_build(DYEC_RELEASE)
        if command.type == "prod"
    }

    assert production_commands == PRODUCTION_COMMAND_IDS
    for command_id in PRODUCTION_COMMAND_IDS:
        command = catalog.get_command_for_dyec_build(command_id, DYEC_RELEASE)
        assert command.git_tag == DAYOA_RELEASE
        assert command.jobs == 333
        assert " -j 333 -T 0 -p" in command.dy_command
        assert command.dryrun_dy_command == f"{command.dy_command} -n"
