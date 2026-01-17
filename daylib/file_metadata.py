"""
File Metadata Module for Daylily

Provides comprehensive metadata capture for genomic files following GA4GH standards:
- Subject/Individual: Source organism identifier
- Biosample: Physical specimen (tissue type, collection info)
- Sequencing Library: Preparation method, protocols
- Sequencing Run: Platform parameters, run metrics
- FASTQ Files: Direct outputs with full provenance

This module supports the Workset Manifest Generator and file registration system.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import PurePosixPath
from typing import Any, Dict, List, Optional, Tuple


class SequencingPlatform(str, Enum):
    """Supported sequencing platforms."""
    ILLUMINA_NOVASEQ_X = "NOVASEQX"
    ILLUMINA_NOVASEQ_6000 = "NOVASEQ6000"
    ILLUMINA_HISEQ_X = "HISEQX"
    ILLUMINA_MISEQ = "MISEQ"
    PACBIO_REVIO = "REVIO"
    PACBIO_SEQUEL = "SEQUEL"
    ONT_PROMETHION = "PROMETHION"
    ONT_MINION = "MINION"


class SequencingVendor(str, Enum):
    """Sequencing technology vendors."""
    ILLUMINA = "ILMN"
    PACBIO = "PACBIO"
    OXFORD_NANOPORE = "ONT"
    BGI = "BGI"
    ELEMENT = "ELEMENT"


class LibraryPrep(str, Enum):
    """Library preparation methods."""
    PCR_FREE_WGS = "noampwgs"
    PCR_WGS = "pcr"
    WES = "wes"
    TARGETED = "targeted"
    RNA_SEQ = "rnaseq"
    AMPLICON = "amplicon"


class SampleType(str, Enum):
    """Biosample tissue types."""
    BLOOD = "blood"
    SALIVA = "saliva"
    TISSUE = "tissue"
    TUMOR = "tumor"
    NORMAL = "normal"
    CFDNA = "cfDNA"
    FFPE = "ffpe"
    ORGANOID = "organoid"


@dataclass
class Subject:
    """
    GA4GH Subject/Individual representation.
    The source organism from which biosamples are derived.
    """
    subject_id: str  # Unique subject identifier (e.g., patient ID, HG002)
    species: str = "Homo sapiens"
    sex: Optional[str] = None  # male, female, unknown
    cohort: Optional[str] = None  # Study or cohort name
    
    def __post_init__(self):
        if not self.subject_id:
            raise ValueError("subject_id is required")


@dataclass
class Biosample:
    """
    GA4GH Biosample representation.
    A physical specimen collected from a Subject.
    """
    biosample_id: str
    subject_id: str  # Reference to Subject
    sample_type: SampleType = SampleType.BLOOD
    tissue_type: Optional[str] = None
    collection_date: Optional[datetime] = None
    preservation_method: Optional[str] = None  # fresh, frozen, ffpe
    tumor_fraction: Optional[float] = None  # For tumor samples
    
    def __post_init__(self):
        if not self.biosample_id:
            raise ValueError("biosample_id is required")


@dataclass
class SequencingLibrary:
    """
    Sequencing library prepared from a Biosample.
    Contains preparation method and target specifications.
    """
    library_id: str
    biosample_id: str  # Reference to Biosample
    lib_prep: LibraryPrep = LibraryPrep.PCR_FREE_WGS
    target_coverage: Optional[float] = None  # Target sequencing depth
    insert_size: Optional[int] = None  # Mean insert size
    protocol_id: Optional[str] = None  # Lab protocol reference
    
    def __post_init__(self):
        if not self.library_id:
            raise ValueError("library_id is required")


@dataclass
class SequencingRun:
    """
    A sequencing run that produces FASTQ files.
    Links to the sequencing platform and run parameters.
    """
    run_id: str
    library_id: str  # Reference to SequencingLibrary
    vendor: SequencingVendor = SequencingVendor.ILLUMINA
    platform: SequencingPlatform = SequencingPlatform.ILLUMINA_NOVASEQ_X
    lane: int = 0
    barcode_id: str = "S1"  # Sample index/barcode
    flowcell_id: Optional[str] = None
    run_date: Optional[datetime] = None
    
    def __post_init__(self):
        if not self.run_id:
            raise ValueError("run_id is required")


@dataclass
class FASTQFile:
    """
    A FASTQ file with full provenance chain.
    The actual file that will be processed by the pipeline.
    """
    file_id: str  # Unique file identifier
    s3_uri: str  # Full S3 URI (s3://bucket/path/file.fastq.gz)
    run_id: str  # Reference to SequencingRun
    read_number: int  # 1 for R1, 2 for R2

    # File metadata
    file_size_bytes: Optional[int] = None
    md5_checksum: Optional[str] = None
    read_count: Optional[int] = None

    # Quality metrics
    mean_quality_score: Optional[float] = None
    percent_q30: Optional[float] = None

    @property
    def filename(self) -> str:
        """Extract filename from S3 URI."""
        return PurePosixPath(self.s3_uri).name

    @property
    def bucket(self) -> Optional[str]:
        """Extract bucket name from S3 URI."""
        if self.s3_uri.startswith("s3://"):
            parts = self.s3_uri[5:].split("/", 1)
            return parts[0] if parts else None
        return None


@dataclass
class AnalysisInput:
    """
    An analysis input for the pipeline (row in stage_samples.tsv).
    Combines all metadata into the format needed for processing.

    This is the GA4GH-aligned term for what was previously called "sample".
    """
    # Identifiers
    sample_id: str  # Pipeline input identifier (SAMPLE_ID column)
    external_sample_id: str  # Subject/individual ID (EXTERNAL_SAMPLE_ID column)
    experiment_id: str = ""  # Experiment grouping (EXPERIMENTID column)
    run_id: str = "R0"  # Analysis run ID (RUN_ID column)

    # Biosample metadata
    sample_type: SampleType = SampleType.BLOOD

    # Library metadata
    lib_prep: LibraryPrep = LibraryPrep.PCR_FREE_WGS

    # Sequencing metadata
    seq_vendor: SequencingVendor = SequencingVendor.ILLUMINA
    seq_platform: SequencingPlatform = SequencingPlatform.ILLUMINA_NOVASEQ_X
    lane: int = 0
    barcode_id: str = "S1"

    # FASTQ files
    r1_fastq: str = ""  # S3 URI to R1 file
    r2_fastq: str = ""  # S3 URI to R2 file (optional for single-end)

    # Staging configuration
    stage_directive: str = "stage_data"
    stage_target: str = "/fsx/staged_sample_data/"
    subsample_pct: str = "na"

    # QC configuration
    concordance_dir: str = ""  # Path to truth VCFs for validation
    is_positive_control: bool = False
    is_negative_control: bool = False

    # Processing hints
    n_x: int = 1  # Ploidy X
    n_y: int = 1  # Ploidy Y

    # User-defined tags for grouping/filtering
    tags: List[str] = field(default_factory=list)

    def to_tsv_row(self) -> Dict[str, str]:
        """Convert to stage_samples.tsv row format."""
        return {
            "RUN_ID": self.run_id,
            "SAMPLE_ID": self.sample_id,
            "EXPERIMENTID": self.experiment_id or self.sample_id,
            "SAMPLE_TYPE": self.sample_type.value if isinstance(self.sample_type, SampleType) else self.sample_type,
            "LIB_PREP": self.lib_prep.value if isinstance(self.lib_prep, LibraryPrep) else self.lib_prep,
            "SEQ_VENDOR": self.seq_vendor.value if isinstance(self.seq_vendor, SequencingVendor) else self.seq_vendor,
            "SEQ_PLATFORM": self.seq_platform.value if isinstance(self.seq_platform, SequencingPlatform) else self.seq_platform,
            "LANE": str(self.lane),
            "SEQBC_ID": self.barcode_id,
            "PATH_TO_CONCORDANCE_DATA_DIR": self.concordance_dir,
            "R1_FQ": self.r1_fastq,
            "R2_FQ": self.r2_fastq,
            "STAGE_DIRECTIVE": self.stage_directive,
            "STAGE_TARGET": self.stage_target,
            "SUBSAMPLE_PCT": self.subsample_pct,
            "IS_POS_CTRL": "true" if self.is_positive_control else "false",
            "IS_NEG_CTRL": "true" if self.is_negative_control else "false",
            "N_X": str(self.n_x),
            "N_Y": str(self.n_y),
            "EXTERNAL_SAMPLE_ID": self.external_sample_id or self.sample_id,
        }


def parse_fastq_filename(filename: str) -> Tuple[str, int, Optional[str]]:
    """
    Parse a FASTQ filename to extract sample ID and read number.

    Supports patterns:
    - sample_R1.fastq.gz / sample_R2.fastq.gz
    - sample.R1.fastq.gz / sample.R2.fastq.gz
    - sample_1.fastq.gz / sample_2.fastq.gz
    - sample_L001_R1_001.fastq.gz (Illumina BCL Convert format)

    Returns:
        Tuple of (sample_id, read_number, lane)
    """
    # Remove extensions
    base = re.sub(r'\.(fastq|fq)(\.gz)?$', '', filename, flags=re.IGNORECASE)

    # Try Illumina BCL Convert format: Sample_S1_L001_R1_001
    bcl_match = re.match(r'^(.+)_S\d+_L(\d+)_R([12])_\d+$', base)
    if bcl_match:
        return bcl_match.group(1), int(bcl_match.group(3)), bcl_match.group(2)

    # Try common patterns
    patterns = [
        r'^(.+)[_.]R([12])$',  # sample_R1, sample.R1
        r'^(.+)[_.]([12])$',   # sample_1, sample.1
        r'^(.+)_R([12])_\d+$', # sample_R1_001
    ]

    for pattern in patterns:
        match = re.match(pattern, base)
        if match:
            return match.group(1), int(match.group(2)), None

    # No pattern matched - assume it's R1
    return base, 1, None


def pair_fastq_files(files: List[str]) -> List[Tuple[str, str, Optional[str]]]:
    """
    Pair R1 and R2 FASTQ files based on naming patterns.

    Args:
        files: List of FASTQ file paths or URIs

    Returns:
        List of tuples: (sample_id, r1_path, r2_path)
        r2_path may be None for unpaired files.
    """
    # Group by sample ID
    samples: Dict[str, Dict[int, str]] = {}

    for filepath in files:
        filename = PurePosixPath(filepath).name
        sample_id, read_num, _ = parse_fastq_filename(filename)

        if sample_id not in samples:
            samples[sample_id] = {}
        samples[sample_id][read_num] = filepath

    # Build paired list
    results = []
    for sample_id, reads in sorted(samples.items()):
        r1 = reads.get(1)
        r2 = reads.get(2)
        if r1:  # Only include if we have at least R1
            results.append((sample_id, r1, r2))

    return results


def create_analysis_inputs_from_files(
    files: List[str],
    run_id: str = "R0",
    stage_target: str = "/fsx/staged_sample_data/",
    default_platform: SequencingPlatform = SequencingPlatform.ILLUMINA_NOVASEQ_X,
    default_vendor: SequencingVendor = SequencingVendor.ILLUMINA,
    default_sample_type: SampleType = SampleType.BLOOD,
    default_lib_prep: LibraryPrep = LibraryPrep.PCR_FREE_WGS,
) -> List[AnalysisInput]:
    """
    Create AnalysisInput objects from a list of FASTQ file paths.

    Automatically pairs R1/R2 files and applies default metadata.
    """
    paired = pair_fastq_files(files)

    inputs = []
    for sample_id, r1, r2 in paired:
        analysis_input = AnalysisInput(
            sample_id=sample_id,
            external_sample_id=sample_id,
            run_id=run_id,
            sample_type=default_sample_type,
            lib_prep=default_lib_prep,
            seq_vendor=default_vendor,
            seq_platform=default_platform,
            r1_fastq=r1,
            r2_fastq=r2 or "",
            stage_target=stage_target,
        )
        inputs.append(analysis_input)

    return inputs


def generate_stage_samples_tsv(
    inputs: List[AnalysisInput],
    include_header: bool = True,
) -> str:
    """
    Generate stage_samples.tsv content from AnalysisInput objects.

    Args:
        inputs: List of AnalysisInput objects
        include_header: Whether to include the header row

    Returns:
        TSV-formatted string ready to write to file
    """
    # Column order matching etc/analysis_samples_template.tsv
    columns = [
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

    lines = []

    if include_header:
        lines.append("\t".join(columns))

    for analysis_input in inputs:
        row = analysis_input.to_tsv_row()
        values = [row.get(col, "") for col in columns]
        lines.append("\t".join(values))

    return "\n".join(lines)


# TSV column definitions for documentation and validation
TSV_COLUMN_DEFINITIONS = {
    "RUN_ID": "Analysis run identifier (e.g., R0, R1)",
    "SAMPLE_ID": "Unique sample identifier for the pipeline",
    "EXPERIMENTID": "Experiment grouping identifier",
    "SAMPLE_TYPE": "Biosample type (blood, saliva, tissue, tumor, normal, cfDNA, ffpe)",
    "LIB_PREP": "Library preparation method (noampwgs, pcr, wes, targeted, rnaseq)",
    "SEQ_VENDOR": "Sequencing vendor (ILMN, PACBIO, ONT, BGI, ELEMENT)",
    "SEQ_PLATFORM": "Sequencing platform model",
    "LANE": "Flowcell lane number (0 for merged)",
    "SEQBC_ID": "Sample barcode/index ID",
    "PATH_TO_CONCORDANCE_DATA_DIR": "Path to truth VCFs for validation",
    "R1_FQ": "S3 URI to R1 FASTQ file",
    "R2_FQ": "S3 URI to R2 FASTQ file (empty for single-end)",
    "STAGE_DIRECTIVE": "Staging directive (stage_data, skip_staging)",
    "STAGE_TARGET": "Target directory for staged files",
    "SUBSAMPLE_PCT": "Subsampling percentage (na for full data)",
    "IS_POS_CTRL": "Is this a positive control sample (true/false)",
    "IS_NEG_CTRL": "Is this a negative control sample (true/false)",
    "N_X": "Ploidy of X chromosome",
    "N_Y": "Ploidy of Y chromosome",
    "EXTERNAL_SAMPLE_ID": "External/subject identifier",
}
