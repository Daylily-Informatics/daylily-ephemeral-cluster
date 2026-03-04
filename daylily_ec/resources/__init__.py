"""Packaged resource access for Daylily Ephemeral Cluster.

This package ships a snapshot of repo assets (config/, etc/, bin/ helpers)
inside the wheel/sdist under ``daylily_ec.resources/payload`` so that
`pip install daylily-ephemeral-cluster` is sufficient to run tools from
any working directory (i.e. without a repo checkout).

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

RES_DIR_ENV = "DAYLILY_EC_RESOURCES_DIR"


def _package_version() -> str:
    try:
        from importlib.metadata import version

        return version("daylily-ephemeral-cluster")
    except Exception:
        # Source-tree or otherwise not installed. Keep path stable but clearly dev.
        return "dev"


def _xdg_config_home() -> Path:
    xdg = os.environ.get("XDG_CONFIG_HOME", "")
    if xdg:
        return Path(xdg).expanduser()
    return Path.home() / ".config"


def _expected_subpaths(root: Path) -> Iterable[Path]:
    # Minimum layout required for the CLI + legacy scripts.
    yield root / "config"
    yield root / "config" / "day_cluster" / "prod_cluster.yaml"
    yield root / "config" / "day_cluster" / "pcluster_env.yml"
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


def ensure_extracted() -> Path:
    """Return the filesystem directory containing extracted resources.

    Extraction is idempotent and safe to call at process startup.
    """
    override = os.environ.get(RES_DIR_ENV, "")
    if override:
        root = Path(override).expanduser()
        _validate_resources_dir(root)
        return root

    version = _package_version()
    dest = _xdg_config_home() / "daylily" / "resources" / version
    marker = dest / ".complete"

    if marker.is_file():
        return dest

    payload = ir.files(__name__).joinpath("payload")
    with ir.as_file(payload) as src:
        # If a previous extraction partially succeeded, replace it cleanly.
        if dest.exists() and not marker.exists():
            shutil.rmtree(dest, ignore_errors=True)

        dest.parent.mkdir(parents=True, exist_ok=True)

        # Copy into a temp dir first, then rename into place.
        tmp_parent = dest.parent
        tmp_dir = Path(
            tempfile.mkdtemp(prefix=f"{dest.name}.tmp-", dir=str(tmp_parent))
        )
        try:
            shutil.copytree(src, tmp_dir, dirs_exist_ok=True)
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
        Repo-relative path inside the payload (e.g. ``config/day_cluster/prod_cluster.yaml``).
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

