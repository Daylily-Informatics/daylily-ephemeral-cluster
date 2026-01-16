# Control Bucket Configuration Guide

## Problem: "Control bucket is not configured for workset registration"

This error occurs when the Daylily API cannot find the control bucket (monitor bucket) needed for workset registration.

## Root Cause Analysis

The workset creation endpoint in `daylib/workset_api.py` (lines 1358-1368) requires a control bucket:

```python
# Use control-plane bucket (monitor bucket) for workset registration
bucket = None
if integration and integration.bucket:
    bucket = integration.bucket
if not bucket:
    bucket = os.getenv("DAYLILY_CONTROL_BUCKET") or os.getenv("DAYLILY_MONITOR_BUCKET")
if not bucket:
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Control bucket is not configured for workset registration",
    )
```

The error is raised when:
1. No `WorksetIntegration` is passed to `create_app()`, OR
2. `WorksetIntegration` is passed but has `bucket=None`, AND
3. Neither `DAYLILY_CONTROL_BUCKET` nor `DAYLILY_MONITOR_BUCKET` environment variables are set

## Solution: Configure the Control Bucket

### Option 1: Set Environment Variables (Recommended)

```bash
# Set the control bucket (monitor bucket) for workset registration
export DAYLILY_CONTROL_BUCKET="your-control-bucket-name"
# OR
export DAYLILY_MONITOR_BUCKET="your-control-bucket-name"

# Then start the API
./bin/daylily-workset-api --table-name daylily-worksets --region us-west-2
```

### Option 2: Use CLI Argument (Preferred)

```bash
./bin/daylily-workset-api \
    --table-name daylily-worksets \
    --region us-west-2 \
    --control-bucket your-control-bucket-name
```

### Option 3: Initialize Integration Layer Explicitly

```python
from daylib.workset_api import create_app
from daylib.workset_state_db import WorksetStateDB
from daylib.workset_integration import WorksetIntegration

state_db = WorksetStateDB(table_name="daylily-worksets")

# Initialize integration with control bucket
integration = WorksetIntegration(
    state_db=state_db,
    bucket="your-control-bucket-name",
    prefix="daylily_monitoring/active_worksets/",
    region="us-west-2",
)

app = create_app(
    state_db=state_db,
    integration=integration,
)
```

## Verification Steps

1. **Check environment variables:**
   ```bash
   echo $DAYLILY_CONTROL_BUCKET
   echo $DAYLILY_MONITOR_BUCKET
   ```

2. **Verify bucket exists and is accessible:**
   ```bash
   aws s3 ls s3://your-control-bucket-name/ --profile lsmc
   ```

3. **Check API logs for initialization:**
   ```bash
   # Look for: "Integration layer initialized"
   # Or: "Control bucket is not configured"
   ```

## Control-Plane Architecture Requirements

Per the daylily control-plane refactor:
- **Control bucket** (monitor bucket) stores workset metadata and state
- **DynamoDB** is authoritative for: state machine, locking, customer_id, run parameters, metrics
- **S3 workset folder** is artifact storage + optional compatibility interface
- Worksets are registered to the **control bucket**, NOT customer data buckets

## Next Steps

1. Identify your control bucket name (typically the monitor/analysis bucket)
2. Set `DAYLILY_CONTROL_BUCKET` environment variable
3. Restart the API server
4. Try creating a workset again

