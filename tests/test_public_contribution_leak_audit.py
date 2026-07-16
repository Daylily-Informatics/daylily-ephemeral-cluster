from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[1] / "scripts" / "public_contribution_leak_audit.py"


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", os.fspath(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _init_repo(tmp_path: Path, *, base_content: str = "baseline\n") -> tuple[Path, str]:
    repo = tmp_path / "public-repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.name", "Test Contributor")
    _git(repo, "config", "user.email", "contributor@example.com")
    (repo / "README.md").write_text(base_content, encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-m", "Initial public baseline")
    return repo, _git(repo, "rev-parse", "HEAD")


def _commit(repo: Path, path: str, content: str, *message_args: str) -> str:
    target = repo / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    _git(repo, "add", path)
    _git(repo, "commit", *message_args)
    return _git(repo, "rev-parse", "HEAD")


def _run(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, os.fspath(SCRIPT), "--repo", os.fspath(repo), *args],
        check=False,
        capture_output=True,
        text=True,
    )


def test_allows_generic_almalinux_parallelcluster_range_and_artifacts(tmp_path: Path) -> None:
    repo, base = _init_repo(tmp_path)
    head = _commit(
        repo,
        "docs/almalinux8.md",
        "Add AlmaLinux 8 support for customer-provided AWS ParallelCluster images.\n",
        "-m",
        "Add AlmaLinux 8 custom image support",
        "-m",
        "Extend AWS ParallelCluster image detection and validation.",
    )
    issue = tmp_path / "issue.md"
    issue.write_text(
        "Add AlmaLinux 8 support for customer-provided parent images.\n",
        encoding="utf-8",
    )
    pr = tmp_path / "pr.md"
    pr.write_text(
        "Tests cover ImageBuilder, Slurm, EFA, and Lustre on AlmaLinux 8.\n",
        encoding="utf-8",
    )

    result = _run(
        repo,
        "--git-range",
        f"{base}..{head}",
        "--artifact",
        os.fspath(issue),
        "--artifact",
        os.fspath(pr),
    )

    assert result.returncode == 0, result.stderr
    assert "PUBLIC CONTRIBUTION AUDIT: PASS" in result.stdout
    assert "git_ranges=1 artifacts=2 commits=1 changed_paths=1" in result.stdout


@pytest.mark.parametrize(
    "fixture_text",
    [
        "Mock custom image fixture: ami-12345678",
        "Mock custom image fixture: ami-000000000000",
        "Official AlmaLinux image owner: 764336703387",
    ],
)
def test_allows_known_public_image_fixtures(tmp_path: Path, fixture_text: str) -> None:
    repo, base = _init_repo(tmp_path)
    head = _commit(
        repo,
        "tests/almalinux8.txt",
        f"{fixture_text}\n",
        "-m",
        "Add generic custom image fixture",
    )

    result = _run(repo, "--git-range", f"{base}..{head}")

    assert result.returncode == 0, result.stderr


def test_scans_diff_paths_and_commit_subjects_and_bodies(tmp_path: Path) -> None:
    repo, base = _init_repo(tmp_path)
    head = _commit(
        repo,
        "docs/lsmc-private.md",
        "Parent image ami-0123456789abcdef0 must stay private.\n",
        "-m",
        "Validate HG003",
        "-m",
        "Do not publish DRAGEN details.",
    )

    result = _run(repo, "--git-range", f"{base}..{head}")

    assert result.returncode == 1
    assert "PUBLIC CONTRIBUTION AUDIT: BLOCKED" in result.stderr
    assert "private_organization_term git-range[1]:changed-path[1]" in result.stderr
    assert "aws_resource_identifier git-range[1]:diff" in result.stderr
    assert "biological_or_sequencing_reference git-range[1]:commit-message[1]" in result.stderr
    assert "vendor_or_product_term git-range[1]:commit-message[1]" in result.stderr
    assert "ami-0123456789abcdef0" not in result.stderr
    assert "HG003" not in result.stderr


def test_scans_each_caller_supplied_text_artifact(tmp_path: Path) -> None:
    repo, _base = _init_repo(tmp_path)
    issue = tmp_path / "issue.md"
    issue.write_text("Upload logs to s3://private-bucket/results/.\n", encoding="utf-8")
    pr = tmp_path / "pr.md"
    pr.write_text("Account 123456789012 owns the test role.\n", encoding="utf-8")
    log = tmp_path / "build.log"
    log.write_text(
        "Processed NA20775 from ILMN run LH01106 on dragain9b successfully.\n",
        encoding="utf-8",
    )

    result = _run(
        repo,
        "--artifact",
        os.fspath(issue),
        "--artifact",
        os.fspath(pr),
        "--artifact",
        os.fspath(log),
    )

    assert result.returncode == 1
    assert "s3_uri artifact[1]:1:" in result.stderr
    assert "aws_account_identifier artifact[2]:1:" in result.stderr
    assert "biological_or_sequencing_reference artifact[3]:1:" in result.stderr
    assert "private_cluster_identifier artifact[3]:1:" in result.stderr
    assert "vendor_or_product_term artifact[3]:1:" in result.stderr
    assert "private-bucket" not in result.stderr
    assert "123456789012" not in result.stderr
    assert "NA20775" not in result.stderr


def test_does_not_scan_unchanged_preexisting_history_or_worktree(tmp_path: Path) -> None:
    repo, base = _init_repo(tmp_path, base_content="DRAGEN private baseline\n")
    head = _commit(
        repo,
        "docs/almalinux.md",
        "AlmaLinux 8 custom image support.\n",
        "-m",
        "Add generic AlmaLinux support",
    )
    (repo / "untracked-private.txt").write_text("HG003\n", encoding="utf-8")

    result = _run(repo, "--git-range", f"{base}..{head}")

    assert result.returncode == 0, result.stderr


def test_does_not_scan_unchanged_hunk_header_context(tmp_path: Path) -> None:
    repo, base = _init_repo(
        tmp_path,
        base_content="PRIVATE_OWNER = 123456789012\nexisting = True\n",
    )
    (repo / "README.md").write_text(
        "PRIVATE_OWNER = 123456789012\nexisting = True\nalmalinux8 = True\n",
        encoding="utf-8",
    )
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-m", "Add generic AlmaLinux fixture")
    head = _git(repo, "rev-parse", "HEAD")

    result = _run(repo, "--git-range", f"{base}..{head}")

    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    "range_value",
    ["HEAD", "HEAD...HEAD", "..HEAD", "HEAD..", "--all..HEAD", "HEAD ..HEAD"],
)
def test_rejects_implicit_or_malformed_ranges(tmp_path: Path, range_value: str) -> None:
    repo, _base = _init_repo(tmp_path)

    result = _run(repo, "--git-range", range_value)

    assert result.returncode == 2
    assert "ERROR" in result.stderr.upper()


def test_rejects_empty_range_and_requires_explicit_inputs(tmp_path: Path) -> None:
    repo, _base = _init_repo(tmp_path)

    no_inputs = _run(repo)
    empty_range = _run(repo, "--git-range", "HEAD..HEAD")

    assert no_inputs.returncode == 2
    assert "at least one --git-range or --artifact is required" in no_inputs.stderr
    assert empty_range.returncode == 2
    assert "must contain at least one commit" in empty_range.stderr


def test_rejects_range_when_base_is_not_an_ancestor(tmp_path: Path) -> None:
    repo, base = _init_repo(tmp_path)
    first_head = _commit(
        repo,
        "first.txt",
        "AlmaLinux 8\n",
        "-m",
        "First branch change",
    )
    _git(repo, "checkout", "-b", "second", base)
    second_head = _commit(
        repo,
        "second.txt",
        "AWS ParallelCluster\n",
        "-m",
        "Second branch change",
    )

    result = _run(repo, "--git-range", f"{first_head}..{second_head}")

    assert result.returncode == 2
    assert "BASE must be an ancestor of HEAD" in result.stderr


def test_fails_closed_for_binary_range_content(tmp_path: Path) -> None:
    repo, base = _init_repo(tmp_path)
    binary = repo / "fixture.bin"
    binary.write_bytes(b"\x00\x01\x02\xff\x00\x10")
    _git(repo, "add", "fixture.bin")
    _git(repo, "commit", "-m", "Add binary fixture")
    head = _git(repo, "rev-parse", "HEAD")

    result = _run(repo, "--git-range", f"{base}..{head}")

    assert result.returncode == 2
    assert "contains binary changes that cannot be audited" in result.stderr


def test_fails_closed_for_missing_binary_and_symlink_artifacts(tmp_path: Path) -> None:
    repo, _base = _init_repo(tmp_path)
    missing = tmp_path / "missing.md"
    binary = tmp_path / "binary.log"
    binary.write_bytes(b"valid prefix\n\x00private suffix\n")
    target = tmp_path / "target.md"
    target.write_text("AlmaLinux 8\n", encoding="utf-8")
    symlink = tmp_path / "issue.md"
    symlink.symlink_to(target)

    missing_result = _run(repo, "--artifact", os.fspath(missing))
    binary_result = _run(repo, "--artifact", os.fspath(binary))
    symlink_result = _run(repo, "--artifact", os.fspath(symlink))

    assert missing_result.returncode == 2
    assert binary_result.returncode == 2
    assert "contains NUL bytes" in binary_result.stderr
    assert symlink_result.returncode == 2
    assert "may not be a symbolic link" in symlink_result.stderr


def test_requires_exact_git_root_and_valid_utf8_artifacts(tmp_path: Path) -> None:
    repo, _base = _init_repo(tmp_path)
    subdirectory = repo / "docs"
    subdirectory.mkdir()
    artifact = tmp_path / "invalid.log"
    artifact.write_bytes(b"\xff\xfe\xfd")

    wrong_root = _run(subdirectory, "--artifact", os.fspath(repo / "README.md"))
    invalid_utf8 = _run(repo, "--artifact", os.fspath(artifact))

    assert wrong_root.returncode == 2
    assert "worktree root exactly" in wrong_root.stderr
    assert invalid_utf8.returncode == 2
    assert "not valid UTF-8 text" in invalid_utf8.stderr
