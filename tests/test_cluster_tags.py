from __future__ import annotations

import json
from subprocess import CompletedProcess
from typing import Any

import pytest
from typer.testing import CliRunner

from daylily_ec.aws.cluster_tags import (
    ClusterTagError,
    parse_tag_assignments,
    parse_tag_deletions,
    stack_id_from_describe_cluster,
    update_cluster_stack_tags,
)
from daylily_ec.cli import app


runner = CliRunner()


STACK_ID = "arn:aws:cloudformation:us-west-2:123456789012:stack/parallelcluster-alpha/abc123"


class FakeWaiter:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def wait(self, **kwargs: Any) -> None:
        self.calls.append(kwargs)


class FakeCloudFormation:
    def __init__(self, *, status: str = "UPDATE_COMPLETE") -> None:
        self.waiter = FakeWaiter()
        self.stack: dict[str, Any] = {
            "StackId": STACK_ID,
            "StackName": "parallelcluster-alpha",
            "StackStatus": status,
            "Capabilities": ["CAPABILITY_NAMED_IAM"],
            "Parameters": [
                {"ParameterKey": "ClusterName", "ParameterValue": "alpha"},
                {"ParameterKey": "HeadNodeInstanceType", "ParameterValue": "m7i.large"},
            ],
            "Tags": [
                {"Key": "aws-parallelcluster-clustername", "Value": "alpha"},
                {"Key": "daylily-accept-jobs", "Value": "true"},
            ],
        }
        self.update_calls: list[dict[str, Any]] = []

    def describe_stacks(self, **kwargs: Any) -> dict[str, Any]:
        assert kwargs == {"StackName": STACK_ID}
        return {"Stacks": [dict(self.stack)]}

    def update_stack(self, **kwargs: Any) -> dict[str, str]:
        self.update_calls.append(kwargs)
        self.stack["Tags"] = kwargs["Tags"]
        return {"StackId": STACK_ID}

    def get_waiter(self, waiter_name: str) -> FakeWaiter:
        assert waiter_name == "stack_update_complete"
        return self.waiter


def _make_cp(stdout: str = "", stderr: str = "", rc: int = 0) -> CompletedProcess:
    return CompletedProcess(args=[], returncode=rc, stdout=stdout, stderr=stderr)


def _activate_dayec_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CONDA_PREFIX", "/tmp/dayec")
    monkeypatch.setenv("CONDA_DEFAULT_ENV", "DAY-EC")


def test_parse_tag_assignments_requires_key_value_shape() -> None:
    assert parse_tag_assignments(["daylily-accept-jobs=false"]) == {
        "daylily-accept-jobs": "false"
    }
    with pytest.raises(ClusterTagError, match="KEY=VALUE"):
        parse_tag_assignments(["daylily-accept-jobs"])
    with pytest.raises(ClusterTagError, match="reserved AWS prefix"):
        parse_tag_assignments(["aws:reserved=nope"])


def test_parse_tag_deletions_rejects_duplicates() -> None:
    assert parse_tag_deletions(["old-tag"]) == ("old-tag",)
    with pytest.raises(ClusterTagError, match="Duplicate"):
        parse_tag_deletions(["old-tag", "old-tag"])


def test_stack_id_from_describe_cluster_requires_cloudformation_arn() -> None:
    assert stack_id_from_describe_cluster({"cloudformationStackArn": STACK_ID}) == STACK_ID
    with pytest.raises(ClusterTagError, match="cloudformationStackArn"):
        stack_id_from_describe_cluster({"clusterName": "alpha"})


def test_update_cluster_stack_tags_sets_edits_and_waits() -> None:
    cfn = FakeCloudFormation()
    result = update_cluster_stack_tags(
        cfn,
        stack_id=STACK_ID,
        set_tags={"daylily-accept-jobs": "false", "ursa-drain-reason": "maintenance"},
        wait=True,
    )

    assert result.updated is True
    assert result.waited is True
    assert result.before_tags["daylily-accept-jobs"] == "true"
    assert result.after_tags["daylily-accept-jobs"] == "false"
    assert result.after_tags["ursa-drain-reason"] == "maintenance"
    assert cfn.waiter.calls == [{"StackName": STACK_ID}]
    call = cfn.update_calls[0]
    assert call["StackName"] == STACK_ID
    assert call["UsePreviousTemplate"] is True
    assert call["Capabilities"] == ["CAPABILITY_NAMED_IAM"]
    assert call["Parameters"] == [
        {"ParameterKey": "ClusterName", "UsePreviousValue": True},
        {"ParameterKey": "HeadNodeInstanceType", "UsePreviousValue": True},
    ]


def test_update_cluster_stack_tags_deletes_explicit_existing_key() -> None:
    cfn = FakeCloudFormation()
    result = update_cluster_stack_tags(
        cfn,
        stack_id=STACK_ID,
        delete_keys=["daylily-accept-jobs"],
    )

    assert result.updated is True
    assert "daylily-accept-jobs" not in result.after_tags
    assert cfn.update_calls


def test_update_cluster_stack_tags_rejects_missing_delete_key() -> None:
    cfn = FakeCloudFormation()
    with pytest.raises(ClusterTagError, match="Cannot delete missing"):
        update_cluster_stack_tags(cfn, stack_id=STACK_ID, delete_keys=["missing"])
    assert cfn.update_calls == []


def test_update_cluster_stack_tags_noops_when_tags_already_match() -> None:
    cfn = FakeCloudFormation()
    result = update_cluster_stack_tags(
        cfn,
        stack_id=STACK_ID,
        set_tags={"daylily-accept-jobs": "true"},
    )

    assert result.updated is False
    assert result.after_tags == result.before_tags
    assert cfn.update_calls == []


def test_update_cluster_stack_tags_rejects_in_progress_stack() -> None:
    cfn = FakeCloudFormation(status="UPDATE_IN_PROGRESS")
    with pytest.raises(ClusterTagError, match="not a stable updateable status"):
        update_cluster_stack_tags(
            cfn,
            stack_id=STACK_ID,
            set_tags={"daylily-accept-jobs": "false"},
        )


def test_cluster_tags_cli_sets_tags_from_parallelcluster_stack(monkeypatch: pytest.MonkeyPatch) -> None:
    _activate_dayec_runtime(monkeypatch)
    monkeypatch.setenv("AWS_PROFILE", "test-profile")
    cfn = FakeCloudFormation()
    describe = {
        "clusterName": "alpha",
        "cloudformationStackArn": STACK_ID,
        "tags": [
            {"key": "daylily-accept-jobs", "value": "true"},
        ],
    }

    def fake_run(*args: Any, **kwargs: Any) -> CompletedProcess:
        cmd = kwargs.get("args") or args[0]
        if isinstance(cmd, (list, tuple)) and "-c" in cmd:
            return _make_cp()
        assert "describe-cluster" in cmd
        return _make_cp(stdout=json.dumps(describe))

    class FakeSession:
        def __init__(self, *, profile_name: str, region_name: str) -> None:
            assert profile_name == "test-profile"
            assert region_name == "us-west-2"

        def client(self, service_name: str) -> FakeCloudFormation:
            assert service_name == "cloudformation"
            return cfn

    monkeypatch.setattr("subprocess.run", fake_run)
    monkeypatch.setattr("boto3.Session", FakeSession)

    result = runner.invoke(
        app,
        [
            "--json",
            "cluster",
            "tags",
            "--region",
            "us-west-2",
            "--cluster",
            "alpha",
            "--set",
            "daylily-accept-jobs=false",
            "--set",
            "ursa-drain-reason=maintenance",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["cluster"] == "alpha"
    assert payload["stack_id"] == STACK_ID
    assert payload["updated"] is True
    assert payload["after"]["daylily-accept-jobs"] == "false"
    assert payload["after"]["ursa-drain-reason"] == "maintenance"
    assert cfn.update_calls


def test_cluster_tags_cli_fails_when_describe_lacks_stack_arn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _activate_dayec_runtime(monkeypatch)
    monkeypatch.setenv("AWS_PROFILE", "test-profile")

    def fake_run(*args: Any, **kwargs: Any) -> CompletedProcess:
        cmd = kwargs.get("args") or args[0]
        if isinstance(cmd, (list, tuple)) and "-c" in cmd:
            return _make_cp()
        return _make_cp(stdout=json.dumps({"clusterName": "alpha"}))

    monkeypatch.setattr("subprocess.run", fake_run)

    result = runner.invoke(
        app,
        [
            "cluster",
            "tags",
            "--region",
            "us-west-2",
            "--cluster",
            "alpha",
            "--set",
            "daylily-accept-jobs=false",
        ],
    )

    assert result.exit_code == 1
    assert "cloudformationStackArn" in result.output

