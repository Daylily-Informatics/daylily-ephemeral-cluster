from __future__ import annotations

from pathlib import Path
import subprocess

import yaml

from daylily_ec.aws.context import AWSContext
from daylily_ec.render.renderer import write_init_artifacts
from daylily_ec.resources import INTEL_TEMPLATE_RELPATHS, resource_path
from daylily_ec.workflow import create_cluster

REPO_ROOT = Path(__file__).resolve().parents[1]
ACTIVE_CLUSTER_TEMPLATES = INTEL_TEMPLATE_RELPATHS
SENTIEON_SINGLE_TEMPLATE = (
    "config/day_cluster/sentieon-single/us-west-2/us-west-2c/"
    "prod_cluster_sentieon-single_us-west-2c.yaml"
)
ACTIVE_CFN_TEMPLATES = (
    "config/day_cluster/slurm_accounting_mysql_ec2.yml",
)
ACTIVE_IAM_POLICY_TEMPLATES = (
    "config/day_cluster/pcluster_env.yml",
    "config/day_cluster/pcluster_env.yml.new",
    "config/day_cluster/pcluster_env.yml.expanded",
    "config/day_cluster/ap-south-1-stack.yml",
)
DAYOA_RUNTIME_SPOT_ACTIONS = (
    "ec2:DescribeInstanceTypes",
    "ec2:DescribeInstanceTypeOfferings",
    "ec2:DescribeSpotPriceHistory",
)
BOOT_CONFIG_FILES = (
    "config/day_cluster/install_slurm_job_submit_policy.sh",
    "config/day_cluster/job_submit.lua",
    "config/day_cluster/post_install_almalinux8_dragen.sh",
    "config/day_cluster/post_install_ubuntu_combined.sh",
    "config/day_cluster/post_install_rhel8_dragen.sh",
    "config/day_cluster/sbatch",
)


def _active_parallelcluster_templates(root: Path) -> list[tuple[Path, dict]]:
    templates: list[tuple[Path, dict]] = []
    for path in sorted(root.rglob("*.yaml")):
        if "archive_do_not_use" in path.parts:
            continue
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict) and "HeadNode" in payload:
            templates.append((path, payload))
    return templates


def test_all_active_cluster_templates_disable_headnode_elastic_ip() -> None:
    roots = (
        REPO_ROOT / "config/day_cluster",
        REPO_ROOT / "daylily_ec/resources/payload/config/day_cluster",
    )
    templates = [
        item
        for root in roots
        for item in _active_parallelcluster_templates(root)
    ]

    assert templates
    for path, payload in templates:
        assert payload["HeadNode"]["Networking"].get("ElasticIp") is False, path


def test_create_workflow_loads_default_config_outside_repo(tmp_path, monkeypatch):
    # Ensure repo-relative config/ is not available.
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("DAYLILY_EC_RESOURCES_DIR", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

    def _boom(cls, *args, **kwargs):  # noqa: ANN001, D401
        raise RuntimeError("boom")

    # run_create_workflow loads config before calling AWSContext.build. The packaged
    # default now intentionally fails non-interactive execution because FSx choices
    # have no set values. A broken resource path would still raise FileNotFoundError.
    monkeypatch.setattr(AWSContext, "build", classmethod(_boom))

    rc = create_cluster.run_create_workflow(
        "us-west-2a",
        profile="dummy",
        config_path=None,
        non_interactive=True,
    )
    assert rc == create_cluster.EXIT_VALIDATION_FAILURE


def test_write_init_artifacts_accepts_packaged_template(tmp_path, monkeypatch):
    monkeypatch.delenv("DAYLILY_EC_RESOURCES_DIR", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

    template = str(
        resource_path(
            "config/day_cluster/intel/us-west-2/us-west-2d/prod_cluster_intel_us-west-2d.yaml"
        )
    )
    substitutions = {
        "REGSUB_REGION": "us-west-2",
        "REGSUB_PUB_SUBNET": "subnet-123",
        "REGSUB_PRIVATE_SUBNET": "subnet-456",
        "REGSUB_CLUSTER_NAME": "test",
    }

    yaml_init, init_template = write_init_artifacts(
        "test",
        "20260101000000",
        template,
        substitutions,
        config_dir=tmp_path / "out",
    )
    assert (tmp_path / "out").is_dir()
    assert (tmp_path / "out" / "test_cluster_20260101000000.yaml.init").is_file()
    assert (tmp_path / "out" / "test_init_template_20260101000000.yaml").is_file()
    assert yaml_init == str(tmp_path / "out" / "test_cluster_20260101000000.yaml.init")
    assert init_template == str(tmp_path / "out" / "test_init_template_20260101000000.yaml")


def test_packaged_global_config_matches_source_config() -> None:
    source = REPO_ROOT / "config" / "daylily_cli_global.yaml"
    packaged = REPO_ROOT / "daylily_ec/resources/payload/config/daylily_cli_global.yaml"

    assert packaged.read_text(encoding="utf-8") == source.read_text(encoding="utf-8")


def test_global_config_uses_strict_sentieon_server_endpoint() -> None:
    for relative_path in (
        "config/daylily_cli_global.yaml",
        "daylily_ec/resources/payload/config/daylily_cli_global.yaml",
    ):
        payload = yaml.safe_load((REPO_ROOT / relative_path).read_text(encoding="utf-8"))
        daylily = payload["daylily"]
        assert "sentieon_lic_path" not in daylily
        assert daylily["sentieon_license"] == {
            "mode": "server",
            "endpoint": "license.sentieon.lsmc.bio:8990",
        }


def test_active_cluster_templates_use_contract_role_dras() -> None:
    for relative_path in ACTIVE_CLUSTER_TEMPLATES:
        text = (REPO_ROOT / relative_path).read_text(encoding="utf-8")
        assert "ImportPath:" not in text
        assert "ExportPath:" not in text
        payload = yaml.safe_load(text)
        fsx_settings = next(
            item["FsxLustreSettings"]
            for item in payload["SharedStorage"]
            if item["StorageType"] == "FsxLustre"
        )
        assert "AutoExportPolicy" not in fsx_settings
        assert "AutoImportPolicy" not in fsx_settings
        associations = fsx_settings["DataRepositoryAssociations"]
        assert [item["Name"] for item in associations] == [
            "reference-data",
        ]
        assert [item["FileSystemPath"] for item in associations] == [
            "/references/",
        ]
        assert [item["DataRepositoryPath"] for item in associations] == [
            "${REGSUB_S3_REFERENCE_URI}/",
        ]
        assert "${REGSUB_S3_CONTROL_DATA_URI}/" not in text
        assert "${REGSUB_S3_STAGE_URI}/" not in text
        assert all(item["BatchImportMetaDataOnCreate"] is True for item in associations)
        assert all(
            item["AutoImportPolicy"] == ["NEW", "CHANGED", "DELETED"] for item in associations
        )


def test_active_cluster_template_uses_expected_partition_contract() -> None:
    for relative_path in ACTIVE_CLUSTER_TEMPLATES:
        text = (REPO_ROOT / relative_path).read_text(encoding="utf-8")
        payload = yaml.safe_load(text)
        queues = payload["Scheduling"]["SlurmQueues"]
        names = [queue["Name"] for queue in queues]
        expected_names = [
            "i8",
            "i96nvme",
            "i128",
            "i128mem",
            "i128bigmem",
            "i128nvme",
            "i192",
            "i192mem",
            "i192bigmem",
            "i192nvme",
        ]
        region_az = Path(relative_path).parent.name
        if region_az not in {
            "ap-south-1a",
            "ap-south-1b",
            "ap-south-1c",
            "us-west-1a",
            "us-west-1b",
        }:
            expected_names.append("i384nvme")
        expected_names.append("i192hugenvme")
        assert names == expected_names
        assert payload["Scheduling"]["SlurmSettings"]["EnableMemoryBasedScheduling"] is False
        assert "bcl-convert" not in names
        assert "bcl2fq-i384-nvme-test" not in names
        queues_by_name = {queue["Name"]: queue for queue in queues}

        def _compute_resource(queue_name: str, resource_name: str) -> dict:
            for resource in queues_by_name[queue_name]["ComputeResources"]:
                if resource["Name"] == resource_name:
                    return resource
            raise AssertionError(f"{relative_path}: {queue_name} lacks {resource_name}")

        for parent_name, resource_name, alias_name in (
            ("i128", "mem128", "i128mem"),
            ("i128", "bigmem128", "i128bigmem"),
            ("i192", "mem192", "i192mem"),
            ("i192", "bigmem192", "i192bigmem"),
        ):
            parent_top_level = {
                key: value
                for key, value in queues_by_name[parent_name].items()
                if key not in {"Name", "ComputeResources"}
            }
            alias_top_level = {
                key: value
                for key, value in queues_by_name[alias_name].items()
                if key not in {"Name", "ComputeResources"}
            }
            assert alias_top_level == parent_top_level
            assert queues_by_name[alias_name]["ComputeResources"] == [
                _compute_resource(parent_name, resource_name)
            ]
        for queue in queues:
            assert queue["JobExclusiveAllocation"] is False
            for resource in queue["ComputeResources"]:
                assert resource.get("Instances"), (
                    f"{relative_path}: {queue['Name']}/{resource['Name']} has no instances"
                )
            if queue["Name"].endswith("nvme"):
                assert (
                    queue["ComputeSettings"]["LocalStorage"]["EphemeralVolume"]["MountDir"]
                    == "/scratch"
                )
            else:
                assert "ComputeSettings" not in queue
        assert "c8a." not in text
        assert "r8in.48xlarge" not in text
        assert "r8ib.48xlarge" not in text
        assert queues_by_name["i96nvme"]["ComputeResources"][0]["MaxCount"] == (
            "${REGSUB_MAX_COUNT_96I_NVME}"
        )


def test_packaged_cluster_templates_match_source_templates() -> None:
    for relative_path in ACTIVE_CLUSTER_TEMPLATES:
        source = (REPO_ROOT / relative_path).read_text(encoding="utf-8")
        packaged = (REPO_ROOT / "daylily_ec/resources/payload" / relative_path).read_text(
            encoding="utf-8"
        )
        assert packaged == source


def test_packaged_az_scoped_cluster_templates_match_source_templates() -> None:
    source_paths = sorted(
        (REPO_ROOT / "config/day_cluster").glob("*/*/*/prod_cluster_*.yaml")
    )
    assert len(source_paths) == 21
    for source_path in source_paths:
        relative_path = source_path.relative_to(REPO_ROOT)
        source = source_path.read_text(encoding="utf-8")
        packaged = (REPO_ROOT / "daylily_ec/resources/payload" / relative_path).read_text(
            encoding="utf-8"
        )
        assert packaged == source


def test_sentieon_single_source_and_packaged_templates_match() -> None:
    source = (REPO_ROOT / SENTIEON_SINGLE_TEMPLATE).read_bytes()
    packaged = (
        REPO_ROOT / "daylily_ec/resources/payload" / SENTIEON_SINGLE_TEMPLATE
    ).read_bytes()

    assert packaged == source


def test_generic_intel_cluster_template_is_not_an_active_template() -> None:
    generic_relpath = (
        "config/day_cluster/prod_cluster_nested_spot_mem_scratch_intel_avx512_expanded.yaml"
    )
    assert not (REPO_ROOT / generic_relpath).exists()
    assert not (REPO_ROOT / "daylily_ec/resources/payload" / generic_relpath).exists()


def test_rhel_az_scoped_templates_only_exist_for_viable_azs() -> None:
    present = {
        path.parent.name
        for path in (REPO_ROOT / "config/day_cluster/rhel").glob("*/*/prod_cluster_rhel_*.yaml")
    }
    assert present == {
        "eu-central-1b",
        "eu-central-1c",
        "us-west-2b",
        "us-west-2c",
    }


def test_packaged_boot_config_matches_source_and_uses_declarative_slurm_policy() -> None:
    for relative_path in BOOT_CONFIG_FILES:
        source = (REPO_ROOT / relative_path).read_text(encoding="utf-8")
        packaged = (REPO_ROOT / "daylily_ec/resources/payload" / relative_path).read_text(
            encoding="utf-8"
        )
        assert packaged == source

    for relative_path in (
        "config/day_cluster/post_install_ubuntu_combined.sh",
        "config/day_cluster/post_install_rhel8_dragen.sh",
    ):
        script = (REPO_ROOT / relative_path).read_text(encoding="utf-8")
        assert "install_slurm_submission_policy" in script
        assert "/opt/slurm/etc/scripts/prolog.d" in script
        assert "/opt/slurm/etc/scripts/epilog.d" in script
        assert "/opt/slurm/etc/slurm.conf" not in script
        assert "systemctl restart slurm" not in script
        assert 'spot_lifecycle_state_dir="/var/lib/daylily/spot_lifecycle"' in script
        assert "spot_price_warn_exception_messages.log" in script
        assert "dyec.spot_price_warn_exception.v1" in script
        assert "write_spot_price_warn_exception" in script
        assert "daylily-spot-lifecycle-shutdown.service" in script
        assert "daylily-spot-interruption-watch.service" in script
        assert "ExecStop=/opt/daylily/bin/daylily-spot-lifecycle-event shutdown systemd-stop" in script
        assert "latest/meta-data/spot/instance-action" in script

    ubuntu_script = (
        REPO_ROOT / "config/day_cluster/post_install_ubuntu_combined.sh"
    ).read_text(encoding="utf-8")
    assert 'spot_price_warn_threshold="${3:?spot price warn threshold argument is required}"' in ubuntu_script
    rhel_script = (
        REPO_ROOT / "config/day_cluster/post_install_rhel8_dragen.sh"
    ).read_text(encoding="utf-8")
    assert 'spot_price_warn_threshold="${3:?spot price warn threshold argument is required}"' in rhel_script

    sbatch = (REPO_ROOT / "config/day_cluster/sbatch").read_text(encoding="utf-8")
    assert "Slurm memory placement is disabled" in sbatch
    assert "--mem-per-cpu" in sbatch
    assert "--exclusive|--exclusive=*" not in sbatch


def test_almalinux_dragen_wrapper_hydrates_secret_without_logging_contents() -> None:
    script = (
        REPO_ROOT / "config/day_cluster/post_install_almalinux8_dragen.sh"
    ).read_text(encoding="utf-8")

    assert 'license_secret_arn="${5:?license secret ARN argument is required}"' in script
    assert 'node_role="${6:?node role argument is required}"' in script
    assert "headnode|dragen|cpu" in script
    assert '"${node_role}"' in script
    assert "aws secretsmanager get-secret-value" in script
    assert 'config_dir="/home/ubuntu/.config"' in script
    assert 'install -d -m 0700 -o ubuntu -g ubuntu "${config_dir}"' in script
    assert 'credential_path="${credential_dir}/lic_creds.txt"' in script
    assert 'chmod 0600 "${credential_path}"' in script
    assert "echo \"${secret_value}\"" not in script
    subprocess.run(["bash", "-n"], input=script, text=True, check=True)


def test_dragen_template_is_packaged_with_explicit_mixed_node_roles() -> None:
    relative_path = (
        "config/day_cluster/dragen/us-west-2/us-west-2b/"
        "prod_cluster_dragen_us-west-2b.yaml"
    )
    source = (REPO_ROOT / relative_path).read_text(encoding="utf-8")
    packaged = (REPO_ROOT / "daylily_ec/resources/payload" / relative_path).read_text(
        encoding="utf-8"
    )
    assert packaged == source

    payload = yaml.safe_load(source)
    queues = payload["Scheduling"]["SlurmQueues"]
    assert [queue["Name"] for queue in queues] == [
        "dragen",
        "dragen-ondemand",
        "i192",
        "i192nvme",
    ]
    assert queues[0]["CapacityType"] == "SPOT"
    assert queues[1]["CapacityType"] == "ONDEMAND"
    for queue in queues[:2]:
        assert queue["CustomActions"]["OnNodeConfigured"]["Args"][-1] == "dragen"
        resource = queue["ComputeResources"][0]
        assert resource["Instances"] == [{"InstanceType": "f2.6xlarge"}]
        assert resource["MinCount"] == 0
        assert resource["MaxCount"] == 1
        assert "SchedulableMemory" not in resource
        assert resource["Efa"]["Enabled"] is False
    assert "SpotPrice" not in queues[1]["ComputeResources"][0]
    for queue in queues[2:]:
        action = queue["CustomActions"]["OnNodeConfigured"]
        assert action["Script"].endswith("/post_install_rhel8_dragen.sh")
        assert action["Args"][-1] == "cpu"
        assert queue["ComputeResources"][0]["Efa"]["Enabled"] is False

    base_script = (
        REPO_ROOT / "config/day_cluster/post_install_rhel8_dragen.sh"
    ).read_text(encoding="utf-8")
    assert 'node_role="${5:?node role argument is required}"' in base_script
    assert "Skipping DRAGEN FPGA validation on explicitly configured CPU compute node" in base_script


def test_rhel_and_legacy_dragen_templates_expose_explicit_ondemand_partition() -> None:
    template_paths = sorted(
        (REPO_ROOT / "config/day_cluster/rhel").glob("*/*/prod_cluster_rhel_*.yaml")
    ) + [
        REPO_ROOT / "config/day_cluster/prod_cluster_dragen_native_ami_rhel8.yaml",
        REPO_ROOT / "config/day_cluster/prod_cluster_dragen_native_ami_rhel8_nofsx.yaml",
        REPO_ROOT / "config/day_cluster/prod_cluster_dragen_pcluster_image_rhel8.yaml",
        REPO_ROOT / "config/day_cluster/prod_cluster_dragen_pcluster_image_rhel8_nofsx.yaml",
    ]

    for path in template_paths:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        queues = payload["Scheduling"]["SlurmQueues"]
        assert [queue["Name"] for queue in queues] == ["dragen", "dragen-ondemand"]
        spot_queue, ondemand_queue = queues
        assert spot_queue["CapacityType"] == "SPOT"
        assert ondemand_queue["CapacityType"] == "ONDEMAND"
        resource = ondemand_queue["ComputeResources"][0]
        assert resource["Name"] == "f26xlargeod"
        assert resource["Instances"] == [{"InstanceType": "f2.6xlarge"}]
        assert resource["MinCount"] == 0
        assert resource["MaxCount"] == 1
        assert "SchedulableMemory" not in resource
        assert resource["Efa"]["Enabled"] is False
        assert "SpotPrice" not in resource
        assert ondemand_queue["ComputeSettings"]["LocalStorage"]["EphemeralVolume"] == {
            "MountDir": "/scratch"
        }

        if "/rhel/" in path.as_posix():
            relative_path = path.relative_to(REPO_ROOT)
            packaged = REPO_ROOT / "daylily_ec/resources/payload" / relative_path
            assert packaged.read_text(encoding="utf-8") == path.read_text(encoding="utf-8")


def test_post_install_s3_executable_install_is_not_sha256_pinned() -> None:
    for relative_path in (
        "config/day_cluster/post_install_ubuntu_combined.sh",
        "config/day_cluster/post_install_rhel8_dragen.sh",
    ):
        script = (REPO_ROOT / relative_path).read_text(encoding="utf-8")
        assert "sbatch_wrapper_sha256" not in script
        assert "sleep_test_sha256" not in script
        assert "install_verified_s3_executable" not in script
        assert 'install_s3_executable "sbatch" /opt/slurm/bin/sbatch' in script
        assert (
            'install_s3_executable "sleep_test.sh" /opt/slurm/bin/sleep_test.sh'
            in script
        )


def test_post_install_templates_pass_spot_warn_threshold_argument() -> None:
    template_paths = (
        *ACTIVE_CLUSTER_TEMPLATES,
        "config/day_cluster/prod_cluster_dragen_native_ami_rhel8.yaml",
        "config/day_cluster/prod_cluster_dragen_native_ami_rhel8_nofsx.yaml",
        "config/day_cluster/prod_cluster_dragen_pcluster_image_rhel8.yaml",
        "config/day_cluster/prod_cluster_dragen_pcluster_image_rhel8_nofsx.yaml",
    )
    for relative_path in template_paths:
        text = (REPO_ROOT / relative_path).read_text(encoding="utf-8")
        assert "${REGSUB_SPOT_PRICE_WARN_THRESHOLD}" in text
        lines = text.splitlines()
        assert any(
            line.strip() == "- ${REGSUB_S3_BUCKET_INIT}"
            and lines[index + 1].strip() == "- ${REGSUB_SPOT_PRICE_WARN_THRESHOLD}"
            for index, line in enumerate(lines[:-1])
        )


def test_spot_lifecycle_helper_heredocs_are_bash_syntax_valid() -> None:
    helper_paths = (
        "/opt/daylily/bin/daylily-spot-lifecycle-event",
        "/opt/daylily/bin/daylily-spot-interruption-watch",
    )
    for relative_path in (
        "config/day_cluster/post_install_ubuntu_combined.sh",
        "config/day_cluster/post_install_rhel8_dragen.sh",
    ):
        script = (REPO_ROOT / relative_path).read_text(encoding="utf-8")
        for helper_path in helper_paths:
            heredoc = _extract_single_quoted_heredoc(script, f"cat > {helper_path} <<'EOF'")
            subprocess.run(["bash", "-n"], input=heredoc, text=True, check=True)


def test_ubuntu_bootstrap_uses_dedicated_sentieon_license_service() -> None:
    script = (
        REPO_ROOT / "config/day_cluster/post_install_ubuntu_combined.sh"
    ).read_text(encoding="utf-8")

    required = (
        "install_sentieon_license_client_profile()",
        "/etc/profile.d/daylily-sentieon-license.sh",
        'export SENTIEON_LICENSE="license.sentieon.lsmc.bio:8990"',
        "install_sentieon_license_client_profile\n",
    )
    for fragment in required:
        assert fragment in script

    for forbidden in (
        "install_sentieon_license_service",
        "daylily-sentieon-license-server.service",
        "daylily-sentieon-license-start",
        "daylily-sentieon-license-ready",
        "licsrvr --start",
        "licsrvr --dump",
        "Life_Sciences_Manufacturing_Corporation_eval.lic",
    ):
        assert forbidden not in script

    subprocess.run(["bash", "-n"], input=script, text=True, check=True)


def test_rhel_bootstrap_exports_dedicated_sentieon_license_endpoint() -> None:
    script = (REPO_ROOT / "config/day_cluster/post_install_rhel8_dragen.sh").read_text(
        encoding="utf-8"
    )

    assert "/etc/profile.d/daylily-sentieon-license.sh" in script
    assert 'export SENTIEON_LICENSE="license.sentieon.lsmc.bio:8990"' in script
    assert "licsrvr --start" not in script
    subprocess.run(["bash", "-n"], input=script, text=True, check=True)


def _extract_single_quoted_heredoc(script: str, marker: str) -> str:
    start = script.index(marker) + len(marker)
    remainder = script[start:]
    if remainder.startswith("\n"):
        remainder = remainder[1:]
    end = remainder.index("\nEOF\n")
    return remainder[:end]


def test_dayoa_headnode_generators_do_not_emit_exclusive_rules() -> None:
    script = (
        REPO_ROOT / "daylily_ec/scripts/daylily_run_omics_analysis_headnode.py"
    ).read_text(encoding="utf-8")

    assert 'exclusive="--exclusive"' not in script
    assert 'exclusive=""' in script


def test_packaged_cfn_templates_match_source_templates() -> None:
    for relative_path in ACTIVE_CFN_TEMPLATES:
        source = (REPO_ROOT / relative_path).read_text(encoding="utf-8")
        packaged = (REPO_ROOT / "daylily_ec/resources/payload" / relative_path).read_text(
            encoding="utf-8"
        )
        assert packaged == source


def test_pcluster_env_policies_allow_dayoa_runtime_spot_discovery() -> None:
    for relative_path in ACTIVE_IAM_POLICY_TEMPLATES:
        source = (REPO_ROOT / relative_path).read_text(encoding="utf-8")
        packaged = (REPO_ROOT / "daylily_ec/resources/payload" / relative_path).read_text(
            encoding="utf-8"
        )
        assert packaged == source
        for action in DAYOA_RUNTIME_SPOT_ACTIONS:
            assert action in source
