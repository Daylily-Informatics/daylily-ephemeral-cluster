from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

import daylily_ec.headnode as headnode


def test_headnode_file_parsers_and_budget_summary(tmp_path: Path) -> None:
    assert headnode._parse_shell_assignment("x='quoted'\ny=plain", "x") == "quoted"
    assert headnode._parse_shell_assignment("x=1", "missing") == ""
    assert headnode._extract_cluster_config_value("project", "Key: other\nValue: x") == ""
    assert headnode._extract_reference_s3_uri("no script") == ""
    missing = tmp_path / "missing"
    assert headnode._read_region(missing) == ""
    assert headnode._read_cluster_project(missing) == ""
    assert headnode._read_reference_s3_uri(missing) == ""
    assert headnode._read_budget_tags(missing) == {}

    tags = tmp_path / "tags"
    tags.write_text("# comment\ninvalid\nproject\talice, bob,\n", encoding="utf-8")
    assert headnode._read_budget_tags(tags) == {"project": ["alice", "bob"]}
    assert headnode._derive_region_az_and_cluster_name("bad") == ("", "")
    summary = headnode._build_budget_summary(
        {
            "BudgetName": "project",
            "BudgetLimit": {"Amount": "0"},
            "CalculatedSpend": {"ActualSpend": {"Amount": "bad"}},
        }
    )
    assert summary.percent_used is None


def test_resolve_project_and_session_variants(monkeypatch: pytest.MonkeyPatch) -> None:
    warnings: list[str] = []
    assert (
        headnode._resolve_project(
            None,
            skip_project_check=False,
            valid_projects={},
            user_name="alice",
            warnings=warnings,
            cluster_project="",
        )
        == ""
    )
    assert warnings
    assert (
        headnode._resolve_project(
            "project",
            skip_project_check=False,
            valid_projects={"project": ["alice"]},
            user_name="alice",
            warnings=[],
            cluster_project="",
        )
        == "project"
    )
    warnings = []
    headnode._resolve_project(
        "wrong",
        skip_project_check=False,
        valid_projects={"allowed": ["alice"]},
        user_name="alice",
        warnings=warnings,
        cluster_project="",
    )
    assert "Valid projects" in warnings[-1]

    calls: list[dict] = []
    monkeypatch.setattr(headnode.boto3, "Session", lambda **kwargs: calls.append(kwargs) or kwargs)
    headnode._build_session("r", "profile")
    headnode._build_session("r", "")
    assert calls == [
        {"profile_name": "profile", "region_name": "r"},
        {"region_name": "r"},
    ]


def test_collect_state_warnings_and_aws_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cfnconfig = tmp_path / "cfnconfig"
    cfnconfig.write_text("cfn_region=us-west-2\n", encoding="utf-8")
    monkeypatch.setattr(headnode.getpass, "getuser", lambda: "alice")
    monkeypatch.setattr(
        headnode,
        "_build_session",
        lambda *args: (_ for _ in ()).throw(RuntimeError("denied")),
    )
    state = headnode.collect_headnode_state(
        project="explicit",
        cfnconfig_path=cfnconfig,
        cluster_config_path=tmp_path / "missing-config",
        budget_tags_path=tmp_path / "missing-tags",
    )
    assert len(state.warnings) == 4
    assert state.warnings[-1] == "Unable to inspect AWS budgets: denied"


def test_prompt_helpers(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    responses = iter(["invalid", "valid@example.com"])
    monkeypatch.setattr(headnode, "_prompt", lambda *args, **kwargs: next(responses))
    assert headnode._prompt_email("default@example.com") == "valid@example.com"
    assert "Invalid email format" in capsys.readouterr().out
    monkeypatch.setattr(headnode, "_prompt", lambda *args, **kwargs: "s3://bucket/prefix/")
    assert headnode._prompt_bucket_name("reference") == "bucket/prefix"


def test_create_missing_budgets_full_flow(monkeypatch: pytest.MonkeyPatch) -> None:
    budgets = SimpleNamespace(
        describe_budgets=lambda **kwargs: {
            "Budgets": [
                {
                    "BudgetName": "cluster",
                    "BudgetLimit": {"Amount": "200"},
                    "CalculatedSpend": {"ActualSpend": {"Amount": "20"}},
                }
            ]
        }
    )
    session = SimpleNamespace(
        client=lambda service, **kwargs: (
            SimpleNamespace(get_caller_identity=lambda: {"Account": "123"})
            if service == "sts"
            else budgets if service == "budgets" else object()
        )
    )
    monkeypatch.setattr(headnode, "_build_session", lambda *args: session)
    monkeypatch.setattr(headnode, "_prompt_email", lambda default: "owner@example.com")
    answers = iter(["global users", "500", "cluster users", "200"])
    monkeypatch.setattr(headnode, "_prompt", lambda *args, **kwargs: next(answers))
    monkeypatch.setattr(headnode, "budget_exists", lambda *args: False)
    created: list[tuple] = []
    notified: list[tuple] = []
    tagged: list[tuple] = []
    monkeypatch.setattr(headnode, "create_budget", lambda *args: created.append(args))
    monkeypatch.setattr(headnode, "create_notifications", lambda *args: notified.append(args))
    monkeypatch.setattr(headnode, "update_tags_file", lambda *args: tagged.append(args))
    result = headnode._create_missing_budgets(
        headnode.HeadnodeState(region="r"),
        project_name="project",
        region_az="r-a",
        cluster_name="cluster",
        bucket_name="bucket",
    )
    assert result.percent_used == 10.0
    assert len(created) == len(notified) == len(tagged) == 2
    assert tagged[0][3] == "globalusers"


def test_create_missing_budgets_existing_global_and_missing_refresh(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    budgets = SimpleNamespace(describe_budgets=lambda **kwargs: {"Budgets": []})
    session = SimpleNamespace(
        client=lambda service, **kwargs: (
            SimpleNamespace(get_caller_identity=lambda: {"Account": "123"})
            if service == "sts"
            else budgets if service == "budgets" else object()
        )
    )
    monkeypatch.setattr(headnode, "_build_session", lambda *args: session)
    monkeypatch.setattr(headnode, "_prompt_email", lambda default: "owner@example.com")
    answers = iter(["global", "500", "cluster", "200"])
    monkeypatch.setattr(headnode, "_prompt", lambda *args, **kwargs: next(answers))
    monkeypatch.setattr(headnode, "budget_exists", lambda *args: True)
    monkeypatch.setattr(headnode, "create_budget", lambda *args: None)
    monkeypatch.setattr(headnode, "create_notifications", lambda *args: None)
    monkeypatch.setattr(headnode, "update_tags_file", lambda *args: None)
    result = headnode._create_missing_budgets(
        headnode.HeadnodeState(region="r"),
        project_name="project",
        region_az="r-a",
        cluster_name="cluster",
        bucket_name="bucket",
    )
    assert result == headnode.BudgetSummary(name="cluster", exists=True)


def test_print_state_all_fields(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(headnode.getpass, "getuser", lambda: "alice")
    headnode._print_state(
        headnode.HeadnodeState(
            region="r",
            project="project",
            aws_profile="profile",
            reference_s3_uri="bucket",
            valid_projects=["project"],
            budget_summary=headnode.BudgetSummary("project", True, "100", "25", 25.0),
        )
    )
    output = capsys.readouterr().out
    assert "AWS Profile: profile" in output
    assert "Valid projects for alice" in output
    assert "Percent used: 25.00%" in output


@pytest.mark.parametrize("outcome", ["missing", "failure", "success"])
def test_run_headnode_init_budget_creation_paths(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    outcome: str,
) -> None:
    state = headnode.HeadnodeState(
        region="r",
        project="project",
        reference_s3_uri="bucket",
        valid_projects=["project"],
        budget_summary=headnode.BudgetSummary("project", False),
    )
    monkeypatch.setattr(headnode, "collect_headnode_state", lambda **kwargs: state)
    monkeypatch.setattr(headnode, "_confirm", lambda *args, **kwargs: True)
    answers = iter(["" if outcome == "missing" else "r-a", "cluster"])
    monkeypatch.setattr(headnode, "_prompt", lambda *args, **kwargs: next(answers))
    monkeypatch.setattr(headnode, "_prompt_bucket_name", lambda uri: "bucket")
    if outcome == "failure":
        monkeypatch.setattr(
            headnode,
            "_create_missing_budgets",
            lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("denied")),
        )
    else:
        monkeypatch.setattr(
            headnode,
            "_create_missing_budgets",
            lambda *args, **kwargs: headnode.BudgetSummary("project", True),
        )
    assert headnode.run_headnode_init() == 0
    output = capsys.readouterr()
    if outcome == "missing":
        assert "skipping budget creation" in output.err
    elif outcome == "failure":
        assert "failed to create budget" in output.err
    else:
        assert "Created budget" in output.out
