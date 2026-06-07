from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

from daylily_ec.cli import app
from daylily_ec.repositories import load_repository_catalog
from daylily_ec.run_mounts import MOUNT_PURPOSE_RUN, RunMountRecord
from daylily_ec.tests_runner import (
    DYEC800_COMMAND_IDS,
    KITCHEN_SINK_COMMAND_IDS,
    CommandCatalogOptions,
    PhaseResult,
    RenderedPhase,
    TestsRunnerError as RunnerError,
    build_evidence_prefix,
    catalog_role_uris,
    chunked,
    convert_manifest_path,
    convert_sample_row,
    convert_manifest_value,
    dyec800_command_codes,
    execute_batch,
    execute_phases,
    generated_config_paths,
    ordered_commands,
    parse_command_codes,
    parse_workflow_launch_metadata,
    prepare_command_inputs,
    prepare_run_mounts,
    record_to_payload,
    render_phase,
    render_dy_command,
    role_root_uri,
    run_command_catalog,
    run_id_from_source,
    run_platform,
    run_profile_source,
    run_pytest,
    selected_dayoa_version,
    wait_for_phase,
    write_phase_plan,
)


runner = CliRunner()


def _run_mount_record(
    *,
    source_s3_uri: str,
    mount_id: str = "RUN123",
    platform: str = "ILMN",
) -> RunMountRecord:
    return RunMountRecord(
        mount_id=mount_id,
        purpose=MOUNT_PURPOSE_RUN,
        run_id=mount_id,
        platform=platform,
        cluster_name="dyec800",
        region="us-west-2",
        source_s3_uri=source_s3_uri,
        fsx_file_system_id="fs-123",
        file_system_path=f"/run_dir_mounts/{mount_id}/",
        headnode_path=f"/fsx/run_dir_mounts/{mount_id}/",
        association_id=f"dra-{mount_id.lower()}",
        lifecycle="AVAILABLE",
        read_only=True,
    )


def _fake_stage(argv: list[str]) -> int:
    config_dir = Path(argv[argv.index("--config-dir") + 1])
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "20260607T000000Z_samples.tsv").write_text("SAMPLE_ID\nHG003\n", encoding="utf-8")
    (config_dir / "20260607T000000Z_units.tsv").write_text("SAMPLE_ID\nHG003\n", encoding="utf-8")
    print("Generated configuration files:")
    print(f"  samples.tsv -> {config_dir / '20260607T000000Z_samples.tsv'}")
    print(f"  units.tsv   -> {config_dir / '20260607T000000Z_units.tsv'}")
    return 0


def _fake_launch_factory(calls: list[list[str]]):
    def fake_launch(argv: list[str]) -> int:
        calls.append(argv)
        session = argv[argv.index("--session-name") + 1]
        print(f"__DAYLILY_SESSION__={session}")
        print(f"__DAYLILY_RUN_DIR__=/home/ubuntu/daylily-runs/{session}")
        print(f"__DAYLILY_REPO_PATH__=/fsx/analysis_results/ubuntu/{session}/daylily-omics-analysis")
        return 0

    return fake_launch


def test_run_pytest_uses_current_python_and_coverage(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, list[str]] = {}

    def fake_run(cmd: list[str]):
        captured["cmd"] = cmd
        return SimpleNamespace(returncode=7)

    monkeypatch.setattr("daylily_ec.tests_runner.subprocess.run", fake_run)

    assert run_pytest(coverage=True, pytest_args=["tests/test_cli_registry_v2.py", "-q"]) == 7
    assert captured["cmd"][1:4] == ["-m", "pytest", "--cov=daylily_ec"]
    assert "--cov-branch" in captured["cmd"]
    assert "--cov-fail-under=80" in captured["cmd"]
    assert captured["cmd"][-2:] == ["tests/test_cli_registry_v2.py", "-q"]


def test_tests_pytest_cli_passes_arguments(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_run_pytest(*, coverage: bool, pytest_args: list[str]) -> int:
        captured["coverage"] = coverage
        captured["pytest_args"] = pytest_args
        return 0

    monkeypatch.setattr("daylily_ec.tests_runner.run_pytest", fake_run_pytest)

    result = runner.invoke(app, ["tests", "pytest", "--coverage", "--", "-k", "smoke"])

    assert result.exit_code == 0, result.output
    assert captured == {"coverage": True, "pytest_args": ["-k", "smoke"]}


def test_command_code_parser_exact_all_duplicate_and_unknown() -> None:
    catalog = load_repository_catalog()

    parsed = parse_command_codes("illumina_snv_alignstats, ont_snv_alignstats", catalog)
    assert [command.command_id for command in parsed] == [
        "illumina_snv_alignstats",
        "ont_snv_alignstats",
    ]
    assert len(parse_command_codes("all", catalog)) == len(catalog.commands())
    with pytest.raises(RunnerError, match="Duplicate command id"):
        parse_command_codes("ont_snv_alignstats ont_snv_alignstats", catalog)
    with pytest.raises(RunnerError, match="Unknown analysis command"):
        parse_command_codes("missing_command", catalog)
    assert dyec800_command_codes() == ",".join(DYEC800_COMMAND_IDS)


def test_kitchen_sinks_order_first() -> None:
    catalog = load_repository_catalog()
    commands = parse_command_codes(
        "illumina_snv_alignstats ont_snv_alignstats_kitchensink ultima_snv_alignstats",
        catalog,
    )

    ordered = ordered_commands(commands)

    assert ordered[0].command_id == "ont_snv_alignstats_kitchensink"
    assert [command.command_id for command in ordered[1:]] == [
        "illumina_snv_alignstats",
        "ultima_snv_alignstats",
    ]


def test_render_dy_command_normalizes_flags_and_warmup() -> None:
    command = "bin/day_run target -p -j 20 -k -T 1 --config 'x={\"y\":1}' -n"

    dry = render_dy_command(command, jobs=150, dry_run=True)
    live = render_dy_command(command, jobs=150, dry_run=False)
    warmup = render_dy_command(command, jobs=150, dry_run=False, warmup=True)

    assert " -j 150 " in f" {dry} "
    assert " -p " in f" {dry} "
    assert " -k " in f" {dry} "
    assert " -T 0 " in f" {dry} "
    assert " -n " in f" {dry} "
    assert dry.endswith("--default-resources time=100")
    assert " -n" not in f" {live} "
    assert " --conda-create-envs-only " in f" {warmup} "
    assert warmup.endswith("--default-resources time=100")
    assert "x={\"y\":1}" in dry
    assert (
        render_dy_command(
            "bin/day_run target --default-resources time=240 -j 20",
            jobs=150,
            dry_run=False,
        ).count("time=")
        == 1
    )


def test_ont_kitchensink_slim_fixture_does_not_require_fastq_alignment() -> None:
    command = load_repository_catalog().get_command("ont_snv_alignstats_kitchensink")

    assert "produce_sentmm2ont_align" not in command.dy_command
    assert "produce_sentmm2ont_align" not in command.dryrun_dy_command
    assert "produce_sentmm2ont_align" not in command.targets
    assert command.test_data_profile == "default_reads_slim"
    assert "ONT_CRAM" in {
        column
        for column_set in command.input_requirements.accepted_source_column_sets
        for column in column_set
    }


def test_prepare_run_mounts_blocks_then_creates_missing() -> None:
    catalog = load_repository_catalog()
    command = catalog.get_command("ont_run_qc")
    source = catalog.test_data_profiles[command.test_data_profile].source_s3_uri_template

    with pytest.raises(RunnerError, match="Missing run-directory DRA mounts"):
        prepare_run_mounts(
            [command],
            catalog=catalog,
            cluster="dyec800",
            profile="lsmc",
            region="us-west-2",
            create_missing=False,
            mount_list_func=lambda **_kwargs: [],
            mount_create_func=lambda _request: _run_mount_record(source_s3_uri=source),
        )

    captured: dict[str, object] = {}

    def fake_create(request):
        captured["request"] = request
        return _run_mount_record(
            source_s3_uri=source,
            mount_id=request.mount_id,
            platform=request.platform,
        )

    records = prepare_run_mounts(
        [command],
        catalog=catalog,
        cluster="dyec800",
        profile="lsmc",
        region="us-west-2",
        create_missing=True,
        mount_list_func=lambda **_kwargs: [],
        mount_create_func=fake_create,
    )

    request = captured["request"]
    assert request.wait is True
    assert request.timeout_seconds == 3600
    assert request.read_only is True
    assert source in records


def test_run_command_catalog_dry_run_only_renders_and_exports(tmp_path: Path) -> None:
    catalog = load_repository_catalog()
    ont = catalog.get_command("ont_run_qc")
    source = catalog.test_data_profiles[ont.test_data_profile].source_s3_uri_template
    launch_calls: list[list[str]] = []

    result = run_command_catalog(
        CommandCatalogOptions(
            cluster="dyec800",
            profile="lsmc",
            region="us-west-2",
            command_codes="illumina_snv_alignstats ont_run_qc",
            evidence_s3_uri="s3://evidence-root/validation",
            dry_run_only=True,
            output_dir=tmp_path,
            stamp="20260607T000000Z",
            poll_interval_seconds=1,
        ),
        stage_func=_fake_stage,
        launch_func=_fake_launch_factory(launch_calls),
        status_func=lambda _metadata, _phase: {"exit_code": 0},
        mount_list_func=lambda **_kwargs: [_run_mount_record(source_s3_uri=source, platform="ONT")],
    )

    assert result.rc == 0
    assert result.evidence_prefix_s3_uri == (
        "s3://evidence-root/validation/dyec800/command_catalog_results/"
        "9.0.0-20260607T000000Z/"
    )
    assert [phase.phase.phase for phase in result.phases] == ["dryrun", "dryrun"]
    assert all("20260607T000000Z" in call[call.index("--analysis-id") + 1] for call in launch_calls)
    assert all("--dry-run" in call for call in launch_calls)
    assert all("-n" in call[call.index("--dy-command") + 1] for call in launch_calls)
    assert (tmp_path / "command_registry.json").is_file()
    assert (tmp_path / "summary.json").is_file()


def test_run_command_catalog_live_only_runs_kitchen_sinks_after_dryrun(tmp_path: Path) -> None:
    launch_calls: list[list[str]] = []

    result = run_command_catalog(
        CommandCatalogOptions(
            cluster="dyec800",
            profile="lsmc",
            region="us-west-2",
            command_codes=(
                "illumina_snv_alignstats "
                "illumina_hg002_kitchensink_multiqc "
                "ont_snv_alignstats_kitchensink"
            ),
            evidence_s3_uri="s3://evidence-root/validation",
            dry_run_only=False,
            output_dir=tmp_path,
            stamp="20260607T000000Z",
            parallel=2,
            poll_interval_seconds=1,
        ),
        stage_func=_fake_stage,
        launch_func=_fake_launch_factory(launch_calls),
        status_func=lambda _metadata, _phase: {"exit_code": 0},
        mount_list_func=lambda **_kwargs: [],
    )

    phase_names = [phase.phase.phase for phase in result.phases]
    assert phase_names[:2] == ["warmup", "warmup"]
    assert phase_names.count("dryrun") == 3
    assert phase_names.count("live") == 2
    live_ids = {phase.phase.command_id for phase in result.phases if phase.phase.phase == "live"}
    assert live_ids <= KITCHEN_SINK_COMMAND_IDS
    warmup_commands = [
        call[call.index("--dy-command") + 1]
        for call in launch_calls
        if "ccv_warmup" in call[call.index("--analysis-id") + 1]
    ]
    assert warmup_commands
    assert all("--conda-create-envs-only" in command for command in warmup_commands)


def test_command_catalog_cli_emits_json(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    payload = {
        "rc": 0,
        "output_dir": str(tmp_path),
        "evidence_prefix_s3_uri": "s3://bucket/dyec800/command_catalog_results/9.0.0-stamp/",
        "command_ids": ["illumina_snv_alignstats"],
        "dry_run_only": True,
        "phases": [],
    }
    captured_read: dict[str, object] = {}

    def fake_read_workflow_file(**kwargs):
        captured_read.update(kwargs)
        return SimpleNamespace(stdout='{"exit_code": 0}')

    def fake_run_command_catalog(*_args, **kwargs):
        status_func = kwargs["status_func"]
        status_func(
            SimpleNamespace(
                session_name="ccv_dryrun_illumina_snv_alignstats",
                run_dir="/home/ubuntu/daylily-runs/ccv_dryrun_illumina_snv_alignstats",
            ),
            RenderedPhase(
                command_id="illumina_snv_alignstats",
                phase="dryrun",
                analysis_id="ccv_dryrun_illumina_snv_alignstats",
                session_name="ccv_dryrun_illumina_snv_alignstats",
                dy_command="dy-r all -j 150 -p -k -T 0 -n",
                workflow_argv=(),
                export_destination_s3_uri="s3://bucket/root/",
            ),
        )
        return SimpleNamespace(rc=0, to_payload=lambda: payload)

    monkeypatch.setattr("daylily_ec.cli._read_workflow_file", fake_read_workflow_file)
    monkeypatch.setattr(
        "daylily_ec.cli._parse_workflow_status_payload",
        lambda _stdout: {"exit_code": 0},
    )
    monkeypatch.setattr("daylily_ec.tests_runner.run_command_catalog", fake_run_command_catalog)

    result = runner.invoke(
        app,
        [
            "--json",
            "tests",
            "command-catalog",
            "--cluster",
            "dyec800",
            "--profile",
            "lsmc",
            "--region",
            "us-west-2",
            "--command-codes",
            "illumina_snv_alignstats",
            "--evidence-s3-uri",
            "s3://bucket/root",
            "--dry-run",
        ],
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == payload
    assert captured_read["session"] == "ccv_dryrun_illumina_snv_alignstats"
    assert captured_read["run_dir"] is None


def test_runner_payloads_and_small_helpers(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    phase = RenderedPhase(
        command_id="illumina_snv_alignstats",
        phase="dryrun",
        analysis_id="ccv_dryrun_illumina_snv_alignstats",
        session_name="ccv_dryrun_illumina_snv_alignstats",
        dy_command="dy-r all -j 150 -p -k -T 0 -n",
        workflow_argv=("workflow", "launch", "--analysis-id", "ccv_dryrun_illumina_snv_alignstats"),
        export_destination_s3_uri=(
            "s3://bucket/root/ubuntu/ccv_dryrun_illumina_snv_alignstats/"
        ),
    )

    assert PhaseResult(phase=phase, launch_rc=1).succeeded is False
    assert PhaseResult(phase=phase).succeeded is True
    assert PhaseResult(phase=phase, status_payload={"exit_code": "0"}).exit_code is None
    payload = PhaseResult(
        phase=phase,
        status_payload={"exit_code": 0},
        launch_metadata=SimpleNamespace(
            session_name="session-a",
            run_dir="/run/dir",
            repo_path="/repo/path",
        ),
    )
    result_payload = SimpleNamespace(
        to_payload=lambda: {
            "phases": [
                {
                    "command_id": payload.phase.command_id,
                    "exit_code": payload.exit_code,
                    "run_dir": payload.launch_metadata.run_dir,
                }
            ]
        }
    ).to_payload()
    assert result_payload["phases"][0]["exit_code"] == 0

    captured: dict[str, list[str]] = {}

    def fake_run(cmd: list[str]):
        captured["cmd"] = cmd
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr("daylily_ec.tests_runner.subprocess.run", fake_run)
    assert run_pytest(coverage=False, pytest_args=[]) == 0
    assert captured["cmd"][-1] == "-q"

    assert parse_workflow_launch_metadata(
        "__DAYLILY_SESSION__=s1\n"
        "__DAYLILY_RUN_DIR__=/runs/s1\n"
        "__DAYLILY_REPO_PATH__=/repo\n"
    ).repo_path == "/repo"
    write_phase_plan(tmp_path / "phase_plan.json", [phase])
    assert json.loads((tmp_path / "phase_plan.json").read_text(encoding="utf-8"))["phases"][0][
        "command_id"
    ] == "illumina_snv_alignstats"
    assert list(chunked([phase, phase, phase], 2)) == [[phase, phase], [phase]]


def test_parser_and_rendering_error_branches(tmp_path: Path) -> None:
    catalog = load_repository_catalog()
    with pytest.raises(RunnerError, match="--command-codes is required"):
        parse_command_codes("", catalog)

    with pytest.raises(RunnerError, match="multiple DayOA git tags"):
        selected_dayoa_version(
            [
                SimpleNamespace(git_tag="9.0.0"),
                SimpleNamespace(git_tag="9.0.1"),
            ]
        )

    compact = render_dy_command(
        "dy-r target -j20 --jobs=30 -T1 --timestamp=2 --dry-run --printshellcmds",
        jobs=150,
        dry_run=False,
    )
    assert compact == "dy-r target -j 150 -p -k -T 0 --default-resources time=100"
    assert (
        render_dy_command(
            "dy-r target -j20",
            jobs=150,
            dry_run=False,
            max_runtime_minutes=0,
        )
        == "dy-r target -j 150 -p -k -T 0"
    )
    assert build_evidence_prefix(
        evidence_s3_uri="s3://bucket/root",
        cluster="dyec800",
        dayoa_version="9.0.0",
        stamp="20260607T000000Z",
    ) == "s3://bucket/root/dyec800/command_catalog_results/9.0.0-20260607T000000Z/"
    assert (
        role_root_uri(
            mount_path="/fsx/references",
            data_root="/fsx/references",
            s3_uri="s3://bucket/",
        )
        == "s3://bucket/"
    )
    assert role_root_uri(
        mount_path="/fsx/references",
        data_root="/fsx/references/hg38",
        s3_uri="s3://bucket/dayoa/hg38/",
    ) == "s3://bucket/dayoa/"

    config_dir = tmp_path / "empty-config"
    config_dir.mkdir()
    with pytest.raises(RunnerError, match="Expected one generated"):
        generated_config_paths(config_dir)


def test_catalog_role_and_input_error_branches(tmp_path: Path) -> None:
    catalog = load_repository_catalog()
    roles = catalog_role_uris(catalog)
    assert roles["reference_s3_uri"].startswith("s3://")
    assert roles["control_data_s3_uri"].startswith("s3://")

    with pytest.raises(RunnerError, match="Catalog is missing"):
        catalog_role_uris(SimpleNamespace(test_data_locations=[]))

    command = SimpleNamespace(command_id="x", test_data_profile="missing")
    with pytest.raises(RunnerError, match="references unknown profile"):
        run_profile_source(command, SimpleNamespace(test_data_profiles={}))

    fallback_command = SimpleNamespace(
        command_id="fallback",
        input_requirements=SimpleNamespace(required_run_context_values={}),
        compatible_platforms=["ONT"],
    )
    assert run_platform(fallback_command) == "ONT"
    with pytest.raises(RunnerError, match="has no run platform"):
        run_platform(
            SimpleNamespace(
                command_id="bad",
                input_requirements=SimpleNamespace(required_run_context_values={}),
                compatible_platforms=[],
            )
        )

    assert run_id_from_source("s3://bucket/path/RUN123/") == "RUN123"

    class Dumpable:
        def model_dump(self, *, mode: str):
            return {"mode": mode}

    assert record_to_payload(Dumpable()) == {"mode": "json"}

    run_command = catalog.get_command("ont_run_qc")
    with pytest.raises(RunnerError, match="No run mount record resolved"):
        prepare_command_inputs(
            [run_command],
            catalog=catalog,
            output_dir=tmp_path,
            role_uris=roles,
            evidence_prefix_s3_uri="s3://bucket/root/dyec800/command_catalog_results/9.0.0-stamp/",
            profile="lsmc",
            region="us-west-2",
            cluster="dyec800",
            run_mounts={},
            stage_func=_fake_stage,
        )

    manifests = prepare_command_inputs(
        [SimpleNamespace(command_id="utility", input_contract="none")],
        catalog=catalog,
        output_dir=tmp_path,
        role_uris=roles,
        evidence_prefix_s3_uri="s3://bucket/root/dyec800/command_catalog_results/9.0.0-stamp/",
        profile="lsmc",
        region="us-west-2",
        cluster="dyec800",
        run_mounts={},
        stage_func=_fake_stage,
    )
    assert manifests == {"utility": {}}

    with pytest.raises(RunnerError, match="Unsupported input contract"):
        prepare_command_inputs(
            [SimpleNamespace(command_id="bad", input_contract="unsupported")],
            catalog=catalog,
            output_dir=tmp_path,
            role_uris=roles,
            evidence_prefix_s3_uri="s3://bucket/root/dyec800/command_catalog_results/9.0.0-stamp/",
            profile="lsmc",
            region="us-west-2",
            cluster="dyec800",
            run_mounts={},
            stage_func=_fake_stage,
        )


def test_manifest_conversion_and_stage_failure(tmp_path: Path) -> None:
    catalog = load_repository_catalog()
    command = catalog.get_command("illumina_snv_alignstats")
    roles = catalog_role_uris(catalog)

    converted = convert_sample_row(
        {
            None: "ignored",
            "REFERENCE": "s3://lsmc-dayoa-references-usw2/hg38/file.fa",
            "CONTROL": "s3://lsmc-dayoa-control-data-usw2/truth.vcf.gz",
            "MIXED": "plain,s3://lsmc-dayoa-references-usw2/index",
        }
    )
    assert None not in converted
    assert converted["REFERENCE"] == "/fsx/references/hg38/file.fa"
    assert converted["CONTROL"] == "/fsx/control_data/truth.vcf.gz"
    assert converted["MIXED"] == "plain,/fsx/references/index"
    assert convert_manifest_value("a,b") == "a,b"
    assert convert_manifest_path("s3://elsewhere/object") == "s3://elsewhere/object"

    with pytest.raises(RunnerError, match="Config generation failed"):
        prepare_command_inputs(
            [command],
            catalog=catalog,
            output_dir=tmp_path,
            role_uris=roles,
            evidence_prefix_s3_uri="s3://bucket/root/dyec800/command_catalog_results/9.0.0-stamp/",
            profile="lsmc",
            region="us-west-2",
            cluster="dyec800",
            run_mounts={},
            stage_func=lambda _argv: 2,
        )


def test_render_phase_none_contract_and_execution_failure_paths(tmp_path: Path) -> None:
    command = SimpleNamespace(
        command_id="simple_test",
        repository="daylily-omics-analysis",
        git_tag="9.0.0",
        genome="hg38",
        dy_command="dy-r help -j 1",
        no_containerized=True,
        input_contract="none",
    )
    phase = render_phase(
        command,
        phase="dryrun",
        manifests={},
        evidence_prefix_s3_uri="s3://bucket/root/dyec800/command_catalog_results/9.0.0-stamp/",
        executing_entity="ubuntu",
        profile="lsmc",
        region="us-west-2",
        cluster="dyec800",
        jobs=150,
        output_dir=tmp_path,
        stamp="20260607T000000Z",
        max_runtime_minutes=100,
        warmup=False,
        dry_run=True,
    )
    assert "--no-containerized" in phase.workflow_argv
    assert "--no-input-staging" in phase.workflow_argv
    assert "--bootstrap-test-config" in phase.workflow_argv

    def failing_launch(_argv: list[str]) -> int:
        print("launch failed")
        return 9

    failed = execute_batch(
        [phase],
        launch_func=failing_launch,
        status_func=lambda _metadata, _phase: {"exit_code": 0},
        timeout_minutes=1,
        poll_interval_seconds=1,
        output_dir=tmp_path,
    )
    assert failed[0].launch_rc == 9
    assert failed[0].status_payload == {}

    timed_out = wait_for_phase(
        PhaseResult(phase=phase),
        status_func=lambda _metadata, _phase: {},
        timeout_minutes=0,
        poll_interval_seconds=0,
    )
    assert timed_out.status_payload["reason"] == "workflow status wait timed out"

    dry = RenderedPhase(
        command_id="simple_test",
        phase="dryrun",
        analysis_id="dry",
        session_name="dry",
        dy_command="dy-r all -n",
        workflow_argv=("workflow", "launch", "--analysis-id", "dry"),
        export_destination_s3_uri="s3://bucket/ubuntu/dry/",
    )
    live = RenderedPhase(
        command_id="simple_test",
        phase="live",
        analysis_id="live",
        session_name="live",
        dy_command="dy-r all",
        workflow_argv=("workflow", "launch", "--analysis-id", "live"),
        export_destination_s3_uri="s3://bucket/ubuntu/live/",
    )
    gated = execute_phases(
        [dry, live],
        dry_run_only=False,
        parallel=3,
        launch_func=lambda _argv: 0,
        status_func=lambda _metadata, _phase: {"exit_code": 1},
        timeout_minutes=1,
        poll_interval_seconds=1,
        output_dir=tmp_path,
    )
    assert [result.phase.phase for result in gated] == ["dryrun", "live"]
    assert gated[1].status_payload["reason"] == "dryrun did not succeed"
