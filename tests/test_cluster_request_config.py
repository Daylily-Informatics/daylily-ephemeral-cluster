from __future__ import annotations

from daylily_ec.config import load_config, write_noninteractive_cluster_config


def test_write_noninteractive_cluster_config_uses_current_dayec_triplets(tmp_path):
    path = write_noninteractive_cluster_config(
        dest=tmp_path / "cluster.yaml",
        cluster_name="cluster-a",
        ssh_key_name="omics-key",
        reference_bucket="dayoa-references",
        control_data_bucket="dayoa-control-data",
        runtime_assets_bucket="dayoa-runtime-assets",
        stage_bucket="dayoa-staging",
        contact_email="ops@example.com",
    )

    cfg = load_config(path)
    values = cfg.ephemeral_cluster.config

    assert values["cluster_name"].to_list() == ["USESETVALUE", "", "cluster-a"]
    assert values["ssh_key_name"].to_list() == ["USESETVALUE", "", "omics-key"]
    assert values["reference_bucket"].to_list() == ["USESETVALUE", "", "dayoa-references"]
    assert values["control_data_bucket"].to_list() == ["USESETVALUE", "", "dayoa-control-data"]
    assert values["runtime_assets_bucket"].to_list() == ["USESETVALUE", "", "dayoa-runtime-assets"]
    assert values["stage_bucket"].to_list() == ["USESETVALUE", "", "dayoa-staging"]
    assert values["budget_email"].to_list() == ["USESETVALUE", "", "ops@example.com"]
    assert values["enforce_budget"].to_list() == ["USESETVALUE", "", "skip"]
    assert values["cluster_template_yaml"].to_list() == ["PROMPTUSER", "", ""]
