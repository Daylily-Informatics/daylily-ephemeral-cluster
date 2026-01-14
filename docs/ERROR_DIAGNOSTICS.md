# Error Diagnostics System

The error diagnostics system provides structured error codes, automatic classification, and remediation suggestions for workset processing failures.

## Overview

When a workset fails, the diagnostics system:
1. Analyzes error messages and logs
2. Classifies the error using pattern matching
3. Assigns a structured error code
4. Provides remediation suggestions
5. Determines if the error is retryable

## Error Code Format

Error codes follow the format: `WS-{CATEGORY}-{NUMBER}`

- **WS**: Workset prefix
- **CATEGORY**: 3-letter category code
- **NUMBER**: 3-digit error number

Example: `WS-RES-001` (Resource - Out of Memory)

## Error Categories

### Resource Errors (WS-RES-xxx)

| Code | Name | Description | Retryable |
|------|------|-------------|-----------|
| WS-RES-001 | OutOfMemory | Process terminated due to insufficient memory | Yes |
| WS-RES-002 | DiskFull | Insufficient disk space | Yes |
| WS-RES-003 | CPUTimeout | Job exceeded CPU time limit | Yes |

### Network Errors (WS-NET-xxx)

| Code | Name | Description | Retryable |
|------|------|-------------|-----------|
| WS-NET-001 | S3Timeout | S3 request timed out | Yes |
| WS-NET-002 | ConnectionRefused | Network connection refused | Yes |

### Data Errors (WS-DAT-xxx)

| Code | Name | Description | Retryable |
|------|------|-------------|-----------|
| WS-DAT-001 | InvalidFASTQ | Invalid or corrupted FASTQ file | No |
| WS-DAT-002 | MissingInput | Required input file not found | No |
| WS-DAT-003 | InvalidReference | Reference genome issue | No |

### AWS Errors (WS-AWS-xxx)

| Code | Name | Description | Retryable |
|------|------|-------------|-----------|
| WS-AWS-001 | AWSThrottling | AWS API rate limit exceeded | Yes |
| WS-AWS-002 | AccessDenied | AWS permission denied | No |

### Pipeline Errors (WS-PIP-xxx)

| Code | Name | Description | Retryable |
|------|------|-------------|-----------|
| WS-PIP-001 | BWAError | BWA alignment failure | Yes |
| WS-PIP-002 | GATKError | GATK processing failure | Yes |

### Cluster Errors (WS-CLU-xxx)

| Code | Name | Description | Retryable |
|------|------|-------------|-----------|
| WS-CLU-001 | NodeFailure | Compute node failure | Yes |
| WS-CLU-002 | SlurmError | SLURM scheduler error | Yes |

## Usage

### Classify an Error

```python
from daylib.workset_diagnostics import classify_error

result = classify_error("Out of memory: Cannot allocate 16GB")
print(result)
# {
#     'error_code': 'WS-RES-001',
#     'error_name': 'OutOfMemory',
#     'severity': 'error',
#     'category': 'resource',
#     'retryable': True,
#     'remediation': [
#         'Increase memory allocation for the workset',
#         'Use a node with more memory',
#         ...
#     ]
# }
```

### Get Remediation Suggestions

```python
from daylib.workset_diagnostics import get_remediation_for_error

suggestions = get_remediation_for_error("No space left on device")
for suggestion in suggestions:
    print(f"- {suggestion}")
```

### Check if Retryable

```python
from daylib.workset_diagnostics import is_retryable

if is_retryable("ThrottlingException"):
    print("Error is retryable, scheduling retry...")
else:
    print("Error is permanent, marking as failed")
```

### Analyze Logs

```python
from daylib.workset_diagnostics import ErrorAnalyzer

analyzer = ErrorAnalyzer()
results = analyzer.analyze_logs("ws-001", log_content)

for result in results:
    print(f"Found: {result.error_code.code} - {result.error_code.name}")
    print(f"Severity: {result.error_code.severity.value}")
```

### Generate Diagnostic Report

```python
from daylib.workset_diagnostics import (
    ErrorAnalyzer,
    format_diagnostic_report,
)

analyzer = ErrorAnalyzer()
result = analyzer.analyze("ws-001", "Out of memory error")
report = format_diagnostic_report(result)
print(report)
```

## Integration with State DB

The diagnostics system integrates with the workset state database:

```python
from daylib.workset_state_db import WorksetStateDB, ErrorCategory
from daylib.workset_diagnostics import classify_error

# Classify the error
classification = classify_error(error_text)

# Map to state DB error category
if classification["retryable"]:
    error_category = ErrorCategory.TRANSIENT
else:
    error_category = ErrorCategory.PERMANENT

# Record failure with classification
state_db.record_failure(
    workset_id="ws-001",
    error_details=error_text,
    error_category=error_category,
)
```

## Severity Levels

- **CRITICAL**: System-wide impact, immediate action required
- **ERROR**: Workset failure, investigation needed
- **WARNING**: Potential issue, monitoring advised
- **INFO**: Informational, no action needed

## Adding Custom Error Codes

To add custom error codes, use the `_register_error` function:

```python
from daylib.workset_diagnostics import (
    _register_error,
    ErrorCode,
    ErrorSeverity,
    ErrorCategory,
)

E_CUSTOM_ERROR = _register_error(ErrorCode(
    code="WS-CUS-001",
    name="CustomError",
    description="Custom error description",
    severity=ErrorSeverity.ERROR,
    category=ErrorCategory.PIPELINE,
    retryable=True,
    patterns=[r"custom error pattern"],
    remediation=["Fix suggestion 1", "Fix suggestion 2"],
))
```

