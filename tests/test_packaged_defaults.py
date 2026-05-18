from __future__ import annotations

from pathlib import Path

import yaml

from daylily_ec.aws.context import AWSContext
from daylily_ec.render.renderer import write_init_artifacts
from daylily_ec.resources import resource_path
from daylily_ec.workflow import create_cluster

REPO_ROOT = Path(__file__).resolve().parents[1]
ACTIVE_CLUSTER_TEMPLATES = (
    "config/day_cluster/prod_cluster.yaml",
    "config/day_cluster/prod_cluster_dragen.yaml",
    "config/day_cluster/prod_cluster_variant.yaml",
    "config/day_cluster/cromwell_test.yaml",
    "config/day_cluster/regions/all_clusters.yaml",
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

    template = str(resource_path("config/day_cluster/prod_cluster.yaml"))
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


def test_active_cluster_templates_use_reference_data_dra_only() -> None:
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
        assert fsx_settings["DataRepositoryAssociations"] == [
            {
                "Name": "reference-data",
                "FileSystemPath": "/data/",
                "DataRepositoryPath": fsx_settings["DataRepositoryAssociations"][0][
                    "DataRepositoryPath"
                ],
                "BatchImportMetaDataOnCreate": True,
                "AutoImportPolicy": ["NEW", "CHANGED", "DELETED"],
            }
        ]


def test_packaged_cluster_templates_match_source_templates() -> None:
    for relative_path in ACTIVE_CLUSTER_TEMPLATES:
        source = (REPO_ROOT / relative_path).read_text(encoding="utf-8")
        packaged = (
            REPO_ROOT / "daylily_ec/resources/payload" / relative_path
        ).read_text(encoding="utf-8")
        assert packaged == source
