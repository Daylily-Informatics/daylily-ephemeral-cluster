from __future__ import annotations

from pathlib import Path

from daylily_ec.resources import ensure_extracted, resource_path


def test_ensure_extracted_extracts_expected_files(tmp_path, monkeypatch):
    # Avoid writing into the developer's real ~/.config during tests.
    monkeypatch.delenv("DAYLILY_EC_RESOURCES_DIR", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

    root = ensure_extracted()
    assert root.is_dir()

    assert (root / "config/day_cluster/prod_cluster.yaml").is_file()
    assert (root / "config/day_cluster/pcluster_env.yml").is_file()
    assert (root / "etc/analysis_samples_template.tsv").is_file()

    # resource_path should return the same filesystem location.
    p = resource_path("config/day_cluster/prod_cluster.yaml")
    assert isinstance(p, Path)
    assert p.is_file()

