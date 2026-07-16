"""Packaged resource access for Daylily Ephemeral Cluster.

This package ships a snapshot of repo assets (config/, etc/, bin/ helpers)
inside the wheel/sdist under ``daylily_ec.resources/payload`` so that
`pip install daylily-ephemeral-cluster` is sufficient to run tools from
any working directory (i.e. without a repo checkout). Legacy SSH/PEM-era
material may live under ``payload/quarantine`` but is excluded from the
active extracted resources tree.

At runtime we extract the payload to a stable per-version directory:

  ${XDG_CONFIG_HOME:-~/.config}/daylily/resources/<pkg-version>/

Users may override extraction by setting ``DAYLILY_EC_RESOURCES_DIR`` to
an existing directory containing the expected layout (config/, etc/, bin/).
"""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from typing import Iterable

import importlib.resources as ir
from daylily_ec import versioning

RES_DIR_ENV = "DAYLILY_EC_RESOURCES_DIR"
INTEL_TEMPLATE_REGION_AZS = (
    "ap-south-1a",
    "ap-south-1b",
    "ap-south-1c",
    "eu-central-1a",
    "eu-central-1b",
    "eu-central-1c",
    "us-east-2a",
    "us-east-2b",
    "us-east-2c",
    "us-west-1a",
    "us-west-1b",
    "us-west-2a",
    "us-west-2b",
    "us-west-2c",
    "us-west-2d",
)
INTEL_SPOT_TEMPLATE_RELPATHS = tuple(
    f"config/day_cluster/intel/{region_az[:-1]}/{region_az}/"
    f"prod_cluster_intel_spot_{region_az}.yaml"
    for region_az in INTEL_TEMPLATE_REGION_AZS
)
INTEL_ONDEMAND_TEMPLATE_RELPATHS = tuple(
    f"config/day_cluster/intel/{region_az[:-1]}/{region_az}/"
    f"prod_cluster_intel_ondemand_{region_az}.yaml"
    for region_az in INTEL_TEMPLATE_REGION_AZS
)
SENTIEON_SINGLE_TEMPLATE_RELPATH = (
    "config/day_cluster/sentieon-single/us-west-2/us-west-2c/"
    "prod_cluster_sentieon-single_us-west-2c.yaml"
)
REQUIRED_CLUSTER_TEMPLATE_RELPATHS = (
    *INTEL_SPOT_TEMPLATE_RELPATHS,
    *INTEL_ONDEMAND_TEMPLATE_RELPATHS,
    SENTIEON_SINGLE_TEMPLATE_RELPATH,
)


def _xdg_config_home() -> Path:
    xdg = os.environ.get("XDG_CONFIG_HOME", "")
    if xdg:
        return Path(xdg).expanduser()
    return Path.home() / ".config"


def _expected_subpaths(root: Path) -> Iterable[Path]:
    # Minimum layout required for the CLI + legacy scripts.
    yield root / "config"
    for relative_path in REQUIRED_CLUSTER_TEMPLATE_RELPATHS:
        yield root / relative_path
    yield root / "config" / "day_cluster" / "pcluster_env.yml"
    yield root / "config" / "day_cluster" / "slurm_accounting_mysql_ec2.yml"
    yield root / "config" / "day_cluster" / "install_slurm_job_submit_policy.sh"
    yield root / "config" / "day_cluster" / "job_submit.lua"
    yield root / "environment.yaml"
    yield root / "etc"
    yield root / "bin"


def _validate_resources_dir(root: Path) -> None:
    missing = [str(p) for p in _expected_subpaths(root) if not p.exists()]
    if missing:
        raise FileNotFoundError(
            "Invalid Daylily resources dir. Missing expected paths:\n"
            + "\n".join(missing)
            + "\n\n"
            f"Set {RES_DIR_ENV} to a directory containing config/, etc/, bin/ "
            "or reinstall daylily-ephemeral-cluster."
        )


def _resources_need_refresh(dest: Path, src: Path) -> bool:
    refresh_rels = (
        "config/daylily_pipeline_command_catalog.yaml",
        *REQUIRED_CLUSTER_TEMPLATE_RELPATHS,
        "config/day_cluster/pcluster_env.yml",
        "config/day_cluster/slurm_accounting_mysql_ec2.yml",
        "config/day_cluster/install_slurm_job_submit_policy.sh",
        "config/day_cluster/job_submit.lua",
        "config/day_cluster/post_install_rhel8_dragen.sh",
        "config/day_cluster/post_install_ubuntu_combined.sh",
        "config/day_cluster/sbatch",
        "config/day_cluster/sleep_test.sh",
    )
    for rel in refresh_rels:
        dest_file = dest / rel
        src_file = src / rel
        if not dest_file.is_file() or not src_file.is_file():
            return True
        if dest_file.read_bytes() != src_file.read_bytes():
            return True
    return False


def ensure_extracted() -> Path:
    """Return the filesystem directory containing extracted resources.

    Extraction is idempotent and safe to call at process startup.
    """
    override = os.environ.get(RES_DIR_ENV, "")
    if override:
        root = Path(override).expanduser()
        _validate_resources_dir(root)
        return root

    version = versioning.get_version()
    dest = _xdg_config_home() / "daylily" / "resources" / version
    marker = dest / ".complete"

    payload = ir.files(__name__).joinpath("payload")
    with ir.as_file(payload) as src:
        if marker.is_file() and not _resources_need_refresh(dest, src):
            return dest

        # If a previous extraction partially succeeded, replace it cleanly.
        if dest.exists():
            shutil.rmtree(dest, ignore_errors=True)

        dest.parent.mkdir(parents=True, exist_ok=True)

        # Copy into a temp dir first, then rename into place.
        tmp_parent = dest.parent
        tmp_dir = Path(
            tempfile.mkdtemp(prefix=f"{dest.name}.tmp-", dir=str(tmp_parent))
        )
        try:
            shutil.copytree(src, tmp_dir, dirs_exist_ok=True, symlinks=True)
            quarantine_dir = tmp_dir / "quarantine"
            if quarantine_dir.exists():
                shutil.rmtree(quarantine_dir, ignore_errors=True)
            (tmp_dir / ".complete").write_text(
                f"daylily-ephemeral-cluster resources {version}\n",
                encoding="utf-8",
            )
            # Ensure destination does not exist so rename is atomic.
            if dest.exists():
                shutil.rmtree(dest, ignore_errors=True)
            tmp_dir.replace(dest)
        finally:
            # If anything failed before rename, best-effort cleanup.
            if tmp_dir.exists() and tmp_dir != dest:
                shutil.rmtree(tmp_dir, ignore_errors=True)

    _validate_resources_dir(dest)
    return dest


def resource_path(rel_path: str) -> Path:
    """Return an extracted resource path.

    Parameters
    ----------
    rel_path:
        Repo-relative path inside the payload.
    """
    rel = rel_path.lstrip("/").replace("\\", "/")
    root = ensure_extracted()
    p = root / rel
    if not p.exists():
        raise FileNotFoundError(
            f"Resource not found: {rel_path}\n"
            f"Resolved resources dir: {root}\n"
            f"Override with {RES_DIR_ENV} if needed."
        )
    return p
