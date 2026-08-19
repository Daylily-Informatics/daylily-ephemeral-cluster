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
DYEC_RELEASE = "18.0.52"
PREVIOUS_DYEC_RELEASE = "18.0.51"
DAYOA_RELEASE = "15.0.29"

RC0_REMEDIATION_COMMAND_IDS = (
    "hiomr2_slim_kitchensink_mega",
    "inflection-bjuice-product-v0.9",
    "illumina_hg002_kitchensink_multiqc",
    "ont_snv_alignstats_kitchensink",
    "ultima_snv_alignstats_kitchensink",
    "complete_genomics_cg_snv_concordance",
    "illumina_sentieon_pangenome_kitchensink",
    "ultima_sentieon_pangenome_kitchensink",
)
MULTIQC_EVIDENCE_COMMAND_IDS = (
    "ont_snv_alignstats_kitchensink",
    "ultima_snv_alignstats_kitchensink",
    "complete_genomics_cg_snv_concordance",
    "illumina_sentieon_pangenome_kitchensink",
    "ultima_sentieon_pangenome_kitchensink",
)
FINAL_MULTIQC = "results/day/hg38/reports/DAY_final_multiqc.html"
EVIDENCE_MANIFEST = "results/day/hg38/reports/dayoa_evidence_manifest.json"


def _raw_catalog() -> dict:
    return yaml.safe_load(SOURCE_CATALOG.read_text(encoding="utf-8"))


def _tag_catalog(release: str) -> dict:
    source = subprocess.check_output(
        ["git", "show", f"{release}:config/daylily_pipeline_command_catalog.yaml"],
        cwd=REPO_ROOT,
        text=True,
    )
    return yaml.safe_load(source)


def test_18_0_52_is_a_frozen_current_snapshot_pinned_to_dayoa_15_0_29() -> None:
    assert SOURCE_CATALOG.read_bytes() == PACKAGED_CATALOG.read_bytes()

    raw = _raw_catalog()
    release = raw["dyec_builds"][DYEC_RELEASE]
    current = raw["dyec_builds"]["current"]
    previous = _tag_catalog(PREVIOUS_DYEC_RELEASE)

    assert release == current
    assert raw["repositories"]["daylily-omics-analysis"]["default_ref"] == DAYOA_RELEASE
    assert current["dayoa_git_tags"] == [DAYOA_RELEASE]
    assert {command["git_tag"] for command in current["commands"].values()} == {
        DAYOA_RELEASE
    }
    assert raw["dyec_builds"][PREVIOUS_DYEC_RELEASE] == previous["dyec_builds"][
        PREVIOUS_DYEC_RELEASE
    ]


def test_18_0_52_has_exact_release_controlled_rc0_remediation_commands() -> None:
    catalog = load_repository_catalog(SOURCE_CATALOG)

    for command_id in RC0_REMEDIATION_COMMAND_IDS:
        command = catalog.get_command_for_dyec_build(command_id, DYEC_RELEASE)
        assert command.type == "prod"
        assert command.git_tag == DAYOA_RELEASE
        assert command.jobs == 333
        assert " -j 333 -T 0 -p" in command.dy_command
        assert command.dryrun_dy_command == f"{command.dy_command} -n"

    for command_id in (
        "hiomr2_slim_kitchensink_mega",
        "inflection-bjuice-product-v0.9",
    ):
        command = catalog.get_command_for_dyec_build(command_id, DYEC_RELEASE)
        assert command.dy_command.startswith(
            "PIP_NO_BUILD_ISOLATION=1 DAY_CONTAINERIZED=true dy-r "
        )


def test_18_0_52_current_catalog_excludes_retired_commands_and_requires_final_evidence() -> None:
    catalog = load_repository_catalog(SOURCE_CATALOG)
    current_ids = {
        command.command_id for command in catalog.commands_for_dyec_build(DYEC_RELEASE)
    }
    assert "bjuice-v2-hg002-custom-multi-analysis-unit-hiomr2-kitchensink-mega" not in current_ids
    assert "inflection-bjuice-product-v0.2" not in current_ids

    for command_id in MULTIQC_EVIDENCE_COMMAND_IDS:
        command = catalog.get_command_for_dyec_build(command_id, DYEC_RELEASE)
        assert FINAL_MULTIQC in command.targets
        assert EVIDENCE_MANIFEST in command.targets
