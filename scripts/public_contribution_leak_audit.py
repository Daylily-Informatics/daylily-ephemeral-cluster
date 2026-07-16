#!/usr/bin/env python3
"""Fail-closed audit for material prepared for a public contribution."""

from __future__ import annotations

import argparse
import os
import re
import stat
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

PASS = 0
FINDINGS = 1
AUDIT_ERROR = 2


class AuditError(RuntimeError):
    """The requested audit could not be completed exactly."""


@dataclass(frozen=True)
class Rule:
    name: str
    pattern: re.Pattern[str]


@dataclass(frozen=True, order=True)
class Finding:
    source: str
    line: int
    column: int
    rule: str


@dataclass
class AuditCounts:
    ranges: int = 0
    artifacts: int = 0
    commits: int = 0
    changed_paths: int = 0


RULES: tuple[Rule, ...] = (
    Rule(
        "private_organization_term",
        re.compile(
            r"(?<![A-Za-z0-9])(?:lsmc|dayoa|dayec|dyec|"
            r"daylily(?:[-_ ]?(?:ec|omics|ephemeral))?)"
            r"(?![A-Za-z0-9])",
            re.IGNORECASE,
        ),
    ),
    Rule(
        "vendor_or_product_term",
        re.compile(r"\b(?:illumina|ilmn|dragen)\b", re.IGNORECASE),
    ),
    Rule(
        "private_cluster_identifier",
        re.compile(r"\b(?:dragain\d+[a-z]*|pclusterTagsAndBudget)\b", re.IGNORECASE),
    ),
    Rule(
        "marketplace_product_reference",
        re.compile(r"\b(?:aws[ -]?)?marketplace\b|\bprodview-[a-z0-9]+\b", re.IGNORECASE),
    ),
    Rule(
        "aws_resource_identifier",
        re.compile(
            r"\b(?:"
            r"ami-(?!(?:0{12}|12345678)\b)[0-9a-f]{8,17}|"
            r"(?:snap|subnet|vpc|sg|i|vol|fs|fsap|agfi|afi)-[0-9a-f]{8,17}"
            r")\b",
            re.IGNORECASE,
        ),
    ),
    Rule(
        "aws_account_identifier",
        re.compile(r"(?<!\d)(?!(?:0{12}|764336703387)(?!\d))\d{12}(?!\d)"),
    ),
    Rule(
        "aws_arn",
        re.compile(r"\barn:(?:aws|aws-us-gov|aws-cn):[^\s'\"]+", re.IGNORECASE),
    ),
    Rule("s3_uri", re.compile(r"\bs3://[^\s'\"]+", re.IGNORECASE)),
    Rule(
        "s3_endpoint",
        re.compile(
            r"\b[a-z0-9][a-z0-9.-]{1,62}\.s3[.-][a-z0-9.-]+\.amazonaws\.com\b",
            re.IGNORECASE,
        ),
    ),
    Rule(
        "credential_or_entitlement_reference",
        re.compile(
            r"\b(?:lic[_-]?creds|lic[_-]?credentials|license[-_ ]server|"
            r"license[-_ ]entitlement|credential(?:s)?[-_ ](?:file|path|url|value|hash))\b|"
            r"--lic-credentials\b|\bsecret(?:smanager)?[-_ /][A-Za-z0-9._/+=,@:-]+",
            re.IGNORECASE,
        ),
    ),
    Rule(
        "credential_in_url",
        re.compile(
            r"https?://[^\s/:]+:[^@\s/]+@|[?&](?:token|password|credential|secret)=[^&\s]+",
            re.IGNORECASE,
        ),
    ),
    Rule(
        "license_url_or_hash",
        re.compile(
            r"(?:https?://[^\s]+[^\n]*\blicen[cs]e\b|\blicen[cs]e\b[^\n]*https?://[^\s]+|"
            r"\bsha256\b[^\n]*\blicen[cs]e\b|\blicen[cs]e\b[^\n]*\bsha256\b)",
            re.IGNORECASE,
        ),
    ),
    Rule("aws_access_key", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    Rule(
        "private_key_material",
        re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----"),
    ),
    Rule(
        "biological_or_sequencing_reference",
        re.compile(
            r"\b(?:HG\d{3}|NA\d{5}|LH\d{5}|SMN(?:12)?|FASTQ|BCLConvert|gVCF|VCF|"
            r"pangenome|sequencing)\b",
            re.IGNORECASE,
        ),
    ),
    Rule(
        "private_reference_path",
        re.compile(
            r"(?:/fsx/references(?:/|\b)|\bhg38(?:_broad)?\b|"
            r"runtime_assets/tool_specific_resources)",
            re.IGNORECASE,
        ),
    ),
    Rule(
        "private_local_path",
        re.compile(r"/Users/jmajor(?:/[^\s'\"]*)?", re.IGNORECASE),
    ),
    Rule(
        "private_ssh_key_path",
        re.compile(r"(?:~|/Users/[^/\s]+)?/\.ssh/[^\s'\"]+\.pem\b", re.IGNORECASE),
    ),
)


def _run_git(repo: Path, args: Sequence[str], *, operation: str) -> bytes:
    try:
        result = subprocess.run(
            ["git", "-C", os.fspath(repo), *args],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except OSError as exc:
        raise AuditError(f"{operation} could not execute git: {exc.__class__.__name__}") from exc
    if result.returncode != 0:
        raise AuditError(f"{operation} failed with git exit code {result.returncode}")
    return result.stdout


def _decode_git_output(data: bytes, *, operation: str) -> str:
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise AuditError(f"{operation} produced non-UTF-8 output") from exc


def _validate_repo(repo_arg: str) -> Path:
    repo = Path(repo_arg).expanduser().resolve()
    if not repo.is_dir():
        raise AuditError("--repo must identify an existing directory")
    top_level_raw = _run_git(repo, ["rev-parse", "--show-toplevel"], operation="repository check")
    top_level = Path(
        _decode_git_output(top_level_raw, operation="repository check").strip()
    ).resolve()
    if top_level != repo:
        raise AuditError("--repo must identify the Git worktree root exactly")
    return repo


def _parse_range(value: str) -> tuple[str, str]:
    if "..." in value or value.count("..") != 1:
        raise AuditError("each --git-range must use the explicit BASE..HEAD form")
    base, separator, head = value.partition("..")
    if not separator or not base or not head:
        raise AuditError("each --git-range must include non-empty BASE and HEAD revisions")
    for endpoint in (base, head):
        if endpoint.startswith("-") or any(character.isspace() for character in endpoint):
            raise AuditError("Git range endpoints may not start with '-' or contain whitespace")
        if any(ord(character) < 32 or ord(character) == 127 for character in endpoint):
            raise AuditError("Git range endpoints may not contain control characters")
    return base, head


def _resolve_commit(repo: Path, revision: str, *, endpoint: str) -> str:
    raw = _run_git(
        repo,
        ["rev-parse", "--verify", f"{revision}^{{commit}}"],
        operation=f"{endpoint} revision validation",
    )
    commit = _decode_git_output(raw, operation=f"{endpoint} revision validation").strip()
    if not re.fullmatch(r"[0-9a-f]{40,64}", commit):
        raise AuditError(f"{endpoint} revision did not resolve to a full commit identifier")
    return commit


def _require_ancestor(repo: Path, base: str, head: str, *, range_index: int) -> None:
    try:
        result = subprocess.run(
            ["git", "-C", os.fspath(repo), "merge-base", "--is-ancestor", base, head],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except OSError as exc:
        raise AuditError(
            f"git range {range_index} ancestry check could not execute git: "
            f"{exc.__class__.__name__}"
        ) from exc
    if result.returncode == 1:
        raise AuditError(f"git range {range_index} BASE must be an ancestor of HEAD")
    if result.returncode != 0:
        raise AuditError(
            f"git range {range_index} ancestry check failed with git exit code "
            f"{result.returncode}"
        )


def _scan_text(text: str, *, source: str) -> list[Finding]:
    findings: list[Finding] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        for rule in RULES:
            for match in rule.pattern.finditer(line):
                findings.append(
                    Finding(
                        source=source,
                        line=line_number,
                        column=match.start() + 1,
                        rule=rule.name,
                    )
                )
    return findings


def _changed_diff_text(diff: str) -> str:
    """Return only added and deleted content, excluding Git diff metadata."""

    changed_lines = []
    for line in diff.splitlines():
        if line.startswith(("+++", "---")):
            continue
        if line.startswith(("+", "-")):
            changed_lines.append(line[1:])
    return "\n".join(changed_lines)


def _parse_changed_paths(data: bytes) -> list[str]:
    tokens = data.split(b"\0")
    if tokens and tokens[-1] == b"":
        tokens.pop()
    paths: list[str] = []
    index = 0
    while index < len(tokens):
        try:
            status_value = tokens[index].decode("ascii")
        except UnicodeDecodeError as exc:
            raise AuditError("changed-path status was not ASCII") from exc
        index += 1
        path_count = 2 if status_value[:1] in {"R", "C"} else 1
        if index + path_count > len(tokens):
            raise AuditError("changed-path output was malformed")
        for raw_path in tokens[index : index + path_count]:
            try:
                paths.append(raw_path.decode("utf-8"))
            except UnicodeDecodeError as exc:
                raise AuditError("a changed path was not UTF-8") from exc
        index += path_count
    return paths


def _parse_commit_messages(data: bytes) -> list[tuple[str, str]]:
    tokens = data.split(b"\0")
    if tokens and tokens[-1] == b"":
        tokens.pop()
    if len(tokens) % 2:
        raise AuditError("commit-message output was malformed")
    commits: list[tuple[str, str]] = []
    for index in range(0, len(tokens), 2):
        try:
            commit = tokens[index].decode("ascii")
            message = tokens[index + 1].decode("utf-8")
        except UnicodeDecodeError as exc:
            raise AuditError("a commit message was not valid UTF-8") from exc
        if not re.fullmatch(r"[0-9a-f]{40,64}", commit):
            raise AuditError("commit-message output contained an invalid commit identifier")
        commits.append((commit, message))
    return commits


def _audit_git_range(
    repo: Path,
    range_value: str,
    *,
    range_index: int,
) -> tuple[list[Finding], int, int]:
    base_revision, head_revision = _parse_range(range_value)
    base = _resolve_commit(repo, base_revision, endpoint="BASE")
    head = _resolve_commit(repo, head_revision, endpoint="HEAD")
    resolved_range = f"{base}..{head}"
    _require_ancestor(repo, base, head, range_index=range_index)

    count_raw = _run_git(
        repo,
        ["rev-list", "--count", resolved_range, "--"],
        operation=f"git range {range_index} commit count",
    )
    count_text = _decode_git_output(
        count_raw, operation=f"git range {range_index} commit count"
    ).strip()
    if not count_text.isdigit() or int(count_text) < 1:
        raise AuditError(f"git range {range_index} must contain at least one commit")

    paths_raw = _run_git(
        repo,
        ["diff", "--name-status", "-z", "--find-renames", base, head, "--"],
        operation=f"git range {range_index} changed-path scan",
    )
    paths = _parse_changed_paths(paths_raw)

    diff_raw = _run_git(
        repo,
        [
            "diff",
            "--no-ext-diff",
            "--no-textconv",
            "--no-color",
            "--unified=0",
            "--binary",
            base,
            head,
            "--",
        ],
        operation=f"git range {range_index} diff scan",
    )
    diff = _decode_git_output(diff_raw, operation=f"git range {range_index} diff scan")
    if "GIT binary patch" in diff or re.search(r"^Binary files .* differ$", diff, re.MULTILINE):
        raise AuditError(f"git range {range_index} contains binary changes that cannot be audited")

    messages_raw = _run_git(
        repo,
        ["log", "-z", "--format=%H%x00%B", resolved_range, "--"],
        operation=f"git range {range_index} commit-message scan",
    )
    commits = _parse_commit_messages(messages_raw)
    if len(commits) != int(count_text):
        raise AuditError(f"git range {range_index} commit enumeration was incomplete")

    findings = _scan_text(
        _changed_diff_text(diff),
        source=f"git-range[{range_index}]:diff",
    )
    for path_index, path in enumerate(paths, start=1):
        findings.extend(
            _scan_text(path, source=f"git-range[{range_index}]:changed-path[{path_index}]")
        )
    for commit_index, (_commit, message) in enumerate(commits, start=1):
        findings.extend(
            _scan_text(
                message,
                source=f"git-range[{range_index}]:commit-message[{commit_index}]",
            )
        )
    return findings, len(commits), len(paths)


def _audit_artifact(path_value: str, *, artifact_index: int) -> list[Finding]:
    path = Path(path_value).expanduser()
    if path.is_symlink():
        raise AuditError(f"artifact {artifact_index} may not be a symbolic link")
    try:
        mode = path.stat().st_mode
    except OSError as exc:
        raise AuditError(
            f"artifact {artifact_index} could not be inspected: {exc.__class__.__name__}"
        ) from exc
    if not stat.S_ISREG(mode):
        raise AuditError(f"artifact {artifact_index} must be a regular file")

    findings: list[Finding] = []
    try:
        with path.open("r", encoding="utf-8", errors="strict", newline=None) as handle:
            for line_number, line in enumerate(handle, start=1):
                if "\x00" in line:
                    raise AuditError(f"artifact {artifact_index} contains NUL bytes")
                for finding in _scan_text(line, source=f"artifact[{artifact_index}]"):
                    findings.append(
                        Finding(
                            source=finding.source,
                            line=line_number,
                            column=finding.column,
                            rule=finding.rule,
                        )
                    )
    except UnicodeDecodeError as exc:
        raise AuditError(f"artifact {artifact_index} is not valid UTF-8 text") from exc
    except OSError as exc:
        raise AuditError(
            f"artifact {artifact_index} could not be read: {exc.__class__.__name__}"
        ) from exc
    return findings


def audit(
    *,
    repo_arg: str,
    git_ranges: Iterable[str],
    artifacts: Iterable[str],
) -> tuple[list[Finding], AuditCounts]:
    range_values = list(git_ranges)
    artifact_values = list(artifacts)
    if not range_values and not artifact_values:
        raise AuditError("at least one --git-range or --artifact is required")
    if len(range_values) != len(set(range_values)):
        raise AuditError("duplicate --git-range values are not allowed")
    if len(artifact_values) != len(set(artifact_values)):
        raise AuditError("duplicate --artifact values are not allowed")

    repo = _validate_repo(repo_arg)
    counts = AuditCounts(ranges=len(range_values), artifacts=len(artifact_values))
    findings: list[Finding] = []
    for range_index, range_value in enumerate(range_values, start=1):
        range_findings, commit_count, path_count = _audit_git_range(
            repo, range_value, range_index=range_index
        )
        findings.extend(range_findings)
        counts.commits += commit_count
        counts.changed_paths += path_count
    for artifact_index, artifact in enumerate(artifact_values, start=1):
        findings.extend(_audit_artifact(artifact, artifact_index=artifact_index))
    return sorted(set(findings)), counts


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Audit explicit public Git BASE..HEAD ranges and caller-supplied UTF-8 text "
            "artifacts. Exit 0 passes, 1 blocks on findings, and 2 reports an incomplete audit."
        )
    )
    parser.add_argument(
        "--repo",
        required=True,
        help="Exact Git worktree root containing every supplied range.",
    )
    parser.add_argument(
        "--git-range",
        action="append",
        default=[],
        metavar="BASE..HEAD",
        help="Explicit commit range to audit; repeat for multiple ranges.",
    )
    parser.add_argument(
        "--artifact",
        action="append",
        default=[],
        metavar="PATH",
        help="Explicit UTF-8 issue, PR, or log text file to audit; repeat as needed.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        findings, counts = audit(
            repo_arg=args.repo,
            git_ranges=args.git_range,
            artifacts=args.artifact,
        )
    except AuditError as exc:
        print(f"PUBLIC CONTRIBUTION AUDIT: ERROR: {exc}", file=sys.stderr)
        return AUDIT_ERROR

    if findings:
        print("PUBLIC CONTRIBUTION AUDIT: BLOCKED", file=sys.stderr)
        print(f"findings={len(findings)}", file=sys.stderr)
        for finding in findings:
            print(
                f"{finding.rule} {finding.source}:{finding.line}:{finding.column}",
                file=sys.stderr,
            )
        return FINDINGS

    print("PUBLIC CONTRIBUTION AUDIT: PASS")
    print(
        f"git_ranges={counts.ranges} artifacts={counts.artifacts} "
        f"commits={counts.commits} changed_paths={counts.changed_paths}"
    )
    return PASS


if __name__ == "__main__":
    raise SystemExit(main())
