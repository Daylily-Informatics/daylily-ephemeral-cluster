"""Behavioral branch coverage for sample staging primitives.

These tests deliberately exercise validation and recovery behavior that is hard to
reach through the happy-path staging examples without making AWS calls.
"""

from __future__ import annotations

import io
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

import daylily_ec.stage_samples as m


def _completed(stdout: str = "", *, returncode: int = 0, stderr: str = ""):
    return subprocess.CompletedProcess([], returncode, stdout, stderr)


@pytest.mark.parametrize(
    ("value", "message"),
    [
        (None, "AWS profile is required"),
        ("", "AWS profile is required"),
    ],
)
def test_profile_validation_rejects_missing_values(value, message):
    with pytest.raises(m.CommandError, match=message):
        m.ensure_profile(value)
    assert m.ensure_profile("lsmc") == "lsmc"


@pytest.mark.parametrize(
    "value",
    [
        "https://bucket/key",
        "/data",
        "/data/run",
        "/fsx/data",
        "/fsx/data/run",
        "/fsx/staging",
        "/fsx/staging/other",
        "/tmp/staging",
    ],
)
def test_stage_target_and_s3_validation_fail_closed(value):
    if value.startswith("http"):
        with pytest.raises(m.CommandError, match="Expected an s3:// URI"):
            m.parse_s3_uri(value)
    else:
        with pytest.raises(m.CommandError):
            m.normalise_stage_target(value)


def test_stage_path_building_and_role_mapping(monkeypatch):
    class FixedDateTime:
        @staticmethod
        def utcnow():
            return SimpleNamespace(strftime=lambda _fmt: "20260716T040000Z")

    monkeypatch.setattr(m.dt, "datetime", FixedDateTime)
    monkeypatch.setattr(m.uuid, "uuid4", lambda: SimpleNamespace(hex="12345678abcdef"))
    stage = m.build_stage_paths(m.ACTIVE_EXTERNAL_STAGE_ROOT, "s3://bucket/prefix/")
    assert stage.remote_stage_name == "remote_stage_20260716T040000Z_12345678"
    assert stage.remote_s3_stage.endswith(stage.remote_stage_name)

    roles = m.S3RoleUris(
        reference_s3_uri="s3://ref/root",
        control_data_s3_uri="s3://control/root",
        stage_s3_uri="s3://stage/root",
        fsx_s3_uri_maps=(("/fsx/custom", "s3://custom/root"),),
    )
    assert m.build_reference_uri("/fsx/custom/a", roles) == "s3://custom/root/a"
    assert m.build_reference_uri("/fsx/references/a", roles) == "s3://ref/root/a"
    assert m.build_reference_uri("/fsx/control_data/a", roles) == "s3://control/root/a"
    assert m.build_reference_uri(f"{m.ACTIVE_EXTERNAL_STAGE_ROOT}/a", roles) == "s3://stage/root/a"
    for path in ("/data/a", "/fsx/runtime_assets/a", "/fsx/run_dir_mounts/x/a", "/tmp/a"):
        with pytest.raises(m.CommandError):
            m.build_reference_uri(path, roles)


@pytest.mark.parametrize(
    "raw",
    ["missing-equals", "relative=s3://bucket/x", "/fsx/x=https://bucket/x"],
)
def test_fsx_s3_mapping_rejects_malformed_entries(raw):
    with pytest.raises(m.CommandError):
        m.parse_fsx_s3_uri_maps([raw])


def test_fsx_s3_mapping_prefers_most_specific_prefix():
    mappings = m.parse_fsx_s3_uri_maps(["/fsx/a=s3://one/root", "/fsx/a/b=s3://two/root/"])
    assert mappings[0][0] == "/fsx/a/b"


@pytest.mark.parametrize("value", ["", ".", "..", "bad/name", "bad name"])
def test_mount_id_rejects_unsafe_components(value):
    with pytest.raises(m.CommandError):
        m.validate_mount_id(value)


@pytest.mark.parametrize(
    "path",
    [
        "/tmp/mount/a",
        "/fsx/run_dir_mounts",
        "/fsx/run_dir_mounts/a/../file",
        "/fsx/run_dir_mounts/a//file",
    ],
)
def test_mounted_path_parser_rejects_escape_and_incomplete_paths(path):
    with pytest.raises(m.CommandError):
        m.parse_mounted_run_dir_path(path, field="SOURCE")


def test_mounted_source_and_root_enforce_identity_and_shape():
    with pytest.raises(m.CommandError, match="uses mount ID"):
        m.require_mounted_source_path(
            "/fsx/run_dir_mounts/other/file", field="SOURCE", expected_mount_id="wanted"
        )
    with pytest.raises(m.CommandError, match="must name a file"):
        m.require_mounted_source_path(
            "/fsx/run_dir_mounts/wanted", field="SOURCE", expected_mount_id="wanted"
        )
    with pytest.raises(m.CommandError, match="uses mount ID"):
        m.require_mounted_root_path("/fsx/run_dir_mounts/other", expected_mount_id="wanted")
    with pytest.raises(m.CommandError, match="must be the mount root"):
        m.require_mounted_root_path("/fsx/run_dir_mounts/wanted/file", expected_mount_id="wanted")


def test_create_staged_prefix_mount_validates_and_wraps_mount_errors(monkeypatch):
    stage = m.StagePaths(
        "/fsx/staging/external", "stage", "/fsx/staging/external/stage", "s3://b/stage"
    )
    assert (
        m.create_staged_prefix_mount(
            stage,
            cluster_name=None,
            fsx_file_system_id=None,
            profile="lsmc",
            region=None,
            timeout_seconds=1,
        )
        is None
    )
    with pytest.raises(m.CommandError, match="region"):
        m.create_staged_prefix_mount(
            stage,
            cluster_name="c",
            fsx_file_system_id=None,
            profile="lsmc",
            region=None,
            timeout_seconds=1,
        )
    with pytest.raises(m.CommandError, match="positive"):
        m.create_staged_prefix_mount(
            stage,
            cluster_name="c",
            fsx_file_system_id=None,
            profile="lsmc",
            region="us-west-2",
            timeout_seconds=0,
        )

    from daylily_ec import run_mounts

    monkeypatch.setattr(run_mounts, "create_run_mount", lambda request: request)
    request = m.create_staged_prefix_mount(
        stage,
        cluster_name="c",
        fsx_file_system_id=None,
        profile="lsmc",
        region="us-west-2",
        timeout_seconds=60,
    )
    assert request.mount_id == "stage"
    assert request.read_only is True

    def fail(_request):
        raise run_mounts.RunMountError("boom")

    monkeypatch.setattr(run_mounts, "create_run_mount", fail)
    with pytest.raises(m.CommandError, match="Unable to create"):
        m.create_staged_prefix_mount(
            stage,
            cluster_name="c",
            fsx_file_system_id=None,
            profile="lsmc",
            region="us-west-2",
            timeout_seconds=60,
        )


def test_aws_environment_and_command_wrappers(monkeypatch, capsys):
    env = m.build_aws_env(m.AwsConfig(profile="lsmc", region="us-west-2"))
    assert env["AWS_PROFILE"] == "lsmc"
    assert env["AWS_REGION"] == "us-west-2"

    calls = []
    monkeypatch.setattr(
        m,
        "run_command",
        lambda command, **kwargs: calls.append((command, kwargs)) or _completed("ok"),
    )
    assert m.aws_command(["sts", "get-caller-identity"], aws_env=env, debug=True).stdout == "ok"
    assert "[DEBUG] aws sts get-caller-identity" in capsys.readouterr().out
    assert calls[0][0][0] == "aws"


class _FakePopen:
    def __init__(self, *, returncode=0, stdout=b"payload", stderr=b""):
        self.returncode = returncode
        self.stdout = io.BytesIO(stdout)
        self._stderr = stderr

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def communicate(self):
        return b"", self._stderr


def test_binary_aws_copy_streams_and_reports_failures(monkeypatch, capsys):
    monkeypatch.setattr(m.subprocess, "Popen", lambda *a, **k: _FakePopen())
    handle = io.BytesIO()
    m.aws_command_binary_to_handle(["s3", "cp", "x", "-"], handle, aws_env={}, debug=True)
    assert handle.getvalue() == b"payload"
    assert "[DEBUG]" in capsys.readouterr().out

    monkeypatch.setattr(
        m.subprocess,
        "Popen",
        lambda *a, **k: _FakePopen(returncode=2, stderr=b"denied"),
    )
    with pytest.raises(m.CommandError, match="denied"):
        m.aws_command_binary_to_handle(["s3", "cp", "x", "-"], io.BytesIO(), aws_env={})


def test_local_and_s3_source_checks_cover_all_namespaces(tmp_path, monkeypatch):
    directory = tmp_path / "directory"
    directory.mkdir()
    m.check_local_path(str(directory), allow_directory=True)
    with pytest.raises(m.CommandError, match="Local path not found"):
        m.check_local_path(str(tmp_path / "missing"))

    checked = []
    monkeypatch.setattr(m, "check_s3_path", lambda uri, **kwargs: checked.append(uri))
    roles = m.S3RoleUris(
        reference_s3_uri="s3://ref",
        control_data_s3_uri="s3://control",
        stage_s3_uri="s3://stage",
    )
    for path in (
        "s3://direct/object",
        "/fsx/references/object",
        "/fsx/control_data/object",
        f"{m.ACTIVE_EXTERNAL_STAGE_ROOT}/object",
    ):
        m.check_source_path(path, reference_s3_uri=roles, aws_env={}, debug=False)
    m.check_source_path(
        "/fsx/run_dir_mounts/run/file", reference_s3_uri=roles, aws_env={}, debug=False
    )
    m.check_source_path("/fsx/scratch/file", reference_s3_uri=roles, aws_env={}, debug=False)
    m.check_source_path("na", reference_s3_uri=roles, aws_env={}, debug=False)
    assert len(checked) == 4


def test_s3_listing_paginates_filters_and_detects_bad_truncation(monkeypatch):
    responses = iter(
        [
            {
                "Contents": [
                    {"Key": "p/file", "Size": 3},
                    {"Key": "p/dir/", "Size": 0},
                    "bad",
                ],
                "IsTruncated": True,
                "NextContinuationToken": "next",
            },
            {"Contents": [{"Key": "p/second", "Size": "4"}], "IsTruncated": False},
        ]
    )
    monkeypatch.setattr(
        m,
        "aws_command",
        lambda *a, **k: _completed(json.dumps(next(responses))),
    )
    objects = m.list_s3_objects("s3://bucket/p", aws_env={}, debug=False)
    assert [obj.size for obj in objects] == [3, 4]

    monkeypatch.setattr(
        m,
        "aws_command",
        lambda *a, **k: _completed(json.dumps({"IsTruncated": True})),
    )
    with pytest.raises(m.CommandError, match="without a continuation token"):
        m.list_s3_objects("s3://bucket/p", aws_env={}, debug=False)


def test_s3_access_and_read_helpers(monkeypatch):
    monkeypatch.setattr(m, "aws_command", lambda *a, **k: _completed(""))
    with pytest.raises(m.CommandError, match="not accessible"):
        m.check_s3_path("s3://b/missing", aws_env={}, debug=False)
    monkeypatch.setattr(m, "aws_command", lambda *a, **k: _completed("text"))
    assert m.read_s3_text("s3://b/key", aws_env={}, debug=False) == "text"


def test_remote_write_probe_always_deletes_local_temp(monkeypatch):
    commands = []
    monkeypatch.setattr(m, "aws_command", lambda args, **kwargs: commands.append(args))
    stage = m.StagePaths("/fsx/staging/external", "x", "/fsx/staging/external/x", "s3://b/x")
    m.ensure_remote_stage_writable(stage, aws_env={}, debug=False)
    assert commands[0][1] == "cp"
    assert commands[1] == ["s3", "rm", "s3://b/x/_write_test.txt"]
    assert not Path(commands[0][2]).exists()


@pytest.mark.parametrize(
    ("value", "expected"),
    [("0.5", "0.5"), ("0", "na"), ("1", "na"), ("bad", "na"), ("", "na")],
)
def test_subsample_normalization(value, expected):
    assert m.validate_subsample_pct(value) == expected


def test_identifier_vendor_and_sex_normalization():
    assert m.safe_int("bad", 7) == 7
    assert m.determine_sex(2, 0) == "female"
    assert m.determine_sex(1, 1) == "male"
    assert m.determine_sex(0, 0) == "na"
    assert m.canonical_manifest_seq_vendor("CG/MGI") == "CG"
    assert m.canonical_manifest_seq_vendor("complete_genomics") == "CG"
    with pytest.raises(m.CommandError, match="path separators"):
        m.normalise_identifier("sample/bad")


@pytest.mark.parametrize(
    "value",
    ["", "run/platform/file", "run:plat/form:file", "run:platform:"],
)
def test_run_metric_spec_validation(value):
    with pytest.raises(m.CommandError):
        m.parse_run_metric_staging_spec(value)


def test_run_metric_resolution_and_precheck(tmp_path, monkeypatch):
    fofn = tmp_path / "metrics.fofn"
    metric = tmp_path / "metric.txt"
    metric.write_text("x", encoding="utf-8")
    fofn.write_text("metric.txt\n", encoding="utf-8")
    spec = m.parse_run_metric_staging_spec(f"run1:ILLUMINA:{fofn}")
    monkeypatch.setattr(m, "check_source_path", lambda *a, **k: None)
    files = m.precheck_run_metrics([spec], reference_s3_uri="s3://ref", aws_env={}, debug=False)
    assert len(files) == 1
    assert files[0].destination_relative_path == "metric.txt"
    assert "files checked=1" in m.format_run_metric_precheck_success([spec], files)


@pytest.mark.parametrize(
    ("r1", "r2", "require_r2"),
    [
        ("r1.fastq", "", True),
        ("", "r2.fastq", True),
        ("", "r2.fastq", False),
        ("a,b", "c", True),
    ],
)
def test_paired_fastq_lists_reject_incomplete_or_unbalanced_inputs(r1, r2, require_r2):
    with pytest.raises(m.CommandError):
        m.paired_fastq_path_lists(
            r1,
            r2,
            r1_field="R1",
            r2_field="R2",
            row_number=2,
            require_r2=require_r2,
        )


def test_fastq_pair_order_requires_matching_mate_tokens():
    with pytest.raises(m.CommandError, match="Cannot identify"):
        m.validate_fastq_pair_order(
            ["sample.fastq.gz"], ["sample_R2.fastq.gz"], row_number=2, r1_field="R1", r2_field="R2"
        )
    with pytest.raises(m.CommandError, match="out of order"):
        m.validate_fastq_pair_order(
            ["a_R1.fastq.gz"], ["b_R2.fastq.gz"], row_number=2, r1_field="R1", r2_field="R2"
        )


def test_manifest_aliases_directives_and_concordance_conflicts():
    legacy, canonical = next(iter(m.LEGACY_SOURCE_ALIASES.items()))
    with pytest.raises(m.CommandError, match="sets both"):
        m.normalize_manifest_row({legacy: "a", canonical: "b"}, row_number=2)
    assert m.normalize_stage_directive("NA") == ""
    with pytest.raises(m.CommandError, match="Unsupported"):
        m.normalize_stage_directive("copy_magic")
    with pytest.raises(m.CommandError, match="must agree"):
        m.resolve_concordance_source({m.PATH_TO_CONCORDANCE: "/a", m.TRUTH_DATA_DIR: "/b"})


def test_mounted_readonly_source_collection_keeps_malformed_value():
    paths = m.mounted_readonly_source_paths({m.ILMN_R1_FQ: "a,,b"})
    assert paths == [(m.ILMN_R1_FQ, "a,,b")]


def test_collect_manifest_issues_aggregates_independent_failures(monkeypatch):
    row = {
        m.SAMPLE_ID: "sample",
        m.RUN_ID: "run",
        m.SEQ_VENDOR: "ILLUMINA",
        m.STAGE_DIRECTIVE: "pass_through",
        m.ONT_FASTQ_PREFIX: "not-s3",
        m.ONT_R1_FQ: "/fsx/scratch/a_R1.fastq.gz",
        m.ONT_R2_FQ: "/tmp/a_R2.fastq.gz",
        m.ULTIMA_CRAM: "/tmp/u.cram",
        m.ULTIMA_CRAM_ALIGNER: "bad",
        m.ONT_CRAM: "/tmp/o.cram",
        m.ONT_CRAM_ALIGNER: "bad",
        m.PB_BAM: "/tmp/p.bam",
        m.PB_BAM_ALIGNER: "bad",
        m.ONT_BAM: "/tmp/o.bam",
        m.ONT_BAM_ALIGNER: "bad",
        m.ROCHE_BAM: "/tmp/r.bam",
        m.ROCHE_BAM_ALIGNER: "bad",
    }

    def missing(path, **_kwargs):
        raise m.CommandError(f"missing {path}")

    monkeypatch.setattr(m, "check_source_path", missing)
    issues = m.collect_manifest_row_issues(
        row,
        row_number=2,
        reference_s3_uri="s3://ref",
        aws_env={},
        debug=False,
    )
    fields = {issue.field for issue in issues}
    assert m.ONT_FASTQ_PREFIX in fields
    assert m.ULTIMA_CRAM_ALIGNER in fields
    assert m.ONT_CRAM_ALIGNER in fields
    assert m.PB_BAM_ALIGNER in fields
    assert m.ONT_BAM_ALIGNER in fields
    assert m.ROCHE_BAM_ALIGNER in fields
    assert len(issues) >= 15


def test_giab_precheck_reports_identity_directory_and_truth_failures(monkeypatch):
    base = {
        m.SAMPLE_ID: "sample",
        m.RUN_ID: "run",
        m.IS_POS_CTRL: "true",
        m.PATH_TO_CONCORDANCE: "/controls/giab/HG002",
    }
    issues, checked = m._precheck_giab_truth_files(
        base,
        row_number=2,
        concordance_source=base[m.PATH_TO_CONCORDANCE],
        reference_s3_uri="s3://ref",
        aws_env={},
        debug=False,
    )
    assert checked == 0
    assert issues[0].field == m.EXTERNAL_SAMPLE_ID

    row = {**base, m.EXTERNAL_SAMPLE_ID: "HG002"}
    monkeypatch.setattr(m, "detect_giab_roi_dirs", lambda *a, **k: ["roi-a", "roi-b"])
    monkeypatch.setattr(
        m,
        "check_source_path",
        lambda path, **kwargs: (_ for _ in ()).throw(m.CommandError(path)),
    )
    issues, checked = m._precheck_giab_truth_files(
        row,
        row_number=2,
        concordance_source=row[m.PATH_TO_CONCORDANCE],
        reference_s3_uri="s3://ref",
        aws_env={},
        debug=False,
    )
    assert len(issues) == 2
    assert checked == 2 * len(m.GIAB_TRUTH_SUFFIXES)


def test_detect_giab_roi_dirs_handles_local_and_s3_sources(tmp_path, monkeypatch):
    (tmp_path / "roi-b").mkdir()
    (tmp_path / "roi-a").mkdir()
    (tmp_path / "file").write_text("x", encoding="utf-8")
    assert m.detect_giab_roi_dirs(
        str(tmp_path), reference_s3_uri="s3://ref", aws_env={}, debug=False
    ) == ["roi-a", "roi-b"]
    monkeypatch.setattr(m, "_s3_child_directories", lambda *a, **k: ["remote"])
    assert m.detect_giab_roi_dirs(
        "s3://bucket/base", reference_s3_uri="s3://ref", aws_env={}, debug=False
    ) == ["remote"]
    assert (
        m.detect_giab_roi_dirs(
            "/fsx/run_dir_mounts/run/controls", reference_s3_uri="s3://ref", aws_env={}, debug=False
        )
        == []
    )


def test_format_precheck_failure_sorts_and_describes_issues():
    report = m.PrecheckReport(
        rows_checked=2,
        samples_checked=1,
        source_objects_checked=3,
        concordance_dirs_checked=1,
        issues=(
            m.PrecheckIssue(3, "s2", "r2", "B", "/b", "second"),
            m.PrecheckIssue(2, "s1", "r1", "A", "", "first"),
        ),
    )
    text = m.format_precheck_failure(report)
    assert text.startswith("Precheck failed")
    assert text.index("row 2") < text.index("row 3")


def _shard(index: int, *, size: int = 8, gzip: bool = True) -> m.OntFastqShard:
    suffix = ".fastq.gz" if gzip else ".fastq"
    name = f"FC_pass_tag_proto_acq_{index}{suffix}"
    return m.OntFastqShard(
        uri=f"s3://bucket/{name}",
        key=name,
        size=size,
        filename=name,
        flowcell_id="FC",
        run_id="run",
        tag="tag",
        shard_index=index,
        gzip_compressed=gzip,
    )


def test_copy_cleanup_and_source_resolution(monkeypatch, tmp_path):
    commands = []
    monkeypatch.setattr(m, "aws_command", lambda args, **kwargs: commands.append(args))
    m.aws_copy("local", "s3://b/d", aws_env={}, debug=False, recursive=True)
    assert commands[-1][-1] == "--recursive"

    def sometimes_fail(args, **kwargs):
        commands.append(args)
        raise m.CommandError("already gone")

    monkeypatch.setattr(m, "aws_command", sometimes_fail)
    m.cleanup_s3_objects(["s3://b/a", "s3://b/b"], aws_env={}, debug=False)

    assert m.source_copy_reference("s3://b/key", reference_s3_uri="s3://ref") == "s3://b/key"
    assert m.source_copy_reference(
        "/fsx/run_dir_mounts/run/file", reference_s3_uri="s3://ref"
    ).endswith("/file")
    assert (
        m.source_copy_reference("/fsx/references/file", reference_s3_uri="s3://ref")
        == "s3://ref/file"
    )
    local = tmp_path / "local"
    assert m.source_copy_reference(str(local), reference_s3_uri="s3://ref") == str(local)
    with pytest.raises(m.CommandError, match="Scratch source"):
        m.source_copy_reference("/fsx/scratch/file", reference_s3_uri="s3://ref")


def test_ont_parsing_rejects_bad_prefix_and_shards():
    for prefix in ("s3://b/no-fastq/tag", "s3://b/run/fastq_pass/tag"):
        with pytest.raises(m.CommandError):
            m.parse_ont_fastq_prefix(prefix)
    with pytest.raises(m.CommandError, match="not FASTQ"):
        m._strip_fastq_suffix("read.txt")
    with pytest.raises(m.CommandError, match="Could not parse"):
        m.parse_ont_fastq_shard(
            m.S3ObjectSummary("s3://b/bad.fastq.gz", "bad.fastq.gz", 1),
            expected_tag="tag",
            run_id="run",
        )
    with pytest.raises(m.CommandError, match="not prefix tag"):
        m.parse_ont_fastq_shard(
            m.S3ObjectSummary(
                "s3://b/FC_pass_barcode02_proto_acq_0.fastq.gz",
                "FC_pass_barcode02_proto_acq_0.fastq.gz",
                1,
            ),
            expected_tag="barcode01",
            run_id="run",
        )


def test_ont_run_output_validation_failure_matrix(monkeypatch):
    prefix = "s3://b/20260716_ONT_run/"

    def objects(*names):
        return [m.S3ObjectSummary(f"s3://b/{name}", name, 1) for name in names]

    cases = [
        ([], "empty"),
        (objects("pod5_pass/x.pod5"), "missing fastq_pass"),
        (objects("fastq_pass/x.fastq.gz"), "missing pod5_pass"),
        (objects("fastq_pass/x.fastq.gz", "pod5_pass/x.pod5"), "missing final_summary"),
        (
            objects(
                "fastq_pass/x.fastq.gz",
                "pod5_pass/x.pod5",
                "final_summary_OTHER.txt",
                "sample_sheet_x.csv",
                "sequencing_summary_x.txt",
                "report_x.html",
            ),
            "no final summary for flowcell",
        ),
    ]
    for payload, message in cases:
        monkeypatch.setattr(m, "list_s3_objects", lambda *a, payload=payload, **k: payload)
        with pytest.raises(m.CommandError, match=message):
            m.validate_ont_run_output(prefix, flowcell_id="FC", aws_env={}, debug=False)

    complete = objects(
        "fastq_pass/FC_read.fastq.gz",
        "pod5_pass/FC_read.pod5",
        "final_summary_FC.txt",
        "sample_sheet_x.csv",
        "sequencing_summary_x.txt",
        "report_x.html",
    )
    monkeypatch.setattr(m, "list_s3_objects", lambda *a, **k: complete)
    summaries = [
        "flow_cell_id=OTHER\nbasecalling_enabled=1\nfastq_files_in_final_dest=1",
        "flow_cell_id=FC\nbasecalling_enabled=0\nfastq_files_in_final_dest=1",
        "flow_cell_id=FC\nbasecalling_enabled=1\nfastq_files_in_final_dest=0",
        "flow_cell_id=FC\nbasecalling_enabled=1\nfastq_files_in_final_dest=2",
        (
            "flow_cell_id=FC\nbasecalling_enabled=1\nfastq_files_in_final_dest=1\n"
            "pod5_files_in_final_dest=2"
        ),
        (
            "flow_cell_id=FC\nbasecalling_enabled=1\nfastq_files_in_final_dest=1\n"
            "pod5_files_in_final_dest=1\nfallback_fastq_files_in_final_dest=1"
        ),
    ]
    for summary in summaries:
        monkeypatch.setattr(m, "read_s3_text", lambda *a, summary=summary, **k: summary)
        with pytest.raises(m.CommandError):
            m.validate_ont_run_output(prefix, flowcell_id="FC", aws_env={}, debug=False)


def test_ensure_s3_objects_resolves_remote_visible_and_local(monkeypatch, tmp_path):
    local = tmp_path / "reads.fastq.gz"
    local.write_text("reads", encoding="utf-8")
    copies = []
    monkeypatch.setattr(m.uuid, "uuid4", lambda: SimpleNamespace(hex="uuid"))
    monkeypatch.setattr(m, "aws_copy", lambda *a, **k: copies.append(a))
    resolved, uploaded = m.ensure_s3_objects(
        ["s3://b/existing", "/fsx/references/ref.fastq.gz", str(local)],
        dest_s3_dir="s3://dest/sample",
        sample_prefix="sample",
        reference_s3_uri="s3://ref",
        aws_env={},
        debug=False,
    )
    assert resolved[:2] == ["s3://b/existing", "s3://ref/ref.fastq.gz"]
    assert uploaded == [resolved[2]]
    assert copies

    cleaned = []

    def fail_copy(*_a, **_k):
        raise RuntimeError("upload failed")

    monkeypatch.setattr(m, "aws_copy", fail_copy)
    monkeypatch.setattr(m, "cleanup_s3_objects", lambda uris, **k: cleaned.extend(uris))
    with pytest.raises(RuntimeError, match="upload failed"):
        m.ensure_s3_objects(
            [str(local)],
            dest_s3_dir="s3://dest/sample",
            sample_prefix="sample",
            reference_s3_uri="s3://ref",
            aws_env={},
            debug=False,
        )
    assert cleaned == []  # the failed object is not recorded as uploaded


def test_multipart_copy_success_and_abort_recovery(monkeypatch):
    calls = []

    def success(args, **kwargs):
        calls.append(args)
        if "create-multipart-upload" in args:
            return _completed('{"UploadId":"u"}')
        if "upload-part-copy" in args:
            return _completed('{"CopyPartResult":{"ETag":"etag"}}')
        return _completed()

    monkeypatch.setattr(m, "aws_command", success)
    m.multipart_concatenate(["s3://b/a", "s3://b/b"], "s3://b/out", aws_env={}, debug=False)
    assert any("complete-multipart-upload" in call for call in calls)

    with pytest.raises(m.CommandError, match="No sources"):
        m.multipart_concatenate([], "s3://b/out", aws_env={}, debug=False)

    monkeypatch.setattr(m, "aws_command", lambda *a, **k: _completed("{}"))
    with pytest.raises(m.CommandError, match="initiate"):
        m.multipart_concatenate(["s3://b/a"], "s3://b/out", aws_env={}, debug=False)

    calls.clear()

    def missing_etag(args, **kwargs):
        calls.append(args)
        if "create-multipart-upload" in args:
            return _completed('{"UploadId":"u"}')
        return _completed("{}")

    monkeypatch.setattr(m, "aws_command", missing_etag)
    with pytest.raises(m.CommandError, match="Failed to copy part"):
        m.multipart_concatenate(["s3://b/a"], "s3://b/out", aws_env={}, debug=False)
    assert any("abort-multipart-upload" in call for call in calls)


def test_bundle_building_and_concat_cleanup(monkeypatch):
    monkeypatch.setattr(
        m,
        "aws_command_binary_to_handle",
        lambda args, handle, **kwargs: handle.write(b"reads"),
    )
    uploads = []
    monkeypatch.setattr(
        m, "aws_copy", lambda source, dest, **kwargs: uploads.append((source, dest))
    )
    monkeypatch.setattr(m.uuid, "uuid4", lambda: SimpleNamespace(hex="uuid"))
    bundle = m._upload_concat_bundle(
        [_shard(0), _shard(1)],
        bundle_s3_dir="s3://b/parts",
        sample_prefix="sample",
        bundle_number=1,
        suffix=".fastq.gz",
        aws_env={},
        debug=False,
    )
    assert bundle.size == 16
    assert bundle.uri.endswith("sample_ont_bundle1_uuid.fastq.gz")
    assert not Path(uploads[0][0]).exists()

    monkeypatch.setattr(
        m,
        "_upload_concat_bundle",
        lambda sources, **kwargs: m.S3ObjectSummary(
            "s3://b/bundle", "bundle", sum(s.size for s in sources)
        ),
    )
    sources, uploaded = m.build_size_aware_concat_sources(
        [_shard(0, size=1), _shard(1, size=m.S3_MULTIPART_MIN_PART_SIZE)],
        bundle_s3_dir="s3://b/parts",
        sample_prefix="sample",
        suffix=".fastq.gz",
        aws_env={},
        debug=False,
    )
    assert [source.uri for source in sources] == ["s3://b/bundle"]
    assert uploaded == ["s3://b/bundle"]

    plan = m.OntFastqPrefixPlan("s3://b/p", "tag", "FC", "run", (_shard(0),), True)
    uploads.clear()
    m.concatenate_ont_fastq_shards(
        plan,
        "s3://b/out",
        bundle_s3_dir="s3://b/parts",
        sample_prefix="sample",
        aws_env={},
        debug=False,
    )
    assert uploads[-1] == (plan.shards[0].uri, "s3://b/out")


def test_staging_copy_primitives(monkeypatch, tmp_path):
    copies = []
    monkeypatch.setattr(m, "aws_copy", lambda *a, **k: copies.append((a, k)))
    r1, r2 = m.stage_single_lane(
        str(tmp_path / "a_R1.fastq.gz"),
        str(tmp_path / "a_R2.fastq.gz"),
        "/fsx/stage/sample",
        "s3://stage/sample",
        reference_s3_uri="s3://ref",
        aws_env={},
        debug=False,
    )
    assert r1.endswith("a_R1.fastq.gz") and r2.endswith("a_R2.fastq.gz")
    assert len(copies) == 2

    copies.clear()
    assert (
        m.stage_concordance(
            "/fsx/references/control",
            "/fsx/dest",
            "s3://dest",
            reference_s3_uri="s3://ref",
            aws_env={},
            debug=False,
        )
        == "/fsx/references/control"
    )
    local_dir = tmp_path / "control"
    local_dir.mkdir()
    assert (
        m.stage_concordance(
            str(local_dir),
            "/fsx/dest",
            "s3://dest",
            reference_s3_uri="s3://ref",
            aws_env={},
            debug=False,
        )
        == "/fsx/dest"
    )
    assert copies[-1][1]["recursive"] is True

    path, created = m.stage_path(
        str(tmp_path / "aligned.cram"),
        dest_fsx_dir="/fsx/dest",
        dest_s3_dir="s3://dest",
        reference_s3_uri="s3://ref",
        aws_env={},
        debug=False,
    )
    assert path == "/fsx/dest/aligned.cram"
    assert created == [path]


def test_precheck_manifest_header_and_row_failures(tmp_path, monkeypatch):
    empty = tmp_path / "empty.tsv"
    empty.write_text("", encoding="utf-8")
    report, rows = m.precheck_manifest(empty, reference_s3_uri="s3://ref", aws_env={}, debug=False)
    assert rows == [] and report.issues[0].field == "header"

    unknown = tmp_path / "unknown.tsv"
    unknown.write_text("UNKNOWN\nvalue\n", encoding="utf-8")
    report, rows = m.precheck_manifest(
        unknown, reference_s3_uri="s3://ref", aws_env={}, debug=False
    )
    assert rows == []
    assert any("Unknown columns" in issue.message for issue in report.issues)
    assert any("Missing required" in issue.message for issue in report.issues)

    with pytest.raises(m.CommandError, match="Unknown columns"):
        m.load_manifest_rows(unknown, reference_s3_uri="s3://ref", aws_env={}, debug=False)


def test_main_precheck_and_config_only_control_flow(tmp_path, monkeypatch, capsys):
    manifest = tmp_path / "manifest.tsv"
    manifest.write_text("header\n", encoding="utf-8")
    stage = m.StagePaths(
        "/fsx/staging/external", "remote_stage_stamp", "/fsx/staging/external/x", "s3://stage/x"
    )
    args = SimpleNamespace(
        analysis_samples=str(manifest),
        profile="lsmc",
        region="us-west-2",
        reference_s3_uri="s3://ref",
        control_data_s3_uri="s3://control",
        stage_s3_uri="s3://stage",
        fsx_s3_uri_map=[],
        stage_target=m.ACTIVE_EXTERNAL_STAGE_ROOT,
        run_metric_staging=[],
        debug=False,
        precheck_only=True,
        config_only=False,
        config_dir=None,
        cluster_name=None,
        fsx_file_system_id=None,
        staging_mount_timeout_seconds=60,
        manifest_contract="legacy_v11",
    )
    monkeypatch.setattr(m, "parse_args", lambda argv: args)
    monkeypatch.setattr(m, "build_stage_paths", lambda *a, **k: stage)
    monkeypatch.setattr(
        m,
        "precheck_manifest",
        lambda *a, **k: (m.PrecheckReport(1, 1, 1, 0, ()), []),
    )
    monkeypatch.setattr(m, "precheck_run_metrics", lambda *a, **k: [])
    assert m.main([]) == 0
    assert "Precheck passed" in capsys.readouterr().out

    monkeypatch.setattr(
        m,
        "precheck_manifest",
        lambda *a, **k: (
            m.PrecheckReport(1, 1, 0, 0, (m.PrecheckIssue(2, "s", "r", "f", "", "bad"),)),
            [],
        ),
    )
    assert m.main([]) == 1
    assert "Precheck failed" in capsys.readouterr().err


def test_multi_lane_staging_success_and_second_mate_failure_cleanup(monkeypatch):
    ensure_calls = []

    def ensure(sources, **kwargs):
        ensure_calls.append(list(sources))
        mate = "r1" if len(ensure_calls) == 1 else "r2"
        return [f"s3://bucket/{mate}-{index}" for index, _ in enumerate(sources)], [
            f"s3://bucket/upload-{mate}"
        ]

    concatenations = []
    cleaned = []
    monkeypatch.setattr(m, "ensure_s3_objects", ensure)
    monkeypatch.setattr(
        m,
        "multipart_concatenate",
        lambda sources, destination, **kwargs: concatenations.append((sources, destination)),
    )
    monkeypatch.setattr(m, "cleanup_s3_objects", lambda uris, **kwargs: cleaned.extend(uris))
    r1, r2 = m.stage_multi_lane(
        ["a_R1.fastq.gz", "b_R1.fastq.gz"],
        ["a_R2.fastq.gz", "b_R2.fastq.gz"],
        "sample",
        "/fsx/stage/sample",
        "s3://stage/sample",
        reference_s3_uri="s3://ref",
        aws_env={},
        debug=False,
    )
    assert r1.endswith("sample_merged_R1.fastq.gz")
    assert r2.endswith("sample_merged_R2.fastq.gz")
    assert len(concatenations) == 2
    assert cleaned == ["s3://bucket/upload-r1", "s3://bucket/upload-r2"]

    calls = 0

    def fail_second(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("R2 staging failed")
        return ["s3://bucket/r1"], ["s3://bucket/r1-upload"]

    cleaned.clear()
    monkeypatch.setattr(m, "ensure_s3_objects", fail_second)
    with pytest.raises(RuntimeError, match="R2 staging failed"):
        m.stage_multi_lane(
            ["a_R1.fastq.gz"],
            ["a_R2.fastq.gz"],
            "sample",
            "/fsx/stage/sample",
            "s3://stage/sample",
            reference_s3_uri="s3://ref",
            aws_env={},
            debug=False,
        )
    assert cleaned == ["s3://bucket/r1-upload"]


def test_concat_failure_cleans_destination_and_uploaded_bundles(monkeypatch):
    shards = (_shard(0), _shard(1))
    plan = m.OntFastqPrefixPlan("s3://b/p", "tag", "FC", "run", shards, True)
    monkeypatch.setattr(
        m,
        "build_size_aware_concat_sources",
        lambda *a, **k: (
            [m.S3ObjectSummary("s3://b/a", "a", 1), m.S3ObjectSummary("s3://b/b", "b", 1)],
            ["s3://b/uploaded"],
        ),
    )
    monkeypatch.setattr(
        m,
        "multipart_concatenate",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("concat failed")),
    )
    cleaned = []
    monkeypatch.setattr(m, "cleanup_s3_objects", lambda uris, **k: cleaned.extend(uris))
    with pytest.raises(RuntimeError, match="concat failed"):
        m.concatenate_ont_fastq_shards(
            plan,
            "s3://b/out",
            bundle_s3_dir="s3://b/parts",
            sample_prefix="sample",
            aws_env={},
            debug=False,
        )
    assert cleaned == ["s3://b/out", "s3://b/uploaded"]


def test_run_metric_precheck_rejects_missing_empty_conflicting_and_duplicate(tmp_path, monkeypatch):
    missing = m.RunMetricStagingSpec("run", "ILLUMINA", tmp_path / "missing.fofn")
    with pytest.raises(m.CommandError, match="not found"):
        m.precheck_run_metrics([missing], reference_s3_uri="s3://ref", aws_env={}, debug=False)

    directory = tmp_path / "dir"
    directory.mkdir()
    with pytest.raises(m.CommandError, match="not a file"):
        m.precheck_run_metrics(
            [m.RunMetricStagingSpec("run", "ILLUMINA", directory)],
            reference_s3_uri="s3://ref",
            aws_env={},
            debug=False,
        )

    empty = tmp_path / "empty.fofn"
    empty.write_text("\n", encoding="utf-8")
    with pytest.raises(m.CommandError, match="contains no files"):
        m.precheck_run_metrics(
            [m.RunMetricStagingSpec("run", "ILLUMINA", empty)],
            reference_s3_uri="s3://ref",
            aws_env={},
            debug=False,
        )

    metric = tmp_path / "metric.txt"
    metric.write_text("x", encoding="utf-8")
    first = tmp_path / "first.fofn"
    second = tmp_path / "second.fofn"
    first.write_text("metric.txt\n", encoding="utf-8")
    second.write_text("metric.txt\n", encoding="utf-8")
    monkeypatch.setattr(m, "check_source_path", lambda *a, **k: None)
    with pytest.raises(m.CommandError, match="conflicting platforms"):
        m.precheck_run_metrics(
            [
                m.RunMetricStagingSpec("run", "ILLUMINA", first),
                m.RunMetricStagingSpec("run", "ONT", second),
            ],
            reference_s3_uri="s3://ref",
            aws_env={},
            debug=False,
        )


def test_manifest_load_header_empty_rows_and_required_columns(tmp_path):
    empty = tmp_path / "empty.tsv"
    empty.write_text("", encoding="utf-8")
    with pytest.raises(m.CommandError, match="missing a header"):
        m.load_manifest_rows(empty, reference_s3_uri="s3://ref", aws_env={}, debug=False)

    required = tmp_path / "required.tsv"
    required.write_text("RUN_ID\nvalue\n", encoding="utf-8")
    with pytest.raises(m.CommandError, match="Missing required columns"):
        m.load_manifest_rows(required, reference_s3_uri="s3://ref", aws_env={}, debug=False)


def test_manifest_mode_detection_rejects_mixed_and_empty_inputs(tmp_path):
    empty = tmp_path / "empty.tsv"
    empty.write_text("", encoding="utf-8")
    with pytest.raises(m.CommandError, match="missing a header"):
        m.detect_manifest_data_modes(empty)
    unknown = tmp_path / "unknown.tsv"
    unknown.write_text("UNKNOWN\nx\n", encoding="utf-8")
    with pytest.raises(m.CommandError, match="Unknown columns"):
        m.detect_manifest_data_modes(unknown)


def test_main_remote_success_and_config_only_rejections(tmp_path, monkeypatch, capsys):
    manifest = tmp_path / "manifest.tsv"
    manifest.write_text("header\n", encoding="utf-8")
    stage = m.StagePaths(
        "/fsx/staging/staged_external_sequencing_data",
        "remote_stage_stamp",
        "/fsx/staging/staged_external_sequencing_data/x",
        "s3://stage/x",
    )
    args = SimpleNamespace(
        analysis_samples=str(manifest),
        profile="lsmc",
        region="us-west-2",
        reference_s3_uri="s3://ref",
        control_data_s3_uri="s3://control",
        stage_s3_uri="s3://stage",
        fsx_s3_uri_map=[],
        stage_target=m.ACTIVE_EXTERNAL_STAGE_ROOT,
        run_metric_staging=[],
        debug=False,
        precheck_only=False,
        config_only=False,
        config_dir=str(tmp_path / "config"),
        cluster_name="cluster",
        fsx_file_system_id=None,
        staging_mount_timeout_seconds=60,
        manifest_contract="legacy_v11",
    )
    monkeypatch.setattr(m, "parse_args", lambda argv: args)
    monkeypatch.setattr(m, "build_stage_paths", lambda *a, **k: stage)
    monkeypatch.setattr(
        m, "precheck_manifest", lambda *a, **k: (m.PrecheckReport(1, 1, 0, 0, ()), [])
    )
    monkeypatch.setattr(m, "precheck_run_metrics", lambda *a, **k: [])
    monkeypatch.setattr(m, "ensure_remote_stage_writable", lambda *a, **k: None)
    monkeypatch.setattr(
        m, "process_samples", lambda *a, **k: ([], [], [stage.remote_fsx_stage + "/file"], [])
    )
    monkeypatch.setattr(m, "stage_run_metrics", lambda *a, **k: [])
    copies = []
    monkeypatch.setattr(m, "aws_copy", lambda *a, **k: copies.append(a))
    monkeypatch.setattr(
        m,
        "create_staged_prefix_mount",
        lambda *a, **k: SimpleNamespace(association_id="dra", lifecycle="AVAILABLE"),
    )
    assert m.main([]) == 0
    output = capsys.readouterr().out
    assert "Remote staging completed successfully" in output
    assert "Staging DRA: dra" in output
    assert len(copies) == 2

    args.config_only = True
    args.run_metric_staging = ["run:ILLUMINA:file.fofn"]
    monkeypatch.setattr(m, "parse_run_metric_staging_specs", lambda values: [object()])
    monkeypatch.setattr(m, "precheck_run_metrics", lambda *a, **k: [])
    assert m.main([]) == 1
    assert "--config-only cannot be used" in capsys.readouterr().err

    args.run_metric_staging = []
    stage_data_row = SimpleNamespace(
        row_number=2, staging=SimpleNamespace(stage_directive="stage_data")
    )
    monkeypatch.setattr(m, "parse_run_metric_staging_specs", lambda values: [])
    monkeypatch.setattr(
        m, "precheck_manifest", lambda *a, **k: (m.PrecheckReport(1, 1, 0, 0, ()), [stage_data_row])
    )
    assert m.main([]) == 1
    assert "stage_data rows" in capsys.readouterr().err


def test_main_rejects_missing_manifest(monkeypatch, tmp_path):
    args = SimpleNamespace(analysis_samples=str(tmp_path / "missing.tsv"))
    monkeypatch.setattr(m, "parse_args", lambda argv: args)
    with pytest.raises(m.CommandError, match="not found"):
        m.main([])


def test_process_samples_merges_two_illumina_lanes_once(monkeypatch, tmp_path):
    def row(lane: str, suffix: str) -> m.ManifestRow:
        return m.build_manifest_row(
            {
                m.RUN_ID: "run",
                m.SAMPLE_ID: "sample",
                m.EXPERIMENT_ID: "experiment",
                m.SAMPLE_TYPE: "germline",
                m.LIB_PREP: "pcrfree",
                m.SEQ_VENDOR: "ILLUMINA",
                m.SEQ_PLATFORM: "NOVASEQ",
                m.LANE: lane,
                m.SEQBC_ID: "barcode",
                m.ILMN_R1_FQ: f"/tmp/{suffix}_R1.fastq.gz",
                m.ILMN_R2_FQ: f"/tmp/{suffix}_R2.fastq.gz",
                m.STAGE_DIRECTIVE: "stage_data",
                m.PATH_TO_CONCORDANCE: "na",
            },
            row_number=int(lane) + 1,
        )

    rows = [row("1", "lane1"), row("2", "lane2")]
    staged = []

    def stage_multi(r1_files, r2_files, sample_prefix, dest_fsx_dir, dest_s3_dir, **kwargs):
        staged.append((r1_files, r2_files, sample_prefix, dest_fsx_dir, dest_s3_dir))
        return f"{dest_fsx_dir}/merged_R1.fastq.gz", f"{dest_fsx_dir}/merged_R2.fastq.gz"

    monkeypatch.setattr(m, "stage_multi_lane", stage_multi)
    samples, units, created, run_ids = m.process_samples(
        tmp_path / "manifest.tsv",
        m.StagePaths(
            m.ACTIVE_EXTERNAL_STAGE_ROOT,
            "stage",
            f"{m.ACTIVE_EXTERNAL_STAGE_ROOT}/stage",
            "s3://bucket/stage",
        ),
        reference_s3_uri="s3://ref",
        aws_env={},
        debug=False,
        rows=rows,
    )
    assert len(staged) == 1
    assert len(samples) == 1
    assert len(units) == 1
    assert units[0]["LANEID"] == "0"
    assert len(created) == 2
    assert run_ids == ["run"]


def test_s3_child_directory_discovery_and_root_uri_edges(monkeypatch):
    monkeypatch.setattr(
        m,
        "list_s3_objects",
        lambda *a, **k: [
            m.S3ObjectSummary("s3://b/base/roi-a/file", "base/roi-a/file", 1),
            m.S3ObjectSummary("s3://b/base/roi-b/nested/file", "base/roi-b/nested/file", 1),
            m.S3ObjectSummary("s3://b/base/root-file", "base/root-file", 1),
            m.S3ObjectSummary("s3://b/other/skip", "other/skip", 1),
        ],
    )
    assert m._s3_child_directories("s3://b/base", aws_env={}, debug=False) == [
        "roi-a",
        "roi-b",
    ]
    assert m.normalise_s3_prefix_uri("s3://bucket") == "s3://bucket/"
    assert m._role_relative("/fsx/references", "/fsx/references") == ""
    assert m._staging_relative(m.ACTIVE_EXTERNAL_STAGE_ROOT) == ""
    with pytest.raises(m.CommandError, match="Missing required S3 role bucket"):
        m._join_s3_uri("", "relative")
