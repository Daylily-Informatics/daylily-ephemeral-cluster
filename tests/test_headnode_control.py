from __future__ import annotations

import inspect
import json
import subprocess

import pytest

import daylily_ec.headnode_control as headnode_control
from daylily_ec.headnode_control import (
    CONTROLLER_ACTION_MARKER,
    CONTROLLER_ACTION_SCHEMA,
    CONTROLLER_INVENTORY_MARKER,
    CONTROLLER_INVENTORY_SCHEMA,
    DEFAULT_MAX_OUTPUT_BYTES,
    MAX_ALLOWED_OUTPUT_BYTES,
    SLURM_JOB_ACTION_MARKER,
    SLURM_JOB_ACTION_SCHEMA,
    SLURM_NODE_STATE_MARKER,
    SLURM_NODE_STATE_SCHEMA,
    HeadnodeControlError,
    build_controller_action_script,
    build_controller_inventory_script,
    build_slurm_all_node_state_script,
    build_slurm_job_action_script,
    parse_controller_action_output,
    parse_controller_inventory_output,
    parse_slurm_all_node_state_output,
    parse_slurm_job_action_output,
)


def marker_output(marker: str, payload: dict[str, object]) -> str:
    return "DAY-EC activated.\n" + marker + json.dumps(payload, separators=(",", ":")) + "\n"


def controller_inventory_payload() -> dict[str, object]:
    return {
        "schema_version": CONTROLLER_INVENTORY_SCHEMA,
        "ok": True,
        "controllers": [],
        "controller_count": 0,
        "controller_count_authoritative": True,
        "controllers_truncated": False,
        "controller_process_identity_error_count": 0,
        "receipted_live_controller_count": 0,
        "unreceipted_live_controller_count": 0,
        "stale_controller_receipt_count": 0,
        "invalid_controller_receipt_count": 0,
        "controller_receipt_scan_truncated": False,
        "controller_receipt_enrichment_complete": True,
        "controller_process_scan_truncated": False,
        "tmux_panes": [],
        "tmux_sessions": [],
        "slurm_jobs": [],
        "slurm_state_counts": {},
        "errors": [],
    }


def test_build_controller_inventory_is_bounded_and_secret_safe() -> None:
    script = build_controller_inventory_script(
        max_controllers=7,
        max_tmux_panes=9,
        max_slurm_jobs=11,
        max_output_bytes=16384,
    )

    assert '"$(id -un)" != "ubuntu"' in script
    assert script.startswith("set +e +u\nset +o pipefail 2>/dev/null || true\n")
    assert "set -euo pipefail" not in script
    assert "controller_target.json" in script
    assert '"tmux",\n    "list-panes"' in script
    assert '"/opt/slurm/bin/squeue"' in script
    assert '"-u",\n    REMOTE_USER' in script
    assert "MAX_CONTROLLERS = 7" in script
    assert "MAX_TMUX_PANES = 9" in script
    assert "MAX_SLURM_JOBS = 11" in script
    assert "MAX_OUTPUT_BYTES = 16384" in script
    assert CONTROLLER_INVENTORY_MARKER in script
    assert CONTROLLER_INVENTORY_SCHEMA in script
    assert 'os.scandir("/proc")' in script
    assert 'proc_dir / "cmdline"' in script
    assert 'proc_dir / "status"' in script
    assert 'proc_dir / "cwd"' in script
    assert 'proc_dir / "environ"' not in script
    assert "entrypoint_names[0] == CONTROLLER_ENTRYPOINT_NAMES[0]" in script
    assert "CONTROLLER_ENTRYPOINT_NAMES[1] in entrypoint_names[1:]" in script
    assert '"command": command' not in script
    assert '"cmdline":' not in script
    assert '"argv":' not in script
    assert "args=" not in script


def test_default_and_maximum_stdout_caps_are_at_most_20_kib() -> None:
    assert DEFAULT_MAX_OUTPUT_BYTES <= 20 * 1024
    assert MAX_ALLOWED_OUTPUT_BYTES <= 20 * 1024
    assert f"MAX_OUTPUT_BYTES = {DEFAULT_MAX_OUTPUT_BYTES}" in (build_controller_inventory_script())


def test_controller_inventory_counts_live_processes_not_receipts() -> None:
    script = build_controller_inventory_script()

    assert "receipts_by_pid.setdefault(pid, []).append" in script
    assert "for proc_dir in proc_dirs:" in script
    assert "controller, identity_error = read_live_controller(proc_dir, expected_uid)" in script
    assert "live_controllers.append(controller)" in script
    assert "controller_total = len(live_controllers)" in script
    assert '"receipt_present": False' in script
    assert '"unreceipted_live_controller_count"' in script
    assert '"stale_controller_receipt_count"' in script
    assert '"controller_count_authoritative": controller_count_authoritative' in script
    assert "controller_process_scan_truncated" in script
    assert '"controller_process_identity_error_count"' in script


def test_receipts_only_enrich_matching_live_controller_roots() -> None:
    script = build_controller_inventory_script()

    assert "ANALYSIS_ROOT_PATTERN.fullmatch(analysis_root)" in script
    assert "path_within(recorded_cwd, analysis_root)" in script
    assert 'path_within(controller["live_cwd"], candidate["analysis_root"])' in script
    assert "receipt_total - len(matched_receipt_keys)" in script


def test_missing_controller_receipt_root_is_empty_inventory_not_failure() -> None:
    script = build_controller_inventory_script()

    assert "if run_root.is_dir():" in script
    assert "errors.append(\"controller_receipt_inventory_failed\")" in script


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("max_controllers", 0),
        ("max_tmux_panes", 257),
        ("max_slurm_jobs", True),
        ("max_output_bytes", 100),
        ("max_output_bytes", 20 * 1024 + 1),
    ],
)
def test_controller_inventory_rejects_invalid_limits(field: str, value: object) -> None:
    kwargs = {field: value}
    with pytest.raises(HeadnodeControlError):
        build_controller_inventory_script(**kwargs)


def test_parse_controller_inventory_accepts_one_exact_marker() -> None:
    payload = controller_inventory_payload()

    assert (
        parse_controller_inventory_output(marker_output(CONTROLLER_INVENTORY_MARKER, payload))
        == payload
    )


def test_parse_controller_inventory_rejects_missing_duplicate_and_wrong_schema() -> None:
    payload = controller_inventory_payload()
    line = CONTROLLER_INVENTORY_MARKER + json.dumps(payload)
    with pytest.raises(HeadnodeControlError, match="exactly one"):
        parse_controller_inventory_output("no marker")
    with pytest.raises(HeadnodeControlError, match="exactly one"):
        parse_controller_inventory_output(line + "\n" + line)
    payload["schema_version"] = "wrong"
    with pytest.raises(HeadnodeControlError, match="schema"):
        parse_controller_inventory_output(marker_output(CONTROLLER_INVENTORY_MARKER, payload))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("controller_count", True),
        ("controller_process_identity_error_count", -1),
        ("unreceipted_live_controller_count", -1),
        ("stale_controller_receipt_count", "1"),
        ("controller_count_authoritative", 1),
    ],
)
def test_parse_controller_inventory_rejects_invalid_authority_counts(
    field: str,
    value: object,
) -> None:
    payload = controller_inventory_payload()
    payload[field] = value

    with pytest.raises(HeadnodeControlError):
        parse_controller_inventory_output(marker_output(CONTROLLER_INVENTORY_MARKER, payload))


def test_parse_controller_inventory_rejects_inconsistent_live_counts() -> None:
    payload = controller_inventory_payload()
    payload["controller_count"] = 2
    payload["receipted_live_controller_count"] = 1

    with pytest.raises(HeadnodeControlError, match="counts are inconsistent"):
        parse_controller_inventory_output(marker_output(CONTROLLER_INVENTORY_MARKER, payload))


def test_parse_controller_inventory_requires_fail_closed_scan_authority() -> None:
    payload = controller_inventory_payload()
    payload["controller_process_scan_truncated"] = True

    with pytest.raises(HeadnodeControlError, match="authority fields"):
        parse_controller_inventory_output(marker_output(CONTROLLER_INVENTORY_MARKER, payload))


def test_parse_controller_inventory_rejects_success_for_truncated_process_scan() -> None:
    payload = controller_inventory_payload()
    payload["controller_count_authoritative"] = False
    payload["controller_process_scan_truncated"] = True

    with pytest.raises(HeadnodeControlError, match="cannot report success"):
        parse_controller_inventory_output(marker_output(CONTROLLER_INVENTORY_MARKER, payload))


def test_parse_controller_inventory_rejects_success_for_identity_gap() -> None:
    payload = controller_inventory_payload()
    payload["controller_count_authoritative"] = False
    payload["controller_process_identity_error_count"] = 1

    with pytest.raises(HeadnodeControlError, match="cannot report success"):
        parse_controller_inventory_output(marker_output(CONTROLLER_INVENTORY_MARKER, payload))


@pytest.mark.parametrize(
    ("action", "signal_name"),
    [("stop", "STOP"), ("restart", "CONT"), ("kill", "KILL")],
)
def test_controller_action_maps_only_approved_signals(action: str, signal_name: str) -> None:
    script = build_controller_action_script(
        pid=4242,
        confirm_pid="4242",
        expected_analysis_root="/fsx/analysis_results/ubuntu/analysis-1",
        action=action,
    )

    assert f"ACTION = '{action}'" in script
    assert f"SIGNAL_NAME = '{signal_name}'" in script
    assert "os.kill(PID, signal_number)" in script
    assert '"$(id -un)" != "ubuntu"' in script
    assert '"Uid:"' in script
    assert 'proc_root / "cwd"' in script
    assert 'proc_root / "cmdline"' in script
    assert "entrypoint_names[0] == CONTROLLER_ENTRYPOINT_NAMES[0]" in script
    assert "CONTROLLER_ENTRYPOINT_NAMES[1] in entrypoint_names[1:]" in script
    assert "process_not_recognized_dayoa_controller" in script
    assert "process_cwd_outside_expected_analysis_root" in script
    assert '"command": command_text' not in script
    assert '"cmdline":' not in script
    assert CONTROLLER_ACTION_MARKER in script
    assert CONTROLLER_ACTION_SCHEMA in script


@pytest.mark.parametrize("value", [0, 1, -1, True, "2.0", " 42", "42 ", "x"])
def test_controller_action_rejects_nonpositive_or_noncanonical_pid(value: object) -> None:
    with pytest.raises(HeadnodeControlError, match="positive integer"):
        build_controller_action_script(
            pid=value,
            confirm_pid=value,
            expected_analysis_root="/fsx/analysis_results/ubuntu/analysis-1",
            action="stop",
        )


def test_controller_action_requires_matching_confirmation() -> None:
    with pytest.raises(HeadnodeControlError, match="exactly match"):
        build_controller_action_script(
            pid=42,
            confirm_pid=43,
            expected_analysis_root="/fsx/analysis_results/ubuntu/analysis-1",
            action="kill",
        )


@pytest.mark.parametrize(
    "root",
    [
        "/fsx/analysis_results/ubuntu",
        "/fsx/analysis_results/ubuntu/analysis-1/child",
        "/fsx/analysis_results/../analysis-1",
        "/tmp/analysis_results/ubuntu/analysis-1",
        "/fsx/analysis_results/ubuntu/analysis 1",
        "/fsx/analysis_results/ubuntu/analysis-1/",
    ],
)
def test_controller_action_requires_exact_safe_analysis_root(root: str) -> None:
    with pytest.raises(HeadnodeControlError, match="expected_analysis_root"):
        build_controller_action_script(
            pid=42,
            confirm_pid=42,
            expected_analysis_root=root,
            action="stop",
        )


def test_controller_action_rejects_arbitrary_action() -> None:
    with pytest.raises(HeadnodeControlError, match="stop"):
        build_controller_action_script(
            pid=42,
            confirm_pid=42,
            expected_analysis_root="/fsx/analysis_results/ubuntu/analysis-1",
            action="TERM; rm -rf /",
        )


def test_parse_controller_action_requires_boolean_signal_sent() -> None:
    payload = {
        "schema_version": CONTROLLER_ACTION_SCHEMA,
        "ok": True,
        "pid": 42,
        "signal_sent": True,
    }
    assert (
        parse_controller_action_output(marker_output(CONTROLLER_ACTION_MARKER, payload)) == payload
    )
    payload["signal_sent"] = "yes"
    with pytest.raises(HeadnodeControlError, match="boolean"):
        parse_controller_action_output(marker_output(CONTROLLER_ACTION_MARKER, payload))


@pytest.mark.parametrize(
    ("action", "command"),
    [
        ("suspend", "['scontrol', 'suspend', '101', '202_3']"),
        ("resume", "['scontrol', 'resume', '101', '202_3']"),
        ("cancel", "['scancel', '101', '202_3']"),
    ],
)
def test_slurm_job_action_uses_exact_argv(action: str, command: str) -> None:
    script = build_slurm_job_action_script(action=action, job_ids=["101", "202_3"])

    assert f"COMMAND = {command}" in script
    assert "subprocess.run(\n        COMMAND" in script
    assert "shell=True" not in script
    assert "squeue" not in script
    assert SLURM_JOB_ACTION_MARKER in script


@pytest.mark.parametrize(
    "job_id",
    ["", "0", "-1", "123.batch", "123+1", "123 456", "123;id", "all", "*"],
)
def test_slurm_job_action_rejects_noncanonical_job_ids(job_id: str) -> None:
    with pytest.raises(HeadnodeControlError, match="Slurm job ID"):
        build_slurm_job_action_script(action="cancel", job_ids=[job_id])


def test_slurm_job_action_rejects_empty_duplicates_and_over_limit() -> None:
    with pytest.raises(HeadnodeControlError, match="must not be empty"):
        build_slurm_job_action_script(action="cancel", job_ids=[])
    with pytest.raises(HeadnodeControlError, match="duplicate"):
        build_slurm_job_action_script(action="cancel", job_ids=["1", "1"])
    with pytest.raises(HeadnodeControlError, match="exceeds"):
        build_slurm_job_action_script(
            action="cancel",
            job_ids=["1", "2", "3"],
            max_job_count=2,
        )
    with pytest.raises(HeadnodeControlError, match="sequence"):
        build_slurm_job_action_script(action="cancel", job_ids="123")


def test_parse_slurm_job_action_validates_shape() -> None:
    payload = {
        "schema_version": SLURM_JOB_ACTION_SCHEMA,
        "ok": True,
        "job_ids": ["101"],
        "return_code": 0,
    }
    assert parse_slurm_job_action_output(marker_output(SLURM_JOB_ACTION_MARKER, payload)) == payload
    payload["job_ids"] = "101"
    with pytest.raises(HeadnodeControlError, match="job_ids"):
        parse_slurm_job_action_output(marker_output(SLURM_JOB_ACTION_MARKER, payload))


def test_slurm_drain_is_all_nodes_confirmed_and_never_cancels_jobs() -> None:
    script = build_slurm_all_node_state_script(
        action="drain",
        cluster="cluster-a",
        confirm_cluster="cluster-a",
        reason="planned controller maintenance",
        operation_id="op-20260722-01",
    )

    assert "['scontrol', 'update', 'NodeName=ALL', 'State=DRAIN'" in script
    assert "Reason=planned controller maintenance [operation_id=op-20260722-01]" in script
    assert '"node_selector": "ALL"' in script
    assert '"jobs_cancelled": False' in script
    assert "scancel" not in script
    assert "NodeName=" + "ALL" in script


def test_slurm_undrain_is_not_exposed_or_retained() -> None:
    with pytest.raises(HeadnodeControlError, match="drain"):
        build_slurm_all_node_state_script(
            action="undrain",
            cluster="cluster-a",
            confirm_cluster="cluster-a",
            reason="maintenance complete",
            operation_id="op-20260722-02",
        )

    source = inspect.getsource(headnode_control)
    assert "UNDRAIN" not in source
    assert "State=RESUME" not in source


def test_slurm_all_node_action_requires_exact_cluster_confirmation() -> None:
    with pytest.raises(HeadnodeControlError, match="exactly match"):
        build_slurm_all_node_state_script(
            action="drain",
            cluster="cluster-a",
            confirm_cluster="cluster-b",
            reason="maintenance",
            operation_id="op-1",
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("cluster", "cluster-a;id"),
        ("reason", "contains\nnewline"),
        ("reason", "x" * 129),
        ("operation_id", "op 1"),
        ("operation_id", "x" * 65),
    ],
)
def test_slurm_all_node_action_rejects_unbounded_or_unsafe_text(
    field: str,
    value: str,
) -> None:
    kwargs = {
        "action": "drain",
        "cluster": "cluster-a",
        "confirm_cluster": "cluster-a",
        "reason": "maintenance",
        "operation_id": "op-1",
    }
    kwargs[field] = value
    if field == "cluster":
        kwargs["confirm_cluster"] = value
    with pytest.raises(HeadnodeControlError):
        build_slurm_all_node_state_script(**kwargs)


def test_parse_slurm_all_node_state_rejects_job_cancellation_claim() -> None:
    payload = {
        "schema_version": SLURM_NODE_STATE_SCHEMA,
        "ok": True,
        "jobs_cancelled": False,
    }
    assert (
        parse_slurm_all_node_state_output(marker_output(SLURM_NODE_STATE_MARKER, payload))
        == payload
    )
    payload["jobs_cancelled"] = True
    with pytest.raises(HeadnodeControlError, match="never cancel"):
        parse_slurm_all_node_state_output(marker_output(SLURM_NODE_STATE_MARKER, payload))


def test_all_builders_accept_no_shell_text_selector_or_regex_parameters() -> None:
    for builder in (
        build_controller_inventory_script,
        build_controller_action_script,
        build_slurm_job_action_script,
        build_slurm_all_node_state_script,
    ):
        names = set(inspect.signature(builder).parameters)
        assert not names.intersection({"shell", "script", "command", "node_selector", "regex"})


def test_all_generated_scripts_have_valid_shell_and_embedded_python_syntax() -> None:
    scripts = [
        build_controller_inventory_script(),
        build_controller_action_script(
            pid=42,
            confirm_pid=42,
            expected_analysis_root="/fsx/analysis_results/ubuntu/analysis-1",
            action="stop",
        ),
        build_slurm_job_action_script(action="suspend", job_ids=["101"]),
        build_slurm_all_node_state_script(
            action="drain",
            cluster="cluster-a",
            confirm_cluster="cluster-a",
            reason="maintenance",
            operation_id="op-1",
        ),
    ]
    for script in scripts:
        shell_check = subprocess.run(
            ["bash", "-n"],
            input=script,
            text=True,
            capture_output=True,
            check=False,
        )
        assert shell_check.returncode == 0, shell_check.stderr
        python_source = script.split("python3 - <<'PY'\n", 1)[1].rsplit("\nPY\n", 1)[0]
        compile(python_source, "<generated-headnode-control>", "exec")


def test_parsers_enforce_output_byte_limit_and_object_payload() -> None:
    oversized = CONTROLLER_ACTION_MARKER + json.dumps(
        {
            "schema_version": CONTROLLER_ACTION_SCHEMA,
            "ok": True,
            "signal_sent": True,
            "padding": "x" * 2000,
        }
    )
    with pytest.raises(HeadnodeControlError, match="exceeds"):
        parse_controller_action_output(oversized, max_output_bytes=1024)
    with pytest.raises(HeadnodeControlError, match="JSON object"):
        parse_controller_action_output(CONTROLLER_ACTION_MARKER + "[]")
