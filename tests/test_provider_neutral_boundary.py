"""Regression blockers for DYEC's provider-neutral identity boundary."""

from __future__ import annotations

import ast
from pathlib import Path

from typer.testing import CliRunner

from daylily_ec.cli import app


ROOT = Path(__file__).resolve().parents[1]
ACTIVE_SURFACES = (
    ROOT / "daylily_ec" / "cli.py",
    ROOT / "daylily_ec" / "manifest_set.py",
    ROOT / "daylily_ec" / "identity_receipts.py",
    ROOT / "daylily_ec" / "scripts" / "daylily_run_omics_analysis_headnode.py",
    ROOT / "daylily_ec" / "workflow" / "create_cluster.py",
    ROOT / "daylily_ec" / "workflow" / "export_data.py",
    ROOT / "config" / "daylily_pipeline_command_catalog.yaml",
    ROOT / "daylily_ec" / "resources" / "payload" / "config"
    / "daylily_pipeline_command_catalog.yaml",
)
FORBIDDEN_PROVIDER_TOKENS = ("dayhoff", "ursa", "bloom", "tapdb", "dewey")


def test_active_dyec_surfaces_have_no_provider_names_or_registration_aliases() -> None:
    violations: list[str] = []
    for path in ACTIVE_SURFACES:
        lowered = path.read_text(encoding="utf-8").lower()
        for token in FORBIDDEN_PROVIDER_TOKENS:
            if token in lowered:
                violations.append(f"{path.relative_to(ROOT)}:{token}")
    assert violations == []
    assert not (ROOT / "daylily_ec" / "workflow" / "dewey_registration.py").exists()


def test_offline_identity_modules_import_no_network_clients() -> None:
    forbidden_import_roots = {
        "boto3",
        "botocore",
        "http",
        "httpx",
        "requests",
        "socket",
        "urllib",
    }
    for relative in ("daylily_ec/manifest_set.py", "daylily_ec/identity_receipts.py"):
        path = ROOT / relative
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imports: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module.split(".", 1)[0])
        assert not imports & forbidden_import_roots, (relative, imports)


def test_cli_exposes_local_identity_commands_without_url_or_token_options(monkeypatch) -> None:
    monkeypatch.setenv("CONDA_PREFIX", "/tmp/dayec")
    monkeypatch.setenv("CONDA_DEFAULT_ENV", "DAY-EC")
    runner = CliRunner()
    for command in ("validate", "plan", "apply", "status", "evidence"):
        result = runner.invoke(app, ["identities", command, "--help"])
        assert result.exit_code == 0
        lowered = result.output.lower()
        assert "--url" not in lowered
        assert "--token" not in lowered
        assert "http" not in lowered


def test_runtime_source_and_packaged_payloads_match() -> None:
    pairs = (
        (
            ROOT / "config" / "day_cluster" / "sbatch",
            ROOT / "daylily_ec" / "resources" / "payload" / "config"
            / "day_cluster" / "sbatch",
        ),
        (
            ROOT / "config" / "daylily_ephemeral_cluster_template.yaml",
            ROOT / "daylily_ec" / "resources" / "payload" / "config"
            / "daylily_ephemeral_cluster_template.yaml",
        ),
        (
            ROOT / "config" / "daylily_pipeline_command_catalog.yaml",
            ROOT / "daylily_ec" / "resources" / "payload" / "config"
            / "daylily_pipeline_command_catalog.yaml",
        ),
    )
    for source, payload in pairs:
        assert source.read_bytes() == payload.read_bytes(), (source, payload)
