from __future__ import annotations

import multiprocessing
import os
from multiprocessing.queues import Queue
from multiprocessing.synchronize import Barrier
from pathlib import Path

import pytest

from daylily_ec.resources import (
    HG002_BJUICE_VERIFIED_5X5X_RESOURCE_RELPATHS,
    HG003_HIOMRS_1X_MANIFEST_RELPATHS,
    INTEL_TEMPLATE_REGION_AZS,
    ensure_extracted,
    resource_path,
)


def _extract_resources_concurrently(
    config_home: str,
    start_barrier: Barrier,
    results: Queue,
) -> None:
    os.environ.pop("DAYLILY_EC_RESOURCES_DIR", None)
    os.environ["XDG_CONFIG_HOME"] = config_home
    start_barrier.wait()
    try:
        results.put(("ok", str(ensure_extracted())))
    except Exception as exc:  # pragma: no cover - reported to the parent process
        results.put(("error", repr(exc)))


def test_ensure_extracted_extracts_expected_files(tmp_path, monkeypatch):
    # Avoid writing into the developer's real ~/.config during tests.
    monkeypatch.delenv("DAYLILY_EC_RESOURCES_DIR", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

    root = ensure_extracted()
    assert root.is_dir()
    for relative_path in HG003_HIOMRS_1X_MANIFEST_RELPATHS:
        assert (root / relative_path).is_file()
    for relative_path in HG002_BJUICE_VERIFIED_5X5X_RESOURCE_RELPATHS:
        assert (root / relative_path).is_file()

    for az in INTEL_TEMPLATE_REGION_AZS:
        assert (
            root
            / f"config/day_cluster/intel/{az[:-1]}/{az}/prod_cluster_intel_spot_{az}.yaml"
        ).is_file()
        assert (
            root
            / f"config/day_cluster/intel/{az[:-1]}/{az}/"
            f"prod_cluster_intel_ondemand_{az}.yaml"
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
        "config/day_cluster/intel/us-west-2/us-west-2d/prod_cluster_intel_spot_us-west-2d.yaml"
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


def test_ensure_extracted_serializes_concurrent_cold_cache_publish(tmp_path):
    process_count = 4
    context = multiprocessing.get_context("spawn")
    start_barrier = context.Barrier(process_count)
    results = context.Queue()
    config_home = str(tmp_path / "xdg")
    processes = [
        context.Process(
            target=_extract_resources_concurrently,
            args=(config_home, start_barrier, results),
        )
        for _ in range(process_count)
    ]

    for process in processes:
        process.start()
    for process in processes:
        process.join(timeout=60)

    assert all(not process.is_alive() for process in processes)
    assert [process.exitcode for process in processes] == [0] * process_count
    outcomes = [results.get(timeout=5) for _ in range(process_count)]
    assert {status for status, _ in outcomes} == {"ok"}
    assert len({path for _, path in outcomes}) == 1
    extracted = Path(outcomes[0][1])
    assert (extracted / ".complete").is_file()
    assert not list(extracted.parent.glob(f"{extracted.name}.tmp-*"))
