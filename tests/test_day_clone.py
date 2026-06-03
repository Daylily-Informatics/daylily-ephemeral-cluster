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
    ssh_line = (
        "    ssh_url: git@github.com:Daylily-Informatics/test-repo.git\n" if include_ssh_url else ""
    )
    available_repos = config_dir / "daylily_pipeline_command_catalog.yaml"
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


def _patch_cluster_name_source(module, monkeypatch, tmp_path: Path, text: str = "stack_name=dyec-515\n") -> Path:
    cfnconfig = tmp_path / "cfnconfig"
    cfnconfig.write_text(text, encoding="utf-8")
    monkeypatch.setattr(module, "CLUSTER_NAME_CONFIG_PATHS", (str(cfnconfig),))
    for key in module.CLUSTER_NAME_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    return cfnconfig


def _disable_cluster_name_sources(module, monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(module, "CLUSTER_NAME_CONFIG_PATHS", (str(tmp_path / "missing-cfnconfig"),))
    for key in module.CLUSTER_NAME_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


def test_day_clone_defaults_to_headnode_cluster_name_and_https_transport(monkeypatch, tmp_path):
    module = _load_day_clone()
    global_config, available_repos, clone_root = _write_configs(tmp_path)
    _patch_day_clone_paths(module, global_config, available_repos, monkeypatch)
    _patch_cluster_name_source(module, monkeypatch, tmp_path)
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
            str(clone_root / "dyec-515" / "analysis" / "test-repo"),
        ]
    ]


def test_day_clone_short_destination_and_tag_clone_default_repository(monkeypatch, tmp_path):
    module = _load_day_clone()
    global_config, available_repos, clone_root = _write_configs(tmp_path)
    _patch_day_clone_paths(module, global_config, available_repos, monkeypatch)
    _patch_cluster_name_source(module, monkeypatch, tmp_path)
    clone_calls: list[list[str]] = []

    def fake_run(cmd, check):
        clone_calls.append(cmd)
        assert check is True
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    rc = module.main(["-d", "analysis", "-t", "2.0.44"])

    assert rc == 0
    assert clone_calls == [
        [
            "git",
            "clone",
            "--branch",
            "2.0.44",
            "https://github.com/Daylily-Informatics/test-repo.git",
            str(clone_root / "dyec-515" / "analysis" / "test-repo"),
        ]
    ]


def test_day_clone_short_tag_still_requires_destination(monkeypatch, tmp_path, capsys):
    module = _load_day_clone()
    global_config, available_repos, _clone_root = _write_configs(tmp_path)
    _patch_day_clone_paths(module, global_config, available_repos, monkeypatch)

    rc = module.main(["-t", "2.0.44"])

    assert rc == 1
    assert "--destination (-d) is required" in capsys.readouterr().err


def test_day_clone_prefers_exported_cluster_name_when_executing_entity_unset(monkeypatch, tmp_path):
    module = _load_day_clone()
    global_config, available_repos, clone_root = _write_configs(tmp_path)
    _patch_day_clone_paths(module, global_config, available_repos, monkeypatch)
    _disable_cluster_name_sources(module, monkeypatch, tmp_path)
    monkeypatch.setenv("DAYLILY_CLUSTER_NAME", "env-cluster")
    clone_calls: list[list[str]] = []

    def fake_run(cmd, check):
        clone_calls.append(cmd)
        assert check is True
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    rc = module.main(["--destination", "analysis", "--repository", "test-repo"])

    assert rc == 0
    assert clone_calls[0][-1] == str(clone_root / "env-cluster" / "analysis" / "test-repo")


def test_day_clone_requires_cluster_identity_when_executing_entity_unset(monkeypatch, tmp_path, capsys):
    module = _load_day_clone()
    global_config, available_repos, _clone_root = _write_configs(tmp_path)
    _patch_day_clone_paths(module, global_config, available_repos, monkeypatch)
    _disable_cluster_name_sources(module, monkeypatch, tmp_path)

    rc = module.main(["--destination", "analysis", "--repository", "test-repo"])

    assert rc == 1
    assert "ParallelCluster cluster identity is unavailable" in capsys.readouterr().err


def test_day_clone_uses_explicit_executing_entity(monkeypatch, tmp_path):
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

    rc = module.main(
        [
            "--destination",
            "analysis",
            "--executing-entity",
            "ursa",
            "--repository",
            "test-repo",
        ]
    )

    assert rc == 0
    assert clone_calls[0][-1] == str(clone_root / "ursa" / "analysis" / "test-repo")


def test_day_clone_rejects_unsafe_executing_entity(monkeypatch, tmp_path, capsys):
    module = _load_day_clone()
    global_config, available_repos, _clone_root = _write_configs(tmp_path)
    _patch_day_clone_paths(module, global_config, available_repos, monkeypatch)

    rc = module.main(
        [
            "--destination",
            "analysis",
            "--executing-entity",
            "../bad",
            "--repository",
            "test-repo",
        ]
    )

    assert rc == 1
    assert "executing_entity" in capsys.readouterr().err


def test_day_clone_ssh_transport_uses_ssh_url(monkeypatch, tmp_path):
    module = _load_day_clone()
    global_config, available_repos, clone_root = _write_configs(tmp_path)
    _patch_day_clone_paths(module, global_config, available_repos, monkeypatch)
    _patch_cluster_name_source(module, monkeypatch, tmp_path)
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
            str(clone_root / "dyec-515" / "analysis" / "test-repo"),
        ]
    ]


def test_day_clone_ssh_transport_requires_ssh_url(monkeypatch, tmp_path, capsys):
    module = _load_day_clone()
    global_config, available_repos, _clone_root = _write_configs(tmp_path, include_ssh_url=False)
    _patch_day_clone_paths(module, global_config, available_repos, monkeypatch)
    _patch_cluster_name_source(module, monkeypatch, tmp_path)

    rc = module.main(["--destination", "analysis", "--repository", "test-repo", "-w", "ssh"])

    assert rc == 1
    assert "does not define a ssh_url" in capsys.readouterr().err


def test_day_clone_requires_explicit_default_repository(monkeypatch, tmp_path, capsys):
    module = _load_day_clone()
    global_config, available_repos, _clone_root = _write_configs(tmp_path)
    available_repos.write_text(
        "repositories:\n"
        "  test-repo:\n"
        "    https_url: https://github.com/Daylily-Informatics/test-repo.git\n"
        "    default_ref: main\n"
        "    relative_path: test-repo\n",
        encoding="utf-8",
    )
    _patch_day_clone_paths(module, global_config, available_repos, monkeypatch)

    rc = module.main(["--destination", "analysis"])

    assert rc == 2
    assert "Missing default_repository" in capsys.readouterr().err


def test_day_clone_list_accepts_real_repository_catalog(monkeypatch, tmp_path, capsys):
    module = _load_day_clone()
    global_config, available_repos, _clone_root = _write_configs(tmp_path)
    available_repos.write_text(
        (REPO_ROOT / "config" / "daylily_pipeline_command_catalog.yaml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    _patch_day_clone_paths(module, global_config, available_repos, monkeypatch)

    rc = module.main(["--list"])

    out = capsys.readouterr()
    assert rc == 0
    assert "day-clone --repository <repo-key> --destination <analysis-id> --git-tag <ref>" in out.out
    assert "day-clone -d <analysis-id> -t <ref>" in out.out
    assert "daylily-omics-analysis" in out.out
    assert "Error:" not in out.err


def test_day_clone_list_accepts_list_valued_command_metadata(monkeypatch, tmp_path, capsys):
    module = _load_day_clone()
    global_config, available_repos, _clone_root = _write_configs(tmp_path)
    available_repos.write_text(
        "command_catalog_version: 1\n"
        "default_repository: test-repo\n"
        "repositories:\n"
        "  test-repo:\n"
        "    display_name: Test Repo\n"
        "    https_url: https://github.com/Daylily-Informatics/test-repo.git\n"
        "    default_ref: main\n"
        "    relative_path: test-repo\n"
        "    analysis_commands:\n"
        "      - command_id: sample_command\n"
        "        targets:\n"
        "          - produce_alignstats\n",
        encoding="utf-8",
    )
    _patch_day_clone_paths(module, global_config, available_repos, monkeypatch)

    rc = module.main(["--list"])

    assert rc == 0
    assert "test-repo: Test Repo" in capsys.readouterr().out


def test_day_clone_invalid_available_repositories_yaml_exits_2(monkeypatch, tmp_path, capsys):
    module = _load_day_clone()
    global_config, available_repos, _clone_root = _write_configs(tmp_path)
    available_repos.write_text(
        "default_repository: [unterminated\n",
        encoding="utf-8",
    )
    _patch_day_clone_paths(module, global_config, available_repos, monkeypatch)

    rc = module.main(["--list"])

    err = capsys.readouterr().err
    assert rc == 2
    assert "Invalid YAML" in err
    assert str(available_repos) in err


def test_packaged_day_clone_matches_source_day_clone():
    source = REPO_ROOT / "bin" / "headnode_utils" / "day-clone"
    packaged = (
        REPO_ROOT / "daylily_ec" / "resources" / "payload" / "bin" / "headnode_utils" / "day-clone"
    )

    assert packaged.read_text(encoding="utf-8") == source.read_text(encoding="utf-8")
