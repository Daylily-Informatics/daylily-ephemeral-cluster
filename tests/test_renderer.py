"""Tests for daylily_ec.render.renderer — CP-011."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from pcluster.schemas.cluster_schema import ClusterSchema

from daylily_ec.render.renderer import (
    ALL_SUBSTITUTION_KEYS,
    CONFIG_DIR,
    REQUIRED_KEYS,
    render_template,
    write_init_artifacts,
)
from daylily_ec.aws.slurm_accounting import (
    SlurmAccountingDb,
    empty_slurm_accounting_render_blocks,
    slurm_accounting_render_blocks,
)


# ── fixtures ─────────────────────────────────────────────────────────

MINI_TEMPLATE = (
    "Region: ${REGSUB_REGION}\n"
    "SubnetPublic: ${REGSUB_PUB_SUBNET}\n"
    "SubnetPrivate: ${REGSUB_PRIVATE_SUBNET}\n"
    "ClusterName: ${REGSUB_CLUSTER_NAME}\n"
)

MINIMAL_SUBS = {
    "REGSUB_REGION": "us-west-2",
    "REGSUB_PUB_SUBNET": "subnet-aaa",
    "REGSUB_PRIVATE_SUBNET": "subnet-bbb",
    "REGSUB_CLUSTER_NAME": "test-cluster",
}


def _full_subs() -> dict[str, str]:
    """Return a substitutions dict covering all known keys."""
    return {k: f"val-{k}" for k in ALL_SUBSTITUTION_KEYS}


# ── TestConstants ────────────────────────────────────────────────────


class TestConstants:
    def test_all_keys_count(self):
        assert len(ALL_SUBSTITUTION_KEYS) == 56

    def test_required_keys_subset(self):
        assert REQUIRED_KEYS.issubset(ALL_SUBSTITUTION_KEYS)

    def test_required_keys_count(self):
        assert len(REQUIRED_KEYS) == 4

    def test_config_dir_ends_with_daylily(self):
        assert CONFIG_DIR.name == "daylily"


# ── TestRenderTemplate ───────────────────────────────────────────────


class TestRenderTemplate:
    def test_basic_substitution(self):
        result = render_template(MINI_TEMPLATE, MINIMAL_SUBS)
        assert "us-west-2" in result
        assert "${REGSUB_REGION}" not in result

    def test_all_tokens_replaced(self):
        result = render_template(MINI_TEMPLATE, MINIMAL_SUBS)
        assert "${" not in result

    def test_preserves_non_token_text(self):
        result = render_template(MINI_TEMPLATE, MINIMAL_SUBS)
        assert result.startswith("Region: us-west-2\n")

    def test_missing_required_key_raises(self):
        subs = dict(MINIMAL_SUBS)
        del subs["REGSUB_REGION"]
        with pytest.raises(ValueError, match="REGSUB_REGION"):
            render_template(MINI_TEMPLATE, subs)

    def test_empty_required_key_raises(self):
        subs = dict(MINIMAL_SUBS)
        subs["REGSUB_REGION"] = ""
        with pytest.raises(ValueError, match="REGSUB_REGION"):
            render_template(MINI_TEMPLATE, subs)

    def test_custom_required_keys(self):
        # Only require REGSUB_REGION — should pass with just that
        subs = {"REGSUB_REGION": "eu-west-1"}
        result = render_template(
            "Region: ${REGSUB_REGION}\n",
            subs,
            required_keys=frozenset({"REGSUB_REGION"}),
        )
        assert result == "Region: eu-west-1\n"

    def test_no_required_keys(self):
        result = render_template(
            "Hello: ${REGSUB_REGION}\n",
            {},
            required_keys=frozenset(),
        )
        assert result == "Hello: ${REGSUB_REGION}\n"

    def test_extra_keys_ignored(self):
        subs = {**MINIMAL_SUBS, "REGSUB_EXTRA": "ignored"}
        result = render_template(MINI_TEMPLATE, subs)
        assert "ignored" not in result


# ── TestByteStability ────────────────────────────────────────────────


class TestByteStability:
    def test_identical_inputs_identical_output(self):
        a = render_template(MINI_TEMPLATE, MINIMAL_SUBS)
        b = render_template(MINI_TEMPLATE, MINIMAL_SUBS)
        assert a == b

    def test_full_subs_stable(self):
        tpl = "".join(f"{k}: ${{{k}}}\n" for k in sorted(ALL_SUBSTITUTION_KEYS))
        subs = _full_subs()
        a = render_template(tpl, subs, required_keys=frozenset())
        b = render_template(tpl, subs, required_keys=frozenset())
        assert a == b


# ── TestAllSubstitutionKeys ──────────────────────────────────────────


class TestAllSubstitutionKeys:
    def test_all_keys_substituted(self):
        tpl = "".join(f"k: ${{{k}}}\n" for k in sorted(ALL_SUBSTITUTION_KEYS))
        subs = _full_subs()
        result = render_template(tpl, subs, required_keys=frozenset())
        assert "${" not in result
        for k in ALL_SUBSTITUTION_KEYS:
            assert f"val-{k}" in result

    def test_known_keys_present(self):
        expected = {
            "REGSUB_REGION",
            "REGSUB_PUB_SUBNET",
            "REGSUB_KEYNAME",
            "REGSUB_S3_BUCKET_INIT",
            "REGSUB_S3_IAM_POLICY",
            "REGSUB_PRIVATE_SUBNET",
            "REGSUB_S3_REFERENCE_BUCKET",
            "REGSUB_S3_CONTROL_DATA_BUCKET",
            "REGSUB_S3_STAGE_BUCKET",
            "REGSUB_S3_EXPORT_BUCKET",
            "REGSUB_S3_REFERENCE_URI",
            "REGSUB_S3_CONTROL_DATA_URI",
            "REGSUB_S3_STAGE_URI",
            "REGSUB_FSX_SIZE",
            "REGSUB_DETAILED_MONITORING",
            "REGSUB_CLUSTER_NAME",
            "REGSUB_USERNAME",
            "REGSUB_PROJECT",
            "REGSUB_DELETE_LOCAL_ROOT",
            "REGSUB_DRAGEN_PCLUSTER_AMI",
            "REGSUB_DRAGEN_LICENSE_POLICY_ARN",
            "REGSUB_DRAGEN_LICENSE_SECRET_ARN",
            "REGSUB_PCLUSTER_COOKBOOK_URI",
            "REGSUB_SAVE_FSX",
            "REGSUB_ENFORCE_BUDGET",
            "REGSUB_COST_CENTER_REGION",
            "REGSUB_COST_CENTER_TABLE",
            "REGSUB_COST_CENTER_USAGE_TABLE",
            "REGSUB_AWS_ACCOUNT_ID",
            "REGSUB_ALLOCATION_STRATEGY",
            "REGSUB_DAYLILY_GIT_DEETS",
            "REGSUB_MAX_COUNT_8I",
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
            "REGSUB_HEADNODE_INSTANCE_TYPE",
            "REGSUB_HEARTBEAT_EMAIL",
            "REGSUB_HEARTBEAT_SCHEDULE",
            "REGSUB_HEARTBEAT_SCHEDULER_ROLE_ARN",
            "REGSUB_SLURM_ACCOUNTING_HEADNODE_NETWORKING",
            "REGSUB_SLURM_ACCOUNTING_DATABASE",
            "REGSUB_SPOT_PRICE_WARN_THRESHOLD",
        }
        assert ALL_SUBSTITUTION_KEYS == expected

    def test_accounting_disabled_template_has_no_dangling_tokens(self):
        template = (
            Path(__file__).resolve().parents[1]
            / "config/day_cluster/intel/us-west-2/us-west-2d/prod_cluster_intel_us-west-2d.yaml"
        ).read_text(encoding="utf-8")
        subs = _full_subs()
        subs.update(empty_slurm_accounting_render_blocks())

        rendered = render_template(template, subs)

        assert "REGSUB_SLURM_ACCOUNTING" not in rendered
        assert "PasswordSecretArn:" not in rendered
        assert "DatabaseName:" not in rendered
        payload = yaml.safe_load(rendered)
        assert "Database" not in payload["Scheduling"]["SlurmSettings"]

    def test_accounting_enabled_template_includes_slurm_database(self):
        template = (
            Path(__file__).resolve().parents[1]
            / "config/day_cluster/intel/us-west-2/us-west-2d/prod_cluster_intel_us-west-2d.yaml"
        ).read_text(encoding="utf-8")
        db = SlurmAccountingDb(
            stack_name="dayec-slurm-accounting-us-west-2b",
            status="CREATE_COMPLETE",
            uri="10.0.1.10:3306",
            private_ip="10.0.1.10",
            database_name="dayec_slurm_acct",
            username="slurm_acct",
            password_secret_arn="arn:aws:secretsmanager:us-west-2:123456789012:secret:acct",
            client_security_group_id="sg-0123456789abcdef0",
            instance_id="i-0123456789abcdef0",
        )
        subs = _full_subs()
        subs.update(slurm_accounting_render_blocks(db))

        rendered = render_template(template, subs)

        assert "AdditionalSecurityGroups:" in rendered
        assert "Database:" in rendered
        assert "Uri: 10.0.1.10:3306" in rendered
        assert "UserName: slurm_acct" in rendered
        assert "PasswordSecretArn: arn:aws:secretsmanager" in rendered
        assert "DatabaseName: dayec_slurm_acct" in rendered
        payload = yaml.safe_load(rendered)
        assert payload["HeadNode"]["Networking"]["AdditionalSecurityGroups"] == [
            "sg-0123456789abcdef0"
        ]
        assert payload["Scheduling"]["SlurmSettings"]["Database"] == {
            "Uri": "10.0.1.10:3306",
            "UserName": "slurm_acct",
            "PasswordSecretArn": (
                "arn:aws:secretsmanager:us-west-2:123456789012:secret:acct"
            ),
            "DatabaseName": "dayec_slurm_acct",
        }

    def test_sentieon_single_template_renders_and_loads_parallelcluster_schema(
        self, monkeypatch
    ):
        monkeypatch.setenv("AWS_DEFAULT_REGION", "us-west-2")
        template = (
            Path(__file__).resolve().parents[1]
            / "config/day_cluster/sentieon-single/us-west-2/us-west-2c/"
            "prod_cluster_sentieon-single_us-west-2c.yaml"
        ).read_text(encoding="utf-8")
        subs = _full_subs()
        subs.update(empty_slurm_accounting_render_blocks())
        subs.update(
            {
                "REGSUB_REGION": "us-west-2",
                "REGSUB_PUB_SUBNET": "subnet-0123456789abcdef0",
                "REGSUB_PRIVATE_SUBNET": "subnet-0123456789abcdef1",
                "REGSUB_CLUSTER_NAME": "sentieon-test",
                "REGSUB_HEADNODE_INSTANCE_TYPE": "r7i.2xlarge",
                "REGSUB_S3_BUCKET_INIT": "s3://dayec-assets/cluster_boot_config",
                "REGSUB_S3_IAM_POLICY": ("arn:aws:iam::123456789012:policy/dayec-cluster"),
                "REGSUB_S3_REFERENCE_BUCKET": "dayec-references",
                "REGSUB_S3_CONTROL_DATA_BUCKET": "dayec-controls",
                "REGSUB_S3_STAGE_BUCKET": "dayec-stage",
                "REGSUB_S3_EXPORT_BUCKET": "dayec-export",
                "REGSUB_S3_REFERENCE_URI": "s3://dayec-references",
                "REGSUB_DETAILED_MONITORING": "false",
                "REGSUB_DELETE_LOCAL_ROOT": "true",
                "REGSUB_SAVE_FSX": "Delete",
                "REGSUB_ENFORCE_BUDGET": '"true"',
                "REGSUB_SPOT_PRICE_WARN_THRESHOLD": '"8.00"',
            }
        )

        rendered = render_template(template, subs)

        assert "${" not in rendered
        payload = yaml.safe_load(rendered)
        for queue in payload["Scheduling"]["SlurmQueues"]:
            queue["ComputeResources"][0]["SpotPrice"] = 8.0
        cluster = ClusterSchema(cluster_name="sentieon-test").load(payload)
        assert cluster.image.os == "ubuntu2204"
        assert len(cluster.scheduling.queues) == 4
        assert payload["SharedStorage"][0]["Name"] == "fsx-hiomrs"

    def test_rhel_dragen_template_renders_rhel_boot_script_with_full_arg_contract(self):
        template = (
            Path(__file__).resolve().parents[1]
            / "config/day_cluster/prod_cluster_dragen_pcluster_image_rhel8.yaml"
        ).read_text(encoding="utf-8")
        subs = _full_subs()
        subs.update(empty_slurm_accounting_render_blocks())
        subs.update(
            {
                "REGSUB_REGION": "us-west-2",
                "REGSUB_S3_BUCKET_INIT": (
                    "s3://lsmc-dayoa-references-usw2/runtime_assets/cluster_boot_config"
                ),
                "REGSUB_SPOT_PRICE_WARN_THRESHOLD": '"6.00"',
                "REGSUB_DRAGEN_PCLUSTER_AMI": "ami-0123456789abcdef0",
            }
        )

        rendered = render_template(template, subs)

        assert "post_install_ubuntu_combined.sh" not in rendered
        payload = yaml.safe_load(rendered)
        assert payload["Image"]["Os"] == "rhel8"
        headnode_action = payload["HeadNode"]["CustomActions"]["OnNodeConfigured"]
        assert headnode_action == {
            "Script": (
                "s3://lsmc-dayoa-references-usw2/runtime_assets/"
                "cluster_boot_config/post_install_rhel8_dragen.sh"
            ),
            "Args": [
                "us-west-2",
                "s3://lsmc-dayoa-references-usw2/runtime_assets/cluster_boot_config",
                "6.00",
                "fsx",
            ],
        }
        queue_action = payload["Scheduling"]["SlurmQueues"][0]["CustomActions"][
            "OnNodeConfigured"
        ]
        assert queue_action == headnode_action


# ── TestWriteInitArtifacts ───────────────────────────────────────────


class TestWriteInitArtifacts:
    def _write_template(self, tmp_path: Path) -> Path:
        tpl = tmp_path / "template.yaml"
        tpl.write_text(MINI_TEMPLATE, encoding="utf-8")
        return tpl

    def test_creates_both_files(self, tmp_path: Path):
        tpl = self._write_template(tmp_path)
        out_dir = tmp_path / "out"
        yaml_init, init_tpl = write_init_artifacts(
            "prod",
            "20260211140000",
            str(tpl),
            MINIMAL_SUBS,
            config_dir=out_dir,
        )
        assert Path(yaml_init).is_file()
        assert Path(init_tpl).is_file()

    def test_yaml_init_is_raw_copy(self, tmp_path: Path):
        tpl = self._write_template(tmp_path)
        out_dir = tmp_path / "out"
        yaml_init, _ = write_init_artifacts(
            "prod",
            "20260211140000",
            str(tpl),
            MINIMAL_SUBS,
            config_dir=out_dir,
        )
        assert Path(yaml_init).read_text() == MINI_TEMPLATE

    def test_init_template_is_rendered(self, tmp_path: Path):
        tpl = self._write_template(tmp_path)
        out_dir = tmp_path / "out"
        _, init_tpl = write_init_artifacts(
            "prod",
            "20260211140000",
            str(tpl),
            MINIMAL_SUBS,
            config_dir=out_dir,
        )
        content = Path(init_tpl).read_text()
        assert "${" not in content
        assert "us-west-2" in content

    def test_naming_convention(self, tmp_path: Path):
        tpl = self._write_template(tmp_path)
        out_dir = tmp_path / "out"
        yaml_init, init_tpl = write_init_artifacts(
            "mycluster",
            "20260211",
            str(tpl),
            MINIMAL_SUBS,
            config_dir=out_dir,
        )
        assert "mycluster_cluster_20260211.yaml.init" in yaml_init
        assert "mycluster_init_template_20260211.yaml" in init_tpl

    def test_creates_config_dir(self, tmp_path: Path):
        tpl = self._write_template(tmp_path)
        out_dir = tmp_path / "deep" / "nested"
        write_init_artifacts(
            "prod",
            "ts",
            str(tpl),
            MINIMAL_SUBS,
            config_dir=out_dir,
        )
        assert out_dir.is_dir()

    def test_missing_template_raises(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError, match="Template not found"):
            write_init_artifacts(
                "prod",
                "ts",
                "/no/such/file.yaml",
                MINIMAL_SUBS,
                config_dir=tmp_path,
            )

    def test_missing_required_key_propagates(self, tmp_path: Path):
        tpl = self._write_template(tmp_path)
        subs = dict(MINIMAL_SUBS)
        del subs["REGSUB_REGION"]
        with pytest.raises(ValueError, match="REGSUB_REGION"):
            write_init_artifacts(
                "prod",
                "ts",
                str(tpl),
                subs,
                config_dir=tmp_path,
            )

    def test_byte_stable_artifacts(self, tmp_path: Path):
        tpl = self._write_template(tmp_path)
        d1 = tmp_path / "run1"
        d2 = tmp_path / "run2"
        _, p1 = write_init_artifacts(
            "c",
            "ts",
            str(tpl),
            MINIMAL_SUBS,
            config_dir=d1,
        )
        _, p2 = write_init_artifacts(
            "c",
            "ts",
            str(tpl),
            MINIMAL_SUBS,
            config_dir=d2,
        )
        assert Path(p1).read_bytes() == Path(p2).read_bytes()
