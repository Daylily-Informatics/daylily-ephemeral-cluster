from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from daylily_ec.aws import slurm_accounting as accounting
from daylily_ec.aws.slurm_accounting import (
    SlurmAccountingDbResolution,
    SlurmAccountingError,
    SlurmAccountingSelectionCandidate,
)
from daylily_ec.pcluster.runner import PclusterResult
from daylily_ec.state.models import CheckResult, CheckStatus, PreflightReport
from daylily_ec.workflow import attach_slurm_accounting as attach
from daylily_ec.workflow import create_cluster
from daylily_ec.workflow.attach_slurm_accounting import (
    SlurmAccountingAttachError,
    SlurmAccountingPreparationError,
)
from tests.test_attach_slurm_accounting import _config, _db
from tests.test_slurm_accounting import (
    FakeAwsContext,
    FakeCloudFormation,
    FakeEc2,
    _network_interface,
    _outputs,
    _stack,
    _tags,
)
from tests.test_workflow import _build_workflow_config, _run_stubbed_create_workflow
from daylily_ec.render import renderer


def _result(body: dict | None = None, *, success: bool = True) -> PclusterResult:
    return PclusterResult(
        command="pcluster",
        returncode=0 if success else 1,
        json_body=body or {},
        success=success,
        stderr="rejected" if not success else "",
        message="rejected" if not success else "",
    )


def test_preflight_only_runs_complete_success_and_abort_paths(tmp_path, monkeypatch):
    template = tmp_path / "template.yaml"
    template.write_text("Region: us-west-2\n", encoding="utf-8")
    cfg = _build_workflow_config(template)
    ctx = SimpleNamespace(
        region="us-west-2",
        profile="test",
        account_id="123456789012",
        caller_arn="arn:aws:iam::123456789012:user/test",
    )

    monkeypatch.setattr(
        "daylily_ec.config.triplets.load_config",
        lambda _path: cfg,
    )
    monkeypatch.setattr(
        "daylily_ec.aws.context.AWSContext.build",
        lambda *_args, **_kwargs: ctx,
    )
    monkeypatch.setattr(
        "daylily_ec.aws.iam.make_iam_preflight_step", lambda *_args, **_kwargs: "iam"
    )
    monkeypatch.setattr(
        "daylily_ec.aws.quotas.make_quota_preflight_step",
        lambda *_args, **_kwargs: "quota",
    )
    monkeypatch.setattr(
        "daylily_ec.aws.s3.make_s3_bucket_preflight_step",
        lambda *_args, **_kwargs: "s3",
    )
    monkeypatch.setattr(create_cluster, "make_repository_catalog_preflight_step", lambda: "repo")
    monkeypatch.setattr(
        create_cluster,
        "_resolve_s3_role_config_value",
        lambda _cfg, key, *_args, **_kwargs: f"s3://bucket/{key}",
    )
    observed: list[object] = []

    def run(report, **kwargs):
        observed.append(kwargs["steps"])
        return report

    monkeypatch.setattr(create_cluster, "run_preflight", run)
    monkeypatch.setattr(create_cluster, "write_preflight_report", observed.append)
    monkeypatch.setattr(create_cluster, "should_abort", lambda *_args, **_kwargs: False)

    assert (
        create_cluster.run_preflight_only(
            "us-west-2d",
            profile="test",
            config_path=str(tmp_path / "config.yaml"),
            non_interactive=True,
            debug=True,
        )
        == create_cluster.EXIT_SUCCESS
    )
    assert observed[0] == ["iam", "repo", "quota", "s3"]

    monkeypatch.setattr(create_cluster, "should_abort", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(create_cluster, "exit_code_for", lambda _report: 7)
    assert (
        create_cluster.run_preflight_only(
            "us-west-2d",
            profile="test",
            config_path=str(tmp_path / "config.yaml"),
            non_interactive=True,
        )
        == 7
    )


@pytest.mark.parametrize(
    ("failure", "expected"),
    [
        ("budget", create_cluster.EXIT_AWS_FAILURE),
        ("render", create_cluster.EXIT_VALIDATION_FAILURE),
        ("pricing", create_cluster.EXIT_AWS_FAILURE),
        ("policy", create_cluster.EXIT_VALIDATION_FAILURE),
        ("table", create_cluster.EXIT_VALIDATION_FAILURE),
        ("dra", create_cluster.EXIT_VALIDATION_FAILURE),
        ("cpu", create_cluster.EXIT_VALIDATION_FAILURE),
        ("dry_run", create_cluster.EXIT_AWS_FAILURE),
        ("break", create_cluster.EXIT_SUCCESS),
        ("create", create_cluster.EXIT_AWS_FAILURE),
        ("monitor", create_cluster.EXIT_AWS_FAILURE),
        ("headnode_id", create_cluster.EXIT_AWS_FAILURE),
        ("ssm", create_cluster.EXIT_AWS_FAILURE),
        ("configure", create_cluster.EXIT_AWS_FAILURE),
    ],
)
def test_create_workflow_failure_gates_are_behavioral(tmp_path, monkeypatch, failure, expected):
    original = create_cluster.run_create_workflow

    def injected(*args, **kwargs):
        import daylily_ec.aws.budgets as budgets
        import daylily_ec.aws.ssm as ssm
        import daylily_ec.pcluster.monitor as monitor
        import daylily_ec.pcluster.runner as runner
        import daylily_ec.render.renderer as renderer

        if failure == "budget":
            monkeypatch.setattr(
                budgets,
                "ensure_global_budget",
                lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("budget")),
            )
        elif failure == "render":
            monkeypatch.setattr(
                renderer,
                "write_init_artifacts",
                lambda *_a, **_k: (_ for _ in ()).throw(ValueError("render")),
            )
        elif failure == "pricing":
            monkeypatch.setattr(
                "daylily_ec.aws.spot_pricing.apply_spot_prices",
                lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("pricing")),
            )
        elif failure == "policy":
            monkeypatch.setattr(
                create_cluster,
                "attach_headnode_managed_policy",
                lambda *_a, **_k: (_ for _ in ()).throw(ValueError("policy")),
            )
        elif failure == "table":
            monkeypatch.setattr(
                create_cluster,
                "_emit_spot_price_partition_table",
                lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("table")),
            )
        elif failure == "dra":
            monkeypatch.setattr(
                create_cluster,
                "validate_startup_dra_contract",
                lambda *_a, **_k: (_ for _ in ()).throw(ValueError("dra")),
            )
        elif failure == "cpu":
            monkeypatch.setattr(
                create_cluster,
                "validate_cpu_only_slurm_contract",
                lambda *_a, **_k: (_ for _ in ()).throw(ValueError("cpu")),
            )
        elif failure == "dry_run":
            monkeypatch.setattr(runner, "dry_run_create", lambda *_a, **_k: _result(success=False))
        elif failure == "break":
            monkeypatch.setattr(runner, "should_break_after_dry_run", lambda: True)
        elif failure == "create":
            monkeypatch.setattr(runner, "create_cluster", lambda *_a, **_k: _result(success=False))
        elif failure in {"monitor", "headnode_id"}:
            monkeypatch.setattr(
                monitor,
                "wait_for_creation",
                lambda *_a, **_k: SimpleNamespace(
                    success=failure == "headnode_id",
                    elapsed_seconds=1,
                    final_status="CREATE_FAILED",
                    error="failed",
                    head_node_ip="",
                    head_node_instance_id="" if failure == "headnode_id" else "i-head",
                ),
            )
        elif failure == "ssm":
            monkeypatch.setattr(
                ssm,
                "wait_for_ssm_online",
                lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("offline")),
            )
        elif failure == "configure":
            monkeypatch.setattr(create_cluster, "configure_headnode", lambda **_kwargs: False)
        return original(*args, **kwargs)

    monkeypatch.setattr(create_cluster, "run_create_workflow", injected)
    records = _run_stubbed_create_workflow(
        tmp_path,
        monkeypatch,
        interactive=False,
        head_node_ip="54.1.2.3",
        say_available=False,
    )
    assert records["rc"] == expected
    assert records["failures"] or failure == "break"


def test_latest_config_skips_bad_state_and_selects_newest(tmp_path, monkeypatch):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    first = _config(tmp_path / "first.yaml")
    latest = _config(tmp_path / "latest.yaml")
    (config_dir / "state-cluster-bad.json").write_text("not json", encoding="utf-8")
    (config_dir / "state_cluster_1.json").write_text(
        '{"cluster_name":"cluster","region":"us-west-2","aws_profile":"p",'
        f'"run_id":"1","cluster_yaml_path":"{first}"}}',
        encoding="utf-8",
    )
    (config_dir / "state_cluster_2.json").write_text(
        '{"cluster_name":"cluster","region":"us-west-2","aws_profile":"p",'
        f'"run_id":"2","cluster_yaml_path":"{latest}"}}',
        encoding="utf-8",
    )
    monkeypatch.setattr(attach, "config_dir", lambda: config_dir)
    assert attach._latest_cluster_config("cluster", "us-west-2", profile="p") == latest
    with pytest.raises(SlurmAccountingAttachError, match="No persisted"):
        attach._latest_cluster_config("missing", "us-west-2", profile=None)


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {"Scheduling": []},
        {"Scheduling": {"SlurmSettings": []}},
        {"Scheduling": {"SlurmSettings": {"Database": {}}}},
        {"Scheduling": {"SlurmSettings": {}}, "HeadNode": []},
        {"Scheduling": {"SlurmSettings": {}}, "HeadNode": {"Networking": []}},
        {
            "Scheduling": {"SlurmSettings": {}},
            "HeadNode": {"Networking": {"AdditionalSecurityGroups": [""]}},
        },
    ],
)
def test_render_rejects_unsafe_yaml_shapes(tmp_path, payload):
    source = tmp_path / "source.yaml"
    source.write_text(yaml.safe_dump(payload), encoding="utf-8")
    with pytest.raises(SlurmAccountingAttachError):
        attach.render_slurm_accounting_update_config(source, tmp_path / "out.yaml", _db())


@pytest.mark.parametrize(
    ("subnets", "reason"),
    [
        ([], "subnet_not_unique"),
        ([{"AvailabilityZone": "us-west-2d"}], "subnet_missing_vpc"),
        ([{"VpcId": "vpc-1"}], "subnet_missing_az"),
    ],
)
def test_prepare_reports_network_contract_failures(tmp_path, monkeypatch, subnets, reason):
    source = _config(tmp_path / "source.yaml")
    ec2 = SimpleNamespace(describe_subnets=lambda **_kwargs: {"Subnets": subnets})
    ctx = SimpleNamespace(client=lambda service: ec2)
    monkeypatch.setattr(attach.AWSContext, "build_region", lambda *_a, **_k: ctx)
    with pytest.raises(SlurmAccountingPreparationError) as caught:
        attach.prepare_slurm_accounting_update(
            cluster_name="cluster",
            region="us-west-2",
            cluster_configuration=source,
            create_if_missing=False,
        )
    assert caught.value.reason_code == reason


def test_prepare_redacts_discovery_and_render_failures(tmp_path, monkeypatch):
    source = _config(tmp_path / "source.yaml")
    ctx = SimpleNamespace(
        client=lambda service: SimpleNamespace(
            describe_subnets=lambda **_k: {
                "Subnets": [{"VpcId": "vpc-1", "AvailabilityZone": "us-west-2d"}]
            }
        )
    )
    monkeypatch.setattr(attach.AWSContext, "build_region", lambda *_a, **_k: ctx)
    monkeypatch.setattr(
        attach,
        "list_regional_slurm_accounting_stacks",
        lambda *_a, **_k: (_ for _ in ()).throw(SlurmAccountingError("secret")),
    )
    with pytest.raises(SlurmAccountingPreparationError) as caught:
        attach.prepare_slurm_accounting_update(
            cluster_name="cluster",
            region="us-west-2",
            cluster_configuration=source,
            create_if_missing=False,
        )
    assert caught.value.reason_code == "service_discovery_failed"

    monkeypatch.setattr(attach, "list_regional_slurm_accounting_stacks", lambda *_a, **_k: [])
    monkeypatch.setattr(
        attach,
        "resolve_slurm_accounting_db",
        lambda *_a, **_k: SlurmAccountingDbResolution(db=_db(), service_created=False),
    )
    monkeypatch.setattr(
        attach,
        "render_slurm_accounting_update_config",
        lambda *_a, **_k: (_ for _ in ()).throw(OSError("secret")),
    )
    with pytest.raises(SlurmAccountingPreparationError) as caught:
        attach.prepare_slurm_accounting_update(
            cluster_name="cluster",
            region="us-west-2",
            cluster_configuration=source,
            create_if_missing=False,
        )
    assert caught.value.reason_code == "update_config_render_failed"


@pytest.mark.parametrize(
    ("cluster", "region", "cluster_result", "fleet_result", "update_results"),
    [
        ("", "us-west-2", _result(), _result(), []),
        ("cluster", "", _result(), _result(), []),
        ("cluster", "us-west-2", _result(success=False), _result(), []),
        ("cluster", "us-west-2", _result({"clusterStatus": "CREATE_FAILED"}), _result(), []),
        (
            "cluster",
            "us-west-2",
            _result({"clusterStatus": "CREATE_COMPLETE"}),
            _result(success=False),
            [],
        ),
    ],
)
def test_attach_rejects_invalid_cluster_lifecycle(
    monkeypatch, cluster, region, cluster_result, fleet_result, update_results
):
    monkeypatch.setattr(
        attach.pcluster_runner, "describe_cluster", lambda *_a, **_k: cluster_result
    )
    monkeypatch.setattr(
        attach.pcluster_runner, "describe_compute_fleet", lambda *_a, **_k: fleet_result
    )
    with pytest.raises(SlurmAccountingAttachError):
        attach.attach_slurm_accounting(cluster_name=cluster, region=region)


def test_attach_rejects_dry_run_and_submit_failures(tmp_path, monkeypatch):
    monkeypatch.setattr(
        attach.pcluster_runner,
        "describe_cluster",
        lambda *_a, **_k: _result({"clusterStatus": "CREATE_COMPLETE"}),
    )
    monkeypatch.setattr(
        attach.pcluster_runner,
        "describe_compute_fleet",
        lambda *_a, **_k: _result({"status": "STOPPED"}),
    )
    monkeypatch.setattr(
        attach,
        "prepare_slurm_accounting_update",
        lambda **_k: attach.PreparedSlurmAccountingUpdate(
            "cluster", "us-west-2", "stack", tmp_path / "update.yaml", False
        ),
    )
    monkeypatch.setattr(
        attach.pcluster_runner, "update_cluster", lambda *_a, **_k: _result(success=False)
    )
    with pytest.raises(SlurmAccountingAttachError, match="dry-run"):
        attach.attach_slurm_accounting(cluster_name="cluster", region="us-west-2")

    calls = iter([_result(), _result(success=False)])
    monkeypatch.setattr(attach.pcluster_runner, "update_cluster", lambda *_a, **_k: next(calls))
    with pytest.raises(SlurmAccountingAttachError, match="failed to submit"):
        attach.attach_slurm_accounting(cluster_name="cluster", region="us-west-2")


def test_accounting_validation_render_and_datetime_edges():
    with pytest.raises(ValueError):
        accounting.derive_slurm_accounting_stack_name(" ")
    with pytest.raises(SlurmAccountingError):
        accounting.derive_validation_slurm_accounting_stack_name("bad")
    assert accounting.derive_validation_slurm_accounting_stack_name("20260716T010203Z").endswith(
        "20260716T010203Z"
    )
    with pytest.raises(SlurmAccountingError):
        accounting.validate_database_name("UPPER")
    with pytest.raises(SlurmAccountingError):
        accounting.validate_username("bad-name")
    assert (
        "AdditionalSecurityGroups"
        in accounting.slurm_accounting_render_blocks(_db())[
            "REGSUB_SLURM_ACCOUNTING_HEADNODE_NETWORKING"
        ]
    )
    with pytest.raises(SlurmAccountingError):
        accounting.format_headnode_networking_block(" ")
    for value in ("", "mysql://host:3306", "host"):
        with pytest.raises(SlurmAccountingError):
            accounting._validate_uri(value)
    assert accounting._as_utc("2026-07-16T01:02:03Z").tzinfo == timezone.utc
    assert accounting._as_utc(datetime(2026, 7, 16)).tzinfo == timezone.utc
    with pytest.raises(SlurmAccountingError):
        accounting._as_utc(123)


def test_validation_stack_guard_lists_only_active_post_cutoff():
    now = datetime(2026, 7, 16, tzinfo=timezone.utc)
    stacks = [
        {**_stack("ordinary"), "CreationTime": now},
        {**_stack("dayec-costacct-old"), "CreationTime": "2026-07-01T00:00:00Z"},
        {**_stack("dayec-costacct-deleted", status="DELETE_COMPLETE"), "CreationTime": now},
        {**_stack("dayec-costacct-current"), "CreationTime": now},
    ]

    class Paginator:
        def paginate(self, **_kwargs):
            yield {
                "StackSummaries": [
                    {
                        "StackName": s["StackName"],
                        "StackStatus": s["StackStatus"],
                        "CreationTime": s["CreationTime"],
                    }
                    for s in stacks
                ]
            }

    cfn = FakeCloudFormation(stacks)
    cfn.get_paginator = lambda _name: Paginator()
    ctx = FakeAwsContext(cfn)
    found = accounting.list_active_validation_slurm_accounting_stacks(ctx)
    assert [s["StackName"] for s in found] == ["dayec-costacct-current"]
    with pytest.raises(SlurmAccountingError, match="current"):
        accounting.require_no_active_validation_slurm_accounting_stacks(ctx)


def test_duplicate_selection_edges_and_unknown_attachment_counts(monkeypatch):
    db = _db()
    bad = SlurmAccountingSelectionCandidate(
        "bad", "CREATE_COMPLETE", "vpc-other", False, "wrong vpc", (), db
    )
    with pytest.raises(SlurmAccountingError, match="none is compatible"):
        accounting._select_duplicate_accounting_candidate(
            [bad], preferred_stack_name="", region="us-west-2"
        )

    good = SlurmAccountingSelectionCandidate(
        "good", "CREATE_COMPLETE", "vpc-1", True, "ok", None, db
    )
    warnings: list[str] = []
    sleeps: list[float] = []
    accounting._warn_and_delay_duplicate_accounting_selection(
        [good],
        selected=good,
        selection_reason="test",
        preferred_stack_name="missing",
        region="us-west-2",
        warning_callback=warnings.append,
        sleep_fn=sleeps.append,
    )
    assert sleeps == [60, 20, 10]
    assert any("not selected" in item for item in warnings)
    assert any("attached_hosts=unknown" in item for item in warnings)


def test_stack_and_ec2_helper_failure_contracts(tmp_path, monkeypatch):
    with pytest.raises(SlurmAccountingError):
        accounting.create_slurm_accounting_stack(
            FakeAwsContext(FakeCloudFormation()),
            region_az="us-west-2d",
            vpc_id="vpc",
            private_subnet_id="",
            stack_name="stack",
            database_name="db",
            username="user",
            instance_type="t3.micro",
        )
    with pytest.raises(SlurmAccountingError):
        accounting.create_slurm_accounting_stack(
            FakeAwsContext(FakeCloudFormation()),
            region_az="us-west-2d",
            vpc_id="vpc",
            private_subnet_id="subnet",
            stack_name="",
            database_name="db",
            username="user",
            instance_type="t3.micro",
        )
    template = tmp_path / "template.yaml"
    template.write_text("Resources: {}\n", encoding="utf-8")

    class BrokenCfn(FakeCloudFormation):
        def create_stack(self, **kwargs):
            raise RuntimeError("boom")

    with pytest.raises(SlurmAccountingError, match="did not complete safely"):
        accounting.create_slurm_accounting_stack(
            FakeAwsContext(BrokenCfn()),
            region_az="us-west-2d",
            vpc_id="vpc",
            private_subnet_id="subnet",
            stack_name="stack",
            database_name="db",
            username="user",
            instance_type="t3.micro",
            template_path=str(template),
        )

    class Broken:
        def get_paginator(self, _name):
            raise RuntimeError("boom")

    with pytest.raises(SlurmAccountingError, match="list CloudFormation"):
        list(accounting._list_stack_summaries(Broken()))
    with pytest.raises(SlurmAccountingError, match="describe CloudFormation"):
        accounting._describe_stack_or_none(
            SimpleNamespace(
                describe_stacks=lambda **_k: (_ for _ in ()).throw(RuntimeError("boom"))
            ),
            "stack",
        )
    with pytest.raises(SlurmAccountingError, match="invalid description"):
        accounting._describe_stack_or_none(
            SimpleNamespace(describe_stacks=lambda **_k: {"Stacks": ["bad"]}), "stack"
        )

    broken_ec2 = SimpleNamespace(
        get_paginator=lambda _name: (_ for _ in ()).throw(RuntimeError("boom"))
    )
    with pytest.raises(SlurmAccountingError, match="list EC2"):
        accounting._list_running_instances_in_vpc(broken_ec2, vpc_id="vpc")
    with pytest.raises(SlurmAccountingError, match="inspect EC2 security"):
        accounting._describe_security_groups(
            SimpleNamespace(
                describe_security_groups=lambda **_k: (_ for _ in ()).throw(RuntimeError("boom"))
            ),
            ["sg"],
        )


def test_network_interface_pagination_and_security_signals():
    calls = []

    def describe(**kwargs):
        calls.append(kwargs)
        if "NextToken" not in kwargs:
            return {
                "NetworkInterfaces": [
                    {"Attachment": {}, "Groups": []},
                    _network_interface("i-2", "sg-a"),
                ],
                "NextToken": "next",
            }
        return {"NetworkInterfaces": [_network_interface("i-1", "sg-a")]}

    assert accounting._attached_instance_ids_by_security_group(
        SimpleNamespace(describe_network_interfaces=describe), ["sg-a"]
    ) == {"sg-a": ("i-1", "i-2")}
    assert calls[1]["NextToken"] == "next"
    assert accounting._attached_instance_ids_by_security_group(SimpleNamespace(), []) == {}

    assert accounting._security_group_allows_tcp_port(
        {"IpPermissions": [{"IpProtocol": "-1"}]}, 3306
    )
    assert not accounting._security_group_allows_tcp_port(
        {"IpPermissions": [{"IpProtocol": "udp"}, {"IpProtocol": "tcp"}]}, 3306
    )
    assert accounting._instance_has_mysql_accounting_signal(
        {"Tags": [{"Key": "Name", "Value": "slurm accounting"}], "SecurityGroups": []}, {}
    )
    assert not accounting._instance_has_mysql_accounting_signal(
        {"Tags": [], "SecurityGroups": []}, {}
    )


def test_scan_rejects_empty_vpc_and_skips_instance_without_id():
    with pytest.raises(SlurmAccountingError, match="VPC ID"):
        accounting.scan_slurm_accounting_ec2_candidates(
            FakeAwsContext(FakeCloudFormation(), FakeEc2()), region_az="us-west-2d", vpc_id=" "
        )
    ec2 = FakeEc2(instances=[{"VpcId": "vpc-1", "Tags": []}])
    assert (
        accounting.scan_slurm_accounting_ec2_candidates(
            FakeAwsContext(FakeCloudFormation(), ec2), region_az="us-west-2d", vpc_id="vpc-1"
        )
        == []
    )


def test_persistent2_create_path_records_owned_storage(tmp_path, monkeypatch):
    original = create_cluster.run_create_workflow

    def injected(*args, **kwargs):
        import daylily_ec.aws.context as context
        import daylily_ec.aws.fsx_persistent2 as persistent2

        patched_build = context.AWSContext.build

        def build(cls, *build_args, **build_kwargs):
            ctx = patched_build(*build_args, **build_kwargs)
            ctx._clients["fsx"] = SimpleNamespace()
            return ctx

        monkeypatch.setattr(context.AWSContext, "build", classmethod(build))
        resources = persistent2.Persistent2Resources(
            file_system_id="fs-123",
            security_group_id="sg-123",
            data_repository_association_id="dra-123",
            subnet_id="subnet-priv",
            vpc_id="vpc-123",
        )
        def ensure_resources(*_args, status_callback=None, **_kwargs):
            assert status_callback is not None
            status_callback(
                "P2 filesystem fs-123: lifecycle=CREATING; "
                "waiting for AVAILABLE (45s elapsed)."
            )
            return resources

        monkeypatch.setattr(
            persistent2,
            "ensure_persistent2_resources",
            ensure_resources,
        )
        monkeypatch.setattr(persistent2, "render_external_mount", lambda *_a, **_k: None)
        monkeypatch.setattr(persistent2, "validate_external_mount", lambda *_a, **_k: None)
        monkeypatch.setattr(
            create_cluster, "write_resource_receipt", lambda **_kwargs: tmp_path / "receipt.json"
        )
        return original(*args, **kwargs)

    monkeypatch.setattr(create_cluster, "run_create_workflow", injected)
    records = _run_stubbed_create_workflow(
        tmp_path,
        monkeypatch,
        interactive=False,
        head_node_ip="54.1.2.3",
        say_available=False,
        config_overrides={
            "fsx_deployment_type": ["USESETVALUE", "", "PERSISTENT_2"],
            "fsx_fs_size": ["USESETVALUE", "", "4800"],
            "fsx_throughput_mbps_per_tib": ["USESETVALUE", "", "250"],
            "fsx_lustre_version": ["USESETVALUE", "", "2.15"],
            "fsx_metadata_mode": ["USESETVALUE", "", "AUTOMATIC"],
            "fsx_encryption_mode": ["USESETVALUE", "", "AWS_MANAGED_FSX"],
            "fsx_owner": ["USESETVALUE", "", "DYEC"],
            "fsx_lifecycle": ["USESETVALUE", "", "CLUSTER_BOUND"],
            "sweep_protection_tag": ["USESETVALUE", "", "ursa-preserve=true"],
        },
    )
    assert records["rc"] == create_cluster.EXIT_SUCCESS
    assert ("P2 FSx ready", "fs-123") not in records["details"]
    assert (
        "P2 filesystem fs-123: lifecycle=CREATING; waiting for AVAILABLE (45s elapsed)."
        in records["infos"]
    )


def test_preflight_runner_reports_fail_warn_and_success(monkeypatch):
    reports: list[PreflightReport] = []
    monkeypatch.setattr(create_cluster, "write_preflight_report", reports.append)
    monkeypatch.setattr(create_cluster.ui, "fail", lambda *_a, **_k: None)
    monkeypatch.setattr(create_cluster.ui, "warn", lambda *_a, **_k: None)
    monkeypatch.setattr(create_cluster.ui, "ok", lambda *_a, **_k: None)

    def add(status):
        def step(report):
            report.checks.append(
                CheckResult(
                    id=f"check.{status.value.lower()}",
                    status=status,
                    remediation="fix it",
                )
            )
            return report

        return step

    failed = create_cluster.run_preflight(PreflightReport(), steps=[add(CheckStatus.FAIL)])
    assert create_cluster.should_abort(failed)
    assert create_cluster.exit_code_for(failed) == create_cluster.EXIT_VALIDATION_FAILURE

    warned = create_cluster.run_preflight(PreflightReport(), steps=[add(CheckStatus.WARN)])
    assert create_cluster.should_abort(warned)
    assert create_cluster.exit_code_for(warned) == create_cluster.EXIT_VALIDATION_FAILURE

    passed = create_cluster.run_preflight(
        PreflightReport(), steps=[add(CheckStatus.PASS)], pass_on_warn=True
    )
    assert not create_cluster.should_abort(passed)
    assert create_cluster.exit_code_for(passed) == create_cluster.EXIT_SUCCESS
    assert len(reports) == 3


def test_repository_catalog_preflight_success_and_failure(tmp_path, monkeypatch):
    good = SimpleNamespace(
        command_catalog_version=2,
        default_repository="dayoa",
        repositories={"dayoa": {}},
        commands=lambda: ["clone"],
    )
    monkeypatch.setattr("daylily_ec.repositories.load_repository_catalog", lambda _path: good)
    report = create_cluster.make_repository_catalog_preflight_step(tmp_path / "catalog.yaml")(
        PreflightReport()
    )
    assert report.checks[0].status == CheckStatus.PASS

    monkeypatch.setattr(
        "daylily_ec.repositories.load_repository_catalog",
        lambda _path: (_ for _ in ()).throw(ValueError("bad catalog")),
    )
    report = create_cluster.make_repository_catalog_preflight_step(tmp_path / "catalog.yaml")(
        PreflightReport()
    )
    assert report.checks[0].status == CheckStatus.FAIL


def test_create_validation_and_repo_source_edge_contracts(tmp_path, monkeypatch):
    with pytest.raises(ValueError, match="boolean"):
        create_cluster.validate_regional_cluster_cap_options(
            None, acknowledge_regional_cap_increase="yes"
        )
    with pytest.raises(ValueError, match="integer"):
        create_cluster.validate_regional_cluster_cap_options(True)
    for records in (
        ["bad"],
        [{"clusterName": "", "clusterStatus": "ok"}],
        [{"clusterName": "ok", "clusterStatus": ""}],
    ):
        with pytest.raises(ValueError):
            create_cluster.evaluate_regional_cluster_cap(
                cluster_name="cluster", records=records, effective_cap=5
            )

    create_cluster.clear_preflight_steps()
    create_cluster.register_preflight_step(lambda report: report)
    assert len(create_cluster._PREFLIGHT_STEPS) == 1
    create_cluster.clear_preflight_steps()

    for url in (
        "git@github.com:invalid",
        "ssh://git@github.com/invalid",
        "https://github.com/invalid",
        "ssh://git@example.com/repo",
    ):
        with pytest.raises(RuntimeError):
            create_cluster._normalize_headnode_repo_url(url)
    with pytest.raises(RuntimeError, match="deploy-key"):
        create_cluster._normalize_headnode_repo_url(
            "https://example.com/repo", deploy_key_auth=True
        )

    monkeypatch.delenv("DAYLILY_EC_REPO_ROOT", raising=False)
    with pytest.raises(RuntimeError, match="REPO_ROOT"):
        create_cluster._resolve_headnode_repo_spec(
            "https://github.com/o/r.git", "main", deploy_key_auth=True
        )
    monkeypatch.setenv("DAYLILY_EC_REPO_ROOT", str(tmp_path / "missing"))
    with pytest.raises(RuntimeError, match="does not exist"):
        create_cluster._resolve_headnode_repo_spec("url", "main")

    with pytest.raises(ValueError, match="provided together"):
        create_cluster._build_headnode_repo_sync_command(
            "repo", "url", "main", deploy_key_secret_arn="arn"
        )
    tagged = create_cluster._build_headnode_repo_sync_command("repo", "url", "refs/tags/1.0.0")
    assert "checkout --detach" in tagged
    keyed = create_cluster._build_headnode_repo_sync_command(
        "repo",
        "git@github.com:o/r.git",
        "main",
        deploy_key_secret_arn="arn",
        deploy_key_region="us-west-2",
    )
    assert "GIT_SSH_COMMAND" in keyed


def test_git_ref_failure_branches(tmp_path, monkeypatch):
    monkeypatch.setattr(
        create_cluster,
        "_git_run",
        lambda *_a, **_k: SimpleNamespace(returncode=1, stderr="git failed", stdout=""),
    )
    with pytest.raises(RuntimeError, match="git failed"):
        create_cluster._git_stdout(tmp_path, "status")
    with pytest.raises(RuntimeError, match="not available"):
        create_cluster._require_published_branch(tmp_path, "main")

    calls = iter(["deadbeef", "", "deadbeef", "one\ntwo", "deadbeef", "1.0.0"])
    monkeypatch.setattr(create_cluster, "_git_stdout", lambda *_a, **_k: next(calls))
    with pytest.raises(RuntimeError, match="no exact tag"):
        create_cluster._require_published_detached_tag(tmp_path)
    with pytest.raises(RuntimeError, match="multiple exact tags"):
        create_cluster._require_published_detached_tag(tmp_path)
    with pytest.raises(RuntimeError, match="not available"):
        create_cluster._require_published_detached_tag(tmp_path)


def test_render_policy_and_misc_helper_errors(tmp_path, monkeypatch):
    path = tmp_path / "cluster.yaml"
    for payload in (
        [],
        {"Scheduling": {"SlurmQueues": ["bad"]}},
        {"Scheduling": {}, "HeadNode": []},
        {"Scheduling": {}, "HeadNode": {"Iam": []}},
        {"Scheduling": {}, "HeadNode": {"Iam": {"AdditionalIamPolicies": "bad"}}},
        {
            "Scheduling": {},
            "HeadNode": {"Iam": {"AdditionalIamPolicies": [{"Policy": "p"}, {"Policy": "p"}]}},
        },
    ):
        path.write_text(yaml.safe_dump(payload), encoding="utf-8")
        with pytest.raises(ValueError):
            create_cluster.attach_headnode_managed_policy(path, "p")

    assert create_cluster._extract_s3_roles(PreflightReport()) == {}
    malformed = PreflightReport(
        checks=[CheckResult(id="s3.role_config", status=CheckStatus.PASS, details={"roles": []})]
    )
    assert create_cluster._extract_s3_roles(malformed) == {}
    assert create_cluster._role_uri({}, "missing") == ""
    assert create_cluster._role_bucket({}, "missing") == ""
    assert create_cluster.parse_create_repo_overrides(None) == {}
    with pytest.raises(ValueError):
        create_cluster.parse_create_repo_overrides(["missing-colon"])
    with pytest.raises(ValueError):
        create_cluster.parse_create_repo_overrides(["repo:"])
    with pytest.raises(ValueError):
        create_cluster.parse_create_repo_overrides(["repo:one", "repo:two"])

    blocked = tmp_path / "blocked"
    blocked.mkdir()
    monkeypatch.setattr(
        Path, "write_text", lambda *_a, **_k: (_ for _ in ()).throw(OSError("readonly"))
    )
    with pytest.raises(RuntimeError, match="Failed to write"):
        create_cluster._write_spot_price_partition_markdown(
            {}, cluster_name="cluster", output_path=blocked / "x.md"
        )


@pytest.mark.parametrize(
    "kwargs",
    [
        {"dyec_deploy_key_secret_arn": "arn"},
        {"dayoa_deploy_key_secret_arn": "arn"},
        {"dyec_deploy_key_secret_arn": "arn", "dyec_deploy_key_region": "us-west-2"},
        {
            "dyec_deploy_key_secret_arn": "arn",
            "dyec_deploy_key_region": "us-west-2",
            "dyec_repo_url": "bad",
            "dyec_repo_ref": "main",
        },
    ],
)
def test_configure_headnode_rejects_incomplete_deploy_key_contract(kwargs):
    assert not create_cluster.configure_headnode("cluster", "i-head", "us-west-2", "test", **kwargs)


def test_attach_source_config_and_prepare_input_edges(tmp_path, monkeypatch):
    unreadable = tmp_path / "bad.yaml"
    unreadable.write_text("[", encoding="utf-8")
    with pytest.raises(SlurmAccountingAttachError, match="Could not read"):
        attach._load_cluster_config(unreadable)
    for payload in ({}, {"HeadNode": {}}, {"HeadNode": {"Networking": {"SubnetId": ""}}}):
        with pytest.raises(SlurmAccountingAttachError):
            attach._headnode_subnet_id(payload)
    for cluster, region, reason in (
        ("", "us-west-2", "invalid_cluster_name"),
        ("cluster", "", "invalid_region"),
    ):
        with pytest.raises(SlurmAccountingPreparationError) as caught:
            attach.prepare_slurm_accounting_update(
                cluster_name=cluster, region=region, create_if_missing=False
            )
        assert caught.value.reason_code == reason

    source = _config(tmp_path / "source.yaml")
    monkeypatch.setattr(
        attach.AWSContext,
        "build_region",
        lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("network")),
    )
    with pytest.raises(SlurmAccountingPreparationError) as caught:
        attach.prepare_slurm_accounting_update(
            cluster_name="cluster",
            region="us-west-2",
            cluster_configuration=source,
            create_if_missing=False,
        )
    assert caught.value.reason_code == "subnet_inspection_failed"


def test_accounting_remaining_structured_edges(tmp_path, monkeypatch):
    db = _db()
    empty_secret = accounting.SlurmAccountingDb(
        stack_name=db.stack_name,
        status=db.status,
        uri=db.uri,
        private_ip=db.private_ip,
        database_name=db.database_name,
        username=db.username,
        password_secret_arn="",
        client_security_group_id=db.client_security_group_id,
        instance_id=db.instance_id,
    )
    with pytest.raises(SlurmAccountingError, match="secret ARN"):
        accounting.format_database_block(empty_secret)

    assert (
        accounting.discover_slurm_accounting_dbs(
            FakeAwsContext(FakeCloudFormation()),
            region_az="us-west-2d",
            vpc_id="vpc-123",
            stack_name="missing",
        )
        == []
    )
    assert (
        accounting.list_regional_slurm_accounting_stacks(
            FakeAwsContext(FakeCloudFormation([_stack("stack")])), region_az="us-west-2d"
        )[0]["StackName"]
        == "stack"
    )

    invalid_stack = _stack("bad", outputs=[])
    candidates = accounting._inspect_selection_candidates(
        FakeAwsContext(FakeCloudFormation(), FakeEc2()),
        stacks=[invalid_stack],
        requested_vpc_id="vpc-123",
    )
    assert candidates[0].db is None

    no_vpc_tags = [tag for tag in _tags() if tag["Key"] != accounting.ACCOUNTING_VPC_TAG_KEY]
    monkeypatch.setattr(
        accounting,
        "_attached_instance_ids_by_security_group",
        lambda *_a, **_k: (_ for _ in ()).throw(SlurmAccountingError("count")),
    )
    candidates = accounting._inspect_selection_candidates(
        FakeAwsContext(FakeCloudFormation(), FakeEc2()),
        stacks=[_stack("missing-vpc", tags=no_vpc_tags), invalid_stack],
        requested_vpc_id="vpc-123",
    )
    assert candidates[0].attached_instance_ids is None
    assert candidates[1].attached_instance_ids == ()

    class CreatedButMissing(FakeCloudFormation):
        def create_stack(self, **kwargs):
            self.calls.append(("create_stack", kwargs))

    template = tmp_path / "template.yaml"
    template.write_text("Resources: {}\n", encoding="utf-8")
    with pytest.raises(SlurmAccountingError, match="cannot be described"):
        accounting.create_slurm_accounting_stack(
            FakeAwsContext(CreatedButMissing()),
            region_az="us-west-2d",
            vpc_id="vpc",
            private_subnet_id="subnet",
            stack_name="stack",
            database_name="db",
            username="user",
            instance_type="t3.micro",
            template_path=str(template),
        )
    assert accounting._read_template_body(accounting.DEFAULT_TEMPLATE_PATH)


@pytest.mark.parametrize(
    "output_key",
    [
        "AccountingDbPrivateIp",
        "AccountingPasswordSecretArn",
        "AccountingClientSecurityGroupId",
    ],
)
def test_db_from_stack_rejects_empty_required_output(output_key):
    outputs = _outputs()
    for output in outputs:
        if output["OutputKey"] == output_key:
            output["OutputValue"] = ""
    with pytest.raises(SlurmAccountingError, match=output_key):
        accounting._db_from_stack(_stack("stack", outputs=outputs))


def test_config_prompt_and_network_failure_branches(tmp_path, monkeypatch):
    cfg = _build_workflow_config(tmp_path / "template.yaml")
    cfg.ephemeral_cluster.config["fsx_fs_size"].set_value = "1300"
    with pytest.raises(ValueError, match="Invalid FSx size"):
        create_cluster._resolve_fsx_size(cfg, non_interactive=True)
    cfg.ephemeral_cluster.config["fsx_deployment_type"].set_value = "invalid"
    with pytest.raises(ValueError, match="Invalid fsx_deployment_type"):
        create_cluster._resolve_fsx_deployment_type(cfg, non_interactive=True)
    with pytest.raises(ValueError, match="supported PERSISTENT"):
        create_cluster._resolve_persistent2_config(
            cfg, deployment_type="UNKNOWN", fsx_size="4800", non_interactive=True
        )
    with pytest.raises(ValueError, match="fsx_fs_size"):
        create_cluster._resolve_persistent2_config(
            cfg, deployment_type="PERSISTENT_2", fsx_size="1300", non_interactive=True
        )

    for url in ("ftp://ursa.example", "https://user:pw@ursa.example", "https://ursa.example?a=1"):
        with pytest.raises(ValueError):
            create_cluster._normalize_ursa_root_url(url)
    assert create_cluster._build_ursa_cluster_url("", "cluster", "us-west-2") == ""

    root = tmp_path / "root.yaml"
    for payload in (
        {},
        {"HeadNode": {"LocalStorage": {"RootVolume": {"VolumeType": "", "Size": 1}}}},
        {"HeadNode": {"LocalStorage": {"RootVolume": {"VolumeType": "gp3", "Size": 0}}}},
        {
            "HeadNode": {
                "LocalStorage": {"RootVolume": {"VolumeType": "gp3", "Size": 1, "Iops": 3000}}
            }
        },
    ):
        root.write_text(yaml.safe_dump(payload), encoding="utf-8")
        with pytest.raises(ValueError):
            create_cluster._read_headnode_root_volume_spec(str(root))

    assert create_cluster._resolve_nonprompt_bool_config(cfg, "missing", "true")
    assert not create_cluster._resolve_nonprompt_bool_config(cfg, "missing", "false")
    with pytest.raises(ValueError):
        create_cluster._resolve_nonprompt_bool_config(cfg, "missing", "maybe")
    for name in ("", "abc", "Uppercase", "a" * 21):
        with pytest.raises(ValueError):
            create_cluster.validate_cluster_name(name)
    assert create_cluster.normalize_enforce_budget("enforced") == "true"
    assert create_cluster.normalize_enforce_budget("false") == "skip"
    with pytest.raises(ValueError):
        create_cluster.normalize_enforce_budget("maybe")
    assert create_cluster._require_values({"one": ""}) == "Missing required values: one"

    from daylily_ec.config.models import Triplet

    cfg.ephemeral_cluster.config["public_subnet_id"] = Triplet(
        action="USESETVALUE", default_value="", set_value="subnet-1"
    )
    failing = SimpleNamespace(
        describe_subnets=lambda **_k: (_ for _ in ()).throw(RuntimeError("no subnet"))
    )
    with pytest.raises(ValueError, match="inaccessible"):
        create_cluster._resolve_explicit_subnet_id(
            failing, cfg, "public_subnet_id", label="public", region_az="us-west-2d"
        )
    with pytest.raises(ValueError, match="resolve VPC"):
        create_cluster._resolve_subnet_vpc_id(failing, "subnet-1", label="public")
    with pytest.raises(ValueError, match="route table"):
        create_cluster._subnet_has_public_default_route(failing, "subnet-1", label="public")


def test_interactive_selection_loops_cover_retries(tmp_path, monkeypatch):
    answers = iter(["bad", "9", "2"])
    monkeypatch.setattr(create_cluster.typer, "prompt", lambda *_a, **_k: next(answers))
    monkeypatch.setattr(create_cluster.typer, "echo", lambda *_a, **_k: None)
    assert create_cluster._prompt_select("choice", ["a", "b"]) == "b"

    cfg = _build_workflow_config(tmp_path / "template.yaml")
    cfg.ephemeral_cluster.config.pop("fsx_fs_size", None)
    answers = iter(["bad", "7200"])
    monkeypatch.setattr(create_cluster.typer, "prompt", lambda *_a, **_k: next(answers))
    assert create_cluster._resolve_fsx_size(cfg, non_interactive=False) == "7200"

    cfg.ephemeral_cluster.config.pop("fsx_deployment_type", None)
    answers = iter(["bad", "persistent_2"])
    monkeypatch.setattr(create_cluster.typer, "prompt", lambda *_a, **_k: next(answers))
    assert create_cluster._resolve_fsx_deployment_type(cfg, non_interactive=False) == "PERSISTENT_2"

    answers = iter(["9", "2"])
    monkeypatch.setattr(create_cluster.typer, "prompt", lambda *_a, **_k: next(answers))
    assert create_cluster._prompt_s3_role_choice("S3", ["s3://a", "s3://b"]) == "s3://b"


def test_network_helper_complete_error_and_route_branches():
    class Ec2:
        subnet_payload = {"Subnets": []}
        route_payloads: list[dict] = []

        def describe_subnets(self, **_kwargs):
            return self.subnet_payload

        def describe_route_tables(self, **_kwargs):
            return self.route_payloads.pop(0)

    ec2 = Ec2()
    with pytest.raises(ValueError, match="subnet not found"):
        create_cluster._resolve_subnet_vpc_id(ec2, "subnet", label="public")
    ec2.subnet_payload = {"Subnets": [{}]}
    with pytest.raises(ValueError, match="missing VpcId"):
        create_cluster._resolve_subnet_vpc_id(ec2, "subnet", label="public")
    assert create_cluster._resolve_subnet_vpc_id(ec2, "", label="public") == ""

    with pytest.raises(ValueError, match="missing VpcId"):
        create_cluster._subnet_has_public_default_route(ec2, "subnet", label="public")
    assert not create_cluster._subnet_has_public_default_route(ec2, "", label="public")

    ec2.subnet_payload = {"Subnets": [{"VpcId": "vpc-1"}]}
    ec2.route_payloads = [
        {"RouteTables": []},
        {
            "RouteTables": [
                {
                    "Associations": [{"Main": True}],
                    "Routes": [
                        {
                            "State": "blackhole",
                            "DestinationCidrBlock": "0.0.0.0/0",
                            "GatewayId": "igw-bad",
                        },
                        {
                            "State": "active",
                            "DestinationCidrBlock": "0.0.0.0/0",
                            "GatewayId": "nat-1",
                        },
                    ],
                }
            ]
        },
    ]
    assert not create_cluster._subnet_has_public_default_route(ec2, "subnet", label="public")
    ec2.route_payloads = [
        {
            "RouteTables": [
                {
                    "Routes": [
                        {
                            "State": "active",
                            "DestinationCidrBlock": "0.0.0.0/0",
                            "GatewayId": "igw-1",
                        }
                    ]
                }
            ]
        }
    ]
    assert create_cluster._subnet_has_public_default_route(ec2, "subnet", label="public")


@pytest.mark.parametrize(
    "failure",
    ["deploy", "repo", "preflight", "baseline", "publish_value", "publish_aws", "idle"],
)
def test_additional_create_pre_mutation_failures(tmp_path, monkeypatch, failure):
    original = create_cluster.run_create_workflow

    def injected(*args, **kwargs):
        import daylily_ec.aws.cloudformation as cfn
        import daylily_ec.aws.idle_cost as idle

        if failure == "deploy":
            monkeypatch.setattr(
                create_cluster,
                "resolve_dyec_deploy_key_inputs",
                lambda *_a, **_k: (_ for _ in ()).throw(ValueError("deploy")),
            )
        elif failure == "repo":
            monkeypatch.setattr(
                create_cluster,
                "resolve_configured_headnode_repo_spec",
                lambda **_k: (_ for _ in ()).throw(RuntimeError("repo")),
            )
        elif failure == "preflight":
            monkeypatch.setattr(create_cluster, "should_abort", lambda *_a, **_k: True)
            monkeypatch.setattr(create_cluster, "exit_code_for", lambda _report: 1)
        elif failure == "baseline":
            monkeypatch.setattr(
                cfn,
                "ensure_pcluster_env_stack",
                lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("cfn")),
            )
        elif failure in {"publish_value", "publish_aws"}:
            error = ValueError("publish") if failure == "publish_value" else RuntimeError("aws")
            monkeypatch.setattr(
                create_cluster,
                "publish_cluster_boot_config",
                lambda *_a, **_k: (_ for _ in ()).throw(error),
            )
        elif failure == "idle":
            monkeypatch.setattr(
                create_cluster,
                "estimate_idle_cluster_cost",
                lambda *_a, **_k: (_ for _ in ()).throw(idle.IdleCostPricingError("price")),
            )
        return original(*args, **kwargs)

    monkeypatch.setattr(create_cluster, "run_create_workflow", injected)
    records = _run_stubbed_create_workflow(
        tmp_path,
        monkeypatch,
        interactive=False,
        head_node_ip="54.1.2.3",
        say_available=False,
    )
    assert records["rc"] != create_cluster.EXIT_SUCCESS


def test_cpu_only_contract_rejects_each_required_surface(tmp_path):
    path = tmp_path / "cluster.yaml"
    base = {
        "Region": "us-west-2",
        "HeadNode": {
            "CustomActions": {
                "OnNodeStart": {
                    "Script": "s3://boot/install_slurm_job_submit_policy.sh",
                    "Args": ["us-west-2", "s3://boot"],
                }
            }
        },
        "Scheduling": {
            "Scheduler": "slurm",
            "SlurmSettings": {
                "EnableMemoryBasedScheduling": False,
                "CustomSlurmSettings": create_cluster.CPU_ONLY_SLURM_CUSTOM_SETTINGS,
            },
            "SlurmQueues": [{"Name": "q", "JobExclusiveAllocation": False}],
        },
    }
    path.write_text(yaml.safe_dump(base), encoding="utf-8")
    create_cluster.validate_cpu_only_slurm_contract(path)
    variants = []
    for mutate in (
        lambda p: p["Scheduling"].update(Scheduler="awsbatch"),
        lambda p: p["Scheduling"]["SlurmSettings"].update(EnableMemoryBasedScheduling=True),
        lambda p: p["Scheduling"]["SlurmSettings"].update(CustomSlurmSettings=[]),
        lambda p: p["HeadNode"].update(CustomActions={}),
        lambda p: p.update(SchedulableMemory=1),
        lambda p: p["Scheduling"].update(SlurmQueues=[]),
        lambda p: p["Scheduling"]["SlurmQueues"][0].update(JobExclusiveAllocation=True),
    ):
        payload = yaml.safe_load(yaml.safe_dump(base))
        mutate(payload)
        variants.append(payload)
    for payload in variants:
        path.write_text(yaml.safe_dump(payload), encoding="utf-8")
        with pytest.raises(ValueError):
            create_cluster.validate_cpu_only_slurm_contract(path)


def test_startup_dra_external_and_missing_path_contracts(tmp_path):
    path = tmp_path / "cluster.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "SharedStorage": [
                    {
                        "StorageType": "FsxLustre",
                        "FsxLustreSettings": {"FileSystemId": "invalid", "Extra": 1},
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="External FSx"):
        create_cluster.validate_startup_dra_contract(path)
    path.write_text(
        yaml.safe_dump(
            {
                "SharedStorage": [
                    {
                        "StorageType": "FsxLustre",
                        "FsxLustreSettings": {
                            "DataRepositoryAssociations": [{"FileSystemPath": "/references/"}]
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="DataRepositoryPath"):
        create_cluster.validate_startup_dra_contract(path)


def _render_contract_template(tmp_path: Path, family: str):
    region_az = "us-west-2c" if family == "sentieon-single" else "us-west-2b"
    template = Path(
        f"config/day_cluster/{family}/us-west-2/{region_az}/prod_cluster_{family}_{region_az}.yaml"
    ).read_text(encoding="utf-8")
    values = {key: "value" for key in renderer.ALL_SUBSTITUTION_KEYS}
    values.update(
        {
            "REGSUB_REGION": "us-west-2",
            "REGSUB_PUB_SUBNET": "subnet-public",
            "REGSUB_PRIVATE_SUBNET": "subnet-private",
            "REGSUB_CLUSTER_NAME": "contract-test",
            "REGSUB_HEADNODE_INSTANCE_TYPE": "r7i.2xlarge",
            "REGSUB_S3_BUCKET_INIT": "s3://private-assets/boot",
            "REGSUB_S3_IAM_POLICY": "arn:aws:iam::123456789012:policy/cluster",
            "REGSUB_S3_REFERENCE_BUCKET": "references",
            "REGSUB_S3_CONTROL_DATA_BUCKET": "controls",
            "REGSUB_S3_STAGE_BUCKET": "stage",
            "REGSUB_S3_EXPORT_BUCKET": "export",
            "REGSUB_S3_REFERENCE_URI": "s3://references",
            "REGSUB_FSX_SIZE": "4800",
            "REGSUB_DETAILED_MONITORING": "false",
            "REGSUB_DELETE_LOCAL_ROOT": "true",
            "REGSUB_SAVE_FSX": "Delete",
            "REGSUB_ENFORCE_BUDGET": '"true"',
            "REGSUB_SPOT_PRICE_WARN_THRESHOLD": '"8.00"',
            "REGSUB_SLURM_ACCOUNTING_HEADNODE_NETWORKING": "",
            "REGSUB_SLURM_ACCOUNTING_DATABASE": "",
            "REGSUB_MAX_COUNT_192I_M": "1",
            "REGSUB_MAX_COUNT_192I_NVME_M": "1",
        }
    )
    secret = "arn:aws:secretsmanager:us-west-2:123456789012:secret:dragen"
    policy = "arn:aws:iam::123456789012:policy/dragen"
    image = "ami-0123456789abcdef0"
    cookbook = "s3://private-assets/cookbook.tgz"
    values.update(
        {
            "REGSUB_DRAGEN_PCLUSTER_AMI": image,
            "REGSUB_DRAGEN_LICENSE_SECRET_ARN": secret,
            "REGSUB_DRAGEN_LICENSE_POLICY_ARN": policy,
            "REGSUB_PCLUSTER_COOKBOOK_URI": cookbook,
        }
    )
    payload = yaml.safe_load(renderer.render_template(template, values))
    path = tmp_path / f"{family}.yaml"
    inputs = create_cluster.DragenCreateInputs(
        backport=SimpleNamespace(image_ami_id=image, cookbook_bundle_uri=cookbook),
        license_secret_arn=secret,
        license_policy_arn=policy,
    )
    return path, payload, inputs


@pytest.mark.parametrize(
    "mutation",
    [
        "region",
        "image",
        "head_script",
        "head_args",
        "queue_names",
        "capacity",
        "allocation",
        "mount",
        "queue_script",
        "resources",
        "resource_name",
        "instances",
        "counts",
        "efa",
        "storage_count",
        "storage_mount",
        "storage_capacity",
        "dra_count",
        "dra_contract",
    ],
)
def test_sentieon_contract_rejection_matrix(tmp_path, mutation):
    path, payload, _inputs = _render_contract_template(tmp_path, "sentieon-single")
    queue = payload["Scheduling"]["SlurmQueues"][0]
    resource = queue["ComputeResources"][0]
    storage = payload["SharedStorage"][0]
    dra = storage["FsxLustreSettings"]["DataRepositoryAssociations"][0]
    if mutation == "region":
        payload["Region"] = "us-east-1"
    elif mutation == "image":
        payload["Image"] = {"Os": "almalinux8"}
    elif mutation == "head_script":
        payload["HeadNode"]["CustomActions"]["OnNodeConfigured"]["Script"] = "bad"
    elif mutation == "head_args":
        payload["HeadNode"]["CustomActions"]["OnNodeConfigured"]["Args"] = []
    elif mutation == "queue_names":
        payload["Scheduling"]["SlurmQueues"] = payload["Scheduling"]["SlurmQueues"][:-1]
    elif mutation == "capacity":
        queue["CapacityType"] = "ONDEMAND"
    elif mutation == "allocation":
        queue["AllocationStrategy"] = "capacity-optimized"
    elif mutation == "mount":
        queue["ComputeSettings"]["LocalStorage"]["EphemeralVolume"]["MountDir"] = "/tmp"
    elif mutation == "queue_script":
        queue["CustomActions"]["OnNodeConfigured"]["Script"] = "bad"
    elif mutation == "resources":
        queue["ComputeResources"] = []
    elif mutation == "resource_name":
        resource["Name"] = "bad"
    elif mutation == "instances":
        resource["Instances"] = []
    elif mutation == "counts":
        resource["MaxCount"] = 99
    elif mutation == "efa":
        resource["Efa"]["Enabled"] = True
    elif mutation == "storage_count":
        payload["SharedStorage"] = []
    elif mutation == "storage_mount":
        storage["MountDir"] = "/wrong"
    elif mutation == "storage_capacity":
        storage["FsxLustreSettings"]["StorageCapacity"] = 2400
    elif mutation == "dra_count":
        storage["FsxLustreSettings"]["DataRepositoryAssociations"] = []
    elif mutation == "dra_contract":
        dra["AutoImportPolicy"] = []
    path.write_text(yaml.safe_dump(payload), encoding="utf-8")
    with pytest.raises(ValueError):
        create_cluster.validate_sentieon_single_cluster_contract(path)


@pytest.mark.parametrize(
    "mutation",
    [
        "os",
        "cluster_ami",
        "head_ami",
        "head_policy",
        "head_script",
        "head_args",
        "queue_capacity",
        "queue_ami",
        "resources",
        "resource_name",
        "instances",
        "efa",
        "ondemand_spot",
        "cpu_capacity",
        "cpu_ami",
        "cpu_policy",
        "cpu_script",
        "cpu_args",
        "cpu_resources",
        "cpu_resource_name",
        "cpu_instances",
        "cpu_min",
        "cpu_max",
        "cpu_efa",
        "cookbook",
    ],
)
def test_dragen_contract_rejection_matrix(tmp_path, mutation):
    path, payload, inputs = _render_contract_template(tmp_path, "dragen")
    queue = payload["Scheduling"]["SlurmQueues"][0]
    ondemand = payload["Scheduling"]["SlurmQueues"][1]
    cpu = payload["Scheduling"]["SlurmQueues"][2]
    resource = queue["ComputeResources"][0]
    cpu_resource = cpu["ComputeResources"][0]
    if mutation == "os":
        payload["Image"]["Os"] = "ubuntu2204"
    elif mutation == "cluster_ami":
        payload["Image"]["CustomAmi"] = "ami-bad"
    elif mutation == "head_ami":
        payload["HeadNode"]["Image"]["CustomAmi"] = "ami-bad"
    elif mutation == "head_policy":
        payload["HeadNode"]["Iam"]["AdditionalIamPolicies"] = []
    elif mutation == "head_script":
        payload["HeadNode"]["CustomActions"]["OnNodeConfigured"]["Script"] = "bad"
    elif mutation == "head_args":
        payload["HeadNode"]["CustomActions"]["OnNodeConfigured"]["Args"] = []
    elif mutation == "queue_capacity":
        queue["CapacityType"] = "ONDEMAND"
    elif mutation == "queue_ami":
        queue["Image"]["CustomAmi"] = "ami-bad"
    elif mutation == "resources":
        queue["ComputeResources"] = []
    elif mutation == "resource_name":
        resource["Name"] = "bad"
    elif mutation == "instances":
        resource["Instances"] = []
    elif mutation == "efa":
        resource["Efa"]["Enabled"] = True
    elif mutation == "ondemand_spot":
        ondemand["ComputeResources"][0]["SpotPrice"] = "1"
    elif mutation == "cpu_capacity":
        cpu["CapacityType"] = "ONDEMAND"
    elif mutation == "cpu_ami":
        cpu["Image"]["CustomAmi"] = "ami-bad"
    elif mutation == "cpu_policy":
        cpu["Iam"]["AdditionalIamPolicies"].append({"Policy": inputs.license_policy_arn})
    elif mutation == "cpu_script":
        cpu["CustomActions"]["OnNodeConfigured"]["Script"] = "bad"
    elif mutation == "cpu_args":
        cpu["CustomActions"]["OnNodeConfigured"]["Args"] = []
    elif mutation == "cpu_resources":
        cpu["ComputeResources"] = []
    elif mutation == "cpu_resource_name":
        cpu_resource["Name"] = "bad"
    elif mutation == "cpu_instances":
        cpu_resource["Instances"] = []
    elif mutation == "cpu_min":
        cpu_resource["MinCount"] = 1
    elif mutation == "cpu_max":
        cpu_resource["MaxCount"] = 0
    elif mutation == "cpu_efa":
        cpu_resource["Efa"]["Enabled"] = True
    elif mutation == "cookbook":
        payload["DevSettings"]["Cookbook"]["ChefCookbook"] = "s3://bad"
    path.write_text(yaml.safe_dump(payload), encoding="utf-8")
    with pytest.raises(ValueError):
        create_cluster.validate_dragen_cluster_contract(path, inputs)


def test_create_rejects_invalid_accounting_and_cluster_type_before_aws(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert (
        create_cluster.run_create_workflow(
            "us-west-2d", slurm_accounting="ON", non_interactive=True
        )
        == create_cluster.EXIT_VALIDATION_FAILURE
    )
    assert (
        create_cluster.run_create_workflow(
            "us-west-2d", cluster_type="unknown", non_interactive=True
        )
        == create_cluster.EXIT_VALIDATION_FAILURE
    )


@pytest.mark.parametrize(
    ("overrides", "failure"),
    [
        ({"ursa_root_url": ["USESETVALUE", "", "ftp://invalid"]}, "ursa"),
        ({"fsx_deployment_type": ["USESETVALUE", "", "INVALID"]}, "fsx"),
        ({"max_count_96I_NVME": ["USESETVALUE", "", ""]}, "max96"),
    ],
)
def test_create_config_validation_exits(tmp_path, monkeypatch, overrides, failure):
    records = _run_stubbed_create_workflow(
        tmp_path,
        monkeypatch,
        interactive=False,
        head_node_ip="54.1.2.3",
        say_available=False,
        config_overrides=overrides,
    )
    assert records["rc"] == create_cluster.EXIT_VALIDATION_FAILURE


@pytest.mark.parametrize(
    "failure",
    ["public_subnet", "private_subnet", "missing_resources", "p2_value", "p2_aws", "heartbeat"],
)
def test_remaining_create_recovery_gates(tmp_path, monkeypatch, failure):
    original = create_cluster.run_create_workflow

    def injected(*args, **kwargs):
        import daylily_ec.aws.fsx_persistent2 as persistent2
        import daylily_ec.aws.heartbeat as heartbeat

        if failure in {"public_subnet", "private_subnet"}:
            original_resolve = create_cluster._resolve_explicit_subnet_id

            def resolve(*resolve_args, **resolve_kwargs):
                if resolve_args[2] == (
                    "public_subnet_id" if failure == "public_subnet" else "private_subnet_id"
                ):
                    raise ValueError("invalid subnet")
                return original_resolve(*resolve_args, **resolve_kwargs)

            monkeypatch.setattr(create_cluster, "_resolve_explicit_subnet_id", resolve)
        elif failure == "missing_resources":
            monkeypatch.setattr(create_cluster, "_require_values", lambda _values: "missing")
        elif failure in {"p2_value", "p2_aws"}:
            error = ValueError("contract") if failure == "p2_value" else RuntimeError("aws")
            monkeypatch.setattr(
                persistent2,
                "ensure_persistent2_resources",
                lambda *_a, **_k: (_ for _ in ()).throw(error),
            )
        elif failure == "heartbeat":
            monkeypatch.setattr(
                heartbeat,
                "ensure_heartbeat",
                lambda *_a, **_k: SimpleNamespace(success=False, error="heartbeat failed"),
            )
        return original(*args, **kwargs)

    monkeypatch.setattr(create_cluster, "run_create_workflow", injected)
    p2 = {
        "fsx_deployment_type": ["USESETVALUE", "", "PERSISTENT_2"],
        "fsx_fs_size": ["USESETVALUE", "", "4800"],
        "fsx_throughput_mbps_per_tib": ["USESETVALUE", "", "250"],
        "fsx_lustre_version": ["USESETVALUE", "", "2.15"],
        "fsx_metadata_mode": ["USESETVALUE", "", "AUTOMATIC"],
        "fsx_encryption_mode": ["USESETVALUE", "", "AWS_MANAGED_FSX"],
        "fsx_owner": ["USESETVALUE", "", "DYEC"],
        "fsx_lifecycle": ["USESETVALUE", "", "CLUSTER_BOUND"],
        "sweep_protection_tag": ["USESETVALUE", "", "ursa-preserve=true"],
    }
    records = _run_stubbed_create_workflow(
        tmp_path,
        monkeypatch,
        interactive=False,
        head_node_ip="54.1.2.3",
        say_available=False,
        config_overrides=p2 if failure.startswith("p2_") else None,
    )
    if failure == "heartbeat":
        assert records["rc"] == create_cluster.EXIT_SUCCESS
        assert any("Heartbeat failed" in warning for warning in records["warnings"])
    else:
        assert records["rc"] != create_cluster.EXIT_SUCCESS


def test_create_skips_heartbeat_and_unconfigured_ursa_page(tmp_path, monkeypatch):
    records = _run_stubbed_create_workflow(
        tmp_path,
        monkeypatch,
        interactive=False,
        head_node_ip="54.1.2.3",
        say_available=False,
        config_overrides={
            "heartbeat_email": ["USESETVALUE", "", ""],
            "ursa_root_url": ["USESETVALUE", "", ""],
        },
    )
    assert records["rc"] == create_cluster.EXIT_SUCCESS
    assert any("not configured" in line for line in records["echoes"])


def test_latest_config_ignores_each_nonmatching_receipt_shape(tmp_path, monkeypatch):
    directory = tmp_path / "state"
    directory.mkdir()
    valid = _config(tmp_path / "valid.yaml")
    payloads = [
        "not-json",
        {"cluster_name": "other", "region": "us-west-2"},
        {"cluster_name": "cluster", "region": "us-east-1"},
        {"cluster_name": "cluster", "region": "us-west-2", "aws_profile": "other"},
        {"cluster_name": "cluster", "region": "us-west-2", "aws_profile": "p", "run_id": "1"},
        {
            "cluster_name": "cluster",
            "region": "us-west-2",
            "aws_profile": "p",
            "cluster_yaml_path": str(valid),
        },
    ]
    for index, payload in enumerate(payloads):
        text = payload if isinstance(payload, str) else __import__("json").dumps(payload)
        (directory / f"state_cluster_{index}.json").write_text(text, encoding="utf-8")
    (directory / "state_cluster_9.json").write_text(
        __import__("json").dumps(
            {
                "cluster_name": "cluster",
                "region": "us-west-2",
                "aws_profile": "p",
                "cluster_yaml_path": str(valid),
                "run_id": "9",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(attach, "config_dir", lambda: directory)
    assert attach._latest_cluster_config("cluster", "us-west-2", profile="p") == valid


def test_repository_catalog_path_local_and_packaged(tmp_path, monkeypatch):
    local = tmp_path / "config/daylily_pipeline_command_catalog.yaml"
    local.parent.mkdir()
    local.write_text("repositories: {}\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert create_cluster._repository_catalog_path() == Path(
        "config/daylily_pipeline_command_catalog.yaml"
    )
    local.unlink()
    packaged = tmp_path / "packaged.yaml"
    monkeypatch.setattr("daylily_ec.repositories.default_catalog_path", lambda: packaged)
    assert create_cluster._repository_catalog_path() == packaged


def test_optional_speech_failure_is_nonfatal(monkeypatch):
    monkeypatch.setattr(
        create_cluster.subprocess,
        "run",
        lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("no speech")),
    )
    create_cluster._maybe_say_onward()
