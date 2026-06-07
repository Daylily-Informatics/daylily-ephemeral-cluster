from __future__ import annotations

import os
import subprocess
from types import SimpleNamespace

import pytest

from daylily_ec.scripts import common


def test_need_cmd_respects_current_process_path_without_shell(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    fakebin = tmp_path / "fakebin"
    fakebin.mkdir()
    fake_tool = fakebin / "fake-tool"
    fake_tool.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    fake_tool.chmod(0o755)
    monkeypatch.setenv("PATH", str(fakebin))

    def fail_if_shell_lookup_is_used(*_args, **_kwargs):
        raise AssertionError("need_cmd should use shutil.which(), not a shell")

    monkeypatch.setattr(common.subprocess, "run", fail_if_shell_lookup_is_used)

    common.need_cmd("fake-tool")


def test_need_cmd_raises_for_missing_command(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setenv("PATH", str(tmp_path))

    with pytest.raises(common.CommandError, match="Missing required command: missing-tool"):
        common.need_cmd("missing-tool")


def test_run_command_still_uses_subprocess_run() -> None:
    result = common.run_command(
        ["python", "-c", "print('ok')"],
        capture_output=True,
        env={**os.environ},
    )

    assert result.stdout.strip() == "ok"
    assert result.returncode == 0


def test_aws_env_sets_profile_region_and_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AWS_DEFAULT_REGION", raising=False)

    env = common.aws_env(profile="lsmc", region="us-west-2")

    assert env["AWS_PROFILE"] == "lsmc"
    assert env["AWS_REGION"] == "us-west-2"
    assert env["AWS_DEFAULT_REGION"] == "us-west-2"


def test_run_command_wraps_subprocess_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_called_process(*_args, **_kwargs):
        raise subprocess.CalledProcessError(
            4,
            ["tool", "arg"],
            output="out",
            stderr="err",
        )

    monkeypatch.setattr(common.subprocess, "run", fail_called_process)

    with pytest.raises(common.CommandError, match="Command failed \\(4\\): tool arg"):
        common.run_command(["tool", "arg"])


def test_run_command_wraps_missing_executable(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_file_not_found(*_args, **_kwargs):
        raise FileNotFoundError("missing")

    monkeypatch.setattr(common.subprocess, "run", fail_file_not_found)

    with pytest.raises(common.CommandError, match="Command not found: missing-tool"):
        common.run_command(["missing-tool"])


def test_choose_from_single_empty_and_interactive(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    assert common.choose_from("Pick:", ["only"]) == "only"
    with pytest.raises(common.CommandError, match="No options available"):
        common.choose_from("Pick:", [])

    answers = iter(["abc", "9", "2"])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(answers))

    assert common.choose_from("Pick:", ["first", "second"]) == "second"
    output = capsys.readouterr().out
    assert "Please enter a number." in output
    assert "Selection out of range" in output


def test_resolve_region_uses_explicit_env_default_and_prompt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert common.resolve_region("lsmc", explicit="us-west-2") == "us-west-2"

    def fake_run_region(_command, **_kwargs):
        return SimpleNamespace(
            stdout='{"Regions":[{"RegionName":"us-east-1"},{"RegionName":"us-west-2"}]}'
        )

    monkeypatch.setattr(common, "run_command", fake_run_region)
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    assert common.resolve_region("lsmc") == "us-east-1"

    monkeypatch.delenv("AWS_REGION", raising=False)
    monkeypatch.delenv("AWS_DEFAULT_REGION", raising=False)
    monkeypatch.setattr(common, "choose_from", lambda _prompt, options: options[-1])
    assert common.resolve_region("lsmc") == "us-west-2"


def test_resolve_region_and_cluster_error_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(common, "run_command", lambda *_args, **_kwargs: SimpleNamespace(stdout="{}"))

    with pytest.raises(common.CommandError, match="Unable to retrieve AWS regions"):
        common.resolve_region("lsmc")

    assert common.resolve_cluster("lsmc", "us-west-2", explicit="dyec800") == "dyec800"

    with pytest.raises(common.CommandError, match="No ParallelCluster clusters"):
        common.resolve_cluster("lsmc", "us-west-2")


def test_resolve_cluster_lists_and_prompts(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run_clusters(_command, **_kwargs):
        return SimpleNamespace(
            stdout='{"clusters":[{"clusterName":"zeta"},{"clusterName":""},{"clusterName":"alpha"}]}'
        )

    monkeypatch.setattr(common, "run_command", fake_run_clusters)
    monkeypatch.setattr(common, "choose_from", lambda _prompt, options: options[0])

    assert common.resolve_cluster("lsmc", "us-west-2") == "alpha"
