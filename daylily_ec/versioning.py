"""Shared version resolution helpers for source checkouts and installed dists."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

DIST_NAME = "daylily-ephemeral-cluster"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _source_tree_version() -> str | None:
    root = _repo_root()
    if not (root / ".git").exists():
        return None

    try:
        from setuptools_scm import get_version as scm_get_version
    except Exception:
        return None

    try:
        return scm_get_version(
            root=str(root),
            relative_to=__file__,
            version_scheme="guess-next-dev",
            local_scheme="node-and-date",
            fallback_version="0.0.0.dev0",
        )
    except Exception:
        return None


def _installed_version(dist_name: str = DIST_NAME) -> str | None:
    try:
        from importlib.metadata import version

        return version(dist_name)
    except Exception:
        return None


@lru_cache(maxsize=1)
def get_version() -> str:
    """Return the best available version string for the current execution context."""
    version = _source_tree_version()
    if version:
        return version

    version = _installed_version()
    if version:
        return version

    return "0.0.0.dev0"
