from __future__ import annotations

import importlib.util
import io
from importlib.machinery import SourceFileLoader
from pathlib import Path
from types import SimpleNamespace


REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_helper():
    script_path = REPO_ROOT / "bin" / "headnode_utils" / "daylily-github-credential"
    loader = SourceFileLoader("daylily_github_credential_under_test", str(script_path))
    spec = importlib.util.spec_from_loader("daylily_github_credential_under_test", loader)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_reference(path: Path) -> None:
    path.write_text(
        '{"config_version": 1, "region": "us-west-2", "secret_arn": "arn:aws:secretsmanager:us-west-2:123456789012:secret:headnode-token"}\n',
        encoding="utf-8",
    )
    path.chmod(0o600)


def test_helper_returns_token_only_for_allowlisted_lsmc_repository(monkeypatch, tmp_path, capsys):
    module = _load_helper()
    token_config = tmp_path / "github_token.json"
    _write_reference(token_config)
    monkeypatch.setattr(module, "CONFIG_PATH", token_config)
    calls: list[list[str]] = []

    def fake_run(command, **kwargs):
        calls.append(command)
        assert kwargs["capture_output"] is True
        assert kwargs["env"]["AWS_PAGER"] == ""
        return SimpleNamespace(returncode=0, stdout="github-token-value\n", stderr="")

    monkeypatch.setattr(module.subprocess, "run", fake_run)
    monkeypatch.setattr(
        module.sys,
        "stdin",
        io.StringIO(
            "protocol=https\nhost=github.com\npath=lsmc-bio/daylily-omics-analysis.git\n\n"
        ),
    )
    monkeypatch.setattr(module.sys, "argv", ["daylily-github-credential", "get"])

    assert module.main() == 0
    assert capsys.readouterr().out == "username=x-access-token\npassword=github-token-value\n"
    assert calls == [
        [
            "aws",
            "secretsmanager",
            "get-secret-value",
            "--region",
            "us-west-2",
            "--secret-id",
            "arn:aws:secretsmanager:us-west-2:123456789012:secret:headnode-token",
            "--query",
            "SecretString",
            "--output",
            "text",
            "--no-cli-pager",
        ]
    ]


def test_helper_does_not_disclose_token_for_any_other_repository(monkeypatch, tmp_path, capsys):
    module = _load_helper()
    token_config = tmp_path / "github_token.json"
    _write_reference(token_config)
    monkeypatch.setattr(module, "CONFIG_PATH", token_config)
    monkeypatch.setattr(
        module.subprocess,
        "run",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("must not read a token")),
    )
    monkeypatch.setattr(
        module.sys,
        "stdin",
        io.StringIO("protocol=https\nhost=github.com\npath=lsmc-bio/other-repo.git\n\n"),
    )
    monkeypatch.setattr(module.sys, "argv", ["daylily-github-credential", "get"])

    assert module.main() == 0
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_helper_rejects_world_readable_token_reference(monkeypatch, tmp_path, capsys):
    module = _load_helper()
    token_config = tmp_path / "github_token.json"
    _write_reference(token_config)
    token_config.chmod(0o644)
    monkeypatch.setattr(module, "CONFIG_PATH", token_config)
    monkeypatch.setattr(
        module.sys,
        "stdin",
        io.StringIO(
            "protocol=https\nhost=github.com\npath=lsmc-bio/daylily-ephemeral-cluster.git\noperation=get\n\n"
        ),
    )

    assert module.main() == 1
    assert "must not be group/world-readable" in capsys.readouterr().err


def test_packaged_helper_matches_source() -> None:
    source = REPO_ROOT / "bin" / "headnode_utils" / "daylily-github-credential"
    packaged = (
        REPO_ROOT
        / "daylily_ec"
        / "resources"
        / "payload"
        / "bin"
        / "headnode_utils"
        / "daylily-github-credential"
    )
    assert packaged.read_text(encoding="utf-8") == source.read_text(encoding="utf-8")
