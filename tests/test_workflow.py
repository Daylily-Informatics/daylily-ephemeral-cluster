"""Tests for CP-017: Wire Workflow + Swap Entrypoint.

Tests cover:
1. _extract_selected helper
2. _noop_heartbeat_result helper
3. run_preflight_only function
4. run_create_workflow function (early exits)
5. Module exports
6. Exit code constants
7. configure_headnode function
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
import yaml

import daylily_ec.aws.cloudformation as cloudformation
import daylily_ec.aws.context as aws_context
import daylily_ec.aws.ec2 as aws_ec2
import daylily_ec.aws.heartbeat as aws_heartbeat
import daylily_ec.aws.iam as aws_iam
import daylily_ec.aws.slurm_accounting as aws_slurm_accounting
from daylily_ec.aws.ssm import SsmCommandFailedError, SsmCommandResult
import daylily_ec.aws.spot_pricing as spot_pricing
import daylily_ec.config.triplets as triplets
import daylily_ec.pcluster.monitor as pcluster_monitor
import daylily_ec.pcluster.runner as pcluster_runner
import daylily_ec.render.renderer as renderer
from daylily_ec.aws.slurm_accounting import SlurmAccountingDb
from daylily_ec.config.models import ConfigFile, Triplet
from daylily_ec.state import store as state_store
from daylily_ec.state.models import CheckResult, CheckStatus, PreflightReport
import daylily_ec.workflow.create_cluster as create_cluster_module
from daylily_ec.workflow.create_cluster import (
    DEFAULT_REGIONAL_CLUSTER_CAP,
    EXIT_AWS_FAILURE,
    EXIT_DRIFT,
    EXIT_SUCCESS,
    EXIT_TOOLCHAIN,
    EXIT_VALIDATION_FAILURE,
    az_cluster_template_relative_path,
    attach_headnode_managed_policy,
    _build_connection_command,
    _is_valid_fsx_size,
    _is_valid_headnode_instance_type,
    _extract_selected,
    _resolve_fsx_size,
    _resolve_headnode_instance_type,
    _resolve_s3_role_config_value,
    _noop_heartbeat_result,
    _require_values,
    _resolve_cluster_name,
    _resolve_config_value,
    _resolve_post_create_inputs,
    resolve_cluster_template_yaml,
    resolve_dayoa_deploy_key_inputs,
    resolve_dyec_deploy_key_inputs,
    resolve_dragen_create_inputs,
    configure_headnode,
    evaluate_regional_cluster_cap,
    make_repository_catalog_preflight_step,
    normalize_create_cluster_type,
    parse_create_repo_overrides,
    run_preflight,
    validate_create_cluster_type_region,
    validate_regional_cluster_cap_options,
    validate_sentieon_single_cluster_contract,
    validate_startup_dra_contract,
    validate_dragen_cluster_contract,
    _validate_cluster_name,
)

# ── Exit code constants ─────────────────────────────────────────────────


class TestExitCodes:
    def test_exit_success(self):
        assert EXIT_SUCCESS == 0

    def test_exit_validation_failure(self):
        assert EXIT_VALIDATION_FAILURE == 1

    def test_exit_aws_failure(self):
        assert EXIT_AWS_FAILURE == 2

    def test_exit_drift(self):
        assert EXIT_DRIFT == 3

    def test_exit_toolchain(self):
        assert EXIT_TOOLCHAIN == 4


class TestClusterBootConfigPublish:
    def test_publishes_expected_boot_files(self, tmp_path):
        source_dir = tmp_path / "boot"
        source_dir.mkdir()
        for name in create_cluster_module.CLUSTER_BOOT_CONFIG_FILENAMES:
            (source_dir / name).write_text(f"content for {name}\n", encoding="utf-8")

        calls = []

        class FakeS3:
            def put_object(self, **kwargs):
                calls.append(kwargs)

        release_uri = create_cluster_module.cluster_boot_config_release_uri(
            base_uri="s3://references/runtime_assets/cluster_boot_config",
            source_dir=source_dir,
        )
        uploaded = create_cluster_module.publish_cluster_boot_config(
            FakeS3(),
            cluster_boot_s3_uri=release_uri,
            source_dir=source_dir,
        )

        assert uploaded == [
            f"{release_uri}/{name}"
            for name in create_cluster_module.CLUSTER_BOOT_CONFIG_FILENAMES
        ]
        assert [call["Bucket"] for call in calls] == ["references"] * len(calls)
        assert [call["Key"] for call in calls] == [
            f"{release_uri.removeprefix('s3://references/')}/{name}"
            for name in create_cluster_module.CLUSTER_BOOT_CONFIG_FILENAMES
        ]
        assert all(call["IfNoneMatch"] == "*" for call in calls)
        assert all(len(call["Metadata"]["daylily-sha256"]) == 64 for call in calls)

    def test_rejects_mutable_shared_destination(self, tmp_path):
        source_dir = tmp_path / "boot"
        source_dir.mkdir()
        for name in create_cluster_module.CLUSTER_BOOT_CONFIG_FILENAMES:
            (source_dir / name).write_text(f"content for {name}\n", encoding="utf-8")

        with pytest.raises(ValueError, match="immutable release prefix"):
            create_cluster_module.publish_cluster_boot_config(
                SimpleNamespace(),
                cluster_boot_s3_uri="s3://references/runtime_assets/cluster_boot_config",
                source_dir=source_dir,
            )

    def test_release_uri_changes_with_bundle_content(self, tmp_path):
        source_dir = tmp_path / "boot"
        source_dir.mkdir()
        for name in create_cluster_module.CLUSTER_BOOT_CONFIG_FILENAMES:
            (source_dir / name).write_text(f"content for {name}\n", encoding="utf-8")
        first = create_cluster_module.cluster_boot_config_release_uri(
            base_uri="s3://references/runtime_assets/cluster_boot_config",
            source_dir=source_dir,
        )
        (source_dir / "sbatch").write_text("changed\n", encoding="utf-8")
        second = create_cluster_module.cluster_boot_config_release_uri(
            base_uri="s3://references/runtime_assets/cluster_boot_config",
            source_dir=source_dir,
        )

        assert first != second
        assert "/releases/sha256-" in first
        assert "/releases/sha256-" in second


def test_attach_headnode_managed_policy_is_headnode_only_and_idempotent(tmp_path):
    policy_arn = "arn:aws:iam::123456789012:policy/DayECHeadnodeDayOAClone"
    path = tmp_path / "cluster.yaml"
    path.write_text(
        """
HeadNode:
  Iam:
    AdditionalIamPolicies:
      - Policy: arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore
Scheduling:
  SlurmQueues:
    - Name: i128
      Iam:
        AdditionalIamPolicies:
          - Policy: arn:aws:iam::123456789012:policy/runtime
""",
        encoding="utf-8",
    )

    attach_headnode_managed_policy(path, policy_arn)
    attach_headnode_managed_policy(path, policy_arn)

    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    head_policies = [item["Policy"] for item in payload["HeadNode"]["Iam"]["AdditionalIamPolicies"]]
    queue_policies = [
        item["Policy"]
        for item in payload["Scheduling"]["SlurmQueues"][0]["Iam"]["AdditionalIamPolicies"]
    ]
    assert head_policies.count(policy_arn) == 1
    assert policy_arn not in queue_policies


def test_attach_headnode_managed_policy_rejects_compute_attachment(tmp_path):
    policy_arn = "arn:aws:iam::123456789012:policy/DayECHeadnodeDayOAClone"
    path = tmp_path / "cluster.yaml"
    path.write_text(
        f"""
HeadNode:
  Iam:
    AdditionalIamPolicies: []
Scheduling:
  SlurmQueues:
    - Name: i128
      Iam:
        AdditionalIamPolicies:
          - Policy: {policy_arn}
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="must not be attached to compute queue"):
        attach_headnode_managed_policy(path, policy_arn)


def test_resolve_dayoa_deploy_key_inputs_requires_matching_account_and_region():
    cfg = ConfigFile.model_validate(
        {
            "ephemeral_cluster": {
                "config": {
                    "dayoa_deploy_key_secret_arn": [
                        "USESETVALUE",
                        "",
                        "arn:aws:secretsmanager:us-west-2:123456789012:secret:dayoa",
                    ],
                    "dayoa_deploy_key_policy_arn": [
                        "USESETVALUE",
                        "",
                        "arn:aws:iam::123456789012:policy/DayECHeadnodeDayOAClone",
                    ],
                }
            }
        }
    )

    inputs = resolve_dayoa_deploy_key_inputs(
        cfg,
        region_az="us-west-2d",
        account_id="123456789012",
        non_interactive=True,
    )

    assert inputs.region == "us-west-2"
    assert inputs.secret_arn.endswith(":secret:dayoa")
    assert inputs.policy_arn.endswith(":policy/DayECHeadnodeDayOAClone")


def test_resolve_dyec_deploy_key_inputs_requires_matching_account_and_region():
    cfg = ConfigFile.model_validate(
        {
            "ephemeral_cluster": {
                "config": {
                    "dyec_deploy_key_secret_arn": [
                        "USESETVALUE",
                        "",
                        "arn:aws:secretsmanager:us-west-2:123456789012:secret:dyec",
                    ],
                    "dyec_deploy_key_policy_arn": [
                        "USESETVALUE",
                        "",
                        "arn:aws:iam::123456789012:policy/DayECHeadnodeDYECClone",
                    ],
                }
            }
        }
    )

    inputs = resolve_dyec_deploy_key_inputs(
        cfg,
        region_az="us-west-2d",
        account_id="123456789012",
        non_interactive=True,
    )

    assert inputs.region == "us-west-2"
    assert inputs.secret_arn.endswith(":secret:dyec")
    assert inputs.policy_arn.endswith(":policy/DayECHeadnodeDYECClone")


class TestClusterBootConfigPublishContinued:
    def test_rejects_legacy_fsx_data_boot_file(self, tmp_path):
        source_dir = tmp_path / "boot"
        source_dir.mkdir()
        for name in create_cluster_module.CLUSTER_BOOT_CONFIG_FILENAMES:
            body = "echo ok\n"
            if name == "sbatch":
                body = "ls /fsx/data\n"
            (source_dir / name).write_text(body, encoding="utf-8")

        class FakeS3:
            def put_object(self, **_kwargs):
                raise AssertionError("legacy boot file must not be uploaded")

        with pytest.raises(ValueError, match="/fsx/data"):
            release_uri = create_cluster_module.cluster_boot_config_release_uri(
                base_uri="s3://references/runtime_assets/cluster_boot_config",
                source_dir=source_dir,
            )
            create_cluster_module.publish_cluster_boot_config(
                FakeS3(),
                cluster_boot_s3_uri=release_uri,
                source_dir=source_dir,
            )

    def test_allows_reference_compat_symlink_boot_contract(self, tmp_path):
        source_dir = tmp_path / "boot"
        source_dir.mkdir()
        for name in create_cluster_module.CLUSTER_BOOT_CONFIG_FILENAMES:
            body = "echo ok\n"
            if name == "post_install_ubuntu_combined.sh":
                body = 'reference_compat_root="/fsx/data"\nln -sfn "${references_root}" "${reference_compat_root}"\n'
            (source_dir / name).write_text(body, encoding="utf-8")

        class FakeS3:
            def __init__(self):
                self.calls = []

            def put_object(self, **kwargs):
                self.calls.append(kwargs)

        fake_s3 = FakeS3()
        release_uri = create_cluster_module.cluster_boot_config_release_uri(
            base_uri="s3://references/runtime_assets/cluster_boot_config",
            source_dir=source_dir,
        )
        uploaded = create_cluster_module.publish_cluster_boot_config(
            fake_s3,
            cluster_boot_s3_uri=release_uri,
            source_dir=source_dir,
        )

        assert len(uploaded) == len(create_cluster_module.CLUSTER_BOOT_CONFIG_FILENAMES)
        assert len(fake_s3.calls) == len(create_cluster_module.CLUSTER_BOOT_CONFIG_FILENAMES)

    def test_rejects_extra_fsx_data_use_even_with_reference_compat_contract(self, tmp_path):
        source_dir = tmp_path / "boot"
        source_dir.mkdir()
        for name in create_cluster_module.CLUSTER_BOOT_CONFIG_FILENAMES:
            body = "echo ok\n"
            if name == "post_install_ubuntu_combined.sh":
                body = 'reference_compat_root="/fsx/data"\nls /fsx/data\n'
            (source_dir / name).write_text(body, encoding="utf-8")

        class FakeS3:
            def put_object(self, **_kwargs):
                raise AssertionError("legacy boot file must not be uploaded")

        with pytest.raises(ValueError, match="/fsx/data"):
            release_uri = create_cluster_module.cluster_boot_config_release_uri(
                base_uri="s3://references/runtime_assets/cluster_boot_config",
                source_dir=source_dir,
            )
            create_cluster_module.publish_cluster_boot_config(
                FakeS3(),
                cluster_boot_s3_uri=release_uri,
                source_dir=source_dir,
            )


class TestAzClusterTemplateResolution:
    def test_parses_repository_overrides_fail_closed(self) -> None:
        assert parse_create_repo_overrides(["daylily-omics-analysis:sentieon-single"]) == {
            "daylily-omics-analysis": "sentieon-single"
        }
        assert parse_create_repo_overrides(None) == {}

        with pytest.raises(ValueError, match="<repo-key>:<git-ref>"):
            parse_create_repo_overrides(["daylily-omics-analysis"])
        with pytest.raises(ValueError, match="more than once"):
            parse_create_repo_overrides(
                [
                    "daylily-omics-analysis:first",
                    "daylily-omics-analysis:second",
                ]
            )

    def test_normalizes_known_cluster_types(self) -> None:
        assert normalize_create_cluster_type("intel") == "intel"
        assert normalize_create_cluster_type("RHEL") == "rhel"
        assert normalize_create_cluster_type("DRAGEN") == "dragen"
        assert normalize_create_cluster_type("SENTIEON-SINGLE") == "sentieon-single"

    def test_rejects_unknown_cluster_type(self) -> None:
        with pytest.raises(ValueError, match="--cluster-type"):
            normalize_create_cluster_type("gpu")

    def test_az_cluster_template_relative_path_uses_region_and_region_az(self) -> None:
        assert az_cluster_template_relative_path("intel", "us-west-2d") == Path(
            "config/day_cluster/intel/us-west-2/us-west-2d/prod_cluster_intel_us-west-2d.yaml"
        )
        assert az_cluster_template_relative_path("rhel", "us-west-2c") == Path(
            "config/day_cluster/rhel/us-west-2/us-west-2c/prod_cluster_rhel_us-west-2c.yaml"
        )
        assert az_cluster_template_relative_path("dragen", "us-west-2b") == Path(
            "config/day_cluster/dragen/us-west-2/us-west-2b/prod_cluster_dragen_us-west-2b.yaml"
        )
        assert az_cluster_template_relative_path("sentieon-single", "us-west-2c") == Path(
            "config/day_cluster/sentieon-single/us-west-2/us-west-2c/"
            "prod_cluster_sentieon-single_us-west-2c.yaml"
        )

    def test_sentieon_single_rejects_any_az_except_us_west_2c(self) -> None:
        validate_create_cluster_type_region("sentieon-single", "us-west-2c")

        with pytest.raises(ValueError, match="supported only in us-west-2c"):
            validate_create_cluster_type_region("sentieon-single", "us-west-2d")

    def test_sentieon_single_rejects_explicit_template_override(self, tmp_path: Path) -> None:
        explicit = tmp_path / "custom.yaml"
        explicit.write_text("Region: us-west-2\n", encoding="utf-8")
        cfg = ConfigFile()
        cfg.ephemeral_cluster.config["cluster_template_yaml"] = Triplet(
            action="USESETVALUE",
            default_value="",
            set_value=str(explicit),
        )

        with pytest.raises(ValueError, match="canonical us-west-2c template"):
            resolve_cluster_template_yaml(
                cfg,
                region_az="us-west-2c",
                cluster_type="sentieon-single",
                resource_path_fn=lambda rel: Path(rel),
            )

    def test_sentieon_single_pinned_types_exclude_x_family_for_separate_spot_quota(
        self,
    ) -> None:
        pinned_types = {
            instance_type
            for instance_types in create_cluster_module.SENTIEON_SINGLE_QUEUE_INSTANCE_TYPES.values()
            for instance_type in instance_types
        }

        assert pinned_types
        assert all(not instance_type.lower().startswith("x") for instance_type in pinned_types)

    def test_sentieon_single_template_enforces_fixed_single_node_contract(
        self, tmp_path: Path
    ) -> None:
        template = Path(
            "config/day_cluster/sentieon-single/us-west-2/us-west-2c/"
            "prod_cluster_sentieon-single_us-west-2c.yaml"
        ).read_text(encoding="utf-8")
        substitutions = {key: "value" for key in renderer.ALL_SUBSTITUTION_KEYS}
        substitutions.update(
            {
                "REGSUB_REGION": "us-west-2",
                "REGSUB_PUB_SUBNET": "subnet-public",
                "REGSUB_PRIVATE_SUBNET": "subnet-private",
                "REGSUB_CLUSTER_NAME": "sentieon-test",
                "REGSUB_HEADNODE_INSTANCE_TYPE": "r7i.2xlarge",
                "REGSUB_S3_BUCKET_INIT": "s3://private-assets/boot",
                "REGSUB_S3_IAM_POLICY": ("arn:aws:iam::123456789012:policy/dayec-cluster"),
                "REGSUB_S3_REFERENCE_BUCKET": "references",
                "REGSUB_S3_CONTROL_DATA_BUCKET": "controls",
                "REGSUB_S3_STAGE_BUCKET": "stage",
                "REGSUB_S3_EXPORT_BUCKET": "export",
                "REGSUB_S3_REFERENCE_URI": "s3://references",
                "REGSUB_DETAILED_MONITORING": "false",
                "REGSUB_DELETE_LOCAL_ROOT": "true",
                "REGSUB_SAVE_FSX": "Delete",
                "REGSUB_ENFORCE_BUDGET": '"true"',
                "REGSUB_SPOT_PRICE_WARN_THRESHOLD": '"8.00"',
                "REGSUB_SLURM_ACCOUNTING_HEADNODE_NETWORKING": "",
                "REGSUB_SLURM_ACCOUNTING_DATABASE": "",
            }
        )
        rendered = renderer.render_template(template, substitutions)
        cluster_yaml = tmp_path / "cluster.yaml"
        cluster_yaml.write_text(rendered, encoding="utf-8")

        validate_startup_dra_contract(cluster_yaml)
        validate_sentieon_single_cluster_contract(cluster_yaml)

        payload = yaml.safe_load(rendered)
        queues = payload["Scheduling"]["SlurmQueues"]
        assert [queue["Name"] for queue in queues] == [
            "i8",
            "i96nvme",
            "i128nvme",
            "i192nvme",
            "i384nvme",
        ]
        for queue in queues:
            assert len(queue["ComputeResources"]) == 1
            resource = queue["ComputeResources"][0]
            assert resource["MinCount"] == 0
            assert resource["MaxCount"] == 12
            assert resource["Efa"]["Enabled"] is False
            assert queue["CapacityType"] == "SPOT"
            assert queue["AllocationStrategy"] == "price-capacity-optimized"

        queues[0]["ComputeResources"][0]["MaxCount"] = 13
        cluster_yaml.write_text(yaml.safe_dump(payload), encoding="utf-8")
        with pytest.raises(ValueError, match="MinCount 0 and MaxCount 12"):
            validate_sentieon_single_cluster_contract(cluster_yaml)

    def test_dragen_rejects_explicit_template_override(self, tmp_path: Path) -> None:
        explicit = tmp_path / "custom.yaml"
        explicit.write_text("Region: us-west-2\n", encoding="utf-8")
        cfg = ConfigFile()
        cfg.ephemeral_cluster.config["cluster_template_yaml"] = Triplet(
            action="USESETVALUE",
            default_value="",
            set_value=str(explicit),
        )

        with pytest.raises(ValueError, match="canonical AZ-scoped template"):
            resolve_cluster_template_yaml(
                cfg,
                region_az="us-west-2b",
                cluster_type="dragen",
                resource_path_fn=lambda rel: Path(rel),
            )

    def test_dragen_requires_explicit_private_inputs(self) -> None:
        with pytest.raises(ValueError, match="pcluster_backport_manifest"):
            resolve_dragen_create_inputs(
                ConfigFile(),
                cluster_type="dragen",
                region_az="us-west-2b",
            )

    @patch("daylily_ec.pcluster.backport.load_operational_backport")
    def test_dragen_resolves_qualified_manifest_and_secret_arns(self, load_backport) -> None:
        load_backport.return_value = SimpleNamespace(image_region="us-west-2")
        cfg = ConfigFile()
        for key, value in {
            "pcluster_backport_manifest": "/private/backport.yaml",
            "dragen_license_secret_arn": (
                "arn:aws:secretsmanager:us-west-2:123456789012:secret:dayec/dragen"
            ),
            "dragen_license_policy_arn": (
                "arn:aws:iam::123456789012:policy/dayec-dragen-license-read"
            ),
        }.items():
            cfg.ephemeral_cluster.config[key] = Triplet(
                action="USESETVALUE",
                default_value="",
                set_value=value,
            )

        inputs = resolve_dragen_create_inputs(
            cfg,
            cluster_type="dragen",
            region_az="us-west-2b",
        )

        assert inputs is not None
        assert inputs.backport is load_backport.return_value
        assert inputs.license_secret_arn.endswith(":secret:dayec/dragen")

    def test_dragen_template_enforces_mixed_spot_contract(self, tmp_path: Path) -> None:
        template = Path(
            "config/day_cluster/dragen/us-west-2/us-west-2b/prod_cluster_dragen_us-west-2b.yaml"
        ).read_text(encoding="utf-8")
        secret_arn = "arn:aws:secretsmanager:us-west-2:123456789012:secret:dayec/dragen"
        policy_arn = "arn:aws:iam::123456789012:policy/dayec-dragen-license-read"
        cookbook_uri = "s3://private-assets/backports/cookbook.tgz"
        ami_id = "ami-0123456789abcdef0"
        substitutions = {key: "value" for key in renderer.ALL_SUBSTITUTION_KEYS}
        substitutions.update(
            {
                "REGSUB_REGION": "us-west-2",
                "REGSUB_PUB_SUBNET": "subnet-public",
                "REGSUB_PRIVATE_SUBNET": "subnet-private",
                "REGSUB_CLUSTER_NAME": "dragen-test",
                "REGSUB_HEADNODE_INSTANCE_TYPE": "r7i.2xlarge",
                "REGSUB_DRAGEN_PCLUSTER_AMI": ami_id,
                "REGSUB_DRAGEN_LICENSE_SECRET_ARN": secret_arn,
                "REGSUB_DRAGEN_LICENSE_POLICY_ARN": policy_arn,
                "REGSUB_PCLUSTER_COOKBOOK_URI": cookbook_uri,
                "REGSUB_S3_BUCKET_INIT": "s3://private-assets/boot",
                "REGSUB_S3_IAM_POLICY": ("arn:aws:iam::123456789012:policy/dayec-cluster"),
                "REGSUB_S3_REFERENCE_BUCKET": "references",
                "REGSUB_S3_CONTROL_DATA_BUCKET": "controls",
                "REGSUB_S3_STAGE_BUCKET": "stage",
                "REGSUB_S3_EXPORT_BUCKET": "export",
                "REGSUB_S3_REFERENCE_URI": "s3://references",
                "REGSUB_FSX_SIZE": "4800",
                "REGSUB_DETAILED_MONITORING": "false",
                "REGSUB_DELETE_LOCAL_ROOT": "true",
                "REGSUB_SAVE_FSX": "Delete",
                "REGSUB_MAX_COUNT_192I_M": "1",
                "REGSUB_MAX_COUNT_192I_NVME_M": "1",
                "REGSUB_ENFORCE_BUDGET": '"true"',
                "REGSUB_SPOT_PRICE_WARN_THRESHOLD": '"8.00"',
                "REGSUB_SLURM_ACCOUNTING_HEADNODE_NETWORKING": "",
                "REGSUB_SLURM_ACCOUNTING_DATABASE": "",
            }
        )
        rendered = renderer.render_template(template, substitutions)
        cluster_yaml = tmp_path / "cluster.yaml"
        cluster_yaml.write_text(rendered, encoding="utf-8")
        inputs = create_cluster_module.DragenCreateInputs(
            backport=SimpleNamespace(
                image_ami_id=ami_id,
                cookbook_bundle_uri=cookbook_uri,
            ),
            license_secret_arn=secret_arn,
            license_policy_arn=policy_arn,
        )

        validate_dragen_cluster_contract(cluster_yaml, inputs)

        payload = yaml.safe_load(rendered)
        queues = payload["Scheduling"]["SlurmQueues"]
        assert [queue["Name"] for queue in queues] == [
            "dragen",
            "dragen-ondemand",
            "i192",
            "i192nvme",
        ]
        assert queues[0]["CustomActions"]["OnNodeConfigured"]["Args"][-1] == "dragen"
        assert queues[1]["CapacityType"] == "ONDEMAND"
        assert queues[1]["CustomActions"]["OnNodeConfigured"]["Args"][-1] == "dragen"
        assert queues[1]["ComputeResources"][0]["Name"] == "f26xlargeod"
        assert "SpotPrice" not in queues[1]["ComputeResources"][0]
        for queue in queues[2:]:
            assert queue["CustomActions"]["OnNodeConfigured"]["Args"][-1] == "cpu"
            policies = [item["Policy"] for item in queue["Iam"]["AdditionalIamPolicies"]]
            assert policy_arn not in policies
            assert queue["ComputeResources"][0]["Efa"]["Enabled"] is False

        missing_cluster_ami = rendered.replace(
            f"  CustomAmi: {ami_id}\nHeadNode:",
            "HeadNode:",
            1,
        )
        cluster_yaml.write_text(missing_cluster_ami, encoding="utf-8")
        with pytest.raises(ValueError, match="cluster-wide AMI"):
            validate_dragen_cluster_contract(cluster_yaml, inputs)

        broken = rendered.replace("MaxCount: 1", "MaxCount: 2")
        cluster_yaml.write_text(broken, encoding="utf-8")
        with pytest.raises(ValueError, match="MinCount 0 and MaxCount 1"):
            validate_dragen_cluster_contract(cluster_yaml, inputs)

        missing_cpu_queue = yaml.safe_load(rendered)
        missing_cpu_queue["Scheduling"]["SlurmQueues"] = missing_cpu_queue["Scheduling"][
            "SlurmQueues"
        ][:2]
        cluster_yaml.write_text(yaml.safe_dump(missing_cpu_queue), encoding="utf-8")
        with pytest.raises(
            ValueError,
            match="dragen, dragen-ondemand, i192, and i192nvme",
        ):
            validate_dragen_cluster_contract(cluster_yaml, inputs)

        bad_cpu_role = rendered.replace("        - cpu\n", "        - dragen\n", 1)
        cluster_yaml.write_text(bad_cpu_role, encoding="utf-8")
        with pytest.raises(ValueError, match="explicit CPU role"):
            validate_dragen_cluster_contract(cluster_yaml, inputs)

    def test_resolves_az_template_when_config_has_no_explicit_template(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        template = (
            tmp_path
            / "config/day_cluster/intel/us-west-2/us-west-2d/prod_cluster_intel_us-west-2d.yaml"
        )
        template.parent.mkdir(parents=True)
        template.write_text("Region: ${REGSUB_REGION}\n", encoding="utf-8")
        monkeypatch.chdir(tmp_path)

        cfg = ConfigFile()

        resolved = resolve_cluster_template_yaml(
            cfg,
            region_az="us-west-2d",
            cluster_type="intel",
            resource_path_fn=lambda rel: (_ for _ in ()).throw(FileNotFoundError(rel)),
        )

        assert resolved == (
            "config/day_cluster/intel/us-west-2/us-west-2d/prod_cluster_intel_us-west-2d.yaml"
        )

    def test_explicit_cluster_template_set_value_wins(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        explicit = tmp_path / "custom.yaml"
        explicit.write_text("Region: ${REGSUB_REGION}\n", encoding="utf-8")
        monkeypatch.chdir(tmp_path)
        cfg = ConfigFile()
        cfg.ephemeral_cluster.config["cluster_template_yaml"] = Triplet(
            action="USESETVALUE",
            default_value="",
            set_value=str(explicit),
        )

        resolved = resolve_cluster_template_yaml(
            cfg,
            region_az="us-west-2d",
            cluster_type="intel",
            resource_path_fn=lambda rel: (_ for _ in ()).throw(FileNotFoundError(rel)),
        )

        assert resolved == str(explicit)

    def test_missing_az_template_fails_hard(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.chdir(tmp_path)
        cfg = ConfigFile()

        with pytest.raises(FileNotFoundError, match="prod_cluster_rhel_us-west-2d.yaml"):
            resolve_cluster_template_yaml(
                cfg,
                region_az="us-west-2d",
                cluster_type="rhel",
                resource_path_fn=lambda rel: (_ for _ in ()).throw(FileNotFoundError(rel)),
            )


class TestStartupDraContract:
    def test_accepts_exactly_one_references_startup_dra(self, tmp_path):
        config = tmp_path / "cluster.yaml"
        config.write_text(
            """
SharedStorage:
  - Name: fsx
    StorageType: FsxLustre
    FsxLustreSettings:
      DataRepositoryAssociations:
        - Name: reference-data
          FileSystemPath: /references/
          DataRepositoryPath: s3://references/
""",
            encoding="utf-8",
        )

        validate_startup_dra_contract(config)

    def test_rejects_any_non_reference_startup_dra(self, tmp_path):
        config = tmp_path / "cluster.yaml"
        config.write_text(
            """
SharedStorage:
  - Name: fsx
    StorageType: FsxLustre
    FsxLustreSettings:
      DataRepositoryAssociations:
        - Name: reference-data
          FileSystemPath: /references/
          DataRepositoryPath: s3://references/
        - Name: control-data
          FileSystemPath: /control_data/
          DataRepositoryPath: s3://control-data/
""",
            encoding="utf-8",
        )

        with pytest.raises(ValueError, match="exactly one FSx DRA: /references/"):
            validate_startup_dra_contract(config)


# ── _extract_selected ───────────────────────────────────────────────────


class TestExtractSelected:
    def test_found(self):
        report = PreflightReport(
            checks=[
                CheckResult(
                    id="s3.bucket_select",
                    status=CheckStatus.PASS,
                    details={"selected": "my-bucket-name"},
                ),
            ],
        )
        assert _extract_selected(report, "s3.bucket_select", "selected") == "my-bucket-name"

    def test_not_found_check(self):
        report = PreflightReport(
            checks=[
                CheckResult(id="other.check", status=CheckStatus.PASS),
            ],
        )
        assert _extract_selected(report, "s3.bucket_select", "selected") == ""

    def test_missing_detail_key(self):
        report = PreflightReport(
            checks=[
                CheckResult(
                    id="s3.bucket_select",
                    status=CheckStatus.PASS,
                    details={"region": "us-west-2"},
                ),
            ],
        )
        assert _extract_selected(report, "s3.bucket_select", "selected") == ""

    def test_empty_report(self):
        report = PreflightReport()
        assert _extract_selected(report, "any", "key") == ""


# ── _noop_heartbeat_result ──────────────────────────────────────────────


class TestNoopHeartbeatResult:
    def test_attributes(self):
        result = _noop_heartbeat_result()
        assert result.success is False
        assert result.topic_arn == ""
        assert result.schedule_name == ""
        assert result.role_arn == ""
        assert result.error == "skipped"


class TestRepositoryCatalogPreflight:
    def test_valid_checked_in_catalog_passes(self):
        catalog_path = (
            Path(__file__).resolve().parents[1]
            / "config"
            / ("daylily_pipeline_command_catalog.yaml")
        )
        report = PreflightReport()

        result = make_repository_catalog_preflight_step(catalog_path)(report)

        check = result.checks[-1]
        assert check.id == "config.repository_catalog"
        assert check.status == CheckStatus.PASS
        assert check.details["path"] == str(catalog_path)
        assert check.details["repository_count"] >= 1
        assert check.details["command_count"] >= 1

    def test_malformed_catalog_fails_with_headnode_day_clone_context(self, tmp_path):
        catalog_path = tmp_path / "daylily_pipeline_command_catalog.yaml"
        catalog_path.write_text(
            "command_catalog_version: [unterminated\n",
            encoding="utf-8",
        )
        report = PreflightReport()

        result = make_repository_catalog_preflight_step(catalog_path)(report)

        check = result.checks[-1]
        assert check.id == "config.repository_catalog"
        assert check.status == CheckStatus.FAIL
        assert check.details["path"] == str(catalog_path)
        assert "while parsing a flow sequence" in check.details["error"]
        assert "Headnode configuration would fail" in check.remediation
        assert "day-clone consumes this file" in check.remediation

    def test_malformed_catalog_short_circuits_preflight_pipeline(self, monkeypatch, tmp_path):
        catalog_path = tmp_path / "daylily_pipeline_command_catalog.yaml"
        catalog_path.write_text(
            "command_catalog_version: [unterminated\n",
            encoding="utf-8",
        )
        called = False

        def later_step(report: PreflightReport) -> PreflightReport:
            nonlocal called
            called = True
            return report

        monkeypatch.setattr(
            create_cluster_module,
            "write_preflight_report",
            lambda report: None,
        )

        result = run_preflight(
            PreflightReport(),
            steps=[make_repository_catalog_preflight_step(catalog_path), later_step],
        )

        assert called is False
        assert result.failed_checks[0].id == "config.repository_catalog"


class TestWorkflowResolutionHelpers:
    def test_resolve_config_value_uses_default_non_interactive(self):
        cfg = ConfigFile.model_validate(
            {
                "ephemeral_cluster": {
                    "config": {"cluster_name": ["PROMPTUSER", "majors-cluster", ""]},
                    "template_defaults": {},
                }
            }
        )

        value = _resolve_config_value(
            cfg,
            "cluster_name",
            "Cluster name",
            non_interactive=True,
            default_fallback="prod",
        )

        assert value == "majors-cluster"

    @patch("daylily_ec.workflow.create_cluster.typer.prompt", return_value="chosen-cluster")
    def test_resolve_config_value_prompts_interactively(self, mock_prompt):
        cfg = ConfigFile.model_validate(
            {
                "ephemeral_cluster": {
                    "config": {"cluster_name": ["PROMPTUSER", "majors-cluster", ""]},
                    "template_defaults": {},
                }
            }
        )

        value = _resolve_config_value(
            cfg,
            "cluster_name",
            "Cluster name",
            non_interactive=False,
            default_fallback="prod",
        )

        assert value == "chosen-cluster"
        mock_prompt.assert_called_once()

    @patch("daylily_ec.aws.s3.list_role_candidate_uris")
    @patch("daylily_ec.workflow.create_cluster.typer.prompt")
    def test_resolve_s3_role_auto_selects_single_candidate(self, mock_prompt, mock_candidates):
        cfg = ConfigFile.model_validate(
            {
                "ephemeral_cluster": {
                    "config": {"reference_s3_uri": ["PROMPTUSER", "", ""]},
                    "template_defaults": {},
                }
            }
        )
        mock_candidates.return_value = ["s3://lsmc-dayoa-references-usw2/"]

        value = _resolve_s3_role_config_value(
            cfg,
            "reference_s3_uri",
            "Reference S3 URI",
            role="reference",
            aws_ctx=SimpleNamespace(region="us-west-2"),
            non_interactive=False,
        )

        assert value == "s3://lsmc-dayoa-references-usw2/"
        mock_prompt.assert_not_called()

    @patch("daylily_ec.aws.s3.list_role_candidate_uris")
    @patch("daylily_ec.workflow.create_cluster.typer.prompt")
    def test_resolve_export_destination_auto_selects_single_candidate(
        self,
        mock_prompt,
        mock_candidates,
    ):
        cfg = ConfigFile.model_validate(
            {
                "ephemeral_cluster": {
                    "config": {"export_destination_s3_uri": ["PROMPTUSER", "", ""]},
                    "template_defaults": {},
                }
            }
        )
        mock_candidates.return_value = ["s3://lsmc-ssf-sequencing-data/derived/"]

        value = _resolve_s3_role_config_value(
            cfg,
            "export_destination_s3_uri",
            "Export destination S3 URI",
            role="export_destination",
            aws_ctx=SimpleNamespace(region="us-west-2"),
            non_interactive=False,
        )

        assert value == "s3://lsmc-ssf-sequencing-data/derived/"
        mock_prompt.assert_not_called()

    @patch("daylily_ec.aws.s3.list_role_candidate_uris")
    @patch("daylily_ec.workflow.create_cluster.typer.prompt", return_value="1")
    def test_resolve_s3_role_respects_disabled_auto_select(
        self,
        mock_prompt,
        mock_candidates,
        monkeypatch,
    ):
        cfg = ConfigFile.model_validate(
            {
                "ephemeral_cluster": {
                    "config": {"reference_s3_uri": ["PROMPTUSER", "", ""]},
                    "template_defaults": {},
                }
            }
        )
        mock_candidates.return_value = ["s3://lsmc-dayoa-references-usw2/"]
        monkeypatch.setenv("DAY_DISABLE_AUTO_SELECT", "1")

        value = _resolve_s3_role_config_value(
            cfg,
            "reference_s3_uri",
            "Reference S3 URI",
            role="reference",
            aws_ctx=SimpleNamespace(region="us-west-2"),
            non_interactive=False,
        )

        assert value == "s3://lsmc-dayoa-references-usw2/"
        mock_prompt.assert_called_once()

    @patch("daylily_ec.aws.s3.list_role_candidate_uris")
    @patch("daylily_ec.workflow.create_cluster.typer.prompt", return_value="2")
    def test_resolve_s3_role_prompts_when_multiple_candidates(self, _mock_prompt, mock_candidates):
        cfg = ConfigFile.model_validate(
            {
                "ephemeral_cluster": {
                    "config": {"stage_s3_uri": ["PROMPTUSER", "", ""]},
                    "template_defaults": {},
                }
            }
        )
        mock_candidates.return_value = [
            "s3://lsmc-dayoa-staging-usw2/",
            "s3://lsmc-ssf-sequencing-data/staged_external_data/",
        ]

        value = _resolve_s3_role_config_value(
            cfg,
            "stage_s3_uri",
            "Stage S3 URI",
            role="staging",
            aws_ctx=SimpleNamespace(region="us-west-2"),
            non_interactive=False,
        )

        assert value == "s3://lsmc-ssf-sequencing-data/staged_external_data/"

    @patch("daylily_ec.aws.s3.list_role_candidate_uris")
    @patch(
        "daylily_ec.workflow.create_cluster.typer.prompt",
        return_value="s3://manual-reference/",
    )
    def test_resolve_s3_role_prompts_for_uri_when_no_candidates(
        self,
        _mock_prompt,
        mock_candidates,
    ):
        cfg = ConfigFile.model_validate(
            {
                "ephemeral_cluster": {
                    "config": {"reference_s3_uri": ["PROMPTUSER", "", ""]},
                    "template_defaults": {},
                }
            }
        )
        mock_candidates.return_value = []

        value = _resolve_s3_role_config_value(
            cfg,
            "reference_s3_uri",
            "Reference S3 URI",
            role="reference",
            aws_ctx=SimpleNamespace(region="us-west-2"),
            non_interactive=False,
        )

        assert value == "s3://manual-reference/"

    @patch("daylily_ec.aws.s3.list_role_candidate_uris")
    def test_resolve_s3_role_non_interactive_does_not_discover(self, mock_candidates):
        cfg = ConfigFile.model_validate(
            {
                "ephemeral_cluster": {
                    "config": {"reference_s3_uri": ["PROMPTUSER", "s3://default-ref/", ""]},
                    "template_defaults": {},
                }
            }
        )

        value = _resolve_s3_role_config_value(
            cfg,
            "reference_s3_uri",
            "Reference S3 URI",
            role="reference",
            aws_ctx=SimpleNamespace(region="us-west-2"),
            non_interactive=True,
        )

        assert value == "s3://default-ref/"
        mock_candidates.assert_not_called()

    def test_require_values_reports_missing_labels(self):
        msg = _require_values({"bucket": "b", "public subnet": "", "IAM policy ARN": ""})
        assert msg == "Missing required values: public subnet, IAM policy ARN"

    def test_post_create_inputs_default_allowed_budget_user_is_ubuntu(self):
        cfg = ConfigFile.model_validate(
            {"ephemeral_cluster": {"config": {}, "template_defaults": {}}}
        )

        values = _resolve_post_create_inputs(
            cfg,
            cluster_name="cluster-a",
            non_interactive=True,
            disable_budget_enforcement=False,
            budget_email_default="ops@example.com",
            allowed_budget_users_default="ubuntu",
        )

        assert values.allowed_budget_users == "ubuntu"
        assert values.enforce_budget == "true"

    def test_build_connection_command_uses_ssm_helper(self):
        cmd = _build_connection_command(
            "majors-cluster",
            region="us-west-2",
            profile="lsmc",
        )
        assert (
            cmd
            == "daylily-ssh-into-headnode --profile lsmc --region us-west-2 --cluster majors-cluster"
        )

    def test_is_valid_fsx_size(self):
        for size in ("1200", "2400", "4800", "7200", "9600", "12000", "14400"):
            assert _is_valid_fsx_size(size) is True
        for size in ("3600", "6000", "1250", "abc", "0"):
            assert _is_valid_fsx_size(size) is False

    def test_resolve_fsx_size_uses_valid_default(self):
        cfg = ConfigFile.model_validate(
            {
                "ephemeral_cluster": {
                    "config": {"fsx_fs_size": ["PROMPTUSER", "4800", ""]},
                    "template_defaults": {},
                }
            }
        )

        assert _resolve_fsx_size(cfg, non_interactive=True) == "4800"

    @pytest.mark.parametrize("default_value", ["3600", "6000", "1250"])
    def test_resolve_fsx_size_rejects_invalid_default(self, default_value):
        cfg = ConfigFile.model_validate(
            {
                "ephemeral_cluster": {
                    "config": {"fsx_fs_size": ["PROMPTUSER", default_value, ""]},
                    "template_defaults": {},
                }
            }
        )

        with patch("daylily_ec.workflow.create_cluster.typer.echo"):
            with pytest.raises(ValueError, match=rf"Invalid FSx size '{default_value}'"):
                _resolve_fsx_size(cfg, non_interactive=True)

    def test_resolve_fsx_size_prompts_with_menu(self):
        cfg = ConfigFile.model_validate(
            {
                "ephemeral_cluster": {
                    "config": {"fsx_fs_size": ["PROMPTUSER", "", ""]},
                    "template_defaults": {},
                }
            }
        )

        with (
            patch(
                "daylily_ec.workflow.create_cluster.typer.prompt", return_value="2"
            ) as mock_prompt,
            patch("daylily_ec.workflow.create_cluster.typer.echo") as mock_echo,
        ):
            assert _resolve_fsx_size(cfg, non_interactive=False) == "2400"

        assert [call.args[0] for call in mock_echo.call_args_list] == [
            "Choose FSx Lustre file system size (GiB).",
            "Smallest allowed sizes:",
            "  [1] 1200",
            "  [2] 2400",
            "  [3] 4800",
            "  [4] 7200",
            "  [5] 9600",
            "  [6] 12000",
            "  [7] 14400",
        ]
        mock_prompt.assert_called_once()

    def test_resolve_fsx_size_accepts_explicit_valid_size(self):
        cfg = ConfigFile.model_validate(
            {
                "ephemeral_cluster": {
                    "config": {"fsx_fs_size": ["PROMPTUSER", "", ""]},
                    "template_defaults": {},
                }
            }
        )

        with (
            patch(
                "daylily_ec.workflow.create_cluster.typer.prompt", return_value="9600"
            ) as mock_prompt,
            patch("daylily_ec.workflow.create_cluster.typer.echo"),
        ):
            assert _resolve_fsx_size(cfg, non_interactive=False) == "9600"

        mock_prompt.assert_called_once()

    def test_valid_headnode_instance_types_are_ordered_smallest_to_largest(self):
        assert _is_valid_headnode_instance_type("r7i.2xlarge") is True
        assert _is_valid_headnode_instance_type("r7i.16xlarge") is True
        assert _is_valid_headnode_instance_type("m5.xlarge") is False

    def test_resolve_headnode_instance_type_uses_approved_configured_value(self):
        cfg = ConfigFile.model_validate(
            {
                "ephemeral_cluster": {
                    "config": {"headnode_instance_type": ["USESETVALUE", "", "r7i.8xlarge"]},
                    "template_defaults": {},
                }
            }
        )

        assert _resolve_headnode_instance_type(cfg, non_interactive=True) == "r7i.8xlarge"

    def test_resolve_headnode_instance_type_rejects_unapproved_value(self):
        cfg = ConfigFile.model_validate(
            {
                "ephemeral_cluster": {
                    "config": {"headnode_instance_type": ["USESETVALUE", "", "m5.xlarge"]},
                    "template_defaults": {},
                }
            }
        )

        with pytest.raises(ValueError, match="approved headnode instance types"):
            _resolve_headnode_instance_type(cfg, non_interactive=True)

    def test_resolve_headnode_instance_type_prompts_with_approved_menu(self):
        cfg = ConfigFile.model_validate(
            {
                "ephemeral_cluster": {
                    "config": {"headnode_instance_type": ["PROMPTUSER", "r7i.2xlarge", ""]},
                    "template_defaults": {},
                }
            }
        )

        with (
            patch(
                "daylily_ec.workflow.create_cluster.typer.prompt",
                return_value="3",
            ) as mock_prompt,
            patch("daylily_ec.workflow.create_cluster.typer.echo") as mock_echo,
        ):
            assert _resolve_headnode_instance_type(cfg, non_interactive=False) == "r7i.8xlarge"

        assert [call.args[0] for call in mock_echo.call_args_list] == [
            "Choose headnode instance type (approved types, smallest to largest).",
            "  [1] r7i.2xlarge (default)",
            "  [2] r7i.4xlarge",
            "  [3] r7i.8xlarge",
            "  [4] r7i.16xlarge",
        ]
        mock_prompt.assert_called_once()


class TestClusterNameValidation:
    @pytest.mark.parametrize(
        "cluster_name",
        [
            "frz-260509",
            "cluster1",
            "a2345",
            "a-1-b",
            "splitdra-ref-260526",
            "sent-hg003-5x-0712",
        ],
    )
    def test_cluster_names_allow_numbers_after_first_character(self, cluster_name):
        assert _validate_cluster_name(cluster_name) == cluster_name

    @pytest.mark.parametrize(
        ("cluster_name", "message"),
        [
            ("260509-frz", "start with a lowercase letter"),
            ("frz_260509", "contain only lowercase letters, digits, and hyphens"),
            ("sent-liscC", "lowercase"),
            ("A2345", "lowercase"),
            ("frz", "5-20 characters"),
            ("a" * 21, "5-20 characters"),
        ],
    )
    def test_invalid_cluster_names_fail_with_actionable_rules(self, cluster_name, message):
        with pytest.raises(ValueError, match=message):
            _validate_cluster_name(cluster_name)

    def test_resolve_cluster_name_rejects_invalid_config_before_aws(self):
        cfg = ConfigFile.model_validate(
            {
                "ephemeral_cluster": {
                    "config": {"cluster_name": ["USESETVALUE", "", "260509-frz"]},
                    "template_defaults": {},
                }
            }
        )

        with pytest.raises(ValueError, match="start with a lowercase letter"):
            _resolve_cluster_name(cfg, non_interactive=True)

    def test_resolve_cluster_name_reprompts_until_name_is_compliant(self):
        cfg = ConfigFile.model_validate(
            {
                "ephemeral_cluster": {
                    "config": {"cluster_name": ["PROMPTUSER", "majors-cluster", ""]},
                    "template_defaults": {},
                }
            }
        )

        with (
            patch(
                "daylily_ec.workflow.create_cluster.typer.prompt",
                side_effect=["sent-liscC", "a" * 21, "sent-liscc"],
            ) as mock_prompt,
            patch("daylily_ec.workflow.create_cluster.typer.echo") as mock_echo,
        ):
            assert _resolve_cluster_name(cfg, non_interactive=False) == "sent-liscc"

        assert mock_prompt.call_count == 3
        errors = [str(call.args[0]) for call in mock_echo.call_args_list]
        assert any("lowercase" in error for error in errors)
        assert any("5-20 characters" in error for error in errors)

    def test_resolve_cluster_name_reprompts_for_invalid_configured_value(self):
        cfg = ConfigFile.model_validate(
            {
                "ephemeral_cluster": {
                    "config": {"cluster_name": ["USESETVALUE", "", "sent-liscC"]},
                    "template_defaults": {},
                }
            }
        )

        with (
            patch(
                "daylily_ec.workflow.create_cluster.typer.prompt",
                return_value="sent-liscc",
            ) as mock_prompt,
            patch("daylily_ec.workflow.create_cluster.typer.echo") as mock_echo,
        ):
            assert _resolve_cluster_name(cfg, non_interactive=False) == "sent-liscc"

        mock_prompt.assert_called_once()
        assert any("lowercase" in str(call.args[0]) for call in mock_echo.call_args_list)

    @patch("daylily_ec.aws.context.AWSContext.build")
    def test_create_workflow_rejects_invalid_cluster_name_before_aws(
        self, mock_build, tmp_path, monkeypatch
    ):
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        config_path = tmp_path / "invalid_cluster.yaml"
        config_path.write_text(
            "\n".join(
                [
                    "ephemeral_cluster:",
                    "  config:",
                    "    cluster_name: [USESETVALUE, '', 260509-frz]",
                    "  template_defaults: {}",
                ]
            ),
            encoding="utf-8",
        )

        from daylily_ec.workflow.create_cluster import run_create_workflow

        rc = run_create_workflow(
            "us-west-2b",
            profile="test",
            config_path=str(config_path),
            non_interactive=True,
        )

        assert rc == EXIT_VALIDATION_FAILURE
        mock_build.assert_not_called()

    @patch("daylily_ec.aws.context.AWSContext.build")
    def test_preflight_rejects_too_long_cluster_name_before_aws(
        self, mock_build, tmp_path, monkeypatch
    ):
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        config_path = tmp_path / "too_long_cluster.yaml"
        config_path.write_text(
            "\n".join(
                [
                    "ephemeral_cluster:",
                    "  config:",
                    f"    cluster_name: [USESETVALUE, '', {'a' * 61}]",
                    "  template_defaults: {}",
                ]
            ),
            encoding="utf-8",
        )

        from daylily_ec.workflow.create_cluster import run_preflight_only

        rc = run_preflight_only(
            "us-west-2b",
            profile="test",
            config_path=str(config_path),
            non_interactive=True,
        )

        assert rc == EXIT_VALIDATION_FAILURE
        mock_build.assert_not_called()


# ── Module exports ──────────────────────────────────────────────────────


class TestWorkflowExports:
    def test_exports(self):
        import daylily_ec.workflow as wf

        assert hasattr(wf, "run_create_workflow")
        assert hasattr(wf, "run_preflight_only")
        assert hasattr(wf, "run_preflight")
        assert hasattr(wf, "should_abort")
        assert hasattr(wf, "exit_code_for")
        assert hasattr(wf, "EXIT_SUCCESS")
        assert hasattr(wf, "EXIT_VALIDATION_FAILURE")
        assert hasattr(wf, "EXIT_AWS_FAILURE")
        assert hasattr(wf, "EXIT_DRIFT")
        assert hasattr(wf, "EXIT_TOOLCHAIN")


# ── run_preflight_only — AWS context failure ────────────────────────────


class TestRunPreflightOnly:
    @patch("daylily_ec.aws.context.AWSContext.build")
    def test_aws_context_failure(self, mock_build, tmp_path, monkeypatch):
        """AWS context build failure returns EXIT_AWS_FAILURE."""
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        monkeypatch.setenv("AWS_PROFILE", "test")
        mock_build.side_effect = RuntimeError("no creds")

        from daylily_ec.workflow.create_cluster import run_preflight_only

        rc = run_preflight_only("us-west-2b", profile="test")
        assert rc == EXIT_AWS_FAILURE


# ── run_create_workflow — AWS context failure ───────────────────────────


class TestRunCreateWorkflow:
    def test_regional_cluster_cap_defaults_to_five(self):
        assert validate_regional_cluster_cap_options(None) == DEFAULT_REGIONAL_CLUSTER_CAP == 5

    @pytest.mark.parametrize("invalid_cap", [0, -1])
    def test_regional_cluster_cap_rejects_values_below_one(self, invalid_cap):
        with pytest.raises(ValueError, match="at least 1"):
            validate_regional_cluster_cap_options(invalid_cap)

    @pytest.mark.parametrize(
        ("increase_ack", "risk_ack", "missing_flag"),
        [
            (False, False, "--acknowledge-regional-cap-increase"),
            (True, False, "--acknowledge-regional-cap-risk"),
            (False, True, "--acknowledge-regional-cap-increase"),
        ],
    )
    def test_regional_cluster_cap_increase_requires_both_acknowledgements(
        self,
        increase_ack,
        risk_ack,
        missing_flag,
    ):
        with pytest.raises(ValueError, match=missing_flag):
            validate_regional_cluster_cap_options(
                6,
                acknowledge_regional_cap_increase=increase_ack,
                acknowledge_regional_cap_risk=risk_ack,
            )

    def test_regional_cluster_cap_rejects_misleading_acknowledgements(self):
        with pytest.raises(ValueError, match="valid only with an explicit"):
            validate_regional_cluster_cap_options(
                5,
                acknowledge_regional_cap_increase=True,
                acknowledge_regional_cap_risk=True,
            )

    def test_regional_cluster_cap_counts_every_status_except_exact_delete_complete(self):
        decision = evaluate_regional_cluster_cap(
            cluster_name="requested-cluster",
            effective_cap=5,
            records=[
                {"clusterName": "deleted-cluster", "clusterStatus": "DELETE_COMPLETE"},
                {"clusterName": "lowercase-delete", "clusterStatus": "delete_complete"},
                {"clusterName": "failed-cluster", "clusterStatus": "CREATE_FAILED"},
            ],
        )

        assert decision.current_count == 2
        assert decision.projected_count == 3
        assert decision.counted_records == (
            ("lowercase-delete", "delete_complete"),
            ("failed-cluster", "CREATE_FAILED"),
        )

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"global_spot_max_cost": 10.01},
            {"spot_cost_limit_pct": 0.99},
            {"spot_cost_limit_pct": 2.21},
            {"write_spot_pricing_warn_threshold": 0},
        ],
    )
    @patch("daylily_ec.aws.context.AWSContext.build")
    def test_spot_pricing_validation_failure_before_aws(
        self,
        mock_build,
        kwargs,
        tmp_path,
        monkeypatch,
    ):
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))

        from daylily_ec.workflow.create_cluster import run_create_workflow

        rc = run_create_workflow(
            "us-west-2b",
            profile="test",
            non_interactive=True,
            **kwargs,
        )

        assert rc == EXIT_VALIDATION_FAILURE
        mock_build.assert_not_called()

    @patch("daylily_ec.aws.context.AWSContext.build")
    def test_regional_cap_override_validation_runs_before_aws(
        self, mock_build, tmp_path, monkeypatch
    ):
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))

        rc = create_cluster_module.run_create_workflow(
            "us-west-2b",
            profile="test",
            non_interactive=True,
            regional_cluster_cap=6,
            acknowledge_regional_cap_increase=True,
        )

        assert rc == EXIT_VALIDATION_FAILURE
        mock_build.assert_not_called()

    @patch("daylily_ec.aws.context.AWSContext.build")
    def test_aws_context_failure(self, mock_build, tmp_path, monkeypatch):
        """AWS context build failure returns EXIT_AWS_FAILURE."""
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        monkeypatch.setenv("AWS_PROFILE", "test")
        mock_build.side_effect = RuntimeError("no creds")

        from daylily_ec.workflow.create_cluster import run_create_workflow

        rc = run_create_workflow("us-west-2b", profile="test", non_interactive=True)
        assert rc == EXIT_AWS_FAILURE

    def test_fifth_projected_cluster_is_allowed(self, tmp_path, monkeypatch):
        clusters = [
            {"clusterName": f"cluster-{index}", "clusterStatus": "CREATE_COMPLETE"}
            for index in range(4)
        ]

        records = _run_stubbed_create_workflow(
            tmp_path,
            monkeypatch,
            interactive=False,
            head_node_ip="54.1.2.3",
            say_available=False,
            regional_clusters=clusters,
        )

        assert records["rc"] == EXIT_SUCCESS
        assert records["baseline_stack_calls"] == 1
        assert records["regional_cluster_list_calls"] == [
            ("us-west-2", {"profile": "lsmc", "executable": "pcluster"})
        ]

    def test_sixth_projected_cluster_is_blocked_before_mutations(self, tmp_path, monkeypatch):
        clusters = [
            {"clusterName": f"cluster-{index}", "clusterStatus": "CREATE_COMPLETE"}
            for index in range(5)
        ]

        records = _run_stubbed_create_workflow(
            tmp_path,
            monkeypatch,
            interactive=False,
            head_node_ip="54.1.2.3",
            say_available=False,
            regional_clusters=clusters,
        )

        assert records["rc"] == EXIT_VALIDATION_FAILURE
        assert records["baseline_stack_calls"] == 0
        assert "cluster_budget_kwargs" not in records
        assert ("phase", "PREFLIGHT") not in records["events"]
        assert "cluster-0=CREATE_COMPLETE" in records["failures"][0]
        assert "projected=6, cap=5" in records["failures"][0]

    def test_same_existing_cluster_name_does_not_increase_projection(self, tmp_path, monkeypatch):
        clusters = [
            {"clusterName": "majors-cluster", "clusterStatus": "CREATE_COMPLETE"},
            {"clusterName": "cluster-one", "clusterStatus": "CREATE_COMPLETE"},
            {"clusterName": "cluster-two", "clusterStatus": "UPDATE_IN_PROGRESS"},
            {"clusterName": "cluster-three", "clusterStatus": "CREATE_FAILED"},
            {"clusterName": "cluster-four", "clusterStatus": "DELETE_IN_PROGRESS"},
        ]

        records = _run_stubbed_create_workflow(
            tmp_path,
            monkeypatch,
            interactive=False,
            head_node_ip="54.1.2.3",
            say_available=False,
            regional_clusters=clusters,
        )

        assert records["rc"] == EXIT_SUCCESS
        cap_details = [value for key, value in records["details"] if key == "Regional cluster cap"]
        assert cap_details == ["current=5, projected=5, cap=5"]

    def test_regional_cluster_list_failure_fails_closed_before_mutations(
        self, tmp_path, monkeypatch
    ):
        records = _run_stubbed_create_workflow(
            tmp_path,
            monkeypatch,
            interactive=False,
            head_node_ip="54.1.2.3",
            say_available=False,
            regional_cluster_list_result=SimpleNamespace(
                success=False,
                returncode=2,
                message="pcluster list-clusters failed with exit code 2",
            ),
        )

        assert records["rc"] == EXIT_AWS_FAILURE
        assert records["baseline_stack_calls"] == 0
        assert "cluster_budget_kwargs" not in records
        assert "failed closed" in records["failures"][0]

    def test_malformed_regional_cluster_inventory_fails_closed_before_mutations(
        self, tmp_path, monkeypatch
    ):
        records = _run_stubbed_create_workflow(
            tmp_path,
            monkeypatch,
            interactive=False,
            head_node_ip="54.1.2.3",
            say_available=False,
            regional_cluster_list_result=SimpleNamespace(
                success=True,
                returncode=0,
                message="",
                json_body={"clusters": "not-a-list"},
            ),
        )

        assert records["rc"] == EXIT_AWS_FAILURE
        assert records["baseline_stack_calls"] == 0
        assert "cluster_budget_kwargs" not in records
        assert "does not contain a clusters list" in records["failures"][0]

    def test_cap_above_five_with_both_acknowledgements_is_allowed(self, tmp_path, monkeypatch):
        clusters = [
            {"clusterName": f"cluster-{index}", "clusterStatus": "CREATE_COMPLETE"}
            for index in range(5)
        ]

        records = _run_stubbed_create_workflow(
            tmp_path,
            monkeypatch,
            interactive=False,
            head_node_ip="54.1.2.3",
            say_available=False,
            regional_clusters=clusters,
            run_kwargs={
                "regional_cluster_cap": 6,
                "acknowledge_regional_cap_increase": True,
                "acknowledge_regional_cap_risk": True,
            },
        )

        assert records["rc"] == EXIT_SUCCESS
        cap_details = [value for key, value in records["details"] if key == "Regional cluster cap"]
        assert cap_details == ["current=5, projected=6, cap=6"]

    def test_collects_budget_and_heartbeat_inputs_before_dry_run(self, tmp_path, monkeypatch):
        records = _run_stubbed_create_workflow(
            tmp_path,
            monkeypatch,
            interactive=True,
            head_node_ip="54.1.2.3",
            say_available=False,
        )

        assert records["rc"] == EXIT_SUCCESS
        assert records["prompt_labels"] == [
            "Budget email",
            "Budget amount",
            "Global budget amount",
            "Allowed budget users",
            "Heartbeat email",
            "Heartbeat schedule",
            "Heartbeat scheduler role ARN (leave blank to skip)",
        ]

        dry_run_phase_index = records["events"].index(("phase", "DRY-RUN VALIDATION"))
        create_phase_index = records["events"].index(("phase", "CREATE CLUSTER"))
        budget_index = records["events"].index(("ensure_cluster_budget", None))
        resolve_role_index = records["events"].index(("resolve_scheduler_role", None))
        prompt_indices = [
            idx for idx, event in enumerate(records["events"]) if event[0] == "prompt"
        ]

        assert prompt_indices
        assert max(prompt_indices) < dry_run_phase_index
        assert budget_index < dry_run_phase_index
        assert create_phase_index < resolve_role_index
        assert records["global_budget_kwargs"]["email"] == "johnm@lsmc.com"
        assert records["global_budget_kwargs"]["amount"] == "200"
        assert records["global_budget_kwargs"]["allowed_users"] == "root"
        assert records["cluster_budget_kwargs"]["email"] == "johnm@lsmc.com"
        assert records["cluster_budget_kwargs"]["cluster_name"] == "majors-cluster"
        assert records["heartbeat_kwargs"]["email"] == "johnm@lsmc.com"
        assert records["heartbeat_kwargs"]["schedule_expression"] == "rate(60 minutes)"
        assert "budget_project" not in records["next_run_values"]
        assert records["next_run_values"]["enforce_budget"] == "true"
        assert records["next_run_values"]["budget_email"] == "johnm@lsmc.com"
        assert records["next_run_values"]["heartbeat_email"] == "johnm@lsmc.com"
        assert records["next_run_values"]["heartbeat_schedule"] == "rate(60 minutes)"
        assert records["next_run_values"]["heartbeat_scheduler_role_arn"] == ""
        assert records["resolve_scheduler_role_kwargs"]["preconfigured"] == ""
        assert records["next_run_values"]["dyec_deploy_key_secret_arn"].endswith(
            ":secret:dayec/dyec-key"
        )
        assert records["next_run_values"]["dyec_deploy_key_policy_arn"].endswith(
            ":policy/DayECHeadnodeDYECClone"
        )
        assert records["next_run_values"]["dayoa_deploy_key_secret_arn"].endswith(
            ":secret:dayec/dayoa-key"
        )
        assert records["next_run_values"]["dayoa_deploy_key_policy_arn"].endswith(
            ":policy/DayECHeadnodeDayOAClone"
        )
        assert records["configure_headnode_kwargs"]["dayoa_deploy_key_region"] == "us-west-2"
        assert records["configure_headnode_kwargs"]["dyec_deploy_key_region"] == "us-west-2"
        assert records["configure_headnode_kwargs"]["dyec_deploy_key_secret_arn"].endswith(
            ":secret:dayec/dyec-key"
        )
        assert records["configure_headnode_kwargs"]["dayoa_deploy_key_secret_arn"].endswith(
            ":secret:dayec/dayoa-key"
        )

    def test_budget_project_override_is_rejected(self, tmp_path, monkeypatch):
        records = _run_stubbed_create_workflow(
            tmp_path,
            monkeypatch,
            interactive=False,
            head_node_ip="54.1.2.3",
            say_available=False,
            run_kwargs={
                "budget_project": "project-alpha",
                "disable_budget_enforcement": True,
            },
        )

        assert records["rc"] == EXIT_VALIDATION_FAILURE

    def test_disable_budget_enforcement_renders_skip_without_budget_project(
        self, tmp_path, monkeypatch
    ):
        records = _run_stubbed_create_workflow(
            tmp_path,
            monkeypatch,
            interactive=False,
            head_node_ip="54.1.2.3",
            say_available=False,
            run_kwargs={
                "disable_budget_enforcement": True,
            },
        )

        assert records["rc"] == EXIT_SUCCESS
        assert records["cluster_budget_kwargs"]["cluster_name"] == "majors-cluster"
        substitutions = records["render_substitutions"]
        assert substitutions["REGSUB_PROJECT"] == "majors-cluster"
        assert substitutions["REGSUB_ENFORCE_BUDGET"] == '"skip"'
        assert "budget_project" not in records["next_run_values"]
        assert records["next_run_values"]["enforce_budget"] == "skip"

    def test_spot_warn_threshold_renders_as_custom_action_string_arg(self, tmp_path, monkeypatch):
        records = _run_stubbed_create_workflow(
            tmp_path,
            monkeypatch,
            interactive=False,
            head_node_ip="54.1.2.3",
            say_available=False,
        )

        assert records["rc"] == EXIT_SUCCESS
        substitutions = records["render_substitutions"]
        assert substitutions["REGSUB_SPOT_PRICE_WARN_THRESHOLD"] == '"8.00"'
        table_path = (
            records["config_dir"]
            / f"{records['render_cluster_name']}-{records['render_run_id']}.md"
        )
        table_text = table_path.read_text(encoding="utf-8")
        assert "| Max Bid $/vCPU-hr |" in table_text
        assert "| i128 | 0 | 1 | 0.0000 | 0.0000 | 1.0000 | 0.0094 |" in table_text
        assert any(str(table_path) in info for info in records["infos"])

    def test_broad_max_counts_populate_rendered_subtype_counts(self, tmp_path, monkeypatch):
        records = _run_stubbed_create_workflow(
            tmp_path,
            monkeypatch,
            interactive=False,
            head_node_ip="54.1.2.3",
            say_available=False,
            config_overrides={
                "max_count_8I": ["USESETVALUE", "1", "16"],
                "max_count_96I_NVME": ["USESETVALUE", "1", "16"],
                "max_count_128I": ["USESETVALUE", "1", "16"],
                "max_count_192I": ["USESETVALUE", "1", "16"],
                "max_count_384I": ["USESETVALUE", "1", "16"],
                "max_count_128I_C": ["USESETVALUE", "1", ""],
                "max_count_128I_M": ["USESETVALUE", "1", ""],
                "max_count_128I_R": ["USESETVALUE", "1", ""],
                "max_count_128I_NVME": ["USESETVALUE", "1", ""],
                "max_count_192I_C": ["USESETVALUE", "1", ""],
                "max_count_192I_M": ["USESETVALUE", "1", ""],
                "max_count_192I_R": ["USESETVALUE", "1", ""],
                "max_count_192I_NVME_C": ["USESETVALUE", "1", ""],
                "max_count_192I_NVME_M": ["USESETVALUE", "1", ""],
                "max_count_192I_NVME_R": ["USESETVALUE", "1", ""],
                "max_count_192I_HUGENVME": ["USESETVALUE", "1", ""],
                "max_count_384I_NVME_C": ["USESETVALUE", "1", ""],
                "max_count_384I_NVME_M": ["USESETVALUE", "1", ""],
                "max_count_384I_NVME_R": ["USESETVALUE", "1", ""],
            },
        )

        assert records["rc"] == EXIT_SUCCESS
        substitutions = records["render_substitutions"]
        for key in [
            "REGSUB_MAX_COUNT_8I",
            "REGSUB_MAX_COUNT_96I_NVME",
            "REGSUB_MAX_COUNT_128I",
            "REGSUB_MAX_COUNT_192I",
            "REGSUB_MAX_COUNT_384I",
            "REGSUB_MAX_COUNT_128I_C",
            "REGSUB_MAX_COUNT_128I_M",
            "REGSUB_MAX_COUNT_128I_R",
            "REGSUB_MAX_COUNT_128I_NVME",
            "REGSUB_MAX_COUNT_192I_C",
            "REGSUB_MAX_COUNT_192I_M",
            "REGSUB_MAX_COUNT_192I_R",
            "REGSUB_MAX_COUNT_192I_NVME_C",
            "REGSUB_MAX_COUNT_192I_NVME_M",
            "REGSUB_MAX_COUNT_192I_NVME_R",
            "REGSUB_MAX_COUNT_192I_HUGENVME",
            "REGSUB_MAX_COUNT_384I_NVME_C",
            "REGSUB_MAX_COUNT_384I_NVME_M",
            "REGSUB_MAX_COUNT_384I_NVME_R",
        ]:
            assert substitutions[key] == "16"

        next_run_values = records["next_run_values"]
        for key in [
            "max_count_8I",
            "max_count_96I_NVME",
            "max_count_128I",
            "max_count_192I",
            "max_count_384I",
            "max_count_128I_C",
            "max_count_128I_M",
            "max_count_128I_R",
            "max_count_128I_NVME",
            "max_count_192I_C",
            "max_count_192I_M",
            "max_count_192I_R",
            "max_count_192I_NVME_C",
            "max_count_192I_NVME_M",
            "max_count_192I_NVME_R",
            "max_count_192I_HUGENVME",
            "max_count_384I_NVME_C",
            "max_count_384I_NVME_M",
            "max_count_384I_NVME_R",
        ]:
            assert next_run_values[key] == "16"

    def test_explicit_subtype_max_count_overrides_broad_count(self, tmp_path, monkeypatch):
        records = _run_stubbed_create_workflow(
            tmp_path,
            monkeypatch,
            interactive=False,
            head_node_ip="54.1.2.3",
            say_available=False,
            config_overrides={
                "max_count_128I": ["USESETVALUE", "1", "16"],
                "max_count_128I_C": ["USESETVALUE", "1", "7"],
            },
        )

        assert records["rc"] == EXIT_SUCCESS
        substitutions = records["render_substitutions"]
        assert substitutions["REGSUB_MAX_COUNT_128I"] == "16"
        assert substitutions["REGSUB_MAX_COUNT_128I_C"] == "7"
        assert substitutions["REGSUB_MAX_COUNT_128I_M"] == "16"

    def test_prints_ssh_command_then_fin_and_runs_say_when_available(self, tmp_path, monkeypatch):
        records = _run_stubbed_create_workflow(
            tmp_path,
            monkeypatch,
            interactive=False,
            head_node_ip="54.1.2.3",
            say_available=True,
        )

        assert records["rc"] == EXIT_SUCCESS
        assert records["echoes"][-2:] == [
            "daylily-ssh-into-headnode --profile lsmc --region us-west-2 --cluster majors-cluster",
            "...fin!",
        ]
        assert records["subprocess_calls"] == [
            ["/bin/sh", "-lc", "command -v say >/dev/null 2>&1"],
            ["say", "Onward to daylily!"],
        ]

    def test_prints_describe_cluster_fallback_when_headnode_ip_is_missing(
        self, tmp_path, monkeypatch
    ):
        records = _run_stubbed_create_workflow(
            tmp_path,
            monkeypatch,
            interactive=False,
            head_node_ip="54.1.2.3",
            say_available=False,
        )

        assert records["rc"] == EXIT_SUCCESS
        assert records["echoes"][-2:] == [
            "daylily-ssh-into-headnode --profile lsmc --region us-west-2 --cluster majors-cluster",
            "...fin!",
        ]
        assert records["subprocess_calls"] == [["/bin/sh", "-lc", "command -v say >/dev/null 2>&1"]]

    def test_scan_slurm_accounting_selection_persists_state(self, tmp_path, monkeypatch):
        accounting_db = SlurmAccountingDb(
            stack_name="dayec-sacct-db",
            status="CREATE_COMPLETE",
            uri="10.0.1.39:3306",
            private_ip="10.0.1.39",
            database_name="slurm_acct_db",
            username="slurm",
            password_secret_arn="arn:aws:secretsmanager:us-west-2:123456789012:secret:sacct",
            client_security_group_id="sg-client",
            instance_id="i-acct",
        )
        candidate = SimpleNamespace(
            instance_id="i-acct",
            name="acct-mariadb",
            private_ip="10.0.1.39",
            availability_zone="us-west-2d",
            vpc_id="vpc-123",
            source="dayec-stack",
            selectable=True,
            reason="Matched healthy DayEC accounting stack dayec-sacct-db.",
            db=accounting_db,
        )

        records = _run_stubbed_create_workflow(
            tmp_path,
            monkeypatch,
            interactive=True,
            head_node_ip="54.1.2.3",
            say_available=False,
            scan_slurm_accounting_db=True,
            scan_candidates=[candidate],
            selection_answer="2",
        )

        assert records["rc"] == EXIT_SUCCESS
        assert records["next_run_values"]["slurm_accounting_enabled"] == "true"
        assert records["next_run_values"]["slurm_accounting_stack_name"] == "dayec-sacct-db"
        assert records["next_run_values"]["slurm_accounting_database_name"] == "slurm_acct_db"
        assert ("Accounting URI", "10.0.1.39:3306") in records["details"]
        assert "Enter selection number" in records["prompt_labels"]

    def test_slurm_accounting_enabled_resolves_existing_db_by_default(self, tmp_path, monkeypatch):
        calls = []

        def fake_ensure_slurm_accounting_db(_aws_ctx, **kwargs):
            calls.append(kwargs)
            return SlurmAccountingDb(
                stack_name="dayec-sacct-db",
                status="CREATE_COMPLETE",
                uri="10.0.1.39:3306",
                private_ip="10.0.1.39",
                database_name="dayec_slurm_acct",
                username="slurm_acct",
                password_secret_arn=("arn:aws:secretsmanager:us-west-2:123456789012:secret:sacct"),
                client_security_group_id="sg-client",
                instance_id="i-acct",
            )

        monkeypatch.setattr(
            aws_slurm_accounting,
            "ensure_slurm_accounting_db",
            fake_ensure_slurm_accounting_db,
        )

        records = _run_stubbed_create_workflow(
            tmp_path,
            monkeypatch,
            interactive=False,
            head_node_ip="54.1.2.3",
            say_available=False,
            config_overrides={
                "slurm_accounting_enabled": ["USESETVALUE", "", "true"],
            },
        )

        assert records["rc"] == EXIT_SUCCESS
        assert calls
        assert calls[0]["create_if_missing"] is False
        assert records["next_run_values"]["slurm_accounting_enabled"] == "true"
        assert ("Accounting stack", "dayec-sacct-db") in records["details"]

    def test_disable_slurm_accounting_overrides_enabled_config(self, tmp_path, monkeypatch):
        records = _run_stubbed_create_workflow(
            tmp_path,
            monkeypatch,
            interactive=False,
            head_node_ip="54.1.2.3",
            say_available=False,
            config_overrides={
                "slurm_accounting_enabled": ["USESETVALUE", "", "true"],
            },
            run_kwargs={"disable_slurm_accounting": True},
        )

        assert records["rc"] == EXIT_SUCCESS
        assert records["next_run_values"]["slurm_accounting_enabled"] == "false"
        assert not any(key == "Accounting stack" for key, _value in records["details"])

    def test_disable_slurm_accounting_rejects_config_create_request(self, tmp_path, monkeypatch):
        records = _run_stubbed_create_workflow(
            tmp_path,
            monkeypatch,
            interactive=False,
            head_node_ip="54.1.2.3",
            say_available=False,
            config_overrides={
                "slurm_accounting_enabled": ["USESETVALUE", "", "true"],
                "slurm_accounting_create_db": ["USESETVALUE", "", "true"],
            },
            run_kwargs={"disable_slurm_accounting": True},
        )

        assert records["rc"] == EXIT_VALIDATION_FAILURE
        assert any(
            "--disable-slurm-accounting cannot be combined" in failure
            for failure in records["failures"]
        )

    def test_scan_slurm_accounting_without_candidates_warns_and_continues(
        self, tmp_path, monkeypatch
    ):
        records = _run_stubbed_create_workflow(
            tmp_path,
            monkeypatch,
            interactive=False,
            head_node_ip="54.1.2.3",
            say_available=False,
            scan_slurm_accounting_db=True,
            scan_candidates=[],
        )

        assert records["rc"] == EXIT_SUCCESS
        assert records["next_run_values"]["slurm_accounting_enabled"] == "false"
        assert any(
            "No usable Slurm accounting DB candidates found" in w for w in records["warnings"]
        )

    def test_scan_slurm_accounting_non_interactive_warns_and_skips(self, tmp_path, monkeypatch):
        accounting_db = SlurmAccountingDb(
            stack_name="dayec-sacct-db",
            status="CREATE_COMPLETE",
            uri="10.0.1.39:3306",
            private_ip="10.0.1.39",
            database_name="slurm_acct_db",
            username="slurm",
            password_secret_arn="arn:aws:secretsmanager:us-west-2:123456789012:secret:sacct",
            client_security_group_id="sg-client",
            instance_id="i-acct",
        )
        candidate = SimpleNamespace(
            instance_id="i-acct",
            name="acct-mariadb",
            private_ip="10.0.1.39",
            availability_zone="us-west-2d",
            vpc_id="vpc-123",
            source="dayec-stack",
            selectable=True,
            reason="Matched healthy DayEC accounting stack dayec-sacct-db.",
            db=accounting_db,
        )

        records = _run_stubbed_create_workflow(
            tmp_path,
            monkeypatch,
            interactive=False,
            head_node_ip="54.1.2.3",
            say_available=False,
            scan_slurm_accounting_db=True,
            scan_candidates=[candidate],
        )

        assert records["rc"] == EXIT_SUCCESS
        assert records["next_run_values"]["slurm_accounting_enabled"] == "false"
        assert any("--non-interactive was set" in w for w in records["warnings"])
        assert "Enter selection number" not in records["prompt_labels"]

    def test_scan_slurm_accounting_rejects_config_create_request(self, tmp_path, monkeypatch):
        records = _run_stubbed_create_workflow(
            tmp_path,
            monkeypatch,
            interactive=False,
            head_node_ip="54.1.2.3",
            say_available=False,
            scan_slurm_accounting_db=True,
            config_overrides={
                "slurm_accounting_create_db": ["USESETVALUE", "", "true"],
            },
        )

        assert records["rc"] == EXIT_VALIDATION_FAILURE
        assert any("cannot be combined" in failure for failure in records["failures"])

    def test_slurm_accounting_create_uses_explicit_private_subnet_vpc(self, tmp_path, monkeypatch):
        calls = []

        def fake_ensure_slurm_accounting_db(_aws_ctx, **kwargs):
            calls.append(kwargs)
            return SlurmAccountingDb(
                stack_name="dayec-sacct-db",
                status="CREATE_COMPLETE",
                uri="10.0.1.39:3306",
                private_ip="10.0.1.39",
                database_name="dayec_slurm_acct",
                username="slurm_acct",
                password_secret_arn="arn:aws:secretsmanager:us-west-2:123456789012:secret:sacct",
                client_security_group_id="sg-client",
                instance_id="i-acct",
            )

        monkeypatch.setattr(
            aws_slurm_accounting,
            "ensure_slurm_accounting_db",
            fake_ensure_slurm_accounting_db,
        )

        records = _run_stubbed_create_workflow(
            tmp_path,
            monkeypatch,
            interactive=False,
            head_node_ip="54.1.2.3",
            say_available=False,
            config_overrides={
                "public_subnet_id": ["USESETVALUE", "", "subnet-explicit-pub"],
                "private_subnet_id": ["USESETVALUE", "", "subnet-explicit-priv"],
                "iam_policy_arn": [
                    "USESETVALUE",
                    "",
                    "arn:aws:iam::123456789012:policy/pclusterTagsAndBudget",
                ],
                "slurm_accounting_create_db": ["USESETVALUE", "", "true"],
                "slurm_accounting_enabled": ["USESETVALUE", "", "true"],
            },
        )

        assert records["rc"] == EXIT_SUCCESS
        assert calls
        assert calls[0]["vpc_id"] == "vpc-explicit-priv"
        assert calls[0]["private_subnet_id"] == "subnet-explicit-priv"
        assert calls[0]["assign_public_ip"] is True

    def test_explicit_network_and_policy_config_skip_baseline_stack(self, tmp_path, monkeypatch):
        records = _run_stubbed_create_workflow(
            tmp_path,
            monkeypatch,
            interactive=False,
            head_node_ip="54.1.2.3",
            say_available=False,
            config_overrides={
                "public_subnet_id": ["USESETVALUE", "", "subnet-explicit-pub"],
                "private_subnet_id": ["USESETVALUE", "", "subnet-explicit-priv"],
                "iam_policy_arn": [
                    "USESETVALUE",
                    "",
                    "arn:aws:iam::123456789012:policy/pclusterTagsAndBudget",
                ],
            },
        )

        assert records["rc"] == EXIT_SUCCESS
        assert records["baseline_stack_calls"] == 0
        assert (
            "Subnets",
            "pub=subnet-explicit-pub  priv=subnet-explicit-priv",
        ) in records["details"]
        assert (
            "Policy",
            "arn:aws:iam::123456789012:policy/pclusterTagsAndBudget",
        ) in records["details"]


# ── configure_headnode ───────────────────────────────────────────────


class TestConfigureHeadnode:
    @patch("daylily_ec.workflow.create_cluster.validate_headnode_readiness")
    @patch("daylily_ec.aws.ssm.write_remote_text")
    @patch("daylily_ec.aws.ssm.run_shell")
    def test_success_path(
        self,
        mock_run_shell,
        mock_write_remote_text,
        mock_validate_headnode_readiness,
        tmp_path,
        monkeypatch,
    ):
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("DAYLILY_EC_REPO_ROOT", raising=False)

        mock_run_shell.side_effect = [
            SimpleNamespace(stdout="", stderr=""),
            SimpleNamespace(stdout="", stderr=""),
            SimpleNamespace(stdout="", stderr=""),
            SimpleNamespace(stdout="", stderr=""),
        ]
        mock_validate_headnode_readiness.return_value = SimpleNamespace(command_id="cmd-ready")

        ok = configure_headnode(
            cluster_name="test-cluster",
            head_node_instance_id="i-abc123",
            region="us-west-2",
            profile="test",
        )
        assert ok is True
        assert mock_run_shell.call_count == 4
        assert [call.kwargs["timeout"] for call in mock_run_shell.call_args_list] == [
            None,
            None,
            None,
            None,
        ]
        assert [call.kwargs["as_user"] for call in mock_run_shell.call_args_list] == [
            "ubuntu",
            "ubuntu",
            "ubuntu",
            "ubuntu",
        ]
        tos_cmd = mock_run_shell.call_args_list[2].args[2]
        assert "conda tos accept --override-channels" in tos_cmd
        assert "https://repo.anaconda.com/pkgs/main" in tos_cmd
        assert "https://repo.anaconda.com/pkgs/r" in tos_cmd
        assert (
            "source ~/projects/daylily-ephemeral-cluster/activate"
            in mock_run_shell.call_args_list[3].args[2]
        )
        mock_validate_headnode_readiness.assert_called_once_with(
            "i-abc123",
            "us-west-2",
            profile="test",
            timeout=120,
            comment="Validate DAY-EC headnode readiness",
            repo_name="daylily-ephemeral-cluster",
            remote_user="ubuntu",
        )
        mock_write_remote_text.assert_not_called()

    @patch("daylily_ec.workflow.create_cluster.validate_headnode_readiness")
    @patch("daylily_ec.aws.ssm.write_remote_text")
    @patch("daylily_ec.aws.ssm.run_shell")
    def test_writes_only_deploy_key_reference_to_headnode(
        self,
        mock_run_shell,
        mock_write_remote_text,
        mock_validate_headnode_readiness,
        tmp_path,
        monkeypatch,
    ):
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("DAYLILY_EC_REPO_ROOT", raising=False)
        mock_run_shell.return_value = SimpleNamespace(stdout="", stderr="")
        mock_validate_headnode_readiness.return_value = SimpleNamespace(command_id="cmd-ready")
        secret_arn = (
            "arn:aws:secretsmanager:us-west-2:123456789012:secret:dayec/github-deploy-keys/dayoa"
        )

        ok = configure_headnode(
            cluster_name="test-cluster",
            head_node_instance_id="i-abc123",
            region="us-west-2",
            profile="test",
            dayoa_deploy_key_secret_arn=secret_arn,
            dayoa_deploy_key_region="us-west-2",
        )

        assert ok is True
        mock_write_remote_text.assert_called_once()
        args = mock_write_remote_text.call_args.args
        assert args[2] == "~/.config/daylily/github_deploy_keys.yaml"
        payload = yaml.safe_load(args[3])
        assert payload == {
            "config_version": 1,
            "deploy_keys": {
                "daylily-omics-analysis": {
                    "region": "us-west-2",
                    "secret_arn": secret_arn,
                }
            },
        }
        assert "PRIVATE KEY" not in args[3]

    @patch("daylily_ec.workflow.create_cluster.validate_headnode_readiness")
    @patch("daylily_ec.aws.ssm.write_remote_text")
    @patch("daylily_ec.aws.ssm.run_shell")
    def test_dyec_deploy_key_bootstraps_exact_private_repo_without_persisting_key(
        self,
        mock_run_shell,
        mock_write_remote_text,
        mock_validate_headnode_readiness,
        tmp_path,
        monkeypatch,
    ):
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("DAYLILY_EC_REPO_ROOT", raising=False)
        mock_run_shell.return_value = SimpleNamespace(stdout="", stderr="")
        mock_validate_headnode_readiness.return_value = SimpleNamespace(command_id="cmd-ready")
        dyec_secret_arn = (
            "arn:aws:secretsmanager:us-west-2:123456789012:" "secret:dayec/github-deploy-keys/dyec"
        )
        dayoa_secret_arn = (
            "arn:aws:secretsmanager:us-west-2:123456789012:" "secret:dayec/github-deploy-keys/dayoa"
        )

        ok = configure_headnode(
            cluster_name="test-cluster",
            head_node_instance_id="i-abc123",
            region="us-west-2",
            profile="test",
            dyec_deploy_key_secret_arn=dyec_secret_arn,
            dyec_deploy_key_region="us-west-2",
            dyec_repo_url="git@github.com:lsmc-bio/daylily-ephemeral-cluster.git",
            dyec_repo_ref="feature/any-published-branch",
            dayoa_deploy_key_secret_arn=dayoa_secret_arn,
            dayoa_deploy_key_region="us-west-2",
        )

        assert ok is True
        assert mock_write_remote_text.call_count == 2
        known_hosts_call, references_call = mock_write_remote_text.call_args_list
        assert known_hosts_call.args[2] == "~/.config/daylily/github_known_hosts"
        assert "github.com ssh-ed25519" in known_hosts_call.args[3]
        assert references_call.args[2] == "~/.config/daylily/github_deploy_keys.yaml"
        assert yaml.safe_load(references_call.args[3]) == {
            "config_version": 1,
            "deploy_keys": {
                "daylily-ephemeral-cluster": {
                    "region": "us-west-2",
                    "secret_arn": dyec_secret_arn,
                },
                "daylily-omics-analysis": {
                    "region": "us-west-2",
                    "secret_arn": dayoa_secret_arn,
                },
            },
        }
        clone_cmd = mock_run_shell.call_args_list[0].args[2]
        assert (
            "git clone git@github.com:lsmc-bio/daylily-ephemeral-cluster.git "
            "daylily-ephemeral-cluster"
        ) in clone_cmd
        assert "origin/feature/any-published-branch" in clone_cmd
        assert dyec_secret_arn in clone_cmd
        assert "StrictHostKeyChecking=yes" in clone_cmd
        assert "IdentitiesOnly=yes" in clone_cmd
        assert "mktemp -d" in clone_cmd
        assert "trap 'rm -rf" in clone_cmd
        assert "--query SecretString --output text" in clone_cmd
        assert 'ssh-keygen -y -f "$dayec_key_dir/deploy_key" >/dev/null' in clone_cmd
        assert "tail -n 1" not in clone_cmd

    @patch("daylily_ec.workflow.create_cluster.validate_headnode_readiness")
    @patch("daylily_ec.aws.ssm.write_remote_text")
    @patch("daylily_ec.aws.ssm.run_shell")
    def test_can_configure_headnode_as_ec2_user(
        self,
        mock_run_shell,
        mock_write_remote_text,
        mock_validate_headnode_readiness,
        tmp_path,
        monkeypatch,
    ):
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("DAYLILY_EC_REPO_ROOT", raising=False)

        mock_run_shell.side_effect = [
            SimpleNamespace(stdout="", stderr=""),
            SimpleNamespace(stdout="", stderr=""),
            SimpleNamespace(stdout="", stderr=""),
            SimpleNamespace(stdout="", stderr=""),
        ]
        mock_validate_headnode_readiness.return_value = SimpleNamespace(command_id="cmd-ready")

        ok = configure_headnode(
            cluster_name="dragen-cluster",
            head_node_instance_id="i-drg123",
            region="us-west-2",
            profile="test",
            remote_user="ec2-user",
        )

        assert ok is True
        assert [call.kwargs["as_user"] for call in mock_run_shell.call_args_list] == [
            "ec2-user",
            "ec2-user",
            "ec2-user",
            "ec2-user",
        ]
        mock_validate_headnode_readiness.assert_called_once_with(
            "i-drg123",
            "us-west-2",
            profile="test",
            timeout=120,
            comment="Validate DAY-EC headnode readiness",
            repo_name="daylily-ephemeral-cluster",
            remote_user="ec2-user",
        )
        mock_write_remote_text.assert_not_called()

    @patch("daylily_ec.workflow.create_cluster.validate_headnode_readiness")
    @patch("daylily_ec.aws.ssm.write_remote_text")
    @patch("daylily_ec.aws.ssm.run_shell")
    def test_login_shell_validation_failure_is_fatal(
        self,
        mock_run_shell,
        mock_write_remote_text,
        mock_validate_headnode_readiness,
        tmp_path,
        monkeypatch,
    ):
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("DAYLILY_EC_REPO_ROOT", raising=False)

        mock_run_shell.side_effect = [
            SimpleNamespace(stdout="", stderr=""),
            SimpleNamespace(stdout="", stderr=""),
            SimpleNamespace(stdout="", stderr=""),
            SimpleNamespace(stdout="", stderr=""),
        ]
        mock_validate_headnode_readiness.side_effect = SsmCommandFailedError(
            "validation failed",
            SsmCommandResult(
                command_id="cmd-1",
                instance_id="i-abc123",
                status="Failed",
                response_code=1,
                stdout="",
                stderr="CONDA_DEFAULT_ENV not DAY-EC",
            ),
        )

        ok = configure_headnode(
            cluster_name="test-cluster",
            head_node_instance_id="i-abc123",
            region="us-west-2",
            profile="test",
        )
        assert ok is False
        assert mock_run_shell.call_count == 4
        mock_validate_headnode_readiness.assert_called_once()
        mock_write_remote_text.assert_not_called()

    @patch("daylily_ec.workflow.create_cluster.validate_headnode_readiness")
    @patch("daylily_ec.aws.ssm.write_remote_text")
    @patch("daylily_ec.aws.ssm.run_shell")
    def test_conda_tos_acceptance_failure_is_fatal(
        self,
        mock_run_shell,
        mock_write_remote_text,
        mock_validate_headnode_readiness,
        tmp_path,
        monkeypatch,
    ):
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("DAYLILY_EC_REPO_ROOT", raising=False)

        mock_run_shell.side_effect = [
            SimpleNamespace(stdout="", stderr=""),
            SimpleNamespace(stdout="", stderr=""),
            SsmCommandFailedError(
                "tos failed",
                SsmCommandResult(
                    command_id="cmd-1",
                    instance_id="i-abc123",
                    status="Failed",
                    response_code=1,
                    stdout="",
                    stderr="CondaToSNonInteractiveError",
                ),
            ),
        ]

        ok = configure_headnode(
            cluster_name="test-cluster",
            head_node_instance_id="i-abc123",
            region="us-west-2",
            profile="test",
        )
        assert ok is False
        assert mock_run_shell.call_count == 3
        mock_validate_headnode_readiness.assert_not_called()
        mock_write_remote_text.assert_not_called()

    @patch("daylily_ec.workflow.create_cluster.validate_headnode_readiness")
    @patch("daylily_ec.aws.ssm.write_remote_text")
    @patch("daylily_ec.aws.ssm.run_shell")
    def test_step_failure_is_fatal(
        self,
        mock_run_shell,
        mock_write_remote_text,
        mock_validate_headnode_readiness,
        tmp_path,
        monkeypatch,
    ):
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("DAYLILY_EC_REPO_ROOT", raising=False)

        mock_run_shell.side_effect = RuntimeError("boom")

        ok = configure_headnode(
            cluster_name="test-cluster",
            head_node_instance_id="i-abc123",
            region="us-west-2",
            profile="test",
        )
        assert ok is False
        mock_validate_headnode_readiness.assert_not_called()
        mock_write_remote_text.assert_not_called()

    @patch("daylily_ec.workflow.create_cluster.validate_headnode_readiness")
    @patch("daylily_ec.aws.ssm.write_remote_text")
    @patch("daylily_ec.aws.ssm.run_shell")
    def test_repo_override_deployment_uses_remote_write(
        self,
        mock_run_shell,
        mock_write_remote_text,
        mock_validate_headnode_readiness,
        tmp_path,
        monkeypatch,
    ):
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("DAYLILY_EC_REPO_ROOT", raising=False)

        mock_run_shell.side_effect = [
            SimpleNamespace(stdout="", stderr=""),
            SimpleNamespace(stdout="", stderr=""),
            SimpleNamespace(stdout="", stderr=""),
            SimpleNamespace(stdout="", stderr=""),
        ]
        mock_validate_headnode_readiness.return_value = SimpleNamespace(command_id="cmd-ready")

        ok = configure_headnode(
            cluster_name="test-cluster",
            head_node_instance_id="i-abc123",
            region="us-west-2",
            profile="test",
            repo_overrides={"daylily-omics-analysis": "feature/refactor"},
        )
        assert ok is True
        assert mock_run_shell.call_count == 4
        mock_write_remote_text.assert_called_once()
        mock_validate_headnode_readiness.assert_called_once()

    @patch("daylily_ec.workflow.create_cluster.validate_headnode_readiness")
    @patch("daylily_ec.aws.ssm.write_remote_text", side_effect=RuntimeError("nope"))
    @patch("daylily_ec.aws.ssm.run_shell")
    def test_repo_override_write_failure_is_fatal(
        self,
        mock_run_shell,
        _mock_write_remote_text,
        mock_validate_headnode_readiness,
        tmp_path,
        monkeypatch,
    ):
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("DAYLILY_EC_REPO_ROOT", raising=False)

        mock_run_shell.side_effect = [
            SimpleNamespace(stdout="", stderr=""),
            SimpleNamespace(stdout="", stderr=""),
            SimpleNamespace(stdout="", stderr=""),
            SimpleNamespace(stdout="", stderr=""),
        ]

        ok = configure_headnode(
            cluster_name="test-cluster",
            head_node_instance_id="i-abc123",
            region="us-west-2",
            profile="test",
            repo_overrides={"daylily-omics-analysis": "feature/refactor"},
        )
        assert ok is False
        mock_validate_headnode_readiness.assert_not_called()

    @patch("daylily_ec.workflow.create_cluster.validate_headnode_readiness")
    @patch("daylily_ec.aws.ssm.write_remote_text")
    @patch("daylily_ec.aws.ssm.run_shell")
    def test_repo_override_requires_available_repo_config(
        self,
        mock_run_shell,
        mock_write_remote_text,
        mock_validate_headnode_readiness,
        tmp_path,
        monkeypatch,
    ):
        import daylily_ec.resources as resources_module

        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("DAYLILY_EC_REPO_ROOT", raising=False)
        (tmp_path / "config").mkdir()
        (tmp_path / "config" / "daylily_cli_global.yaml").write_text(
            "daylily: {}\n", encoding="utf-8"
        )
        monkeypatch.setattr(
            resources_module,
            "resource_path",
            lambda _rel: tmp_path / "missing_available_repositories.yaml",
        )

        mock_run_shell.side_effect = [
            SimpleNamespace(stdout="", stderr=""),
            SimpleNamespace(stdout="", stderr=""),
            SimpleNamespace(stdout="", stderr=""),
            SimpleNamespace(stdout="", stderr=""),
        ]

        ok = configure_headnode(
            cluster_name="test-cluster",
            head_node_instance_id="i-abc123",
            region="us-west-2",
            profile="test",
            repo_overrides={"daylily-omics-analysis": "feature/refactor"},
        )
        assert ok is False
        mock_validate_headnode_readiness.assert_not_called()
        mock_write_remote_text.assert_not_called()

    @patch("daylily_ec.workflow.create_cluster.validate_headnode_readiness")
    @patch("daylily_ec.aws.ssm.write_remote_text")
    @patch("daylily_ec.aws.ssm.run_shell")
    def test_repo_override_rejects_unknown_repository_key(
        self,
        mock_run_shell,
        mock_write_remote_text,
        mock_validate_headnode_readiness,
        tmp_path,
        monkeypatch,
    ):
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("DAYLILY_EC_REPO_ROOT", raising=False)

        mock_run_shell.side_effect = [
            SimpleNamespace(stdout="", stderr=""),
            SimpleNamespace(stdout="", stderr=""),
            SimpleNamespace(stdout="", stderr=""),
            SimpleNamespace(stdout="", stderr=""),
        ]

        ok = configure_headnode(
            cluster_name="test-cluster",
            head_node_instance_id="i-abc123",
            region="us-west-2",
            profile="test",
            repo_overrides={"unknown-repository": "feature/refactor"},
        )

        assert ok is False
        mock_write_remote_text.assert_not_called()
        mock_validate_headnode_readiness.assert_not_called()

    @patch("daylily_ec.workflow.create_cluster.validate_headnode_readiness")
    @patch("daylily_ec.aws.ssm.write_remote_text")
    @patch("daylily_ec.aws.ssm.run_shell")
    @patch("daylily_ec.workflow.create_cluster.subprocess.run")
    def test_repo_checkout_uses_local_branch_and_refreshes_remote_checkout(
        self,
        mock_subprocess_run,
        mock_run_shell,
        mock_write_remote_text,
        mock_validate_headnode_readiness,
        tmp_path,
        monkeypatch,
    ):
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.chdir(tmp_path)
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        monkeypatch.setenv("DAYLILY_EC_REPO_ROOT", str(repo_root))

        def fake_git_run(cmd, **_kwargs):
            if cmd == ["git", "-C", str(repo_root), "config", "--get", "remote.origin.url"]:
                return subprocess.CompletedProcess(cmd, 0, "https://example.com/daylily.git\n", "")
            if cmd == ["git", "-C", str(repo_root), "symbolic-ref", "--short", "HEAD"]:
                return subprocess.CompletedProcess(cmd, 0, "codex/ssh-to-ssm-refactor\n", "")
            if cmd == [
                "git",
                "-C",
                str(repo_root),
                "ls-remote",
                "--exit-code",
                "--heads",
                "origin",
                "codex/ssh-to-ssm-refactor",
            ]:
                return subprocess.CompletedProcess(
                    cmd,
                    0,
                    "abc\trefs/heads/codex/ssh-to-ssm-refactor\n",
                    "",
                )
            raise AssertionError(f"unexpected subprocess.run call: {cmd}")

        mock_subprocess_run.side_effect = fake_git_run
        mock_run_shell.side_effect = [
            SimpleNamespace(stdout="", stderr=""),
            SimpleNamespace(stdout="", stderr=""),
            SimpleNamespace(stdout="", stderr=""),
            SimpleNamespace(stdout="", stderr=""),
        ]
        mock_validate_headnode_readiness.return_value = SimpleNamespace(command_id="cmd-ready")

        ok = configure_headnode(
            cluster_name="test-cluster",
            head_node_instance_id="i-abc123",
            region="us-west-2",
            profile="test",
        )

        assert ok is True
        assert mock_run_shell.call_count == 4
        clone_cmd = mock_run_shell.call_args_list[0].args[2]
        assert "repo already cloned" not in clone_cmd
        assert "git clone https://example.com/daylily.git daylily-ephemeral-cluster" in clone_cmd
        assert "git fetch origin --tags --prune" in clone_cmd
        assert "git clean -fdx" in clone_cmd
        assert "git checkout -B daylily-managed origin/codex/ssh-to-ssm-refactor" in clone_cmd
        mock_validate_headnode_readiness.assert_called_once()
        mock_write_remote_text.assert_not_called()

    @patch("daylily_ec.workflow.create_cluster.validate_headnode_readiness")
    @patch("daylily_ec.aws.ssm.write_remote_text")
    @patch("daylily_ec.aws.ssm.run_shell")
    @patch("daylily_ec.workflow.create_cluster.subprocess.run")
    def test_repo_checkout_uses_published_detached_tag(
        self,
        mock_subprocess_run,
        mock_run_shell,
        mock_write_remote_text,
        mock_validate_headnode_readiness,
        tmp_path,
        monkeypatch,
    ):
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.chdir(tmp_path)
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        monkeypatch.setenv("DAYLILY_EC_REPO_ROOT", str(repo_root))

        def fake_git_run(cmd, **_kwargs):
            if cmd == ["git", "-C", str(repo_root), "config", "--get", "remote.origin.url"]:
                return subprocess.CompletedProcess(cmd, 0, "https://example.com/daylily.git\n", "")
            if cmd == ["git", "-C", str(repo_root), "symbolic-ref", "--short", "HEAD"]:
                return subprocess.CompletedProcess(
                    cmd,
                    1,
                    "",
                    "fatal: ref HEAD is not a symbolic ref\n",
                )
            if cmd == ["git", "-C", str(repo_root), "rev-parse", "--short=12", "HEAD"]:
                return subprocess.CompletedProcess(cmd, 0, "4f076d77359f\n", "")
            if cmd == ["git", "-C", str(repo_root), "tag", "--points-at", "HEAD"]:
                return subprocess.CompletedProcess(cmd, 0, "5.1.30\n", "")
            if cmd == [
                "git",
                "-C",
                str(repo_root),
                "ls-remote",
                "--exit-code",
                "--tags",
                "origin",
                "refs/tags/5.1.30",
            ]:
                return subprocess.CompletedProcess(cmd, 0, "abc\trefs/tags/5.1.30\n", "")
            raise AssertionError(f"unexpected subprocess.run call: {cmd}")

        mock_subprocess_run.side_effect = fake_git_run
        mock_run_shell.side_effect = [
            SimpleNamespace(stdout="", stderr=""),
            SimpleNamespace(stdout="", stderr=""),
            SimpleNamespace(stdout="", stderr=""),
            SimpleNamespace(stdout="", stderr=""),
        ]
        mock_validate_headnode_readiness.return_value = SimpleNamespace(command_id="cmd-ready")

        ok = configure_headnode(
            cluster_name="test-cluster",
            head_node_instance_id="i-abc123",
            region="us-west-2",
            profile="test",
        )

        assert ok is True
        clone_cmd = mock_run_shell.call_args_list[0].args[2]
        assert "git checkout --detach refs/tags/5.1.30" in clone_cmd
        assert "git checkout -B daylily-managed" not in clone_cmd
        mock_validate_headnode_readiness.assert_called_once()
        mock_write_remote_text.assert_not_called()

    @patch("daylily_ec.aws.ssm.write_remote_text")
    @patch("daylily_ec.aws.ssm.run_shell")
    @patch("daylily_ec.workflow.create_cluster.subprocess.run")
    def test_repo_checkout_detached_head_requires_exact_tag(
        self,
        mock_subprocess_run,
        mock_run_shell,
        mock_write_remote_text,
        tmp_path,
        monkeypatch,
    ):
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.chdir(tmp_path)
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        monkeypatch.setenv("DAYLILY_EC_REPO_ROOT", str(repo_root))

        def fake_git_run(cmd, **_kwargs):
            if cmd == ["git", "-C", str(repo_root), "config", "--get", "remote.origin.url"]:
                return subprocess.CompletedProcess(cmd, 0, "https://example.com/daylily.git\n", "")
            if cmd == ["git", "-C", str(repo_root), "symbolic-ref", "--short", "HEAD"]:
                return subprocess.CompletedProcess(
                    cmd,
                    1,
                    "",
                    "fatal: ref HEAD is not a symbolic ref\n",
                )
            if cmd == ["git", "-C", str(repo_root), "rev-parse", "--short=12", "HEAD"]:
                return subprocess.CompletedProcess(cmd, 0, "4f076d77359f\n", "")
            if cmd == ["git", "-C", str(repo_root), "tag", "--points-at", "HEAD"]:
                return subprocess.CompletedProcess(cmd, 0, "", "")
            raise AssertionError(f"unexpected subprocess.run call: {cmd}")

        mock_subprocess_run.side_effect = fake_git_run

        ok = configure_headnode(
            cluster_name="test-cluster",
            head_node_instance_id="i-abc123",
            region="us-west-2",
            profile="test",
        )

        assert ok is False
        mock_run_shell.assert_not_called()
        mock_write_remote_text.assert_not_called()

    @patch("daylily_ec.workflow.create_cluster.validate_headnode_readiness")
    @patch("daylily_ec.aws.ssm.write_remote_text")
    @patch("daylily_ec.aws.ssm.run_shell")
    @patch("daylily_ec.workflow.create_cluster.subprocess.run")
    @pytest.mark.parametrize(
        ("origin_url", "expected_url"),
        [
            (
                "git@github.com:lsmc-bio/daylily-ephemeral-cluster.git\n",
                "https://github.com/lsmc-bio/daylily-ephemeral-cluster.git",
            ),
            (
                "ssh://git@github.com/lsmc-bio/daylily-ephemeral-cluster.git\n",
                "https://github.com/lsmc-bio/daylily-ephemeral-cluster.git",
            ),
        ],
    )
    def test_repo_checkout_normalizes_github_ssh_origin_for_headnode_clone(
        self,
        mock_subprocess_run,
        mock_run_shell,
        mock_write_remote_text,
        mock_validate_headnode_readiness,
        origin_url,
        expected_url,
        tmp_path,
        monkeypatch,
    ):
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.chdir(tmp_path)
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        monkeypatch.setenv("DAYLILY_EC_REPO_ROOT", str(repo_root))

        def fake_git_run(cmd, **_kwargs):
            if cmd == ["git", "-C", str(repo_root), "config", "--get", "remote.origin.url"]:
                return subprocess.CompletedProcess(cmd, 0, origin_url, "")
            if cmd == ["git", "-C", str(repo_root), "symbolic-ref", "--short", "HEAD"]:
                return subprocess.CompletedProcess(cmd, 0, "codex/https-headnode-clone\n", "")
            if cmd == [
                "git",
                "-C",
                str(repo_root),
                "ls-remote",
                "--exit-code",
                "--heads",
                "origin",
                "codex/https-headnode-clone",
            ]:
                return subprocess.CompletedProcess(
                    cmd,
                    0,
                    "abc\trefs/heads/codex/https-headnode-clone\n",
                    "",
                )
            raise AssertionError(f"unexpected subprocess.run call: {cmd}")

        mock_subprocess_run.side_effect = fake_git_run
        mock_run_shell.side_effect = [
            SimpleNamespace(stdout="", stderr=""),
            SimpleNamespace(stdout="", stderr=""),
            SimpleNamespace(stdout="", stderr=""),
            SimpleNamespace(stdout="", stderr=""),
        ]
        mock_validate_headnode_readiness.return_value = SimpleNamespace(command_id="cmd-ready")

        ok = configure_headnode(
            cluster_name="test-cluster",
            head_node_instance_id="i-abc123",
            region="us-west-2",
            profile="test",
        )

        assert ok is True
        clone_cmd = mock_run_shell.call_args_list[0].args[2]
        assert f"git clone {expected_url} daylily-ephemeral-cluster" in clone_cmd
        assert "git@github.com" not in clone_cmd
        assert "ssh://git@github.com" not in clone_cmd
        mock_validate_headnode_readiness.assert_called_once()
        mock_write_remote_text.assert_not_called()

    @patch("daylily_ec.aws.ssm.write_remote_text")
    @patch("daylily_ec.aws.ssm.run_shell")
    @patch("daylily_ec.workflow.create_cluster.subprocess.run")
    def test_repo_checkout_rejects_unsupported_ssh_origin_for_headnode_clone(
        self,
        mock_subprocess_run,
        mock_run_shell,
        mock_write_remote_text,
        tmp_path,
        monkeypatch,
    ):
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.chdir(tmp_path)
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        monkeypatch.setenv("DAYLILY_EC_REPO_ROOT", str(repo_root))

        def fake_git_run(cmd, **_kwargs):
            if cmd == ["git", "-C", str(repo_root), "config", "--get", "remote.origin.url"]:
                return subprocess.CompletedProcess(
                    cmd, 0, "git@gitlab.example.com:org/repo.git\n", ""
                )
            raise AssertionError(f"unexpected subprocess.run call: {cmd}")

        mock_subprocess_run.side_effect = fake_git_run

        ok = configure_headnode(
            cluster_name="test-cluster",
            head_node_instance_id="i-abc123",
            region="us-west-2",
            profile="test",
        )

        assert ok is False
        mock_run_shell.assert_not_called()
        mock_write_remote_text.assert_not_called()

    @patch("daylily_ec.aws.ssm.write_remote_text")
    @patch("daylily_ec.aws.ssm.run_shell")
    @patch("daylily_ec.workflow.create_cluster.subprocess.run")
    def test_repo_checkout_branch_must_be_published(
        self,
        mock_subprocess_run,
        mock_run_shell,
        mock_write_remote_text,
        tmp_path,
        monkeypatch,
    ):
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.chdir(tmp_path)
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        monkeypatch.setenv("DAYLILY_EC_REPO_ROOT", str(repo_root))

        def fake_git_run(cmd, **_kwargs):
            if cmd == ["git", "-C", str(repo_root), "config", "--get", "remote.origin.url"]:
                return subprocess.CompletedProcess(cmd, 0, "https://example.com/daylily.git\n", "")
            if cmd == ["git", "-C", str(repo_root), "symbolic-ref", "--short", "HEAD"]:
                return subprocess.CompletedProcess(cmd, 0, "feature/local-only\n", "")
            if cmd == [
                "git",
                "-C",
                str(repo_root),
                "ls-remote",
                "--exit-code",
                "--heads",
                "origin",
                "feature/local-only",
            ]:
                return subprocess.CompletedProcess(cmd, 2, "", "fatal: not found")
            raise AssertionError(f"unexpected subprocess.run call: {cmd}")

        mock_subprocess_run.side_effect = fake_git_run

        ok = configure_headnode(
            cluster_name="test-cluster",
            head_node_instance_id="i-abc123",
            region="us-west-2",
            profile="test",
        )

        assert ok is False
        mock_run_shell.assert_not_called()
        mock_write_remote_text.assert_not_called()


# ── configure_headnode export ────────────────────────────────────────


class TestConfigureHeadnodeExport:
    def test_exported_from_workflow(self):
        import daylily_ec.workflow as wf

        assert hasattr(wf, "configure_headnode")


def _build_workflow_config(
    template_path: Path,
    *,
    config_overrides: dict[str, list[str]] | None = None,
) -> ConfigFile:
    config = {
        "cluster_name": ["USESETVALUE", "", "majors-cluster"],
        "reference_s3_uri": ["USESETVALUE", "", "s3://dayoa-references"],
        "control_data_s3_uri": ["USESETVALUE", "", "s3://dayoa-control-data"],
        "stage_s3_uri": [
            "USESETVALUE",
            "",
            "s3://lsmc-ssf-sequencing-data/staged_external_data/",
        ],
        "export_destination_s3_uri": [
            "USESETVALUE",
            "",
            "s3://lsmc-ssf-sequencing-data/derived/",
        ],
        "max_count_8I": ["USESETVALUE", "", "1"],
        "max_count_96I_NVME": ["USESETVALUE", "", "1"],
        "max_count_128I": ["USESETVALUE", "", "1"],
        "max_count_192I": ["USESETVALUE", "", "1"],
        "max_count_384I": ["USESETVALUE", "", "1"],
        "cluster_template_yaml": ["USESETVALUE", "", str(template_path)],
        "fsx_fs_size": ["USESETVALUE", "", "2400"],
        "enable_detailed_monitoring": ["USESETVALUE", "", "false"],
        "delete_local_root": ["USESETVALUE", "", "false"],
        "auto_delete_fsx": ["USESETVALUE", "", "Delete"],
        "enforce_budget": ["USESETVALUE", "", "true"],
        "spot_instance_allocation_strategy": [
            "USESETVALUE",
            "",
            "capacity-optimized",
        ],
        "headnode_instance_type": ["USESETVALUE", "", "r7i.2xlarge"],
        "budget_email": ["PROMPTUSER", "johnm@lsmc.com", ""],
        "budget_amount": ["PROMPTUSER", "200", ""],
        "global_budget_amount": ["PROMPTUSER", "200", ""],
        "allowed_budget_users": ["PROMPTUSER", "root", ""],
        "heartbeat_email": ["PROMPTUSER", "johnm@lsmc.com", ""],
        "heartbeat_schedule": ["PROMPTUSER", "rate(60 minutes)", ""],
        "heartbeat_scheduler_role_arn": ["PROMPTUSER", "", ""],
        "slurm_accounting_enabled": ["USESETVALUE", "", "false"],
        "slurm_accounting_create_db": ["USESETVALUE", "", "false"],
        "dyec_deploy_key_secret_arn": [
            "USESETVALUE",
            "",
            "arn:aws:secretsmanager:us-west-2:123456789012:secret:dayec/dyec-key",
        ],
        "dyec_deploy_key_policy_arn": [
            "USESETVALUE",
            "",
            "arn:aws:iam::123456789012:policy/DayECHeadnodeDYECClone",
        ],
        "dayoa_deploy_key_secret_arn": [
            "USESETVALUE",
            "",
            "arn:aws:secretsmanager:us-west-2:123456789012:secret:dayec/dayoa-key",
        ],
        "dayoa_deploy_key_policy_arn": [
            "USESETVALUE",
            "",
            "arn:aws:iam::123456789012:policy/DayECHeadnodeDayOAClone",
        ],
    }
    if config_overrides:
        config.update(config_overrides)
    return ConfigFile.model_validate(
        {
            "ephemeral_cluster": {
                "config": config,
                "template_defaults": {},
            }
        }
    )


def _run_stubbed_create_workflow(
    tmp_path: Path,
    monkeypatch,
    *,
    interactive: bool,
    head_node_ip: str | None,
    say_available: bool,
    scan_slurm_accounting_db: bool = False,
    scan_candidates: list[object] | None = None,
    selection_answer: str = "1",
    config_overrides: dict[str, list[str]] | None = None,
    run_kwargs: dict[str, object] | None = None,
    regional_clusters: list[dict[str, str]] | None = None,
    regional_cluster_list_result: object | None = None,
) -> dict[str, object]:
    template_path = tmp_path / "template.yaml"
    template_path.write_text("Region: REGSUB_REGION\n", encoding="utf-8")

    records: dict[str, object] = {
        "events": [],
        "echoes": [],
        "prompt_labels": [],
        "subprocess_calls": [],
        "boot_config_publishes": [],
        "warnings": [],
        "details": [],
        "failures": [],
        "baseline_stack_calls": 0,
        "regional_cluster_list_calls": [],
    }
    config_dir = tmp_path / "daylily-config"
    config_dir.mkdir()
    records["config_dir"] = config_dir
    cfg = _build_workflow_config(template_path, config_overrides=config_overrides)

    class FakeAWSContext:
        profile = "lsmc"
        region = "us-west-2"
        account_id = "123456789012"
        iam_username = "root"
        caller_arn = "arn:aws:iam::123456789012:root"

        def __init__(self) -> None:
            class FakeSharedClient:
                def describe_subnets(self, SubnetIds):
                    subnet_id = SubnetIds[0]
                    vpc_id = (
                        "vpc-explicit-priv" if subnet_id == "subnet-explicit-priv" else "vpc-123"
                    )
                    return {
                        "Subnets": [
                            {
                                "SubnetId": subnet_id,
                                "AvailabilityZone": "us-west-2d",
                                "State": "available",
                                "VpcId": vpc_id,
                            }
                        ]
                    }

                def describe_route_tables(self, Filters):
                    _ = Filters
                    return {
                        "RouteTables": [
                            {
                                "Associations": [{"Main": True}],
                                "Routes": [
                                    {
                                        "DestinationCidrBlock": "0.0.0.0/0",
                                        "GatewayId": "igw-123",
                                        "State": "active",
                                    }
                                ],
                            }
                        ]
                    }

            shared_client = FakeSharedClient()
            self._clients = {
                "ec2": shared_client,
                "iam": shared_client,
                "budgets": shared_client,
                "s3": shared_client,
                "secretsmanager": shared_client,
                "sns": shared_client,
                "scheduler": shared_client,
            }

        def client(self, service_name: str):
            return self._clients[service_name]

    aws_ctx_instance = FakeAWSContext()

    def fake_build(_cls, region_az: str, profile: str | None = None):
        assert region_az == "us-west-2d"
        assert profile == "lsmc"
        return aws_ctx_instance

    def fake_prompt(label: str, default=None):
        _ = default
        records["prompt_labels"].append(label)
        records["events"].append(("prompt", label))
        answers = {
            "Budget email": "johnm@lsmc.com",
            "Budget amount": "200",
            "Global budget amount": "200",
            "Allowed budget users": "root",
            "DRAGEN PCluster AMI (leave blank to skip)": "",
            "Heartbeat email": "johnm@lsmc.com",
            "Heartbeat schedule": "rate(60 minutes)",
            "Heartbeat scheduler role ARN (leave blank to skip)": "",
            "Enter selection number": selection_answer,
        }
        return answers[label]

    def fake_run_preflight(report: PreflightReport, **_kwargs):
        report.checks.append(
            CheckResult(
                id="s3.role_config",
                status=CheckStatus.PASS,
                details={
                    "roles": {
                        "reference": {
                            "uri": "s3://dayoa-references",
                            "bucket": "dayoa-references",
                            "prefix": "",
                        },
                        "control_data": {
                            "uri": "s3://dayoa-control-data",
                            "bucket": "dayoa-control-data",
                            "prefix": "",
                        },
                        "staging": {
                            "uri": "s3://lsmc-ssf-sequencing-data/staged_external_data/",
                            "bucket": "lsmc-ssf-sequencing-data",
                            "prefix": "staged_external_data",
                        },
                        "export_destination": {
                            "uri": "s3://lsmc-ssf-sequencing-data/derived/",
                            "bucket": "lsmc-ssf-sequencing-data",
                            "prefix": "derived",
                        },
                    }
                },
            )
        )
        return report

    def fake_phase(title: str):
        records["events"].append(("phase", title))

    def fake_success_panel(title: str, body: str):
        records["events"].append(("success_panel", title))
        records["success_panel"] = (title, body)

    def fake_echo(message: str):
        records["echoes"].append(message)

    def fake_create_cluster(*_args, **_kwargs):
        records["events"].append(("create_cluster", None))
        return SimpleNamespace(success=True, returncode=0, stderr="", message="")

    def fake_resolve_scheduler_role(*_args, **kwargs):
        records["events"].append(("resolve_scheduler_role", None))
        records["resolve_scheduler_role_kwargs"] = kwargs
        return (
            "arn:aws:iam::123456789012:role/eventbridge-scheduler-to-sns",
            "existing_role:eventbridge-scheduler-to-sns",
        )

    def fake_ensure_global_budget(*_args, **kwargs):
        records["events"].append(("ensure_global_budget", None))
        records["global_budget_kwargs"] = kwargs
        return "daylily-global"

    def fake_ensure_cluster_budget(*_args, **kwargs):
        records["events"].append(("ensure_cluster_budget", None))
        records["cluster_budget_kwargs"] = kwargs
        return kwargs.get("cluster_name") or "majors-cluster"

    def fake_ensure_heartbeat(*_args, **kwargs):
        records["heartbeat_kwargs"] = kwargs
        return SimpleNamespace(
            success=True,
            topic_arn="arn:aws:sns:us-west-2:123456789012:daylily",
            schedule_name="daylily-majors-cluster-heartbeat",
            role_arn=kwargs["role_arn"],
        )

    def fake_write_next_run_template(_cfg, final_values, dest):
        records["next_run_values"] = dict(final_values)
        Path(dest).write_text("next-run\n", encoding="utf-8")
        return Path(dest)

    def fake_subprocess_run(cmd, **kwargs):
        _ = kwargs
        records["subprocess_calls"].append(list(cmd))
        if cmd == ["/bin/sh", "-lc", "command -v say >/dev/null 2>&1"]:
            return subprocess.CompletedProcess(
                args=cmd,
                returncode=0 if say_available else 1,
                stdout="",
                stderr="",
            )
        if cmd == ["say", "Onward to daylily!"]:
            return subprocess.CompletedProcess(
                args=cmd,
                returncode=0,
                stdout="",
                stderr="",
            )
        raise AssertionError(f"unexpected subprocess.run call: {cmd}")

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setenv("DAY_CONTACT_EMAIL", "johnm@lsmc.com")
    monkeypatch.setattr(renderer, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(aws_context.AWSContext, "build", classmethod(fake_build))
    monkeypatch.setattr(triplets, "load_config", lambda _path: cfg)
    monkeypatch.setattr(create_cluster_module, "run_preflight", fake_run_preflight)
    monkeypatch.setattr(
        create_cluster_module,
        "should_abort",
        lambda *_args, **_kwargs: False,
    )

    def fake_ensure_pcluster_env_stack(*_args, **_kwargs):
        records["baseline_stack_calls"] += 1
        return SimpleNamespace(
            public_subnet_id="subnet-pub",
            private_subnet_id="subnet-priv",
            policy_arn="arn:policy:default",
            vpc_id="vpc-123",
        )

    monkeypatch.setattr(
        cloudformation,
        "ensure_pcluster_env_stack",
        fake_ensure_pcluster_env_stack,
    )
    monkeypatch.setattr(cloudformation, "derive_stack_name", lambda _region_az: "daylily-stack")
    monkeypatch.setattr(aws_ec2, "list_public_subnets", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(aws_ec2, "list_private_subnets", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(
        aws_ec2,
        "list_pcluster_tags_budget_policies",
        lambda *_args, **_kwargs: [],
    )

    def fake_configure_headnode(**kwargs):
        records["configure_headnode_kwargs"] = kwargs
        return True

    monkeypatch.setattr(
        create_cluster_module,
        "configure_headnode",
        fake_configure_headnode,
    )
    monkeypatch.setattr(
        create_cluster_module,
        "resolve_configured_headnode_repo_spec",
        lambda *, deploy_key_auth: SimpleNamespace(
            url=(
                "git@github.com:lsmc-bio/daylily-ephemeral-cluster.git"
                if deploy_key_auth
                else "https://github.com/lsmc-bio/daylily-ephemeral-cluster.git"
            ),
            ref="sentieon-single",
        ),
    )

    def fake_write_init_artifacts(
        cluster_name: str,
        run_id: str,
        template_yaml: str,
        substitutions: dict[str, str],
    ):
        records["render_cluster_name"] = cluster_name
        records["render_run_id"] = run_id
        records["render_template_yaml"] = template_yaml
        records["render_substitutions"] = dict(substitutions)
        return (
            str(tmp_path / "cluster.yaml.init"),
            str(tmp_path / "init-template.yaml"),
        )

    monkeypatch.setattr(renderer, "write_init_artifacts", fake_write_init_artifacts)

    def fake_apply_spot_prices(_init_template_path, cluster_yaml_path, *_args, **_kwargs):
        Path(cluster_yaml_path).write_text(
            """
Region: us-west-2
HeadNode:
  CustomActions:
    OnNodeStart:
      Script: s3://boot-config/install_slurm_job_submit_policy.sh
      Args:
        - us-west-2
        - s3://boot-config
  Iam:
    AdditionalIamPolicies:
      - Policy: arn:policy:default
Scheduling:
  Scheduler: slurm
  SlurmSettings:
    EnableMemoryBasedScheduling: false
    CustomSlurmSettings:
      - JobSubmitPlugins: lua
      - AccountingStoreFlags: job_comment
      - PrologFlags: Alloc
  SlurmQueues:
    - Name: i128
      JobExclusiveAllocation: false
      ComputeResources:
        - Name: price128
SharedStorage:
  - Name: fsx
    StorageType: FsxLustre
    FsxLustreSettings:
      DataRepositoryAssociations:
        - Name: reference-data
          FileSystemPath: /references/
          DataRepositoryPath: s3://references/
""",
            encoding="utf-8",
        )
        return {
            "schema_version": "dyec.spot_price_summary.v1",
            "resources": [],
            "partitions": [
                {
                    "queue": "i128",
                    "min_instances": 0,
                    "max_instances": 1,
                    "raw_min_hourly_cost_without_limiter": 0.0,
                    "raw_max_hourly_cost_without_limiter": 0.0,
                    "max_reference_median_spot_price": 1.0,
                    "max_final_bid_usd_per_vcpu_hour": 0.0094,
                    "max_uncapped_pct_bid": 1.2,
                    "max_final_bid": 1.2,
                    "global_spot_max_cost": 7.5,
                    "write_spot_pricing_warn_threshold": 6.0,
                    "global_limiter_applied": False,
                    "warn_threshold_exceeded": False,
                    "reference_partitions": "i128",
                }
            ],
        }

    monkeypatch.setattr(spot_pricing, "apply_spot_prices", fake_apply_spot_prices)

    def fake_list_clusters(region: str, **kwargs):
        records["regional_cluster_list_calls"].append((region, kwargs))
        if regional_cluster_list_result is not None:
            return regional_cluster_list_result
        return SimpleNamespace(
            success=True,
            returncode=0,
            message="",
            json_body={"clusters": regional_clusters or []},
        )

    monkeypatch.setattr(pcluster_runner, "list_clusters", fake_list_clusters)
    monkeypatch.setattr(
        pcluster_runner,
        "dry_run_create",
        lambda *_args, **_kwargs: SimpleNamespace(success=True, message="", stderr=""),
    )
    monkeypatch.setattr(pcluster_runner, "should_break_after_dry_run", lambda: False)
    monkeypatch.setattr(pcluster_runner, "create_cluster", fake_create_cluster)
    monkeypatch.setattr(
        pcluster_monitor,
        "wait_for_creation",
        lambda *_args, **_kwargs: SimpleNamespace(
            success=True,
            elapsed_seconds=125.0,
            final_status="CREATE_COMPLETE",
            error="",
            head_node_ip=head_node_ip,
            head_node_instance_id="i-abc123",
        ),
    )
    import daylily_ec.aws.ssm as aws_ssm

    monkeypatch.setattr(aws_ssm, "wait_for_ssm_online", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(aws_iam, "resolve_scheduler_role", fake_resolve_scheduler_role)
    monkeypatch.setattr(aws_heartbeat, "ensure_heartbeat", fake_ensure_heartbeat)
    monkeypatch.setattr(
        aws_slurm_accounting,
        "scan_slurm_accounting_ec2_candidates",
        lambda *_args, **_kwargs: scan_candidates or [],
    )
    monkeypatch.setattr(create_cluster_module.ui, "phase", fake_phase)
    monkeypatch.setattr(create_cluster_module.ui, "step", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(create_cluster_module.ui, "ok", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        create_cluster_module.ui,
        "warn",
        lambda message, *_args, **_kwargs: records["warnings"].append(message),
    )
    monkeypatch.setattr(
        create_cluster_module.ui,
        "info",
        lambda message, *_args, **_kwargs: records.setdefault("infos", []).append(message),
    )
    monkeypatch.setattr(
        create_cluster_module.ui,
        "detail",
        lambda key, value, *_args, **_kwargs: records["details"].append((key, value)),
    )
    monkeypatch.setattr(
        create_cluster_module.ui,
        "fail",
        lambda message, *_args, **_kwargs: records["failures"].append(message),
    )
    monkeypatch.setattr(create_cluster_module.ui, "success_panel", fake_success_panel)
    monkeypatch.setattr(create_cluster_module.typer, "prompt", fake_prompt)
    monkeypatch.setattr(create_cluster_module.typer, "echo", fake_echo)
    monkeypatch.setattr(create_cluster_module.subprocess, "run", fake_subprocess_run)
    monkeypatch.setattr(triplets, "write_next_run_template", fake_write_next_run_template)
    monkeypatch.setattr(
        state_store,
        "write_state_record",
        lambda state: tmp_path / f"{state.cluster_name}.json",
    )
    monkeypatch.setattr(
        create_cluster_module,
        "write_state_record",
        lambda state: tmp_path / f"{state.cluster_name}.json",
    )
    monkeypatch.setattr(
        create_cluster_module,
        "_noop_heartbeat_result",
        lambda: SimpleNamespace(
            success=False,
            topic_arn="",
            schedule_name="",
            role_arn="",
            error="skipped",
        ),
    )
    monkeypatch.setattr(
        create_cluster_module,
        "publish_cluster_boot_config",
        lambda _s3_client, *, cluster_boot_s3_uri, source_dir: (
            records["boot_config_publishes"].append((cluster_boot_s3_uri, str(source_dir)))
            or [f"{cluster_boot_s3_uri}/post_install_ubuntu_combined.sh"]
        ),
    )

    import daylily_ec.aws.budgets as budgets

    monkeypatch.setattr(budgets, "ensure_global_budget", fake_ensure_global_budget)
    monkeypatch.setattr(budgets, "ensure_cluster_budget", fake_ensure_cluster_budget)

    records["rc"] = create_cluster_module.run_create_workflow(
        "us-west-2d",
        profile="lsmc",
        config_path=str(tmp_path / "config.yaml"),
        non_interactive=not interactive,
        scan_slurm_accounting_db=scan_slurm_accounting_db,
        **(run_kwargs or {}),
    )
    return records
