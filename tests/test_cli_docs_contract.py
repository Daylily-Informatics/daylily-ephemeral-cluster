"""Keep living DYEC Markdown aligned with the shipped CLI contract."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from daylily_ec.cli import app
from daylily_ec.repositories import load_repository_catalog
from daylily_ec.versioning import get_version

REPO_ROOT = Path(__file__).resolve().parents[1]
CURRENT_OPERATOR_DOCS = (
    REPO_ROOT / "README.md",
    REPO_ROOT / "README.md.bland",
    REPO_ROOT / "docs" / "DAY_EC_ENVIRONMENT.md",
    REPO_ROOT / "docs" / "aws_setup.md",
    REPO_ROOT / "docs" / "cli_reference.md",
    REPO_ROOT / "docs" / "dra_fsx_strategy.md",
    REPO_ROOT / "docs" / "monitoring_and_troubleshooting.md",
    REPO_ROOT / "docs" / "operations.md",
    REPO_ROOT / "docs" / "overview.md",
    REPO_ROOT / "docs" / "pip_install.md",
    REPO_ROOT / "docs" / "quickest_start.md",
    REPO_ROOT / "docs" / "s3_bucket_lifecycle.md",
    REPO_ROOT / "docs" / "testing_and_debugging.md",
    REPO_ROOT / "docs" / "ultra_rapid_start.md",
)
ROOT_COMMANDS = (
    "set-vars",
    "unset-vars",
    "runtime-cache",
    "repositories",
    "catalog",
    "analysis",
    "mounts",
    "headnode",
)
RETIRED_CURRENT_DOC_TERMS = (
    "10.0.69",
    "9.0.0",
    "8.0.0",
    "1.0.16",
    "13.0.19",
    "13.0.20",
    "16.1.81",
    "hybrid_ilmn_ont_hiomrs_kitchensink",
    "Dewey",
    "artifact_registration",
    "--dewey-url",
    "--dewey-token-env",
)
RUN_CONTEXT_HEADER = "\t".join(
    (
        "RUNID",
        "PLATFORM",
        "RUN_DIR",
        "SOURCE_S3_URI",
        "MOUNT_ID",
        "SAMPLE_SHEET",
        "BASECALLING_STATE",
        "RUN_STATUS",
        "OUTPUT_ROOT",
        "REGION",
        "PROFILE",
    )
)


def _current_docs_text() -> str:
    return "\n".join(path.read_text(encoding="utf-8") for path in CURRENT_OPERATOR_DOCS)


def test_current_operator_docs_state_the_shipped_cli_and_catalog_versions() -> None:
    text = _current_docs_text()
    dayoa_tag = load_repository_catalog().repositories["daylily-omics-analysis"].default_ref
    release_version = get_version().partition(".dev")[0].partition("+")[0]

    # A release branch describes the next tag before that tag exists; an exact
    # release checkout reports the new tag once it has been created.
    assert release_version == "18.0.26"
    assert "`18.0.26`" in text
    assert dayoa_tag == "15.0.15"
    assert f"`{dayoa_tag}`" in text
    assert "dyec set-vars" in text
    assert "dyec unset-vars" in text
    assert "dyec -v" in text
    assert "validation_pending" in text
    assert "hybrid_ilmn_ont_hiomr_kitchensink" in text


def test_current_operator_docs_index_live_root_commands() -> None:
    result = CliRunner().invoke(app, ["--help"])
    assert result.exit_code == 0, result.output
    text = _current_docs_text()
    for command in ROOT_COMMANDS:
        assert command in result.output
        assert command in text


def test_current_operator_docs_exclude_retired_cli_and_metadata_service_claims() -> None:
    text = _current_docs_text()
    for term in RETIRED_CURRENT_DOC_TERMS:
        assert term not in text


def test_current_operator_docs_show_the_current_run_context_schema() -> None:
    for path in (REPO_ROOT / "README.md", REPO_ROOT / "docs" / "cli_reference.md"):
        text = path.read_text(encoding="utf-8")
        assert RUN_CONTEXT_HEADER in text
        assert "RUN_ID\tPLATFORM\tRUN_MOUNT" not in text
