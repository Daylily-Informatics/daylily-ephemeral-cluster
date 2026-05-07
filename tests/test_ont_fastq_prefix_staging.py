from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

import daylily_ec.stage_samples as module

ONT_FASTQ_PREFIX = "ONT_FASTQ_PREFIX"
ONT_FLOWCELL_ID = "ONT_FLOWCELL_ID"
MIN_S3_MULTIPART_PART_SIZE = 5 * 1024 * 1024


def _stage_paths() -> module.StagePaths:
    return module.StagePaths(
        remote_fsx_root="/data/staged_sample_data",
        remote_stage_name="remote_stage_test",
        remote_fsx_stage="/data/staged_sample_data/remote_stage_test",
        remote_s3_stage="s3://bucket/data/staged_sample_data/remote_stage_test",
    )


def _write_ont_fastq_manifest(
    tmp_path: Path,
    *,
    run_id: str = "ONT.run_01",
    prefix: str = "s3://bucket/ont/HG003/20260401_ONT_run.01/fastq_pass/barcode01/",
    flowcell_id: str | None = "FLO-PRO114M",
    include_flowcell_column: bool = True,
) -> Path:
    header = [
        "RUN_ID",
        "SAMPLE_ID",
        "EXPERIMENTID",
        "SAMPLE_TYPE",
        "LIB_PREP",
        "SEQ_VENDOR",
        "SEQ_PLATFORM",
        "LANE",
        "SEQBC_ID",
        ONT_FASTQ_PREFIX,
        "STAGE_DIRECTIVE",
        "DEEP_MODEL",
        "IS_POS_CTRL",
        "IS_NEG_CTRL",
        "N_X",
        "N_Y",
        "EXTERNAL_SAMPLE_ID",
    ]
    row = [
        run_id,
        "HG003",
        "3x",
        "gdna",
        "SQK-LSK114",
        "ONT",
        "PROMETHION",
        "1",
        "D0",
        prefix,
        "stage_data",
        "ONT_R104",
        "true",
        "false",
        "1",
        "1",
        "HG003",
    ]
    if include_flowcell_column:
        header.insert(10, ONT_FLOWCELL_ID)
        row.insert(10, flowcell_id or "")

    path = tmp_path / "analysis_samples.tsv"
    path.write_text("\t".join(header) + "\n" + "\t".join(row) + "\n", encoding="utf-8")
    return path


def _install_fake_ont_prefix_stager(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, str]]:
    calls: list[dict[str, str]] = []

    def fake_stage_ont_fastq_prefix(
        prefix: str,
        *,
        flowcell_id: str,
        sample_prefix: str,
        dest_fsx_dir: str,
        **_kwargs: object,
    ) -> tuple[str, list[str]]:
        calls.append(
            {
                "prefix": prefix,
                "flowcell_id": flowcell_id,
                "sample_prefix": sample_prefix,
                "dest_fsx_dir": dest_fsx_dir,
            }
        )
        staged_r1 = f"{dest_fsx_dir}/{sample_prefix}_{flowcell_id}_ONT_R1.fastq.gz"
        return staged_r1, [staged_r1]

    monkeypatch.setattr(
        module, "stage_ont_fastq_prefix", fake_stage_ont_fastq_prefix, raising=False
    )
    return calls


def _ont_fastq_manifest_row(
    *,
    prefix: str = "s3://bucket/ont/HG003/20260401_ONT_run.01/fastq_pass/barcode01/",
    flowcell_id: str = "FLO-PRO114M",
) -> module.ManifestRow:
    return module.build_manifest_row(
        {
            "RUN_ID": "ONT.run_01",
            "SAMPLE_ID": "HG003",
            "EXPERIMENTID": "3x",
            "SAMPLE_TYPE": "gdna",
            "LIB_PREP": "SQK-LSK114",
            "SEQ_VENDOR": "ONT",
            "SEQ_PLATFORM": "PROMETHION",
            "LANE": "1",
            "SEQBC_ID": "D0",
            ONT_FASTQ_PREFIX: prefix,
            ONT_FLOWCELL_ID: flowcell_id,
            "STAGE_DIRECTIVE": "stage_data",
            "DEEP_MODEL": "ONT_R104",
            "IS_POS_CTRL": "true",
            "IS_NEG_CTRL": "false",
            "N_X": "1",
            "N_Y": "1",
            "EXTERNAL_SAMPLE_ID": "HG003",
        }
    )


def _completed(args: list[str], stdout: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=args, returncode=0, stdout=stdout, stderr="")


def _fake_aws_command_for_ont_prefix(
    contents: list[dict[str, Any]],
    command_log: list[list[str]],
) -> Any:
    marker_contents = [
        {
            "Key": "ont/HG003/20260401_ONT_run.01/pod5_pass/read.pod5",
            "Size": 1024,
        },
        {
            "Key": "ont/HG003/20260401_ONT_run.01/final_summary_FLO-PRO114M.txt",
            "Size": 256,
        },
        {
            "Key": "ont/HG003/20260401_ONT_run.01/sample_sheet_20260401.csv",
            "Size": 128,
        },
        {
            "Key": "ont/HG003/20260401_ONT_run.01/sequencing_summary_FLO-PRO114M.txt",
            "Size": 128,
        },
        {
            "Key": "ont/HG003/20260401_ONT_run.01/report_FLO-PRO114M.html",
            "Size": 128,
        },
    ]
    all_contents = [*contents, *marker_contents]

    def fake_aws_command(
        args: list[str],
        *,
        aws_env: dict[str, str],
        debug: bool,
        capture_output: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        del aws_env, debug, capture_output
        command_log.append(list(args))
        if args[:2] == ["s3", "ls"]:
            stdout = "\n".join(
                f"2026-01-01 00:00:00 {entry['Size']:>10} {entry['Key']}" for entry in contents
            )
            return _completed(args, stdout=stdout)
        if args[:2] == ["s3api", "list-objects-v2"]:
            prefix = args[args.index("--prefix") + 1]
            filtered = [entry for entry in all_contents if entry["Key"].startswith(prefix)]
            return _completed(args, stdout=json.dumps({"Contents": filtered}))
        if args[:3] == [
            "s3",
            "cp",
            "s3://bucket/ont/HG003/20260401_ONT_run.01/final_summary_FLO-PRO114M.txt",
        ]:
            return _completed(
                args,
                stdout=(
                    "flow_cell_id=FLO-PRO114M\n"
                    "basecalling_enabled=1\n"
                    "fastq_files_in_final_dest=3\n"
                    "fallback_fastq_files_in_final_dest=0\n"
                    "fallback_pod5_files_in_final_dest=0\n"
                ),
            )
        if args[:2] == ["s3api", "create-multipart-upload"]:
            return _completed(args, stdout=json.dumps({"UploadId": "upload-1"}))
        if args[:2] == ["s3api", "upload-part-copy"]:
            part_number = args[args.index("--part-number") + 1]
            return _completed(
                args,
                stdout=json.dumps({"CopyPartResult": {"ETag": f"etag-{part_number}"}}),
            )
        if tuple(args[:2]) in {
            ("s3api", "complete-multipart-upload"),
            ("s3api", "abort-multipart-upload"),
            ("s3", "cp"),
            ("s3", "rm"),
        }:
            return _completed(args)
        raise AssertionError(f"Unhandled fake AWS command: {args}")

    return fake_aws_command


def _stage_prefix_with_fake_s3(
    monkeypatch: pytest.MonkeyPatch,
    *,
    contents: list[dict[str, Any]],
    flowcell_id: str,
) -> tuple[str, list[str], list[list[str]]]:
    stage_ont_fastq_prefix = getattr(module, "stage_ont_fastq_prefix")
    command_log: list[list[str]] = []
    monkeypatch.setattr(
        module, "aws_command", _fake_aws_command_for_ont_prefix(contents, command_log)
    )
    sample_prefix = "20260401-ONT-run-01_HG003-PROMETHION-SQK-LSK114-gdna-3x_D0_0"
    staged_r1, created = stage_ont_fastq_prefix(
        "s3://bucket/ont/HG003/20260401_ONT_run.01/fastq_pass/barcode01/",
        flowcell_id=flowcell_id,
        sample_prefix=sample_prefix,
        dest_fsx_dir=f"/data/staged_sample_data/remote_stage_test/{sample_prefix}",
        dest_s3_dir=f"s3://bucket/data/staged_sample_data/remote_stage_test/{sample_prefix}",
        reference_bucket="s3://bucket",
        aws_env={},
        debug=False,
    )
    return staged_r1, created, command_log


def test_ont_fastq_prefix_fields_are_public_manifest_fields() -> None:
    assert getattr(module, "ONT_FASTQ_PREFIX") == ONT_FASTQ_PREFIX
    assert getattr(module, "ONT_FLOWCELL_ID") == ONT_FLOWCELL_ID
    assert ONT_FASTQ_PREFIX in module.ALLOWED_MANIFEST_FIELDS
    assert ONT_FLOWCELL_ID in module.ALLOWED_MANIFEST_FIELDS


def test_process_samples_emits_r1_only_ont_prefix_row_and_sanitizes_run_id(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    analysis_samples = _write_ont_fastq_manifest(tmp_path)
    stage_calls = _install_fake_ont_prefix_stager(monkeypatch)

    def fake_resolve_plan(
        prefix: str,
        *,
        flowcell_id: str,
        **_kwargs: object,
    ) -> module.OntFastqPrefixPlan:
        normalized_prefix, tag, run_id, _run_output_prefix = module.parse_ont_fastq_prefix(prefix)
        shard = module.OntFastqShard(
            uri=f"{normalized_prefix}{flowcell_id}_pass_{tag}_proto_acq_0.fastq.gz",
            key=f"prefix/{flowcell_id}_pass_{tag}_proto_acq_0.fastq.gz",
            size=1024,
            filename=f"{flowcell_id}_pass_{tag}_proto_acq_0.fastq.gz",
            flowcell_id=flowcell_id,
            run_id=run_id,
            tag=tag,
            shard_index=0,
            gzip_compressed=True,
        )
        return module.OntFastqPrefixPlan(
            prefix=normalized_prefix,
            tag=tag,
            flowcell_id=flowcell_id,
            run_id=run_id,
            shards=(shard,),
            gzip_compressed=True,
        )

    monkeypatch.setattr(
        module,
        "resolve_ont_fastq_prefix_plan",
        fake_resolve_plan,
    )
    monkeypatch.setattr(module, "check_source_path", lambda *args, **kwargs: None)
    monkeypatch.setattr(module, "stage_concordance", lambda source, *args, **kwargs: source)

    samples_rows, units_rows, created_files, run_ids = module.process_samples(
        analysis_samples,
        _stage_paths(),
        reference_bucket="s3://bucket",
        aws_env={},
        debug=False,
    )

    assert run_ids == ["20260401-ONT-run-01"]
    assert len(samples_rows) == 1
    assert len(units_rows) == 1
    assert len(stage_calls) == 1
    assert (
        stage_calls[0]["prefix"]
        == "s3://bucket/ont/HG003/20260401_ONT_run.01/fastq_pass/barcode01/"
    )
    assert stage_calls[0]["flowcell_id"] == "FLO-PRO114M"
    assert stage_calls[0]["sample_prefix"].startswith("20260401-ONT-run-01_")
    assert "20260401_ONT_run.01" not in stage_calls[0]["sample_prefix"]
    assert "20260401-ONT-run.01" not in stage_calls[0]["sample_prefix"]

    units_row = units_rows[0]
    assert units_row["RUNID"] == "20260401-ONT-run-01"
    assert units_row["SEQ_VENDOR"] == "ONT"
    assert units_row["SEQ_PLATFORM"] == "PROMETHION"
    assert units_row["ONT_R1_PATH"] == created_files[0]
    assert units_row["ONT_R1_PATH"].endswith("_FLO-PRO114M_ONT_R1.fastq.gz")
    assert units_row["ONT_R2_PATH"] == "na"
    assert units_row["ILMN_R1_PATH"] == ""
    assert units_row["ILMN_R2_PATH"] == ""


def test_stage_ont_fastq_prefix_orders_numeric_shards_before_concatenation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    large = MIN_S3_MULTIPART_PART_SIZE + 1024
    contents = [
        {
            "Key": "ont/HG003/20260401_ONT_run.01/fastq_pass/barcode01/"
            "FLO-PRO114M_pass_barcode01_proto_acq_2.fastq.gz",
            "Size": large,
        },
        {
            "Key": "ont/HG003/20260401_ONT_run.01/fastq_pass/barcode01/"
            "FLO-PRO114M_pass_barcode01_proto_acq_0.fastq.gz",
            "Size": large,
        },
        {
            "Key": "ont/HG003/20260401_ONT_run.01/fastq_pass/barcode01/"
            "FLO-PRO114M_pass_barcode01_proto_acq_1.fastq.gz",
            "Size": large,
        },
    ]
    staged_r1, created, command_log = _stage_prefix_with_fake_s3(
        monkeypatch,
        contents=contents,
        flowcell_id="FLO-PRO114M",
    )

    copy_sources = [
        command[command.index("--copy-source") + 1]
        for command in command_log
        if command[:2] == ["s3api", "upload-part-copy"]
    ]
    assert copy_sources == [
        "bucket/ont/HG003/20260401_ONT_run.01/fastq_pass/barcode01/"
        "FLO-PRO114M_pass_barcode01_proto_acq_0.fastq.gz",
        "bucket/ont/HG003/20260401_ONT_run.01/fastq_pass/barcode01/"
        "FLO-PRO114M_pass_barcode01_proto_acq_1.fastq.gz",
        "bucket/ont/HG003/20260401_ONT_run.01/fastq_pass/barcode01/"
        "FLO-PRO114M_pass_barcode01_proto_acq_2.fastq.gz",
    ]
    assert staged_r1.endswith(".fastq.gz")
    assert created == [staged_r1]


def test_stage_ont_fastq_prefix_bundles_small_shards_before_multipart_copy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    contents = [
        {
            "Key": "ont/HG003/20260401_ONT_run.01/fastq_pass/barcode01/"
            "FLO-PRO114M_pass_barcode01_proto_acq_0.fastq.gz",
            "Size": 1024,
        },
        {
            "Key": "ont/HG003/20260401_ONT_run.01/fastq_pass/barcode01/"
            "FLO-PRO114M_pass_barcode01_proto_acq_1.fastq.gz",
            "Size": 1024,
        },
        {
            "Key": "ont/HG003/20260401_ONT_run.01/fastq_pass/barcode01/"
            "FLO-PRO114M_pass_barcode01_proto_acq_2.fastq.gz",
            "Size": 1024,
        },
    ]
    monkeypatch.setattr(
        module,
        "_write_bundle_file",
        lambda _sources, bundle_path, **_kwargs: Path(bundle_path).write_bytes(b"bundle"),
    )
    _staged_r1, _created, command_log = _stage_prefix_with_fake_s3(
        monkeypatch,
        contents=contents,
        flowcell_id="FLO-PRO114M",
    )

    original_copy_sources = {
        "bucket/ont/HG003/20260401_ONT_run.01/fastq_pass/barcode01/"
        "FLO-PRO114M_pass_barcode01_proto_acq_0.fastq.gz",
        "bucket/ont/HG003/20260401_ONT_run.01/fastq_pass/barcode01/"
        "FLO-PRO114M_pass_barcode01_proto_acq_1.fastq.gz",
        "bucket/ont/HG003/20260401_ONT_run.01/fastq_pass/barcode01/"
        "FLO-PRO114M_pass_barcode01_proto_acq_2.fastq.gz",
    }
    multipart_copy_sources = {
        command[command.index("--copy-source") + 1]
        for command in command_log
        if command[:2] == ["s3api", "upload-part-copy"]
    }
    assert multipart_copy_sources.isdisjoint(original_copy_sources)
    assert any(
        command[:2] == ["s3", "cp"] and "bundle" in " ".join(command).lower()
        for command in command_log
    )


def test_stage_ont_fastq_prefix_rejects_mixed_flowcells_without_ont_flowcell_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    contents = [
        {
            "Key": "ont/HG003/20260401_ONT_run.01/fastq_pass/barcode01/"
            "FLO-PRO114M_pass_barcode01_proto_acq_0.fastq.gz",
            "Size": 1024,
        },
        {
            "Key": "ont/HG003/20260401_ONT_run.01/fastq_pass/barcode01/"
            "FLO-PRO114N_pass_barcode01_proto_acq_0.fastq.gz",
            "Size": 1024,
        },
    ]
    with pytest.raises(module.CommandError, match="ONT_FLOWCELL_ID"):
        _stage_prefix_with_fake_s3(monkeypatch, contents=contents, flowcell_id="")


def test_stage_ont_fastq_prefix_rejects_corrupt_or_incomplete_prefix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    contents = [
        {
            "Key": "ont/HG003/20260401_ONT_run.01/fastq_pass/barcode01/"
            "FLO-PRO114M_pass_barcode01_proto_acq_0.fastq.gz",
            "Size": 0,
        },
        {
            "Key": "ont/HG003/20260401_ONT_run.01/fastq_pass/barcode01/"
            "FLO-PRO114M_pass_barcode01_proto_acq_1.fastq.gz.incomplete",
            "Size": 1024,
        },
    ]
    with pytest.raises(module.CommandError, match="corrupt|incomplete|ONT_FASTQ_PREFIX"):
        _stage_prefix_with_fake_s3(
            monkeypatch,
            contents=contents,
            flowcell_id="FLO-PRO114M",
        )
