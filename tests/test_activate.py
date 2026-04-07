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

if [[ "$cmd" == "activate" ]]; then
  [[ -d "${root}/envs/${subcmd}" ]]
  exit $?
fi

if [[ "$cmd" == "run" && "$subcmd" == "-n" ]]; then
  env_name="$third"
  shift 3
  if [[ "${1:-}" == "python" && "${2:-}" == "-m" && "${3:-}" == "pip" && "${4:-}" == "install" && "${5:-}" == "--editable" ]]; then
    repo_root="${6:-}"
    mkdir -p "${root}/envs/${env_name}/bin"
    printf '%s\\n' "${repo_root}" > "${root}/last_editable_repo"
    cat > "${root}/envs/${env_name}/bin/daylily-ec" <<'EOF'
#!/usr/bin/env bash
if [[ "${1:-}" == "version" ]]; then
  echo "env-version"
  exit 0
fi
printf 'env-cli:%s\\n' "$*"
EOF
    chmod +x "${root}/envs/${env_name}/bin/daylily-ec"
    exit 0
  fi

  if [[ "${1:-}" == "daylily-ec" ]]; then
    shift
    exec "${root}/envs/${env_name}/bin/daylily-ec" "$@"
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

    env = os.environ.copy()
    env["FAKE_CONDA_ROOT"] = str(fake_root)
    env["FAKE_CONDA_LOG"] = str(log_path)
    env["FAKE_CONDA_EXE"] = str(fake_bin / "conda")
    env["CONDA_EXE"] = str(fake_bin / "conda")
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
    assert f"env create -n DAY-EC -f {ENVIRONMENT_YAML}" in log
    assert f"run -n DAY-EC python -m pip install --editable {REPO_ROOT}" in log


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
