from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from daylily_ec.aws.ssm import SsmCommandFailedError, SsmCommandResult
from daylily_ec.headnode_readiness import (
    REQUIRED_HEADNODE_WORK_DIRECTORIES,
    REQUIRED_ROLE_DIRECTORIES,
    REQUIRED_ROLE_FILES,
    REQUIRED_WRITABLE_CACHE_DIRECTORY_TEMPLATES,
    build_headnode_readiness_script,
    validate_headnode_readiness,
)


def test_readiness_script_requires_day_ec_tools_and_fsx_reference_assets():
    script = build_headnode_readiness_script()

    assert 'script -q -c "bash -lc' in script
    assert 'test "$(id -un)" = ubuntu' in script
    assert "DAYLILY_EC_HEADNODE_BOOTSTRAPPED" in script
    assert "CONDA_DEFAULT_ENV:-}" in script
    assert "= DAY-EC" in script
    assert "command -v daylily-ec" in script
    assert "command -v day-clone" in script
    assert "day-clone --list >/dev/null" in script
    assert "day-clone --check-auth --repository daylily-omics-analysis" in script
    assert "stty -a" in script
    assert "-ixon" in script
    assert "df -P /fsx >/dev/null" in script
    assert "test -d /data" not in script
    assert "test -L /fsx/data" in script
    assert 'test "$(readlink -f /fsx/data)" = /fsx/references' in script
    for path in REQUIRED_ROLE_FILES:
        assert f"test -s {path}" in script
    for path in REQUIRED_ROLE_DIRECTORIES:
        assert f"test -d {path}" in script
    for template in REQUIRED_WRITABLE_CACHE_DIRECTORY_TEMPLATES:
        assert f"test -d {template.format(hostname='$(hostname)')}" in script
    for path in REQUIRED_HEADNODE_WORK_DIRECTORIES:
        assert f"test -d {path}" in script
    assert "test -r /etc/profile.d/daylily-runtime-cache.sh" in script
    assert "DAYLILY_CONTAINER_CACHE" in script
    assert "DAYLILY_APPTAINER_CACHE" in script
    assert "DAYLILY_NEXTFLOW_SEED_CACHE" in script
    assert "NXF_SINGULARITY_CACHEDIR" in script


def test_readiness_script_can_target_ec2_user():
    script = build_headnode_readiness_script(remote_user="ec2-user")

    assert 'test "$(id -un)" = ec2-user' in script
    assert 'test "$(id -un)" = ubuntu' not in script
    assert "DAYLILY_EC_HEADNODE_BOOTSTRAPPED" in script
    assert "day-clone --list >/dev/null" in script
    assert "day-clone --check-auth --repository daylily-omics-analysis" in script


def test_validate_headnode_readiness_runs_shared_script_as_ubuntu():
    expected = SimpleNamespace(command_id="cmd-ready")

    with patch("daylily_ec.headnode_readiness.run_shell", return_value=expected) as mock_run_shell:
        result = validate_headnode_readiness(
            "i-abc123",
            "us-west-2",
            profile="test",
            timeout=99,
            comment="custom readiness",
        )

    assert result is expected
    instance_id, region, script = mock_run_shell.call_args.args
    assert instance_id == "i-abc123"
    assert region == "us-west-2"
    assert "day-clone --list" in script
    assert "day-clone --check-auth --repository daylily-omics-analysis" in script
    assert "/fsx/references/genomic_data" in script
    assert "/fsx/resources/environments/conda/ubuntu/$(hostname)" in script
    assert "/fsx/resources/environments/containers/ubuntu/$(hostname)" in script
    assert "/fsx/work/ubuntu/containers" in script
    assert "/fsx/work/ubuntu/nextflow" in script
    assert "/fsx/work/ubuntu/sarek" in script
    assert "/fsx/run_dir_mounts" in script
    assert "/etc/profile.d/daylily-runtime-cache.sh" in script
    assert "/fsx/control_data/genomic_data" not in script
    assert "test ! -e /fsx/runtime_assets" in script
    assert "test -L /fsx/data" in script
    assert 'test "$(readlink -f /fsx/data)" = /fsx/references' in script
    assert mock_run_shell.call_args.kwargs == {
        "profile": "test",
        "as_user": "ubuntu",
        "timeout": 99,
        "comment": "custom readiness",
    }


def test_validate_headnode_readiness_can_run_as_ec2_user():
    expected = SimpleNamespace(command_id="cmd-ready")

    with patch("daylily_ec.headnode_readiness.run_shell", return_value=expected) as mock_run_shell:
        result = validate_headnode_readiness(
            "i-drg123",
            "us-west-2",
            profile="test",
            remote_user="ec2-user",
        )

    assert result is expected
    _instance_id, _region, script = mock_run_shell.call_args.args
    assert 'test "$(id -un)" = ec2-user' in script
    assert mock_run_shell.call_args.kwargs["as_user"] == "ec2-user"


def test_validate_headnode_readiness_propagates_ssm_failures():
    failure = SsmCommandFailedError(
        "readiness failed",
        SsmCommandResult(
            command_id="cmd-1",
            instance_id="i-abc123",
            status="Failed",
            response_code=1,
            stdout="",
            stderr="missing /fsx/references/runtime_assets/cached_envs/conda",
        ),
    )

    with patch("daylily_ec.headnode_readiness.run_shell", side_effect=failure):
        with pytest.raises(SsmCommandFailedError, match="readiness failed"):
            validate_headnode_readiness("i-abc123", "us-west-2", profile="test")
