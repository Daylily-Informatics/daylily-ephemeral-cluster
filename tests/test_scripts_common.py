from __future__ import annotations

import os

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
