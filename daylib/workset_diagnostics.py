"""Enhanced error diagnostics for workset processing.

Provides structured error codes, log analysis, and remediation suggestions
for troubleshooting workset failures.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Pattern

LOGGER = logging.getLogger("daylily.workset_diagnostics")


class ErrorSeverity(str, Enum):
    """Error severity levels."""
    CRITICAL = "critical"  # System-wide impact, immediate action required
    ERROR = "error"  # Workset failure, investigation needed
    WARNING = "warning"  # Potential issue, monitoring advised
    INFO = "info"  # Informational, no action needed


class ErrorCategory(str, Enum):
    """Error categories for classification."""
    RESOURCE = "resource"  # Memory, CPU, disk issues
    NETWORK = "network"  # Connectivity, timeout issues
    DATA = "data"  # Input data quality issues
    CONFIG = "config"  # Configuration errors
    AWS = "aws"  # AWS service errors
    PIPELINE = "pipeline"  # Bioinformatics pipeline errors
    CLUSTER = "cluster"  # HPC cluster issues
    AUTH = "auth"  # Authentication/authorization
    UNKNOWN = "unknown"  # Unclassified errors


@dataclass
class ErrorCode:
    """Structured error code definition."""
    code: str  # e.g., "WS-RES-001"
    name: str  # Human-readable name
    description: str  # Detailed description
    severity: ErrorSeverity
    category: ErrorCategory
    retryable: bool = False  # Can be automatically retried
    patterns: List[str] = field(default_factory=list)  # Regex patterns to match
    remediation: List[str] = field(default_factory=list)  # Suggested fixes
    documentation_url: Optional[str] = None


# ========== Error Code Definitions ==========

ERROR_CODES: Dict[str, ErrorCode] = {}


def _register_error(error: ErrorCode) -> ErrorCode:
    """Register an error code."""
    ERROR_CODES[error.code] = error
    return error


# Resource Errors (WS-RES-xxx)
E_OUT_OF_MEMORY = _register_error(ErrorCode(
    code="WS-RES-001",
    name="OutOfMemory",
    description="Process terminated due to insufficient memory",
    severity=ErrorSeverity.ERROR,
    category=ErrorCategory.RESOURCE,
    retryable=True,
    patterns=[
        r"Out of memory",
        r"oom-kill",
        r"OOMKilled",
        r"Cannot allocate memory",
        r"MemoryError",
        r"java\.lang\.OutOfMemoryError",
    ],
    remediation=[
        "Increase memory allocation for the workset",
        "Use a node with more memory (e.g., r5.4xlarge instead of r5.2xlarge)",
        "Split the workset into smaller batches",
        "Check for memory leaks in custom scripts",
    ],
))

E_DISK_FULL = _register_error(ErrorCode(
    code="WS-RES-002",
    name="DiskFull",
    description="Insufficient disk space for workset processing",
    severity=ErrorSeverity.ERROR,
    category=ErrorCategory.RESOURCE,
    retryable=True,
    patterns=[
        r"No space left on device",
        r"ENOSPC",
        r"Disk quota exceeded",
        r"write error: No space",
    ],
    remediation=[
        "Increase FSx Lustre storage capacity",
        "Clean up intermediate files from previous runs",
        "Enable automatic cleanup of temporary files",
        "Move to a node with larger local storage",
    ],
))

E_CPU_TIMEOUT = _register_error(ErrorCode(
    code="WS-RES-003",
    name="CPUTimeout",
    description="Job exceeded CPU time limit",
    severity=ErrorSeverity.WARNING,
    category=ErrorCategory.RESOURCE,
    retryable=True,
    patterns=[
        r"TIME LIMIT",
        r"TIMEOUT",
        r"Job exceeded time limit",
        r"slurmstepd: error: \*\*\* JOB.*TIME LIMIT",
    ],
    remediation=[
        "Increase job time limit",
        "Check for inefficient processing in pipeline steps",
        "Consider using faster instance types",
        "Split workset into smaller chunks",
    ],
))

# Network Errors (WS-NET-xxx)
E_S3_TIMEOUT = _register_error(ErrorCode(
    code="WS-NET-001",
    name="S3Timeout",
    description="S3 request timed out",
    severity=ErrorSeverity.WARNING,
    category=ErrorCategory.NETWORK,
    retryable=True,
    patterns=[
        r"S3.*timed out",
        r"Connect timeout",
        r"Read timeout",
        r"aws s3.*timeout",
    ],
    remediation=[
        "Retry the operation (usually transient)",
        "Check AWS service health dashboard",
        "Verify network connectivity from cluster",
        "Increase S3 client timeout settings",
    ],
))

E_CONNECTION_REFUSED = _register_error(ErrorCode(
    code="WS-NET-002",
    name="ConnectionRefused",
    description="Network connection refused",
    severity=ErrorSeverity.ERROR,
    category=ErrorCategory.NETWORK,
    retryable=True,
    patterns=[
        r"Connection refused",
        r"ECONNREFUSED",
        r"Unable to connect",
    ],
    remediation=[
        "Check if target service is running",
        "Verify security group rules allow connection",
        "Check VPC network ACLs",
    ],
))

# Data Errors (WS-DAT-xxx)
E_INVALID_FASTQ = _register_error(ErrorCode(
    code="WS-DAT-001",
    name="InvalidFASTQ",
    description="Invalid or corrupted FASTQ file",
    severity=ErrorSeverity.ERROR,
    category=ErrorCategory.DATA,
    retryable=False,
    patterns=[
        r"truncated quality string",
        r"FASTQ.*corrupt",
        r"Invalid FASTQ format",
        r"Unexpected end of.*fastq",
    ],
    remediation=[
        "Verify FASTQ file integrity with md5sum",
        "Re-download or re-transfer the file",
        "Check for incomplete uploads",
        "Validate FASTQ format before submission",
    ],
))

E_MISSING_INPUT = _register_error(ErrorCode(
    code="WS-DAT-002",
    name="MissingInput",
    description="Required input file not found",
    severity=ErrorSeverity.ERROR,
    category=ErrorCategory.DATA,
    retryable=False,
    patterns=[
        r"file not found",
        r"No such file or directory",
        r"Input file.*missing",
        r"Cannot find input",
    ],
    remediation=[
        "Verify all required files are uploaded",
        "Check S3 bucket permissions",
        "Ensure file paths in YAML are correct",
        "Verify FSx import completed successfully",
    ],
))

E_BAD_REFERENCE = _register_error(ErrorCode(
    code="WS-DAT-003",
    name="InvalidReference",
    description="Reference genome issue",
    severity=ErrorSeverity.ERROR,
    category=ErrorCategory.DATA,
    retryable=False,
    patterns=[
        r"reference.*not found",
        r"index.*missing",
        r"Invalid reference",
        r"Reference mismatch",
    ],
    remediation=[
        "Verify reference genome path is correct",
        "Check reference index files exist (.fai, .dict, BWA indexes)",
        "Use supported reference genome (hg38, grch38)",
    ],
))

# AWS Errors (WS-AWS-xxx)
E_THROTTLING = _register_error(ErrorCode(
    code="WS-AWS-001",
    name="AWSThrottling",
    description="AWS API rate limit exceeded",
    severity=ErrorSeverity.WARNING,
    category=ErrorCategory.AWS,
    retryable=True,
    patterns=[
        r"ThrottlingException",
        r"Rate exceeded",
        r"Throttling",
        r"TooManyRequestsException",
    ],
    remediation=[
        "Wait and retry (automatic with exponential backoff)",
        "Reduce request frequency",
        "Request AWS service quota increase",
    ],
))

E_ACCESS_DENIED = _register_error(ErrorCode(
    code="WS-AWS-002",
    name="AccessDenied",
    description="AWS permission denied",
    severity=ErrorSeverity.ERROR,
    category=ErrorCategory.AUTH,
    retryable=False,
    patterns=[
        r"AccessDenied",
        r"Access Denied",
        r"not authorized",
        r"UnauthorizedAccess",
    ],
    remediation=[
        "Check IAM role permissions",
        "Verify S3 bucket policy allows access",
        "Check KMS key permissions if using encryption",
        "Verify cross-account trust if applicable",
    ],
))

# Pipeline Errors (WS-PIP-xxx)
E_BWA_ERROR = _register_error(ErrorCode(
    code="WS-PIP-001",
    name="BWAError",
    description="BWA alignment failure",
    severity=ErrorSeverity.ERROR,
    category=ErrorCategory.PIPELINE,
    retryable=True,
    patterns=[
        r"\[bwa\].*error",
        r"bwa mem.*failed",
        r"BWA-MEM.*error",
    ],
    remediation=[
        "Check BWA index integrity",
        "Verify sufficient memory for alignment",
        "Check input FASTQ quality",
    ],
))

E_GATK_ERROR = _register_error(ErrorCode(
    code="WS-PIP-002",
    name="GATKError",
    description="GATK processing failure",
    severity=ErrorSeverity.ERROR,
    category=ErrorCategory.PIPELINE,
    retryable=True,
    patterns=[
        r"GATK.*error",
        r"HaplotypeCaller.*failed",
        r"UserException",
        r"A USER ERROR has occurred",
    ],
    remediation=[
        "Check GATK logs for specific error message",
        "Verify BAM file is properly sorted and indexed",
        "Ensure reference dictionary matches BAM header",
        "Check for sufficient memory allocation",
    ],
))

# Cluster Errors (WS-CLU-xxx)
E_NODE_FAILURE = _register_error(ErrorCode(
    code="WS-CLU-001",
    name="NodeFailure",
    description="Compute node failure",
    severity=ErrorSeverity.ERROR,
    category=ErrorCategory.CLUSTER,
    retryable=True,
    patterns=[
        r"NODE_FAIL",
        r"Node failure",
        r"lost contact with node",
    ],
    remediation=[
        "Retry on a different node",
        "Check AWS EC2 instance health",
        "Review cluster auto-scaling events",
    ],
))

E_SLURM_ERROR = _register_error(ErrorCode(
    code="WS-CLU-002",
    name="SlurmError",
    description="SLURM scheduler error",
    severity=ErrorSeverity.WARNING,
    category=ErrorCategory.CLUSTER,
    retryable=True,
    patterns=[
        r"slurmstepd.*error",
        r"sbatch.*error",
        r"Job submit failure",
    ],
    remediation=[
        "Check SLURM scheduler status",
        "Verify job submission parameters",
        "Check cluster queue status",
    ],
))


# ========== Diagnostic Result Classes ==========

@dataclass
class DiagnosticResult:
    """Result of error diagnosis."""
    workset_id: str
    error_code: Optional[ErrorCode]
    matched_patterns: List[str] = field(default_factory=list)
    confidence: float = 0.0  # 0.0 to 1.0
    context: Dict[str, Any] = field(default_factory=dict)
    timestamp: dt.datetime = field(default_factory=lambda: dt.datetime.now(dt.timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "workset_id": self.workset_id,
            "error_code": self.error_code.code if self.error_code else None,
            "error_name": self.error_code.name if self.error_code else None,
            "severity": self.error_code.severity.value if self.error_code else None,
            "category": self.error_code.category.value if self.error_code else None,
            "description": self.error_code.description if self.error_code else None,
            "retryable": self.error_code.retryable if self.error_code else False,
            "remediation": self.error_code.remediation if self.error_code else [],
            "matched_patterns": self.matched_patterns,
            "confidence": self.confidence,
            "context": self.context,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class LogEntry:
    """Parsed log entry."""
    timestamp: Optional[dt.datetime]
    level: str
    message: str
    source: Optional[str] = None
    line_number: Optional[int] = None


# ========== Error Analyzer ==========

class ErrorAnalyzer:
    """Analyzes errors and provides diagnostics."""

    def __init__(self):
        """Initialize error analyzer."""
        self._compiled_patterns: Dict[str, List[Pattern]] = {}
        self._compile_patterns()

    def _compile_patterns(self) -> None:
        """Pre-compile regex patterns for performance."""
        for code, error in ERROR_CODES.items():
            self._compiled_patterns[code] = [
                re.compile(p, re.IGNORECASE) for p in error.patterns
            ]

    def analyze(
        self,
        workset_id: str,
        error_text: str,
        logs: Optional[List[str]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> DiagnosticResult:
        """Analyze an error and return diagnostics.

        Args:
            workset_id: Workset identifier
            error_text: Error message or exception text
            logs: Optional list of log lines
            context: Optional additional context

        Returns:
            DiagnosticResult with matched error code and remediation
        """
        combined_text = error_text
        if logs:
            combined_text += "\n" + "\n".join(logs)

        best_match: Optional[ErrorCode] = None
        best_confidence = 0.0
        matched_patterns: List[str] = []

        for code, patterns in self._compiled_patterns.items():
            match_count = 0
            current_patterns = []

            for pattern in patterns:
                if pattern.search(combined_text):
                    match_count += 1
                    current_patterns.append(pattern.pattern)

            if match_count > 0:
                # Calculate confidence based on number of patterns matched
                confidence = min(match_count / len(patterns), 1.0)

                if confidence > best_confidence:
                    best_confidence = confidence
                    best_match = ERROR_CODES[code]
                    matched_patterns = current_patterns

        return DiagnosticResult(
            workset_id=workset_id,
            error_code=best_match,
            matched_patterns=matched_patterns,
            confidence=best_confidence,
            context=context or {},
        )

    def analyze_logs(
        self,
        workset_id: str,
        log_content: str,
    ) -> List[DiagnosticResult]:
        """Analyze log file content for multiple errors.

        Args:
            workset_id: Workset identifier
            log_content: Full log file content

        Returns:
            List of DiagnosticResults for each error found
        """
        results = []
        seen_codes = set()

        for code, patterns in self._compiled_patterns.items():
            for pattern in patterns:
                matches = pattern.findall(log_content)
                if matches and code not in seen_codes:
                    seen_codes.add(code)
                    results.append(DiagnosticResult(
                        workset_id=workset_id,
                        error_code=ERROR_CODES[code],
                        matched_patterns=[pattern.pattern],
                        confidence=0.8,
                        context={"match_count": len(matches)},
                    ))
                    break

        # Sort by severity
        severity_order = {
            ErrorSeverity.CRITICAL: 0,
            ErrorSeverity.ERROR: 1,
            ErrorSeverity.WARNING: 2,
            ErrorSeverity.INFO: 3,
        }
        results.sort(
            key=lambda r: severity_order.get(
                r.error_code.severity if r.error_code else ErrorSeverity.INFO,
                4
            )
        )

        return results

    def get_error_by_code(self, code: str) -> Optional[ErrorCode]:
        """Get error code by its code string.

        Args:
            code: Error code (e.g., "WS-RES-001")

        Returns:
            ErrorCode or None if not found
        """
        return ERROR_CODES.get(code)

    def get_errors_by_category(self, category: ErrorCategory) -> List[ErrorCode]:
        """Get all error codes in a category.

        Args:
            category: Error category

        Returns:
            List of ErrorCodes in that category
        """
        return [e for e in ERROR_CODES.values() if e.category == category]

    def get_retryable_errors(self) -> List[ErrorCode]:
        """Get all retryable error codes.

        Returns:
            List of retryable ErrorCodes
        """
        return [e for e in ERROR_CODES.values() if e.retryable]


# ========== Utility Functions ==========

def get_remediation_for_error(error_text: str) -> List[str]:
    """Get remediation suggestions for an error message.

    Args:
        error_text: Error message text

    Returns:
        List of remediation suggestions
    """
    analyzer = ErrorAnalyzer()
    result = analyzer.analyze("unknown", error_text)
    if result.error_code:
        return result.error_code.remediation
    return [
        "Review the full error message and logs",
        "Check AWS CloudWatch logs for additional details",
        "Contact support if the issue persists",
    ]


def classify_error(error_text: str) -> Dict[str, Any]:
    """Classify an error and return structured info.

    Args:
        error_text: Error message text

    Returns:
        Dict with error classification
    """
    analyzer = ErrorAnalyzer()
    result = analyzer.analyze("unknown", error_text)
    return result.to_dict()


def is_retryable(error_text: str) -> bool:
    """Check if an error is retryable.

    Args:
        error_text: Error message text

    Returns:
        True if error is retryable
    """
    analyzer = ErrorAnalyzer()
    result = analyzer.analyze("unknown", error_text)
    return result.error_code.retryable if result.error_code else False


def format_diagnostic_report(result: DiagnosticResult) -> str:
    """Format a diagnostic result as a human-readable report.

    Args:
        result: DiagnosticResult to format

    Returns:
        Formatted report string
    """
    lines = [
        f"=== Diagnostic Report for {result.workset_id} ===",
        f"Timestamp: {result.timestamp.isoformat()}",
        "",
    ]

    if result.error_code:
        lines.extend([
            f"Error Code: {result.error_code.code}",
            f"Error Name: {result.error_code.name}",
            f"Severity: {result.error_code.severity.value.upper()}",
            f"Category: {result.error_code.category.value}",
            f"Retryable: {'Yes' if result.error_code.retryable else 'No'}",
            "",
            f"Description:",
            f"  {result.error_code.description}",
            "",
            f"Confidence: {result.confidence * 100:.0f}%",
            f"Matched Patterns: {len(result.matched_patterns)}",
            "",
            "Remediation Steps:",
        ])
        for i, step in enumerate(result.error_code.remediation, 1):
            lines.append(f"  {i}. {step}")
    else:
        lines.extend([
            "Error Code: Unknown",
            "Unable to classify this error automatically.",
            "",
            "Recommended Actions:",
            "  1. Review the full error message and logs",
            "  2. Check AWS CloudWatch logs for additional details",
            "  3. Contact support if the issue persists",
        ])

    return "\n".join(lines)


def get_all_error_codes() -> List[Dict[str, Any]]:
    """Get all registered error codes.

    Returns:
        List of error code dictionaries
    """
    return [
        {
            "code": e.code,
            "name": e.name,
            "description": e.description,
            "severity": e.severity.value,
            "category": e.category.value,
            "retryable": e.retryable,
        }
        for e in ERROR_CODES.values()
    ]
