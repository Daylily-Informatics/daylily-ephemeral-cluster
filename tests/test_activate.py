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


def _fake_env_python_script() -> str:
    return """#!/usr/bin/env bash
set -euo pipefail

printf 'python %s\\n' "$*" >> "${FAKE_CONDA_LOG:?}"

if [[ "${1:-}" == "-m" && "${2:-}" == "pip" && "${3:-}" == "install" && "${4:-}" == "--editable" ]]; then
  repo_spec="${5:-}"
  env_bin="$(dirname "$0")"
  printf '%s\\n' "${repo_spec}" > "${FAKE_CONDA_ROOT:?}/last_editable_repo"
  cat > "${env_bin}/daylily-ec" <<'EOF'
#!/usr/bin/env bash
printf 'env-cli:%s\\n' "$*"
EOF
  chmod +x "${env_bin}/daylily-ec"
  exit 0
fi

exit 1
"""


def _fake_conda_script() -> str:
    return """#!/usr/bin/env bash
set -euo pipefail

root="${FAKE_CONDA_ROOT:?}"
log="${FAKE_CONDA_LOG:?}"
printf '%s\\n' "$*" >> "$log"

write_env_python() {
  local env_name="$1"
  mkdir -p "${root}/envs/${env_name}/bin"
  cat > "${root}/envs/${env_name}/bin/python" <<'PYEOF'
""" + _fake_env_python_script().rstrip() + """
PYEOF
  chmod +x "${root}/envs/${env_name}/bin/python"
}

cmd="${1:-}"
subcmd="${2:-}"

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
  write_env_python "${env_name}"
  printf '%s\\n' "${env_file}" > "${root}/last_env_file"
  exit 0
fi

if [[ "$cmd" == "activate" ]]; then
  [[ -d "${root}/envs/${subcmd}" ]]
  exit $?
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
) -> tuple[dict[str, str], Path, Path]:
    fake_bin = tmp_path / "fake-bin"
    fake_root = tmp_path / "fake-conda-root"
    log_path = tmp_path / "commands.log"

    fake_bin.mkdir()
    (fake_root / "base").mkdir(parents=True)
    if existing_env:
        env_bin = fake_root / "envs" / "DAY-EC" / "bin"
        env_bin.mkdir(parents=True)
        _write_executable(env_bin / "python", _fake_env_python_script())
        if existing_env_cli:
            _write_executable(
                env_bin / "daylily-ec",
                """#!/usr/bin/env bash
printf 'existing-env:%s\\n' "$*"
""",
            )

    _write_executable(fake_bin / "conda", _fake_conda_script())
    _write_executable(
        fake_bin / "daylily-ec",
        """#!/usr/bin/env bash
echo "Traceback (most recent call last):" >&2
echo "ModuleNotFoundError: No module named 'cli_core_yo'" >&2
exit 17
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

    return env, log_path, fake_root


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


def test_activate_creates_dayec_activates_and_installs_editable(tmp_path: Path) -> None:
    env, log_path, fake_root = _prepare_fake_runtime(tmp_path)

    result = _source_activate_and_run(
        env,
        'printf "env=%s\\n" "$CONDA_DEFAULT_ENV" && '
        'printf "prefix=%s\\n" "$CONDA_PREFIX" && '
        'printf "cli=%s\\n" "$(type -P daylily-ec)" && '
        'printf "kind=%s\\n" "$(type -t daylily-ec)" && '
        "daylily-ec --help",
    )

    expected_prefix = fake_root / "envs" / "DAY-EC"
    expected_cli = expected_prefix / "bin" / "daylily-ec"
    log = log_path.read_text(encoding="utf-8")
    combined = result.stdout + result.stderr

    assert result.returncode == 0
    assert "env=DAY-EC" in result.stdout
    assert f"prefix={expected_prefix}" in result.stdout
    assert f"cli={expected_cli}" in result.stdout
    assert "kind=file" in result.stdout
    assert "env-cli:--help" in result.stdout
    assert f"env create -n DAY-EC -f {ENVIRONMENT_YAML}" in log
    assert f"python -m pip install --editable {REPO_ROOT}" in log
    assert (fake_root / "last_editable_repo").read_text(encoding="utf-8").strip() == str(REPO_ROOT)
    assert "env update" not in log
    assert "run -n DAY-EC" not in log
    assert "daylily-ec version" not in log
    assert "aws --version" not in log
    assert "pcluster version" not in log
    assert "session-manager-plugin" not in log
    assert "ModuleNotFoundError" not in combined
    assert f"Installing daylily-ephemeral-cluster into DAY-EC from {REPO_ROOT} ..." in result.stderr
    assert f"Installed daylily-ephemeral-cluster into DAY-EC from {REPO_ROOT}." in result.stderr


def test_activate_reuses_existing_dayec_without_create_update_pip_or_smoke_tests(
    tmp_path: Path,
) -> None:
    env, log_path, fake_root = _prepare_fake_runtime(
        tmp_path,
        existing_env=True,
        existing_env_cli=True,
    )

    result = _source_activate_and_run(
        env,
        'printf "prefix=%s\\n" "$CONDA_PREFIX" && daylily-ec --help',
    )

    expected_prefix = fake_root / "envs" / "DAY-EC"
    log = log_path.read_text(encoding="utf-8")

    assert result.returncode == 0
    assert f"prefix={expected_prefix}" in result.stdout
    assert "existing-env:--help" in result.stdout
    assert "env create -n DAY-EC" not in log
    assert "env update" not in log
    assert "pip install" not in log
    assert "run -n DAY-EC" not in log
    assert "daylily-ec version" not in log
    assert "aws --version" not in log
    assert "pcluster version" not in log
    assert "session-manager-plugin" not in log
    assert "Installing daylily-ephemeral-cluster" not in result.stderr


def test_activate_uses_dayec_cli_before_broken_global_path(tmp_path: Path) -> None:
    env, _, fake_root = _prepare_fake_runtime(
        tmp_path,
        existing_env=True,
        existing_env_cli=True,
    )

    result = _source_activate_and_run(
        env,
        'printf "cli=%s\\n" "$(type -P daylily-ec)" && daylily-ec --help',
    )

    expected_cli = fake_root / "envs" / "DAY-EC" / "bin" / "daylily-ec"
    combined = result.stdout + result.stderr

    assert result.returncode == 0
    assert f"cli={expected_cli}" in result.stdout
    assert "existing-env:--help" in result.stdout
    assert "ModuleNotFoundError" not in combined
    assert "fake-bin/daylily-ec" not in result.stdout
