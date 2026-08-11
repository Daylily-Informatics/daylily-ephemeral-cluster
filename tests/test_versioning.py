from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

from typer.testing import CliRunner

from daylily_ec import versioning
from daylily_ec.resources import ensure_extracted

runner = CliRunner()


def test_get_version_prefers_source_tree(monkeypatch):
    versioning.get_version.cache_clear()
    monkeypatch.setattr(versioning, "_source_tree_version", lambda: "1.2.3")
    monkeypatch.setattr(
        versioning, "_installed_version", lambda dist_name=versioning.DIST_NAME: "9.9.9"
    )

    assert versioning.get_version() == "1.2.3"


def test_get_version_falls_back_to_installed_metadata(monkeypatch):
    versioning.get_version.cache_clear()
    monkeypatch.setattr(versioning, "_source_tree_version", lambda: None)
    monkeypatch.setattr(
        versioning, "_installed_version", lambda dist_name=versioning.DIST_NAME: "2.3.4"
    )

    assert versioning.get_version() == "2.3.4"


def test_source_tree_version_uses_repo_root_without_relative_to(monkeypatch):
    calls = {}

    monkeypatch.setattr(versioning, "_exact_source_tag", lambda root: None)

    def fake_get_version(**kwargs):
        calls.update(kwargs)
        return "8.9.10"

    monkeypatch.setitem(
        sys.modules,
        "setuptools_scm",
        SimpleNamespace(get_version=fake_get_version),
    )

    assert versioning._source_tree_version() == "8.9.10"
    assert calls["root"] == str(Path(versioning.__file__).resolve().parents[1])
    assert "relative_to" not in calls


def test_exact_source_tag_accepts_only_exact_semver_tags(monkeypatch):
    root = Path("/example/repository")
    calls = {}

    def fake_run(*args, **kwargs):
        calls["args"] = args
        calls["kwargs"] = kwargs
        return SimpleNamespace(returncode=0, stdout="16.1.68\n")

    monkeypatch.setattr(versioning.subprocess, "run", fake_run)

    assert versioning._exact_source_tag(root) == "16.1.68"
    assert calls["args"] == (
        ["git", "-C", str(root), "describe", "--tags", "--exact-match", "HEAD"],
    )
    assert calls["kwargs"] == {"check": False, "capture_output": True, "text": True}


def test_source_tree_version_prefers_exact_tag_before_setuptools_scm(monkeypatch):
    monkeypatch.setattr(versioning, "_exact_source_tag", lambda root: "16.1.68")

    assert versioning._source_tree_version() == "16.1.68"


def test_import_daylily_ec_is_lightweight_and_exports_create_cluster():
    original_modules = {
        name: module
        for name, module in sys.modules.items()
        if name == "daylily_ec" or name.startswith("daylily_ec.")
    }
    try:
        for name in original_modules:
            sys.modules.pop(name, None)

        import daylily_ec as reloaded_daylily_ec

        assert reloaded_daylily_ec.__version__
        assert "daylily_ec.create" not in sys.modules
        assert "daylily_ec.workflow" not in sys.modules
        assert "daylily_ec.workflow.export_data" not in sys.modules

        create_cluster = reloaded_daylily_ec.create_cluster

        assert callable(create_cluster)
        assert create_cluster.__module__ == "daylily_ec.create"
        assert "daylily_ec.create" in sys.modules
    finally:
        for name in tuple(sys.modules):
            if name == "daylily_ec" or name.startswith("daylily_ec."):
                sys.modules.pop(name, None)
        sys.modules.update(original_modules)


def test_cli_version_uses_source_aware_version():
    from daylily_ec.cli import app

    versioning.get_version.cache_clear()
    result = runner.invoke(app, ["--json", "version"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["version"] == versioning.get_version()
    assert payload["app"] == "Daylily Ephemeral Cluster"


def test_cli_info_uses_source_aware_version(monkeypatch, tmp_path):
    from daylily_ec.cli import spec

    versioning.get_version.cache_clear()
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))

    from cli_core_yo.app import create_app

    fresh_app = create_app(spec)
    result = runner.invoke(fresh_app, ["--json", "info"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["Version"] == versioning.get_version()
    assert payload["Config Dir"] == str((tmp_path / "config" / "daylily").resolve())
    assert "CLI Core" in payload


def test_resources_dir_uses_repo_version_resolver(tmp_path, monkeypatch):
    versioning.get_version.cache_clear()
    monkeypatch.setattr(versioning, "get_version", lambda: "5.6.7")
    monkeypatch.delenv("DAYLILY_EC_RESOURCES_DIR", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

    root = ensure_extracted()

    assert root.name == "5.6.7"
