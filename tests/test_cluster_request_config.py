from __future__ import annotations

from daylily_ec.config import load_config, write_noninteractive_cluster_config


def test_write_noninteractive_cluster_config_uses_current_dayec_triplets(tmp_path):
    path = write_noninteractive_cluster_config(
        dest=tmp_path / "cluster.yaml",
        cluster_name="cluster-a",
        ssh_key_name="omics-key",
        reference_s3_uri="dayoa-references",
        control_data_s3_uri="dayoa-control-data",
        stage_s3_uri="dayoa-staging",
        export_destination_s3_uri="dayoa-results/analysis_results/ops/run-a/",
        contact_email="ops@example.com",
    )

    cfg = load_config(path)
    values = cfg.ephemeral_cluster.config

    assert values["cluster_name"].to_list() == ["USESETVALUE", "", "cluster-a"]
    assert values["ssh_key_name"].to_list() == ["USESETVALUE", "", "omics-key"]
    assert values["reference_s3_uri"].to_list() == ["USESETVALUE", "", "dayoa-references"]
    assert values["control_data_s3_uri"].to_list() == ["USESETVALUE", "", "dayoa-control-data"]
    assert values["stage_s3_uri"].to_list() == ["USESETVALUE", "", "dayoa-staging"]
    assert values["export_destination_s3_uri"].to_list() == [
        "USESETVALUE",
        "",
        "dayoa-results/analysis_results/ops/run-a/",
    ]
    assert values["budget_email"].to_list() == ["USESETVALUE", "", "ops@example.com"]
    assert values["enforce_budget"].to_list() == ["USESETVALUE", "", "skip"]
    assert values["cluster_template_yaml"].to_list() == ["PROMPTUSER", "", ""]
