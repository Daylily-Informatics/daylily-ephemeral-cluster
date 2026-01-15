# daylib

`./daylib` holds the library code which supports daylily, and a few (but growing) number of scripts and tools are using.

## Core Components

### Workset Management
- **workset_api.py**: FastAPI application for workset lifecycle management
- **workset_state_db.py**: DynamoDB interface for workset state
- **workset_scheduler.py**: Workset scheduling and lifecycle management
- **workset_auth.py**: AWS Cognito authentication

### File Management (NEW)
- **file_registry.py**: DynamoDB-backed file metadata registry
- **file_api.py**: FastAPI endpoints for file registration and management
- **file_metadata.py**: Utilities for FASTQ file pairing and analysis input generation

See [FILE_MANAGEMENT_DEPLOYMENT.md](../FILE_MANAGEMENT_DEPLOYMENT.md) for deployment guide.

## Making libs available

```bash
conda activate DAY-EC
cd ~/projects/daylily
pip install -e .
```

## Run a test
_assuming your aws credentials are in place, and `AWS_PROFILE=<something>`.

```bash
calc_daylily_aws_cost_estimates
```

## File Management Quick Start

```python
import boto3
from daylib.file_registry import FileRegistry

# Initialize
dynamodb = boto3.resource('dynamodb', region_name='us-west-2')
registry = FileRegistry(dynamodb)

# Register a file
from daylib.file_registry import FileRegistration, FileMetadata, BiosampleMetadata, SequencingMetadata

registration = FileRegistration(
    file_id="file-001",
    customer_id="customer-123",
    file_metadata=FileMetadata(
        file_id="file-001",
        s3_uri="s3://bucket/sample_R1.fastq.gz",
        file_size_bytes=1024000,
    ),
    biosample_metadata=BiosampleMetadata(
        biosample_id="bio-001",
        subject_id="HG002",
    ),
    sequencing_metadata=SequencingMetadata(
        platform="ILLUMINA_NOVASEQ_X",
        vendor="ILMN",
    ),
)

registry.register_file(registration)
```