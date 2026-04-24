from __future__ import annotations

import re
import subprocess
import tomllib
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
REPO_ENV = REPO_ROOT / "environment.yaml"
PAYLOAD_ENV = REPO_ROOT / "daylily_ec" / "resources" / "payload" / "environment.yaml"
INIT_DAYEC = REPO_ROOT / "bin" / "init_dayec"
PAYLOAD_INIT_DAYEC = REPO_ROOT / "daylily_ec" / "resources" / "payload" / "bin" / "init_dayec"
PYPROJECT = REPO_ROOT / "pyproject.toml"

ACTIVE_ENV_FILES = [
    REPO_ROOT / "activate",
    INIT_DAYEC,
    PAYLOAD_INIT_DAYEC,
    REPO_ROOT / "README.md",
    REPO_ROOT / "README.md.bland",
    REPO_ROOT / "docs" / "DAY_EC_ENVIRONMENT.md",
    REPO_ROOT / "docs" / "aws_setup.md",
    REPO_ROOT / "docs" / "cli_reference.md",
    REPO_ROOT / "docs" / "monitoring_and_troubleshooting.md",
    REPO_ROOT / "docs" / "operations.md",
    REPO_ROOT / "docs" / "overview.md",
    REPO_ROOT / "docs" / "pip_install.md",
    REPO_ROOT / "docs" / "quickest_start.md",
    REPO_ROOT / "docs" / "testing_and_debugging.md",
    REPO_ROOT / "docs" / "ultra_rapid_start.md",
]

RETIRED_MINER_PATTERNS = (
    "xmrig",
    "REGSUB_XMR",
    "xmr_miner",
    "mine_cron",
    "/fsx/miners",
    r"\bminers?\b",
    r"\bmining\b",
    r"\bmonero\b",
    "monero_mining",
    "enable_xmr",
    "xmr_a192",
    "xmr_b192",
)


def _load_env(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _dep_name(raw: str) -> str:
    value = raw.strip()
    value = re.split(r"[<>=!~ ]", value, maxsplit=1)[0]
    value = value.split("[", maxsplit=1)[0]
    return value.lower()


def test_payload_environment_yaml_matches_repo_environment_yaml() -> None:
    assert PAYLOAD_ENV.read_text(encoding="utf-8") == REPO_ENV.read_text(encoding="utf-8")


def test_init_dayec_scripts_bootstrap_from_environment_yaml() -> None:
    expected = 'env_yaml="${RES_DIR}/environment.yaml"'
    assert expected in INIT_DAYEC.read_text(encoding="utf-8")
    assert expected in PAYLOAD_INIT_DAYEC.read_text(encoding="utf-8")


def test_init_dayec_installs_repo_checkout_without_extras() -> None:
    expected = 'pip_args+=(--editable "${repo_root}")'
    assert expected in INIT_DAYEC.read_text(encoding="utf-8")
    assert expected in PAYLOAD_INIT_DAYEC.read_text(encoding="utf-8")


def test_environment_yaml_is_limited_to_conda_operator_tooling() -> None:
    env = _load_env(REPO_ENV)
    deps = env["dependencies"]
    assert all(isinstance(dep, str) for dep in deps)

    dep_names = {_dep_name(dep) for dep in deps}
    required = {
        "python",
        "pip",
        "awscli",
        "aws-session-manager-plugin",
        "bash",
        "jq",
        "yq",
        "rclone",
        "nodejs",
        "fd-find",
        "parallel",
        "perl",
    }
    disallowed = {
        "boto3",
        "pyyaml",
        "ruamel.yaml",
        "pydantic",
        "pydantic-settings",
        "typer",
        "pytest",
        "pytest-cov",
        "moto",
        "black",
        "ruff",
        "mypy",
        "ipython",
        "yamllint",
        "requests",
        "tabulate",
        "python-dateutil",
    }

    assert required <= dep_names
    assert dep_names.isdisjoint(disallowed)


def test_pyproject_declares_expected_runtime_python_dependencies() -> None:
    project = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    deps = {_dep_name(dep) for dep in project["project"]["dependencies"]}
    expected = {
        "aws-parallelcluster",
        "boto3",
        "cli-core-yo",
        "pydantic",
        "pydantic-settings",
        "pyyaml",
        "python-dateutil",
        "requests",
        "ruamel.yaml",
        "setuptools",
        "tabulate",
        "typer",
    }
    assert expected <= deps
    assert "optional-dependencies" not in project["project"]


def test_pyproject_declares_cli_entrypoints() -> None:
    project = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    scripts = project["project"]["scripts"]

    assert scripts["daylily-ec"] == "daylily_ec.cli:main"
    assert scripts["dyec"] == "daylily_ec.cli:main"


def test_legacy_day_env_surfaces_are_not_active() -> None:
    banned_patterns = (
        r"config/day/daycli\.yaml",
        r"\bDAYOA\b",
        r"day_env_installer\.sh",
    )
    failures: list[str] = []
    for path in ACTIVE_ENV_FILES:
        text = path.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), start=1):
            if any(re.search(pattern, line) for pattern in banned_patterns):
                failures.append(f"{path.relative_to(REPO_ROOT)}:{lineno}: {line.strip()}")

    assert not failures, "Active files still reference retired env surfaces:\n" + "\n".join(
        failures
    )


def test_legacy_day_env_assets_are_archived_or_quarantined() -> None:
    assert not (REPO_ROOT / "config" / "day" / "daycli.yaml").exists()
    assert not (REPO_ROOT / "config" / "day" / "day.yaml").exists()
    assert not (REPO_ROOT / "config" / "day" / "day_env_installer.sh").exists()
    assert not (REPO_ROOT / "config" / "day" / "conda_base.yaml").exists()
    assert not (
        REPO_ROOT / "daylily_ec" / "resources" / "payload" / "config" / "day" / "day.yaml"
    ).exists()
    assert not (
        REPO_ROOT
        / "daylily_ec"
        / "resources"
        / "payload"
        / "config"
        / "day"
        / "day_env_installer.sh"
    ).exists()
    assert not (
        REPO_ROOT / "daylily_ec" / "resources" / "payload" / "config" / "day" / "conda_base.yaml"
    ).exists()

    assert (REPO_ROOT / "docs" / "archive" / "legacy-dayoa-env" / "day.yaml").is_file()
    assert (REPO_ROOT / "docs" / "archive" / "legacy-dayoa-env" / "day_env_installer.sh").is_file()
    assert (REPO_ROOT / "docs" / "archive" / "legacy-dayoa-env" / "conda_base.yaml").is_file()
    assert (
        REPO_ROOT
        / "daylily_ec"
        / "resources"
        / "payload"
        / "quarantine"
        / "config"
        / "day"
        / "day.yaml"
    ).is_file()
    assert (
        REPO_ROOT
        / "daylily_ec"
        / "resources"
        / "payload"
        / "quarantine"
        / "config"
        / "day"
        / "day_env_installer.sh"
    ).is_file()
    assert (
        REPO_ROOT
        / "daylily_ec"
        / "resources"
        / "payload"
        / "quarantine"
        / "config"
        / "day"
        / "conda_base.yaml"
    ).is_file()


def test_tracked_files_do_not_reintroduce_retired_miner_support() -> None:
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    failures: list[str] = []
    ignored_paths = {"tests/test_environment_contract.py"}

    for rel_path in result.stdout.splitlines():
        if rel_path in ignored_paths:
            continue
        path = REPO_ROOT / rel_path
        if not path.is_file():
            continue
        for pattern in RETIRED_MINER_PATTERNS:
            if re.search(pattern, rel_path, flags=re.IGNORECASE):
                failures.append(f"{rel_path}: path contains retired miner marker {pattern!r}")

        try:
            text = path.read_text(encoding="utf-8")
        except (FileNotFoundError, UnicodeDecodeError):
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            for pattern in RETIRED_MINER_PATTERNS:
                if re.search(pattern, line, flags=re.IGNORECASE):
                    failures.append(
                        f"{rel_path}:{lineno}: contains retired miner marker {pattern!r}"
                    )

    assert not failures, "Tracked files still contain retired miner support:\n" + "\n".join(
        failures
    )
