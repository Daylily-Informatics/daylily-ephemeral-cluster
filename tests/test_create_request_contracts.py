from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml

from daylily_ec.aws.context import AWSContext
from daylily_ec.config.models import REQUIRED_CONFIG_KEYS
from daylily_ec.state.models import SlurmAccountingReceipt, SlurmAccountingStage
from daylily_ec.workflow.create_request import (
    CREATE_PREPARATION_SCHEMA,
    CREATE_PRICING_RECEIPT_SCHEMA,
    CREATE_REQUEST_OVERRIDE_KEYS,
    CREATE_REQUEST_OVERRIDES_SCHEMA,
    CREATE_REQUEST_SCHEMA,
    SPOT_PRICE_POLICY,
    CreateRequestError,
    load_strict_create_request_payload,
    load_verified_preparation_receipt,
    prepare_create_request,
    price_create_input_and_write_receipt,
    render_create_request,
    require_dynamic_spot_policy,
    require_protected_file,
    sha256_path,
    validate_create_success_payload,
    write_create_terminal_receipt,
)

TEMPLATE_RESOURCE = (
    "config/day_cluster/intel/us-west-2/us-west-2d/prod_cluster_intel_spot_us-west-2d.yaml"
)
ACCOUNT_ID = "123456789012"


def _source_values() -> dict[str, str]:
    return {
        "allowed_budget_users": "ubuntu",
        "budget_amount": "500",
        "budget_email": "owner@example.org",
        "cluster_name": "unused-source-name",
        "cluster_template_yaml": TEMPLATE_RESOURCE,
        "cost_center_allowed_users": "ubuntu",
        "cost_center_monthly_cap_usd": "500",
        "cost_center_name": "analysis-full",
        "delete_local_root": "true",
        "dragen_license_policy_arn": "",
        "dragen_license_secret_arn": "",
        "dyec_deploy_key_policy_arn": (f"arn:aws:iam::{ACCOUNT_ID}:policy/DayECHeadnodeDYECClone"),
        "dyec_deploy_key_secret_arn": (
            f"arn:aws:secretsmanager:us-west-2:{ACCOUNT_ID}:secret:dayec/dyec-key"
        ),
        "dayoa_deploy_key_policy_arn": (
            f"arn:aws:iam::{ACCOUNT_ID}:policy/DayECHeadnodeDayOAClone"
        ),
        "dayoa_deploy_key_secret_arn": (
            f"arn:aws:secretsmanager:us-west-2:{ACCOUNT_ID}:secret:dayec/dayoa-key"
        ),
        "enable_detailed_monitoring": "true",
        "enforce_budget": "true",
        "fsx_deployment_type": "SCRATCH_2",
        "fsx_encryption_mode": "AWS_MANAGED_FSX",
        "fsx_fs_size": "2400",
        "fsx_lifecycle": "CLUSTER_BOUND",
        "fsx_lustre_version": "2.15",
        "fsx_metadata_mode": "AUTOMATIC",
        "fsx_owner": "DYEC",
        "fsx_throughput_mbps_per_tib": "250",
        "global_allowed_budget_users": "ubuntu",
        "global_budget_amount": "5000",
        "headnode_instance_type": "r7i.2xlarge",
        "heartbeat_email": "owner@example.org",
        "heartbeat_schedule": "rate(60 minutes)",
        "heartbeat_scheduler_role_arn": "",
        "iam_policy_arn": f"arn:aws:iam::{ACCOUNT_ID}:policy/PClusterTagsAndBudget",
        "max_count_128I": "1",
        "max_count_192I": "1",
        "max_count_384I": "1",
        "max_count_8I": "1",
        "max_count_96I_NVME": "1",
        "private_subnet_id": "subnet-00000000000000001",
        "pcluster_backport_manifest": "",
        "public_subnet_id": "subnet-00000000000000002",
        "reference_s3_uri": "s3://example-reference/reference",
        "control_data_s3_uri": "s3://example-control/control",
        "stage_s3_uri": "s3://example-stage/stage",
        "export_destination_s3_uri": "s3://example-export/derived",
        "spot_instance_allocation_strategy": "price-capacity-optimized",
        "sweep_protection_tag": "dyec-preserve=false",
    }


def _write_source_config(path: Path, *, prompt_key: str | None = None) -> None:
    values = _source_values()
    assert set(values) == set(REQUIRED_CONFIG_KEYS)
    config = {
        key: (
            ["PROMPTUSER", "", ""]
            if key in CREATE_REQUEST_OVERRIDE_KEYS or key == prompt_key
            else ["USESETVALUE", "", value]
        )
        for key, value in values.items()
    }
    path.write_text(
        yaml.safe_dump({"ephemeral_cluster": {"config": config}}, sort_keys=False),
        encoding="utf-8",
    )


def _override_values() -> dict[str, str]:
    values = _source_values()
    values["cluster_name"] = "ursa-full-2d"
    return {key: values[key] for key in CREATE_REQUEST_OVERRIDE_KEYS}


def _write_overrides(
    path: Path,
    *,
    values: dict[str, str] | None = None,
) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": CREATE_REQUEST_OVERRIDES_SCHEMA,
                "values": values or _override_values(),
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    path.chmod(0o600)


def _render(tmp_path: Path) -> tuple[Path, dict[str, object]]:
    source = tmp_path / "source.yaml"
    overrides = tmp_path / "overrides.json"
    request = tmp_path / "request.yaml"
    _write_source_config(source)
    _write_overrides(overrides)
    template = Path(TEMPLATE_RESOURCE).resolve()
    payload = render_create_request(
        source_config=source,
        expected_source_config_sha256=sha256_path(source),
        source_template=TEMPLATE_RESOURCE,
        expected_source_template_sha256=sha256_path(template),
        overrides_json=overrides,
        region_az="us-west-2d",
        output_path=request,
    )
    return request, payload


class _SpotEc2:
    def __init__(self, price: float) -> None:
        self.price = price

    def describe_spot_price_history(self, **_kwargs):
        return {
            "SpotPriceHistory": [
                {
                    "SpotPrice": str(self.price),
                    "Timestamp": datetime.now(timezone.utc),
                }
            ]
        }

    def describe_instance_types(self, *, InstanceTypes):
        return {
            "InstanceTypes": [
                {
                    "InstanceType": instance_type,
                    "VCpuInfo": {"DefaultVCpus": 8},
                }
                for instance_type in InstanceTypes
            ]
        }


class _AwsContext:
    profile = "lsmc"
    account_id = ACCOUNT_ID
    region = "us-west-2"
    iam_username = "ursa-provisioner"

    def __init__(self, price: float) -> None:
        self.ec2 = _SpotEc2(price)

    def client(self, service_name: str, **_kwargs):
        assert service_name == "ec2"
        return self.ec2


def test_render_is_exact_private_and_does_not_persist_numeric_spot_prices(
    tmp_path: Path,
) -> None:
    request, result = _render(tmp_path)

    assert result["schema_version"] == CREATE_REQUEST_SCHEMA
    assert result["status"] == "rendered"
    assert result["override_keys"] == sorted(CREATE_REQUEST_OVERRIDE_KEYS)
    assert "owner@example.org" not in json.dumps(result)
    assert "secretsmanager" not in json.dumps(result)
    assert request.stat().st_mode & 0o777 == 0o600
    request_payload = yaml.safe_load(request.read_text(encoding="utf-8"))
    assert request_payload["dyec_create_request"]["schema_version"] == CREATE_REQUEST_SCHEMA
    assert request_payload["ephemeral_cluster"]["config"]["cluster_name"] == [
        "USESETVALUE",
        "",
        "ursa-full-2d",
    ]
    template_text = Path(TEMPLATE_RESOURCE).read_text(encoding="utf-8")
    assert "SpotPrice: CALCULATE_MAX_SPOT_PRICE" in template_text


def test_render_rejects_unknown_override_and_static_prompt(tmp_path: Path) -> None:
    source = tmp_path / "source.yaml"
    overrides = tmp_path / "overrides.json"
    request = tmp_path / "request.yaml"
    _write_source_config(source)
    values = _override_values()
    values["budget_project"] = "retired"
    _write_overrides(overrides, values=values)
    with pytest.raises(CreateRequestError, match="unknown=budget_project"):
        render_create_request(
            source_config=source,
            expected_source_config_sha256=sha256_path(source),
            source_template=TEMPLATE_RESOURCE,
            expected_source_template_sha256=sha256_path(TEMPLATE_RESOURCE),
            overrides_json=overrides,
            region_az="us-west-2d",
            output_path=request,
        )

    _write_source_config(source, prompt_key="public_subnet_id")
    _write_overrides(overrides)
    with pytest.raises(CreateRequestError, match="public_subnet_id.*USESETVALUE"):
        render_create_request(
            source_config=source,
            expected_source_config_sha256=sha256_path(source),
            source_template=TEMPLATE_RESOURCE,
            expected_source_template_sha256=sha256_path(TEMPLATE_RESOURCE),
            overrides_json=overrides,
            region_az="us-west-2d",
            output_path=request,
        )


def test_render_and_prepare_require_protected_request_inputs(
    tmp_path: Path,
    monkeypatch,
) -> None:
    source = tmp_path / "source.yaml"
    overrides = tmp_path / "overrides.json"
    request = tmp_path / "request.yaml"
    _write_source_config(source)
    _write_overrides(overrides)
    template = Path(TEMPLATE_RESOURCE).resolve()

    overrides.chmod(0o644)
    with pytest.raises(CreateRequestError, match="overrides JSON must be protected"):
        render_create_request(
            source_config=source,
            expected_source_config_sha256=sha256_path(source),
            source_template=TEMPLATE_RESOURCE,
            expected_source_template_sha256=sha256_path(template),
            overrides_json=overrides,
            region_az="us-west-2d",
            output_path=request,
        )

    overrides.chmod(0o600)
    render_create_request(
        source_config=source,
        expected_source_config_sha256=sha256_path(source),
        source_template=TEMPLATE_RESOURCE,
        expected_source_template_sha256=sha256_path(template),
        overrides_json=overrides,
        region_az="us-west-2d",
        output_path=request,
    )
    request.chmod(0o644)
    with pytest.raises(
        CreateRequestError, match="existing create-request output must be protected"
    ):
        render_create_request(
            source_config=source,
            expected_source_config_sha256=sha256_path(source),
            source_template=TEMPLATE_RESOURCE,
            expected_source_template_sha256=sha256_path(template),
            overrides_json=overrides,
            region_az="us-west-2d",
            output_path=request,
        )
    with pytest.raises(CreateRequestError, match="request config must be protected"):
        prepare_create_request(
            request_config=request,
            expected_request_sha256=sha256_path(request),
            source_template=TEMPLATE_RESOURCE,
            expected_source_template_sha256=sha256_path(template),
            profile="lsmc",
            region_az="us-west-2d",
            spot_price_policy=SPOT_PRICE_POLICY,
            output_dir=tmp_path / "admission",
        )

    from daylily_ec.aws.context import AWSContext

    request.chmod(0o600)
    monkeypatch.setattr(
        AWSContext,
        "build",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            RuntimeError("provider secret credential text")
        ),
    )
    with pytest.raises(CreateRequestError, match="profile/account identity") as exc_info:
        prepare_create_request(
            request_config=request,
            expected_request_sha256=sha256_path(request),
            source_template=TEMPLATE_RESOURCE,
            expected_source_template_sha256=sha256_path(template),
            profile="lsmc",
            region_az="us-west-2d",
            spot_price_policy=SPOT_PRICE_POLICY,
            output_dir=tmp_path / "admission",
        )
    assert "credential" not in str(exc_info.value)


def test_render_rejects_retired_source_fields_without_compatibility(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.yaml"
    overrides = tmp_path / "overrides.json"
    request = tmp_path / "request.yaml"
    _write_source_config(source)
    payload = yaml.safe_load(source.read_text(encoding="utf-8"))
    payload["ephemeral_cluster"]["config"]["slurm_accounting_enabled"] = [
        "USESETVALUE",
        "",
        "true",
    ]
    source.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    _write_overrides(overrides)

    with pytest.raises(CreateRequestError, match="extra=slurm_accounting_enabled"):
        render_create_request(
            source_config=source,
            expected_source_config_sha256=sha256_path(source),
            source_template=TEMPLATE_RESOURCE,
            expected_source_template_sha256=sha256_path(TEMPLATE_RESOURCE),
            overrides_json=overrides,
            region_az="us-west-2d",
            output_path=request,
        )


def test_protected_inputs_reject_symlinks_and_nonregular_files(tmp_path: Path) -> None:
    protected = tmp_path / "protected.json"
    protected.write_text("{}\n", encoding="utf-8")
    protected.chmod(0o600)
    symlink = tmp_path / "protected-link.json"
    symlink.symlink_to(protected)

    with pytest.raises(CreateRequestError, match="must not be a symbolic link"):
        require_protected_file(symlink, label="protected test input")

    fifo = tmp_path / "protected.fifo"
    os.mkfifo(fifo, mode=0o600)
    with pytest.raises(CreateRequestError, match="regular file"):
        require_protected_file(fifo, label="protected test input")


def test_render_rejects_duplicate_or_nonfinite_override_json(tmp_path: Path) -> None:
    source = tmp_path / "source.yaml"
    overrides = tmp_path / "overrides.json"
    request = tmp_path / "request.yaml"
    _write_source_config(source)
    values_json = json.dumps(_override_values(), sort_keys=True)
    duplicate_values_json = values_json.replace(
        '"cluster_name": "ursa-full-2d"',
        '"cluster_name": "first", "cluster_name": "second"',
    )
    overrides.write_text(
        '{"schema_version":"dyec.create_request_overrides.v1","values":'
        + duplicate_values_json
        + "}\n",
        encoding="utf-8",
    )
    overrides.chmod(0o600)

    with pytest.raises(CreateRequestError, match="duplicate key"):
        render_create_request(
            source_config=source,
            expected_source_config_sha256=sha256_path(source),
            source_template=TEMPLATE_RESOURCE,
            expected_source_template_sha256=sha256_path(TEMPLATE_RESOURCE),
            overrides_json=overrides,
            region_az="us-west-2d",
            output_path=request,
        )

    overrides.write_text(
        '{"schema_version":"dyec.create_request_overrides.v1","values":NaN}\n',
        encoding="utf-8",
    )
    overrides.chmod(0o600)
    with pytest.raises(CreateRequestError, match="non-finite"):
        render_create_request(
            source_config=source,
            expected_source_config_sha256=sha256_path(source),
            source_template=TEMPLATE_RESOURCE,
            expected_source_template_sha256=sha256_path(TEMPLATE_RESOURCE),
            overrides_json=overrides,
            region_az="us-west-2d",
            output_path=request,
        )


def test_strict_request_loader_rejects_duplicate_yaml_keys(tmp_path: Path) -> None:
    request, _payload = _render(tmp_path)
    request.write_text(
        request.read_text(encoding="utf-8") + "ephemeral_cluster: {}\n",
        encoding="utf-8",
    )
    request.chmod(0o600)

    with pytest.raises(CreateRequestError, match="Invalid YAML document"):
        load_strict_create_request_payload(request)


def test_relative_input_never_falls_back_to_a_cwd_file(
    tmp_path: Path,
    monkeypatch,
) -> None:
    source = tmp_path / "not-a-packaged-source.yaml"
    overrides = tmp_path / "overrides.json"
    request = tmp_path / "request.yaml"
    _write_source_config(source)
    _write_overrides(overrides)
    template_sha256 = sha256_path(TEMPLATE_RESOURCE)
    monkeypatch.chdir(tmp_path)

    with pytest.raises(CreateRequestError, match="source config does not exist"):
        render_create_request(
            source_config=source.name,
            expected_source_config_sha256=sha256_path(source),
            source_template=TEMPLATE_RESOURCE,
            expected_source_template_sha256=template_sha256,
            overrides_json=overrides,
            region_az="us-west-2d",
            output_path=request,
        )


@pytest.mark.parametrize(
    "queues",
    [
        [
            {
                "Name": "spot",
                "CapacityType": "SPOT",
                "ComputeResources": [{"Name": "missing-policy"}],
            }
        ],
        [
            {
                "Name": "ondemand",
                "CapacityType": "ONDEMAND",
                "ComputeResources": [{"Name": "invalid-policy", "SpotPrice": SPOT_PRICE_POLICY}],
            }
        ],
    ],
)
def test_dynamic_template_policy_rejects_missing_spot_or_ondemand_price(
    tmp_path: Path,
    queues: list[dict[str, object]],
) -> None:
    template = tmp_path / "template.yaml"
    template.write_text(
        yaml.safe_dump({"Scheduling": {"SlurmQueues": queues}}, sort_keys=False),
        encoding="utf-8",
    )

    with pytest.raises(CreateRequestError):
        require_dynamic_spot_policy(template)


def test_dynamic_template_policy_requires_exact_spot_and_no_ondemand_price(
    tmp_path: Path,
) -> None:
    template = tmp_path / "template.yaml"
    template.write_text(
        yaml.safe_dump(
            {
                "Scheduling": {
                    "SlurmQueues": [
                        {
                            "Name": "spot",
                            "CapacityType": "SPOT",
                            "ComputeResources": [
                                {"Name": "priced", "SpotPrice": SPOT_PRICE_POLICY}
                            ],
                        },
                        {
                            "Name": "ondemand",
                            "CapacityType": "ONDEMAND",
                            "ComputeResources": [{"Name": "fixed"}],
                        },
                    ]
                }
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    require_dynamic_spot_policy(template)


def test_prepare_and_final_reprice_are_independent_and_content_bound(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request, _render_result = _render(tmp_path)
    admission_dir = tmp_path / "admission"
    monkeypatch.setattr(
        AWSContext,
        "build",
        classmethod(lambda _cls, *_args, **_kwargs: _AwsContext(1.0)),
    )

    admission = prepare_create_request(
        request_config=request,
        expected_request_sha256=sha256_path(request),
        source_template=TEMPLATE_RESOURCE,
        expected_source_template_sha256=sha256_path(TEMPLATE_RESOURCE),
        profile="lsmc",
        region_az="us-west-2d",
        spot_price_policy=SPOT_PRICE_POLICY,
        output_dir=admission_dir,
    )

    assert admission["schema_version"] == CREATE_PREPARATION_SCHEMA
    assert admission["status"] == "complete"
    assert admission["phase"] == "admission"
    assert admission["pricing_source"]["maximum_age_seconds"] == 3600
    assert (
        admission["unpriced_cluster_config_sha256"]
        != admission["admission_priced_cluster_config_sha256"]
    )
    load_verified_preparation_receipt(
        receipt_path=admission["receipt_path"],
        expected_receipt_sha256=admission["receipt_sha256"],
        request_config_path=request,
        source_template_path=TEMPLATE_RESOURCE,
        profile="lsmc",
        account_id=ACCOUNT_ID,
        region_az="us-west-2d",
        global_spot_max_cost=9.99,
        spot_cost_limit_pct=1.70,
        write_spot_pricing_warn_threshold=8.0,
    )

    effective_path = admission_dir / admission["artifacts"]["effective_cluster"]["name"]
    final_dir = tmp_path / "final"
    final_dir.mkdir()
    final_summary, final_receipt = price_create_input_and_write_receipt(
        effective_path=effective_path,
        priced_path=final_dir / "cluster.yaml",
        summary_path=final_dir / "spot.json",
        receipt_path=final_dir / "receipt.json",
        request_config_path=request,
        source_template_path=TEMPLATE_RESOURCE,
        profile="lsmc",
        account_id=ACCOUNT_ID,
        region="us-west-2",
        region_az="us-west-2d",
        cluster_name="ursa-full-2d",
        repository_credential_reference_keys=admission["repository_credential_reference_keys"],
        repository_credential_references_sha256=admission[
            "repository_credential_references_sha256"
        ],
        ec2_client=_SpotEc2(2.0),
        global_spot_max_cost=9.99,
        spot_cost_limit_pct=1.70,
        write_spot_pricing_warn_threshold=8.0,
        admission_receipt_path=admission["receipt_path"],
        admission_receipt_sha256=admission["receipt_sha256"],
    )

    assert final_receipt["schema_version"] == CREATE_PRICING_RECEIPT_SCHEMA
    assert final_receipt["admission_receipt_sha256"] == admission["receipt_sha256"]
    assert final_receipt["final_cluster_config_sha256"] == sha256_path(final_dir / "cluster.yaml")
    admission_bid = admission["pricing_result"]["resources"][0]["final_bid"]
    final_bid = final_summary["resources"][0]["final_bid"]
    assert final_bid != admission_bid
    assert final_bid == 3.4
    assert os.stat(final_receipt["receipt_path"]).st_mode & 0o777 == 0o600


def test_preparation_receipt_rejects_portable_artifact_hash_mismatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request, _render_result = _render(tmp_path)
    monkeypatch.setattr(
        AWSContext,
        "build",
        classmethod(lambda _cls, *_args, **_kwargs: _AwsContext(1.0)),
    )
    admission = prepare_create_request(
        request_config=request,
        expected_request_sha256=sha256_path(request),
        source_template=TEMPLATE_RESOURCE,
        expected_source_template_sha256=sha256_path(TEMPLATE_RESOURCE),
        profile="lsmc",
        region_az="us-west-2d",
        spot_price_policy=SPOT_PRICE_POLICY,
        output_dir=tmp_path / "admission",
    )
    artifact = tmp_path / "admission" / admission["artifacts"]["effective_cluster"]["name"]
    original = artifact.read_bytes()
    artifact.write_bytes(bytes([original[0] ^ 1]) + original[1:])

    with pytest.raises(CreateRequestError, match="digest does not match"):
        load_verified_preparation_receipt(
            receipt_path=admission["receipt_path"],
            expected_receipt_sha256=admission["receipt_sha256"],
            request_config_path=request,
            source_template_path=TEMPLATE_RESOURCE,
            profile="lsmc",
            account_id=ACCOUNT_ID,
            region_az="us-west-2d",
            global_spot_max_cost=9.99,
            spot_cost_limit_pct=1.70,
            write_spot_pricing_warn_threshold=8.0,
        )


def test_preparation_receipt_rejects_duplicate_json_keys(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request, _render_result = _render(tmp_path)
    monkeypatch.setattr(
        AWSContext,
        "build",
        classmethod(lambda _cls, *_args, **_kwargs: _AwsContext(1.0)),
    )
    admission = prepare_create_request(
        request_config=request,
        expected_request_sha256=sha256_path(request),
        source_template=TEMPLATE_RESOURCE,
        expected_source_template_sha256=sha256_path(TEMPLATE_RESOURCE),
        profile="lsmc",
        region_az="us-west-2d",
        spot_price_policy=SPOT_PRICE_POLICY,
        output_dir=tmp_path / "admission",
    )
    receipt = Path(admission["receipt_path"])
    receipt.write_text(
        receipt.read_text(encoding="utf-8").replace(
            '"status": "complete"',
            '"status": "complete", "status": "failed"',
            1,
        ),
        encoding="utf-8",
    )
    receipt.chmod(0o600)

    with pytest.raises(CreateRequestError, match="duplicate key"):
        load_verified_preparation_receipt(
            receipt_path=receipt,
            expected_receipt_sha256=sha256_path(receipt),
            request_config_path=request,
            source_template_path=TEMPLATE_RESOURCE,
            profile="lsmc",
            account_id=ACCOUNT_ID,
            region_az="us-west-2d",
            global_spot_max_cost=9.99,
            spot_cost_limit_pct=1.70,
            write_spot_pricing_warn_threshold=8.0,
        )


def test_terminal_create_receipt_and_public_success_require_working_sacct(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request, _render_result = _render(tmp_path)
    monkeypatch.setattr(
        AWSContext,
        "build",
        classmethod(lambda _cls, *_args, **_kwargs: _AwsContext(1.0)),
    )
    admission = prepare_create_request(
        request_config=request,
        expected_request_sha256=sha256_path(request),
        source_template=TEMPLATE_RESOURCE,
        expected_source_template_sha256=sha256_path(TEMPLATE_RESOURCE),
        profile="lsmc",
        region_az="us-west-2d",
        spot_price_policy=SPOT_PRICE_POLICY,
        output_dir=tmp_path / "admission",
    )
    effective = tmp_path / "admission" / admission["artifacts"]["effective_cluster"]["name"]
    final_dir = tmp_path / "final"
    final_dir.mkdir()
    _summary, pricing = price_create_input_and_write_receipt(
        effective_path=effective,
        priced_path=final_dir / "priced.yaml",
        summary_path=final_dir / "summary.json",
        receipt_path=final_dir / "pricing.json",
        request_config_path=request,
        source_template_path=TEMPLATE_RESOURCE,
        profile="lsmc",
        account_id="123456789012",
        region="us-west-2",
        region_az="us-west-2d",
        cluster_name="ursa-m-rgx-test",
        repository_credential_reference_keys=list(
            admission["repository_credential_reference_keys"]
        ),
        repository_credential_references_sha256=admission[
            "repository_credential_references_sha256"
        ],
        ec2_client=_SpotEc2(1.2),
        global_spot_max_cost=9.99,
        spot_cost_limit_pct=1.7,
        write_spot_pricing_warn_threshold=8.0,
        admission_receipt_path=admission["receipt_path"],
        admission_receipt_sha256=admission["receipt_sha256"],
    )
    accounting_path = final_dir / "accounting.json"
    accounting = SlurmAccountingReceipt(
        requested_mode="on",
        stage_reached=SlurmAccountingStage.COMPLETE,
        update_config_path="/protected/update.yaml",
        terminal_cluster_state="UPDATE_COMPLETE",
        terminal_fleet_state="RUNNING",
        fleet_restored=True,
        recovery_required=False,
        stack_name="dayec-slurm-accounting-us-west-2c",
    )
    accounting_path.write_text(
        accounting.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )
    accounting_path.chmod(0o600)
    terminal = write_create_terminal_receipt(
        receipt_path=final_dir / "terminal.json",
        cluster_name="ursa-m-rgx-test",
        profile="lsmc",
        account_id="123456789012",
        region="us-west-2",
        region_az="us-west-2d",
        request_config_sha256=sha256_path(request),
        final_cluster_config_sha256=pricing["final_cluster_config_sha256"],
        pricing_receipt_path=pricing["receipt_path"],
        accounting_receipt_path=accounting_path,
        provider_cluster_state="UPDATE_COMPLETE",
        fleet_state="RUNNING",
        accounting_state="ENABLED",
        sacct_verified=True,
    )
    public = {
        "schema_version": "dyec.create.v1",
        "dyec_version": terminal["dyec_version"],
        "status": "complete",
        "terminal": True,
        "phase": "terminal",
        "captured_at": terminal["captured_at"],
        "cluster_name": "ursa-m-rgx-test",
        "profile": "lsmc",
        "account_id": "123456789012",
        "region": "us-west-2",
        "region_az": "us-west-2d",
        "provider_cluster_state": "UPDATE_COMPLETE",
        "fleet_state": "RUNNING",
        "accounting_state": "ENABLED",
        "sacct_verified": True,
        "request_config_sha256": sha256_path(request),
        "final_cluster_config_sha256": pricing["final_cluster_config_sha256"],
        "pricing_receipt_sha256": pricing["receipt_sha256"],
        "accounting_receipt_sha256": sha256_path(accounting_path),
        "terminal_receipt_path": terminal["terminal_receipt_path"],
        "terminal_receipt_sha256": terminal["terminal_receipt_sha256"],
    }

    validate_create_success_payload(public)
    with pytest.raises(CreateRequestError, match="sacct_verified"):
        validate_create_success_payload({**public, "sacct_verified": False})

    incomplete = accounting.model_copy(
        update={"stage_reached": SlurmAccountingStage.UPDATE_COMPLETE}
    )
    accounting_path.write_text(
        incomplete.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )
    accounting_path.chmod(0o600)
    with pytest.raises(CreateRequestError, match="working sacct"):
        write_create_terminal_receipt(
            receipt_path=final_dir / "blocked-terminal.json",
            cluster_name="ursa-m-rgx-test",
            profile="lsmc",
            account_id="123456789012",
            region="us-west-2",
            region_az="us-west-2d",
            request_config_sha256=sha256_path(request),
            final_cluster_config_sha256=pricing["final_cluster_config_sha256"],
            pricing_receipt_path=pricing["receipt_path"],
            accounting_receipt_path=accounting_path,
            provider_cluster_state="UPDATE_COMPLETE",
            fleet_state="RUNNING",
            accounting_state="ENABLED",
            sacct_verified=True,
        )
