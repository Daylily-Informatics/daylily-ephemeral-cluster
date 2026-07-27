"""Bounded semantic headnode-control script builders and JSON parsers.

The builders in this module do not execute remote commands. Callers pass the
returned script to the central ``daylily_ec.aws.ssm.run_shell`` helper. These
DayOA controller helpers currently inspect Ubuntu-owned DayOA controllers.
Inputs are deliberately narrow: no builder accepts shell text, process
selectors, node selectors, or broad regular expressions.
"""

from __future__ import annotations

import json
import re
import textwrap
from collections.abc import Sequence
from typing import Any


REMOTE_USER = "ubuntu"
DEFAULT_MAX_OUTPUT_BYTES = 20 * 1024
MAX_ALLOWED_OUTPUT_BYTES = 20 * 1024
DEFAULT_MAX_CONTROLLERS = 20
DEFAULT_MAX_TMUX_PANES = 40
DEFAULT_MAX_SLURM_JOBS = 100
DEFAULT_MAX_SLURM_JOB_ACTIONS = 64
MAX_ALLOWED_LIST_ITEMS = 256

CONTROLLER_INVENTORY_MARKER = "__DYEC_HEADNODE_CONTROLLER_INVENTORY__="
CONTROLLER_ACTION_MARKER = "__DYEC_HEADNODE_CONTROLLER_ACTION__="
SLURM_JOB_ACTION_MARKER = "__DYEC_HEADNODE_SLURM_JOB_ACTION__="
SLURM_NODE_STATE_MARKER = "__DYEC_HEADNODE_SLURM_NODE_STATE__="

CONTROLLER_INVENTORY_SCHEMA = "dyec.headnode_controller_inventory.v1"
CONTROLLER_ACTION_SCHEMA = "dyec.headnode_controller_action.v1"
SLURM_JOB_ACTION_SCHEMA = "dyec.headnode_slurm_job_action.v1"
SLURM_NODE_STATE_SCHEMA = "dyec.headnode_slurm_node_state.v1"

_SAFE_SEGMENT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_ANALYSIS_ROOT_RE = re.compile(
    r"^/fsx/analysis_results/(?P<owner>[A-Za-z0-9][A-Za-z0-9._-]*)/"
    r"(?P<analysis>[A-Za-z0-9][A-Za-z0-9._-]*)$"
)
_SLURM_JOB_ID_RE = re.compile(r"^[1-9][0-9]*(?:_[0-9]+)?$")
_REASON_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._:/@+-]*$")
_OPERATION_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")

_CONTROLLER_SIGNAL_BY_ACTION = {
    "stop": "STOP",
    "restart": "CONT",
    "kill": "KILL",
}
_SLURM_JOB_COMMAND_BY_ACTION = {
    "suspend": ("scontrol", "suspend"),
    "resume": ("scontrol", "resume"),
    "cancel": ("scancel",),
}
_SLURM_NODE_STATE_BY_ACTION = {
    "drain": "DRAIN",
}


class HeadnodeControlError(ValueError):
    """Raised when a bounded headnode-control contract is invalid."""


def _bounded_int(value: object, *, field: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise HeadnodeControlError(f"{field} must be an integer")
    if value < minimum or value > maximum:
        raise HeadnodeControlError(f"{field} must be between {minimum} and {maximum}")
    return value


def _positive_pid(value: object, *, field: str) -> int:
    if isinstance(value, bool):
        raise HeadnodeControlError(f"{field} must be a positive integer greater than 1")
    text = str(value)
    if text != text.strip():
        raise HeadnodeControlError(f"{field} must be a positive integer greater than 1")
    try:
        parsed = int(text)
    except (TypeError, ValueError) as exc:
        raise HeadnodeControlError(f"{field} must be a positive integer greater than 1") from exc
    if parsed <= 1 or text != str(parsed):
        raise HeadnodeControlError(f"{field} must be a positive integer greater than 1")
    return parsed


def _analysis_root(value: object) -> str:
    text = str(value or "")
    match = _ANALYSIS_ROOT_RE.fullmatch(text)
    if not match:
        raise HeadnodeControlError(
            "expected_analysis_root must be exactly /fsx/analysis_results/<owner>/<analysis>"
        )
    for segment in (match.group("owner"), match.group("analysis")):
        if segment in {".", ".."} or ".." in segment:
            raise HeadnodeControlError("expected_analysis_root contains an unsafe segment")
    return text


def _choice(value: object, *, field: str, choices: set[str]) -> str:
    text = str(value or "").strip().lower()
    if text not in choices:
        raise HeadnodeControlError(f"{field} must be one of: {', '.join(sorted(choices))}")
    return text


def _safe_segment(value: object, *, field: str) -> str:
    text = str(value or "")
    if not _SAFE_SEGMENT_RE.fullmatch(text) or text in {".", ".."} or ".." in text:
        raise HeadnodeControlError(f"{field} must be one path-safe segment")
    return text


def _bounded_text(
    value: object,
    *,
    field: str,
    maximum: int,
    pattern: re.Pattern[str],
) -> str:
    text = str(value or "")
    if not text or text != text.strip() or len(text) > maximum or not pattern.fullmatch(text):
        raise HeadnodeControlError(
            f"{field} must be 1-{maximum} characters and contain only approved characters"
        )
    return text


def _output_limit(value: object) -> int:
    return _bounded_int(
        value,
        field="max_output_bytes",
        minimum=1024,
        maximum=MAX_ALLOWED_OUTPUT_BYTES,
    )


def _remote_python_script(source: str) -> str:
    body = textwrap.dedent(source).strip()
    return (
        "set +e +u\n"
        "set +o pipefail 2>/dev/null || true\n"
        f'if [[ "$(id -un)" != "{REMOTE_USER}" ]]; then\n'
        '  printf "DYEC headnode control requires ubuntu\\n" >&2\n'
        "  exit 91\n"
        "fi\n"
        "python3 - <<'PY'\n"
        f"{body}\n"
        "PY\n"
    )


def build_controller_inventory_script(
    *,
    max_controllers: int = DEFAULT_MAX_CONTROLLERS,
    max_tmux_panes: int = DEFAULT_MAX_TMUX_PANES,
    max_slurm_jobs: int = DEFAULT_MAX_SLURM_JOBS,
    max_output_bytes: int = DEFAULT_MAX_OUTPUT_BYTES,
) -> str:
    """Build a secret-safe, live-process-authoritative controller inventory."""

    controller_limit = _bounded_int(
        max_controllers,
        field="max_controllers",
        minimum=1,
        maximum=MAX_ALLOWED_LIST_ITEMS,
    )
    tmux_limit = _bounded_int(
        max_tmux_panes,
        field="max_tmux_panes",
        minimum=1,
        maximum=MAX_ALLOWED_LIST_ITEMS,
    )
    slurm_limit = _bounded_int(
        max_slurm_jobs,
        field="max_slurm_jobs",
        minimum=1,
        maximum=MAX_ALLOWED_LIST_ITEMS,
    )
    output_limit = _output_limit(max_output_bytes)
    return _remote_python_script(
        f"""
        import datetime
        import json
        import os
        from pathlib import Path
        import re
        import subprocess

        MARKER = {CONTROLLER_INVENTORY_MARKER!r}
        SCHEMA = {CONTROLLER_INVENTORY_SCHEMA!r}
        MAX_CONTROLLERS = {controller_limit}
        MAX_TMUX_PANES = {tmux_limit}
        MAX_SLURM_JOBS = {slurm_limit}
        MAX_RECEIPT_SCAN_ENTRIES = {MAX_ALLOWED_LIST_ITEMS}
        MAX_PROCESS_SCAN_ENTRIES = 4096
        MAX_OUTPUT_BYTES = {output_limit}
        REMOTE_USER = {REMOTE_USER!r}
        ANALYSIS_ROOT_PATTERN = re.compile(
            r"^/fsx/analysis_results/[A-Za-z0-9][A-Za-z0-9._-]*/"
            r"[A-Za-z0-9][A-Za-z0-9._-]*$"
        )
        CONTROLLER_ENTRYPOINT_NAMES = (
            "dy-r",
            "dayoa-controller-launch.sh",
        )

        def run(argv):
            try:
                result = subprocess.run(
                    argv,
                    capture_output=True,
                    text=True,
                    timeout=15,
                    check=False,
                )
            except (OSError, subprocess.SubprocessError):
                return "", 127
            return result.stdout or "", int(result.returncode)

        def path_within(path, root):
            return bool(path and (path == root or path.startswith(root.rstrip("/") + "/")))

        def read_live_controller(proc_dir, expected_uid):
            try:
                status_lines = (proc_dir / "status").read_text(
                    encoding="utf-8", errors="replace"
                ).splitlines()
                uid_line = next(line for line in status_lines if line.startswith("Uid:"))
                state_line = next(line for line in status_lines if line.startswith("State:"))
                process_uid = int(uid_line.split()[1])
                process_state = state_line.split()[1][:8]
            except (OSError, StopIteration, ValueError, IndexError):
                return None, proc_dir.is_dir()
            if process_uid != expected_uid or process_state == "Z":
                return None, False
            try:
                command_bytes = (proc_dir / "cmdline").read_bytes()[:8192]
                command_parts = [
                    part.decode("utf-8", errors="replace")
                    for part in command_bytes.split(b"\\x00")
                    if part
                ]
                entrypoint_names = [Path(part).name for part in command_parts]
                if not entrypoint_names or not (
                    entrypoint_names[0] == CONTROLLER_ENTRYPOINT_NAMES[0]
                    or CONTROLLER_ENTRYPOINT_NAMES[1] in entrypoint_names[1:]
                ):
                    return None, False
                cwd = os.readlink(proc_dir / "cwd")
                command_name = (proc_dir / "comm").read_text(
                    encoding="utf-8", errors="replace"
                ).strip()
            except OSError:
                return None, proc_dir.is_dir()
            return {{
                "pid": int(proc_dir.name),
                "owner": REMOTE_USER,
                "process_state": process_state,
                "command_name": Path(command_name).name[:64] or None,
                "live_cwd": cwd[:512] or None,
                "recognized_dayoa_controller": True,
                "live": True,
            }}, False

        errors = []
        tmux_stdout, tmux_rc = run([
            "tmux",
            "list-panes",
            "-a",
            "-F",
            "#{{session_name}}\\t#{{pane_pid}}\\t#{{pane_current_path}}\\t#{{pane_current_command}}",
        ])
        tmux_panes = []
        for line in tmux_stdout.splitlines()[:MAX_TMUX_PANES]:
            fields = line.split("\\t", 3)
            if len(fields) != 4 or not fields[0].strip() or not fields[1].strip().isdigit():
                continue
            tmux_panes.append({{
                "session_name": fields[0].strip()[:128],
                "pane_pid": int(fields[1].strip()),
                "current_path": fields[2].strip()[:512] or None,
                "current_command": Path(fields[3].strip()).name[:64] or None,
            }})
        tmux_total = len(tmux_stdout.splitlines())
        if tmux_rc not in (0, 1):
            errors.append("tmux_inventory_failed")

        run_root = Path("/home") / REMOTE_USER / "daylily-runs"
        receipt_paths = []
        receipt_scan_truncated = False
        try:
            if run_root.is_dir():
                for index, entry in enumerate(sorted(run_root.iterdir(), key=lambda item: item.name)):
                    if index >= MAX_RECEIPT_SCAN_ENTRIES:
                        receipt_scan_truncated = True
                        break
                    candidate = entry / "controller_target.json"
                    if entry.is_dir() and candidate.is_file():
                        receipt_paths.append(candidate)
        except OSError:
            errors.append("controller_receipt_inventory_failed")

        receipts_by_pid = {{}}
        invalid_receipt_count = 0
        for path in receipt_paths:
            try:
                receipt = json.loads(path.read_text(encoding="utf-8")[:16384])
                pid = int(receipt["pid"])
                controller_id = str(receipt["controller_id"])
                analysis_root = str(receipt["analysis_root"])
                recorded_cwd = str(receipt["cwd"])
                if (
                    pid <= 1
                    or not controller_id
                    or not ANALYSIS_ROOT_PATTERN.fullmatch(analysis_root)
                    or not path_within(recorded_cwd, analysis_root)
                ):
                    raise ValueError("invalid controller receipt")
            except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
                invalid_receipt_count += 1
                continue
            receipts_by_pid.setdefault(pid, []).append({{
                "receipt_key": str(path),
                "controller_id": controller_id[:128],
                "analysis_root": analysis_root[:512],
                "recorded_cwd": recorded_cwd[:512],
            }})

        proc_dirs = []
        process_scan_truncated = False
        try:
            with os.scandir("/proc") as entries:
                for entry in entries:
                    if not entry.name.isdigit():
                        continue
                    if len(proc_dirs) >= MAX_PROCESS_SCAN_ENTRIES:
                        process_scan_truncated = True
                        break
                    proc_dirs.append(Path(entry.path))
        except OSError:
            errors.append("controller_process_inventory_failed")
        proc_dirs.sort(key=lambda item: int(item.name))

        expected_uid = os.getuid()
        live_controllers = []
        matched_receipt_keys = set()
        unreceipted_live_controller_count = 0
        process_identity_error_count = 0
        for proc_dir in proc_dirs:
            controller, identity_error = read_live_controller(proc_dir, expected_uid)
            if identity_error:
                process_identity_error_count += 1
            if controller is None:
                continue
            pid = controller["pid"]
            receipt = None
            for candidate in receipts_by_pid.get(pid, []):
                if path_within(controller["live_cwd"], candidate["analysis_root"]):
                    receipt = candidate
                    matched_receipt_keys.add(candidate["receipt_key"])
                    break
            if receipt is None:
                unreceipted_live_controller_count += 1
                controller.update({{
                    "receipt_present": False,
                    "controller_id": None,
                    "analysis_root": None,
                    "recorded_cwd": None,
                    "live_cwd_in_analysis_root": None,
                }})
            else:
                controller.update({{
                    "receipt_present": True,
                    "controller_id": receipt["controller_id"],
                    "analysis_root": receipt["analysis_root"],
                    "recorded_cwd": receipt["recorded_cwd"],
                    "live_cwd_in_analysis_root": True,
                }})
            matching_sessions = sorted({{
                pane["session_name"]
                for pane in tmux_panes
                if pane["pane_pid"] == pid
                or (
                    controller["controller_id"] is not None
                    and pane["session_name"] == controller["controller_id"]
                )
            }})
            controller.update({{
                "tmux_session": matching_sessions[0] if len(matching_sessions) == 1 else None,
                "tmux_session_candidates": matching_sessions[:4],
            }})
            live_controllers.append(controller)
        controller_total = len(live_controllers)
        controllers = live_controllers[:MAX_CONTROLLERS]
        receipt_total = sum(len(receipts) for receipts in receipts_by_pid.values())
        stale_receipt_count = receipt_total - len(matched_receipt_keys)
        if process_scan_truncated:
            errors.append("controller_process_scan_truncated")
        if process_identity_error_count:
            errors.append("controller_process_identity_unavailable")
        controller_count_authoritative = not (
            process_scan_truncated or process_identity_error_count
        )

        squeue_stdout, squeue_rc = run([
            "/opt/slurm/bin/squeue",
            "-h",
            "-u",
            REMOTE_USER,
            "-o",
            "%A|%T|%P",
        ])
        slurm_jobs = []
        slurm_state_counts = {{}}
        for line in squeue_stdout.splitlines():
            fields = line.split("|", 2)
            if len(fields) != 3 or not fields[0].strip():
                continue
            state = fields[1].strip().upper()[:64] or "UNKNOWN"
            slurm_state_counts[state] = slurm_state_counts.get(state, 0) + 1
            if len(slurm_jobs) < MAX_SLURM_JOBS:
                slurm_jobs.append({{
                    "job_id": fields[0].strip()[:64],
                    "state": state,
                    "partition": fields[2].strip()[:64] or None,
                }})
        slurm_total = sum(slurm_state_counts.values())
        if squeue_rc != 0:
            errors.append("slurm_inventory_failed")

        payload = {{
            "schema_version": SCHEMA,
            "ok": not errors,
            "observed_at": datetime.datetime.now(datetime.timezone.utc).isoformat().replace(
                "+00:00", "Z"
            ),
            "remote_user": REMOTE_USER,
            "controllers": controllers,
            "controller_count": controller_total,
            "controller_count_authoritative": controller_count_authoritative,
            "controllers_truncated": controller_total > len(controllers),
            "controller_process_identity_error_count": process_identity_error_count,
            "receipted_live_controller_count": (
                controller_total - unreceipted_live_controller_count
            ),
            "unreceipted_live_controller_count": unreceipted_live_controller_count,
            "stale_controller_receipt_count": stale_receipt_count,
            "invalid_controller_receipt_count": invalid_receipt_count,
            "controller_receipt_scan_truncated": receipt_scan_truncated,
            "controller_receipt_enrichment_complete": not receipt_scan_truncated,
            "controller_process_scan_truncated": process_scan_truncated,
            "tmux_sessions": sorted({{pane["session_name"] for pane in tmux_panes}}),
            "tmux_panes": tmux_panes,
            "tmux_pane_count": tmux_total,
            "tmux_panes_truncated": tmux_total > len(tmux_panes),
            "slurm_jobs": slurm_jobs,
            "slurm_job_count": slurm_total,
            "slurm_jobs_truncated": slurm_total > len(slurm_jobs),
            "slurm_state_counts": slurm_state_counts,
            "errors": errors,
        }}
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        if len(encoded.encode("utf-8")) > MAX_OUTPUT_BYTES:
            payload = {{
                "schema_version": SCHEMA,
                "ok": False,
                "error": "output_limit_exceeded",
                "max_output_bytes": MAX_OUTPUT_BYTES,
            }}
            encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        print(MARKER + encoded)
        """
    )


def build_controller_action_script(
    *,
    pid: object,
    confirm_pid: object,
    expected_analysis_root: object,
    action: object,
    max_output_bytes: int = DEFAULT_MAX_OUTPUT_BYTES,
) -> str:
    """Build a bounded, identity-revalidating DayOA controller signal script."""

    resolved_pid = _positive_pid(pid, field="pid")
    resolved_confirm_pid = _positive_pid(confirm_pid, field="confirm_pid")
    if resolved_pid != resolved_confirm_pid:
        raise HeadnodeControlError("confirm_pid must exactly match pid")
    resolved_root = _analysis_root(expected_analysis_root)
    resolved_action = _choice(
        action,
        field="action",
        choices=set(_CONTROLLER_SIGNAL_BY_ACTION),
    )
    resolved_signal = _CONTROLLER_SIGNAL_BY_ACTION[resolved_action]
    output_limit = _output_limit(max_output_bytes)
    return _remote_python_script(
        f"""
        import json
        import os
        from pathlib import Path
        import signal

        MARKER = {CONTROLLER_ACTION_MARKER!r}
        SCHEMA = {CONTROLLER_ACTION_SCHEMA!r}
        PID = {resolved_pid}
        CONFIRM_PID = {resolved_confirm_pid}
        EXPECTED_ANALYSIS_ROOT = {resolved_root!r}
        ACTION = {resolved_action!r}
        SIGNAL_NAME = {resolved_signal!r}
        MAX_OUTPUT_BYTES = {output_limit}
        REMOTE_USER = {REMOTE_USER!r}
        CONTROLLER_ENTRYPOINT_NAMES = (
            "dy-r",
            "dayoa-controller-launch.sh",
        )

        def emit(payload):
            encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
            if len(encoded.encode("utf-8")) > MAX_OUTPUT_BYTES:
                encoded = json.dumps({{
                    "schema_version": SCHEMA,
                    "ok": False,
                    "error": "output_limit_exceeded",
                    "signal_sent": False,
                }}, sort_keys=True, separators=(",", ":"))
            print(MARKER + encoded)

        def fail(code):
            emit({{
                "schema_version": SCHEMA,
                "ok": False,
                "error": code,
                "pid": PID,
                "action": ACTION,
                "signal": SIGNAL_NAME,
                "expected_analysis_root": EXPECTED_ANALYSIS_ROOT,
                "signal_sent": False,
            }})
            raise SystemExit(2)

        if PID != CONFIRM_PID:
            fail("confirm_pid_mismatch")
        proc_root = Path(f"/proc/{{PID}}")
        if not proc_root.is_dir():
            fail("process_not_live")
        try:
            status_lines = (proc_root / "status").read_text(encoding="utf-8").splitlines()
            uid_line = next(line for line in status_lines if line.startswith("Uid:"))
            process_uid = int(uid_line.split()[1])
            ubuntu_uid = os.getuid()
            cwd = os.readlink(proc_root / "cwd")
            command_bytes = (proc_root / "cmdline").read_bytes()[:8192]
        except (OSError, StopIteration, ValueError):
            fail("process_identity_unavailable")
        if process_uid != ubuntu_uid or ubuntu_uid == 0:
            fail("process_not_ubuntu_owned")
        if not (cwd == EXPECTED_ANALYSIS_ROOT or cwd.startswith(EXPECTED_ANALYSIS_ROOT + "/")):
            fail("process_cwd_outside_expected_analysis_root")
        command_parts = [
            part.decode("utf-8", errors="replace")
            for part in command_bytes.split(b"\\x00")
            if part
        ]
        entrypoint_names = [Path(part).name for part in command_parts]
        if not entrypoint_names or not (
            entrypoint_names[0] == CONTROLLER_ENTRYPOINT_NAMES[0]
            or CONTROLLER_ENTRYPOINT_NAMES[1] in entrypoint_names[1:]
        ):
            fail("process_not_recognized_dayoa_controller")
        signal_number = getattr(signal, "SIG" + SIGNAL_NAME)
        try:
            os.kill(PID, signal_number)
        except ProcessLookupError:
            fail("process_exited_before_signal")
        except PermissionError:
            fail("signal_permission_denied")
        emit({{
            "schema_version": SCHEMA,
            "ok": True,
            "pid": PID,
            "action": ACTION,
            "signal": SIGNAL_NAME,
            "expected_analysis_root": EXPECTED_ANALYSIS_ROOT,
            "live_cwd": cwd,
            "owner": REMOTE_USER,
            "recognized_dayoa_controller": True,
            "signal_sent": True,
        }})
        """
    )


def _validated_job_ids(job_ids: object, *, max_job_count: int) -> list[str]:
    if isinstance(job_ids, (str, bytes)) or not isinstance(job_ids, Sequence):
        raise HeadnodeControlError("job_ids must be a sequence of explicit Slurm job IDs")
    if not job_ids:
        raise HeadnodeControlError("job_ids must not be empty")
    if len(job_ids) > max_job_count:
        raise HeadnodeControlError(f"job_ids exceeds max_job_count={max_job_count}")
    resolved: list[str] = []
    for value in job_ids:
        text = str(value or "")
        if not _SLURM_JOB_ID_RE.fullmatch(text):
            raise HeadnodeControlError(f"invalid Slurm job ID: {text!r}")
        if text in resolved:
            raise HeadnodeControlError(f"duplicate Slurm job ID: {text}")
        resolved.append(text)
    return resolved


def build_slurm_job_action_script(
    *,
    action: object,
    job_ids: object,
    max_job_count: int = DEFAULT_MAX_SLURM_JOB_ACTIONS,
    max_output_bytes: int = DEFAULT_MAX_OUTPUT_BYTES,
) -> str:
    """Build a bounded Slurm suspend, resume, or cancel script for explicit job IDs."""

    resolved_action = _choice(
        action,
        field="action",
        choices=set(_SLURM_JOB_COMMAND_BY_ACTION),
    )
    resolved_max_jobs = _bounded_int(
        max_job_count,
        field="max_job_count",
        minimum=1,
        maximum=MAX_ALLOWED_LIST_ITEMS,
    )
    resolved_job_ids = _validated_job_ids(job_ids, max_job_count=resolved_max_jobs)
    command = [*_SLURM_JOB_COMMAND_BY_ACTION[resolved_action], *resolved_job_ids]
    output_limit = _output_limit(max_output_bytes)
    return _remote_python_script(
        f"""
        import json
        import subprocess

        MARKER = {SLURM_JOB_ACTION_MARKER!r}
        SCHEMA = {SLURM_JOB_ACTION_SCHEMA!r}
        ACTION = {resolved_action!r}
        JOB_IDS = {resolved_job_ids!r}
        COMMAND = {command!r}
        MAX_OUTPUT_BYTES = {output_limit}

        try:
            result = subprocess.run(
                COMMAND,
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )
            return_code = int(result.returncode)
            error = None if return_code == 0 else "slurm_job_action_failed"
        except (OSError, subprocess.SubprocessError):
            return_code = 127
            error = "slurm_job_action_unavailable"
        payload = {{
            "schema_version": SCHEMA,
            "ok": return_code == 0,
            "action": ACTION,
            "job_ids": JOB_IDS,
            "job_count": len(JOB_IDS),
            "return_code": return_code,
            "error": error,
        }}
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        if len(encoded.encode("utf-8")) > MAX_OUTPUT_BYTES:
            encoded = json.dumps({{
                "schema_version": SCHEMA,
                "ok": False,
                "error": "output_limit_exceeded",
            }}, sort_keys=True, separators=(",", ":"))
        print(MARKER + encoded)
        raise SystemExit(return_code)
        """
    )


def build_slurm_all_node_state_script(
    *,
    action: object,
    cluster: object,
    confirm_cluster: object,
    reason: object,
    operation_id: object,
    max_output_bytes: int = DEFAULT_MAX_OUTPUT_BYTES,
) -> str:
    """Build a confirmed all-node DRAIN operation that never cancels jobs."""

    resolved_action = _choice(
        action,
        field="action",
        choices=set(_SLURM_NODE_STATE_BY_ACTION),
    )
    resolved_state = _SLURM_NODE_STATE_BY_ACTION[resolved_action]
    resolved_cluster = _safe_segment(cluster, field="cluster")
    resolved_confirm_cluster = _safe_segment(confirm_cluster, field="confirm_cluster")
    if resolved_cluster != resolved_confirm_cluster:
        raise HeadnodeControlError("confirm_cluster must exactly match cluster")
    resolved_reason = _bounded_text(
        reason,
        field="reason",
        maximum=128,
        pattern=_REASON_RE,
    )
    resolved_operation_id = _bounded_text(
        operation_id,
        field="operation_id",
        maximum=64,
        pattern=_OPERATION_ID_RE,
    )
    output_limit = _output_limit(max_output_bytes)
    command = [
        "scontrol",
        "update",
        "NodeName=ALL",
        f"State={resolved_state}",
        f"Reason={resolved_reason} [operation_id={resolved_operation_id}]",
    ]
    return _remote_python_script(
        f"""
        import json
        import subprocess

        MARKER = {SLURM_NODE_STATE_MARKER!r}
        SCHEMA = {SLURM_NODE_STATE_SCHEMA!r}
        ACTION = {resolved_action!r}
        STATE = {resolved_state!r}
        CLUSTER = {resolved_cluster!r}
        CONFIRM_CLUSTER = {resolved_confirm_cluster!r}
        REASON = {resolved_reason!r}
        OPERATION_ID = {resolved_operation_id!r}
        COMMAND = {command!r}
        MAX_OUTPUT_BYTES = {output_limit}

        if CLUSTER != CONFIRM_CLUSTER:
            payload = {{
                "schema_version": SCHEMA,
                "ok": False,
                "error": "confirm_cluster_mismatch",
                "action": ACTION,
                "state": STATE,
                "cluster": CLUSTER,
                "operation_id": OPERATION_ID,
                "jobs_cancelled": False,
            }}
            return_code = 2
        else:
            try:
                result = subprocess.run(
                    COMMAND,
                    capture_output=True,
                    text=True,
                    timeout=60,
                    check=False,
                )
                return_code = int(result.returncode)
                error = None if return_code == 0 else "slurm_node_state_action_failed"
            except (OSError, subprocess.SubprocessError):
                return_code = 127
                error = "slurm_node_state_action_unavailable"
            payload = {{
                "schema_version": SCHEMA,
                "ok": return_code == 0,
                "error": error,
                "action": ACTION,
                "state": STATE,
                "cluster": CLUSTER,
                "reason": REASON,
                "operation_id": OPERATION_ID,
                "node_selector": "ALL",
                "jobs_cancelled": False,
                "return_code": return_code,
            }}
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        if len(encoded.encode("utf-8")) > MAX_OUTPUT_BYTES:
            encoded = json.dumps({{
                "schema_version": SCHEMA,
                "ok": False,
                "error": "output_limit_exceeded",
                "jobs_cancelled": False,
            }}, sort_keys=True, separators=(",", ":"))
        print(MARKER + encoded)
        raise SystemExit(return_code)
        """
    )


def _parse_marker_payload(
    stdout: object,
    *,
    marker: str,
    schema: str,
    max_output_bytes: int,
) -> dict[str, Any]:
    output_limit = _output_limit(max_output_bytes)
    if not isinstance(stdout, str):
        raise HeadnodeControlError("headnode output must be text")
    if len(stdout.encode("utf-8")) > output_limit:
        raise HeadnodeControlError("headnode output exceeds max_output_bytes")
    marker_lines = [line for line in stdout.splitlines() if line.startswith(marker)]
    if len(marker_lines) != 1:
        raise HeadnodeControlError(f"expected exactly one {marker.rstrip('=')} marker")
    raw_payload = marker_lines[0][len(marker) :]
    try:
        payload = json.loads(raw_payload)
    except json.JSONDecodeError as exc:
        raise HeadnodeControlError("headnode marker payload is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise HeadnodeControlError("headnode marker payload must be a JSON object")
    if payload.get("schema_version") != schema:
        raise HeadnodeControlError(f"headnode payload schema must be {schema}")
    if not isinstance(payload.get("ok"), bool):
        raise HeadnodeControlError("headnode payload ok must be boolean")
    return payload


def parse_controller_inventory_output(
    stdout: object,
    *,
    max_output_bytes: int = DEFAULT_MAX_OUTPUT_BYTES,
) -> dict[str, Any]:
    payload = _parse_marker_payload(
        stdout,
        marker=CONTROLLER_INVENTORY_MARKER,
        schema=CONTROLLER_INVENTORY_SCHEMA,
        max_output_bytes=max_output_bytes,
    )
    if payload.get("error") == "output_limit_exceeded":
        return payload
    for field in ("controllers", "tmux_panes", "tmux_sessions", "slurm_jobs", "errors"):
        if not isinstance(payload.get(field), list):
            raise HeadnodeControlError(f"controller inventory {field} must be a list")
    if not isinstance(payload.get("slurm_state_counts"), dict):
        raise HeadnodeControlError("controller inventory slurm_state_counts must be an object")
    count_fields = (
        "controller_count",
        "controller_process_identity_error_count",
        "receipted_live_controller_count",
        "unreceipted_live_controller_count",
        "stale_controller_receipt_count",
        "invalid_controller_receipt_count",
    )
    for field in count_fields:
        value = payload.get(field)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise HeadnodeControlError(
                f"controller inventory {field} must be a nonnegative integer"
            )
    boolean_fields = (
        "controller_count_authoritative",
        "controllers_truncated",
        "controller_receipt_scan_truncated",
        "controller_receipt_enrichment_complete",
        "controller_process_scan_truncated",
    )
    for field in boolean_fields:
        if not isinstance(payload.get(field), bool):
            raise HeadnodeControlError(f"controller inventory {field} must be boolean")
    if (
        payload["receipted_live_controller_count"] + payload["unreceipted_live_controller_count"]
        != payload["controller_count"]
    ):
        raise HeadnodeControlError("controller inventory live controller counts are inconsistent")
    if len(payload["controllers"]) > payload["controller_count"]:
        raise HeadnodeControlError("controller inventory controllers exceed controller_count")
    expected_authority = not (
        payload["controller_process_scan_truncated"]
        or payload["controller_process_identity_error_count"]
    )
    if payload["controller_count_authoritative"] != expected_authority:
        raise HeadnodeControlError(
            "controller inventory process scan authority fields are inconsistent"
        )
    if not expected_authority and payload["ok"]:
        raise HeadnodeControlError("incomplete controller process inventory cannot report success")
    if (
        payload["controller_receipt_enrichment_complete"]
        == payload["controller_receipt_scan_truncated"]
    ):
        raise HeadnodeControlError(
            "controller inventory receipt scan completeness fields are inconsistent"
        )
    return payload


def parse_controller_action_output(
    stdout: object,
    *,
    max_output_bytes: int = DEFAULT_MAX_OUTPUT_BYTES,
) -> dict[str, Any]:
    payload = _parse_marker_payload(
        stdout,
        marker=CONTROLLER_ACTION_MARKER,
        schema=CONTROLLER_ACTION_SCHEMA,
        max_output_bytes=max_output_bytes,
    )
    if not isinstance(payload.get("signal_sent"), bool):
        raise HeadnodeControlError("controller action signal_sent must be boolean")
    return payload


def parse_slurm_job_action_output(
    stdout: object,
    *,
    max_output_bytes: int = DEFAULT_MAX_OUTPUT_BYTES,
) -> dict[str, Any]:
    payload = _parse_marker_payload(
        stdout,
        marker=SLURM_JOB_ACTION_MARKER,
        schema=SLURM_JOB_ACTION_SCHEMA,
        max_output_bytes=max_output_bytes,
    )
    if payload.get("error") != "output_limit_exceeded":
        if not isinstance(payload.get("job_ids"), list):
            raise HeadnodeControlError("Slurm job action job_ids must be a list")
        if not isinstance(payload.get("return_code"), int):
            raise HeadnodeControlError("Slurm job action return_code must be an integer")
    return payload


def parse_slurm_all_node_state_output(
    stdout: object,
    *,
    max_output_bytes: int = DEFAULT_MAX_OUTPUT_BYTES,
) -> dict[str, Any]:
    payload = _parse_marker_payload(
        stdout,
        marker=SLURM_NODE_STATE_MARKER,
        schema=SLURM_NODE_STATE_SCHEMA,
        max_output_bytes=max_output_bytes,
    )
    if not isinstance(payload.get("jobs_cancelled"), bool):
        raise HeadnodeControlError("Slurm node-state jobs_cancelled must be boolean")
    if payload["jobs_cancelled"]:
        raise HeadnodeControlError("Slurm all-node state action must never cancel jobs")
    return payload
