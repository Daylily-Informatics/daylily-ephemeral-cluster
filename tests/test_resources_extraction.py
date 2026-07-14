from __future__ import annotations

from pathlib import Path

import pytest

from daylily_ec.resources import INTEL_TEMPLATE_REGION_AZS, ensure_extracted, resource_path


def test_ensure_extracted_extracts_expected_files(tmp_path, monkeypatch):
    # Avoid writing into the developer's real ~/.config during tests.
    monkeypatch.delenv("DAYLILY_EC_RESOURCES_DIR", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

    root = ensure_extracted()
    assert root.is_dir()

    for az in INTEL_TEMPLATE_REGION_AZS:
        assert (
            root
            / f"config/day_cluster/intel/{az[:-1]}/{az}/prod_cluster_intel_{az}.yaml"
        ).is_file()
    sentieon_single = (
        root / "config/day_cluster/sentieon-single/us-west-2/us-west-2c/"
        "prod_cluster_sentieon-single_us-west-2c.yaml"
    )
    assert sentieon_single.is_file()
    assert not (
        root
        / "config/day_cluster/prod_cluster_nested_spot_mem_scratch_intel_avx512_expanded.yaml"
    ).exists()
    assert (root / "config/day_cluster/pcluster_env.yml").is_file()
    assert (root / "environment.yaml").is_file()
    assert (root / "etc/analysis_samples_template.tsv").is_file()
    assert not (root / "quarantine").exists()
    with pytest.raises(FileNotFoundError):
        resource_path("quarantine/README.md")

    # resource_path should return the same filesystem location.
    p = resource_path(
        "config/day_cluster/intel/us-west-2/us-west-2d/prod_cluster_intel_us-west-2d.yaml"
    )
    assert isinstance(p, Path)
    assert p.is_file()
    assert (
        resource_path(
            "config/day_cluster/sentieon-single/us-west-2/us-west-2c/"
            "prod_cluster_sentieon-single_us-west-2c.yaml"
        )
        == sentieon_single
    )


def test_ensure_extracted_refreshes_stale_boot_scripts(tmp_path, monkeypatch):
    monkeypatch.delenv("DAYLILY_EC_RESOURCES_DIR", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

    root = ensure_extracted()
    boot_script = root / "config/day_cluster/post_install_ubuntu_combined.sh"
    boot_script.write_text("stale boot script\n", encoding="utf-8")

    refreshed = ensure_extracted()

    assert refreshed == root
    assert "stale boot script" not in boot_script.read_text(encoding="utf-8")
