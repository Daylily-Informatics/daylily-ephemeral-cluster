from __future__ import annotations

from importlib.metadata import version as dist_version
import json

from typer.testing import CliRunner

from daylily_ec import versioning
from daylily_ec.cli import app, spec
from daylily_ec.resources import ensure_extracted

runner = CliRunner()


def test_get_version_prefers_source_tree(monkeypatch):
    versioning.get_version.cache_clear()
    monkeypatch.setattr(versioning, "_source_tree_version", lambda: "1.2.3")
    monkeypatch.setattr(versioning, "_installed_version", lambda dist_name=versioning.DIST_NAME: "9.9.9")

    assert versioning.get_version() == "1.2.3"


def test_get_version_falls_back_to_installed_metadata(monkeypatch):
    versioning.get_version.cache_clear()
    monkeypatch.setattr(versioning, "_source_tree_version", lambda: None)
    monkeypatch.setattr(versioning, "_installed_version", lambda dist_name=versioning.DIST_NAME: "2.3.4")

    assert versioning.get_version() == "2.3.4"


def test_cli_version_uses_installed_dist_metadata():
    result = runner.invoke(app, ["--json", "version"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["version"] == dist_version("daylily-ephemeral-cluster")
    assert payload["app"] == "Daylily Ephemeral Cluster"


def test_cli_info_uses_installed_dist_metadata(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))

    from cli_core_yo.app import create_app

    fresh_app = create_app(spec)
    result = runner.invoke(fresh_app, ["--json", "info"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["Version"] == dist_version("daylily-ephemeral-cluster")
    assert payload["Config Dir"] == str((tmp_path / "config" / "daylily").resolve())
    assert "CLI Core" in payload


def test_resources_dir_uses_repo_version_resolver(tmp_path, monkeypatch):
    versioning.get_version.cache_clear()
    monkeypatch.setattr(versioning, "get_version", lambda: "5.6.7")
    monkeypatch.delenv("DAYLILY_EC_RESOURCES_DIR", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

    root = ensure_extracted()

    assert root.name == "5.6.7"
