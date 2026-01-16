# Workset Monitor Quick Reference

Quick reference guide for common operations with the Daylily Workset Monitor.

## Installation

```bash
# Install with all dependencies
pip install -e .[dev]

# Install production dependencies only
pip install -e .
```

## Starting the API Server

```bash
# Basic server
uvicorn daylib.workset_api:app --host 0.0.0.0 --port 8000

# With auto-reload for development
uvicorn daylib.workset_api:app --reload --host 0.0.0.0 --port 8000
```

## Common API Calls

### Queue Management

```bash
# Get queue statistics
curl http://localhost:8001/queue/stats

# Get scheduler statistics
curl http://localhost:8001/scheduler/stats

# Get next workset to execute
curl http://localhost:8001/worksets/next
```

### Workset Operations

```bash
# List all worksets
curl http://localhost:8001/worksets

# List worksets by state
curl "http://localhost:8001/worksets?state=ready&limit=10"

# Get specific workset
curl http://localhost:8001/worksets/ws-001

# Update workset state
curl -X PUT http://localhost:8001/worksets/ws-001/state \
  -H "Content-Type: application/json" \
  -d '{"state": "in_progress"}'

# Update workset priority
curl -X PUT http://localhost:8001/worksets/ws-001/priority \
  -H "Content-Type: application/json" \
  -d '{"priority": "high"}'
```

### Workset Validation

```bash
# Validate workset configuration
curl -X POST "http://localhost:8001/worksets/validate?bucket=my-bucket&prefix=worksets/ws-001/"

# Validate in dry-run mode (skip file checks)
curl -X POST "http://localhost:8001/worksets/validate?bucket=my-bucket&prefix=worksets/ws-001/&dry_run=true"
```

### Customer Management

```bash
# Create customer
curl -X POST http://localhost:8001/customers \
  -H "Content-Type: application/json" \
  -d '{
    "customer_name": "Acme Genomics",
    "email": "admin@acme.com",
    "max_concurrent_worksets": 10,
    "max_storage_gb": 5000,
    "cost_center": "CC-GENOMICS"
  }'

# Get customer details
curl http://localhost:8001/customers/acme-genomics-a1b2c3d4

# List all customers
curl http://localhost:8001/customers

# Get customer usage
curl http://localhost:8001/customers/acme-genomics-a1b2c3d4/usage
```

### YAML Generator

```bash
# Generate daylily_work.yaml
curl -X POST http://localhost:8001/worksets/generate-yaml \
  -H "Content-Type: application/json" \
  -d '{
    "samples": [
      {"sample_id": "sample1", "fastq_r1": "sample1_R1.fq.gz"}
    ],
    "reference_genome": "hg38",
    "pipeline": "germline",
    "priority": "normal"
  }'
```

## Python API Examples

### Initialize Components

```python
from daylib.workset_state_db import WorksetStateDB
from daylib.workset_scheduler import WorksetScheduler
from daylib.workset_validation import WorksetValidator
from daylib.workset_customer import CustomerManager

# State database
state_db = WorksetStateDB("daylily-worksets", "us-west-2")

# Scheduler
scheduler = WorksetScheduler(state_db)

# Validator
validator = WorksetValidator("us-west-2")

# Customer manager
customer_manager = CustomerManager("us-west-2")
```

### Concurrent Processing

```python
from daylib.workset_concurrent_processor import ConcurrentWorksetProcessor, ProcessorConfig

config = ProcessorConfig(
    max_concurrent_worksets=10,
    max_workers=5,
    poll_interval_seconds=30,
    enable_retry=True,
    enable_validation=True,
)

processor = ConcurrentWorksetProcessor(
    state_db=state_db,
    scheduler=scheduler,
    config=config,
    validator=validator,
)

# Start processing
processor.start()

# Stop processing
processor.stop()
```

### Workset Operations

```python
from daylib.workset_state_db import WorksetState, WorksetPriority

# Register workset
state_db.register_workset(
    workset_id="ws-001",
    bucket="my-bucket",
    prefix="worksets/ws-001/",
    priority=WorksetPriority.NORMAL,
    metadata={"customer_id": "acme-genomics"},
)

# Update state
state_db.update_state("ws-001", WorksetState.IN_PROGRESS)

# Update priority
state_db.update_priority("ws-001", WorksetPriority.HIGH)

# Get workset
workset = state_db.get_workset("ws-001")

# List ready worksets
ready = state_db.get_ready_worksets_prioritized(limit=10)
```

### Error Handling and Retry

```python
from daylib.workset_state_db import ErrorCategory

# Record failure
should_retry = state_db.record_failure(
    workset_id="ws-001",
    error_details="Network timeout",
    error_category=ErrorCategory.TRANSIENT,
    failed_step="download_fastq",
)

# Get retryable worksets
retryable = state_db.get_retryable_worksets()

# Reset for retry
state_db.reset_for_retry("ws-001")
```

### Cluster Affinity

```python
# Set cluster affinity
state_db.set_cluster_affinity(
    workset_id="ws-001",
    cluster_name="cluster-us-west-2a",
    affinity_reason="data_locality",
)

# Get worksets by cluster
worksets = state_db.get_worksets_by_cluster("cluster-us-west-2a")
```

### Validation

```python
# Validate workset
result = validator.validate_workset(
    bucket="my-bucket",
    prefix="worksets/ws-001/",
)

if result.is_valid:
    print("Validation passed!")
    print(f"Estimated cost: ${result.estimated_cost_usd}")
else:
    print("Validation failed:")
    for error in result.errors:
        print(f"  - {error}")
```

### Customer Management

```python
# Onboard customer
config = customer_manager.onboard_customer(
    customer_name="Acme Genomics",
    email="admin@acme.com",
    max_concurrent_worksets=10,
    max_storage_gb=5000,
)

# Get customer
config = customer_manager.get_customer_config("acme-genomics-a1b2c3d4")

# Get usage
usage = customer_manager.get_customer_usage("acme-genomics-a1b2c3d4")
print(f"Storage: {usage['storage_gb']} GB")
```

## Environment Variables

```bash
# AWS credentials
export AWS_PROFILE=my-profile
export AWS_REGION=us-west-2

# DynamoDB table names
export WORKSET_TABLE_NAME=daylily-worksets
export CUSTOMER_TABLE_NAME=daylily-customers

# Cognito configuration
export COGNITO_USER_POOL_ID=us-west-2_XXXXXXXXX
export COGNITO_APP_CLIENT_ID=XXXXXXXXXXXXXXXXXXXXXXXXXX

# API configuration
export API_HOST=0.0.0.0
export API_PORT=8000
export ENABLE_AUTH=true
```

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_workset_concurrent_processor.py -v

# Run with coverage
pytest tests/ --cov=daylib --cov-report=html

# Run specific test
pytest tests/test_workset_state_db.py::test_record_failure_transient -v
```

## Troubleshooting

### Check DynamoDB Connection
```python
state_db = WorksetStateDB("daylily-worksets", "us-west-2")
# If this succeeds, connection is working
```

### Check S3 Access
```python
validator = WorksetValidator("us-west-2")
result = validator.validate_workset("my-bucket", "worksets/test/", dry_run=True)
# dry_run=True skips actual S3 checks
```

### Check Cognito Configuration
```python
from daylib.workset_auth import CognitoAuth

auth = CognitoAuth(
    region="us-west-2",
    user_pool_id="us-west-2_XXXXXXXXX",
    app_client_id="XXXXXXXXXXXXXXXXXXXXXXXXXX",
)
# If this succeeds, Cognito is configured correctly
```

## See Also

- [Feature Summary](FEATURE_SUMMARY.md)
- [Concurrent Processing](CONCURRENT_PROCESSING.md)
- [Customer Portal](CUSTOMER_PORTAL.md)
- [Workset Validation](WORKSET_VALIDATION.md)

