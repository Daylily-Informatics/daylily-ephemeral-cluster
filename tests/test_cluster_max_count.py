from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from daylily_ec.workflow.cluster_max_count import (
    CLUSTER_MAX_COUNT_SCHEMA,
    ClusterMaxCountError,
    _wait_for_update,
    build_max_count_configuration,
    run_cluster_max_count_update,
)
from daylily_ec.workflow.compute_fleet import ClusterIdleProof


def _configuration(*, first: int = 8, second: int = 17) -> dict[str, object]:
    return {
        "Region": "us-west-2",
        "Scheduling": {
            "Scheduler": "slurm",
            "SlurmQueues": [
                {
                    "Name": "i8",
                    "ComputeResources": [{"Name": "price8", "MinCount": 0, "MaxCount": first}],
                },
                {
                    "Name": "i128",
                    "ComputeResources": [{"Name": "price128", "MinCount": 0, "MaxCount": second}],
                },
            ],
        },
    }


def _source_download(configuration: dict[str, object]):
    content = yaml.safe_dump(configuration, sort_keys=False).encode("utf-8")
    return configuration, content, hashlib.sha256(content).hexdigest()


def _describe(**_kwargs):
    return {
        "clusterName": "cluster-a",
        "clusterStatus": "UPDATE_COMPLETE",
        "clusterConfiguration": {"url": "https://example.amazonaws.com/config.yaml"},
    }


def test_build_max_count_configuration_changes_every_resource_only() -> None:
    source = _configuration()

    updated, changes = build_max_count_configuration(
        source,
        max_count=20,
        expected_resource_count=2,
    )

    assert source["Scheduling"]["SlurmQueues"][0]["ComputeResources"][0]["MaxCount"] == 8
    assert [row.before for row in changes] == [8, 17]
    assert [row.after for row in changes] == [20, 20]
    assert updated["Scheduling"]["SlurmQueues"][0]["ComputeResources"][0]["MaxCount"] == 20
    assert updated["Scheduling"]["SlurmQueues"][1]["ComputeResources"][0]["MaxCount"] == 20


def test_build_max_count_configuration_rejects_topology_drift() -> None:
    with pytest.raises(ClusterMaxCountError, match="Expected exactly 23"):
        build_max_count_configuration(
            _configuration(),
            max_count=20,
            expected_resource_count=23,
        )


def test_build_max_count_configuration_rejects_already_targeted_resource() -> None:
    with pytest.raises(ClusterMaxCountError, match="already has MaxCount 20"):
        build_max_count_configuration(
            _configuration(first=20),
            max_count=20,
            expected_resource_count=2,
        )


def test_dry_run_writes_exact_config_and_receipt_without_idle_probe(tmp_path: Path) -> None:
    source = _configuration()
    _configuration_value, _content, source_sha256 = _source_download(source)
    update_calls: list[bool] = []

    def update_fn(*_args, dry_run: bool, **_kwargs):
        update_calls.append(dry_run)
        return SimpleNamespace(success=True)

    result = run_cluster_max_count_update(
        cluster_name="cluster-a",
        region="us-west-2",
        profile="dev",
        max_count=20,
        expected_resource_count=2,
        expected_source_sha256=source_sha256,
        expected_cluster_status="UPDATE_COMPLETE",
        output_dir=tmp_path / "dry",
        apply=False,
        timeout_seconds=60,
        poll_interval_seconds=1,
        describe_fn=_describe,
        download_fn=lambda _details: _source_download(source),
        update_fn=update_fn,
        idle_probe_fn=lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("unexpected idle probe")
        ),
    )

    assert update_calls == [True]
    assert result.dry_run_only is True
    assert result.update_submitted is False
    assert len(result.changes) == 2
    receipt = json.loads((tmp_path / "dry" / "cluster_max_count_receipt.json").read_text())
    assert receipt["schema_version"] == CLUSTER_MAX_COUNT_SCHEMA
    assert receipt["provider_dry_run_validated"] is True
    update_config = yaml.safe_load((tmp_path / "dry" / "cluster_max_count_update.yaml").read_text())
    assert all(
        resource["MaxCount"] == 20
        for queue in update_config["Scheduling"]["SlurmQueues"]
        for resource in queue["ComputeResources"]
    )


def test_apply_requires_idle_then_submits_and_verifies(tmp_path: Path) -> None:
    source = _configuration()
    _configuration_value, _content, source_sha256 = _source_download(source)
    update_calls: list[bool] = []

    def update_fn(*_args, dry_run: bool, **_kwargs):
        update_calls.append(dry_run)
        return SimpleNamespace(success=True)

    idle = ClusterIdleProof(
        authoritative=True,
        controller_count=0,
        slurm_job_count=0,
        observed_at="2026-08-24T12:00:00Z",
        instance_id="i-abc",
        ssm_command_ids=("cmd-controller", "cmd-queue"),
    )

    result = run_cluster_max_count_update(
        cluster_name="cluster-a",
        region="us-west-2",
        profile="dev",
        max_count=20,
        expected_resource_count=2,
        expected_source_sha256=source_sha256,
        expected_cluster_status="UPDATE_COMPLETE",
        output_dir=tmp_path / "live",
        apply=True,
        timeout_seconds=60,
        poll_interval_seconds=1,
        describe_fn=_describe,
        download_fn=lambda _details: _source_download(source),
        update_fn=update_fn,
        idle_probe_fn=lambda **_kwargs: idle,
        wait_fn=lambda **_kwargs: ("UPDATE_COMPLETE", 3.0, "f" * 64),
    )

    assert update_calls == [True, False]
    assert result.update_submitted is True
    assert result.final_cluster_status == "UPDATE_COMPLETE"
    assert result.final_configuration_sha256 == "f" * 64
    assert result.idle_proof == idle


def test_apply_refuses_active_cluster_after_valid_dry_run(tmp_path: Path) -> None:
    source = _configuration()
    _configuration_value, _content, source_sha256 = _source_download(source)
    calls: list[bool] = []

    def update_fn(*_args, dry_run: bool, **_kwargs):
        calls.append(dry_run)
        return SimpleNamespace(success=True)

    active = ClusterIdleProof(
        authoritative=True,
        controller_count=1,
        slurm_job_count=4,
        observed_at="2026-08-24T12:00:00Z",
        instance_id="i-abc",
        ssm_command_ids=("cmd-controller", "cmd-queue"),
    )
    with pytest.raises(ClusterMaxCountError, match="active controllers or Slurm jobs remain"):
        run_cluster_max_count_update(
            cluster_name="cluster-a",
            region="us-west-2",
            profile="dev",
            max_count=20,
            expected_resource_count=2,
            expected_source_sha256=source_sha256,
            expected_cluster_status="UPDATE_COMPLETE",
            output_dir=tmp_path / "active",
            apply=True,
            timeout_seconds=60,
            poll_interval_seconds=1,
            describe_fn=_describe,
            download_fn=lambda _details: _source_download(source),
            update_fn=update_fn,
            idle_probe_fn=lambda **_kwargs: active,
        )
    assert calls == [True]


def test_wait_does_not_accept_stale_update_complete_configuration() -> None:
    source = _configuration()
    expected, _changes = build_max_count_configuration(
        source,
        max_count=20,
        expected_resource_count=2,
    )
    downloaded = iter(
        [
            (*_source_download(source)[:2], "a" * 64),
            (*_source_download(expected)[:2], "b" * 64),
        ]
    )
    clock_values = iter([0.0, 0.0, 1.0, 1.0])

    final_status, elapsed, final_sha = _wait_for_update(
        cluster_name="cluster-a",
        region="us-west-2",
        profile="dev",
        pcluster_executable="pcluster",
        expected_configuration=expected,
        max_count=20,
        expected_resource_count=2,
        timeout_seconds=10,
        poll_interval_seconds=1,
        describe_fn=_describe,
        download_fn=lambda _details: next(downloaded),
        monotonic_fn=lambda: next(clock_values),
        sleep_fn=lambda _seconds: None,
    )

    assert final_status == "UPDATE_COMPLETE"
    assert elapsed == 1.0
    assert final_sha == "b" * 64
