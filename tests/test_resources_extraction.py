from __future__ import annotations

from pathlib import Path

import pytest

from daylily_ec.resources import ensure_extracted, resource_path


def test_ensure_extracted_extracts_expected_files(tmp_path, monkeypatch):
    # Avoid writing into the developer's real ~/.config during tests.
    monkeypatch.delenv("DAYLILY_EC_RESOURCES_DIR", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

    root = ensure_extracted()
    assert root.is_dir()

    assert (root / "config/day_cluster/prod_cluster_v8.yaml").is_file()
    assert (root / "config/day_cluster/prod_cluster.yaml").is_file()
    assert (root / "config/day_cluster/pcluster_env.yml").is_file()
    assert (root / "environment.yaml").is_file()
    assert (root / "etc/analysis_samples_template.tsv").is_file()
    assert not (root / "quarantine").exists()
    with pytest.raises(FileNotFoundError):
        resource_path("quarantine/README.md")

    # resource_path should return the same filesystem location.
    p = resource_path("config/day_cluster/prod_cluster_v8.yaml")
    assert isinstance(p, Path)
    assert p.is_file()


def test_ensure_extracted_refreshes_stale_boot_scripts(tmp_path, monkeypatch):
    monkeypatch.delenv("DAYLILY_EC_RESOURCES_DIR", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

    root = ensure_extracted()
    boot_script = root / "config/day_cluster/post_install_ubuntu_combined.sh"
    boot_script.write_text("stale boot script\n", encoding="utf-8")

    refreshed = ensure_extracted()

    assert refreshed == root
    assert "stale boot script" not in boot_script.read_text(encoding="utf-8")
