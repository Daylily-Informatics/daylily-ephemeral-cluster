"""Bounded public scheduler and controller-evidence receipt contracts."""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import os
import re
import stat
import tempfile
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any, Mapping


SCHEDULER_SNAPSHOT_SCHEMA = "dyec.headnode.scheduler_snapshot.v1"
CONTROLLER_EVIDENCE_SCHEMA = "dyec.headnode.controller_evidence.v1"
RUNTIME_IDENTITY_SCHEMA = "dyec.headnode.runtime_identity.v1"
_SCHEDULER_MARKER = "__DYEC_SCHEDULER_SNAPSHOT__="
_EVIDENCE_MARKER = "__DYEC_CONTROLLER_EVIDENCE__="
_RUNTIME_IDENTITY_MARKER = "__DYEC_RUNTIME_IDENTITY__="
MAX_LOG_BYTES = 2 * 1024 * 1024
MAX_DAG_BYTES = 8 * 1024 * 1024
MAX_ENVELOPE_BYTES = 14 * 1024 * 1024
_PID_RE = re.compile(r"^[1-9][0-9]{0,8}$")


class HeadnodeReceiptError(RuntimeError):
    """Raised for bounded public headnode receipt violations."""


def _python_script(body: str) -> str:
    """Run one static Python receipt body through the supported Bash transport."""

    return "python3 - <<'PY'\n" + body.rstrip() + "\nPY\n"


def _positive_pid(value: object, *, field: str) -> int:
    text = str(value or "").strip()
    if not _PID_RE.fullmatch(text):
        raise HeadnodeReceiptError(f"{field} must be one positive decimal PID")
    return int(text)


def _analysis_root(value: object) -> str:
    raw = str(value or "").strip().rstrip("/")
    path = PurePosixPath(raw)
    if (
        not raw
        or not path.is_absolute()
        or path.parts[:3] != ("/", "fsx", "analysis_results")
        or len(path.parts) != 5
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise HeadnodeReceiptError(
            "analysis_root must be /fsx/analysis_results/<owner>/<analysis_id>"
        )
    return path.as_posix()


def _expected_cwd(value: object, *, analysis_root: str) -> str:
    raw = str(value or "").strip().rstrip("/")
    path = PurePosixPath(raw)
    root = PurePosixPath(analysis_root)
    if not raw or not path.is_absolute() or path == root:
        raise HeadnodeReceiptError("expected_cwd must be an absolute directory beneath analysis_root")
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise HeadnodeReceiptError("expected_cwd must be beneath analysis_root") from exc
    if any(part in {"", ".", ".."} for part in path.parts):
        raise HeadnodeReceiptError("expected_cwd contains an invalid path segment")
    return path.as_posix()


def _relative_file(value: object, *, field: str) -> str:
    raw = str(value or "").strip().replace("\\", "/")
    path = PurePosixPath(raw)
    if (
        not raw
        or raw.startswith("/")
        or "//" in raw
        or path.is_absolute()
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise HeadnodeReceiptError(
            f"{field} must be one exact relative path beneath analysis_root"
        )
    return path.as_posix()


def _staging_s3_uri(value: object) -> str:
    raw = str(value or "").strip().rstrip("/")
    if (
        not raw.startswith("s3://")
        or len(raw.split("/", 3)) != 4
        or not raw.split("/", 3)[2]
        or not raw.split("/", 3)[3]
        or any(character in raw for character in "\r\n\x00")
    ):
        raise HeadnodeReceiptError(
            "staging_s3_uri must be one exact s3://bucket/prefix/object URI"
        )
    return raw


def build_scheduler_snapshot_script(*, max_jobs: int, max_nodes: int) -> str:
    if isinstance(max_jobs, bool) or not isinstance(max_jobs, int) or not 1 <= max_jobs <= 500:
        raise HeadnodeReceiptError("max_jobs must be between 1 and 500")
    if isinstance(max_nodes, bool) or not isinstance(max_nodes, int) or not 1 <= max_nodes <= 500:
        raise HeadnodeReceiptError("max_nodes must be between 1 and 500")
    return _python_script(f"""
import datetime
import json
import subprocess

SCHEMA = {SCHEDULER_SNAPSHOT_SCHEMA!r}
MARKER = {_SCHEDULER_MARKER!r}
MAX_JOBS = {max_jobs}
MAX_NODES = {max_nodes}

def run(command):
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=30, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.splitlines()

jobs_raw = run(["squeue", "--noheader", "--format=%i|%t|%u|%j|%N"])
nodes_raw = run(["sinfo", "--noheader", "--format=%N|%T|%C"])
if jobs_raw is None or nodes_raw is None:
    payload = {{"schema_version": SCHEMA, "ok": False, "error": "scheduler_command_unavailable"}}
else:
    jobs = []
    for line in jobs_raw[:MAX_JOBS]:
        fields = line.split("|", 4)
        if len(fields) != 5 or not fields[0] or not fields[1]:
            payload = {{"schema_version": SCHEMA, "ok": False, "error": "invalid_squeue_output"}}
            break
        jobs.append({{"job_id": fields[0], "state": fields[1], "user": fields[2], "name": fields[3], "nodes": fields[4]}})
    else:
        nodes = []
        for line in nodes_raw[:MAX_NODES]:
            fields = line.split("|", 2)
            if len(fields) != 3 or not fields[0] or not fields[1]:
                payload = {{"schema_version": SCHEMA, "ok": False, "error": "invalid_sinfo_output"}}
                break
            nodes.append({{"name": fields[0], "state": fields[1], "cpu": fields[2]}})
        else:
            payload = {{
                "schema_version": SCHEMA,
                "ok": True,
                "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z"),
                "jobs": jobs,
                "nodes": nodes,
                "job_count": len(jobs_raw),
                "node_count": len(nodes_raw),
                "jobs_truncated": len(jobs_raw) > MAX_JOBS,
                "nodes_truncated": len(nodes_raw) > MAX_NODES,
                "max_jobs": MAX_JOBS,
                "max_nodes": MAX_NODES,
            }}
print(MARKER + json.dumps(payload, sort_keys=True, separators=(",", ":")))
""")


def build_controller_evidence_script(
    *,
    analysis_root: object,
    controller_pid: object,
    confirm_pid: object,
    expected_cwd: object,
    log_file: object,
    dag_file: object,
    staging_s3_uri: object,
) -> str:
    """Build the sole remote collector for bounded log and DAG evidence."""

    root = _analysis_root(analysis_root)
    pid = _positive_pid(controller_pid, field="controller_pid")
    confirm = _positive_pid(confirm_pid, field="confirm_pid")
    if pid != confirm:
        raise HeadnodeReceiptError("confirm_pid must exactly match controller_pid")
    cwd = _expected_cwd(expected_cwd, analysis_root=root)
    requested_log = _relative_file(log_file, field="log_file")
    requested_dag = _relative_file(dag_file, field="dag_file")
    if requested_log == requested_dag:
        raise HeadnodeReceiptError("log_file and dag_file must be different exact paths")
    relay_uri = _staging_s3_uri(staging_s3_uri)
    return _python_script(f"""
import base64
import datetime
import hashlib
import json
import os
import pwd
import stat
import subprocess
import tempfile
from pathlib import Path

SCHEMA = {CONTROLLER_EVIDENCE_SCHEMA!r}
MARKER = {_EVIDENCE_MARKER!r}
ROOT = Path({root!r})
PID = {pid}
CONFIRM_PID = {confirm}
EXPECTED_CWD = Path({cwd!r})
REQUESTED = {{"log": {requested_log!r}, "dag": {requested_dag!r}}}
LIMITS = {{"log": {MAX_LOG_BYTES}, "dag": {MAX_DAG_BYTES}}}
STAGING_S3_URI = {relay_uri!r}

def fail(code):
    print(MARKER + json.dumps({{"schema_version": SCHEMA, "ok": False, "error": code}}, sort_keys=True, separators=(",", ":")))
    raise SystemExit(2)

if PID != CONFIRM_PID:
    fail("confirm_pid_mismatch")
try:
    root = ROOT.resolve(strict=True)
except OSError:
    fail("analysis_root_unavailable")
if root != ROOT:
    fail("analysis_root_not_real")
proc = Path("/proc") / str(PID)
if not proc.is_dir():
    fail("controller_not_live")
try:
    uid_line = next(line for line in (proc / "status").read_text(encoding="utf-8").splitlines() if line.startswith("Uid:"))
    process_uid = int(uid_line.split()[1])
    process_owner = pwd.getpwuid(process_uid).pw_name
    cwd = Path(os.readlink(proc / "cwd")).resolve(strict=True)
    command = [part.decode("utf-8", errors="replace") for part in (proc / "cmdline").read_bytes()[:8192].split(b"\\x00") if part]
except (KeyError, OSError, StopIteration, ValueError):
    fail("controller_identity_unavailable")
if process_owner != "ubuntu":
    fail("controller_not_ubuntu_owned")
if cwd != EXPECTED_CWD:
    fail("controller_cwd_mismatch")
if not any("day_run" in value or "snakemake" in value or value.endswith("/dy-r") or value == "dy-r" for value in command):
    fail("controller_not_recognized")

rows = {{}}
total = 0
for role, relative in REQUESTED.items():
    candidate = ROOT / relative
    try:
        if candidate.is_symlink():
            fail("evidence_path_not_regular")
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(ROOT)
        info = resolved.lstat()
        if not stat.S_ISREG(info.st_mode) or stat.S_ISLNK(info.st_mode):
            fail("evidence_path_not_regular")
        with resolved.open("rb") as handle:
            content = handle.read(LIMITS[role] + 1)
    except (OSError, ValueError):
        fail("evidence_path_unavailable")
    if len(content) > LIMITS[role]:
        fail(role + "_size_exceeded")
    total += len(content)
    rows[role] = {{
        "relative_path": relative,
        "size_bytes": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
        "content_b64": base64.b64encode(content).decode("ascii"),
        "complete": True,
    }}
collected_at = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
envelope = {{
    "schema_version": SCHEMA,
    "ok": True,
    "collected_at": collected_at,
    "analysis_root": str(ROOT),
    "controller_pid": PID,
    "confirmed_pid": CONFIRM_PID,
    "controller_owner": process_owner,
    "controller_cwd": str(cwd),
    "requested_files": dict(REQUESTED),
    "files": rows,
    "file_count": 2,
    "total_bytes": total,
    "complete": True,
    "limits": dict(LIMITS),
}}
encoded = json.dumps(envelope, sort_keys=True, separators=(",", ":")).encode("utf-8")
if len(encoded) > {MAX_ENVELOPE_BYTES}:
    fail("evidence_envelope_size_exceeded")
descriptor, temporary_name = tempfile.mkstemp(prefix="dyec-controller-evidence-", suffix=".json")
try:
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())
    os.chmod(temporary_name, 0o600)
    uploaded = subprocess.run(
        ["aws", "s3", "cp", "--only-show-errors", temporary_name, STAGING_S3_URI],
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    if uploaded.returncode != 0:
        fail("evidence_relay_upload_failed")
finally:
    try:
        os.unlink(temporary_name)
    except OSError:
        pass
receipt = {{
    "schema_version": SCHEMA,
    "ok": True,
    "status": "staged",
    "collected_at": collected_at,
    "analysis_root": str(ROOT),
    "controller_pid": PID,
    "confirmed_pid": CONFIRM_PID,
    "controller_owner": process_owner,
    "controller_cwd": str(cwd),
    "requested_files": dict(REQUESTED),
    "envelope_s3_uri": STAGING_S3_URI,
    "envelope_sha256": hashlib.sha256(encoded).hexdigest(),
    "envelope_size_bytes": len(encoded),
    "complete": True,
}}
print(MARKER + json.dumps(receipt, sort_keys=True, separators=(",", ":")))
""")


def _parse_marker(stdout: object, *, marker: str, schema: str) -> dict[str, Any]:
    if not isinstance(stdout, str):
        raise HeadnodeReceiptError("headnode receipt output must be text")
    lines = [line for line in stdout.splitlines() if line.startswith(marker)]
    if len(lines) != 1:
        raise HeadnodeReceiptError("headnode receipt must contain exactly one marker")
    try:
        payload = json.loads(lines[0][len(marker) :])
    except json.JSONDecodeError as exc:
        raise HeadnodeReceiptError("headnode receipt marker is not valid JSON") from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != schema:
        raise HeadnodeReceiptError("headnode receipt schema does not match")
    if payload.get("ok") is not True:
        raise HeadnodeReceiptError("headnode receipt reports failure")
    return payload


def parse_scheduler_snapshot(stdout: object) -> dict[str, Any]:
    payload = _parse_marker(stdout, marker=_SCHEDULER_MARKER, schema=SCHEDULER_SNAPSHOT_SCHEMA)
    required = {
        "generated_at",
        "jobs",
        "nodes",
        "job_count",
        "node_count",
        "jobs_truncated",
        "nodes_truncated",
        "max_jobs",
        "max_nodes",
    }
    if not required.issubset(payload) or not isinstance(payload["jobs"], list) or not isinstance(payload["nodes"], list):
        raise HeadnodeReceiptError("scheduler snapshot is incomplete")
    generated_at = str(payload.get("generated_at") or "").strip()
    try:
        generated = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HeadnodeReceiptError("scheduler snapshot generated_at is invalid") from exc
    if generated.tzinfo is None:
        raise HeadnodeReceiptError("scheduler snapshot generated_at must include a timezone")
    checked = datetime.now(UTC)
    age_seconds = (checked - generated.astimezone(UTC)).total_seconds()
    if age_seconds < -30 or age_seconds > 300:
        raise HeadnodeReceiptError("scheduler snapshot is outside the five-minute freshness bound")
    payload["complete"] = not (payload["jobs_truncated"] or payload["nodes_truncated"])
    payload["freshness"] = {
        "checked_at": checked.isoformat().replace("+00:00", "Z"),
        "age_seconds": round(max(0.0, age_seconds), 3),
        "maximum_age_seconds": 300,
        "fresh": True,
    }
    return payload


def parse_staged_controller_evidence(stdout: object) -> dict[str, Any]:
    payload = _parse_marker(stdout, marker=_EVIDENCE_MARKER, schema=CONTROLLER_EVIDENCE_SCHEMA)
    required = {
        "status",
        "analysis_root",
        "controller_pid",
        "confirmed_pid",
        "controller_owner",
        "controller_cwd",
        "requested_files",
        "envelope_s3_uri",
        "envelope_sha256",
        "envelope_size_bytes",
        "complete",
    }
    if not required.issubset(payload) or payload.get("status") != "staged" or payload.get("complete") is not True:
        raise HeadnodeReceiptError("controller evidence staging receipt is incomplete")
    if payload.get("controller_owner") != "ubuntu" or payload.get("controller_pid") != payload.get("confirmed_pid"):
        raise HeadnodeReceiptError("controller evidence staging identity is invalid")
    root = _analysis_root(payload.get("analysis_root"))
    _expected_cwd(payload.get("controller_cwd"), analysis_root=root)
    _staging_s3_uri(payload.get("envelope_s3_uri"))
    if not isinstance(payload.get("envelope_size_bytes"), int) or not 1 <= payload["envelope_size_bytes"] <= MAX_ENVELOPE_BYTES:
        raise HeadnodeReceiptError("controller evidence envelope size is invalid")
    if not isinstance(payload.get("envelope_sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", payload["envelope_sha256"]):
        raise HeadnodeReceiptError("controller evidence envelope digest is invalid")
    requested = payload.get("requested_files")
    if not isinstance(requested, Mapping) or set(requested) != {"log", "dag"}:
        raise HeadnodeReceiptError("controller evidence requested files are invalid")
    for role in ("log", "dag"):
        _relative_file(requested[role], field=f"{role}_file")
    return payload


def build_runtime_identity_script() -> str:
    """Return a bounded remote probe for the installed DYEC package provenance."""

    return _python_script(f"""
import importlib.metadata
import importlib.util
import json
from pathlib import Path
import re
import subprocess

SCHEMA = {RUNTIME_IDENTITY_SCHEMA!r}
MARKER = {_RUNTIME_IDENTITY_MARKER!r}
try:
    distribution = importlib.metadata.distribution("daylily-ephemeral-cluster")
    version = str(distribution.version or "").strip()
    repo_root = (Path.home() / "projects" / "daylily-ephemeral-cluster").resolve()
    package_spec = importlib.util.find_spec("daylily_ec")
    package_origin = Path(str(getattr(package_spec, "origin", "") or "")).resolve()
    source_remote = subprocess.run(
        ["git", "-C", str(repo_root), "remote", "get-url", "origin"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    commit_id = subprocess.run(
        ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip().lower()
    tag_type = subprocess.run(
        ["git", "-C", str(repo_root), "cat-file", "-t", f"refs/tags/{{version}}"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    tag_commit = subprocess.run(
        ["git", "-C", str(repo_root), "rev-parse", f"refs/tags/{{version}}^{{commit}}"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip().lower()
    worktree_status = subprocess.run(
        ["git", "-C", str(repo_root), "status", "--porcelain", "--untracked-files=all"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    allowed_remotes = {{
        "git@github.com:lsmc-bio/daylily-ephemeral-cluster.git",
        "ssh://git@github.com/lsmc-bio/daylily-ephemeral-cluster.git",
        "https://github.com/lsmc-bio/daylily-ephemeral-cluster",
        "https://github.com/lsmc-bio/daylily-ephemeral-cluster.git",
    }}
    if (
        re.fullmatch(r"[0-9]+\\.[0-9]+\\.[0-9]+(?:\\.[0-9]+)?", version) is None
        or source_remote not in allowed_remotes
        or re.fullmatch(r"[0-9a-f]{{40}}", commit_id) is None
        or tag_type != "tag"
        or tag_commit != commit_id
        or worktree_status
        or not package_origin.is_relative_to(repo_root / "daylily_ec")
    ):
        raise RuntimeError("installed_dyec_provenance_invalid")
    payload = {{
        "schema_version": SCHEMA,
        "ok": True,
        "dyec_version": version,
        "source_url": "https://github.com/lsmc-bio/daylily-ephemeral-cluster.git",
        "requested_revision": version,
        "commit_id": commit_id,
    }}
except Exception:
    payload = {{"schema_version": SCHEMA, "ok": False, "error": "installed_dyec_provenance_invalid"}}
print(MARKER + json.dumps(payload, sort_keys=True, separators=(",", ":")))
""")


def parse_runtime_identity(stdout: object) -> dict[str, Any]:
    """Validate one exact version/provenance receipt returned by the headnode."""

    payload = _parse_marker(
        stdout,
        marker=_RUNTIME_IDENTITY_MARKER,
        schema=RUNTIME_IDENTITY_SCHEMA,
    )
    version = str(payload.get("dyec_version") or "").strip()
    source_url = str(payload.get("source_url") or "").strip()
    requested_revision = str(payload.get("requested_revision") or "").strip()
    commit_id = str(payload.get("commit_id") or "").strip().lower()
    if (
        not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+(?:\.[0-9]+)?", version)
        or not requested_revision
        or re.fullmatch(r"[0-9a-f]{40}", commit_id) is None
        or (
            source_url
            not in {
                "https://github.com/lsmc-bio/daylily-ephemeral-cluster",
                "https://github.com/lsmc-bio/daylily-ephemeral-cluster.git",
            }
            and not source_url.startswith("file:///opt/ursa-build/")
        )
    ):
        raise HeadnodeReceiptError("headnode DYEC runtime identity is invalid")
    return {
        "schema_version": RUNTIME_IDENTITY_SCHEMA,
        "ok": True,
        "dyec_version": version,
        "source_url": source_url,
        "requested_revision": requested_revision,
        "commit_id": commit_id,
    }


def parse_controller_evidence_envelope(
    content: bytes,
    *,
    staged_receipt: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate the staged envelope before any local evidence materialization."""

    expected_size = staged_receipt.get("envelope_size_bytes")
    expected_sha256 = staged_receipt.get("envelope_sha256")
    if len(content) != expected_size or hashlib.sha256(content).hexdigest() != expected_sha256:
        raise HeadnodeReceiptError("controller evidence relay digest or size does not match")
    try:
        payload = json.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HeadnodeReceiptError("controller evidence relay is not valid JSON") from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != CONTROLLER_EVIDENCE_SCHEMA:
        raise HeadnodeReceiptError("controller evidence envelope schema does not match")
    if payload.get("ok") is not True or payload.get("complete") is not True:
        raise HeadnodeReceiptError("controller evidence envelope is incomplete")
    for field in (
        "analysis_root",
        "controller_pid",
        "confirmed_pid",
        "controller_owner",
        "controller_cwd",
        "requested_files",
    ):
        if payload.get(field) != staged_receipt.get(field):
            raise HeadnodeReceiptError("controller evidence relay identity does not match staging receipt")
    if payload.get("controller_owner") != "ubuntu":
        raise HeadnodeReceiptError("controller evidence owner is invalid")
    files = payload.get("files")
    requested = payload.get("requested_files")
    limits = payload.get("limits")
    if not isinstance(files, Mapping) or set(files) != {"log", "dag"}:
        raise HeadnodeReceiptError("controller evidence envelope files are invalid")
    if not isinstance(requested, Mapping) or not isinstance(limits, Mapping):
        raise HeadnodeReceiptError("controller evidence envelope metadata is invalid")
    total = 0
    normalized_files: dict[str, dict[str, Any]] = {}
    for role, maximum in (("log", MAX_LOG_BYTES), ("dag", MAX_DAG_BYTES)):
        row = files.get(role)
        if not isinstance(row, Mapping) or row.get("complete") is not True:
            raise HeadnodeReceiptError("controller evidence file row is incomplete")
        relative = _relative_file(row.get("relative_path"), field=f"{role}_file")
        if relative != requested.get(role):
            raise HeadnodeReceiptError("controller evidence file path does not match requested path")
        raw = row.get("content_b64")
        if not isinstance(raw, str):
            raise HeadnodeReceiptError("controller evidence content is missing")
        try:
            data = base64.b64decode(raw.encode("ascii"), validate=True)
        except (ValueError, binascii.Error) as exc:
            raise HeadnodeReceiptError("controller evidence content encoding is invalid") from exc
        expected = row.get("sha256")
        if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-f]{64}", expected):
            raise HeadnodeReceiptError("controller evidence content digest is invalid")
        if hashlib.sha256(data).hexdigest() != expected or row.get("size_bytes") != len(data):
            raise HeadnodeReceiptError("controller evidence content digest or size does not match")
        if len(data) > maximum or limits.get(role) != maximum:
            raise HeadnodeReceiptError("controller evidence file exceeds its fixed bound")
        total += len(data)
        normalized_files[role] = {
            "relative_path": relative,
            "content": data,
            "sha256": expected,
            "size_bytes": len(data),
        }
    if payload.get("file_count") != 2 or payload.get("total_bytes") != total:
        raise HeadnodeReceiptError("controller evidence total is invalid")
    return {
        "schema_version": CONTROLLER_EVIDENCE_SCHEMA,
        "analysis_root": payload["analysis_root"],
        "controller_pid": payload["controller_pid"],
        "confirmed_pid": payload["confirmed_pid"],
        "controller_owner": payload["controller_owner"],
        "controller_cwd": payload["controller_cwd"],
        "requested_files": dict(requested),
        "collected_at": payload.get("collected_at"),
        "files": normalized_files,
        "total_bytes": total,
    }


def _protected_directory(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    info = path.lstat()
    if (
        not stat.S_ISDIR(info.st_mode)
        or stat.S_ISLNK(info.st_mode)
        or info.st_uid != os.getuid()
    ):
        raise HeadnodeReceiptError("output_dir must be an owned 0700 directory")
    os.chmod(path, 0o700)
    resolved = path.resolve(strict=True)
    info = resolved.lstat()
    if info.st_mode & 0o077:
        raise HeadnodeReceiptError("output_dir must be an owned 0700 directory")
    return resolved


def _atomic_write(destination: Path, content: bytes, *, root: Path) -> None:
    parent = _protected_directory(destination.parent)
    try:
        parent.relative_to(root)
    except ValueError as exc:
        raise HeadnodeReceiptError("evidence materialization escaped output_dir") from exc
    if destination.exists() and stat.S_ISLNK(destination.lstat().st_mode):
        raise HeadnodeReceiptError("evidence materialization must not replace a symbolic link")
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{destination.name}.", suffix=".tmp", dir=str(parent))
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, destination)
    finally:
        if temporary.exists():
            temporary.unlink()


def materialize_controller_evidence(
    envelope: Mapping[str, Any],
    *,
    output_dir: object,
    staged_receipt: Mapping[str, Any],
) -> dict[str, Any]:
    """Atomically write only the validated fixed evidence pair to local storage."""

    raw_output = str(output_dir or "").strip()
    if not raw_output:
        raise HeadnodeReceiptError("output_dir is required")
    destination = Path(raw_output).expanduser()
    if not destination.is_absolute():
        raise HeadnodeReceiptError("output_dir must be an absolute path")
    root = _protected_directory(destination)
    files: list[dict[str, Any]] = []
    source_files = envelope.get("files")
    if not isinstance(source_files, Mapping):
        raise HeadnodeReceiptError("validated controller evidence files are unavailable")
    for role in ("log", "dag"):
        row = source_files.get(role)
        if not isinstance(row, Mapping) or not isinstance(row.get("content"), bytes):
            raise HeadnodeReceiptError("validated controller evidence content is unavailable")
        relative = _relative_file(row.get("relative_path"), field=f"{role}_file")
        target = root / relative
        _atomic_write(target, row["content"], root=root)
        files.append(
            {
                "role": role,
                "relative_path": relative,
                "materialized_path": str(target),
                "sha256": row["sha256"],
                "size_bytes": row["size_bytes"],
            }
        )
    receipt = {
        "schema_version": CONTROLLER_EVIDENCE_SCHEMA,
        "ok": True,
        "status": "materialized",
        "analysis_root": envelope["analysis_root"],
        "controller_pid": envelope["controller_pid"],
        "confirmed_pid": envelope["confirmed_pid"],
        "controller_owner": envelope["controller_owner"],
        "controller_cwd": envelope["controller_cwd"],
        "requested_files": envelope["requested_files"],
        "collected_at": envelope.get("collected_at"),
        "complete": True,
        "total_bytes": envelope["total_bytes"],
        "files": files,
        "output_dir": str(root),
        "relay": {
            "s3_uri": staged_receipt["envelope_s3_uri"],
            "sha256": staged_receipt["envelope_sha256"],
            "size_bytes": staged_receipt["envelope_size_bytes"],
        },
    }
    receipt["receipt_sha256"] = hashlib.sha256(
        json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return receipt


__all__ = [
    "CONTROLLER_EVIDENCE_SCHEMA",
    "HeadnodeReceiptError",
    "MAX_ENVELOPE_BYTES",
    "RUNTIME_IDENTITY_SCHEMA",
    "SCHEDULER_SNAPSHOT_SCHEMA",
    "build_controller_evidence_script",
    "build_runtime_identity_script",
    "build_scheduler_snapshot_script",
    "materialize_controller_evidence",
    "parse_controller_evidence_envelope",
    "parse_runtime_identity",
    "parse_scheduler_snapshot",
    "parse_staged_controller_evidence",
]
