from __future__ import annotations

from daylily_ec.config import load_config, write_noninteractive_cluster_config


def test_write_noninteractive_cluster_config_uses_current_dayec_triplets(tmp_path):
    path = write_noninteractive_cluster_config(
        dest=tmp_path / "cluster.yaml",
        cluster_name="cluster-a",
        ssh_key_name="omics-key",
        s3_bucket_name="omics-bucket",
        contact_email="ops@example.com",
    )

    cfg = load_config(path)
    values = cfg.ephemeral_cluster.config

    assert values["cluster_name"].to_list() == ["USESETVALUE", "", "cluster-a"]
    assert values["ssh_key_name"].to_list() == ["USESETVALUE", "", "omics-key"]
    assert values["s3_bucket_name"].to_list() == ["USESETVALUE", "", "omics-bucket"]
    assert values["budget_email"].to_list() == ["USESETVALUE", "", "ops@example.com"]
    assert values["enforce_budget"].to_list() == ["USESETVALUE", "", "skip"]
    assert values["cluster_template_yaml"].to_list() == ["PROMPTUSER", "", ""]
