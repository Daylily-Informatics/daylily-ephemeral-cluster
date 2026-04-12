from __future__ import annotations

from pathlib import Path
import re

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]

SUPPORTED_DOCS = [
    REPO_ROOT / "README.md",
    REPO_ROOT / "README.md.bland",
    REPO_ROOT / "docs" / "DAY_EC_ENVIRONMENT.md",
    REPO_ROOT / "docs" / "operations.md",
    REPO_ROOT / "docs" / "overview.md",
    REPO_ROOT / "docs" / "pip_install.md",
    REPO_ROOT / "docs" / "quickest_start.md",
    REPO_ROOT / "docs" / "ultra_rapid_start.md",
]

SUPPORTED_SCRIPT_ROOTS = [
    REPO_ROOT / "bin",
    REPO_ROOT / "daylily_ec" / "resources" / "payload" / "bin",
]

SUPPORTED_CONFIG_ROOTS = [
    REPO_ROOT / "config",
    REPO_ROOT / "daylily_ec" / "resources" / "payload" / "config",
]

BANNED_PATTERNS = {
    r"\b--pem\b": "legacy PEM CLI flag",
    r"\bssh -i\b": "direct PEM-based SSH command",
    r"\bssh_key_name\b": "legacy SSH key config field",
    r"\bPEM_PATH\b": "legacy PEM environment variable",
    r"\bStrictHostKeyChecking\b": "legacy SSH option",
    r"\bUserKnownHostsFile\b": "legacy SSH option",
    r"\bsudo -iu ubuntu\b": "manual user-switch instruction",
    r"\bsudo su - ubuntu\b": "manual user-switch instruction",
    r"\bssh_url\b": "unsupported SSH repository URL field",
    r"\bgit_ephemeral_cluster_repo_ssh\b": "unsupported SSH repository config field",
    r"--which-one\s+\{https,ssh\}": "unsupported day-clone transport selector",
    r"\bscp\b": "legacy SSH file copy command",
}


def _iter_supported_script_files():
    for root in SUPPORTED_SCRIPT_ROOTS:
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            if "legacy" in path.parts:
                continue
            if "quarantine" in path.parts:
                continue
            if "__pycache__" in path.parts:
                continue
            if path.suffix in {".pyc", ".pyo"}:
                continue
            yield path


def _find_banned_refs(path: Path):
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return []
    hits = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        for pattern, label in BANNED_PATTERNS.items():
            if re.search(pattern, line):
                hits.append(f"{path.relative_to(REPO_ROOT)}:{lineno}: {label}: {line.strip()}")
    return hits


def _iter_supported_config_files():
    for root in SUPPORTED_CONFIG_ROOTS:
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            if "__pycache__" in path.parts:
                continue
            if path.suffix in {".pyc", ".pyo"}:
                continue
            yield path


def test_supported_docs_have_no_pem_references():
    failures = []
    for path in SUPPORTED_DOCS:
        failures.extend(_find_banned_refs(path))
    if failures:
        pytest.fail("Supported docs still contain PEM references:\n" + "\n".join(failures))


def test_supported_scripts_have_no_pem_references():
    failures = []
    for path in _iter_supported_script_files():
        failures.extend(_find_banned_refs(path))
    if failures:
        pytest.fail("Supported scripts still contain unsupported SSH/PEM references:\n" + "\n".join(failures))


def test_supported_configs_have_no_ssh_or_pem_references():
    failures = []
    for path in _iter_supported_config_files():
        failures.extend(_find_banned_refs(path))
    if failures:
        pytest.fail("Supported configs still contain unsupported SSH/PEM references:\n" + "\n".join(failures))


def test_legacy_payload_assets_are_quarantined_out_of_runtime_bundle():
    assert not (REPO_ROOT / "daylily_ec" / "resources" / "payload" / "bin" / "legacy").exists()
    assert (
        REPO_ROOT / "daylily_ec" / "resources" / "payload" / "quarantine" / "bin" / "legacy"
    ).is_dir()
