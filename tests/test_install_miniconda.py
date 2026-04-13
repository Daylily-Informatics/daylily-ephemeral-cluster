from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "bin" / "install_miniconda"
PAYLOAD_SCRIPT_PATH = (
    REPO_ROOT / "daylily_ec" / "resources" / "payload" / "bin" / "install_miniconda"
)


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
  exit 0
fi

exit 0
""",
    )


def _base_env(tmp_path: Path) -> tuple[dict[str, str], Path, Path]:
    fake_bin = tmp_path / "fake-bin"
    home_dir = tmp_path / "home"
    log_path = tmp_path / "installer.log"

    fake_bin.mkdir()
    home_dir.mkdir()

    _write_executable(fake_bin / "uname", _fake_uname_script())

    env = os.environ.copy()
    env.update(
        {
            "HOME": str(home_dir),
            "INSTALLER_TEST_LOG": str(log_path),
            "PATH": f"{fake_bin}:/usr/bin:/bin",
        }
    )
    env.pop("MACHINE", None)
    env.pop("CONDA_PREFIX", None)
    env.pop("CONDA_DEFAULT_ENV", None)
    return env, fake_bin, log_path


@pytest.mark.parametrize(
    ("system_name", "machine_name", "expected"),
    [
        ("Darwin", "arm64", "apple_silicon"),
        ("Darwin", "x86_64", "intel_mac"),
        ("Linux", "arm64", "linux_arm"),
        ("Linux", "x86_64", "linux_x86"),
    ],
)
def test_detect_machine_returns_expected_class(
    tmp_path: Path,
    system_name: str,
    machine_name: str,
    expected: str,
) -> None:
    env, _fake_bin, _log_path = _base_env(tmp_path)
    env["DAY_TEST_UNAME_S"] = system_name
    env["DAY_TEST_UNAME_M"] = machine_name

    result = _run_bash(f'source "{SCRIPT_PATH}" && detect_machine', env)

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == expected


def test_install_miniconda_uses_curl_with_unset_machine(tmp_path: Path) -> None:
    env, fake_bin, log_path = _base_env(tmp_path)
    env["DAY_TEST_UNAME_S"] = "Darwin"
    env["DAY_TEST_UNAME_M"] = "arm64"

    _write_executable(fake_bin / "curl", _fake_downloader_script("curl"))

    result = _run_bash(f'"{SCRIPT_PATH}"', env)

    assert result.returncode == 0, result.stderr
    assert "Miniconda installation successful." in result.stdout

    log_text = log_path.read_text(encoding="utf-8")
    assert "curl:-fsSL https://repo.anaconda.com/miniconda/Miniconda3-latest-MacOSX-arm64.sh" in log_text
    assert "wget:" not in log_text
    assert "# >>> conda initialize >>>" in (Path(env["HOME"]) / ".bashrc").read_text(
        encoding="utf-8"
    )
    assert "# >>> conda initialize >>>" in (
        Path(env["HOME"]) / ".bash_profile"
    ).read_text(encoding="utf-8")


def test_install_miniconda_falls_back_to_wget_when_curl_fails(tmp_path: Path) -> None:
    env, fake_bin, log_path = _base_env(tmp_path)
    env["DAY_TEST_UNAME_S"] = "Linux"
    env["DAY_TEST_UNAME_M"] = "x86_64"

    _write_executable(fake_bin / "curl", _fake_downloader_script("curl", fail=True))
    _write_executable(fake_bin / "wget", _fake_downloader_script("wget"))

    result = _run_bash(f'"{SCRIPT_PATH}"', env)

    assert result.returncode == 0, result.stderr

    log_text = log_path.read_text(encoding="utf-8")
    assert "curl:-fsSL https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh" in log_text
    assert "wget:-q https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh" in log_text


def test_install_miniconda_does_not_require_conda_config_accept_channel_terms(tmp_path: Path) -> None:
    env, fake_bin, _log_path = _base_env(tmp_path)
    env["DAY_TEST_UNAME_S"] = "Linux"
    env["DAY_TEST_UNAME_M"] = "x86_64"
    env["INSTALLER_FAIL_ON_CONDA_CONFIG"] = "1"

    _write_executable(fake_bin / "curl", _fake_downloader_script("curl"))

    result = _run_bash(f'"{SCRIPT_PATH}"', env)

    assert result.returncode == 0, result.stderr


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
    assert "# >>> conda initialize >>>" in (
        Path(env["HOME"]) / ".bash_profile"
    ).read_text(encoding="utf-8")


def test_install_miniconda_payload_mirror_matches_repo_script() -> None:
    assert SCRIPT_PATH.read_text(encoding="utf-8") == PAYLOAD_SCRIPT_PATH.read_text(
        encoding="utf-8"
    )
