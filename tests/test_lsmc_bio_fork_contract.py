from pathlib import Path

import tomllib
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]

_OLD_ORG = "Daylily-" + "Informatics"
DAYOA_DEFAULT_TAG = "15.0.6"
DAYOA_VALIDATED_TAG = "15.0.1"
BJUICE_V2_DAYOA_TARGET_TAG = "15.0.6"
BJUICE_V2_DAYOA_VALIDATED_TAG = "15.0.3"
DAYOA_HIGHEST_RELEASE_COMMIT = "243763b3d293b1049129b82e3717b1225a1fd21c"
ONT_DAYOA_TAG = "15.0.6"
ONT_DAYOA_VALIDATED_TAG = "15.0.1"
ONT_DAYOA_RELEASE_COMMIT = "243763b3d293b1049129b82e3717b1225a1fd21c"

FORBIDDEN_ACTIVE_REFERENCES = (
    f"{_OLD_ORG}/daylily-omics-analysis",
    f"{_OLD_ORG}/daylily-ephemeral-cluster",
    f"github.com:{_OLD_ORG}/daylily-omics-analysis",
    f"github.com:{_OLD_ORG}/daylily-ephemeral-cluster",
    f"github.com/{_OLD_ORG}/daylily-omics-analysis",
    f"github.com/{_OLD_ORG}/daylily-ephemeral-cluster",
    "daylily-omics-analysis" + "==",
)

ACTIVE_PATHS = (
    "README.md",
    "pyproject.toml",
    "config/daylily_cli_global.yaml",
    "config/daylily_pipeline_command_catalog.yaml",
    "daylily_ec/resources/payload/config/daylily_cli_global.yaml",
    "daylily_ec/resources/payload/config/daylily_pipeline_command_catalog.yaml",
    "scripts/finish_headnode_cfg.sh",
    "bin/quick_start_all_prereq_done_prior.bash",
    "daylily_ec/workflow/create_cluster.py",
    "tests/test_workflow.py",
)


def test_active_surfaces_do_not_reference_daylily_informatics_dayoa_or_dyec() -> None:
    offenders: list[str] = []
    for relative_path in ACTIVE_PATHS:
        text = (REPO_ROOT / relative_path).read_text(encoding="utf-8")
        for forbidden in FORBIDDEN_ACTIVE_REFERENCES:
            if forbidden in text:
                offenders.append(f"{relative_path}: {forbidden}")

    assert not offenders


def test_pyproject_does_not_install_dayoa_as_a_python_dependency() -> None:
    data = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    dependencies = data["project"]["dependencies"]

    assert not any("daylily-omics-analysis" in dependency for dependency in dependencies)


def test_catalogs_and_dyec_repository_config_are_lsmc_bio_pinned() -> None:
    for relative_path in (
        "config/daylily_cli_global.yaml",
        "daylily_ec/resources/payload/config/daylily_cli_global.yaml",
    ):
        data = yaml.safe_load((REPO_ROOT / relative_path).read_text(encoding="utf-8"))
        daylily = data["daylily"]
        assert "git_ephemeral_cluster_repo_tag" not in daylily
        assert "git_ephemeral_cluster_repo_release_tag" not in daylily
        assert (
            daylily["git_ephemeral_cluster_repo"]
            == "https://github.com/lsmc-bio/daylily-ephemeral-cluster.git"
        )

    for relative_path in (
        "config/daylily_pipeline_command_catalog.yaml",
        "daylily_ec/resources/payload/config/daylily_pipeline_command_catalog.yaml",
    ):
        data = yaml.safe_load((REPO_ROOT / relative_path).read_text(encoding="utf-8"))
        repo = data["repositories"]["daylily-omics-analysis"]
        assert repo["https_url"] == "https://github.com/lsmc-bio/daylily-omics-analysis.git"
        assert repo["ssh_url"] == "git@github.com:lsmc-bio/daylily-omics-analysis.git"
        assert repo["clone_transport"] == "ssh"
        assert repo["auth_mode"] == "aws_deploy_key"
        assert repo["default_ref"] == DAYOA_DEFAULT_TAG
        commands = {command["command_id"]: command for command in repo["analysis_commands"]}
        for command_id in (
            "hybrid_ilmn_ont_hiomr",
            "hybrid_ilmn_ont_hiomr_kitchensink",
            "hybrid_ilmn_ont_hiomr2_kitchensink_inflection_analytical",
            "betelgeuser_hiomr_prod_v1",
            "inflection-bjuice-product-v0.2",
            "hiomr2_slim_kitchensink_mega",
        ):
            assert commands[command_id]["git_tag"] == DAYOA_DEFAULT_TAG
            assert commands[command_id]["validated_version"] == DAYOA_VALIDATED_TAG
        assert commands["package_inflection_hybrid_data"]["git_tag"] == DAYOA_DEFAULT_TAG
        assert (
            commands["package_inflection_hybrid_data"]["validated_version"] == DAYOA_VALIDATED_TAG
        )
        assert (
            commands[
                "bjuice-v2-hg002-multi-analysis-unit-hiomr2-kitchensink-mega-inflection-analytical"
            ]["git_tag"]
            == BJUICE_V2_DAYOA_TARGET_TAG
        )
        assert (
            commands[
                "bjuice-v2-hg002-multi-analysis-unit-hiomr2-kitchensink-mega-inflection-analytical"
            ]["validated_version"]
            == BJUICE_V2_DAYOA_VALIDATED_TAG
        )
        assert data["dyec_builds"]["16.1.82"]["dayoa_git_tags"] == ["13.4.31"]
        assert data["dyec_builds"]["current"]["dayoa_git_tags"] == [DAYOA_DEFAULT_TAG]
        assert data["dyec_builds"]["16.1.85"]["dayoa_git_tags"] == ["13.4.33"]
        assert data["dyec_builds"]["16.1.86"]["dayoa_git_tags"] == ["13.4.34"]
        assert data["dyec_builds"]["17.0.0"]["dayoa_git_tags"] == ["14.0.0"]
        assert data["dyec_builds"]["17.0.1"]["dayoa_git_tags"] == ["14.0.2"]
        assert data["dyec_builds"]["17.0.2"]["dayoa_git_tags"] == ["14.0.3"]
        assert data["dyec_builds"]["17.0.3"]["dayoa_git_tags"] == ["14.0.4"]
        assert data["dyec_builds"]["17.0.4"]["dayoa_git_tags"] == ["14.0.6"]
        assert data["dyec_builds"]["17.0.5"]["dayoa_git_tags"] == ["14.0.7"]
        assert data["dyec_builds"]["17.0.6"]["dayoa_git_tags"] == ["14.0.8"]
        assert data["dyec_builds"]["17.0.7"]["dayoa_git_tags"] == ["14.0.9"]
        assert data["dyec_builds"]["17.0.8"]["dayoa_git_tags"] == ["14.0.9"]
        assert data["dyec_builds"]["17.0.9"]["dayoa_git_tags"] == ["14.0.10"]
        assert data["dyec_builds"]["17.0.10"]["dayoa_git_tags"] == ["14.0.11"]
        assert data["dyec_builds"]["17.0.11"]["dayoa_git_tags"] == ["14.0.13"]
        assert data["dyec_builds"]["17.0.12"]["dayoa_git_tags"] == ["14.0.13"]
        assert data["dyec_builds"]["17.0.13"]["dayoa_git_tags"] == ["14.0.14"]
        assert data["dyec_builds"]["17.0.14"]["dayoa_git_tags"] == ["14.0.14"]
        assert data["dyec_builds"]["17.0.15"]["dayoa_git_tags"] == [
            "14.0.14",
            "14.0.15",
        ]
        assert data["dyec_builds"]["17.0.16"]["dayoa_git_tags"] == ["14.0.16"]
        assert data["dyec_builds"]["17.0.17"]["dayoa_git_tags"] == [
            "14.0.14",
            "14.0.15",
        ]
        assert data["dyec_builds"]["17.0.29"]["dayoa_git_tags"] == ["14.0.22"]
        assert data["dyec_builds"]["current"] != data["dyec_builds"]["17.0.29"]
        current = data["dyec_builds"]["current"]
        assert set(current["commands"]) | set(current["aliases"]) == set(commands)
        assert "hiomr2_slim_kitchensink_mega_inflection_analytical" not in commands
        alias = current["aliases"]["inflection-bjuice-product-v0.2"]
        assert alias["alias_of"] == "hiomr2_slim_kitchensink_mega"


def test_dayoa_commands_use_the_scoped_release_pins() -> None:
    assert len(DAYOA_HIGHEST_RELEASE_COMMIT) == 40
    assert set(DAYOA_HIGHEST_RELEASE_COMMIT) <= set("0123456789abcdef")
    assert len(ONT_DAYOA_RELEASE_COMMIT) == 40
    assert set(ONT_DAYOA_RELEASE_COMMIT) <= set("0123456789abcdef")

    for relative_path in (
        "config/daylily_pipeline_command_catalog.yaml",
        "daylily_ec/resources/payload/config/daylily_pipeline_command_catalog.yaml",
    ):
        data = yaml.safe_load((REPO_ROOT / relative_path).read_text(encoding="utf-8"))
        commands = data["repositories"]["daylily-omics-analysis"]["analysis_commands"]
        command_by_id = {command["command_id"]: command for command in commands}
        uniform_commands = [
            command
            for command in commands
            if command["command_id"]
            not in {
                "ont_run_qc",
                "bjuice-v2-hg002-multi-analysis-unit-hiomr2-kitchensink-mega-inflection-analytical",
            }
        ]

        assert commands
        assert {command["git_tag"] for command in uniform_commands} == {DAYOA_DEFAULT_TAG}
        assert {command["validated_version"] for command in uniform_commands} == {
            DAYOA_VALIDATED_TAG
        }
        assert command_by_id["ont_run_qc"]["git_tag"] == ONT_DAYOA_TAG
        assert command_by_id["ont_run_qc"]["validated_version"] == ONT_DAYOA_VALIDATED_TAG
