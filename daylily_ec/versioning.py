"""Shared version resolution helpers for source checkouts and installed dists."""

from __future__ import annotations

import re
import subprocess
from functools import lru_cache
from pathlib import Path

DIST_NAME = "daylily-ephemeral-cluster"
_SEMVER_TAG = re.compile(r"^\d+\.\d+\.\d+(?:\.\d+)?$")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _exact_source_tag(root: Path) -> str | None:
    """Return the exact release tag at ``HEAD``, independent of worktree dirt."""
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "describe", "--tags", "--exact-match", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return None

    tag = result.stdout.strip()
    if result.returncode == 0 and _SEMVER_TAG.fullmatch(tag):
        return tag
    return None


def _source_tree_version() -> str | None:
    root = _repo_root()
    if not (root / ".git").exists():
        return None

    exact_tag = _exact_source_tag(root)
    if exact_tag is not None:
        return exact_tag

    try:
        from setuptools_scm import get_version as scm_get_version
    except Exception:
        return None

    try:
        return scm_get_version(
            root=str(root),
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
