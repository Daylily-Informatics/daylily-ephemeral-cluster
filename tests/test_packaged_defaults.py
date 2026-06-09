from __future__ import annotations

from pathlib import Path

import yaml

from daylily_ec.aws.context import AWSContext
from daylily_ec.render.renderer import write_init_artifacts
from daylily_ec.resources import resource_path
from daylily_ec.workflow import create_cluster

REPO_ROOT = Path(__file__).resolve().parents[1]
ACTIVE_CLUSTER_TEMPLATES = (
    "config/day_cluster/prod_cluster_nested_spot_mem_scratch_intel_avx512_expanded.yaml",
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


def test_create_workflow_loads_default_config_outside_repo(tmp_path, monkeypatch):
    # Ensure repo-relative config/ is not available.
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("DAYLILY_EC_RESOURCES_DIR", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

    def _boom(cls, *args, **kwargs):  # noqa: ANN001, D401
        raise RuntimeError("boom")

    # run_create_workflow loads config before calling AWSContext.build. If the
    # default config path resolution is broken, this test will raise FileNotFoundError.
    monkeypatch.setattr(AWSContext, "build", classmethod(_boom))

    rc = create_cluster.run_create_workflow(
        "us-west-2a",
        profile="dummy",
        config_path=None,
        non_interactive=True,
    )
    assert rc == create_cluster.EXIT_AWS_FAILURE


def test_write_init_artifacts_accepts_packaged_template(tmp_path, monkeypatch):
    monkeypatch.delenv("DAYLILY_EC_RESOURCES_DIR", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

    template = str(
        resource_path(
            "config/day_cluster/prod_cluster_nested_spot_mem_scratch_intel_avx512_expanded.yaml"
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
    text = (
        REPO_ROOT
        / "config/day_cluster/prod_cluster_nested_spot_mem_scratch_intel_avx512_expanded.yaml"
    ).read_text(encoding="utf-8")
    payload = yaml.safe_load(text)
    queues = payload["Scheduling"]["SlurmQueues"]
    names = [queue["Name"] for queue in queues]
    assert names == ["i8", "i128", "i128nvme", "i192", "i192nvme", "i384nvme", "i192hugenvme"]
    assert payload["Scheduling"]["SlurmSettings"]["EnableMemoryBasedScheduling"] is True
    assert "i192mem" not in names
    assert "i192bigmem" not in names
    assert "bcl-convert" not in names
    assert "bcl2fq-i384-nvme-test" not in names
    for queue in queues:
        if queue["Name"].endswith("nvme"):
            assert queue["JobExclusiveAllocation"] is True
            assert (
                queue["ComputeSettings"]["LocalStorage"]["EphemeralVolume"]["MountDir"]
                == "/scratch"
            )
        else:
            assert "ComputeSettings" not in queue
    assert "c8a." not in text
    assert "r8in.48xlarge" not in text
    assert "r8ib.48xlarge" not in text


def test_packaged_cluster_templates_match_source_templates() -> None:
    for relative_path in ACTIVE_CLUSTER_TEMPLATES:
        source = (REPO_ROOT / relative_path).read_text(encoding="utf-8")
        packaged = (REPO_ROOT / "daylily_ec/resources/payload" / relative_path).read_text(
            encoding="utf-8"
        )
        assert packaged == source


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
