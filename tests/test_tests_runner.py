from __future__ import annotations

import csv
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

from daylily_ec.cli import app
from daylily_ec.repositories import load_repository_catalog
from daylily_ec.run_mounts import MOUNT_PURPOSE_RUN, RunMountRecord
from daylily_ec.tests_runner import (
    DEFAULT_COMMAND_CATALOG_PARALLEL,
    DYEC_RELEASED_ALL_COMMAND_TOKEN,
    DYEC_RELEASED_CORE_COMMAND_IDS,
    DYEC_RELEASED_CORE_COMMAND_TOKEN,
    CommandCatalogOptions,
    PhaseResult,
    RUN_DRA_CREATE_WAIT_TIMEOUT_SECONDS,
    RenderedPhase,
    TestsRunnerError as RunnerError,
    build_evidence_prefix,
    catalog_role_uris,
    chunked,
    convert_manifest_path,
    convert_sample_row,
    convert_manifest_value,
    dyec_released_core_command_codes,
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
    write_sample_manifest,
    write_phase_plan,
)


runner = CliRunner()
DAYOA_BLESSED_TAG = "10.0.85"


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


def test_run_pytest_defaults_to_quiet_current_python(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, list[str]] = {}

    def fake_run(cmd: list[str]):
        captured["cmd"] = cmd
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr("daylily_ec.tests_runner.subprocess.run", fake_run)

    assert run_pytest(coverage=False, pytest_args=[]) == 0
    assert captured["cmd"][1:] == ["-m", "pytest", "-q"]


@pytest.mark.parametrize("override_arg", ["--no-cov", "--cov-fail-under", "--cov-fail-under=0"])
def test_run_pytest_coverage_rejects_gate_overrides(
    monkeypatch: pytest.MonkeyPatch,
    override_arg: str,
) -> None:
    def fail_if_called(_cmd: list[str]):
        raise AssertionError("pytest subprocess should not run after a coverage gate override")

    monkeypatch.setattr("daylily_ec.tests_runner.subprocess.run", fail_if_called)

    with pytest.raises(RunnerError, match="coverage source and 80% fail-under gate"):
        run_pytest(coverage=True, pytest_args=[override_arg])


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


def test_tests_pytest_cli_rejects_coverage_gate_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CONDA_PREFIX", "/tmp/dayec")
    monkeypatch.setenv("CONDA_DEFAULT_ENV", "DAY-EC")

    result = runner.invoke(
        app,
        ["tests", "pytest", "--coverage", "--", "--cov-fail-under=0"],
    )

    assert result.exit_code != 0
    assert "pytest-cov override flags" in result.output
    assert "--cov-fail-under=0" in result.output


def test_command_code_parser_exact_released_sets_duplicate_and_unknown() -> None:
    catalog = load_repository_catalog()

    parsed = parse_command_codes("illumina_snv_alignstats, ont_snv_alignstats", catalog)
    assert [command.command_id for command in parsed] == [
        "illumina_snv_alignstats",
        "ont_snv_alignstats",
    ]
    core_commands = parse_command_codes(DYEC_RELEASED_CORE_COMMAND_TOKEN, catalog)
    assert [command.command_id for command in core_commands] == list(DYEC_RELEASED_CORE_COMMAND_IDS)
    assert dyec_released_core_command_codes() == DYEC_RELEASED_CORE_COMMAND_TOKEN
    all_commands = parse_command_codes(DYEC_RELEASED_ALL_COMMAND_TOKEN, catalog)
    assert len(all_commands) == len(
        tuple(command for command in catalog.commands() if command.type != "research")
    )
    all_command_ids = {command.command_id for command in all_commands}
    assert "complete_genomics_mgi_snv_concordance" in all_command_ids
    assert "simple-test" in all_command_ids
    assert "illumina_pangenome_snv" in all_command_ids
    assert "illumina_bclconvert" not in all_command_ids
    assert "illumina_run_qc_bclconvert" not in all_command_ids
    with pytest.raises(RunnerError, match="Unknown analysis command"):
        parse_command_codes("all", catalog)
    assert (
        parse_command_codes("complete_genomics_mgi_snv_concordance", catalog)[0].command_id
        == "complete_genomics_mgi_snv_concordance"
    )
    assert (
        parse_command_codes("illumina_bclconvert", catalog)[0].command_id
        == "illumina_bclconvert"
    )
    with pytest.raises(RunnerError, match="Duplicate command id"):
        parse_command_codes("ont_snv_alignstats ont_snv_alignstats", catalog)
    with pytest.raises(RunnerError, match="Unknown analysis command"):
        parse_command_codes("missing_command", catalog)


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
    assert " -T 1 " in f" {dry} "
    assert " -n " in f" {dry} "
    assert "--default-resources" not in dry
    assert " -n" not in f" {live} "
    assert " --conda-create-envs-only " in f" {warmup} "
    assert "--default-resources" not in warmup
    assert "x={\"y\":1}" in dry
    assert (
        render_dy_command(
            "bin/day_run target --default-resources time=240 -j 20",
            jobs=150,
            dry_run=False,
        ).count("time=")
        == 1
    )
    simple_test = render_dy_command(
        "source dyoainit; dy-a local hg38; dy-r -p -k -j 1 help",
        jobs=150,
        dry_run=True,
    )
    assert simple_test.startswith("source dyoainit; dy-a local hg38; dy-r help ")
    assert "'dyoainit;'" not in simple_test
    assert "'hg38;'" not in simple_test


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


def test_complete_genomics_slim_fixture_can_be_written(tmp_path: Path) -> None:
    command = load_repository_catalog().get_command("complete_genomics_mgi_snv_concordance")

    manifest = write_sample_manifest(command, tmp_path)

    text = manifest.read_text(encoding="utf-8")
    assert "CG_R1_FQ" in text
    assert "CG_R2_FQ" in text
    assert "CG/MGI" in text
    assert "\tpass_through\t/fsx/staging/staged_external_sequencing_data\t" in text


def test_write_sample_manifest_uses_command_specific_templates(tmp_path: Path) -> None:
    catalog = load_repository_catalog()
    ilmn_dir = tmp_path / "ilmn"
    metagenomics_dir = tmp_path / "metagenomics"
    hybrid_dir = tmp_path / "hybrid"
    inflection_dir = tmp_path / "inflection"
    ilmn_dir.mkdir()
    metagenomics_dir.mkdir()
    hybrid_dir.mkdir()
    inflection_dir.mkdir()

    ilmn_manifest = write_sample_manifest(
        catalog.get_command("illumina_hg002_kitchensink_multiqc"), ilmn_dir
    )
    metagenomics_manifest = write_sample_manifest(
        catalog.get_command("all_metagenomic_pipelines"), metagenomics_dir
    )
    hybrid_manifest = write_sample_manifest(
        catalog.get_command("hybrid_ilmn_ont_snv_kitchensink"), hybrid_dir
    )
    inflection_manifest = write_sample_manifest(
        catalog.get_command("inflection-bjuice-product-v0.1"), inflection_dir
    )

    with ilmn_manifest.open(newline="", encoding="utf-8") as handle:
        ilmn_row = next(csv.DictReader(handle, delimiter="\t"))
    with metagenomics_manifest.open(newline="", encoding="utf-8") as handle:
        metagenomics_row = next(csv.DictReader(handle, delimiter="\t"))
    with hybrid_manifest.open(newline="", encoding="utf-8") as handle:
        hybrid_row = next(csv.DictReader(handle, delimiter="\t"))
    with inflection_manifest.open(newline="", encoding="utf-8") as handle:
        inflection_row = next(csv.DictReader(handle, delimiter="\t"))

    assert ilmn_row["SAMPLE_ID"] == "HG002"
    assert ilmn_row["EXTERNAL_SAMPLE_ID"] == "HG002"
    assert ilmn_row["EXPERIMENTID"] == "5x"
    assert "HG002_5x_R1.fastq.gz" in ilmn_row["ILMN_R1_FQ"]
    assert "HG002_5x_R2.fastq.gz" in ilmn_row["ILMN_R2_FQ"]
    assert metagenomics_row["SAMPLE_ID"] == "HG003"
    assert metagenomics_row["EXPERIMENTID"] == "5x"
    assert "HG003_5x_R1.fastq.gz" in metagenomics_row["ILMN_R1_FQ"]
    assert "HG003_5x_R2.fastq.gz" in metagenomics_row["ILMN_R2_FQ"]
    assert ilmn_row["ILMN_R1_FQ"].startswith("/fsx/data/genomic_data/organism_reads_slim/")
    assert ilmn_row["ILMN_R2_FQ"].startswith("/fsx/data/genomic_data/organism_reads_slim/")
    assert ilmn_row["STAGE_DIRECTIVE"] == "pass_through"

    assert hybrid_row["SAMPLE_ID"] == "HG003"
    assert hybrid_row["EXTERNAL_SAMPLE_ID"] == "HG003"
    assert hybrid_row["EXPERIMENTID"] == "SR5x-ONT5x"
    assert hybrid_row["ILMN_R1_FQ"].startswith("/fsx/data/genomic_data/organism_reads_slim/")
    assert hybrid_row["ILMN_R2_FQ"].startswith("/fsx/data/genomic_data/organism_reads_slim/")
    assert hybrid_row["ONT_CRAM"].startswith("/fsx/data/genomic_data/organism_reads_slim/")
    assert "HG003_5x_R1.fastq.gz" in hybrid_row["ILMN_R1_FQ"]
    assert "HG003_5x_R2.fastq.gz" in hybrid_row["ILMN_R2_FQ"]
    assert "HG003_5x.cleaned.cram" in hybrid_row["ONT_CRAM"]
    assert hybrid_row["STAGE_DIRECTIVE"] == "pass_through"

    assert inflection_row["SAMPLE_ID"] == "HG003"
    assert inflection_row["EXPERIMENTID"] == "SR5x-ONT5x"
    assert "HG003_5x_R1.fastq.gz" in inflection_row["ILMN_R1_FQ"]
    assert "HG003_5x_R2.fastq.gz" in inflection_row["ILMN_R2_FQ"]
    assert "HG003_5x.cleaned.cram" in inflection_row["ONT_CRAM"]
    assert inflection_row["STAGE_DIRECTIVE"] == "pass_through"


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
    assert request.timeout_seconds == RUN_DRA_CREATE_WAIT_TIMEOUT_SECONDS
    assert request.read_only is True
    assert source in records


def test_run_command_catalog_dry_run_only_renders_and_exports(tmp_path: Path) -> None:
    catalog = load_repository_catalog()
    ont = catalog.get_command("ont_run_qc")
    ultima = catalog.get_command("ultima_run_qc")
    ont_source = catalog.test_data_profiles[ont.test_data_profile].source_s3_uri_template
    ultima_source = catalog.test_data_profiles[ultima.test_data_profile].source_s3_uri_template
    launch_calls: list[list[str]] = []

    result = run_command_catalog(
        CommandCatalogOptions(
            cluster="dyec800",
            profile="lsmc",
            region="us-west-2",
            command_codes="illumina_snv_alignstats ont_run_qc ultima_run_qc",
            evidence_s3_uri="s3://evidence-root/validation",
            dry_run_only=True,
            output_dir=tmp_path,
            stamp="20260607T000000Z",
            poll_interval_seconds=1,
        ),
        stage_func=_fake_stage,
        launch_func=_fake_launch_factory(launch_calls),
        status_func=lambda _metadata, _phase: {"exit_code": 0},
        mount_list_func=lambda **_kwargs: [
            _run_mount_record(source_s3_uri=ont_source, mount_id="ONT-RUN", platform="ONT"),
            _run_mount_record(source_s3_uri=ultima_source, mount_id="ULTIMA-RUN", platform="ULTIMA"),
        ],
    )

    assert result.rc == 0
    selected_commands = [catalog.get_command(command_id) for command_id in result.command_ids]
    assert result.evidence_prefix_s3_uri == (
        "s3://evidence-root/validation/dyec800/command_catalog_results/"
        f"{selected_dayoa_version(selected_commands)}-20260607T000000Z/"
    )
    assert [phase.phase.phase for phase in result.phases] == ["dryrun", "dryrun", "dryrun"]
    assert all("20260607T000000Z" in call[call.index("--analysis-id") + 1] for call in launch_calls)
    assert all("--dry-run" in call for call in launch_calls)
    assert all("-n" in call[call.index("--dy-command") + 1] for call in launch_calls)
    assert all("--export-destination-s3-uri" not in call for call in launch_calls)
    assert all("--export-trigger" not in call for call in launch_calls)
    ont_call = next(call for call in launch_calls if "ont_run_qc" in call[call.index("--analysis-id") + 1])
    ont_command = ont_call[ont_call.index("--dy-command") + 1]
    assert "run_context_file=config/runs.tsv" in ont_command
    assert "samples_table=.test_data/data/samples.tsv" in ont_command
    assert "units_table=.test_data/data/units.tsv" in ont_command
    with (tmp_path / "ultima_run_qc" / "runs.tsv").open(newline="", encoding="utf-8") as handle:
        ultima_rows = list(csv.DictReader(handle, delimiter="\t"))
    assert ultima_rows[0]["METRICS_PATH"] == (
        ".test_data/data/ultima_run_qc/ultima_demux_summary_mqc.tsv"
    )
    assert (tmp_path / "command_registry.json").is_file()
    assert (tmp_path / "summary.json").is_file()


def test_run_command_catalog_launches_ready_commands_before_missing_run_dras(
    tmp_path: Path,
) -> None:
    catalog = load_repository_catalog()
    ont = catalog.get_command("ont_run_qc")
    ont_source = catalog.test_data_profiles[ont.test_data_profile].source_s3_uri_template
    events: list[str] = []

    def fake_create(request):
        events.append(f"mount_create:{request.mount_id}")
        return _run_mount_record(
            source_s3_uri=ont_source,
            mount_id=request.mount_id,
            platform=request.platform,
        )

    def fake_launch(argv: list[str]) -> int:
        analysis_id = argv[argv.index("--analysis-id") + 1]
        events.append(f"launch:{analysis_id}")
        print(f"__DAYLILY_SESSION__={analysis_id}")
        return 0

    result = run_command_catalog(
        CommandCatalogOptions(
            cluster="dyec800",
            profile="lsmc",
            region="us-west-2",
            command_codes="illumina_snv_alignstats ont_run_qc",
            evidence_s3_uri="s3://evidence-root/validation",
            dry_run_only=True,
            create_missing_mounts=True,
            output_dir=tmp_path,
            stamp="20260607T000000Z",
            poll_interval_seconds=1,
        ),
        stage_func=_fake_stage,
        launch_func=fake_launch,
        status_func=lambda _metadata, _phase: {"exit_code": 0},
        mount_list_func=lambda **_kwargs: [],
        mount_create_func=fake_create,
    )

    assert result.rc == 0
    assert events[0] == "launch:ccv_dryrun_illumina_snv_alignstats_20260607T000000Z"
    assert events[1].startswith("mount_create:")
    assert events[2] == "launch:ccv_dryrun_ont_run_qc_20260607T000000Z"


def test_run_command_catalog_live_runs_all_requested_after_dryrun(tmp_path: Path) -> None:
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
    assert phase_names[:3] == ["warmup", "warmup", "warmup"]
    assert phase_names.count("dryrun") == 3
    assert phase_names.count("live") == 3
    live_ids = {phase.phase.command_id for phase in result.phases if phase.phase.phase == "live"}
    assert live_ids == {
        "illumina_snv_alignstats",
        "illumina_hg002_kitchensink_multiqc",
        "ont_snv_alignstats_kitchensink",
    }
    warmup_commands = [
        call[call.index("--dy-command") + 1]
        for call in launch_calls
        if "ccv_warmup" in call[call.index("--analysis-id") + 1]
    ]
    assert warmup_commands
    assert all("--conda-create-envs-only" in command for command in warmup_commands)
    assert all("--export-destination-s3-uri" not in call for call in launch_calls)
    assert json.loads(
        (tmp_path / "illumina_snv_alignstats" / "live_rendered.json").read_text(
            encoding="utf-8"
        )
    )["export_destination_s3_uri"].endswith(
        "/ubuntu/ccv_live_illumina_snv_alignstats_20260607T000000Z/"
    )


def test_run_command_catalog_live_runs_pangenome_dev_commands(tmp_path: Path) -> None:
    launch_calls: list[list[str]] = []

    result = run_command_catalog(
        CommandCatalogOptions(
            cluster="dyec800",
            profile="lsmc",
            region="us-west-2",
            command_codes="illumina_pangenome_snv ultima_pangenome_snv",
            evidence_s3_uri="s3://evidence-root/validation",
            dry_run_only=False,
            output_dir=tmp_path,
            stamp="20260607T000000Z",
            parallel=1,
            poll_interval_seconds=1,
        ),
        stage_func=_fake_stage,
        launch_func=_fake_launch_factory(launch_calls),
        status_func=lambda _metadata, _phase: {"exit_code": 0},
        mount_list_func=lambda **_kwargs: [],
    )

    assert result.rc == 0
    phase_names = [phase.phase.phase for phase in result.phases]
    assert phase_names == ["warmup", "warmup", "dryrun", "dryrun", "live", "live"]
    live_ids = {phase.phase.command_id for phase in result.phases if phase.phase.phase == "live"}
    assert live_ids == {"illumina_pangenome_snv", "ultima_pangenome_snv"}
    assert all(phase.phase.command_type == "dev" for phase in result.phases)


def test_run_command_catalog_renders_dragen_dev_command_with_rhel_profile(
    tmp_path: Path,
) -> None:
    launch_calls: list[list[str]] = []

    result = run_command_catalog(
        CommandCatalogOptions(
            cluster="dragen-fix",
            profile="lsmc",
            region="us-west-2",
            command_codes="illumina_dragen_pangenome_snv_concordance",
            evidence_s3_uri="s3://evidence-root/validation",
            dry_run_only=True,
            output_dir=tmp_path,
            stamp="20260607T000000Z",
            parallel=1,
            poll_interval_seconds=1,
        ),
        stage_func=_fake_stage,
        launch_func=_fake_launch_factory(launch_calls),
        status_func=lambda _metadata, _phase: {"exit_code": 0},
        mount_list_func=lambda **_kwargs: [],
    )

    assert result.rc == 0
    assert len(launch_calls) == 1
    launch = launch_calls[0]
    dy_command = launch[launch.index("--dy-command") + 1]
    assert launch[launch.index("--git-tag") + 1] == DAYOA_BLESSED_TAG
    assert launch[launch.index("--genome") + 1] == "hg38"
    assert "--no-default-activation" in launch
    assert dy_command.startswith("source dyoainit;")
    assert "dy-a slurm_rhel hg38" in dy_command
    assert "dy-r produce_drgpg_snv_vcf produce_snv_concordances" in dy_command
    assert "-n" in dy_command
    assert "bin/day_run" not in dy_command
    rendered = json.loads(
        (tmp_path / "illumina_dragen_pangenome_snv_concordance" / "dryrun_rendered.json")
        .read_text(encoding="utf-8")
    )
    assert rendered["command_type"] == "dev"
    assert rendered["day_profile"] == "slurm_rhel"
    with (
        tmp_path / "illumina_dragen_pangenome_snv_concordance" / "analysis_samples.tsv"
    ).open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    assert rows[0]["ILMN_R1_FQ"].startswith(
        "/fsx/data/genomic_data/organism_reads_slim/"
    )
    assert rows[0]["ILMN_R2_FQ"].startswith(
        "/fsx/data/genomic_data/organism_reads_slim/"
    )
    assert rows[0]["STAGE_DIRECTIVE"] == "pass_through"


def test_run_command_catalog_counts_dev_commands_for_aggregate_rc(tmp_path: Path) -> None:
    launch_calls: list[list[str]] = []

    result = run_command_catalog(
        CommandCatalogOptions(
            cluster="dyec800",
            profile="lsmc",
            region="us-west-2",
            command_codes="complete_genomics_mgi_snv_concordance",
            evidence_s3_uri="s3://evidence-root/validation",
            dry_run_only=True,
            output_dir=tmp_path,
            stamp="20260607T000000Z",
            parallel=1,
            poll_interval_seconds=1,
        ),
        stage_func=_fake_stage,
        launch_func=_fake_launch_factory(launch_calls),
        status_func=lambda _metadata, _phase: {"exit_code": 1},
        mount_list_func=lambda **_kwargs: [],
    )

    assert result.rc == 1
    assert len(result.phases) == 1
    assert result.phases[0].phase.command_type == "dev"
    assert result.phases[0].succeeded is False


def test_command_catalog_cli_emits_json(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    payload = {
        "rc": 0,
        "output_dir": str(tmp_path),
        "evidence_prefix_s3_uri": "s3://bucket/dyec800/command_catalog_results/10.0.0-stamp/",
        "command_ids": ["illumina_snv_alignstats"],
        "dry_run_only": True,
        "phases": [],
    }
    captured_read: dict[str, object] = {}

    def fake_read_workflow_file(**kwargs):
        captured_read.update(kwargs)
        return SimpleNamespace(stdout='{"exit_code": 0}')

    def fake_run_command_catalog(options, **kwargs):
        captured_read["parallel"] = options.parallel
        status_func = kwargs["status_func"]
        status_func(
            SimpleNamespace(
                session_name="ccv_dryrun_illumina_snv_alignstats",
                run_dir="/home/ubuntu/daylily-runs/ccv_dryrun_illumina_snv_alignstats",
            ),
            RenderedPhase(
                command_id="illumina_snv_alignstats",
                command_type="prod",
                phase="dryrun",
                analysis_id="ccv_dryrun_illumina_snv_alignstats",
                session_name="ccv_dryrun_illumina_snv_alignstats",
                dy_command="dy-r all -j 150 -p -k -T 1 -n",
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
    assert captured_read["parallel"] == DEFAULT_COMMAND_CATALOG_PARALLEL


def test_runner_payloads_and_small_helpers(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    phase = RenderedPhase(
        command_id="illumina_snv_alignstats",
        command_type="prod",
        phase="dryrun",
        analysis_id="ccv_dryrun_illumina_snv_alignstats",
        session_name="ccv_dryrun_illumina_snv_alignstats",
        dy_command="dy-r all -j 150 -p -k -T 1 -n",
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
                SimpleNamespace(git_tag="10.0.0"),
                SimpleNamespace(git_tag="9.0.1"),
            ]
        )

    compact = render_dy_command(
        "dy-r target -j20 --jobs=30 -T1 --timestamp=2 --dry-run --printshellcmds",
        jobs=150,
        dry_run=False,
    )
    assert compact == "dy-r target -j 150 -p -k -T 1"
    assert (
        render_dy_command(
            "dy-r target -j20",
            jobs=150,
            dry_run=False,
            max_runtime_minutes=0,
        )
        == "dy-r target -j 150 -p -k -T 1"
    )
    assert build_evidence_prefix(
        evidence_s3_uri="s3://bucket/root",
        cluster="dyec800",
        dayoa_version="10.0.0",
        stamp="20260607T000000Z",
    ) == "s3://bucket/root/dyec800/command_catalog_results/10.0.0-20260607T000000Z/"
    assert (
        role_root_uri(
            mount_path="/fsx/data",
            data_root="/fsx/data/genomic_data/organism_reads_slim",
            s3_uri="s3://bucket/genomic_data/organism_reads_slim/",
        )
        == "s3://bucket/"
    )
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
            evidence_prefix_s3_uri="s3://bucket/root/dyec800/command_catalog_results/10.0.0-stamp/",
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
        evidence_prefix_s3_uri="s3://bucket/root/dyec800/command_catalog_results/10.0.0-stamp/",
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
            evidence_prefix_s3_uri="s3://bucket/root/dyec800/command_catalog_results/10.0.0-stamp/",
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
            "SLIM": (
                "s3://lsmc-dayoa-references-usw2/genomic_data/organism_reads_slim/"
                "HG003/R1.fastq.gz"
            ),
            "REFERENCE": "s3://lsmc-dayoa-references-usw2/hg38/file.fa",
            "CONTROL": "s3://lsmc-dayoa-control-data-usw2/truth.vcf.gz",
            "MIXED": "plain,s3://lsmc-dayoa-references-usw2/index",
        }
    )
    assert None not in converted
    assert converted["SLIM"] == "/fsx/data/genomic_data/organism_reads_slim/HG003/R1.fastq.gz"
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
            evidence_prefix_s3_uri="s3://bucket/root/dyec800/command_catalog_results/10.0.0-stamp/",
            profile="lsmc",
            region="us-west-2",
            cluster="dyec800",
            run_mounts={},
            stage_func=lambda _argv: 2,
        )


def test_render_phase_none_contract_and_execution_failure_paths(tmp_path: Path) -> None:
    command = SimpleNamespace(
        command_id="simple_test",
        type="prod",
        repository="daylily-omics-analysis",
        git_tag="10.0.0",
        genome="hg38",
        dy_command="dy-r help -j 1",
        no_containerized=True,
        input_contract="none",
    )
    phase = render_phase(
        command,
        phase="dryrun",
        manifests={},
        evidence_prefix_s3_uri="s3://bucket/root/dyec800/command_catalog_results/10.0.0-stamp/",
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
        command_type="prod",
        phase="dryrun",
        analysis_id="dry",
        session_name="dry",
        dy_command="dy-r all -n",
        workflow_argv=("workflow", "launch", "--analysis-id", "dry"),
        export_destination_s3_uri="s3://bucket/ubuntu/dry/",
    )
    live = RenderedPhase(
        command_id="simple_test",
        command_type="prod",
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


def test_execute_phases_batches_warmups_by_parallel(tmp_path: Path) -> None:
    launches: list[str] = []
    status_launch_counts: list[int] = []

    phases = [
        RenderedPhase(
            command_id=f"cmd{i}",
            command_type="prod",
            phase="warmup",
            analysis_id=f"warmup-{i}",
            session_name=f"warmup-{i}",
            dy_command="dy-r all --conda-create-envs-only",
            workflow_argv=("workflow", "launch", "--analysis-id", f"warmup-{i}"),
            export_destination_s3_uri=f"s3://bucket/ubuntu/warmup-{i}/",
        )
        for i in range(3)
    ]

    def launch(argv: list[str]) -> int:
        launches.append(argv[argv.index("--analysis-id") + 1])
        return 0

    def status(_metadata, _phase) -> dict[str, int]:
        status_launch_counts.append(len(launches))
        return {"exit_code": 0}

    results = execute_phases(
        phases,
        dry_run_only=True,
        parallel=2,
        launch_func=launch,
        status_func=status,
        timeout_minutes=1,
        poll_interval_seconds=1,
        output_dir=tmp_path,
    )

    assert [result.phase.analysis_id for result in results] == [
        "warmup-0",
        "warmup-1",
        "warmup-2",
    ]
    assert status_launch_counts == [2, 2, 3]
