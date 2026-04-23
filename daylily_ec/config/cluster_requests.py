from __future__ import annotations

from pathlib import Path

from daylily_ec.config.models import ConfigFile, Triplet
from daylily_ec.config.triplets import ensure_required_keys, write_config


def build_noninteractive_cluster_config(
    *,
    cluster_name: str,
    ssh_key_name: str,
    s3_bucket_name: str,
    contact_email: str | None = None,
) -> ConfigFile:
    """Build the day-ec 2.1.1 non-interactive cluster request config."""

    values = {
        "cluster_name": cluster_name,
        "ssh_key_name": ssh_key_name,
        "s3_bucket_name": s3_bucket_name,
        "enforce_budget": "skip",
    }
    if contact_email:
        values["budget_email"] = contact_email

    cfg = ConfigFile()
    ensure_required_keys(cfg)
    for key, value in values.items():
        cfg.ephemeral_cluster.config[key] = Triplet(
            action="USESETVALUE",
            default_value="",
            set_value=str(value),
        )
    return cfg


def write_noninteractive_cluster_config(
    *,
    dest: str | Path,
    cluster_name: str,
    ssh_key_name: str,
    s3_bucket_name: str,
    contact_email: str | None = None,
) -> Path:
    """Write a day-ec cluster request config and return the written path."""

    path = Path(dest)
    cfg = build_noninteractive_cluster_config(
        cluster_name=cluster_name,
        ssh_key_name=ssh_key_name,
        s3_bucket_name=s3_bucket_name,
        contact_email=contact_email,
    )
    write_config(cfg, path)
    return path
