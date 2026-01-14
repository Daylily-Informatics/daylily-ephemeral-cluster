"""Tests for workset error diagnostics."""

import pytest

from daylib.workset_diagnostics import (
    ErrorAnalyzer,
    ErrorCode,
    ErrorSeverity,
    ErrorCategory,
    DiagnosticResult,
    ERROR_CODES,
    get_remediation_for_error,
    classify_error,
    is_retryable,
    format_diagnostic_report,
    get_all_error_codes,
    E_OUT_OF_MEMORY,
    E_DISK_FULL,
    E_S3_TIMEOUT,
    E_INVALID_FASTQ,
    E_THROTTLING,
    E_BWA_ERROR,
)


class TestErrorCodes:
    """Test error code definitions."""

    def test_error_codes_registered(self):
        """Test that error codes are registered."""
        assert len(ERROR_CODES) > 0
        assert "WS-RES-001" in ERROR_CODES
        assert "WS-NET-001" in ERROR_CODES

    def test_error_code_structure(self):
        """Test error code has required fields."""
        error = E_OUT_OF_MEMORY
        assert error.code == "WS-RES-001"
        assert error.name == "OutOfMemory"
        assert error.severity == ErrorSeverity.ERROR
        assert error.category == ErrorCategory.RESOURCE
        assert len(error.patterns) > 0
        assert len(error.remediation) > 0

    def test_error_categories_covered(self):
        """Test multiple categories have errors."""
        categories = {e.category for e in ERROR_CODES.values()}
        assert ErrorCategory.RESOURCE in categories
        assert ErrorCategory.NETWORK in categories
        assert ErrorCategory.DATA in categories
        assert ErrorCategory.PIPELINE in categories


class TestErrorAnalyzer:
    """Test ErrorAnalyzer class."""

    @pytest.fixture
    def analyzer(self):
        """Create analyzer instance."""
        return ErrorAnalyzer()

    def test_analyze_out_of_memory(self, analyzer):
        """Test OOM error detection."""
        result = analyzer.analyze(
            "test-ws-001",
            "Process killed: Out of memory"
        )
        
        assert result.error_code is not None
        assert result.error_code.code == "WS-RES-001"
        assert result.confidence > 0

    def test_analyze_disk_full(self, analyzer):
        """Test disk full error detection."""
        result = analyzer.analyze(
            "test-ws-001",
            "write error: No space left on device"
        )
        
        assert result.error_code is not None
        assert result.error_code.code == "WS-RES-002"

    def test_analyze_s3_timeout(self, analyzer):
        """Test S3 timeout error detection."""
        result = analyzer.analyze(
            "test-ws-001",
            "S3 request timed out after 60 seconds"
        )
        
        assert result.error_code is not None
        assert result.error_code.code == "WS-NET-001"
        assert result.error_code.retryable is True

    def test_analyze_invalid_fastq(self, analyzer):
        """Test invalid FASTQ detection."""
        result = analyzer.analyze(
            "test-ws-001",
            "Error: truncated quality string in FASTQ file"
        )
        
        assert result.error_code is not None
        assert result.error_code.code == "WS-DAT-001"
        assert result.error_code.retryable is False

    def test_analyze_throttling(self, analyzer):
        """Test AWS throttling detection."""
        result = analyzer.analyze(
            "test-ws-001",
            "ThrottlingException: Rate exceeded"
        )
        
        assert result.error_code is not None
        assert result.error_code.code == "WS-AWS-001"

    def test_analyze_unknown_error(self, analyzer):
        """Test unknown error returns None code."""
        result = analyzer.analyze(
            "test-ws-001",
            "Some random error message"
        )
        
        assert result.error_code is None
        assert result.confidence == 0.0

    def test_analyze_with_logs(self, analyzer):
        """Test analysis with additional logs."""
        result = analyzer.analyze(
            "test-ws-001",
            "Job failed",
            logs=[
                "Starting alignment",
                "OOMKilled: process exceeded memory limit",
                "Job terminated"
            ]
        )
        
        assert result.error_code is not None
        assert result.error_code.code == "WS-RES-001"

    def test_analyze_logs_multiple_errors(self, analyzer):
        """Test analyzing logs with multiple error types."""
        log_content = """
        2024-01-15 10:00:00 Starting pipeline
        2024-01-15 10:00:01 Error: No space left on device
        2024-01-15 10:00:02 Warning: ThrottlingException from AWS
        2024-01-15 10:00:03 Pipeline failed
        """
        
        results = analyzer.analyze_logs("test-ws-001", log_content)
        
        assert len(results) >= 2
        codes = {r.error_code.code for r in results if r.error_code}
        assert "WS-RES-002" in codes  # Disk full
        assert "WS-AWS-001" in codes  # Throttling

    def test_get_error_by_code(self, analyzer):
        """Test getting error by code."""
        error = analyzer.get_error_by_code("WS-RES-001")
        assert error is not None
        assert error.name == "OutOfMemory"
        
        error = analyzer.get_error_by_code("INVALID")
        assert error is None

    def test_get_errors_by_category(self, analyzer):
        """Test getting errors by category."""
        resource_errors = analyzer.get_errors_by_category(ErrorCategory.RESOURCE)
        assert len(resource_errors) >= 3
        assert all(e.category == ErrorCategory.RESOURCE for e in resource_errors)

    def test_get_retryable_errors(self, analyzer):
        """Test getting retryable errors."""
        retryable = analyzer.get_retryable_errors()
        assert len(retryable) > 0
        assert all(e.retryable for e in retryable)


class TestDiagnosticResult:
    """Test DiagnosticResult class."""

    def test_to_dict(self):
        """Test conversion to dictionary."""
        result = DiagnosticResult(
            workset_id="test-ws-001",
            error_code=E_OUT_OF_MEMORY,
            matched_patterns=["Out of memory"],
            confidence=0.9,
        )

        d = result.to_dict()

        assert d["workset_id"] == "test-ws-001"
        assert d["error_code"] == "WS-RES-001"
        assert d["error_name"] == "OutOfMemory"
        assert d["severity"] == "error"
        assert d["category"] == "resource"
        assert d["retryable"] is True
        assert len(d["remediation"]) > 0

    def test_to_dict_no_error_code(self):
        """Test to_dict with no error code."""
        result = DiagnosticResult(
            workset_id="test-ws-001",
            error_code=None,
        )

        d = result.to_dict()

        assert d["error_code"] is None
        assert d["retryable"] is False


class TestUtilityFunctions:
    """Test utility functions."""

    def test_get_remediation_for_error(self):
        """Test getting remediation for error text."""
        remediation = get_remediation_for_error("Out of memory error")

        assert len(remediation) > 0
        assert any("memory" in r.lower() for r in remediation)

    def test_get_remediation_unknown_error(self):
        """Test remediation for unknown error."""
        remediation = get_remediation_for_error("Unknown error xyz123")

        assert len(remediation) > 0  # Default remediation

    def test_classify_error(self):
        """Test error classification."""
        result = classify_error("ThrottlingException: Rate exceeded")

        assert result["error_code"] == "WS-AWS-001"
        assert result["category"] == "aws"

    def test_is_retryable_true(self):
        """Test retryable detection for retryable error."""
        assert is_retryable("ThrottlingException") is True
        assert is_retryable("Out of memory") is True

    def test_is_retryable_false(self):
        """Test retryable detection for non-retryable error."""
        assert is_retryable("Invalid FASTQ format") is False
        assert is_retryable("AccessDenied") is False

    def test_format_diagnostic_report(self):
        """Test diagnostic report formatting."""
        result = DiagnosticResult(
            workset_id="test-ws-001",
            error_code=E_OUT_OF_MEMORY,
            matched_patterns=["Out of memory"],
            confidence=0.9,
        )

        report = format_diagnostic_report(result)

        assert "test-ws-001" in report
        assert "WS-RES-001" in report
        assert "OutOfMemory" in report
        assert "Remediation" in report

    def test_format_diagnostic_report_unknown(self):
        """Test report formatting for unknown error."""
        result = DiagnosticResult(
            workset_id="test-ws-001",
            error_code=None,
        )

        report = format_diagnostic_report(result)

        assert "Unknown" in report
        assert "Review" in report

    def test_get_all_error_codes(self):
        """Test getting all error codes."""
        codes = get_all_error_codes()

        assert len(codes) > 10
        assert all("code" in c for c in codes)
        assert all("severity" in c for c in codes)

