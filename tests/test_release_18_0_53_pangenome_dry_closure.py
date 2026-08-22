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
DYEC_RELEASE = "18.0.53"
PREVIOUS_DYEC_RELEASE = "18.0.52"
DAYOA_RELEASE = "15.0.30"

PANGENOME_COMMANDS = {
    "illumina_sentieon_pangenome_kitchensink": "produce_sentpg_sr_snv_vcf",
    "ultima_sentieon_pangenome_kitchensink": "produce_sentpg_ug_snv_vcf",
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


def test_18_0_53_remains_a_frozen_snapshot_pinned_to_dayoa_15_0_30() -> None:
    assert SOURCE_CATALOG.read_bytes() == PACKAGED_CATALOG.read_bytes()

    raw = _raw_catalog()
    release = raw["dyec_builds"][DYEC_RELEASE]
    tagged = _tag_catalog(DYEC_RELEASE)
    previous = _tag_catalog(PREVIOUS_DYEC_RELEASE)

    assert release == tagged["dyec_builds"][DYEC_RELEASE]
    assert raw["dyec_builds"][PREVIOUS_DYEC_RELEASE] == previous["dyec_builds"][
        PREVIOUS_DYEC_RELEASE
    ]


def test_18_0_53_pangenome_commands_are_production_same_root_dry_closures() -> None:
    catalog = load_repository_catalog(SOURCE_CATALOG)

    for command_id, graph_target in PANGENOME_COMMANDS.items():
        command = catalog.get_command_for_dyec_build(command_id, DYEC_RELEASE)

        assert command.type == "prod"
        assert command.git_tag == DAYOA_RELEASE
        assert command.genome == "hg38"
        assert command.jobs == 333
        assert graph_target in command.targets
        assert " -j 333 -T 0 -p" in command.dy_command
        assert command.dryrun_dy_command == f"{command.dy_command} -n"
