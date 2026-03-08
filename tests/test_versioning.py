from __future__ import annotations

from typer.testing import CliRunner

from daylily_ec import versioning
from daylily_ec.cli import app
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


def test_cli_version_uses_shared_version_resolver(monkeypatch):
    versioning.get_version.cache_clear()
    monkeypatch.setattr(versioning, "get_version", lambda: "3.4.5")

    result = runner.invoke(app, ["version"])

    assert result.exit_code == 0
    assert "3.4.5" in result.stdout


def test_cli_info_uses_shared_version_resolver(monkeypatch):
    versioning.get_version.cache_clear()
    monkeypatch.setattr(versioning, "get_version", lambda: "4.5.6")

    result = runner.invoke(app, ["info"])

    assert result.exit_code == 0
    assert "4.5.6" in result.stdout


def test_resources_dir_uses_shared_version_resolver(tmp_path, monkeypatch):
    versioning.get_version.cache_clear()
    monkeypatch.setattr(versioning, "get_version", lambda: "5.6.7")
    monkeypatch.delenv("DAYLILY_EC_RESOURCES_DIR", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

    root = ensure_extracted()

    assert root.name == "5.6.7"
