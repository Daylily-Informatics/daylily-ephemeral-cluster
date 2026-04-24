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


def test_headnode_visible_path_maps_data_prefix_to_fsx() -> None:
    assert module.headnode_visible_path("/data") == "/fsx/data"
    assert (
        module.headnode_visible_path("/data/staged_sample_data/remote_stage_1")
        == "/fsx/data/staged_sample_data/remote_stage_1"
    )
    assert module.headnode_visible_path("/tmp/local") == "/tmp/local"


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

    samples_rows, units_rows, created_files, run_ids = module.process_samples(
        analysis_samples,
        _stage_paths(),
        reference_bucket="s3://bucket",
        aws_env={},
        debug=False,
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
            "IS_POSITIVE_CONTROL": "true",
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
    assert units_row["SAMPLEUSE"] == "posControl"
    assert units_row["BWA_KMER"] == "19"
    assert units_row["ONT_CRAM"] == ""
    assert units_row["PB_BAM"] == ""
    assert units_row["ROCHE_BAM"] == ""


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

    with pytest.raises(module.CommandError, match="Duplicate FASTQ lane sources are not supported"):
        module.process_samples(
            analysis_samples,
            _stage_paths(),
            reference_bucket="s3://bucket",
            aws_env={},
            debug=False,
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

    samples_rows, units_rows, created_files, run_ids = module.process_samples(
        analysis_samples,
        _stage_paths(),
        reference_bucket="s3://bucket",
        aws_env={},
        debug=False,
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

    _samples_rows, units_rows, created_files, run_ids = module.process_samples(
        analysis_samples,
        _stage_paths(),
        reference_bucket="s3://bucket",
        aws_env={},
        debug=False,
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

    _samples_rows, units_rows, created_files, _run_ids = module.process_samples(
        analysis_samples,
        _stage_paths(),
        reference_bucket="s3://bucket",
        aws_env={},
        debug=False,
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

    _samples_rows, units_rows, created_files, run_ids = module.process_samples(
        analysis_samples,
        _stage_paths(),
        reference_bucket="s3://bucket",
        aws_env={},
        debug=False,
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

    with pytest.raises(module.CommandError, match="Local path not found"):
        module.process_samples(
            analysis_samples,
            _stage_paths(),
            reference_bucket="s3://bucket",
            aws_env={},
            debug=False,
        )


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
