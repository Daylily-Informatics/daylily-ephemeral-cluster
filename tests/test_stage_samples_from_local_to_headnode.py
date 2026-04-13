from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from importlib.machinery import SourceFileLoader

import pytest


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "bin"
    / "daylily-stage-samples-from-local-to-headnode"
)


def _load_stage_script():
    loader = SourceFileLoader("daylily_stage_samples_from_local_to_headnode", str(SCRIPT_PATH))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[loader.name] = module
    loader.exec_module(module)
    return module


def test_headnode_visible_path_maps_data_prefix_to_fsx() -> None:
    module = _load_stage_script()

    assert module.headnode_visible_path("/data") == "/fsx/data"
    assert (
        module.headnode_visible_path("/data/staged_sample_data/remote_stage_1")
        == "/fsx/data/staged_sample_data/remote_stage_1"
    )
    assert module.headnode_visible_path("/tmp/local") == "/tmp/local"


def test_process_samples_emits_dayoa_compatible_ilmn_giab_rows(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = _load_stage_script()
    analysis_samples = tmp_path / "analysis_samples.tsv"
    analysis_samples.write_text(
        "RUN_ID\tSAMPLE_ID\tEXPERIMENTID\tSAMPLE_TYPE\tLIB_PREP\tSEQ_VENDOR\tSEQ_PLATFORM\tLANE\tSEQBC_ID\tPATH_TO_CONCORDANCE_DATA_DIR\tR1_FQ\tR2_FQ\tSTAGE_DIRECTIVE\tSTAGE_TARGET\tSUBSAMPLE_PCT\tIS_POS_CTRL\tIS_NEG_CTRL\tN_X\tN_Y\tEXTERNAL_SAMPLE_ID\n"
        "R0\tHG002\tx0p1\tblood\tnoampwgs\tILMN\tNOVASEQX\t0\tS1\t/fsx/data/genomic_data/organism_annotations/H_sapiens/hg38/controls/giab/snv/v4.2.1/HG002/\t/tmp/HG002_0.1x_R1.fastq.gz\t/tmp/HG002_0.1x_R2.fastq.gz\tstage_data\t/fsx/staged_sample_data/\tna\tfalse\tfalse\t1\t1\tHG002\n",
        encoding="utf-8",
    )
    stage = module.StagePaths(
        remote_fsx_root="/data/staged_sample_data",
        remote_stage_name="remote_stage_test",
        remote_fsx_stage="/data/staged_sample_data/remote_stage_test",
        remote_s3_stage="s3://bucket/data/staged_sample_data/remote_stage_test",
    )

    monkeypatch.setattr(module, "validate_sources", lambda *args, **kwargs: None)
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
        stage,
        reference_bucket="s3://bucket",
        aws_env={},
        debug=False,
    )

    assert module.ILMN_TRIM_READ_LENGTH in module.UNITS_HEADER
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
    assert units_rows == [
        {
            "RUNID": "R0",
            "SAMPLEID": "HG002",
            "EXPERIMENTID": "x0p1",
            "LANEID": "0",
            "BARCODEID": "S1",
            "LIBPREP": "PCR-FREE",
            "SEQ_VENDOR": "ILMN",
            "SEQ_PLATFORM": "NOVASEQ",
            "ILMN_R1_PATH": "/data/staged_sample_data/remote_stage_test/R0_HG002-NOVASEQ-PCR-FREE-blood-x0p1_S1_0/HG002_0.1x_R1.fastq.gz",
            "ILMN_R2_PATH": "/data/staged_sample_data/remote_stage_test/R0_HG002-NOVASEQ-PCR-FREE-blood-x0p1_S1_0/HG002_0.1x_R2.fastq.gz",
            "PACBIO_R1_PATH": "",
            "PACBIO_R2_PATH": "",
            "ONT_R1_PATH": "",
            "ONT_R2_PATH": "",
            "UG_R1_PATH": "",
            "UG_R2_PATH": "",
            "SUBSAMPLE_PCT": "na",
            "ILMN_TRIM_READ_LENGTH": "",
            "SAMPLEUSE": "posControl",
            "BWA_KMER": "19",
            "DEEP_MODEL": "",
            "ULTIMA_CRAM": "",
            "ULTIMA_CRAM_ALIGNER": "",
            "ULTIMA_CRAM_SNV_CALLER": "",
            "ONT_CRAM": "",
            "ONT_CRAM_ALIGNER": "",
            "ONT_CRAM_SNV_CALLER": "",
            "PB_BAM": "",
            "PB_BAM_ALIGNER": "",
            "PB_BAM_SNV_CALLER": "",
        }
    ]


def test_process_samples_rejects_duplicate_multi_lane_fastq_pairs(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = _load_stage_script()
    analysis_samples = tmp_path / "analysis_samples.tsv"
    analysis_samples.write_text(
        "RUN_ID\tSAMPLE_ID\tEXPERIMENTID\tSAMPLE_TYPE\tLIB_PREP\tSEQ_VENDOR\tSEQ_PLATFORM\tLANE\tSEQBC_ID\tPATH_TO_CONCORDANCE_DATA_DIR\tR1_FQ\tR2_FQ\tSTAGE_DIRECTIVE\tSTAGE_TARGET\tSUBSAMPLE_PCT\tIS_POS_CTRL\tIS_NEG_CTRL\tN_X\tN_Y\tEXTERNAL_SAMPLE_ID\n"
        "R0\tHG002\tx3\tblood\tnoampwgs\tILMN\tNOVASEQX\t1\tS1\t/fsx/data/genomic_data/organism_annotations/H_sapiens/hg38/controls/giab/snv/v4.2.1/HG002/\ts3://bucket/HG002_1x_R1.fastq.gz\ts3://bucket/HG002_1x_R2.fastq.gz\tstage_data\t/fsx/staged_sample_data/\tna\tfalse\tfalse\t1\t1\tHG002\n"
        "R0\tHG002\tx3\tblood\tnoampwgs\tILMN\tNOVASEQX\t2\tS0\t/fsx/data/genomic_data/organism_annotations/H_sapiens/hg38/controls/giab/snv/v4.2.1/HG002/\ts3://bucket/HG002_1x_R1.fastq.gz\ts3://bucket/HG002_1x_R2.fastq.gz\tstage_data\t/fsx/staged_sample_data/\tna\tfalse\tfalse\t1\t1\tHG002\n",
        encoding="utf-8",
    )
    stage = module.StagePaths(
        remote_fsx_root="/data/staged_sample_data",
        remote_stage_name="remote_stage_test",
        remote_fsx_stage="/data/staged_sample_data/remote_stage_test",
        remote_s3_stage="s3://bucket/data/staged_sample_data/remote_stage_test",
    )

    monkeypatch.setattr(module, "validate_sources", lambda *args, **kwargs: None)

    with pytest.raises(module.CommandError, match="Duplicate FASTQ lane sources are not supported"):
        module.process_samples(
            analysis_samples,
            stage,
            reference_bucket="s3://bucket",
            aws_env={},
            debug=False,
        )
