from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace


REPO_ROOT = Path(__file__).resolve().parents[1]
DRIVER_PATH = (
    REPO_ROOT
    / "docs/plans/20260604T020327Z_forked_catalog_j100_jitter_validation/driver.py"
)


def _load_driver():
    spec = importlib.util.spec_from_file_location("forked_catalog_jitter_driver", DRIVER_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_driver_forces_j100_print_keep_jitter_and_isolated_conda() -> None:
    driver = _load_driver()
    command = SimpleNamespace(command_id="illumina_snv_alignstats", genome="hg38_broad")

    rendered = driver.dy_r_command(
        command,
        "bin/day_run produce_sent_align produce_alignstats -p -j 20 -k -T 1",
    )

    assert rendered == (
        "source dyoainit; dy-a slurm hg38_broad; dy-r "
        "produce_sent_align produce_alignstats -p -j 100 -k -T 1 "
        "--sentieon-start-jitter --rerun-triggers mtime --isolated-conda-prefix"
    )


def test_driver_preserves_dyr_contract_for_source_initialized_commands() -> None:
    driver = _load_driver()
    command = SimpleNamespace(command_id="simple-test", genome="hg38")

    rendered = driver.dy_r_command(
        command,
        "source dyoainit; dy-a local hg38; dy-r -p -k -j 1 help",
    )

    assert "bin/day_run" not in rendered
    assert "snakemake" not in rendered
    assert "dy-a slurm hg38" in rendered
    assert "dy-a local" not in rendered
    assert (
        "dy-r -p -k -j 100 help --sentieon-start-jitter "
        "--rerun-triggers mtime --isolated-conda-prefix"
    ) in rendered


def test_driver_refuses_catalog_conda_prefix_conflict() -> None:
    driver = _load_driver()
    command = SimpleNamespace(command_id="illumina_snv_alignstats", genome="hg38_broad")

    try:
        driver.dy_r_command(
            command,
            "bin/day_run produce_alignstats --conda-prefix /fsx/shared/conda -j 20",
        )
    except RuntimeError as exc:
        assert "already sets --conda-prefix" in str(exc)
    else:
        raise AssertionError("catalog command with --conda-prefix was accepted")


def test_driver_launch_uses_required_dayoa_git_ref(monkeypatch) -> None:
    driver = _load_driver()
    events: list[dict] = []
    captured: dict[str, str] = {}

    class FakeCommand:
        command_id = "simple-test"
        genome = "hg38"
        jobs = 1
        git_tag = "catalog-tag-must-not-be-used"

        def launch_argv(self, **kwargs):
            captured["git_tag"] = kwargs["git_tag"]
            return [
                "workflow",
                "launch",
                "--dy-command",
                "bin/day_run help -p -k -j 1",
            ]

    monkeypatch.setattr(driver, "DAYOA_GIT_REF", "abc123dayoasha")
    monkeypatch.setattr(driver, "dyec", lambda: "dyec")
    monkeypatch.setattr(driver, "last_event", lambda *args, **kwargs: None)
    monkeypatch.setattr(driver, "append_event", lambda event: events.append(event))
    monkeypatch.setattr(
        driver,
        "run_cmd",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, "", ""),
    )

    session = driver.launch_workflow(
        FakeCommand(),
        dry_run=True,
        samples_file=None,
        units_file=None,
        run_context_file=None,
    )

    assert session.startswith(f"{driver.ANALYSIS_ID_PREFIX}_")
    assert captured["git_tag"] == "abc123dayoasha"
    assert events[-1]["git_tag"] == "abc123dayoasha"
    assert events[-1]["jobs"] == 100
    assert "--sentieon-start-jitter" in events[-1]["dy_command"]
    assert "--rerun-triggers mtime" in events[-1]["dy_command"]
    assert "--isolated-conda-prefix" in events[-1]["dy_command"]


def test_driver_requires_dayoa_git_ref(monkeypatch) -> None:
    driver = _load_driver()

    monkeypatch.setattr(driver, "DAYOA_GIT_REF", "")

    try:
        driver.launch_workflow(
            SimpleNamespace(command_id="simple-test"),
            dry_run=True,
            samples_file=None,
            units_file=None,
            run_context_file=None,
        )
    except RuntimeError as exc:
        assert "--dayoa-git-ref is required" in str(exc)
    else:
        raise AssertionError("launch_workflow accepted an empty DAYOA_GIT_REF")


def test_driver_current_launch_events_ignore_prior_prefixes(monkeypatch, tmp_path: Path) -> None:
    driver = _load_driver()
    events_path = tmp_path / "events.jsonl"
    old_session = f"ccvforked_j100_jitter_r2_{driver.STAMP}_01_simple-test_dryrun"
    current_session = f"{driver.ANALYSIS_ID_PREFIX}_{driver.STAMP}_01_simple-test_dryrun"
    events_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "command_id": "simple-test",
                        "phase": "dryrun",
                        "status": "FAILED",
                        "session_name": old_session,
                    }
                ),
                json.dumps(
                    {
                        "command_id": "simple-test",
                        "phase": "dryrun",
                        "status": "DRYRUN_RUNNING",
                        "session_name": current_session,
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(driver, "EVENTS_PATH", events_path)

    assert driver.last_event("simple-test", "dryrun")["session_name"] == current_session
    assert (
        driver.last_event("simple-test", "dryrun", "FAILED", current_launch_only=True)
        is None
    )
    assert (
        driver.last_event("simple-test", "dryrun", "DRYRUN_RUNNING", current_launch_only=True)[
            "session_name"
        ]
        == current_session
    )


def test_driver_slim_config_validation_allows_mounted_slim_and_rejects_staging(tmp_path: Path) -> None:
    driver = _load_driver()
    samples = tmp_path / "samples.tsv"
    units = tmp_path / "units.tsv"
    samples.write_text(
        "SAMPLE_ID\tR1\n"
        "HG003\t/fsx/references/genomic_data/organism_reads_slim/HG003/R1.fastq.gz\n",
        encoding="utf-8",
    )
    units.write_text(
        "SAMPLE_ID\tR1\n"
        "HG003\t/fsx/control_data/genomic_data/organism_reads_slim/HG003/R1.fastq.gz\n",
        encoding="utf-8",
    )

    driver.verify_slim_mounted_config(samples, units)

    units.write_text(
        "SAMPLE_ID\tR1\n"
        "HG003\t/fsx/staging/staged_external_sequencing_data/HG003/R1.fastq.gz\n",
        encoding="utf-8",
    )

    try:
        driver.verify_slim_mounted_config(samples, units)
    except RuntimeError as exc:
        assert "staging path" in str(exc)
    else:
        raise AssertionError("staging path was accepted")


def test_driver_mount_create_uses_long_wait_contract() -> None:
    text = DRIVER_PATH.read_text(encoding="utf-8")

    assert '"--timeout-seconds",\n                "5400"' in text
    assert '"--timeout-seconds",\n                "2400"' not in text


def test_driver_command_selector_orders_and_rejects_bad_ids() -> None:
    driver = _load_driver()
    command_map = {command_id: object() for command_id in driver.COMMAND_ORDER}

    selected = driver.parse_requested_commands(
        command_map,
        "ont_snv_alignstats,illumina_snv_alignstats",
    )

    assert selected == ["illumina_snv_alignstats", "ont_snv_alignstats"]

    try:
        driver.parse_requested_commands(command_map, "illumina_snv_alignstats,not-a-command")
    except RuntimeError as exc:
        assert "Unknown command IDs" in str(exc)
    else:
        raise AssertionError("unknown command id was accepted")
