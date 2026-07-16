"""Edge behavior coverage for AWS validation and FSx run-mount helpers."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from botocore.exceptions import ClientError

import daylily_ec.aws.validation as v
import daylily_ec.run_mounts as mounts
from daylily_ec.state.models import CheckResult, CheckStatus


def _record(**updates) -> mounts.RunMountRecord:
    values = dict(
        mount_id="run",
        purpose=mounts.MOUNT_PURPOSE_RUN,
        run_id="run",
        platform="ILMN",
        cluster_name="cluster",
        region="us-west-2",
        source_s3_uri="s3://bucket/run/",
        fsx_file_system_id="fs-1",
        file_system_path="/run_dir_mounts/run/",
        headnode_path="/fsx/run_dir_mounts/run/",
        association_id="dra-1",
        lifecycle="AVAILABLE",
        read_only=True,
        auto_import_events=("NEW",),
        created_at="2026-07-16T00:00:00Z",
    )
    values.update(updates)
    return mounts.RunMountRecord(**values)


def test_run_mount_path_event_and_overlap_edges():
    assert mounts._normalize_absolute_fsx_api_path("/custom/path") == "/custom/path/"
    assert (
        mounts.normalize_file_system_path(
            "/control_data", mount_id="ignored", purpose=mounts.MOUNT_PURPOSE_CONTROL_DATA
        )
        == "/control_data/"
    )
    assert mounts.headnode_path_from_file_system_path("/control_data") == "/fsx/control_data/"
    assert mounts.headnode_path_from_file_system_path("/custom") == "/fsx/custom/"
    with pytest.raises(mounts.RunMountError, match="S3 source prefix overlaps"):
        mounts.validate_no_overlaps(
            [
                {
                    "Lifecycle": "AVAILABLE",
                    "FileSystemPath": "/elsewhere/",
                    "DataRepositoryPath": "s3://bucket/run/child/",
                    "AssociationId": "dra",
                }
            ],
            file_system_path="/custom/path/",
            source_s3_uri="s3://bucket/run/",
        )
    assert mounts.parse_auto_import_events(None) == list(mounts.DEFAULT_AUTO_IMPORT_EVENTS)
    assert mounts.parse_auto_export_events(None, allow_writeback_admin=False, read_only=True) == []
    assert mounts._parse_event_tokens("", default=("NEW",)) == ["NEW"]
    assert mounts._parse_event_tokens("none", default=("NEW",)) == []
    assert mounts._parse_event_tokens("all", default=()) == list(mounts.ALL_AUTO_IMPORT_EVENTS)
    assert mounts._parse_event_tokens("new,NEW changed", default=()) == ["NEW", "CHANGED"]
    with pytest.raises(mounts.RunMountError, match="Unsupported"):
        mounts._parse_event_tokens("impossible", default=())


class _Paginator:
    def __init__(self, pages):
        self.pages = pages

    def paginate(self, **_kwargs):
        return list(self.pages)


class _FsxResolver:
    def __init__(self, pages=None, error=None):
        self.pages = pages or []
        self.error = error

    def get_paginator(self, operation):
        assert operation == "describe_file_systems"
        if self.error:
            raise self.error
        return _Paginator(self.pages)


def _filesystem(fs_id, cluster):
    return {
        "FileSystemId": fs_id,
        "Tags": [{"Key": "parallelcluster:cluster-name", "Value": cluster}],
    }


def test_fsx_resolution_covers_success_none_multiple_and_client_failure():
    with pytest.raises(mounts.RunMountError, match="cluster_name is required"):
        mounts.resolve_fsx_file_system_id(_FsxResolver(), "")
    assert (
        mounts.resolve_fsx_file_system_id(
            _FsxResolver([{"FileSystems": [_filesystem("fs-1", "cluster")]}]),
            "cluster",
        )
        == "fs-1"
    )
    with pytest.raises(mounts.RunMountError, match="No FSx"):
        mounts.resolve_fsx_file_system_id(
            _FsxResolver([{"FileSystems": [_filesystem("fs-1", "other")]}]), "cluster"
        )
    with pytest.raises(mounts.RunMountError, match="Multiple FSx"):
        mounts.resolve_fsx_file_system_id(
            _FsxResolver(
                [
                    {
                        "FileSystems": [
                            _filesystem("fs-1", "cluster"),
                            _filesystem("fs-2", "cluster"),
                        ]
                    }
                ]
            ),
            "cluster",
        )
    with pytest.raises(mounts.RunMountError, match="Unable to describe"):
        mounts.resolve_fsx_file_system_id(_FsxResolver(error=RuntimeError("denied")), "cluster")


class _DescribeFsx:
    def __init__(self, payload=None, error=None):
        self.payload = payload or {}
        self.error = error

    def describe_file_systems(self, **_kwargs):
        if self.error:
            raise self.error
        return self.payload


def test_fsx_describe_and_compatibility_fail_closed():
    with pytest.raises(mounts.RunMountError, match="required"):
        mounts.describe_fsx_file_system(_DescribeFsx(), "")
    with pytest.raises(mounts.RunMountError, match="Unable to describe FSx"):
        mounts.describe_fsx_file_system(_DescribeFsx(error=RuntimeError("denied")), "fs-1")
    with pytest.raises(mounts.RunMountError, match="exactly one"):
        mounts.describe_fsx_file_system(_DescribeFsx({"FileSystems": []}), "fs-1")
    with pytest.raises(mounts.RunMountError, match="Malformed"):
        mounts.describe_fsx_file_system(_DescribeFsx({"FileSystems": ["bad"]}), "fs-1")
    with pytest.raises(mounts.RunMountError, match="require Lustre"):
        mounts.validate_dra_compatible_file_system(
            {"FileSystemId": "fs", "FileSystemType": "WINDOWS"}
        )
    with pytest.raises(mounts.RunMountError, match="require AVAILABLE"):
        mounts.validate_dra_compatible_file_system(
            {
                "FileSystemId": "fs",
                "FileSystemType": "LUSTRE",
                "Lifecycle": "UPDATING",
            }
        )


class _AssociationClient:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []

    def describe_data_repository_associations(self, **kwargs):
        self.calls.append(kwargs)
        result = next(self.responses)
        if isinstance(result, Exception):
            raise result
        return result


def _client_error(code="Denied"):
    return ClientError({"Error": {"Code": code, "Message": code}}, "operation")


def test_association_pagination_wait_and_delete_recovery(monkeypatch):
    client = _AssociationClient(
        [
            {"Associations": [{"AssociationId": "a"}], "NextToken": "next"},
            {"Associations": [{"AssociationId": "b"}]},
        ]
    )
    assert len(mounts.describe_data_repository_associations(client)) == 2
    assert client.calls[1]["NextToken"] == "next"
    with pytest.raises(mounts.RunMountError, match="Unable to describe"):
        mounts.describe_data_repository_associations(_AssociationClient([_client_error()]))

    monkeypatch.setattr(mounts.time, "time", lambda: 10)
    with pytest.raises(mounts.RunMountError, match="Timed out"):
        mounts.wait_for_association(
            _AssociationClient([{"Associations": [{"Lifecycle": "CREATING"}]}]),
            "dra",
            target_lifecycles=("AVAILABLE",),
            timeout_seconds=0,
            poll_interval_seconds=0,
        )
    deleted = mounts.wait_for_deleted_association(
        _AssociationClient([{"Associations": []}]),
        "dra",
        fallback_association={"AssociationId": "dra"},
        timeout_seconds=1,
    )
    assert deleted["Lifecycle"] == "DELETED"
    with pytest.raises(mounts.RunMountError, match="Timed out"):
        mounts.wait_for_deleted_association(
            _AssociationClient([{"Associations": [{"Lifecycle": "DELETING"}]}]),
            "dra",
            fallback_association={},
            timeout_seconds=0,
            poll_interval_seconds=0,
        )


def test_mount_record_projection_formatting_clients_and_local_state(tmp_path, monkeypatch):
    assert mounts.extract_mount_id("/staging/staged_external_sequencing_data/stage-1/") == "stage-1"
    record = _record(auto_export_events=("NEW",))
    association = mounts._association_from_record(record, lifecycle="DELETING")
    assert association["S3"]["AutoExportPolicy"]["Events"] == ["NEW"]
    assert json.loads(mounts.format_mount_described(record))["mount_id"] == "run"
    assert mounts.format_mount_list([]) == "No mounts found."
    assert "MOUNT_ID" in mounts.format_mount_list([record])

    sessions = []

    class Session:
        def __init__(self, **kwargs):
            sessions.append(kwargs)

        def client(self, service):
            return service

    monkeypatch.setattr(mounts.boto3, "Session", Session)
    assert mounts._build_fsx_client(region="us-west-2", profile="lsmc") == "fsx"
    assert mounts._build_s3_client(region="us-west-2", profile=None) == "s3"
    assert sessions == [
        {"region_name": "us-west-2", "profile_name": "lsmc"},
        {"region_name": "us-west-2"},
    ]

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    owner = tmp_path / "daylily" / "run_mounts" / "us-west-2" / "cluster"
    owner.mkdir(parents=True)
    (owner / "bad.json").write_text("not-json", encoding="utf-8")
    (owner / "run.json").write_text(json.dumps(record.to_state_payload()), encoding="utf-8")
    loaded = mounts._load_mount_records_by_mount_id(
        region="us-west-2", cluster_name="cluster", fsx_file_system_id=None
    )
    assert loaded["run"].association_id == "dra-1"
    assert (
        mounts._load_mount_record(
            region="us-west-2", cluster_name="cluster", fsx_file_system_id=None, mount_id="run"
        ).association_id
        == "dra-1"
    )
    assert mounts._find_local_record_by_association_id("us-west-2", "dra-1").mount_id == "run"


@pytest.mark.parametrize(
    ("instance_type", "expected"),
    [
        ("hpc7g.4xlarge", "hpc"),
        ("inf2.xlarge", "inf"),
        ("trn1.2xlarge", "trn"),
        ("dl1.24xlarge", "dl"),
        ("g6.xlarge", "g_vt"),
        ("x2idn.xlarge", "x"),
        ("f2.6xlarge", "f"),
        ("p5.48xlarge", "p"),
        ("u-12tb1.112xlarge", "high_memory"),
        ("m7i.large", "standard"),
        ("weird.1", "unmapped_weird"),
        ("", "unmapped_unknown"),
    ],
)
def test_vcpu_quota_family_mapping(instance_type, expected):
    assert v._ec2_vcpu_quota_group(instance_type) == expected


def test_network_usage_counters_cover_pagination_batching_and_filters():
    class Ec2:
        def get_paginator(self, operation):
            assert operation == "describe_nat_gateways"
            return _Paginator(
                [
                    {
                        "NatGateways": [
                            {"SubnetId": "subnet-a"},
                            {"SubnetId": "subnet-b"},
                            {},
                        ]
                    }
                ]
            )

        def describe_subnets(self, **_kwargs):
            return {
                "Subnets": [
                    {"SubnetId": "subnet-a", "AvailabilityZone": "us-west-2c"},
                    {"SubnetId": "subnet-b", "AvailabilityZone": "us-west-2d"},
                ]
            }

        def describe_addresses(self):
            return {
                "Addresses": [
                    {"PublicIpv4Pool": "amazon"},
                    {"PublicIpv4Pool": "amazon", "ServiceManaged": True},
                    {"PublicIpv4Pool": "byoip"},
                ]
            }

    ec2 = Ec2()
    assert v._count_nat_gateways_in_az(ec2, region_az="us-west-2c", request={}) == 1
    assert v._count_customer_managed_amazon_eips(ec2) == 1


def test_count_headroom_and_named_quota_lookup_edges():
    check = CheckResult(
        id="quota", status=CheckStatus.PASS, details={"current_value": 2, "quota_code": "q"}
    )
    v._apply_count_headroom(check, current_used=2, required_new=1)
    assert check.status == CheckStatus.FAIL
    warn = CheckResult(id="quota", status=CheckStatus.WARN, details={"current_value": 10})
    v._apply_count_headroom(warn, current_used=1, required_new=1)
    assert warn.status == CheckStatus.WARN
    unknown = CheckResult(id="quota", status=CheckStatus.PASS, details={"current_value": None})
    v._apply_count_headroom(unknown, current_used=1, required_new=1)
    assert "projected_used" not in unknown.details

    class Quotas:
        def get_paginator(self, operation):
            if operation == "list_service_quotas":
                return _Paginator([{"Quotas": [{"QuotaName": "General Purpose gp3", "Value": 2}]}])
            raise RuntimeError("no paginator")

        def list_aws_default_service_quotas(self, **_kwargs):
            return {"Quotas": []}

    assert (
        v._find_quota_by_name(Quotas(), service_code="ebs", fragments=("general purpose", "gp3"))[
            "Value"
        ]
        == 2
    )
    assert v._find_quota_by_name(Quotas(), service_code="ebs", fragments=("missing",)) is None


def test_ebs_gp3_headroom_success_failure_and_usage_warning(monkeypatch):
    base = CheckResult(
        id="quota.ebs.gp3_storage",
        status=CheckStatus.PASS,
        details={"current_value": 1, "quota_code": "q"},
    )
    monkeypatch.setattr(v, "_check_named_service_quota", lambda *a, **k: base)

    class Volumes:
        def get_paginator(self, _operation):
            return _Paginator([{"Volumes": [{"Size": 900}, {"Size": 100}]}])

    ctx = SimpleNamespace(client=lambda service: Volumes())
    result = v._check_ebs_gp3_headroom(
        ctx, required_new_gib=30, additional_slurm_accounting_gp3_gib=20
    )
    assert result.status == CheckStatus.FAIL
    assert result.details["projected_used_gib"] == 1030

    warning = CheckResult(
        id="quota.ebs.gp3_storage",
        status=CheckStatus.PASS,
        details={"current_value": 2},
    )
    monkeypatch.setattr(v, "_check_named_service_quota", lambda *a, **k: warning)
    broken = SimpleNamespace(
        client=lambda service: (_ for _ in ()).throw(RuntimeError("DescribeVolumes denied"))
    )
    assert (
        v._check_ebs_gp3_headroom(
            broken, required_new_gib=1, additional_slurm_accounting_gp3_gib=0
        ).status
        == CheckStatus.WARN
    )


def test_validation_path_and_required_value_errors(tmp_path, monkeypatch):
    monkeypatch.setattr(v, "_effective_config_value", lambda cfg, key, fallback="": "")
    with pytest.raises(ValueError, match="Missing required"):
        v._required_int_config_value(object(), "max_count")
    file_path = tmp_path / "config.yaml"
    file_path.write_text("x", encoding="utf-8")
    assert v._resolve_data_path(str(file_path)) == file_path
    monkeypatch.setattr(v, "resource_path", lambda path: file_path)
    assert v._resolve_data_path("relative.yaml") == file_path
    monkeypatch.setattr(
        v, "resource_path", lambda path: (_ for _ in ()).throw(FileNotFoundError(path))
    )
    with pytest.raises(FileNotFoundError, match="File not found"):
        v._resolve_data_path("missing.yaml")
