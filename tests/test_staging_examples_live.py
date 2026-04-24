from __future__ import annotations

import csv
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional, Sequence

import pytest

from tests.test_staging_examples import EXAMPLES, EXAMPLE_ROOT


ROOT = Path(__file__).resolve().parents[1]
LIVE_OUTPUT_ROOT = ROOT / "tmp-stage-config" / "live-staging-examples"


@dataclass(frozen=True)
class LiveStagingOptions:
    profile: str
    region: str
    cluster: str
    reference_bucket: str
    non_dryrun: bool
    workflow_timeout_minutes: int


@dataclass(frozen=True)
class WorkflowCommandSpec:
    dy_command: str
    dryrun_dy_command: str


WORKFLOW_COMMANDS = {
    "ilmn_solo": WorkflowCommandSpec(
        dy_command=(
            "bin/day_run produce_snv_concordances produce_alignstats "
            "--config aligners=['sent'] dedupers=['dppl'] snv_callers=['sentd'] "
            "-p -k -j 2"
        ),
        dryrun_dy_command=(
            "bin/day_run produce_snv_concordances produce_alignstats "
            "--config aligners=['sent'] dedupers=['dppl'] snv_callers=['sentd'] "
            "-p -k -j 2 -n"
        ),
    ),
    "ultima_solo": WorkflowCommandSpec(
        dy_command=(
            "bin/day_run produce_alignstats produce_sentdug_vcf --config dppl=['na'] -p -j 20 -k"
        ),
        dryrun_dy_command=(
            "bin/day_run produce_alignstats produce_sentdug_vcf --config dppl=['na'] -p -j 20 -k -n"
        ),
    ),
    "ont_solo": WorkflowCommandSpec(
        dy_command=(
            "bin/day_run produce_alignstats produce_sentmm2ont_align_sort "
            "produce_sentdont_vcf --config dedupers=['na'] -p -j 5 -k"
        ),
        dryrun_dy_command=(
            "bin/day_run produce_alignstats produce_sentmm2ont_align_sort "
            "produce_sentdont_vcf --config dedupers=['na'] -p -j 5 -k -n"
        ),
    ),
    "hybrid_ilmn_ont": WorkflowCommandSpec(
        dy_command=(
            "bin/day_run produce_snv_concordances produce_sentdhiom_sv "
            "produce_sentdhiom_vcf -p -j 100 -k"
        ),
        dryrun_dy_command=(
            "bin/day_run produce_snv_concordances produce_sentdhiom_sv "
            "produce_sentdhiom_vcf -p -j 100 -k -n"
        ),
    ),
    "pacbio_solo": WorkflowCommandSpec(
        dy_command=(
            "bin/day_run produce_sentdpb_vcf produce_alignstats produce_snv_concordances "
            "-p -j 2 -k -T 1"
        ),
        dryrun_dy_command=(
            "bin/day_run produce_sentdpb_vcf produce_alignstats produce_snv_concordances "
            "-p -j 2 -k -T 1 -n"
        ),
    ),
    "roche_solo": WorkflowCommandSpec(
        dy_command=(
            "bin/day_run produce_alignstats produce_rochehc_vcf --config dedupers=['na'] -p -j 5 -k"
        ),
        # Roche HC dry-run asks Snakemake to resolve a private Roche container
        # even in -n mode. The full non-dry-run command stays covered above.
        dryrun_dy_command="bin/day_run produce_alignstats --config dedupers=['na'] -p -j 5 -k -n",
    ),
}


@pytest.fixture(scope="session")
def live_staging_options(pytestconfig: pytest.Config) -> LiveStagingOptions:
    if not pytestconfig.getoption("--run-live-staging-examples"):
        pytest.skip("live staging examples require --run-live-staging-examples")
    return LiveStagingOptions(
        profile=pytestconfig.getoption("--live-staging-profile"),
        region=pytestconfig.getoption("--live-staging-region"),
        cluster=pytestconfig.getoption("--live-staging-cluster"),
        reference_bucket=pytestconfig.getoption("--live-staging-reference-bucket"),
        non_dryrun=pytestconfig.getoption("--live-staging-non-dryrun"),
        workflow_timeout_minutes=pytestconfig.getoption("--live-staging-workflow-timeout-minutes"),
    )


def _live_env(options: LiveStagingOptions) -> dict[str, str]:
    env = dict(os.environ)
    env["AWS_PROFILE"] = options.profile
    env["AWS_REGION"] = options.region
    env["AWS_DEFAULT_REGION"] = options.region
    return env


def _write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def _run_cli(
    args: Sequence[str],
    *,
    evidence_dir: Path,
    name: str,
    env: dict[str, str],
    timeout_seconds: int,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    command = [sys.executable, "-m", "daylily_ec.cli", *args]
    _write_text(
        evidence_dir / f"{name}.command.json",
        json.dumps({"command": command, "cwd": str(ROOT)}, indent=2) + "\n",
    )
    result = subprocess.run(
        command,
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        timeout=timeout_seconds,
        check=False,
    )
    _write_text(evidence_dir / f"{name}.stdout", result.stdout)
    _write_text(evidence_dir / f"{name}.stderr", result.stderr)
    if check and result.returncode != 0:
        raise AssertionError(
            f"{name} failed with exit code {result.returncode}.\n"
            f"Command: {' '.join(command)}\n"
            f"STDOUT:\n{result.stdout}\n"
            f"STDERR:\n{result.stderr}"
        )
    return result


def _parse_remote_stage_dir(stdout: str) -> str:
    match = re.search(r"^Remote FSx stage directory:\s*(?P<path>\S+)\s*$", stdout, re.M)
    assert match, f"staging output did not include Remote FSx stage directory:\n{stdout}"
    return match.group("path")


def _parse_launch(stdout: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for line in stdout.splitlines():
        if line.startswith("__DAYLILY_SESSION__="):
            parsed["session_name"] = line.split("=", 1)[1].strip()
        elif line.startswith("__DAYLILY_RUN_DIR__="):
            parsed["run_dir"] = line.split("=", 1)[1].strip()
        elif line.startswith("__DAYLILY_REPO_PATH__="):
            parsed["repo_path"] = line.split("=", 1)[1].strip()
    missing = {"session_name", "run_dir", "repo_path"} - parsed.keys()
    assert not missing, f"workflow launch output missing {sorted(missing)}:\n{stdout}"
    return parsed


def _parse_json_stdout(stdout: str, *, allow_missing: bool = False) -> Optional[dict[str, object]]:
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        start = stdout.find("{")
        end = stdout.rfind("}")
        if allow_missing and (start < 0 or end <= start):
            return None
        assert start >= 0 and end > start, f"stdout did not contain JSON:\n{stdout}"
        payload = json.loads(stdout[start : end + 1])
    assert isinstance(payload, dict), f"workflow status JSON was not an object: {payload!r}"
    return payload


def test_parse_json_stdout_allows_transient_missing_status_response() -> None:
    assert _parse_json_stdout("", allow_missing=True) is None
    assert _parse_json_stdout("no json here", allow_missing=True) is None


def test_parse_json_stdout_extracts_status_json_from_noisy_output() -> None:
    assert _parse_json_stdout('noise\n{"exit_code": 0}\n') == {"exit_code": 0}


def _count_tsv_rows(path: Path) -> int:
    with path.open(newline="") as handle:
        return sum(1 for row in csv.DictReader(handle, delimiter="\t") if any(row.values()))


def _assert_generated_config(config_dir: Path, *, expected_units_rows: int) -> None:
    samples_paths = sorted(config_dir.glob("*_samples.tsv"))
    units_paths = sorted(config_dir.glob("*_units.tsv"))
    assert len(samples_paths) == 1, f"expected one generated samples TSV in {config_dir}"
    assert len(units_paths) == 1, f"expected one generated units TSV in {config_dir}"
    assert _count_tsv_rows(samples_paths[0]) == 1
    assert _count_tsv_rows(units_paths[0]) == expected_units_rows


def _wait_for_workflow_exit_zero(
    *,
    options: LiveStagingOptions,
    session_name: str,
    evidence_dir: Path,
    env: dict[str, str],
) -> dict[str, object]:
    deadline = time.time() + options.workflow_timeout_minutes * 60
    last_result: subprocess.CompletedProcess[str] | None = None
    poll_interval_seconds = 10

    while time.time() < deadline:
        result = _run_cli(
            [
                "workflow",
                "status",
                "--profile",
                options.profile,
                "--region",
                options.region,
                "--cluster",
                options.cluster,
                "--session",
                session_name,
            ],
            evidence_dir=evidence_dir,
            name="workflow-status-last",
            env=env,
            timeout_seconds=180,
            check=False,
        )
        last_result = result
        if result.returncode == 0:
            payload = _parse_json_stdout(result.stdout, allow_missing=True)
            if payload is None:
                _write_text(
                    evidence_dir / "workflow-status-last-transient.json",
                    json.dumps(
                        {
                            "returncode": result.returncode,
                            "stdout": result.stdout,
                            "stderr": result.stderr,
                        },
                        indent=2,
                        sort_keys=True,
                    )
                    + "\n",
                )
                time.sleep(poll_interval_seconds)
                continue
            _write_text(
                evidence_dir / "workflow-status-last.json",
                json.dumps(payload, indent=2, sort_keys=True) + "\n",
            )
            if payload.get("exit_code") is not None:
                assert payload["exit_code"] == 0, (
                    f"workflow exited non-zero for {session_name}: {payload}"
                )
                return payload
        time.sleep(poll_interval_seconds)

    detail = ""
    if last_result is not None:
        detail = f"\nLast stdout:\n{last_result.stdout}\nLast stderr:\n{last_result.stderr}"
    raise AssertionError(
        f"workflow session {session_name} did not report exit_code=0 within "
        f"{options.workflow_timeout_minutes} minutes.{detail}"
    )


@pytest.mark.live_aws
@pytest.mark.parametrize("example_name,expected", EXAMPLES.items())
def test_live_staging_example_dryrun_or_workflow(
    live_staging_options: LiveStagingOptions,
    live_staging_run_id: str,
    example_name: str,
    expected: dict[str, object],
) -> None:
    options = live_staging_options
    env = _live_env(options)
    evidence_dir = LIVE_OUTPUT_ROOT / live_staging_run_id / example_name
    evidence_dir.mkdir(parents=True, exist_ok=True)
    _write_text(
        evidence_dir / "live-options.json",
        json.dumps(asdict(options), indent=2, sort_keys=True) + "\n",
    )

    manifest_path = EXAMPLE_ROOT / example_name / "analysis_samples_manifest.tsv"
    config_dir = evidence_dir / "generated-config"
    stage_timeout_seconds = max(options.workflow_timeout_minutes * 60, 1800)
    stage_result = _run_cli(
        [
            "samples",
            "stage",
            str(manifest_path),
            "--profile",
            options.profile,
            "--region",
            options.region,
            "--reference-bucket",
            options.reference_bucket,
            "--config-dir",
            str(config_dir),
        ],
        evidence_dir=evidence_dir,
        name="samples-stage",
        env=env,
        timeout_seconds=stage_timeout_seconds,
    )
    remote_stage_dir = _parse_remote_stage_dir(stage_result.stdout)
    _assert_generated_config(config_dir, expected_units_rows=int(expected["rows"]))

    session_name = f"stg-ex-{example_name.replace('_', '-')}-{live_staging_run_id}"
    workflow_spec = WORKFLOW_COMMANDS[example_name]
    dy_command = workflow_spec.dy_command if options.non_dryrun else workflow_spec.dryrun_dy_command
    launch_args = [
        "workflow",
        "launch",
        "--profile",
        options.profile,
        "--region",
        options.region,
        "--cluster",
        options.cluster,
        "--stage-dir",
        remote_stage_dir,
        "--session-name",
        session_name,
        "--dy-command",
        dy_command,
    ]
    if not options.non_dryrun:
        launch_args.append("--dry-run")

    launch_result = _run_cli(
        launch_args,
        evidence_dir=evidence_dir,
        name="workflow-launch",
        env=env,
        timeout_seconds=300,
    )
    launch_info = _parse_launch(launch_result.stdout)
    assert launch_info["session_name"] == session_name
    _write_text(
        evidence_dir / "live-metadata.json",
        json.dumps(
            {
                "example": example_name,
                "remote_stage_dir": remote_stage_dir,
                "session_name": session_name,
                "launch_info": launch_info,
                "dry_run": not options.non_dryrun,
                "dy_command": dy_command,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
    )

    status = _wait_for_workflow_exit_zero(
        options=options,
        session_name=session_name,
        evidence_dir=evidence_dir,
        env=env,
    )
    assert status["session_name"] == session_name
