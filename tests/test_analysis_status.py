from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

from daylily_ec.analysis_status import (
    AnalysisStatusError,
    collect_analysis_status,
    render_analysis_status,
)
from daylily_ec.cli import app

runner = CliRunner()


def _root(
    tmp_path: Path,
    *,
    complete: bool = False,
    terminal_success_without_progress: bool = False,
) -> Path:
    root = tmp_path / "fsx" / "analysis_results" / "cluster" / "analysis-1"
    dayoa = root / "daylily-omics-analysis"
    log_dir = dayoa / ".snakemake" / "log"
    log_dir.mkdir(parents=True)
    if terminal_success_without_progress:
        log_text = "rule final_report:\nWORKFLOW SUCCESS\nRETURN CODE: 0\n"
    else:
        progress = "10 of 20 steps (50%) done"
        if complete:
            progress = "20 of 20 steps (100%) done"
        log_text = "rule align:\n" + progress + "\n"
    (log_dir / "20260716.snakemake.log").write_text(log_text, encoding="utf-8")
    if complete or terminal_success_without_progress:
        report = dayoa / "results" / "day" / "hg38" / "reports"
        (report / "DAY_final_multiqc_data").mkdir(parents=True)
        (report / "DAY_final_multiqc.html").write_text("html", encoding="utf-8")
        (report / "DAY_final_multiqc_data" / "multiqc_data.json").write_text("{}", encoding="utf-8")
        (report / "dayoa_evidence_manifest.json").write_text("{}", encoding="utf-8")
    return root


def _fake_runner(argv, **_kwargs):
    if argv[:3] == ["ps", "-eo", "pid=,ppid=,etimes=,args="]:
        return subprocess.CompletedProcess(argv, 0, "", "")
    if argv[:2] == ["df", "-Pk"]:
        return subprocess.CompletedProcess(
            argv,
            0,
            "Filesystem 1024-blocks Used Available Capacity Mounted on\n"
            "/dev/fsx 1000000 250000 750000 25% /fsx\n",
            "",
        )
    raise AssertionError(argv)


def _activate(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CONDA_DEFAULT_ENV", "DAY-EC")
    monkeypatch.setenv("CONDA_PREFIX", "/tmp/dayec")
    monkeypatch.setenv("DAYOA_AGENT_ID", "analysis-status-test")


def test_slim_status_records_visit_and_does_not_claim_empty_queue_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _root(tmp_path)
    _activate(monkeypatch)
    monkeypatch.setattr("daylily_ec.analysis_status.shutil.which", lambda _name: None)

    payload = collect_analysis_status(root, mode="slim", runner=_fake_runner)

    assert payload["state"] == "INCOMPLETE_OR_UNKNOWN"
    assert payload["workflow"]["progress"] == {
        "completed": 10,
        "total": 20,
        "percent": 50,
    }
    assert payload["filesystem"]["use_percent"] == 25
    assert payload["slurm"]["available"] is False
    assert payload["visit"]["mode"] == "monitor"
    assert payload["manifests"]["available"] is False
    assert (root / ".dayoa_agent" / "visits").is_dir()
    assert "Progress: 10/20 (50%)" in render_analysis_status(payload)


def test_status_reads_and_validates_exact_dayoa13_six_manifest_set(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _root(tmp_path)
    config = root / "daylily-omics-analysis" / "config"
    config.mkdir(parents=True)
    (config / "specimens.tsv").write_text(
        "SPECIMEN_ID\tSPECIMEN_EUID\nspecimen-1\t\n",
        encoding="utf-8",
    )
    (config / "samples.tsv").write_text(
        "SAMPLEID\tSAMPLE_EUID\tSPECIMEN_ID\nsample-1\tfixture-sample-owned-1\tspecimen-1\n",
        encoding="utf-8",
    )
    (config / "libraries.tsv").write_text(
        "LIBRARY_ID\tLIBRARY_EUID\tSAMPLEID\nlibrary-1\t\tsample-1\n",
        encoding="utf-8",
    )
    (config / "sequencing_inputs.tsv").write_text(
        "SEQUENCING_INPUT_UID\tLIBRARY_ID\tMODALITY\tLAYOUT\tILMN_R1_PATH\tILMN_R2_PATH\n"
        "input-1\tlibrary-1\tsr\tpaired_fastq\t/data/r1.fastq.gz\t/data/r2.fastq.gz\n",
        encoding="utf-8",
    )
    (config / "analysis_units.tsv").write_text(
        "ANALYSIS_UNIT_UID\tSAMPLEID\nanalysis-unit-1\tsample-1\n",
        encoding="utf-8",
    )
    (config / "analysis_unit_inputs.tsv").write_text(
        "ANALYSIS_UNIT_UID\tSEQUENCING_INPUT_UID\tROLE\tINPUT_ORDINAL\n"
        "analysis-unit-1\tinput-1\tsr\t1\n",
        encoding="utf-8",
    )
    _activate(monkeypatch)
    monkeypatch.setattr("daylily_ec.analysis_status.shutil.which", lambda _name: None)

    payload = collect_analysis_status(root, mode="slim", runner=_fake_runner)

    assert payload["manifests"] == {
        "available": True,
        "input_contract": "six_manifest",
        "files": [
            "specimens.tsv",
            "samples.tsv",
            "libraries.tsv",
            "sequencing_inputs.tsv",
            "analysis_units.tsv",
            "analysis_unit_inputs.tsv",
        ],
        "hashes": payload["manifests"]["hashes"],
        "row_counts": {
            "specimens": 1,
            "samples": 1,
            "libraries": 1,
            "sequencing_inputs": 1,
            "analysis_units": 1,
            "analysis_unit_inputs": 1,
        },
        "analysis_units": [
            {
                "analysis_unit_uid": "analysis-unit-1",
                "library_ids": ["library-1"],
                "library_euids": [],
                "sequencing_inputs": [
                    {
                        "sequencing_input_uid": "input-1",
                        "role": "sr",
                        "input_ordinal": 1,
                        "library_id": "library-1",
                        "library_euid": None,
                    }
                ],
            }
        ],
        "lineage_validated": True,
    }

    (config / "units.tsv").write_text(
        "ANALYSIS_UNIT_UID\tSAMPLEID\nanalysis-unit-1\tsample-1\n",
        encoding="utf-8",
    )
    with pytest.raises(AnalysisStatusError, match="legacy manifest files are prohibited"):
        collect_analysis_status(root, mode="slim", runner=_fake_runner)


def test_success_requires_complete_progress_and_all_canonical_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _root(tmp_path, complete=True)
    _activate(monkeypatch)
    monkeypatch.setattr("daylily_ec.analysis_status.shutil.which", lambda _name: None)

    payload = collect_analysis_status(root, mode="slim", runner=_fake_runner)

    assert payload["state"] == "COMPLETE_ARTIFACTS_RC_UNKNOWN"
    assert payload["canonical_artifacts"]["all_present"] is True
    assert "success is unverified" in payload["warnings"][-1]


def test_success_is_verified_only_with_controller_rc_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _root(tmp_path, complete=True)
    _activate(monkeypatch)
    monkeypatch.setattr(
        "daylily_ec.analysis_status.shutil.which",
        lambda name: "/bin/tool" if name in {"tmux", "squeue", "scontrol"} else None,
    )

    def fake(argv, **_kwargs):
        if argv[0] == "ps":
            return subprocess.CompletedProcess(argv, 0, "", "")
        if argv[0] == "df":
            return _fake_runner(argv)
        if argv[0] == "squeue":
            return subprocess.CompletedProcess(argv, 0, "", "")
        if argv[:2] == ["tmux", "list-panes"]:
            return subprocess.CompletedProcess(
                argv,
                0,
                f"controller|0|0|999|{root.resolve()}|0|0\n",
                "",
            )
        if argv[:2] == ["tmux", "capture-pane"]:
            return subprocess.CompletedProcess(
                argv,
                0,
                f"run complete in {root.resolve()}\nDAYOA_CONTROLLER_RC=0\n",
                "",
            )
        raise AssertionError(argv)

    payload = collect_analysis_status(root, mode="slim", runner=fake)

    assert payload["state"] == "SUCCESS"
    assert payload["controller"]["return_code"] == 0
    assert payload["terminal_evidence"]["success_verified"] is True


def test_success_can_use_master_log_terminal_rc_when_progress_line_is_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _root(tmp_path, terminal_success_without_progress=True)
    _activate(monkeypatch)
    monkeypatch.setattr(
        "daylily_ec.analysis_status.shutil.which",
        lambda name: "/bin/tool" if name in {"squeue", "scontrol"} else None,
    )

    def fake(argv, **_kwargs):
        if argv[0] == "ps":
            return subprocess.CompletedProcess(argv, 0, "", "")
        if argv[0] == "df":
            return _fake_runner(argv)
        if argv[0] == "squeue":
            return subprocess.CompletedProcess(argv, 0, "", "")
        raise AssertionError(argv)

    payload = collect_analysis_status(root, mode="slim", runner=fake)

    assert payload["state"] == "SUCCESS"
    assert payload["terminal_evidence"]["return_code"] == 0
    assert payload["terminal_evidence"]["return_code_source"].endswith("20260716.snakemake.log")
    assert payload["terminal_evidence"]["requirements"]["workflow_progress_complete"] is False
    assert payload["terminal_evidence"]["requirements"]["workflow_terminal_success"] is True
    assert payload["terminal_evidence"]["success_verified"] is True
    assert "INCOMPLETE_OR_UNKNOWN" not in render_analysis_status(payload)


def test_controller_rc_zero_does_not_claim_success_without_scheduler_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _root(tmp_path, complete=True)
    _activate(monkeypatch)
    monkeypatch.setattr(
        "daylily_ec.analysis_status.shutil.which",
        lambda name: "/bin/tmux" if name == "tmux" else None,
    )

    def fake(argv, **_kwargs):
        if argv[0] == "ps":
            return subprocess.CompletedProcess(argv, 0, "", "")
        if argv[0] == "df":
            return _fake_runner(argv)
        if argv[:2] == ["tmux", "list-panes"]:
            return subprocess.CompletedProcess(
                argv,
                0,
                f"controller|0|0|999|{root.resolve()}|0|0\n",
                "",
            )
        if argv[:2] == ["tmux", "capture-pane"]:
            return subprocess.CompletedProcess(argv, 0, "DAYOA_CONTROLLER_RC=0\n", "")
        raise AssertionError(argv)

    payload = collect_analysis_status(root, mode="slim", runner=fake)

    assert payload["state"] == "COMPLETE_ARTIFACTS_RC_ZERO_SCHEDULER_UNKNOWN"
    assert payload["terminal_evidence"]["success_verified"] is False
    assert payload["terminal_evidence"]["requirements"]["scheduler_idle"] is False


def test_job_counts_are_source_backed_and_dependency_blocked_is_explicit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _root(tmp_path)
    dayoa = root / "daylily-omics-analysis"
    master = next((dayoa / ".snakemake" / "log").glob("*.snakemake.log"))
    master.write_text(
        master.read_text(encoding="utf-8")
        + "Submitted job 88 with external jobid '123'.\nFinished job 88.\n",
        encoding="utf-8",
    )
    _activate(monkeypatch)
    monkeypatch.setattr(
        "daylily_ec.analysis_status.shutil.which",
        lambda name: "/bin/tool" if name in {"squeue", "scontrol", "sacct"} else None,
    )

    def fake(argv, **_kwargs):
        if argv[0] == "squeue":
            return subprocess.CompletedProcess(
                argv,
                0,
                "123|i128|1|PD|(null)|1|PENDING|1G|00:00|1|align.HG003_unit\n",
                "",
            )
        if argv[0] == "scontrol":
            return subprocess.CompletedProcess(
                argv,
                0,
                f"JobId=123 WorkDir={dayoa} Reason=Dependency StdOut=/tmp/o StdErr=/tmp/e",
                "",
            )
        if argv[0] == "sacct":
            rows = [
                [
                    "122",
                    "align.HG003_unit",
                    "COMPLETED",
                    "00:01:00",
                    "1",
                    "node-1",
                    "i128",
                    str(dayoa),
                    "0:0",
                    "project-a",
                    "2026-07-16T00:00:00",
                    "2026-07-16T00:01:00",
                    "2026-07-16T00:02:00",
                    "None",
                ],
                [
                    "121",
                    "old.HG003_unit",
                    "CANCELLED by 1000",
                    "00:00:10",
                    "1",
                    "node-1",
                    "i128",
                    str(dayoa),
                    "0:15",
                    "project-a",
                    "2026-07-16T00:00:00",
                    "2026-07-16T00:00:01",
                    "2026-07-16T00:00:11",
                    "None",
                ],
            ]
            return subprocess.CompletedProcess(
                argv,
                0,
                "".join("|".join(row) + "|\n" for row in rows),
                "",
            )
        if argv[0] == "ps":
            return subprocess.CompletedProcess(argv, 0, "", "")
        if argv[0] == "df":
            return _fake_runner(argv)
        raise AssertionError(argv)

    payload = collect_analysis_status(root, mode="slim", runner=fake)

    assert payload["job_counts"]["pending"]["value"] == 1
    assert payload["job_counts"]["dependency_blocked"]["value"] == 1
    assert payload["job_counts"]["submitted"]["value"] == 1
    assert payload["job_counts"]["completed"]["value"] == 10
    assert payload["job_counts"]["failed"]["value"] == 1
    assert payload["accounting"]["unique_job_count"] == 2
    assert payload["slurm"]["jobs"][0]["reason"] == "Dependency"


def test_full_status_scopes_slurm_by_exact_workdir_and_tails_streams(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _root(tmp_path)
    dayoa = root / "daylily-omics-analysis"
    stdout = dayoa / "slurm-123.out"
    stderr = dayoa / "slurm-123.err"
    stdout.write_text("stage 1\n50% complete\n", encoding="utf-8")
    stderr.write_text("warning only\n", encoding="utf-8")
    _activate(monkeypatch)
    monkeypatch.setattr(
        "daylily_ec.analysis_status.shutil.which",
        lambda name: "/bin/tool" if name in {"squeue", "scontrol"} else None,
    )

    def fake(argv, **_kwargs):
        if argv[0] == "squeue":
            return subprocess.CompletedProcess(
                argv,
                0,
                "123|i128nvme|128|R|node-1|128|RUNNING|N/A|01:00|1|group_core\n"
                "999|i128nvme|128|R|node-2|128|RUNNING|N/A|01:00|1|other\n",
                "",
            )
        if argv[:4] == ["scontrol", "show", "job", "-o"]:
            workdir = dayoa if argv[4] == "123" else tmp_path / "other"
            return subprocess.CompletedProcess(
                argv,
                0,
                f"JobId={argv[4]} WorkDir={workdir} StdOut={stdout} StdErr={stderr}",
                "",
            )
        if argv[0] == "ps":
            return subprocess.CompletedProcess(
                argv,
                0,
                f"1234 1000 90 snakemake --directory {dayoa}\n",
                "",
            )
        if argv[0] == "df":
            return _fake_runner(argv)
        if argv[0] == "ssh":
            return subprocess.CompletedProcess(argv, 0, "cpu.user: 80\nmem.percent: 40", "")
        raise AssertionError(argv)

    payload = collect_analysis_status(root, mode="full", tail_lines=1000, runner=fake)

    assert payload["state"] == "RUNNING"
    assert [job["job_id"] for job in payload["slurm"]["jobs"]] == ["123"]
    assert payload["slurm"]["jobs"][0]["stdout_tail"]["excerpt"][-1] == "50% complete"
    assert payload["slurm"]["jobs"][0]["stdout_tail"]["progress_markers"][-1] == ("50% complete")
    assert payload["node_telemetry"][0]["node"] == "node-1"
    assert payload["node_telemetry"][0]["point_sample_only"] is True


def test_invalid_mode_fails_clearly(tmp_path: Path) -> None:
    root = _root(tmp_path)
    with pytest.raises(AnalysisStatusError, match="slim.*full"):
        collect_analysis_status(root, mode="wide", runner=_fake_runner)


def test_cli_json_slim_local(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _root(tmp_path)
    _activate(monkeypatch)
    monkeypatch.setattr("daylily_ec.analysis_status.shutil.which", lambda _name: None)
    monkeypatch.setattr("daylily_ec.analysis_status.subprocess.run", _fake_runner)

    result = runner.invoke(
        app,
        ["--json", "analysis", "status", "slim", "--analysis-root", str(root)],
    )

    assert result.exit_code == 0, result.stdout + result.stderr
    assert json.loads(result.stdout)["workflow"]["progress"]["percent"] == 50


def test_cli_remote_status_uses_supported_ssm_headnode_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import daylily_ec.cli as cli_module

    root = _root(tmp_path)
    _activate(monkeypatch)
    monkeypatch.setattr("daylily_ec.analysis_status.shutil.which", lambda _name: None)
    payload = collect_analysis_status(root, mode="slim", runner=_fake_runner)
    captured: dict[str, object] = {}
    scripts: list[str] = []
    monkeypatch.setattr(
        cli_module,
        "_resolve_headnode_cli_target",
        lambda **_kwargs: (
            "lsmc",
            "us-west-2",
            "cluster-a",
            SimpleNamespace(instance_id="i-123"),
        ),
    )
    monkeypatch.setattr("daylily_ec.aws.ssm.wait_for_ssm_online", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("daylily_ec.aws.ssm.resolve_remote_user", lambda *_args, **_kwargs: "ubuntu")

    manifest = {
        "path": "/tmp/dyec-slim-analysis-status-test.json",
        "size": 123,
        "sha256": "b" * 64,
    }

    def fake_run_shell(instance_id, region, script, **kwargs):
        scripts.append(script)
        captured.update(
            {
                "instance_id": instance_id,
                "region": region,
                "script": script,
                "kwargs": kwargs,
            }
        )
        return SimpleNamespace(
            stdout="DAY-EC activated.\n"
            "__DYEC_REMOTE_JSON_MANIFEST__="
            + json.dumps(manifest, sort_keys=True)
            + "\n",
            stderr="",
        )

    monkeypatch.setattr("daylily_ec.aws.ssm.run_shell", fake_run_shell)
    monkeypatch.setattr(cli_module, "_download_remote_json_payload", lambda **_kwargs: payload)

    result = runner.invoke(
        app,
        [
            "--json",
            "analysis",
            "status",
            "slim",
            "--profile",
            "lsmc",
            "--region",
            "us-west-2",
            "--cluster",
            "cluster-a",
            "--analysis-root",
            "/fsx/analysis_results/cluster-a/analysis-1",
        ],
    )

    assert result.exit_code == 0, result.stdout + result.stderr
    remote = json.loads(result.stdout)
    assert remote["cluster"]["headnode_instance_id"] == "i-123"
    assert captured["instance_id"] == "i-123"
    assert "dyec --json analysis status slim" in scripts[0]
    assert captured["kwargs"]["as_user"] == "ubuntu"
