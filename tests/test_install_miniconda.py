from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "bin" / "install_miniconda"
ACTIVATE_SCRIPT_PATH = REPO_ROOT / "activate"
PAYLOAD_SCRIPT_PATH = (
    REPO_ROOT / "daylily_ec" / "resources" / "payload" / "bin" / "install_miniconda"
)


EXPECTED_CONDA_CONFIG_LOG = """config --set plugins.auto_accept_tos true
config --add channels bioconda
config --add channels conda-forge
config --get channels
config --remove channels defaults
config --set channel_priority strict
"""

EXPECTED_IDEMPOTENT_CONDA_CONFIG_LOG = """config --set plugins.auto_accept_tos true
config --add channels bioconda
config --add channels conda-forge
config --get channels
config --set channel_priority strict
"""


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)


def _fake_uname_script() -> str:
    return """#!/usr/bin/env bash
set -euo pipefail

if [[ "${1:-}" == "-s" ]]; then
  printf '%s\\n' "${DAY_TEST_UNAME_S:?}"
  exit 0
fi

if [[ "${1:-}" == "-m" ]]; then
  printf '%s\\n' "${DAY_TEST_UNAME_M:?}"
  exit 0
fi

printf '%s\\n' "${DAY_TEST_UNAME_S:?}"
"""


def _fake_downloader_script(name: str, *, fail: bool = False) -> str:
    status_block = "exit 22" if fail else _fake_installer_payload_writer()
    return f"""#!/usr/bin/env bash
set -euo pipefail

log="${{INSTALLER_TEST_LOG:?}}"
printf '{name}:%s\\n' "$*" >> "$log"
{status_block}
"""


def _fake_sha256sum_script() -> str:
    return """#!/usr/bin/env bash
set -euo pipefail

case "$(basename "$1")" in
  Miniconda3-py312_25.7.0-2-MacOSX-arm64.sh)
    printf '%s  %s\\n' '8d67e7824088d7aa3bde938a4fc4365bb39ba1f710104cfe7bd9cfb9a99bd8d2' "$1"
    ;;
  Miniconda3-py312_25.7.0-2-MacOSX-x86_64.sh)
    printf '%s  %s\\n' 'e8f6aed58d708cc544ba6bacbebad86787cb8df56667ff4729ad2fe36af32846' "$1"
    ;;
  Miniconda3-py312_25.7.0-2-Linux-x86_64.sh)
    printf '%s  %s\\n' '188b5d94ab3acefdeaebd7cb470d2fb74a3280563c77075de6e3e1d58d84ab0a' "$1"
    ;;
  Miniconda3-py312_25.7.0-2-Linux-aarch64.sh)
    printf '%s  %s\\n' 'edc03373d75b3a06de594a7f819ad351bd2fa7602854f392107998e62468c783' "$1"
    ;;
  *)
    printf 'unexpected file %s\\n' "$1" >&2
    exit 1
    ;;
esac
"""


def _fake_installer_payload_writer() -> str:
    return """output=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    -o|-O)
      output="$2"
      shift 2
      ;;
    *)
      shift
      ;;
  esac
done

cat > "$output" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

mkdir -p "$HOME/miniconda3/bin"
cat > "$HOME/miniconda3/bin/conda" <<'EOC'
#!/usr/bin/env bash
set -euo pipefail

if [[ "${1:-}" == "init" ]]; then
  rcfile="$HOME/.bashrc"
  if [[ "${2:-}" == "zsh" ]]; then
    rcfile="$HOME/.zshrc"
  fi
  cat > "$rcfile" <<'EOI'
# >>> conda initialize >>>
# <<< conda initialize <<<
EOI
  exit 0
fi

if [[ "${1:-}" == "config" ]]; then
  if [[ "${INSTALLER_FAIL_ON_CONDA_CONFIG:-0}" == "1" ]]; then
    exit 42
  fi
  printf '%s\\n' "$*" >> "${INSTALLER_CONDA_CONFIG_MARKER:?}"
  if [[ "$*" == "config --get channels" ]]; then
    printf -- "--add channels 'bioconda'   # lowest priority\\n"
    printf -- "--add channels 'conda-forge'   # highest priority\\n"
    if [[ -f "${INSTALLER_EXPLICIT_DEFAULTS_STATE:?}" ]]; then
      printf -- "--add channels 'defaults'\\n"
    fi
  fi
  if [[ "$*" == "config --show channels" ]]; then
    printf 'channels:\\n  - conda-forge\\n  - bioconda\\n  - defaults\\n'
  fi
  if [[ "$*" == "config --remove channels defaults" ]]; then
    if [[ ! -f "${INSTALLER_EXPLICIT_DEFAULTS_STATE:?}" ]]; then
      printf "CondaKeyError: 'channels': value 'defaults' not present in config\\n" >&2
      exit 1
    fi
    rm "${INSTALLER_EXPLICIT_DEFAULTS_STATE:?}"
  fi
  exit 0
fi

exit 0
EOC
chmod +x "$HOME/miniconda3/bin/conda"
EOF

chmod +x "$output"
"""


def _run_bash(script: str, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", "--noprofile", "--norc", "-c", script],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def _write_fake_home_conda(home_dir: Path) -> None:
    conda_path = home_dir / "miniconda3" / "bin" / "conda"
    conda_path.parent.mkdir(parents=True, exist_ok=True)
    _write_executable(
        conda_path,
        """#!/usr/bin/env bash
set -euo pipefail

if [[ "${1:-}" == "init" ]]; then
  rcfile="$HOME/.bashrc"
  if [[ "${2:-}" == "zsh" ]]; then
    rcfile="$HOME/.zshrc"
  fi
  cat > "$rcfile" <<'EOF'
# >>> conda initialize >>>
# <<< conda initialize <<<
EOF
  exit 0
fi

if [[ "${1:-}" == "config" ]]; then
  if [[ "${INSTALLER_FAIL_ON_CONDA_CONFIG:-0}" == "1" ]]; then
    exit 42
  fi
  printf '%s\\n' "$*" >> "${INSTALLER_CONDA_CONFIG_MARKER:?}"
  if [[ "$*" == "config --get channels" ]]; then
    printf -- "--add channels 'bioconda'   # lowest priority\\n"
    printf -- "--add channels 'conda-forge'   # highest priority\\n"
    if [[ -f "${INSTALLER_EXPLICIT_DEFAULTS_STATE:?}" ]]; then
      printf -- "--add channels 'defaults'\\n"
    fi
  fi
  if [[ "$*" == "config --show channels" ]]; then
    printf 'channels:\\n  - conda-forge\\n  - bioconda\\n  - defaults\\n'
  fi
  if [[ "$*" == "config --remove channels defaults" ]]; then
    if [[ ! -f "${INSTALLER_EXPLICIT_DEFAULTS_STATE:?}" ]]; then
      printf "CondaKeyError: 'channels': value 'defaults' not present in config\\n" >&2
      exit 1
    fi
    rm "${INSTALLER_EXPLICIT_DEFAULTS_STATE:?}"
  fi
  exit 0
fi

exit 0
""",
    )


def _base_env(tmp_path: Path) -> tuple[dict[str, str], Path, Path]:
    fake_bin = tmp_path / "fake-bin"
    home_dir = tmp_path / "home"
    log_path = tmp_path / "installer.log"
    explicit_defaults_state = tmp_path / "conda-explicit-defaults"

    fake_bin.mkdir()
    home_dir.mkdir()
    explicit_defaults_state.write_text("configured\n", encoding="utf-8")

    _write_executable(fake_bin / "uname", _fake_uname_script())
    _write_executable(fake_bin / "sha256sum", _fake_sha256sum_script())

    env = os.environ.copy()
    env.update(
        {
            "HOME": str(home_dir),
            "INSTALLER_TEST_LOG": str(log_path),
            "INSTALLER_CONDA_CONFIG_MARKER": str(tmp_path / "conda-config.marker"),
            "INSTALLER_EXPLICIT_DEFAULTS_STATE": str(explicit_defaults_state),
            "PATH": f"{fake_bin}:/usr/bin:/bin",
        }
    )
    env.pop("MACHINE", None)
    env.pop("CONDA_PREFIX", None)
    env.pop("CONDA_DEFAULT_ENV", None)
    return env, fake_bin, log_path


@pytest.mark.parametrize(
    ("system_name", "machine_name", "expected_url"),
    [
        (
            "Darwin",
            "arm64",
            "https://repo.anaconda.com/miniconda/Miniconda3-py312_25.7.0-2-MacOSX-arm64.sh",
        ),
        (
            "Darwin",
            "x86_64",
            "https://repo.anaconda.com/miniconda/Miniconda3-py312_25.7.0-2-MacOSX-x86_64.sh",
        ),
        (
            "Linux",
            "arm64",
            "https://repo.anaconda.com/miniconda/Miniconda3-py312_25.7.0-2-Linux-aarch64.sh",
        ),
        (
            "Linux",
            "x86_64",
            "https://repo.anaconda.com/miniconda/Miniconda3-py312_25.7.0-2-Linux-x86_64.sh",
        ),
    ],
)
def test_install_miniconda_selects_expected_installer_url(
    tmp_path: Path,
    system_name: str,
    machine_name: str,
    expected_url: str,
) -> None:
    env, fake_bin, log_path = _base_env(tmp_path)
    env["DAY_TEST_UNAME_S"] = system_name
    env["DAY_TEST_UNAME_M"] = machine_name
    _write_executable(fake_bin / "curl", _fake_downloader_script("curl"))

    result = _run_bash(f'"{SCRIPT_PATH}"', env)

    assert result.returncode == 0, result.stderr
    assert f"curl:-fsSL {expected_url}" in log_path.read_text(encoding="utf-8")
    assert (
        Path(env["INSTALLER_CONDA_CONFIG_MARKER"]).read_text(encoding="utf-8")
        == EXPECTED_CONDA_CONFIG_LOG
    )


def test_install_miniconda_rejects_sourcing(tmp_path: Path) -> None:
    env, _fake_bin, _log_path = _base_env(tmp_path)
    env["DAY_TEST_UNAME_S"] = "Linux"
    env["DAY_TEST_UNAME_M"] = "x86_64"

    result = _run_bash(f'source "{SCRIPT_PATH}"', env)

    assert result.returncode == 2
    assert "install_miniconda must be run, not sourced" in result.stderr


def test_install_miniconda_uses_curl_with_unset_machine(tmp_path: Path) -> None:
    env, fake_bin, log_path = _base_env(tmp_path)
    env["DAY_TEST_UNAME_S"] = "Darwin"
    env["DAY_TEST_UNAME_M"] = "arm64"

    _write_executable(fake_bin / "curl", _fake_downloader_script("curl"))

    result = _run_bash(f'"{SCRIPT_PATH}"', env)

    assert result.returncode == 0, result.stderr
    assert "Miniconda installation successful." in result.stdout

    log_text = log_path.read_text(encoding="utf-8")
    assert (
        "curl:-fsSL https://repo.anaconda.com/miniconda/Miniconda3-py312_25.7.0-2-MacOSX-arm64.sh"
        in log_text
    )
    assert "latest" not in log_text
    assert "wget:" not in log_text
    assert "# >>> conda initialize >>>" in (Path(env["HOME"]) / ".bashrc").read_text(
        encoding="utf-8"
    )
    assert "# >>> conda initialize >>>" in (Path(env["HOME"]) / ".bash_profile").read_text(
        encoding="utf-8"
    )


def test_install_miniconda_falls_back_to_wget_when_curl_fails(tmp_path: Path) -> None:
    env, fake_bin, log_path = _base_env(tmp_path)
    env["DAY_TEST_UNAME_S"] = "Linux"
    env["DAY_TEST_UNAME_M"] = "x86_64"

    _write_executable(fake_bin / "curl", _fake_downloader_script("curl", fail=True))
    _write_executable(fake_bin / "wget", _fake_downloader_script("wget"))

    result = _run_bash(f'"{SCRIPT_PATH}"', env)

    assert result.returncode == 0, result.stderr

    log_text = log_path.read_text(encoding="utf-8")
    assert (
        "curl:-fsSL https://repo.anaconda.com/miniconda/Miniconda3-py312_25.7.0-2-Linux-x86_64.sh"
        in log_text
    )
    assert (
        "wget:-q https://repo.anaconda.com/miniconda/Miniconda3-py312_25.7.0-2-Linux-x86_64.sh"
        in log_text
    )
    assert "latest" not in log_text


def test_install_miniconda_fails_when_auto_tos_config_fails(tmp_path: Path) -> None:
    env, fake_bin, _log_path = _base_env(tmp_path)
    env["DAY_TEST_UNAME_S"] = "Linux"
    env["DAY_TEST_UNAME_M"] = "x86_64"
    env["INSTALLER_FAIL_ON_CONDA_CONFIG"] = "1"

    _write_executable(fake_bin / "curl", _fake_downloader_script("curl"))

    result = _run_bash(f'"{SCRIPT_PATH}"', env)

    assert result.returncode == 42


def test_activate_configures_user_scoped_conda_tos_auto_acceptance() -> None:
    activate = ACTIVATE_SCRIPT_PATH.read_text(encoding="utf-8")

    assert "conda config --set plugins.auto_accept_tos true" in activate
    assert "conda config --system --set plugins.auto_accept_tos true" not in activate
    assert "sudo" not in activate


def test_install_miniconda_configures_supported_bioconda_channels() -> None:
    installer = SCRIPT_PATH.read_text(encoding="utf-8")

    assert "config --add channels bioconda" in installer
    assert "config --add channels conda-forge" in installer
    assert "config --get channels" in installer
    assert "config --show channels" not in installer
    assert "config --remove channels defaults" in installer
    assert "config --set channel_priority strict" in installer
    assert installer.index("config --add channels bioconda") < installer.index(
        "config --add channels conda-forge"
    )
    assert "Failed to set conda priority" not in installer


def test_install_miniconda_channel_configuration_is_idempotent(tmp_path: Path) -> None:
    env, fake_bin, log_path = _base_env(tmp_path)
    env["DAY_TEST_UNAME_S"] = "Linux"
    env["DAY_TEST_UNAME_M"] = "x86_64"
    _write_fake_home_conda(Path(env["HOME"]))
    _write_executable(fake_bin / "curl", _fake_downloader_script("curl"))

    first = _run_bash(f'"{SCRIPT_PATH}"', env)
    second = _run_bash(f'"{SCRIPT_PATH}"', env)

    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr
    assert not log_path.exists() or "curl:" not in log_path.read_text(encoding="utf-8")
    config_log = Path(env["INSTALLER_CONDA_CONFIG_MARKER"]).read_text(encoding="utf-8")
    assert config_log == EXPECTED_CONDA_CONFIG_LOG + EXPECTED_IDEMPOTENT_CONDA_CONFIG_LOG
    assert config_log.count("config --remove channels defaults") == 1
    assert not Path(env["INSTALLER_EXPLICIT_DEFAULTS_STATE"]).exists()


def test_install_miniconda_repairs_shell_init_when_home_miniconda_exists(tmp_path: Path) -> None:
    env, fake_bin, log_path = _base_env(tmp_path)
    env["DAY_TEST_UNAME_S"] = "Linux"
    env["DAY_TEST_UNAME_M"] = "x86_64"
    _write_fake_home_conda(Path(env["HOME"]))
    _write_executable(fake_bin / "curl", _fake_downloader_script("curl"))

    result = _run_bash(f'"{SCRIPT_PATH}"', env)

    assert result.returncode == 0, result.stderr
    assert "already installed at" in result.stdout
    assert not log_path.exists() or "curl:" not in log_path.read_text(encoding="utf-8")
    assert "# >>> conda initialize >>>" in (Path(env["HOME"]) / ".bashrc").read_text(
        encoding="utf-8"
    )
    assert "# >>> conda initialize >>>" in (Path(env["HOME"]) / ".bash_profile").read_text(
        encoding="utf-8"
    )


def test_install_miniconda_payload_mirror_matches_repo_script() -> None:
    assert SCRIPT_PATH.read_text(encoding="utf-8") == PAYLOAD_SCRIPT_PATH.read_text(
        encoding="utf-8"
    )
