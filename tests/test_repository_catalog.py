from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from daylily_ec.cli import app
from daylily_ec.repositories import load_repository_catalog


runner = CliRunner()


REPO_ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = REPO_ROOT / "config" / "daylily_available_repositories.yaml"
PACKAGED_CATALOG_PATH = (
    REPO_ROOT
    / "daylily_ec"
    / "resources"
    / "payload"
    / "config"
    / "daylily_available_repositories.yaml"
)


def test_repository_catalog_loads_initial_blessed_command() -> None:
    catalog = load_repository_catalog(CATALOG_PATH)
    command = catalog.get_command("illumina_snv_alignstats")

    assert catalog.command_catalog_version == 1
    assert command.repository == "daylily-omics-analysis"
    assert command.datasource == "Illumina"
    assert command.targets == ["produce_snv_concordances", "produce_alignstats"]
    assert command.snv_callers == ["sentd"]
    assert command.sv_callers == []
    assert command.git_tag == "0.7.754"
    assert command.compatible_platforms == ["ILMN"]
    assert command.compatible_data_modes == ["ilmn_solo"]
    assert "bin/day_run" in command.dy_command
    assert command.dryrun_dy_command.endswith(" -n")

    launch_argv = command.launch_argv(destination="run-1", cluster="cluster-a")
    assert "--dy-command" in launch_argv
    assert "--git-tag" in launch_argv
    assert "0.7.754" in launch_argv


def test_repository_catalog_commands_have_run_metadata() -> None:
    catalog = load_repository_catalog(CATALOG_PATH)

    command_ids = {command.command_id for command in catalog.commands()}
    assert {
        "illumina_snv_alignstats",
        "ultima_snv_alignstats",
        "ont_snv_alignstats",
        "pacbio_snv_alignstats",
        "roche_snv_alignstats",
        "hybrid_ilmn_ont_snv",
        "hybrid_ultima_ont_snv",
        "complete_genomics_mgi_snv_concordance",
    } <= command_ids

    for command in catalog.commands():
        assert command.dy_command.startswith("bin/day_run ")
        assert command.dryrun_dy_command.startswith("bin/day_run ")
        assert command.dryrun_dy_command.endswith(" -n")
        assert command.compatible_platforms
        assert command.compatible_data_modes
        assert command.git_tag == "0.7.754"

    complete_genomics = catalog.get_command("complete_genomics_mgi_snv_concordance")
    assert complete_genomics.compatible_platforms == ["CG/MGI"]
    assert complete_genomics.compatible_data_modes == ["complete_genomics_solo"]
    assert "produce_cgt7p_vcf" in complete_genomics.dy_command
    assert "aligners=['sentcg']" in complete_genomics.dy_command


def test_repository_catalog_requires_catalog_version(tmp_path: Path) -> None:
    path = tmp_path / "bad.yaml"
    path.write_text(
        "default_repository: repo\n"
        "repositories:\n"
        "  repo:\n"
        "    https_url: https://example.invalid/repo.git\n"
        "    default_ref: main\n"
        "    relative_path: repo\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="command_catalog_version"):
        load_repository_catalog(path)


def test_packaged_repository_catalog_matches_source_catalog() -> None:
    assert PACKAGED_CATALOG_PATH.read_text(encoding="utf-8") == CATALOG_PATH.read_text(
        encoding="utf-8"
    )


def test_repositories_commands_json_cli_lists_blessed_command() -> None:
    result = runner.invoke(
        app,
        [
            "repositories",
            "commands",
            "--config",
            str(CATALOG_PATH),
            "--command-id",
            "illumina_snv_alignstats",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert [item["command_id"] for item in payload["commands"]] == ["illumina_snv_alignstats"]
    assert payload["commands"][0]["compatible_platforms"] == ["ILMN"]
