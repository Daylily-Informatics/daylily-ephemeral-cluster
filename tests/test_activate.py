from __future__ import annotations

import os
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
ACTIVATE = REPO_ROOT / "activate"
ENVIRONMENT_YAML = REPO_ROOT / "environment.yaml"


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)


def _fake_conda_script() -> str:
    return """#!/usr/bin/env bash
set -euo pipefail

root="${FAKE_CONDA_ROOT:?}"
log="${FAKE_CONDA_LOG:?}"
printf '%s\\n' "$*" >> "$log"

cmd="${1:-}"
subcmd="${2:-}"
third="${3:-}"

if [[ "$cmd" == "shell.bash" && "$subcmd" == "hook" ]]; then
  printf '%s\\n' 'conda() {' '  "${FAKE_CONDA_EXE}" "$@"' '  rc=$?' '  if [ "${1:-}" = "activate" ] && [ "$rc" -eq 0 ]; then' '    export CONDA_DEFAULT_ENV="${2:-}"' '    export CONDA_PREFIX="${FAKE_CONDA_ROOT}/envs/${2:-}"' '    PATH="${CONDA_PREFIX}/bin:${PATH}"' '    export PATH' '    hash -r 2>/dev/null || true' '  fi' '  return "$rc"' '}'
  exit 0
fi

if [[ "$cmd" == "env" && "$subcmd" == "list" ]]; then
  echo "# conda environments:"
  echo "#"
  echo "base * ${root}/base"
  if [[ -d "${root}/envs/DAY-EC" ]]; then
    echo "DAY-EC ${root}/envs/DAY-EC"
  fi
  exit 0
fi

if [[ "$cmd" == "config" && "$subcmd" == "--set" ]]; then
  exit 0
fi

if [[ "$cmd" == "tos" && "$subcmd" == "accept" ]]; then
  exit 0
fi

if [[ "$cmd" == "env" && "$subcmd" == "create" ]]; then
  env_name=""
  env_file=""
  shift 2
  while [[ $# -gt 0 ]]; do
    case "$1" in
      -n)
        env_name="$2"
        shift 2
        ;;
      -f)
        env_file="$2"
        shift 2
        ;;
      *)
        shift
        ;;
    esac
  done
  mkdir -p "${root}/envs/${env_name}/bin"
  printf '%s\\n' "${env_file}" > "${root}/last_env_file"
  exit 0
fi

if [[ "$cmd" == "env" && "$subcmd" == "update" ]]; then
  env_name=""
  env_file=""
  shift 2
  while [[ $# -gt 0 ]]; do
    case "$1" in
      -n)
        env_name="$2"
        shift 2
        ;;
      -f)
        env_file="$2"
        shift 2
        ;;
      *)
        shift
        ;;
    esac
  done
  mkdir -p "${root}/envs/${env_name}/bin"
  printf '%s\\n' "${env_file}" > "${root}/last_env_update_file"
  cat > "${root}/envs/${env_name}/bin/node" <<'EOF'
#!/usr/bin/env bash
if [[ "${1:-}" == "--version" ]]; then
  echo "env-node-version"
  exit 0
fi
printf 'env-node:%s\\n' "$*"
EOF
  chmod +x "${root}/envs/${env_name}/bin/node"
  cat > "${root}/envs/${env_name}/bin/aws" <<'EOF'
#!/usr/bin/env bash
if [[ "${1:-}" == "--version" ]]; then
  echo "aws-cli/2.22.4"
  exit 0
fi
printf 'env-aws:%s\\n' "$*"
EOF
  chmod +x "${root}/envs/${env_name}/bin/aws"
  cat > "${root}/envs/${env_name}/bin/session-manager-plugin" <<'EOF'
#!/usr/bin/env bash
echo "The Session Manager plugin is installed successfully. Use the AWS CLI to start a session."
EOF
  chmod +x "${root}/envs/${env_name}/bin/session-manager-plugin"
  exit 0
fi

if [[ "$cmd" == "activate" ]]; then
  [[ -d "${root}/envs/${subcmd}" ]]
  exit $?
fi

if [[ "$cmd" == "run" && "$subcmd" == "-n" ]]; then
  env_name="$third"
  shift 3
  if [[ "${1:-}" == "python" && "${2:-}" == "-m" && "${3:-}" == "pip" && "${4:-}" == "install" && "${5:-}" == "--editable" ]]; then
    repo_spec="${6:-}"
    repo_root="${repo_spec%\\[dev]}"
    mkdir -p "${root}/envs/${env_name}/bin"
    printf '%s\\n' "${repo_spec}" > "${root}/last_editable_repo"
    cat > "${root}/envs/${env_name}/bin/daylily-ec" <<'EOF'
#!/usr/bin/env bash
if [[ "${1:-}" == "version" ]]; then
  echo "env-version"
  exit 0
fi
printf 'env-cli:%s\\n' "$*"
EOF
    chmod +x "${root}/envs/${env_name}/bin/daylily-ec"
    cat > "${root}/envs/${env_name}/bin/pcluster" <<'EOF'
#!/usr/bin/env bash
if [[ "${1:-}" == "version" ]]; then
  echo "env-pcluster-version"
  exit 0
fi
printf 'env-pcluster:%s\\n' "$*"
EOF
    chmod +x "${root}/envs/${env_name}/bin/pcluster"
    cat > "${root}/envs/${env_name}/bin/aws" <<'EOF'
#!/usr/bin/env bash
if [[ "${1:-}" == "--version" ]]; then
  echo "aws-cli/2.22.4"
  exit 0
fi
printf 'env-aws:%s\\n' "$*"
EOF
    chmod +x "${root}/envs/${env_name}/bin/aws"
    cat > "${root}/envs/${env_name}/bin/node" <<'EOF'
#!/usr/bin/env bash
if [[ "${1:-}" == "--version" ]]; then
  echo "env-node-version"
  exit 0
fi
printf 'env-node:%s\\n' "$*"
EOF
    chmod +x "${root}/envs/${env_name}/bin/node"
    cat > "${root}/envs/${env_name}/bin/session-manager-plugin" <<'EOF'
#!/usr/bin/env bash
echo "The Session Manager plugin is installed successfully. Use the AWS CLI to start a session."
EOF
    chmod +x "${root}/envs/${env_name}/bin/session-manager-plugin"
    exit 0
  fi

  if [[ "${1:-}" == "daylily-ec" ]]; then
    shift
    exec "${root}/envs/${env_name}/bin/daylily-ec" "$@"
  fi

  if [[ "${1:-}" == "pcluster" ]]; then
    shift
    exec "${root}/envs/${env_name}/bin/pcluster" "$@"
  fi

  if [[ "${1:-}" == "aws" ]]; then
    shift
    exec "${root}/envs/${env_name}/bin/aws" "$@"
  fi

  if [[ "${1:-}" == "session-manager-plugin" ]]; then
    shift
    exec "${root}/envs/${env_name}/bin/session-manager-plugin" "$@"
  fi

  if [[ "${1:-}" == "python" && "${2:-}" == "-c" ]]; then
    if grep -q "bin', 'node'" <<<"${3:-}"; then
      if [[ -x "${root}/envs/${env_name}/bin/node" ]]; then
        exit 0
      fi
      exit 1
    fi
  fi

  exit 1
fi

if [[ "$cmd" == "info" && "$subcmd" == "--base" ]]; then
  printf '%s\\n' "${root}"
  exit 0
fi

exit 1
"""


def _prepare_fake_runtime(
    tmp_path: Path,
    *,
    existing_env: bool = False,
    existing_env_cli: bool = False,
    broken_existing_env_pcluster: bool = False,
    missing_existing_env_node: bool = False,
) -> tuple[dict[str, str], Path]:
    fake_bin = tmp_path / "fake-bin"
    fake_root = tmp_path / "fake-conda-root"
    log_path = tmp_path / "conda.log"

    fake_bin.mkdir()
    (fake_root / "base").mkdir(parents=True)
    if existing_env:
        (fake_root / "envs" / "DAY-EC" / "bin").mkdir(parents=True)

    _write_executable(fake_bin / "conda", _fake_conda_script())
    _write_executable(
        fake_bin / "daylily-ec",
        """#!/usr/bin/env bash
echo "Traceback (most recent call last):" >&2
echo "ModuleNotFoundError: No module named 'cli_core_yo'" >&2
exit 1
""",
    )

    if existing_env and existing_env_cli:
        _write_executable(
            fake_root / "envs" / "DAY-EC" / "bin" / "daylily-ec",
            """#!/usr/bin/env bash
if [[ "${1:-}" == "version" ]]; then
  echo "existing-env-version"
  exit 0
fi
printf 'existing-env:%s\\n' "$*"
""",
        )
        _write_executable(
            fake_root / "envs" / "DAY-EC" / "bin" / "pcluster",
            """#!/usr/bin/env bash
if [[ "${1:-}" == "version" ]]; then
  echo "existing-pcluster-version"
  exit 0
fi
printf 'existing-pcluster:%s\\n' "$*"
""",
        )
        _write_executable(
            fake_root / "envs" / "DAY-EC" / "bin" / "aws",
            """#!/usr/bin/env bash
if [[ "${1:-}" == "--version" ]]; then
  echo "existing-aws-version"
  exit 0
fi
printf 'existing-aws:%s\\n' "$*"
""",
        )
        _write_executable(
            fake_root / "envs" / "DAY-EC" / "bin" / "session-manager-plugin",
            """#!/usr/bin/env bash
echo "The Session Manager plugin is installed successfully. Use the AWS CLI to start a session."
""",
        )
        if not missing_existing_env_node:
            _write_executable(
                fake_root / "envs" / "DAY-EC" / "bin" / "node",
                """#!/usr/bin/env bash
if [[ "${1:-}" == "--version" ]]; then
  echo "existing-node-version"
  exit 0
fi
printf 'existing-node:%s\\n' "$*"
""",
            )

    if existing_env and broken_existing_env_pcluster:
        _write_executable(
            fake_root / "envs" / "DAY-EC" / "bin" / "pcluster",
            """#!/usr/bin/env bash
echo "Traceback (most recent call last):" >&2
echo "ModuleNotFoundError: No module named 'pkg_resources'" >&2
exit 1
""",
        )

    env = os.environ.copy()
    env["FAKE_CONDA_ROOT"] = str(fake_root)
    env["FAKE_CONDA_LOG"] = str(log_path)
    env["FAKE_CONDA_EXE"] = str(fake_bin / "conda")
    env["CONDA_EXE"] = str(fake_bin / "conda")
    env.pop("CONDA_PREFIX", None)
    env.pop("CONDA_DEFAULT_ENV", None)
    env["PATH"] = f"{fake_bin}:{env.get('PATH', '')}"
    env["HOME"] = str(tmp_path)

    return env, log_path


def _source_activate_and_run(env: dict[str, str], command: str) -> subprocess.CompletedProcess[str]:
    script = f'source "{ACTIVATE}" && {command}'
    return subprocess.run(
        ["bash", "--noprofile", "--norc", "-c", script],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_activate_bootstraps_missing_dayec_from_environment_yaml(tmp_path: Path) -> None:
    env, log_path = _prepare_fake_runtime(tmp_path)

    result = _source_activate_and_run(env, "daylily-ec --help")

    assert result.returncode == 0
    assert "env-cli:--help" in result.stdout

    log = log_path.read_text(encoding="utf-8")
    main_tos = "tos accept --override-channels --channel https://repo.anaconda.com/pkgs/main"
    r_tos = "tos accept --override-channels --channel https://repo.anaconda.com/pkgs/r"
    assert main_tos in log
    assert r_tos in log
    assert log.index(main_tos) < log.index(f"env create -n DAY-EC -f {ENVIRONMENT_YAML}")
    assert log.index(r_tos) < log.index(f"env create -n DAY-EC -f {ENVIRONMENT_YAML}")
    assert f"env create -n DAY-EC -f {ENVIRONMENT_YAML}" in log
    assert f"run -n DAY-EC python -m pip install --editable {REPO_ROOT}[dev]" in log


def test_activate_supports_version_and_pricing_help_flow(tmp_path: Path) -> None:
    env, _ = _prepare_fake_runtime(tmp_path)

    result = _source_activate_and_run(
        env,
        "daylily-ec version && AWS_PROFILE=lsmc daylily-ec pricing snapshot --help",
    )

    assert result.returncode == 0
    assert "env-version" in result.stdout
    assert "env-cli:pricing snapshot --help" in result.stdout


def test_activate_repairs_existing_dayec_when_pcluster_smoke_fails(tmp_path: Path) -> None:
    env, log_path = _prepare_fake_runtime(
        tmp_path,
        existing_env=True,
        existing_env_cli=True,
        broken_existing_env_pcluster=True,
    )

    result = _source_activate_and_run(env, "daylily-ec version")

    assert result.returncode == 0
    assert "env-version" in result.stdout
    assert "pkg_resources" not in (result.stdout + result.stderr)
    log = log_path.read_text(encoding="utf-8")
    assert f"env update -n DAY-EC -f {ENVIRONMENT_YAML}" in log
    assert f"run -n DAY-EC python -m pip install --editable {REPO_ROOT}[dev]" in log


def test_activate_repairs_existing_dayec_when_node_smoke_fails(tmp_path: Path) -> None:
    env, log_path = _prepare_fake_runtime(
        tmp_path,
        existing_env=True,
        existing_env_cli=True,
        missing_existing_env_node=True,
    )

    result = _source_activate_and_run(env, "daylily-ec version")

    assert result.returncode == 0
    assert "env-version" in result.stdout
    log = log_path.read_text(encoding="utf-8")
    assert f"env update -n DAY-EC -f {ENVIRONMENT_YAML}" in log
    assert f"run -n DAY-EC python -m pip install --editable {REPO_ROOT}[dev]" in log


def test_activate_does_not_fall_back_to_broken_global_cli(tmp_path: Path) -> None:
    env, _ = _prepare_fake_runtime(tmp_path, existing_env=True, existing_env_cli=True)

    result = _source_activate_and_run(env, "daylily-ec --help")
    combined = result.stdout + result.stderr

    assert result.returncode == 0
    assert "existing-env:--help" in result.stdout
    assert "ModuleNotFoundError" not in combined


def test_activate_reuses_existing_dayec_without_recreating_it(tmp_path: Path) -> None:
    env, log_path = _prepare_fake_runtime(tmp_path, existing_env=True, existing_env_cli=True)

    result = _source_activate_and_run(env, "daylily-ec --help")

    assert result.returncode == 0
    log = log_path.read_text(encoding="utf-8")
    assert "env create -n DAY-EC" not in log
    assert "python -m pip install --editable" not in log


def test_activate_exposes_env_local_operator_clis(tmp_path: Path) -> None:
    env, _ = _prepare_fake_runtime(tmp_path)

    result = _source_activate_and_run(
        env,
        "aws --version && pcluster version && session-manager-plugin",
    )

    assert result.returncode == 0
    assert "aws-cli/2.22.4" in result.stdout
    assert "env-pcluster-version" in result.stdout
    assert "Session Manager plugin is installed successfully" in result.stdout
