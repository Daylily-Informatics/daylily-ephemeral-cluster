from __future__ import annotations

from subprocess import CompletedProcess
from types import SimpleNamespace

import pytest

import daylily_ec.cli as cli
from daylily_ec.scripts.common import CommandError


class _Item:
    def __init__(self, name: str, **values: object) -> None:
        self.name = name
        self.values = values

    def to_dict(self) -> dict[str, object]:
        return {"name": self.name, **self.values}


def _context(monkeypatch: pytest.MonkeyPatch):
    dynamodb = object()
    context = SimpleNamespace(
        account_id="123456789012",
        caller_arn="arn:aws:iam::123456789012:user/tester",
        session=SimpleNamespace(client=lambda service, **kwargs: (service, kwargs)),
        client=lambda service: ("regional", service),
    )
    monkeypatch.setattr(cli, "_cost_center_context", lambda profile, region: (context, dynamodb))
    monkeypatch.setattr(cli, "_warn_if_dayec_env_inactive", lambda: None)
    return context, dynamodb


def _capture_payload(monkeypatch: pytest.MonkeyPatch) -> list[tuple[object, str]]:
    captured: list[tuple[object, str]] = []
    monkeypatch.setattr(
        cli, "_emit_payload", lambda payload, text: captured.append((payload, text))
    )
    return captured


def test_json_mode_emit_payload_and_environment_warning(monkeypatch: pytest.MonkeyPatch) -> None:
    emitted: list[object] = []
    printed: list[str] = []
    monkeypatch.setattr(cli.output, "emit_json", emitted.append)
    monkeypatch.setattr(cli.output, "print_text", printed.append)
    monkeypatch.setattr(cli, "get_context", lambda: SimpleNamespace(json_mode=True))
    cli._emit_payload({"ok": True}, "human")
    assert emitted == [{"ok": True}]
    assert printed == []

    monkeypatch.setattr(cli, "get_context", lambda: SimpleNamespace(json_mode=False))
    cli._emit_payload({"ok": True}, "human")
    assert printed == ["human"]

    def fail_context():
        raise RuntimeError("no command context")

    monkeypatch.setattr(cli, "get_context", fail_context)
    assert cli._json_mode() is False

    monkeypatch.setenv("CONDA_DEFAULT_ENV", "DAY-EC")
    assert cli._dayec_env_warning_message() is None
    monkeypatch.setenv("CONDA_DEFAULT_ENV", "other")
    assert "other" in str(cli._dayec_env_warning_message())
    monkeypatch.delenv("CONDA_DEFAULT_ENV")
    monkeypatch.setenv("CONDA_PREFIX", "/tmp/conda")
    assert "CONDA_DEFAULT_ENV" in str(cli._dayec_env_warning_message())
    monkeypatch.delenv("CONDA_PREFIX")
    assert "not active" in str(cli._dayec_env_warning_message())


def test_profile_environment_and_command_failure_details(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AWS_PROFILE", "env-profile")
    assert cli._resolved_aws_profile(None) == "env-profile"
    assert cli._resolved_aws_profile("explicit") == "explicit"
    monkeypatch.delenv("AWS_PROFILE")
    with pytest.raises(CommandError, match="AWS profile is required"):
        cli._resolved_aws_profile(None)

    env = cli._aws_env(profile="profile", region="us-west-2")
    assert env["AWS_PROFILE"] == "profile"
    assert env["AWS_REGION"] == env["AWS_DEFAULT_REGION"] == "us-west-2"

    assert cli._command_failure_detail(CompletedProcess([], 1, "", "")) == "unknown error"
    assert cli._command_failure_detail(CompletedProcess([], 1, '{"message":"bad"}', "stderr")) == (
        "bad\nstderr"
    )
    assert cli._command_failure_detail(CompletedProcess([], 1, "plain", "")) == "plain"
    assert cli._command_failure_detail(CompletedProcess([], 1, '["bad"]', "")) == '["bad"]'


@pytest.mark.parametrize(
    ("process", "message"),
    [
        (CompletedProcess([], 2, "", "denied"), "pcluster command failed: denied"),
        (CompletedProcess([], 0, "not-json", ""), "Failed to parse pcluster JSON output"),
        (CompletedProcess([], 0, "[]", ""), "pcluster returned non-object JSON"),
    ],
)
def test_run_pcluster_json_errors(
    monkeypatch: pytest.MonkeyPatch,
    process: CompletedProcess[str],
    message: str,
) -> None:
    monkeypatch.setattr(cli.subprocess, "run", lambda *args, **kwargs: process)
    with pytest.raises(CommandError, match=message):
        cli._run_pcluster_json(["pcluster", "list-clusters"], profile="p", region="r")


def test_run_pcluster_json_success_and_missing_binary(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        cli.subprocess,
        "run",
        lambda *args, **kwargs: CompletedProcess([], 0, '{"clusters": []}', ""),
    )
    assert cli._run_pcluster_json(["pcluster"], profile="p", region="r") == {"clusters": []}

    def missing(*args, **kwargs):
        raise FileNotFoundError

    monkeypatch.setattr(cli.subprocess, "run", missing)
    with pytest.raises(CommandError, match="pcluster CLI not found"):
        cli._run_pcluster_json(["pcluster"], profile="p", region="r")


def test_cluster_rows_and_description_helpers(monkeypatch: pytest.MonkeyPatch) -> None:
    describe_cluster_payload = cli._describe_cluster_payload
    details = {
        "clusterStatus": "CREATE_COMPLETE",
        "creationTime": "created",
        "lastUpdatedTime": "updated",
        "headNode": {
            "launchTime": "launched",
            "publicIpAddress": "203.0.113.4",
            "instanceId": "i-head",
        },
    }
    row = cli._cluster_row_from_details("alpha", details)
    assert row["status"] == "CREATE_COMPLETE"
    assert row["instance_id"] == "i-head"
    assert cli._cluster_row_from_details("empty", {})["ip"] == "N/A"

    calls: list[tuple[str, str]] = []
    monkeypatch.setattr(cli, "_describe_cluster_payload", lambda **kwargs: details)
    monkeypatch.setattr(
        cli,
        "_cluster_headnode_config_status",
        lambda item, **kwargs: calls.append((item["name"], kwargs["region"])),
    )
    payload = {"clusters": [None, {}, {"clusterName": "alpha"}]}
    assert cli._cluster_rows_from_list(
        payload, profile="p", region="us-west-2", details=False, verbose=False
    ) == [{"name": "alpha", "region": "us-west-2", "ip": "203.0.113.4"}]
    verbose = cli._cluster_rows_from_list(
        payload, profile="p", region="us-west-2", details=True, verbose=True
    )
    assert verbose[0]["details"] == details
    assert calls == [("alpha", "us-west-2")]
    assert (
        cli._cluster_rows_from_list(
            {"clusters": "invalid"}, profile="p", region="r", details=False, verbose=False
        )
        == []
    )

    captured: list[object] = []
    monkeypatch.setattr(
        cli, "_run_pcluster_json", lambda command, **kwargs: captured.append(command) or {}
    )
    assert describe_cluster_payload(profile="p", region="r", cluster="alpha") == {}
    assert captured[0][0:3] == ["pcluster", "describe-cluster", "--cluster-name"]


def test_cluster_headnode_status_missing_and_success(monkeypatch: pytest.MonkeyPatch) -> None:
    row: dict[str, object] = {"name": "alpha", "instance_id": ""}
    cli._cluster_headnode_config_status(row, profile="p", region="r")
    assert row["headnode_configured"] is None

    import daylily_ec.aws.ssm as ssm

    calls: list[tuple[object, ...]] = []
    monkeypatch.setattr(ssm, "run_shell", lambda *args, **kwargs: calls.append(args))
    row = {"name": "alpha", "instance_id": "i-head"}
    cli._cluster_headnode_config_status(row, profile="p", region="r")
    assert row["headnode_configured_text"] == "YES"
    assert calls[0][0:2] == ("i-head", "r")


@pytest.mark.parametrize(
    ("verbose", "include_instance", "expected"),
    [
        (False, False, "CLUSTER_NAME"),
        (True, False, "HEADNODE_LAUNCHED_AT"),
        (True, True, "INSTANCE_ID"),
    ],
)
def test_emit_cluster_table_layouts(
    monkeypatch: pytest.MonkeyPatch,
    verbose: bool,
    include_instance: bool,
    expected: str,
) -> None:
    printed: list[str] = []
    monkeypatch.setattr(cli.output, "heading", printed.append)
    monkeypatch.setattr(cli.output, "print_text", printed.append)
    row = {
        "name": "alpha",
        "region": "us-west-2",
        "ip": "203.0.113.4",
        "status": "CREATE_COMPLETE",
        "headnode_configured_text": "YES",
        "created_at": "created",
        "updated_at": "updated",
        "headnode_launched_at": "launched",
        "instance_id": "i-head",
    }
    cli._emit_cluster_table(
        ["us-west-2"], [row], verbose=verbose, include_instance=include_instance
    )
    assert expected in "\n".join(printed)
    assert "alpha" in "\n".join(printed)


def test_emit_cluster_table_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    printed: list[str] = []
    monkeypatch.setattr(cli.output, "print_text", printed.append)
    cli._emit_cluster_table(["us-west-2"], [], verbose=False, include_instance=False)
    assert printed == ["No clusters found in us-west-2."]


def test_cost_center_context_builds_home_region(monkeypatch: pytest.MonkeyPatch) -> None:
    import daylily_ec.aws.context as context_module

    context = SimpleNamespace(client=lambda service: ("client", service))
    calls: list[tuple[str, str | None]] = []
    monkeypatch.setattr(
        context_module.AWSContext,
        "build_region",
        lambda region, profile=None: calls.append((region, profile)) or context,
    )
    assert cli._cost_center_context("profile", "us-west-2") == (
        context,
        ("client", "dynamodb"),
    )
    assert calls == [("us-west-2", "profile")]


def test_cost_centers_ensure_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    import daylily_ec.aws.cost_centers as module

    context, dynamodb = _context(monkeypatch)
    captured = _capture_payload(monkeypatch)
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        module,
        "ensure_cost_center_registry",
        lambda client, **kwargs: calls.append({"client": client, **kwargs}) or {"ready": True},
    )
    cli.cost_centers_ensure_registry("p", "r", "registry", "usage")
    assert calls == [
        {
            "client": dynamodb,
            "table_name": "registry",
            "usage_table_name": "usage",
            "actor_arn": context.caller_arn,
        }
    ]
    assert captured[0][0] == {"ready": True}


def test_cost_centers_create_edit_disable_show_list(monkeypatch: pytest.MonkeyPatch) -> None:
    import daylily_ec.aws.cost_centers as module

    context, dynamodb = _context(monkeypatch)
    captured = _capture_payload(monkeypatch)
    calls: dict[str, object] = {}
    monkeypatch.setattr(
        module,
        "create_cost_center",
        lambda client, name, **kwargs: calls.setdefault("create", (client, name, kwargs))
        and _Item(name, status="active"),
    )
    monkeypatch.setattr(
        module,
        "edit_cost_center",
        lambda client, name, **kwargs: calls.setdefault("edit", (client, name, kwargs))
        and _Item(name, status="disabled"),
    )
    monkeypatch.setattr(
        module,
        "disable_cost_center",
        lambda client, name, **kwargs: calls.setdefault("disable", (client, name, kwargs))
        and _Item(name, status="disabled"),
    )
    monkeypatch.setattr(module, "get_cost_center", lambda *args, **kwargs: _Item("alpha"))
    monkeypatch.setattr(
        module, "list_cost_centers", lambda *args, **kwargs: [_Item("alpha"), _Item("beta")]
    )

    cli.cost_centers_create(
        "alpha", "100", ["alice"], ["group"], ["owner@example.com"], "notes", "p", "r", "t", "u"
    )
    cli.cost_centers_edit(
        "alpha", "200", ["bob"], ["new"], ["new@example.com"], "edited", "disabled", "p", "r", "t"
    )
    cli.cost_centers_disable("alpha", "done", "p", "r", "t")
    cli.cost_centers_show("alpha", "p", "r", "t")
    cli.cost_centers_list("all", "p", "r", "t")

    assert calls["create"][2]["actor_arn"] == context.caller_arn
    assert calls["create"][2]["allowed_users"] == ["alice"]
    assert calls["edit"][2]["status"] == "disabled"
    assert calls["disable"][2]["reason"] == "done"
    assert captured[-1][0]["cost_centers"] == [{"name": "alpha"}, {"name": "beta"}]
    assert all(call[0] is dynamodb for call in calls.values())


def test_cost_centers_usage_one_missing_and_list(monkeypatch: pytest.MonkeyPatch) -> None:
    import daylily_ec.aws.cost_centers as module

    _context(monkeypatch)
    captured = _capture_payload(monkeypatch)
    monkeypatch.setattr(module, "get_cost_center_usage", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        module, "list_cost_center_usage", lambda *args, **kwargs: [_Item("alpha", spend="12.34")]
    )
    cli.cost_centers_usage("alpha", "2026-07", "p", "r", "usage")
    cli.cost_centers_usage(None, "2026-07", "p", "r", "usage")
    assert captured[0][0] == {"usage": None}
    assert captured[1][0] == {"usage": [{"name": "alpha", "spend": "12.34"}]}


def test_cost_centers_put_usage(monkeypatch: pytest.MonkeyPatch) -> None:
    import daylily_ec.aws.cost_centers as module

    _context(monkeypatch)
    captured = _capture_payload(monkeypatch)
    monkeypatch.setattr(module, "get_cost_center", lambda *args, **kwargs: _Item("alpha"))
    monkeypatch.setattr(module, "utc_now_iso", lambda: "2026-07-16T00:00:00Z")
    seen: list[object] = []
    monkeypatch.setattr(
        module,
        "put_cost_center_usage",
        lambda client, item, **kwargs: seen.append(item) or item,
    )
    cli.cost_centers_put_usage(
        "alpha", "2026-07", "42.50", "2026-07-15T23:00:00Z", "p", "r", "registry", "usage"
    )
    assert seen[0].updated_at == "2026-07-16T00:00:00Z"
    assert captured[0][0]["usage"]["monthly_spend_usd"] == "42.50"


@pytest.mark.parametrize("provided_uri", [None, "s3://custom/results/"])
def test_cost_centers_refresh_usage(
    monkeypatch: pytest.MonkeyPatch, provided_uri: str | None
) -> None:
    import daylily_ec.cost_center_refresh as module

    context, dynamodb = _context(monkeypatch)
    captured = _capture_payload(monkeypatch)
    seen: list[dict[str, object]] = []
    monkeypatch.setattr(
        module,
        "refresh_dedicated_cluster_usage",
        lambda **kwargs: seen.append(kwargs) or _Item("alpha", refreshed=True),
    )
    cli.cost_centers_refresh_usage(
        "alpha",
        "alpha",
        "2026-07",
        "p",
        "us-west-2",
        "us-east-1",
        "db",
        "table",
        provided_uri,
        "registry",
        "usage",
        True,
    )
    expected_uri = provided_uri or "s3://dayec-cur-123456789012-us-east-1/dayec-cur/athena-results/"
    assert seen[0]["athena_client"] == ("athena", {"region_name": "us-east-1"})
    assert seen[0]["dynamodb_client"] is dynamodb
    assert seen[0]["cur_config"].output_s3_uri == expected_uri
    assert captured[0][0]["refreshed"] is True
    assert context.account_id in expected_uri or provided_uri is not None


def test_cost_centers_ensure_cur_export(monkeypatch: pytest.MonkeyPatch) -> None:
    import daylily_ec.aws.context as context_module
    import daylily_ec.aws.cur_export as module

    context = SimpleNamespace(
        account_id="123456789012",
        session=SimpleNamespace(client=lambda service, **kwargs: (service, kwargs)),
        client=lambda service: ("regional", service),
    )
    monkeypatch.setattr(context_module.AWSContext, "build_region", lambda *args, **kwargs: context)
    monkeypatch.setattr(
        module, "default_cur_export_bucket", lambda account_id: f"bucket-{account_id}"
    )
    seen: list[dict[str, object]] = []
    monkeypatch.setattr(
        module,
        "ensure_cur2_athena_source",
        lambda **kwargs: seen.append(kwargs) or {"ready": True},
    )
    monkeypatch.setattr(cli, "_warn_if_dayec_env_inactive", lambda: None)
    captured = _capture_payload(monkeypatch)
    cli.cost_centers_ensure_cur_export(
        "p",
        "us-east-1",
        None,
        "us-west-2",
        None,
        "export",
        "prefix",
        "db",
        "table",
        "",
        "cluster-tag",
        True,
        True,
    )
    config = seen[0]["config"]
    assert config.bucket == "bucket-123456789012"
    assert config.athena_region == "us-west-2"
    assert seen[0]["update_existing_export"] is True
    assert seen[0]["adopt_glue_table"] is True
    assert captured[0][0] == {"ready": True}
