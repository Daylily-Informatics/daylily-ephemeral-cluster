"""
Tests for file_metadata.py - FASTQ parsing, pairing, and TSV generation.
"""

import pytest
from daylib.file_metadata import (
    AnalysisInput,
    LibraryPrep,
    SampleType,
    SequencingPlatform,
    SequencingVendor,
    create_analysis_inputs_from_files,
    generate_stage_samples_tsv,
    pair_fastq_files,
    parse_fastq_filename,
)


class TestParseFastqFilename:
    """Test FASTQ filename parsing."""
    
    def test_parse_illumina_bcl_convert_format(self):
        """Test Illumina BCL Convert format: Sample_S1_L001_R1_001.fastq.gz"""
        sample_id, read_num, lane = parse_fastq_filename("Sample_S1_L001_R1_001.fastq.gz")
        assert sample_id == "Sample"
        assert read_num == 1
        assert lane == "001"
    
    def test_parse_underscore_r1_format(self):
        """Test sample_R1.fastq.gz format."""
        sample_id, read_num, lane = parse_fastq_filename("sample_R1.fastq.gz")
        assert sample_id == "sample"
        assert read_num == 1
        assert lane is None
    
    def test_parse_underscore_r2_format(self):
        """Test sample_R2.fastq.gz format."""
        sample_id, read_num, lane = parse_fastq_filename("sample_R2.fastq.gz")
        assert sample_id == "sample"
        assert read_num == 2
        assert lane is None
    
    def test_parse_dot_r1_format(self):
        """Test sample.R1.fastq.gz format."""
        sample_id, read_num, lane = parse_fastq_filename("sample.R1.fastq.gz")
        assert sample_id == "sample"
        assert read_num == 1
        assert lane is None
    
    def test_parse_numeric_1_format(self):
        """Test sample_1.fastq.gz format."""
        sample_id, read_num, lane = parse_fastq_filename("sample_1.fastq.gz")
        assert sample_id == "sample"
        assert read_num == 1
        assert lane is None
    
    def test_parse_numeric_2_format(self):
        """Test sample_2.fastq.gz format."""
        sample_id, read_num, lane = parse_fastq_filename("sample_2.fastq.gz")
        assert sample_id == "sample"
        assert read_num == 2
        assert lane is None
    
    def test_parse_uncompressed_fastq(self):
        """Test uncompressed .fastq file."""
        sample_id, read_num, lane = parse_fastq_filename("sample_R1.fastq")
        assert sample_id == "sample"
        assert read_num == 1
    
    def test_parse_fq_extension(self):
        """Test .fq extension."""
        sample_id, read_num, lane = parse_fastq_filename("sample_R1.fq.gz")
        assert sample_id == "sample"
        assert read_num == 1
    
    def test_parse_unknown_format_defaults_to_r1(self):
        """Test unknown format defaults to R1."""
        sample_id, read_num, lane = parse_fastq_filename("unknown_file.fastq.gz")
        assert sample_id == "unknown_file"
        assert read_num == 1
        assert lane is None
    
    def test_parse_complex_sample_name(self):
        """Test complex sample names with underscores."""
        sample_id, read_num, lane = parse_fastq_filename("HG002_NA24385_son_R1.fastq.gz")
        assert sample_id == "HG002_NA24385_son"
        assert read_num == 1


class TestPairFastqFiles:
    """Test R1/R2 pairing logic."""
    
    def test_pair_simple_r1_r2(self):
        """Test pairing simple R1/R2 files."""
        files = [
            "s3://bucket/sample_R1.fastq.gz",
            "s3://bucket/sample_R2.fastq.gz",
        ]
        pairs = pair_fastq_files(files)
        assert len(pairs) == 1
        assert pairs[0][0] == "sample"
        assert pairs[0][1] == "s3://bucket/sample_R1.fastq.gz"
        assert pairs[0][2] == "s3://bucket/sample_R2.fastq.gz"
    
    def test_pair_multiple_samples(self):
        """Test pairing multiple samples."""
        files = [
            "s3://bucket/sample1_R1.fastq.gz",
            "s3://bucket/sample1_R2.fastq.gz",
            "s3://bucket/sample2_R1.fastq.gz",
            "s3://bucket/sample2_R2.fastq.gz",
        ]
        pairs = pair_fastq_files(files)
        assert len(pairs) == 2
        assert pairs[0][0] == "sample1"
        assert pairs[1][0] == "sample2"
    
    def test_pair_unpaired_r1_only(self):
        """Test unpaired R1-only files."""
        files = [
            "s3://bucket/sample_R1.fastq.gz",
        ]
        pairs = pair_fastq_files(files)
        assert len(pairs) == 1
        assert pairs[0][0] == "sample"
        assert pairs[0][1] == "s3://bucket/sample_R1.fastq.gz"
        assert pairs[0][2] is None
    
    def test_pair_sorted_output(self):
        """Test that output is sorted by sample ID."""
        files = [
            "s3://bucket/zebra_R1.fastq.gz",
            "s3://bucket/apple_R1.fastq.gz",
            "s3://bucket/banana_R1.fastq.gz",
        ]
        pairs = pair_fastq_files(files)
        assert pairs[0][0] == "apple"
        assert pairs[1][0] == "banana"
        assert pairs[2][0] == "zebra"
    
    def test_pair_mixed_formats(self):
        """Test pairing with mixed naming formats."""
        files = [
            "s3://bucket/sample1_R1.fastq.gz",
            "s3://bucket/sample1_R2.fastq.gz",
            "s3://bucket/sample2.R1.fastq.gz",
            "s3://bucket/sample2.R2.fastq.gz",
        ]
        pairs = pair_fastq_files(files)
        assert len(pairs) == 2


class TestCreateAnalysisInputs:
    """Test AnalysisInput creation from files."""
    
    def test_create_from_paired_files(self):
        """Test creating analysis inputs from paired files."""
        files = [
            "s3://bucket/sample_R1.fastq.gz",
            "s3://bucket/sample_R2.fastq.gz",
        ]
        inputs = create_analysis_inputs_from_files(files)
        
        assert len(inputs) == 1
        assert inputs[0].sample_id == "sample"
        assert inputs[0].r1_fastq == "s3://bucket/sample_R1.fastq.gz"
        assert inputs[0].r2_fastq == "s3://bucket/sample_R2.fastq.gz"
    
    def test_create_with_defaults(self):
        """Test that defaults are applied."""
        files = ["s3://bucket/sample_R1.fastq.gz"]
        inputs = create_analysis_inputs_from_files(files)
        
        assert inputs[0].seq_platform == SequencingPlatform.ILLUMINA_NOVASEQ_X
        assert inputs[0].seq_vendor == SequencingVendor.ILLUMINA
        assert inputs[0].lib_prep == LibraryPrep.PCR_FREE_WGS
        assert inputs[0].sample_type == SampleType.BLOOD
    
    def test_create_with_custom_defaults(self):
        """Test custom default values."""
        files = ["s3://bucket/sample_R1.fastq.gz"]
        inputs = create_analysis_inputs_from_files(
            files,
            default_platform=SequencingPlatform.ILLUMINA_HISEQ_X,
            default_lib_prep=LibraryPrep.WES,
            default_sample_type=SampleType.TISSUE,
        )
        
        assert inputs[0].seq_platform == SequencingPlatform.ILLUMINA_HISEQ_X
        assert inputs[0].lib_prep == LibraryPrep.WES
        assert inputs[0].sample_type == SampleType.TISSUE
    
    def test_create_unpaired_r1_only(self):
        """Test unpaired R1-only files."""
        files = ["s3://bucket/sample_R1.fastq.gz"]
        inputs = create_analysis_inputs_from_files(files)
        
        assert len(inputs) == 1
        assert inputs[0].r1_fastq == "s3://bucket/sample_R1.fastq.gz"
        assert inputs[0].r2_fastq == ""


class TestAnalysisInputTsvRow:
    """Test AnalysisInput TSV row generation."""
    
    def test_to_tsv_row_complete(self):
        """Test complete TSV row generation."""
        analysis_input = AnalysisInput(
            sample_id="sample1",
            external_sample_id="HG002",
            experiment_id="exp1",
            run_id="R0",
            sample_type=SampleType.BLOOD,
            lib_prep=LibraryPrep.PCR_FREE_WGS,
            seq_vendor=SequencingVendor.ILLUMINA,
            seq_platform=SequencingPlatform.ILLUMINA_NOVASEQ_X,
            lane=1,
            barcode_id="S1",
            r1_fastq="s3://bucket/sample1_R1.fastq.gz",
            r2_fastq="s3://bucket/sample1_R2.fastq.gz",
        )
        
        row = analysis_input.to_tsv_row()
        
        assert row["SAMPLE_ID"] == "sample1"
        assert row["EXTERNAL_SAMPLE_ID"] == "HG002"
        assert row["RUN_ID"] == "R0"
        assert row["SAMPLE_TYPE"] == "blood"
        assert row["LIB_PREP"] == "noampwgs"
        assert row["SEQ_VENDOR"] == "ILMN"
        assert row["SEQ_PLATFORM"] == "NOVASEQX"
        assert row["LANE"] == "1"
        assert row["SEQBC_ID"] == "S1"
        assert row["R1_FQ"] == "s3://bucket/sample1_R1.fastq.gz"
        assert row["R2_FQ"] == "s3://bucket/sample1_R2.fastq.gz"
    
    def test_to_tsv_row_controls(self):
        """Test control sample flags."""
        analysis_input = AnalysisInput(
            sample_id="control_pos",
            external_sample_id="control",
            r1_fastq="s3://bucket/control_R1.fastq.gz",
            is_positive_control=True,
        )
        
        row = analysis_input.to_tsv_row()
        assert row["IS_POS_CTRL"] == "true"
        assert row["IS_NEG_CTRL"] == "false"


class TestGenerateStageSamplesTsv:
    """Test TSV generation."""
    
    def test_generate_with_header(self):
        """Test TSV generation with header."""
        inputs = [
            AnalysisInput(
                sample_id="sample1",
                external_sample_id="HG002",
                r1_fastq="s3://bucket/sample1_R1.fastq.gz",
                r2_fastq="s3://bucket/sample1_R2.fastq.gz",
            ),
        ]
        
        tsv = generate_stage_samples_tsv(inputs, include_header=True)
        lines = tsv.split("\n")
        
        assert len(lines) == 2  # header + 1 row
        assert "RUN_ID" in lines[0]
        assert "SAMPLE_ID" in lines[0]
        assert "sample1" in lines[1]
    
    def test_generate_without_header(self):
        """Test TSV generation without header."""
        inputs = [
            AnalysisInput(
                sample_id="sample1",
                external_sample_id="HG002",
                r1_fastq="s3://bucket/sample1_R1.fastq.gz",
            ),
        ]
        
        tsv = generate_stage_samples_tsv(inputs, include_header=False)
        lines = tsv.split("\n")
        
        assert len(lines) == 1
        assert "RUN_ID" not in lines[0]
        assert "sample1" in lines[0]
    
    def test_generate_multiple_samples(self):
        """Test TSV with multiple samples."""
        inputs = [
            AnalysisInput(sample_id="s1", external_sample_id="s1", r1_fastq="s3://b/s1_R1.fq.gz"),
            AnalysisInput(sample_id="s2", external_sample_id="s2", r1_fastq="s3://b/s2_R1.fq.gz"),
            AnalysisInput(sample_id="s3", external_sample_id="s3", r1_fastq="s3://b/s3_R1.fq.gz"),
        ]
        
        tsv = generate_stage_samples_tsv(inputs, include_header=True)
        lines = tsv.split("\n")
        
        assert len(lines) == 4  # header + 3 rows
        assert "s1" in lines[1]
        assert "s2" in lines[2]
        assert "s3" in lines[3]
    
    def test_column_order(self):
        """Test that columns are in correct order."""
        inputs = [
            AnalysisInput(
                sample_id="sample1",
                external_sample_id="HG002",
                r1_fastq="s3://bucket/sample1_R1.fastq.gz",
            ),
        ]
        
        tsv = generate_stage_samples_tsv(inputs, include_header=True)
        header = tsv.split("\n")[0]
        columns = header.split("\t")
        
        # Verify first and last columns
        assert columns[0] == "RUN_ID"
        assert columns[-1] == "EXTERNAL_SAMPLE_ID"
        assert len(columns) == 20  # Should have exactly 20 columns

