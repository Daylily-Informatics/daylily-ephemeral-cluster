from __future__ import annotations

import importlib.util
from importlib.machinery import SourceFileLoader
from pathlib import Path
import subprocess


REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_day_clone():
    script_path = REPO_ROOT / "bin" / "headnode_utils" / "day-clone"
    loader = SourceFileLoader("day_clone_under_test", str(script_path))
    spec = importlib.util.spec_from_loader("day_clone_under_test", loader)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_configs(
    tmp_path: Path,
    *,
    include_ssh_url: bool = True,
) -> tuple[Path, Path, Path]:
    config_dir = tmp_path / "config"
    clone_root = tmp_path / "analysis_results"
    clone_root.mkdir()
    config_dir.mkdir()
    global_config = config_dir / "daylily_cli_global.yaml"
    global_config.write_text(
        f"daylily:\n  analysis_root: {clone_root}\n",
        encoding="utf-8",
    )
    ssh_line = "    ssh_url: git@github.com:Daylily-Informatics/test-repo.git\n" if include_ssh_url else ""
    available_repos = config_dir / "daylily_available_repositories.yaml"
    available_repos.write_text(
        "default_repository: test-repo\n"
        "repositories:\n"
        "  test-repo:\n"
        "    https_url: https://github.com/Daylily-Informatics/test-repo.git\n"
        f"{ssh_line}"
        "    default_ref: main\n"
        "    relative_path: test-repo\n",
        encoding="utf-8",
    )
    return global_config, available_repos, clone_root


def _patch_day_clone_paths(module, global_config: Path, available_repos: Path, monkeypatch) -> None:
    monkeypatch.setattr(module, "GLOBAL_CONFIG_PATH", str(global_config))
    monkeypatch.setattr(module, "AVAILABLE_REPOS_PATH", str(available_repos))


def test_day_clone_defaults_to_https_transport(monkeypatch, tmp_path):
    module = _load_day_clone()
    global_config, available_repos, clone_root = _write_configs(tmp_path)
    _patch_day_clone_paths(module, global_config, available_repos, monkeypatch)
    monkeypatch.setenv("USER", "ubuntu")
    clone_calls: list[list[str]] = []

    def fake_run(cmd, check):
        clone_calls.append(cmd)
        assert check is True
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    rc = module.main(["--destination", "analysis", "--repository", "test-repo"])

    assert rc == 0
    assert clone_calls == [
        [
            "git",
            "clone",
            "--branch",
            "main",
            "https://github.com/Daylily-Informatics/test-repo.git",
            str(clone_root / "ubuntu" / "analysis" / "test-repo"),
        ]
    ]


def test_day_clone_ssh_transport_uses_ssh_url(monkeypatch, tmp_path):
    module = _load_day_clone()
    global_config, available_repos, clone_root = _write_configs(tmp_path)
    _patch_day_clone_paths(module, global_config, available_repos, monkeypatch)
    monkeypatch.setenv("USER", "ubuntu")
    clone_calls: list[list[str]] = []

    def fake_run(cmd, check):
        clone_calls.append(cmd)
        assert check is True
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    rc = module.main(["--destination", "analysis", "--repository", "test-repo", "-w", "ssh"])

    assert rc == 0
    assert clone_calls == [
        [
            "git",
            "clone",
            "--branch",
            "main",
            "git@github.com:Daylily-Informatics/test-repo.git",
            str(clone_root / "ubuntu" / "analysis" / "test-repo"),
        ]
    ]


def test_day_clone_ssh_transport_requires_ssh_url(monkeypatch, tmp_path, capsys):
    module = _load_day_clone()
    global_config, available_repos, _clone_root = _write_configs(tmp_path, include_ssh_url=False)
    _patch_day_clone_paths(module, global_config, available_repos, monkeypatch)
    monkeypatch.setenv("USER", "ubuntu")

    rc = module.main(["--destination", "analysis", "--repository", "test-repo", "-w", "ssh"])

    assert rc == 1
    assert "does not define a ssh_url" in capsys.readouterr().err


def test_packaged_day_clone_matches_source_day_clone():
    source = REPO_ROOT / "bin" / "headnode_utils" / "day-clone"
    packaged = REPO_ROOT / "daylily_ec" / "resources" / "payload" / "bin" / "headnode_utils" / "day-clone"

    assert packaged.read_text(encoding="utf-8") == source.read_text(encoding="utf-8")
