from __future__ import annotations

from pathlib import Path
import click
import pytest
import typer

import daylily_ec.cli as cli


def _capture_output(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    values: list[str] = []
    monkeypatch.setattr(cli.output, "heading", values.append)
    monkeypatch.setattr(cli.output, "print_text", values.append)
    monkeypatch.setattr(cli.output, "emit_json", lambda payload: values.append(str(payload)))
    monkeypatch.setattr(cli.typer, "echo", lambda value, **kwargs: values.append(str(value)))
    return values


@pytest.mark.parametrize(
    "changes",
    [
        {"dry_run": True, "set": {"a": "1"}, "deleted": ["old"]},
        {"updated": True, "waited": True},
        {"updated": True, "waited": False},
        {},
    ],
)
def test_emit_cluster_tags_text_all_outcomes(
    monkeypatch: pytest.MonkeyPatch,
    changes: dict[str, object],
) -> None:
    output = _capture_output(monkeypatch)
    payload: dict[str, object] = {
        "cluster": "alpha",
        "region": "us-west-2",
        "dry_run": False,
        "updated": False,
        "waited": False,
        "stack_id": "stack",
        "stack_status": "UPDATE_COMPLETE",
        "set": {},
        "deleted": [],
        "after": {"z": "last", "a": "first"},
    }
    payload.update(changes)
    cli._emit_cluster_tags_text(payload)
    rendered = "\n".join(output)
    assert "alpha" in rendered
    assert "Stack:  stack" in rendered
    assert "a" in rendered and "z" in rendered


def test_cluster_headnode_configuration_runtime_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import daylily_ec.aws.ssm as ssm

    monkeypatch.setattr(
        ssm,
        "run_shell",
        lambda *args, **kwargs: (_ for _ in ()).throw(TimeoutError("offline")),
    )
    row: dict[str, object] = {"name": "alpha", "instance_id": "i-head"}
    cli._cluster_headnode_config_status(row, profile="p", region="r")
    assert row["headnode_configured"] is False
    assert row["headnode_config_error"] == "offline"


def test_state_list_empty_and_mixed_rows(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import daylily_ec.state.store as store

    output = _capture_output(monkeypatch)
    monkeypatch.setattr(cli, "_json_mode", lambda: False)
    monkeypatch.setattr(store, "config_dir", lambda: tmp_path)
    cli.state_list()
    assert "No state files found" in output[-1]

    good = tmp_path / "state_a.json"
    bad = tmp_path / "state_b.json"
    good.write_text("{}", encoding="utf-8")
    bad.write_text("{}", encoding="utf-8")

    def payload(path: Path) -> dict[str, object]:
        if path == bad:
            raise ValueError("malformed")
        return {
            "cluster_name": "alpha",
            "run_id": "run-1",
            "region": "us-west-2",
            "path": str(path),
        }

    monkeypatch.setattr(cli, "_state_payload", payload)
    cli.state_list()
    rendered = "\n".join(output)
    assert "Daylily state files" in rendered
    assert "alpha" in rendered
    assert "ERROR" in rendered


def test_latest_state_skips_bad_files_and_selects_latest(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import daylily_ec.state.store as store

    paths = [tmp_path / name for name in ("state_bad.json", "state_1.json", "state_2.json")]
    for path in paths:
        path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(store, "config_dir", lambda: tmp_path)

    def payload(path: Path) -> dict[str, object]:
        if "bad" in path.name:
            raise ValueError("bad")
        return {
            "cluster_name": "alpha",
            "run_id": path.stem[-1],
            "path": str(path),
        }

    monkeypatch.setattr(cli, "_state_payload", payload)
    assert cli._latest_state_for_cluster("alpha")["run_id"] == "2"
    with pytest.raises(Exception, match="No state file"):
        cli._latest_state_for_cluster("missing")


def test_state_show_text_and_argument_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    output = _capture_output(monkeypatch)
    monkeypatch.setattr(cli, "_json_mode", lambda: False)
    path = tmp_path / "state.json"
    path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(cli, "_state_payload", lambda value: {"path": str(value), "run_id": "1"})
    cli.state_show(path, None)
    assert '"run_id": "1"' in output[-1]

    class HeadnodeExit(RuntimeError):
        pass

    monkeypatch.setattr(
        cli, "_exit_headnode_error", lambda exc: (_ for _ in ()).throw(HeadnodeExit(str(exc)))
    )
    with pytest.raises(HeadnodeExit, match="exactly one"):
        cli.state_show(None, None)


def test_emit_analysis_payload_modes(monkeypatch: pytest.MonkeyPatch) -> None:
    output = _capture_output(monkeypatch)
    monkeypatch.setattr(cli, "_json_mode", lambda: True)
    cli._emit_analysis_payload({"ok": True}, text="human")
    monkeypatch.setattr(cli, "_json_mode", lambda: False)
    cli._emit_analysis_payload({"ok": True}, text="human")
    cli._emit_analysis_payload({"ok": True})
    assert "{'ok': True}" in output[0]
    assert output[1] == "human"
    assert '"ok": true' in output[2]


def test_analysis_guard_command_reraises_exit(monkeypatch: pytest.MonkeyPatch) -> None:
    import daylily_ec.analysis_lock as locks

    monkeypatch.setattr(locks, "guarded_run", lambda *args, **kwargs: 7)
    with pytest.raises(typer.Exit) as exc_info:
        cli.analysis_guard("/analysis", "write", "intent", None, ["command"])
    assert exc_info.value.exit_code == 7


def test_analysis_lock_status_locked_and_unlocked(monkeypatch: pytest.MonkeyPatch) -> None:
    import daylily_ec.analysis_lock as locks

    emitted: list[tuple[object, str | None]] = []
    monkeypatch.setattr(
        cli,
        "_emit_analysis_payload",
        lambda payload, text=None: emitted.append((payload, text)),
    )
    responses = iter(
        [
            {"locked": False, "owner": None},
            {"locked": True, "owner": {"agent_id": "agent-a"}},
        ]
    )
    monkeypatch.setattr(locks, "lock_status", lambda root: next(responses))
    cli.analysis_lock_status("/analysis")
    cli.analysis_lock_status("/analysis")
    assert [text for _, text in emitted] == ["unlocked", "locked by agent-a"]


def test_analysis_release_and_heartbeat_forwarding(monkeypatch: pytest.MonkeyPatch) -> None:
    import daylily_ec.analysis_lock as locks

    calls: list[tuple[str, dict[str, object]]] = []
    monkeypatch.setattr(
        locks,
        "release_lock",
        lambda root, **kwargs: calls.append((root, kwargs)) or {"released": True},
    )
    monkeypatch.setattr(
        locks,
        "heartbeat_lock",
        lambda root, **kwargs: calls.append((root, kwargs)) or {"heartbeat": True},
    )
    monkeypatch.setattr(cli, "_emit_analysis_payload", lambda *args, **kwargs: None)
    cli.analysis_lock_release("/analysis", "human", "done")
    cli.analysis_lock_heartbeat("/analysis", "human", "alive")
    assert calls == [
        ("/analysis", {"human_requestor": "human", "note": "done"}),
        ("/analysis", {"human_requestor": "human", "note": "alive"}),
    ]


def test_analysis_takeover_request_and_execution(monkeypatch: pytest.MonkeyPatch) -> None:
    import daylily_ec.analysis_lock as locks

    emitted: list[tuple[object, str | None]] = []
    monkeypatch.setattr(
        locks,
        "takeover_request",
        lambda root, **kwargs: {
            "token": "token",
            "analysis_root": root,
            "operation": kwargs["operation"],
        },
    )
    forwarded: list[dict[str, object]] = []
    monkeypatch.setattr(
        locks,
        "takeover_lock",
        lambda root, **kwargs: forwarded.append({"root": root, **kwargs}) or {"taken": True},
    )
    monkeypatch.setattr(
        cli,
        "_emit_analysis_payload",
        lambda payload, text=None: emitted.append((payload, text)),
    )
    cli.analysis_lock_takeover(
        "/analysis", "kill", "stale", True, None, None, "intent", "human", "command"
    )
    cli.analysis_lock_takeover(
        "/analysis", "kill", "stale", False, "token", "approver", "intent", "human", "command"
    )
    assert "takeover token token" in str(emitted[0][1])
    assert forwarded[0]["confirm_token"] == "token"
    assert forwarded[0]["approved_by"] == "approver"


def test_analysis_takeover_requires_confirmation(monkeypatch: pytest.MonkeyPatch) -> None:
    class HeadnodeExit(RuntimeError):
        pass

    monkeypatch.setattr(
        cli, "_exit_headnode_error", lambda exc: (_ for _ in ()).throw(HeadnodeExit(str(exc)))
    )
    with pytest.raises(HeadnodeExit, match="confirm-token"):
        cli.analysis_lock_takeover(
            "/analysis", "write", "reason", False, None, None, "intent", None, None
        )


def test_analysis_wrapper_failures_use_headnode_error(monkeypatch: pytest.MonkeyPatch) -> None:
    import daylily_ec.analysis_lock as locks

    class HeadnodeExit(RuntimeError):
        pass

    def fail(*args, **kwargs):
        raise ValueError("lock failure")

    monkeypatch.setattr(
        cli, "_exit_headnode_error", lambda exc: (_ for _ in ()).throw(HeadnodeExit(str(exc)))
    )
    for name, invoke in (
        (
            "write_visit",
            lambda: cli.analysis_visit("/analysis", "intent", "read", None, None, None),
        ),
        (
            "acquire_lock",
            lambda: cli.analysis_lock_acquire("/analysis", "write", "intent", None, None, None),
        ),
        (
            "release_lock",
            lambda: cli.analysis_lock_release("/analysis", None, None),
        ),
        (
            "heartbeat_lock",
            lambda: cli.analysis_lock_heartbeat("/analysis", None, None),
        ),
    ):
        monkeypatch.setattr(locks, name, fail)
        with pytest.raises(HeadnodeExit, match="lock failure"):
            invoke()


@pytest.mark.parametrize(
    ("result", "expected"),
    [(7, 7), (None, 0)],
)
def test_run_cli_return_values(
    monkeypatch: pytest.MonkeyPatch,
    result: object,
    expected: int,
) -> None:
    monkeypatch.setattr(cli, "_reset_cli_core_runtime", lambda: None)
    monkeypatch.setattr(cli, "create_app", lambda spec: lambda args, standalone_mode: result)
    assert cli._run_cli(["version"]) == expected


@pytest.mark.parametrize(
    ("exception", "expected"),
    [
        (click.ClickException("bad"), 1),
        (SystemExit(9), 9),
        (SystemExit("message"), 0),
        (KeyboardInterrupt(), 130),
    ],
)
def test_run_cli_handled_exceptions(
    monkeypatch: pytest.MonkeyPatch,
    exception: BaseException,
    expected: int,
) -> None:
    monkeypatch.setattr(cli, "_reset_cli_core_runtime", lambda: None)

    def fail(args, standalone_mode):
        raise exception

    monkeypatch.setattr(cli, "create_app", lambda spec: fail)
    assert cli._run_cli(["version"]) == expected


def test_run_cli_no_args_help(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli, "_reset_cli_core_runtime", lambda: None)
    context = click.Context(click.Command("dyec"))

    def fail(args, standalone_mode):
        raise click.exceptions.NoArgsIsHelpError(context)

    monkeypatch.setattr(cli, "create_app", lambda spec: fail)
    assert cli._run_cli([]) == 0
