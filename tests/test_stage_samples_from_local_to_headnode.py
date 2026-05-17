from __future__ import annotations

from pathlib import Path

import pytest

import daylily_ec.stage_samples as module


def _stage_paths() -> module.StagePaths:
    return module.StagePaths(
        remote_fsx_root="/data/staged_sample_data",
        remote_stage_name="remote_stage_test",
        remote_fsx_stage="/data/staged_sample_data/remote_stage_test",
        remote_s3_stage="s3://bucket/data/staged_sample_data/remote_stage_test",
    )


def _write_manifest(tmp_path: Path, header: str, rows: list[str]) -> Path:
    path = tmp_path / "analysis_samples.tsv"
    path.write_text(header + "\n" + "\n".join(rows) + "\n", encoding="utf-8")
    return path


def _prechecked_rows(
    monkeypatch: pytest.MonkeyPatch,
    analysis_samples: Path,
    *,
    reference_bucket: str = "s3://bucket",
    aws_env: dict[str, str] | None = None,
    debug: bool = False,
) -> list[module.ManifestRow]:
    monkeypatch.setattr(module, "detect_giab_roi_dirs", lambda *args, **kwargs: ["giabHC"])
    report, rows = module.precheck_manifest(
        analysis_samples,
        reference_bucket=reference_bucket,
        aws_env=aws_env or {},
        debug=debug,
    )
    assert report.issues == (), module.format_precheck_failure(report)
    return rows


def _process_samples(
    monkeypatch: pytest.MonkeyPatch,
    analysis_samples: Path,
    stage: module.StagePaths,
    *,
    reference_bucket: str = "s3://bucket",
    aws_env: dict[str, str] | None = None,
    debug: bool = False,
) -> tuple[list[dict[str, str]], list[dict[str, str]], list[str], list[str]]:
    resolved_aws_env = aws_env or {}
    rows = _prechecked_rows(
        monkeypatch,
        analysis_samples,
        reference_bucket=reference_bucket,
        aws_env=resolved_aws_env,
        debug=debug,
    )
    return module.process_samples(
        analysis_samples,
        stage,
        reference_bucket=reference_bucket,
        aws_env=resolved_aws_env,
        debug=debug,
        rows=rows,
    )


def test_headnode_visible_path_maps_data_prefix_to_fsx() -> None:
    assert module.headnode_visible_path("/data") == "/fsx/data"
    assert (
        module.headnode_visible_path("/data/staged_sample_data/remote_stage_1")
        == "/fsx/data/staged_sample_data/remote_stage_1"
    )
    assert module.is_headnode_visible_path("/fsx/run_dir_mounts/RUN123/fastqs/S1_R1.fastq.gz")
    assert module.is_headnode_visible_path("/run_dir_mounts/RUN123/fastqs/S1_R1.fastq.gz")
    assert (
        module.headnode_visible_path("/run_dir_mounts/RUN123/fastqs/S1_R1.fastq.gz")
        == "/run_dir_mounts/RUN123/fastqs/S1_R1.fastq.gz"
    )
    assert module.headnode_visible_path("/tmp/local") == "/tmp/local"


def test_normalise_samples_paths_rewrites_staged_concordance_paths() -> None:
    rows = [
        {
            "SAMPLEID": "HG003",
            "CONCORDANCE_CONTROL_PATH": "/data/staged_sample_data/run/concordance_data",
            "TRUTH_DATA_DIR": "/data/staged_sample_data/run/concordance_data",
        }
    ]

    module.normalise_samples_paths(rows)

    assert rows == [
        {
            "SAMPLEID": "HG003",
            "CONCORDANCE_CONTROL_PATH": "/fsx/data/staged_sample_data/run/concordance_data",
            "TRUTH_DATA_DIR": "/fsx/data/staged_sample_data/run/concordance_data",
        }
    ]


def test_check_source_path_accepts_mounted_paths_without_reference_translation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden_aws(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("mounted run-directory paths must not use AWS reference lookups")

    monkeypatch.setattr(module, "aws_command", forbidden_aws)

    module.check_source_path(
        "/fsx/run_dir_mounts/RUN123/fastqs/S1_R1.fastq.gz",
        reference_bucket="s3://reference",
        aws_env={},
        debug=False,
    )


def test_process_samples_requires_prechecked_rows(tmp_path: Path) -> None:
    analysis_samples = tmp_path / "analysis_samples.tsv"
    with pytest.raises(TypeError, match="rows"):
        module.process_samples(
            analysis_samples,
            _stage_paths(),
            reference_bucket="s3://bucket",
            aws_env={},
            debug=False,
        )


def test_process_samples_emits_dayoa_compatible_legacy_ilmn_rows(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    analysis_samples = _write_manifest(
        tmp_path,
        "\t".join(
            [
                "RUN_ID",
                "SAMPLE_ID",
                "EXPERIMENTID",
                "SAMPLE_TYPE",
                "LIB_PREP",
                "SEQ_VENDOR",
                "SEQ_PLATFORM",
                "LANE",
                "SEQBC_ID",
                "PATH_TO_CONCORDANCE_DATA_DIR",
                "R1_FQ",
                "R2_FQ",
                "STAGE_DIRECTIVE",
                "STAGE_TARGET",
                "SUBSAMPLE_PCT",
                "IS_POS_CTRL",
                "IS_NEG_CTRL",
                "N_X",
                "N_Y",
                "EXTERNAL_SAMPLE_ID",
            ]
        ),
        [
            "\t".join(
                [
                    "R0",
                    "HG002",
                    "x0p1",
                    "blood",
                    "noampwgs",
                    "ILMN",
                    "NOVASEQX",
                    "0",
                    "S1",
                    "/fsx/data/genomic_data/organism_annotations/H_sapiens/hg38/controls/giab/snv/v4.2.1/HG002/",
                    "/tmp/HG002_0.1x_R1.fastq.gz",
                    "/tmp/HG002_0.1x_R2.fastq.gz",
                    "stage_data",
                    "/fsx/staged_sample_data/",
                    "na",
                    "false",
                    "false",
                    "1",
                    "1",
                    "HG002",
                ]
            )
        ],
    )

    monkeypatch.setattr(module, "check_source_path", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        module,
        "stage_single_lane",
        lambda *args, **kwargs: (
            "/data/staged_sample_data/remote_stage_test/R0_HG002-NOVASEQ-PCR-FREE-blood-x0p1_S1_0/HG002_0.1x_R1.fastq.gz",
            "/data/staged_sample_data/remote_stage_test/R0_HG002-NOVASEQ-PCR-FREE-blood-x0p1_S1_0/HG002_0.1x_R2.fastq.gz",
        ),
    )
    monkeypatch.setattr(module, "stage_concordance", lambda source, *args, **kwargs: source)

    samples_rows, units_rows, created_files, run_ids = _process_samples(
        monkeypatch,
        analysis_samples,
        _stage_paths(),
    )

    assert module.ILMN_TRIM_READ_LENGTH in module.UNITS_HEADER
    assert module.ROCHE_BAM in module.UNITS_HEADER
    assert module.LONGREADTRIM_READ_LENGTH in module.UNITS_HEADER
    assert run_ids == ["R0"]
    assert created_files == [
        "/data/staged_sample_data/remote_stage_test/R0_HG002-NOVASEQ-PCR-FREE-blood-x0p1_S1_0/HG002_0.1x_R1.fastq.gz",
        "/data/staged_sample_data/remote_stage_test/R0_HG002-NOVASEQ-PCR-FREE-blood-x0p1_S1_0/HG002_0.1x_R2.fastq.gz",
    ]
    assert samples_rows == [
        {
            "SAMPLEID": "HG002",
            "SAMPLESOURCE": "blood",
            "SAMPLECLASS": "research",
            "BIOLOGICAL_SEX": "male",
            "CONCORDANCE_CONTROL_PATH": "/fsx/data/genomic_data/organism_annotations/H_sapiens/hg38/controls/giab/snv/v4.2.1/HG002/",
            "IS_POSITIVE_CONTROL": "false",
            "IS_NEGATIVE_CONTROL": "false",
            "SAMPLE_TYPE": "blood",
            "TUM_NRM_SAMPLEID_MATCH": "na",
            "EXTERNAL_SAMPLE_ID": "HG002",
            "N_X": "1",
            "N_Y": "1",
            "TRUTH_DATA_DIR": "/fsx/data/genomic_data/organism_annotations/H_sapiens/hg38/controls/giab/snv/v4.2.1/HG002/",
        }
    ]
    assert len(units_rows) == 1
    units_row = units_rows[0]
    assert units_row["RUNID"] == "R0"
    assert units_row["SAMPLEID"] == "HG002"
    assert units_row["EXPERIMENTID"] == "x0p1"
    assert units_row["LANEID"] == "0"
    assert units_row["BARCODEID"] == "S1"
    assert units_row["LIBPREP"] == "PCR-FREE"
    assert units_row["SEQ_VENDOR"] == "ILMN"
    assert units_row["SEQ_PLATFORM"] == "NOVASEQ"
    assert units_row["ILMN_R1_PATH"].endswith("HG002_0.1x_R1.fastq.gz")
    assert units_row["ILMN_R2_PATH"].endswith("HG002_0.1x_R2.fastq.gz")
    assert units_row["SAMPLEUSE"] == "sample"
    assert units_row["BWA_KMER"] == "19"
    assert units_row["ONT_CRAM"] == ""
    assert units_row["PB_BAM"] == ""
    assert units_row["ROCHE_BAM"] == ""


def test_process_samples_emits_complete_genomics_fastq_rows(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    analysis_samples = _write_manifest(
        tmp_path,
        "\t".join(
            [
                "RUN_ID",
                "SAMPLE_ID",
                "EXPERIMENTID",
                "SAMPLE_TYPE",
                "LIB_PREP",
                "SEQ_VENDOR",
                "SEQ_PLATFORM",
                "LANE",
                "SEQBC_ID",
                "CG_R1_FQ",
                "CG_R2_FQ",
                "STAGE_DIRECTIVE",
                "SUBSAMPLE_PCT",
            ]
        ),
        [
            "\t".join(
                [
                    "CGT7P",
                    "HG003",
                    "T7PLUS",
                    "blood",
                    "PCR-FREE",
                    "CG",
                    "DNBSEQ",
                    "0",
                    "D0",
                    "s3://bucket/HG003_CG_R1.fastq.gz",
                    "s3://bucket/HG003_CG_R2.fastq.gz",
                    "stage_data",
                    "0.182",
                ]
            )
        ],
    )

    monkeypatch.setattr(module, "check_source_path", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        module,
        "stage_single_lane",
        lambda *args, **kwargs: (
            "/data/staged_sample_data/remote_stage_test/CGT7P_HG003-DNBSEQ-PCR-FREE-blood-T7PLUS_D0_0/HG003_CG_R1.fastq.gz",
            "/data/staged_sample_data/remote_stage_test/CGT7P_HG003-DNBSEQ-PCR-FREE-blood-T7PLUS_D0_0/HG003_CG_R2.fastq.gz",
        ),
    )
    monkeypatch.setattr(module, "stage_concordance", lambda source, *args, **kwargs: source)

    samples_rows, units_rows, _created_files, run_ids = _process_samples(
        monkeypatch,
        analysis_samples,
        _stage_paths(),
    )

    assert module.detect_manifest_data_modes(analysis_samples) == ["complete_genomics_solo"]
    assert run_ids == ["CGT7P"]
    assert samples_rows[0]["SAMPLEID"] == "HG003"
    units_row = units_rows[0]
    assert units_row["RUNID"] == "CGT7P"
    assert units_row["SEQ_VENDOR"] == "CG"
    assert units_row["SEQ_PLATFORM"] == "DNBSEQ"
    assert units_row["ILMN_R1_PATH"].endswith("HG003_CG_R1.fastq.gz")
    assert units_row["ILMN_R2_PATH"].endswith("HG003_CG_R2.fastq.gz")
    assert units_row["SUBSAMPLE_PCT"] == "0.182"


def test_process_samples_rejects_incomplete_complete_genomics_fastq_pair(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    analysis_samples = _write_manifest(
        tmp_path,
        "\t".join(
            [
                "RUN_ID",
                "SAMPLE_ID",
                "EXPERIMENTID",
                "SAMPLE_TYPE",
                "LIB_PREP",
                "SEQ_VENDOR",
                "SEQ_PLATFORM",
                "LANE",
                "SEQBC_ID",
                "CG_R1_FQ",
                "CG_R2_FQ",
            ]
        ),
        [
            "\t".join(
                [
                    "CGT7P",
                    "HG003",
                    "T7PLUS",
                    "blood",
                    "PCR-FREE",
                    "CG",
                    "DNBSEQ",
                    "0",
                    "D0",
                    "s3://bucket/HG003_CG_R1.fastq.gz",
                    "",
                ]
            )
        ],
    )

    monkeypatch.setattr(module, "check_source_path", lambda *args, **kwargs: None)

    report, _rows = module.precheck_manifest(
        analysis_samples,
        reference_bucket="s3://bucket",
        aws_env={},
        debug=False,
    )

    assert any(
        "must populate both CG_R1_FQ and CG_R2_FQ" in issue.message for issue in report.issues
    )


def test_process_samples_rejects_duplicate_multi_lane_fastq_pairs(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    analysis_samples = _write_manifest(
        tmp_path,
        "\t".join(
            [
                "RUN_ID",
                "SAMPLE_ID",
                "EXPERIMENTID",
                "SAMPLE_TYPE",
                "LIB_PREP",
                "SEQ_VENDOR",
                "SEQ_PLATFORM",
                "LANE",
                "SEQBC_ID",
                "PATH_TO_CONCORDANCE_DATA_DIR",
                "R1_FQ",
                "R2_FQ",
                "STAGE_DIRECTIVE",
                "SUBSAMPLE_PCT",
                "IS_POS_CTRL",
                "IS_NEG_CTRL",
                "N_X",
                "N_Y",
                "EXTERNAL_SAMPLE_ID",
            ]
        ),
        [
            "\t".join(
                [
                    "R0",
                    "HG002",
                    "x3",
                    "blood",
                    "noampwgs",
                    "ILMN",
                    "NOVASEQX",
                    "1",
                    "S1",
                    "/fsx/data/genomic_data/organism_annotations/H_sapiens/hg38/controls/giab/snv/v4.2.1/HG002/",
                    "s3://bucket/HG002_1x_R1.fastq.gz",
                    "s3://bucket/HG002_1x_R2.fastq.gz",
                    "stage_data",
                    "na",
                    "false",
                    "false",
                    "1",
                    "1",
                    "HG002",
                ]
            ),
            "\t".join(
                [
                    "R0",
                    "HG002",
                    "x3",
                    "blood",
                    "noampwgs",
                    "ILMN",
                    "NOVASEQX",
                    "2",
                    "S0",
                    "/fsx/data/genomic_data/organism_annotations/H_sapiens/hg38/controls/giab/snv/v4.2.1/HG002/",
                    "s3://bucket/HG002_1x_R1.fastq.gz",
                    "s3://bucket/HG002_1x_R2.fastq.gz",
                    "stage_data",
                    "na",
                    "false",
                    "false",
                    "1",
                    "1",
                    "HG002",
                ]
            ),
        ],
    )

    monkeypatch.setattr(module, "check_source_path", lambda *args, **kwargs: None)

    report, _rows = module.precheck_manifest(
        analysis_samples,
        reference_bucket="s3://bucket",
        aws_env={},
        debug=False,
    )

    assert any(
        "Duplicate FASTQ lane sources are not supported" in issue.message for issue in report.issues
    )


def test_process_samples_emits_ultima_cram_unit_rows(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    analysis_samples = _write_manifest(
        tmp_path,
        "\t".join(
            [
                "RUN_ID",
                "SAMPLE_ID",
                "EXPERIMENTID",
                "SAMPLE_TYPE",
                "LIB_PREP",
                "SEQ_VENDOR",
                "SEQ_PLATFORM",
                "LANE",
                "SEQBC_ID",
                "PATH_TO_CONCORDANCE_DATA_DIR",
                "ULTIMA_CRAM",
                "ULTIMA_CRAM_ALIGNER",
                "ULTIMA_CRAM_SNV_CALLER",
                "DEEP_MODEL",
                "IS_POS_CTRL",
                "IS_NEG_CTRL",
                "N_X",
                "N_Y",
                "EXTERNAL_SAMPLE_ID",
            ]
        ),
        [
            "\t".join(
                [
                    "Ug1",
                    "HG003",
                    "1x",
                    "blood",
                    "PF",
                    "UG",
                    "ULTIMA",
                    "1",
                    "D0",
                    "/fsx/data/genomic_data/organism_annotations/H_sapiens/hg38/controls/giab/snv/v4.2.1/HG003/",
                    "/fsx/data/genomic_data/organism_reads/H_sapiens/giab/agbt_2026/ug/HG003_1x.cleaned.cram",
                    "ug",
                    "ug",
                    "WGS",
                    "true",
                    "false",
                    "1",
                    "1",
                    "HG003",
                ]
            )
        ],
    )

    monkeypatch.setattr(module, "check_source_path", lambda *args, **kwargs: None)
    monkeypatch.setattr(module, "stage_concordance", lambda source, *args, **kwargs: source)

    samples_rows, units_rows, created_files, run_ids = _process_samples(
        monkeypatch,
        analysis_samples,
        _stage_paths(),
    )

    assert run_ids == ["Ug1"]
    assert created_files == []
    assert samples_rows[0]["SAMPLEID"] == "HG003"
    assert len(units_rows) == 1
    units_row = units_rows[0]
    assert units_row["RUNID"] == "Ug1"
    assert units_row["SAMPLEID"] == "HG003"
    assert units_row["EXPERIMENTID"] == "1x"
    assert units_row["LANEID"] == "1"
    assert units_row["BARCODEID"] == "D0"
    assert units_row["LIBPREP"] == "PF"
    assert units_row["SEQ_VENDOR"] == "UG"
    assert units_row["SEQ_PLATFORM"] == "ULTIMA"
    assert units_row["SUBSAMPLE_PCT"] == "na"
    assert units_row["SAMPLEUSE"] == "posControl"
    assert units_row["BWA_KMER"] == "19"
    assert units_row["DEEP_MODEL"] == "WGS"
    assert (
        units_row["ULTIMA_CRAM"]
        == "/fsx/data/genomic_data/organism_reads/H_sapiens/giab/agbt_2026/ug/HG003_1x.cleaned.cram"
    )
    assert units_row["ULTIMA_CRAM_ALIGNER"] == "ug"
    assert units_row["ULTIMA_CRAM_SNV_CALLER"] == "ug"


def test_process_samples_emits_ont_cram_rows(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    analysis_samples = _write_manifest(
        tmp_path,
        "\t".join(
            [
                "RUN_ID",
                "SAMPLE_ID",
                "EXPERIMENTID",
                "SAMPLE_TYPE",
                "LIB_PREP",
                "SEQ_VENDOR",
                "SEQ_PLATFORM",
                "LANE",
                "SEQBC_ID",
                "PATH_TO_CONCORDANCE_DATA_DIR",
                "ONT_CRAM",
                "ONT_CRAM_ALIGNER",
                "ONT_CRAM_SNV_CALLER",
                "DEEP_MODEL",
                "IS_POS_CTRL",
                "IS_NEG_CTRL",
                "N_X",
                "N_Y",
                "EXTERNAL_SAMPLE_ID",
            ]
        ),
        [
            "\t".join(
                [
                    "On1",
                    "HG003",
                    "3x",
                    "blood",
                    "PF",
                    "ONT",
                    "PROMETHION",
                    "2",
                    "D0",
                    "/fsx/data/genomic_data/organism_annotations/H_sapiens/hg38/controls/giab/snv/v4.2.1/HG003/",
                    "/fsx/data/genomic_data/organism_reads/H_sapiens/giab/agbt_2026/ont/HG003_3x.cleaned.cram",
                    "ont",
                    "sentdont",
                    "ONT_R104",
                    "true",
                    "false",
                    "1",
                    "1",
                    "HG003",
                ]
            )
        ],
    )

    monkeypatch.setattr(module, "check_source_path", lambda *args, **kwargs: None)
    monkeypatch.setattr(module, "stage_concordance", lambda source, *args, **kwargs: source)

    _samples_rows, units_rows, created_files, run_ids = _process_samples(
        monkeypatch,
        analysis_samples,
        _stage_paths(),
    )

    assert run_ids == ["On1"]
    assert created_files == []
    assert (
        units_rows[0]["ONT_CRAM"]
        == "/fsx/data/genomic_data/organism_reads/H_sapiens/giab/agbt_2026/ont/HG003_3x.cleaned.cram"
    )
    assert units_rows[0]["ONT_CRAM_ALIGNER"] == "ont"
    assert units_rows[0]["ONT_CRAM_SNV_CALLER"] == "sentdont"
    assert units_rows[0]["DEEP_MODEL"] == "ONT_R104"


def test_process_samples_mounted_readonly_preserves_fastq_paths_without_copying(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    r1 = "/fsx/run_dir_mounts/RUN123/fastqs/S1_R1.fastq.gz"
    r2 = "/fsx/run_dir_mounts/RUN123/fastqs/S1_R2.fastq.gz"
    analysis_samples = _write_manifest(
        tmp_path,
        "\t".join(
            [
                "RUN_ID",
                "SAMPLE_ID",
                "EXPERIMENTID",
                "SAMPLE_TYPE",
                "LIB_PREP",
                "SEQ_VENDOR",
                "SEQ_PLATFORM",
                "LANE",
                "SEQBC_ID",
                "ILMN_R1_FQ",
                "ILMN_R2_FQ",
                "STAGE_DIRECTIVE",
                "MOUNT_ID",
                "MOUNT_SOURCE_S3_URI",
                "MOUNT_FSX_PATH",
                "DATA_LOCALITY",
            ]
        ),
        [
            "\t".join(
                [
                    "RUN123",
                    "S1",
                    "exp1",
                    "blood",
                    "PCR-FREE",
                    "ILMN",
                    "NOVASEQ",
                    "1",
                    "BC1",
                    r1,
                    r2,
                    "mounted_readonly",
                    "RUN123",
                    "s3://sequencer-runs/RUN123/",
                    "/fsx/run_dir_mounts/RUN123/",
                    "mounted_readonly",
                ]
            )
        ],
    )

    def forbidden_copy(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("mounted_readonly source bytes must not be staged or copied")

    monkeypatch.setattr(module, "aws_copy", forbidden_copy)
    monkeypatch.setattr(module, "stage_single_lane", forbidden_copy)
    monkeypatch.setattr(module, "stage_multi_lane", forbidden_copy)
    monkeypatch.setattr(module, "stage_path_with_sidecars", forbidden_copy)

    _samples_rows, units_rows, created_files, run_ids = _process_samples(
        monkeypatch,
        analysis_samples,
        _stage_paths(),
    )

    assert created_files == []
    assert run_ids == ["RUN123"]
    assert units_rows[0]["ILMN_R1_PATH"] == r1
    assert units_rows[0]["ILMN_R2_PATH"] == r2


def test_process_samples_mounted_readonly_preserves_cram_paths_without_copying(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    cram = "/run_dir_mounts/RUN123/crams/S1.ont.cram"
    analysis_samples = _write_manifest(
        tmp_path,
        "\t".join(
            [
                "RUN_ID",
                "SAMPLE_ID",
                "EXPERIMENTID",
                "SAMPLE_TYPE",
                "LIB_PREP",
                "SEQ_VENDOR",
                "SEQ_PLATFORM",
                "LANE",
                "SEQBC_ID",
                "ONT_CRAM",
                "ONT_CRAM_ALIGNER",
                "ONT_CRAM_SNV_CALLER",
                "STAGE_DIRECTIVE",
                "MOUNT_ID",
                "MOUNT_FSX_PATH",
            ]
        ),
        [
            "\t".join(
                [
                    "RUN123",
                    "S1",
                    "exp1",
                    "blood",
                    "PF",
                    "ONT",
                    "PROMETHION",
                    "1",
                    "BC1",
                    cram,
                    "ont",
                    "sentdont",
                    "mounted_readonly",
                    "RUN123",
                    "/run_dir_mounts/RUN123/",
                ]
            )
        ],
    )

    def forbidden_copy(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("mounted_readonly aligned bytes must not be staged or copied")

    monkeypatch.setattr(module, "aws_copy", forbidden_copy)
    monkeypatch.setattr(module, "stage_single_lane", forbidden_copy)
    monkeypatch.setattr(module, "stage_multi_lane", forbidden_copy)
    monkeypatch.setattr(module, "stage_path_with_sidecars", forbidden_copy)

    _samples_rows, units_rows, created_files, run_ids = _process_samples(
        monkeypatch,
        analysis_samples,
        _stage_paths(),
    )

    assert created_files == []
    assert run_ids == ["RUN123"]
    assert units_rows[0]["ONT_CRAM"] == cram
    assert units_rows[0]["ONT_CRAM_ALIGNER"] == "ont"
    assert units_rows[0]["ONT_CRAM_SNV_CALLER"] == "sentdont"


def _ont_prefix() -> str:
    return (
        "s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/pca100/2026/"
        "20260424_ONT_100ul/FC1/20260424_2252_1F_PBK85691_9b079e46/"
        "fastq_pass/barcode03/"
    )


def _ont_run_root() -> str:
    return (
        "s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/pca100/2026/"
        "20260424_ONT_100ul/FC1/20260424_2252_1F_PBK85691_9b079e46/"
    )


def _s3_obj(uri: str, size: int) -> module.S3ObjectSummary:
    _bucket, key = module.parse_s3_uri(uri)
    return module.S3ObjectSummary(uri=uri, key=key, size=size)


def _valid_ont_objects(prefix: str) -> list[module.S3ObjectSummary]:
    return [
        _s3_obj(f"{prefix}PBK85691_pass_barcode03_9b079e46_1709963d_0.fastq.gz", 10),
        _s3_obj(f"{prefix}PBK85691_pass_barcode03_9b079e46_1709963d_1.fastq.gz", 20),
        _s3_obj(f"{prefix}PBK85691_pass_barcode03_9b079e46_1709963d_2.fastq.gz", 30),
    ]


def _valid_ont_root_objects(prefix: str) -> list[module.S3ObjectSummary]:
    root = _ont_run_root()
    return [
        *_valid_ont_objects(prefix),
        _s3_obj(f"{root}pod5_pass/barcode03/PBK85691_pass_barcode03_9b079e46_1709963d_0.pod5", 40),
        _s3_obj(f"{root}final_summary_PBK85691_9b079e46.txt", 1),
        _s3_obj(f"{root}sample_sheet_PBK85691_9b079e46.csv", 1),
        _s3_obj(f"{root}sequencing_summary_PBK85691_9b079e46.txt", 1),
        _s3_obj(f"{root}report_PBK85691_9b079e46.json", 1),
    ]


def test_process_samples_emits_ont_fastq_prefix_rows(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    prefix = _ont_prefix()
    analysis_samples = _write_manifest(
        tmp_path,
        "\t".join(
            [
                "RUN_ID",
                "SAMPLE_ID",
                "EXPERIMENTID",
                "SAMPLE_TYPE",
                "LIB_PREP",
                "SEQ_VENDOR",
                "SEQ_PLATFORM",
                "LANE",
                "SEQBC_ID",
                "PATH_TO_CONCORDANCE_DATA_DIR",
                "ONT_FASTQ_PREFIX",
                "ONT_FLOWCELL_ID",
                "STAGE_DIRECTIVE",
                "DEEP_MODEL",
                "EXTERNAL_SAMPLE_ID",
            ]
        ),
        [
            "\t".join(
                [
                    "manifest.run_id",
                    "HG003",
                    "pca100",
                    "blood",
                    "SQK-LSK114",
                    "ONT",
                    "PROMETHION",
                    "placeholder",
                    "placeholder",
                    "/fsx/data/genomic_data/organism_annotations/H_sapiens/hg38/controls/giab/snv/v4.2.1/HG003/",
                    prefix,
                    "PBK85691",
                    "stage_data",
                    "ONT_R104",
                    "HG003",
                ]
            )
        ],
    )

    def fake_list_s3_objects(uri: str, **_kwargs: object) -> list[module.S3ObjectSummary]:
        if uri == module.normalise_s3_prefix_uri(prefix):
            return _valid_ont_objects(prefix)
        if uri == _ont_run_root():
            return _valid_ont_root_objects(prefix)
        raise AssertionError(uri)

    concatenated: list[list[str]] = []

    def fake_concatenate(
        plan: module.OntFastqPrefixPlan,
        destination: str,
        **_kwargs: object,
    ) -> None:
        concatenated.append([shard.uri for shard in plan.shards])
        assert destination.endswith("20260424-ONT-100ul-PBK85691-barcode03-R1.fastq.gz")

    monkeypatch.setattr(module, "list_s3_objects", fake_list_s3_objects)
    monkeypatch.setattr(
        module,
        "read_s3_text",
        lambda *_args, **_kwargs: "\n".join(
            [
                "flow_cell_id=PBK85691",
                "basecalling_enabled=1",
                "fastq_files_in_final_dest=3",
                "pod5_files_in_final_dest=1",
                "fallback_fastq_files_in_final_dest=0",
                "fallback_pod5_files_in_final_dest=0",
            ]
        ),
    )
    monkeypatch.setattr(module, "concatenate_ont_fastq_shards", fake_concatenate)
    monkeypatch.setattr(module, "check_source_path", lambda *args, **kwargs: None)
    monkeypatch.setattr(module, "stage_concordance", lambda source, *args, **kwargs: source)

    _samples_rows, units_rows, created_files, run_ids = _process_samples(
        monkeypatch,
        analysis_samples,
        _stage_paths(),
    )

    assert module.detect_manifest_data_modes(analysis_samples) == ["ont_solo"]
    assert run_ids == ["20260424-ONT-100ul"]
    assert concatenated == [[obj.uri for obj in _valid_ont_objects(prefix)]]
    assert created_files == [
        "/data/staged_sample_data/remote_stage_test/"
        "20260424-ONT-100ul_HG003-PROMETHION-SQK-LSK114-blood-pca100_PBK85691_barcode03_0/"
        "20260424-ONT-100ul-PBK85691-barcode03-R1.fastq.gz"
    ]
    units_row = units_rows[0]
    assert units_row["RUNID"] == "20260424-ONT-100ul"
    assert units_row["LANEID"] == "PBK85691"
    assert units_row["BARCODEID"] == "barcode03"
    assert units_row["ONT_R1_PATH"].endswith("20260424-ONT-100ul-PBK85691-barcode03-R1.fastq.gz")
    assert units_row["ONT_R2_PATH"] == "na"
    assert units_row["DEEP_MODEL"] == "ONT_R104"


def test_ont_fastq_prefix_requires_flowcell_for_mixed_prefix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prefix = _ont_prefix()

    def fake_list_s3_objects(uri: str, **_kwargs: object) -> list[module.S3ObjectSummary]:
        assert uri == module.normalise_s3_prefix_uri(prefix)
        return [
            _s3_obj(f"{prefix}PBK85691_pass_barcode03_9b079e46_1709963d_0.fastq.gz", 10),
            _s3_obj(f"{prefix}PBK93388_pass_barcode03_9b079e46_1709963d_0.fastq.gz", 10),
        ]

    monkeypatch.setattr(module, "list_s3_objects", fake_list_s3_objects)

    with pytest.raises(module.CommandError, match="contains multiple flowcells"):
        module.resolve_ont_fastq_prefix_plan(
            prefix,
            flowcell_id="",
            aws_env={},
            debug=False,
        )


def test_ont_fastq_prefix_rejects_missing_run_output_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prefix = _ont_prefix()

    def fake_list_s3_objects(uri: str, **_kwargs: object) -> list[module.S3ObjectSummary]:
        if uri == module.normalise_s3_prefix_uri(prefix):
            return _valid_ont_objects(prefix)
        if uri == _ont_run_root():
            return [
                *_valid_ont_objects(prefix),
                _s3_obj(
                    f"{_ont_run_root()}pod5_pass/barcode03/PBK85691_pass_barcode03_9b079e46_1709963d_0.pod5",
                    40,
                ),
            ]
        raise AssertionError(uri)

    monkeypatch.setattr(module, "list_s3_objects", fake_list_s3_objects)

    with pytest.raises(module.CommandError, match="missing final_summary"):
        module.resolve_ont_fastq_prefix_plan(
            prefix,
            flowcell_id="PBK85691",
            aws_env={},
            debug=False,
        )


def test_ont_fastq_concat_bundles_small_shards(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prefix = _ont_prefix()
    shards = [
        module.parse_ont_fastq_shard(obj, expected_tag="barcode03", run_id="20260424-ONT-100ul")
        for obj in _valid_ont_objects(prefix)
    ]
    uploaded_groups: list[list[str]] = []

    def fake_upload_bundle(
        sources: list[module.OntFastqShard],
        *,
        bundle_s3_dir: str,
        bundle_number: int,
        **_kwargs: object,
    ) -> module.S3ObjectSummary:
        uploaded_groups.append([source.filename for source in sources])
        return module.S3ObjectSummary(
            uri=f"{bundle_s3_dir}/bundle-{bundle_number}.fastq.gz",
            key=f"_parts/bundle-{bundle_number}.fastq.gz",
            size=sum(source.size for source in sources),
        )

    monkeypatch.setattr(module, "_upload_concat_bundle", fake_upload_bundle)

    concat_sources, uploaded = module.build_size_aware_concat_sources(
        shards,
        bundle_s3_dir="s3://bucket/stage/_parts",
        sample_prefix="sample",
        suffix=".fastq.gz",
        aws_env={},
        debug=False,
    )

    assert uploaded_groups == [[shard.filename for shard in shards]]
    assert [source.uri for source in concat_sources] == [
        "s3://bucket/stage/_parts/bundle-1.fastq.gz"
    ]
    assert uploaded == ["s3://bucket/stage/_parts/bundle-1.fastq.gz"]


def test_process_samples_emits_hybrid_ilmn_ont_rows(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    analysis_samples = _write_manifest(
        tmp_path,
        "\t".join(
            [
                "RUN_ID",
                "SAMPLE_ID",
                "EXPERIMENTID",
                "SAMPLE_TYPE",
                "LIB_PREP",
                "SEQ_VENDOR",
                "SEQ_PLATFORM",
                "LANE",
                "SEQBC_ID",
                "PATH_TO_CONCORDANCE_DATA_DIR",
                "ILMN_R1_FQ",
                "ILMN_R2_FQ",
                "ONT_CRAM",
                "ONT_CRAM_ALIGNER",
                "ONT_CRAM_SNV_CALLER",
                "DEEP_MODEL",
                "STAGE_DIRECTIVE",
                "IS_POS_CTRL",
                "IS_NEG_CTRL",
                "N_X",
                "N_Y",
                "EXTERNAL_SAMPLE_ID",
            ]
        ),
        [
            "\t".join(
                [
                    "HIOa",
                    "HG003",
                    "SR1x-ONT3x",
                    "blood",
                    "PF",
                    "ILMN",
                    "NOVASEQ",
                    "1",
                    "D0",
                    "/fsx/data/genomic_data/organism_annotations/H_sapiens/hg38/controls/giab/snv/v4.2.1/HG003/",
                    "s3://bucket/HG003_1x_R1.fastq.gz",
                    "s3://bucket/HG003_1x_R2.fastq.gz",
                    "/fsx/data/genomic_data/organism_reads/H_sapiens/giab/agbt_2026/ont/HG003_3x.cleaned.cram",
                    "ont",
                    "sentdont",
                    "WGS",
                    "stage_data",
                    "true",
                    "false",
                    "1",
                    "1",
                    "HG003",
                ]
            )
        ],
    )

    monkeypatch.setattr(module, "check_source_path", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        module,
        "stage_single_lane",
        lambda *args, **kwargs: (
            "/data/staged_sample_data/remote_stage_test/HIOa_HG003-NOVASEQ-PF-blood-SR1x-ONT3x_D0_0/HG003_1x_R1.fastq.gz",
            "/data/staged_sample_data/remote_stage_test/HIOa_HG003-NOVASEQ-PF-blood-SR1x-ONT3x_D0_0/HG003_1x_R2.fastq.gz",
        ),
    )
    monkeypatch.setattr(
        module,
        "stage_path_with_sidecars",
        lambda *args, **kwargs: (
            "/data/staged_sample_data/remote_stage_test/HIOa_HG003-NOVASEQ-PF-blood-SR1x-ONT3x_D0_0/HG003_3x.cleaned.cram",
            [
                "/data/staged_sample_data/remote_stage_test/HIOa_HG003-NOVASEQ-PF-blood-SR1x-ONT3x_D0_0/HG003_3x.cleaned.cram",
                "/data/staged_sample_data/remote_stage_test/HIOa_HG003-NOVASEQ-PF-blood-SR1x-ONT3x_D0_0/HG003_3x.cleaned.cram.crai",
            ],
        ),
    )
    monkeypatch.setattr(module, "stage_concordance", lambda source, *args, **kwargs: source)

    _samples_rows, units_rows, created_files, _run_ids = _process_samples(
        monkeypatch,
        analysis_samples,
        _stage_paths(),
    )

    assert units_rows[0]["ILMN_R1_PATH"].endswith("HG003_1x_R1.fastq.gz")
    assert units_rows[0]["ILMN_R2_PATH"].endswith("HG003_1x_R2.fastq.gz")
    assert units_rows[0]["ONT_CRAM"].endswith("HG003_3x.cleaned.cram")
    assert units_rows[0]["ONT_CRAM_ALIGNER"] == "ont"
    assert units_rows[0]["ONT_CRAM_SNV_CALLER"] == "sentdont"
    assert len(created_files) == 4


def test_process_samples_emits_pacbio_and_roche_rows(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    analysis_samples = _write_manifest(
        tmp_path,
        "\t".join(
            [
                "RUN_ID",
                "SAMPLE_ID",
                "EXPERIMENTID",
                "SAMPLE_TYPE",
                "LIB_PREP",
                "SEQ_VENDOR",
                "SEQ_PLATFORM",
                "LANE",
                "SEQBC_ID",
                "PATH_TO_CONCORDANCE_DATA_DIR",
                "PB_BAM",
                "PB_BAM_ALIGNER",
                "PB_BAM_SNV_CALLER",
                "ROCHE_BAM",
                "ROCHE_BAM_ALIGNER",
                "ROCHE_BAM_SNV_CALLER",
                "ROCHE_DOWNSAMPLE_RATIO",
                "DEEP_MODEL",
                "IS_POS_CTRL",
                "IS_NEG_CTRL",
                "N_X",
                "N_Y",
                "EXTERNAL_SAMPLE_ID",
            ]
        ),
        [
            "\t".join(
                [
                    "PB1",
                    "HG003",
                    "rep1",
                    "blood",
                    "PCR-FREE",
                    "PACBIO",
                    "REVIO",
                    "0",
                    "rep1",
                    "/fsx/data/genomic_data/organism_annotations/H_sapiens/hg38/controls/giab/snv/v4.2.1/HG003/",
                    "/fsx/data/genomic_data/organism_reads/H_sapiens/giab/pacbio/revio_2024Q4/GIAB_trio/HG003.bc2020.bam",
                    "sentmm2",
                    "sentdpb",
                    "",
                    "",
                    "",
                    "",
                    "WGS",
                    "true",
                    "false",
                    "1",
                    "1",
                    "HG003",
                ]
            ),
            "\t".join(
                [
                    "RH1",
                    "HG003R",
                    "1x",
                    "blood",
                    "PF",
                    "ROCHE",
                    "SBX-DUPLEX",
                    "0",
                    "D0",
                    "/fsx/data/genomic_data/organism_annotations/H_sapiens/hg38/controls/giab/snv/v4.2.1/HG003/",
                    "",
                    "",
                    "",
                    "/fsx/data/genomic_data/organism_reads/H_sapiens/giab/roche/HG003.bam",
                    "roche",
                    "rochehc",
                    "0.0172",
                    "WGS",
                    "true",
                    "false",
                    "1",
                    "1",
                    "HG003R",
                ]
            ),
        ],
    )

    monkeypatch.setattr(module, "check_source_path", lambda *args, **kwargs: None)
    monkeypatch.setattr(module, "stage_concordance", lambda source, *args, **kwargs: source)

    _samples_rows, units_rows, created_files, run_ids = _process_samples(
        monkeypatch,
        analysis_samples,
        _stage_paths(),
    )

    assert created_files == []
    assert run_ids == ["PB1", "RH1"]
    pb_row = next(row for row in units_rows if row["RUNID"] == "PB1")
    roche_row = next(row for row in units_rows if row["RUNID"] == "RH1")
    assert pb_row["PB_BAM"].endswith("HG003.bc2020.bam")
    assert pb_row["PB_BAM_ALIGNER"] == "sentmm2"
    assert pb_row["PB_BAM_SNV_CALLER"] == "sentdpb"
    assert roche_row["ROCHE_BAM"].endswith("HG003.bam")
    assert roche_row["ROCHE_BAM_ALIGNER"] == "roche"
    assert roche_row["ROCHE_BAM_SNV_CALLER"] == "rochehc"
    assert roche_row["ROCHE_DOWNSAMPLE_RATIO"] == "0.0172"


def test_process_samples_rejects_ultima_cram_without_crai(
    tmp_path: Path,
) -> None:
    cram = tmp_path / "sample.cram"
    cram.write_text("x", encoding="utf-8")
    analysis_samples = _write_manifest(
        tmp_path,
        "\t".join(
            [
                "RUN_ID",
                "SAMPLE_ID",
                "EXPERIMENTID",
                "SAMPLE_TYPE",
                "LIB_PREP",
                "SEQ_VENDOR",
                "SEQ_PLATFORM",
                "LANE",
                "SEQBC_ID",
                "ULTIMA_CRAM",
                "ULTIMA_CRAM_ALIGNER",
                "STAGE_DIRECTIVE",
            ]
        ),
        [
            "\t".join(
                [
                    "Ug1",
                    "HG003",
                    "1x",
                    "blood",
                    "PF",
                    "UG",
                    "ULTIMA",
                    "1",
                    "D0",
                    str(cram),
                    "ug",
                    "stage_data",
                ]
            )
        ],
    )

    report, _rows = module.precheck_manifest(
        analysis_samples,
        reference_bucket="s3://bucket",
        aws_env={},
        debug=False,
    )

    assert any("Local path not found" in issue.message for issue in report.issues)


def test_stage_path_with_sidecars_stages_cram_before_crai(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def fake_stage_path(
        source: str, *, dest_fsx_dir: str, **_kwargs: object
    ) -> tuple[str, list[str]]:
        calls.append(source)
        remote_path = f"{dest_fsx_dir}/{Path(source).name}"
        return remote_path, [remote_path]

    monkeypatch.setattr(module, "stage_path", fake_stage_path)

    remote_path, created = module.stage_path_with_sidecars(
        "s3://bucket/sample.cram",
        sidecar_suffixes=(".crai",),
        dest_fsx_dir="/data/staged_sample_data/remote_stage_test/sample",
        dest_s3_dir="s3://bucket/data/staged_sample_data/remote_stage_test/sample",
        reference_bucket="s3://reference",
        aws_env={},
        debug=False,
    )

    assert calls == ["s3://bucket/sample.cram", "s3://bucket/sample.cram.crai"]
    assert remote_path.endswith("/sample.cram")
    assert created == [
        "/data/staged_sample_data/remote_stage_test/sample/sample.cram",
        "/data/staged_sample_data/remote_stage_test/sample/sample.cram.crai",
    ]


def test_parse_run_metric_staging_specs_normalizes_run_uid_and_platform(tmp_path: Path) -> None:
    first = tmp_path / "run1.fofn"
    second = tmp_path / "run2.fofn"

    specs = module.parse_run_metric_staging_specs(
        [
            f"RUN_1:ilmn:{first}",
            f"RUN.2:ont:{second}",
        ]
    )

    assert [(spec.run_uid, spec.platform, spec.fofn) for spec in specs] == [
        ("RUN-1", "ILMN", first),
        ("RUN-2", "ONT", second),
    ]


def test_precheck_run_metrics_preserves_relative_dirs_and_uses_basename(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    relative_metric = tmp_path / "qc" / "summary.txt"
    relative_metric.parent.mkdir()
    relative_metric.write_text("relative\n", encoding="utf-8")
    absolute_metric = tmp_path / "absolute" / "instrument.csv"
    absolute_metric.parent.mkdir()
    absolute_metric.write_text("absolute\n", encoding="utf-8")
    fofn = tmp_path / "metrics.fofn"
    fofn.write_text(
        "\n".join(
            [
                "qc/summary.txt",
                str(absolute_metric),
                "s3://source-bucket/metrics/report.json",
                "/fsx/data/run_metrics/headnode.txt",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    checked_paths: list[str] = []

    def fake_check_source_path(path: str, **_kwargs: object) -> None:
        checked_paths.append(path)

    monkeypatch.setattr(module, "check_source_path", fake_check_source_path)

    specs = module.parse_run_metric_staging_specs([f"RUN.1:ilmn:{fofn}"])
    files = module.precheck_run_metrics(
        specs,
        reference_bucket="s3://reference",
        aws_env={},
        debug=False,
    )

    assert checked_paths == [
        str(relative_metric.resolve()),
        str(absolute_metric),
        "s3://source-bucket/metrics/report.json",
        "/fsx/data/run_metrics/headnode.txt",
    ]
    assert [(item.source, item.destination_relative_path) for item in files] == [
        (str(relative_metric.resolve()), "qc/summary.txt"),
        (str(absolute_metric), "instrument.csv"),
        ("s3://source-bucket/metrics/report.json", "report.json"),
        ("/fsx/data/run_metrics/headnode.txt", "headnode.txt"),
    ]
    assert all(item.spec.run_uid == "RUN-1" for item in files)
    assert all(item.spec.platform == "ILMN" for item in files)


def test_stage_run_metrics_copies_under_runs_subdir(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    spec = module.RunMetricStagingSpec(run_uid="RUN-1", platform="ILMN", fofn=tmp_path / "x.fofn")
    files = [
        module.RunMetricFile(
            spec=spec,
            source="/fsx/data/run_metrics/headnode.txt",
            destination_relative_path="headnode.txt",
        ),
        module.RunMetricFile(
            spec=spec,
            source="s3://source-bucket/metrics/report.json",
            destination_relative_path="qc/report.json",
        ),
    ]
    copies: list[tuple[str, str]] = []

    def fake_aws_copy(source: str, destination: str, **_kwargs: object) -> None:
        copies.append((source, destination))

    monkeypatch.setattr(module, "aws_copy", fake_aws_copy)

    created = module.stage_run_metrics(
        files,
        _stage_paths(),
        reference_bucket="s3://reference-bucket",
        aws_env={},
        debug=False,
    )

    assert copies == [
        (
            "s3://reference-bucket/data/run_metrics/headnode.txt",
            "s3://bucket/data/staged_sample_data/remote_stage_test/runs/RUN-1/headnode.txt",
        ),
        (
            "s3://source-bucket/metrics/report.json",
            "s3://bucket/data/staged_sample_data/remote_stage_test/runs/RUN-1/qc/report.json",
        ),
    ]
    assert created == [
        "/data/staged_sample_data/remote_stage_test/runs/RUN-1/headnode.txt",
        "/data/staged_sample_data/remote_stage_test/runs/RUN-1/qc/report.json",
    ]


def test_precheck_run_metrics_rejects_duplicate_destination_paths(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    first = tmp_path / "a" / "metrics.txt"
    second = tmp_path / "b" / "metrics.txt"
    first.parent.mkdir()
    second.parent.mkdir()
    first.write_text("first\n", encoding="utf-8")
    second.write_text("second\n", encoding="utf-8")
    fofn = tmp_path / "metrics.fofn"
    fofn.write_text(f"{first}\n{second}\n", encoding="utf-8")

    monkeypatch.setattr(module, "check_source_path", lambda *args, **kwargs: None)

    specs = module.parse_run_metric_staging_specs([f"RUN1:ILMN:{fofn}"])
    with pytest.raises(module.CommandError, match="maps multiple sources"):
        module.precheck_run_metrics(
            specs,
            reference_bucket="s3://reference",
            aws_env={},
            debug=False,
        )


def test_precheck_run_metrics_rejects_parent_relative_destination(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    fofn = tmp_path / "metrics.fofn"
    fofn.write_text("../metrics.txt\n", encoding="utf-8")
    checked_paths: list[str] = []

    def fake_check_source_path(path: str, **_kwargs: object) -> None:
        checked_paths.append(path)

    monkeypatch.setattr(module, "check_source_path", fake_check_source_path)

    specs = module.parse_run_metric_staging_specs([f"RUN1:ILMN:{fofn}"])
    with pytest.raises(module.CommandError, match="must not contain '..'"):
        module.precheck_run_metrics(
            specs,
            reference_bucket="s3://reference",
            aws_env={},
            debug=False,
        )
    assert checked_paths == []


def test_main_precheck_only_validates_run_metrics_without_copying(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    analysis_samples = tmp_path / "analysis_samples.tsv"
    analysis_samples.write_text("RUN_ID\tSAMPLE_ID\n", encoding="utf-8")
    metric = tmp_path / "metric.txt"
    metric.write_text("metric\n", encoding="utf-8")
    fofn = tmp_path / "metrics.fofn"
    fofn.write_text("metric.txt\n", encoding="utf-8")
    checked_paths: list[str] = []

    def fake_precheck_manifest(
        *_args: object, **_kwargs: object
    ) -> tuple[module.PrecheckReport, list[module.ManifestRow]]:
        return module.PrecheckReport(0, 0, 0, 0, ()), []

    def fake_check_source_path(path: str, **_kwargs: object) -> None:
        checked_paths.append(path)

    def unexpected_copy_step(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("precheck-only must not copy files")

    monkeypatch.setattr(module, "precheck_manifest", fake_precheck_manifest)
    monkeypatch.setattr(module, "check_source_path", fake_check_source_path)
    monkeypatch.setattr(module, "ensure_remote_stage_writable", unexpected_copy_step)
    monkeypatch.setattr(module, "stage_run_metrics", unexpected_copy_step)

    rc = module.main(
        [
            str(analysis_samples),
            "--reference-bucket",
            "s3://reference",
            "--profile",
            "dev",
            "--run-metric-staging",
            f"RUN1:ILMN:{fofn}",
            "--precheck-only",
        ]
    )

    assert rc == 0
    assert checked_paths == [str(metric.resolve())]


def _minimal_ilmn_header() -> str:
    return "\t".join(
        [
            "RUN_ID",
            "SAMPLE_ID",
            "EXPERIMENTID",
            "SAMPLE_TYPE",
            "LIB_PREP",
            "SEQ_VENDOR",
            "SEQ_PLATFORM",
            "LANE",
            "SEQBC_ID",
            "ILMN_R1_FQ",
            "ILMN_R2_FQ",
            "STAGE_DIRECTIVE",
        ]
    )


def _minimal_ilmn_row(
    *,
    run_id: str = "R1",
    sample_id: str = "S1",
    r1: str = "s3://bucket/S1_R1.fastq.gz",
    r2: str = "s3://bucket/S1_R2.fastq.gz",
) -> str:
    return "\t".join(
        [
            run_id,
            sample_id,
            "exp1",
            "blood",
            "PCR-FREE",
            "ILMN",
            "NOVASEQ",
            "1",
            "BC1",
            r1,
            r2,
            "stage_data",
        ]
    )


def _mounted_ilmn_header() -> str:
    return "\t".join(
        [
            "RUN_ID",
            "SAMPLE_ID",
            "EXPERIMENTID",
            "SAMPLE_TYPE",
            "LIB_PREP",
            "SEQ_VENDOR",
            "SEQ_PLATFORM",
            "LANE",
            "SEQBC_ID",
            "ILMN_R1_FQ",
            "ILMN_R2_FQ",
            "STAGE_DIRECTIVE",
            "MOUNT_ID",
        ]
    )


def _mounted_ilmn_row(
    *,
    r1: str = "/fsx/run_dir_mounts/RUN123/fastqs/S1_R1.fastq.gz",
    r2: str = "/fsx/run_dir_mounts/RUN123/fastqs/S1_R2.fastq.gz",
    mount_id: str = "RUN123",
) -> str:
    return "\t".join(
        [
            "RUN123",
            "S1",
            "exp1",
            "blood",
            "PCR-FREE",
            "ILMN",
            "NOVASEQ",
            "1",
            "BC1",
            r1,
            r2,
            "mounted_readonly",
            mount_id,
        ]
    )


def test_precheck_manifest_rejects_mounted_readonly_paths_outside_run_dir_mounts(
    tmp_path: Path,
) -> None:
    analysis_samples = _write_manifest(
        tmp_path,
        _mounted_ilmn_header(),
        [
            _mounted_ilmn_row(
                r1="/fsx/data/staged_sample_data/S1_R1.fastq.gz",
            )
        ],
    )

    report, rows = module.precheck_manifest(
        analysis_samples,
        reference_bucket="s3://bucket",
        aws_env={},
        debug=False,
    )

    assert rows == []
    assert any(
        issue.field == module.ILMN_R1_FQ and "must be under /fsx/run_dir_mounts" in issue.message
        for issue in report.issues
    )


def test_precheck_manifest_rejects_mounted_readonly_mount_id_mismatch(
    tmp_path: Path,
) -> None:
    analysis_samples = _write_manifest(
        tmp_path,
        _mounted_ilmn_header(),
        [
            _mounted_ilmn_row(
                r1="/fsx/run_dir_mounts/RUN999/fastqs/S1_R1.fastq.gz",
            )
        ],
    )

    report, rows = module.precheck_manifest(
        analysis_samples,
        reference_bucket="s3://bucket",
        aws_env={},
        debug=False,
    )

    assert rows == []
    assert any(
        issue.field == module.ILMN_R1_FQ
        and "uses mount ID RUN999, but MOUNT_ID is RUN123" in issue.message
        for issue in report.issues
    )


def test_precheck_manifest_collects_multiple_row_errors(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    analysis_samples = _write_manifest(
        tmp_path,
        _minimal_ilmn_header(),
        [
            _minimal_ilmn_row(sample_id="S1", r1="s3://missing/S1_R1.fastq.gz"),
            _minimal_ilmn_row(sample_id="S2", r2="s3://missing/S2_R2.fastq.gz"),
        ],
    )

    def fake_check_source_path(path: str, **_kwargs: object) -> None:
        if path.startswith("s3://missing/"):
            raise module.CommandError(f"S3 object or prefix not accessible: {path}")

    monkeypatch.setattr(module, "check_source_path", fake_check_source_path)

    report, rows = module.precheck_manifest(
        analysis_samples,
        reference_bucket="s3://bucket",
        aws_env={},
        debug=False,
    )

    assert len(rows) == 2
    assert report.rows_checked == 2
    assert report.samples_checked == 2
    assert report.source_objects_checked == 4
    assert [(issue.row_number, issue.sample_id, issue.field) for issue in report.issues] == [
        (2, "S1", "ILMN_R1_FQ"),
        (3, "S2", "ILMN_R2_FQ"),
    ]
    failure = module.format_precheck_failure(report)
    assert "Precheck failed; no files were copied." in failure
    assert "SAMPLE_ID=S1" in failure
    assert "SAMPLE_ID=S2" in failure


def test_precheck_manifest_collects_multiple_structural_errors_in_one_row(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    analysis_samples = _write_manifest(
        tmp_path,
        "\t".join(
            [
                "RUN_ID",
                "SAMPLE_ID",
                "EXPERIMENTID",
                "SAMPLE_TYPE",
                "LIB_PREP",
                "SEQ_VENDOR",
                "SEQ_PLATFORM",
                "LANE",
                "SEQBC_ID",
                "ILMN_R1_FQ",
                "ILMN_R2_FQ",
                "ONT_FASTQ_PREFIX",
                "STAGE_DIRECTIVE",
            ]
        ),
        [
            "\t".join(
                [
                    "R1",
                    "S1",
                    "exp1",
                    "blood",
                    "PCR-FREE",
                    "ILMN",
                    "NOVASEQ",
                    "1",
                    "BC1",
                    "s3://bucket/S1_R1.fastq.gz",
                    "s3://bucket/S1_R2.fastq.gz",
                    "s3://bucket/not_an_ont_run/fastq_pass/barcode01/",
                    "pass_through",
                ]
            )
        ],
    )

    monkeypatch.setattr(module, "check_source_path", lambda *args, **kwargs: None)

    report, _rows = module.precheck_manifest(
        analysis_samples,
        reference_bucket="s3://bucket",
        aws_env={},
        debug=False,
    )

    messages = [issue.message for issue in report.issues if issue.row_number == 2]
    assert any("requires SEQ_VENDOR=ONT" in message for message in messages)
    assert any("must not combine ONT_FASTQ_PREFIX" in message for message in messages)
    assert any("requires STAGE_DIRECTIVE=stage_data" in message for message in messages)


def test_precheck_manifest_rejects_giab_replicate_external_id(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    header = "\t".join(
        [
            "RUN_ID",
            "SAMPLE_ID",
            "EXPERIMENTID",
            "SAMPLE_TYPE",
            "LIB_PREP",
            "SEQ_VENDOR",
            "SEQ_PLATFORM",
            "LANE",
            "SEQBC_ID",
            "PATH_TO_CONCORDANCE_DATA_DIR",
            "ILMN_R1_FQ",
            "ILMN_R2_FQ",
            "STAGE_DIRECTIVE",
            "IS_POS_CTRL",
            "EXTERNAL_SAMPLE_ID",
        ]
    )
    concordance = (
        "/fsx/data/genomic_data/organism_annotations/H_sapiens/hg38/controls/giab/snv/v4.2.1/HG001"
    )

    def row(external_sample_id: str) -> str:
        return "\t".join(
            [
                "R1",
                "HG001-a",
                "exp1",
                "blood",
                "PCR-FREE",
                "ILMN",
                "NOVASEQ",
                "1",
                "BC1",
                concordance,
                "s3://bucket/HG001-a_R1.fastq.gz",
                "s3://bucket/HG001-a_R2.fastq.gz",
                "stage_data",
                "true",
                external_sample_id,
            ]
        )

    def fake_check_source_path(path: str, **_kwargs: object) -> None:
        if path.startswith("s3://bucket/") or path == concordance:
            return
        if any(path.endswith(f"/giabHC/HG001{suffix}") for suffix in module.GIAB_TRUTH_SUFFIXES):
            return
        raise module.CommandError(f"Path not accessible: {path}")

    monkeypatch.setattr(module, "check_source_path", fake_check_source_path)
    monkeypatch.setattr(module, "detect_giab_roi_dirs", lambda *args, **kwargs: ["giabHC"])

    bad_manifest = _write_manifest(tmp_path, header, [row("HG001-a")])
    bad_report, _bad_rows = module.precheck_manifest(
        bad_manifest,
        reference_bucket="s3://bucket",
        aws_env={},
        debug=False,
    )

    assert len(bad_report.issues) == 1
    assert bad_report.issues[0].field == "EXTERNAL_SAMPLE_ID"
    assert "EXTERNAL_SAMPLE_ID=HG001-a" in bad_report.issues[0].message

    good_manifest = _write_manifest(tmp_path, header, [row("HG001")])
    good_report, _good_rows = module.precheck_manifest(
        good_manifest,
        reference_bucket="s3://bucket",
        aws_env={},
        debug=False,
    )

    assert good_report.issues == ()
    assert good_report.source_objects_checked == 5
    assert good_report.concordance_dirs_checked == 1


def test_precheck_manifest_respects_explicit_false_positive_control(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    concordance = (
        "/fsx/data/genomic_data/organism_annotations/H_sapiens/hg38/controls/giab/snv/v4.2.1/HG001"
    )
    analysis_samples = _write_manifest(
        tmp_path,
        "\t".join(
            [
                "RUN_ID",
                "SAMPLE_ID",
                "EXPERIMENTID",
                "SAMPLE_TYPE",
                "LIB_PREP",
                "SEQ_VENDOR",
                "SEQ_PLATFORM",
                "LANE",
                "SEQBC_ID",
                "PATH_TO_CONCORDANCE_DATA_DIR",
                "ILMN_R1_FQ",
                "ILMN_R2_FQ",
                "STAGE_DIRECTIVE",
                "IS_POS_CTRL",
                "EXTERNAL_SAMPLE_ID",
            ]
        ),
        [
            "\t".join(
                [
                    "R1",
                    "HG001-a",
                    "exp1",
                    "blood",
                    "PCR-FREE",
                    "ILMN",
                    "NOVASEQ",
                    "1",
                    "BC1",
                    concordance,
                    "s3://bucket/HG001-a_R1.fastq.gz",
                    "s3://bucket/HG001-a_R2.fastq.gz",
                    "stage_data",
                    "false",
                    "HG001-a",
                ]
            )
        ],
    )

    monkeypatch.setattr(module, "check_source_path", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        module,
        "detect_giab_roi_dirs",
        lambda *args, **kwargs: pytest.fail("IS_POS_CTRL=false must not run GIAB truth checks"),
    )

    report, rows = module.precheck_manifest(
        analysis_samples,
        reference_bucket="s3://bucket",
        aws_env={},
        debug=False,
    )

    assert report.issues == ()
    assert rows[0].sample.is_pos_ctrl == "false"


def test_precheck_manifest_infers_positive_control_when_flag_is_omitted(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    concordance = (
        "/fsx/data/genomic_data/organism_annotations/H_sapiens/hg38/controls/giab/snv/v4.2.1/HG001"
    )
    analysis_samples = _write_manifest(
        tmp_path,
        "\t".join(
            [
                "RUN_ID",
                "SAMPLE_ID",
                "EXPERIMENTID",
                "SAMPLE_TYPE",
                "LIB_PREP",
                "SEQ_VENDOR",
                "SEQ_PLATFORM",
                "LANE",
                "SEQBC_ID",
                "PATH_TO_CONCORDANCE_DATA_DIR",
                "ILMN_R1_FQ",
                "ILMN_R2_FQ",
                "STAGE_DIRECTIVE",
                "EXTERNAL_SAMPLE_ID",
            ]
        ),
        [
            "\t".join(
                [
                    "R1",
                    "HG001",
                    "exp1",
                    "blood",
                    "PCR-FREE",
                    "ILMN",
                    "NOVASEQ",
                    "1",
                    "BC1",
                    concordance,
                    "s3://bucket/HG001_R1.fastq.gz",
                    "s3://bucket/HG001_R2.fastq.gz",
                    "stage_data",
                    "HG001",
                ]
            )
        ],
    )

    def fake_check_source_path(path: str, **_kwargs: object) -> None:
        if path.startswith("s3://bucket/") or path == concordance:
            return
        if any(path.endswith(f"/giabHC/HG001{suffix}") for suffix in module.GIAB_TRUTH_SUFFIXES):
            return
        raise module.CommandError(f"Path not accessible: {path}")

    monkeypatch.setattr(module, "check_source_path", fake_check_source_path)
    monkeypatch.setattr(module, "detect_giab_roi_dirs", lambda *args, **kwargs: ["giabHC"])

    report, rows = module.precheck_manifest(
        analysis_samples,
        reference_bucket="s3://bucket",
        aws_env={},
        debug=False,
    )

    assert report.issues == ()
    assert rows[0].sample.is_pos_ctrl == "true"


def test_precheck_manifest_rejects_explicit_positive_control_with_non_giab_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    concordance = "/fsx/data/non_giab_controls/HG001"
    analysis_samples = _write_manifest(
        tmp_path,
        "\t".join(
            [
                "RUN_ID",
                "SAMPLE_ID",
                "EXPERIMENTID",
                "SAMPLE_TYPE",
                "LIB_PREP",
                "SEQ_VENDOR",
                "SEQ_PLATFORM",
                "LANE",
                "SEQBC_ID",
                "PATH_TO_CONCORDANCE_DATA_DIR",
                "ILMN_R1_FQ",
                "ILMN_R2_FQ",
                "STAGE_DIRECTIVE",
                "IS_POS_CTRL",
                "EXTERNAL_SAMPLE_ID",
            ]
        ),
        [
            "\t".join(
                [
                    "R1",
                    "HG001",
                    "exp1",
                    "blood",
                    "PCR-FREE",
                    "ILMN",
                    "NOVASEQ",
                    "1",
                    "BC1",
                    concordance,
                    "s3://bucket/HG001_R1.fastq.gz",
                    "s3://bucket/HG001_R2.fastq.gz",
                    "stage_data",
                    "true",
                    "HG001",
                ]
            )
        ],
    )

    monkeypatch.setattr(module, "check_source_path", lambda *args, **kwargs: None)

    report, _rows = module.precheck_manifest(
        analysis_samples,
        reference_bucket="s3://bucket",
        aws_env={},
        debug=False,
    )

    assert any(
        issue.field == "IS_POS_CTRL" and "requires a GIAB concordance path" in issue.message
        for issue in report.issues
    )


def test_main_precheck_failure_does_not_stage_or_write_configs(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    analysis_samples = _write_manifest(
        tmp_path,
        _minimal_ilmn_header(),
        [_minimal_ilmn_row(r1="s3://missing/S1_R1.fastq.gz")],
    )
    forbidden_calls: list[str] = []

    def forbidden(name: str):
        def _inner(*_args: object, **_kwargs: object) -> object:
            forbidden_calls.append(name)
            raise AssertionError(f"{name} should not run after a failed precheck")

        return _inner

    def fake_check_source_path(path: str, **_kwargs: object) -> None:
        if path.startswith("s3://missing/"):
            raise module.CommandError(f"S3 object or prefix not accessible: {path}")

    monkeypatch.setattr(module, "check_source_path", fake_check_source_path)
    monkeypatch.setattr(module, "ensure_remote_stage_writable", forbidden("write-test"))
    monkeypatch.setattr(module, "stage_single_lane", forbidden("stage_single_lane"))
    monkeypatch.setattr(module, "stage_path_with_sidecars", forbidden("stage_path_with_sidecars"))
    monkeypatch.setattr(module, "stage_concordance", forbidden("stage_concordance"))
    monkeypatch.setattr(module, "aws_copy", forbidden("aws_copy"))
    monkeypatch.setattr(module, "write_tsv", forbidden("write_tsv"))

    rc = module.main(
        [
            str(analysis_samples),
            "--reference-bucket",
            "s3://bucket",
            "--profile",
            "test",
            "--region",
            "us-west-2",
            "--config-dir",
            str(tmp_path / "config"),
        ]
    )

    captured = capsys.readouterr()
    assert rc == 1
    assert "Precheck failed; no files were copied." in captured.err
    assert "Precheck passed" not in captured.out
    assert forbidden_calls == []
    assert not (tmp_path / "config").exists()


def test_main_precheck_only_clean_manifest_exits_without_copies(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    analysis_samples = _write_manifest(
        tmp_path,
        _minimal_ilmn_header(),
        [_minimal_ilmn_row()],
    )

    def forbidden(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("precheck-only should not stage, write configs, or upload")

    monkeypatch.setattr(module, "check_source_path", lambda *args, **kwargs: None)
    monkeypatch.setattr(module, "ensure_remote_stage_writable", forbidden)
    monkeypatch.setattr(module, "stage_single_lane", forbidden)
    monkeypatch.setattr(module, "stage_path_with_sidecars", forbidden)
    monkeypatch.setattr(module, "stage_concordance", forbidden)
    monkeypatch.setattr(module, "aws_copy", forbidden)
    monkeypatch.setattr(module, "write_tsv", forbidden)

    rc = module.main(
        [
            str(analysis_samples),
            "--reference-bucket",
            "s3://bucket",
            "--profile",
            "test",
            "--region",
            "us-west-2",
            "--precheck-only",
        ]
    )

    captured = capsys.readouterr()
    assert rc == 0
    assert "Precheck passed:" in captured.out
    assert captured.err == ""


def test_main_precheck_only_bad_manifest_reports_aggregated_errors(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    analysis_samples = _write_manifest(
        tmp_path,
        _minimal_ilmn_header(),
        [
            _minimal_ilmn_row(sample_id="S1", r1="s3://missing/S1_R1.fastq.gz"),
            _minimal_ilmn_row(sample_id="S2", r2="s3://missing/S2_R2.fastq.gz"),
        ],
    )

    def fake_check_source_path(path: str, **_kwargs: object) -> None:
        if path.startswith("s3://missing/"):
            raise module.CommandError(f"S3 object or prefix not accessible: {path}")

    monkeypatch.setattr(module, "check_source_path", fake_check_source_path)
    monkeypatch.setattr(
        module,
        "ensure_remote_stage_writable",
        lambda *args, **kwargs: pytest.fail("precheck failure must not run write test"),
    )

    rc = module.main(
        [
            str(analysis_samples),
            "--reference-bucket",
            "s3://bucket",
            "--profile",
            "test",
            "--region",
            "us-west-2",
            "--precheck-only",
        ]
    )

    captured = capsys.readouterr()
    assert rc == 1
    assert "Precheck failed; no files were copied." in captured.err
    assert "SAMPLE_ID=S1" in captured.err
    assert "SAMPLE_ID=S2" in captured.err
