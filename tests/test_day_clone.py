from __future__ import annotations

import importlib.util
from importlib.machinery import SourceFileLoader
import os
from pathlib import Path
import shlex
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
    clone_transport: str = "https",
    auth_mode: str = "none",
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
        f"    clone_transport: {clone_transport}\n"
        f"    auth_mode: {auth_mode}\n"
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


def _patch_cluster_name_source(
    module, monkeypatch, tmp_path: Path, text: str = "stack_name=dyec-515\n"
) -> Path:
    cfnconfig = tmp_path / "cfnconfig"
    cfnconfig.write_text(text, encoding="utf-8")
    monkeypatch.setattr(module, "CLUSTER_NAME_CONFIG_PATHS", (str(cfnconfig),))
    for key in module.CLUSTER_NAME_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    return cfnconfig


def _patch_deploy_key_files(module, monkeypatch, tmp_path: Path) -> tuple[Path, Path]:
    deploy_config = tmp_path / "github_deploy_keys.yaml"
    deploy_config.write_text(
        "config_version: 1\n"
        "deploy_keys:\n"
        "  test-repo:\n"
        "    region: us-west-2\n"
        "    secret_arn: arn:aws:secretsmanager:us-west-2:123456789012:secret:test\n",
        encoding="utf-8",
    )
    known_hosts = tmp_path / "github_known_hosts"
    known_hosts.write_text("github.com ssh-ed25519 test-host-key\n", encoding="utf-8")
    monkeypatch.setattr(module, "DEPLOY_KEYS_PATH", str(deploy_config))
    monkeypatch.setattr(module, "GITHUB_KNOWN_HOSTS_PATH", str(known_hosts))
    return deploy_config, known_hosts


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


def test_day_clone_accepts_new_lock_initialized_workspace(monkeypatch, tmp_path):
    module = _load_day_clone()
    global_config, available_repos, clone_root = _write_configs(tmp_path)
    _patch_day_clone_paths(module, global_config, available_repos, monkeypatch)
    _patch_cluster_name_source(module, monkeypatch, tmp_path)
    workspace = clone_root / "dyec-515" / "analysis"
    (workspace / ".dayoa_agent" / "write.lock").mkdir(parents=True)
    clone_calls: list[list[str]] = []

    def fake_run(cmd, check):
        clone_calls.append(cmd)
        assert check is True
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    rc = module.main(["-d", "analysis", "-t", "2.0.44"])

    assert rc == 0
    assert clone_calls[0][-1] == str(workspace / "test-repo")


def test_day_clone_rejects_lock_initialized_workspace_with_analysis_data(
    monkeypatch, tmp_path, capsys
):
    module = _load_day_clone()
    global_config, available_repos, clone_root = _write_configs(tmp_path)
    _patch_day_clone_paths(module, global_config, available_repos, monkeypatch)
    _patch_cluster_name_source(module, monkeypatch, tmp_path)
    workspace = clone_root / "dyec-515" / "analysis"
    (workspace / ".dayoa_agent" / "write.lock").mkdir(parents=True)
    (workspace / "existing.txt").write_text("analysis data\n", encoding="utf-8")

    rc = module.main(["-d", "analysis", "-t", "2.0.44"])

    assert rc == 1
    assert "already exists" in capsys.readouterr().err


def test_day_clone_full_sha_clones_then_detaches(monkeypatch, tmp_path):
    module = _load_day_clone()
    global_config, available_repos, clone_root = _write_configs(tmp_path)
    _patch_day_clone_paths(module, global_config, available_repos, monkeypatch)
    _patch_cluster_name_source(module, monkeypatch, tmp_path)
    clone_calls: list[list[str]] = []
    commit_sha = "9f442ed1f32ecb19cf0163c41d196974f8198364"
    target = str(clone_root / "dyec-515" / "analysis" / "test-repo")

    def fake_run(cmd, check):
        clone_calls.append(cmd)
        assert check is True
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    rc = module.main(["-d", "analysis", "-t", commit_sha])

    assert rc == 0
    assert clone_calls == [
        [
            "git",
            "clone",
            "https://github.com/Daylily-Informatics/test-repo.git",
            target,
        ],
        ["git", "-C", target, "checkout", "--detach", commit_sha],
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


def test_day_clone_requires_cluster_identity_when_executing_entity_unset(
    monkeypatch, tmp_path, capsys
):
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
    global_config, available_repos, clone_root = _write_configs(
        tmp_path,
        clone_transport="ssh",
    )
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
    global_config, available_repos, _clone_root = _write_configs(
        tmp_path,
        include_ssh_url=False,
        clone_transport="ssh",
    )
    _patch_day_clone_paths(module, global_config, available_repos, monkeypatch)
    _patch_cluster_name_source(module, monkeypatch, tmp_path)

    rc = module.main(["--destination", "analysis", "--repository", "test-repo", "-w", "ssh"])

    assert rc == 1
    assert "does not define a ssh_url" in capsys.readouterr().err


def test_day_clone_aws_deploy_key_uses_strict_temporary_ssh_identity(
    monkeypatch,
    tmp_path,
):
    module = _load_day_clone()
    global_config, available_repos, clone_root = _write_configs(
        tmp_path,
        clone_transport="ssh",
        auth_mode="aws_deploy_key",
    )
    _patch_day_clone_paths(module, global_config, available_repos, monkeypatch)
    _patch_cluster_name_source(module, monkeypatch, tmp_path)
    _patch_deploy_key_files(module, monkeypatch, tmp_path)
    monkeypatch.setattr(
        module,
        "fetch_deploy_key",
        lambda _secret_arn, _region: (
            "-----BEGIN OPENSSH PRIVATE KEY-----\nprivate-test-material\n"
            "-----END OPENSSH PRIVATE KEY-----\n"
        ),
    )
    key_paths: list[str] = []
    clone_calls: list[list[str]] = []

    def fake_run(cmd, **kwargs):
        clone_calls.append(cmd)
        env = kwargs["env"]
        ssh_command = shlex.split(env["GIT_SSH_COMMAND"])
        key_path = ssh_command[ssh_command.index("-i") + 1]
        key_paths.append(key_path)
        assert os.path.isfile(key_path)
        assert oct(os.stat(key_path).st_mode & 0o777) == "0o600"
        assert "IdentitiesOnly=yes" in ssh_command
        assert "StrictHostKeyChecking=yes" in ssh_command
        assert env["GIT_TERMINAL_PROMPT"] == "0"
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    rc = module.main(["--destination", "analysis", "--repository", "test-repo"])

    assert rc == 0
    assert clone_calls[0][0:4] == ["git", "clone", "--branch", "main"]
    assert clone_calls[0][-2] == "git@github.com:Daylily-Informatics/test-repo.git"
    assert clone_calls[0][-1] == str(clone_root / "dyec-515" / "analysis" / "test-repo")
    assert key_paths
    assert all(not os.path.exists(path) for path in key_paths)


def test_day_clone_check_auth_uses_deploy_key_without_destination(monkeypatch, tmp_path):
    module = _load_day_clone()
    global_config, available_repos, _clone_root = _write_configs(
        tmp_path,
        clone_transport="ssh",
        auth_mode="aws_deploy_key",
    )
    _patch_day_clone_paths(module, global_config, available_repos, monkeypatch)
    _patch_deploy_key_files(module, monkeypatch, tmp_path)
    monkeypatch.setattr(
        module,
        "fetch_deploy_key",
        lambda *_args: (
            "-----BEGIN OPENSSH PRIVATE KEY-----\nprivate-test-material\n"
            "-----END OPENSSH PRIVATE KEY-----\n"
        ),
    )
    calls: list[tuple[list[str], dict]] = []

    def fake_run(cmd, **kwargs):
        calls.append((cmd, kwargs))
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    rc = module.main(["--check-auth", "--repository", "test-repo", "--git-tag", "2.0.44"])

    assert rc == 0
    assert calls[0][0] == [
        "git",
        "ls-remote",
        "--exit-code",
        "git@github.com:Daylily-Informatics/test-repo.git",
        "2.0.44",
        "refs/heads/2.0.44",
        "refs/tags/2.0.44",
    ]
    assert "env" in calls[0][1]


def test_day_clone_deploy_key_cleanup_survives_clone_failure(monkeypatch, tmp_path, capsys):
    module = _load_day_clone()
    global_config, available_repos, _clone_root = _write_configs(
        tmp_path,
        clone_transport="ssh",
        auth_mode="aws_deploy_key",
    )
    _patch_day_clone_paths(module, global_config, available_repos, monkeypatch)
    _patch_cluster_name_source(module, monkeypatch, tmp_path)
    _patch_deploy_key_files(module, monkeypatch, tmp_path)
    monkeypatch.setattr(
        module,
        "fetch_deploy_key",
        lambda *_args: (
            "-----BEGIN OPENSSH PRIVATE KEY-----\nprivate-test-material\n"
            "-----END OPENSSH PRIVATE KEY-----\n"
        ),
    )
    key_paths: list[str] = []

    def fake_run(cmd, **kwargs):
        ssh_command = shlex.split(kwargs["env"]["GIT_SSH_COMMAND"])
        key_paths.append(ssh_command[ssh_command.index("-i") + 1])
        raise subprocess.CalledProcessError(128, cmd)

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    rc = module.main(["--destination", "analysis", "--repository", "test-repo"])

    assert rc == 1
    assert "Git clone failed with exit code 128" in capsys.readouterr().err
    assert key_paths
    assert all(not os.path.exists(path) for path in key_paths)


def test_day_clone_rejects_transport_override_for_deploy_key_repo(
    monkeypatch,
    tmp_path,
    capsys,
):
    module = _load_day_clone()
    global_config, available_repos, _clone_root = _write_configs(
        tmp_path,
        clone_transport="ssh",
        auth_mode="aws_deploy_key",
    )
    _patch_day_clone_paths(module, global_config, available_repos, monkeypatch)

    rc = module.main(
        ["--destination", "analysis", "--repository", "test-repo", "--which-one", "https"]
    )

    assert rc == 1
    assert "requires ssh transport" in capsys.readouterr().err


def test_day_clone_requires_explicit_default_repository(monkeypatch, tmp_path, capsys):
    module = _load_day_clone()
    global_config, available_repos, _clone_root = _write_configs(tmp_path)
    available_repos.write_text(
        "repositories:\n"
        "  test-repo:\n"
        "    clone_transport: https\n"
        "    auth_mode: none\n"
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
        (REPO_ROOT / "config" / "daylily_pipeline_command_catalog.yaml").read_text(
            encoding="utf-8"
        ),
        encoding="utf-8",
    )
    _patch_day_clone_paths(module, global_config, available_repos, monkeypatch)

    rc = module.main(["--list"])

    out = capsys.readouterr()
    assert rc == 0
    assert (
        "day-clone --repository <repo-key> --destination <analysis-id> --git-tag <ref>" in out.out
    )
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
        "    clone_transport: https\n"
        "    auth_mode: none\n"
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


def test_packaged_github_known_hosts_matches_source():
    source = REPO_ROOT / "config" / "github_known_hosts"
    packaged = REPO_ROOT / "daylily_ec" / "resources" / "payload" / "config" / "github_known_hosts"

    assert packaged.read_text(encoding="utf-8") == source.read_text(encoding="utf-8")


def test_packaged_squeue_helpers_match_source_helpers():
    for helper in ("sq", "sqq"):
        source = REPO_ROOT / "bin" / "headnode_utils" / helper
        packaged = (
            REPO_ROOT / "daylily_ec" / "resources" / "payload" / "bin" / "headnode_utils" / helper
        )

        assert packaged.read_text(encoding="utf-8") == source.read_text(encoding="utf-8")
