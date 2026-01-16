# Control Bucket Configuration Fix Summary

## Issue
Error: "Control bucket is not configured for workset registration" when creating worksets via the web interface.

## Root Cause
The workset creation endpoint requires a control bucket (monitor bucket) for workset registration per the control-plane refactor architecture. The bucket must be configured via:
1. `WorksetIntegration` initialization with a bucket parameter, OR
2. `DAYLILY_CONTROL_BUCKET` environment variable, OR
3. `DAYLILY_MONITOR_BUCKET` environment variable

If none of these are set, the error is raised.

## Changes Made

### 1. Enhanced CLI (`bin/daylily-workset-api`)
Added two new command-line arguments:
- `--control-bucket`: Specify the S3 control bucket for workset registration
- `--control-prefix`: Specify the S3 prefix within the control bucket (default: `daylily_monitoring/active_worksets/`)

The CLI now:
- Accepts control bucket configuration via CLI arguments
- Falls back to environment variables if not provided
- Automatically initializes `WorksetIntegration` with the control bucket
- Logs initialization status and warnings

### 2. Improved Error Messages (`daylib/workset_api.py`)
Enhanced the error message to guide users:
- Shows what environment variables to set
- References the configuration guide
- Logs the error for debugging

### 3. Configuration Guide (`CONTROL_BUCKET_CONFIGURATION_GUIDE.md`)
Created comprehensive documentation covering:
- Problem diagnosis
- Root cause analysis
- Three configuration options
- Verification steps
- Control-plane architecture requirements

## How to Fix the Error

### Quick Fix (Option 1: Environment Variable)
```bash
export DAYLILY_CONTROL_BUCKET="your-control-bucket-name"
./bin/daylily-workset-api --table-name daylily-worksets --region us-west-2
```

### Recommended Fix (Option 2: CLI Argument)
```bash
./bin/daylily-workset-api \
    --table-name daylily-worksets \
    --region us-west-2 \
    --control-bucket your-control-bucket-name
```

### Programmatic Fix (Option 3: Code)
```python
from daylib.workset_api import create_app
from daylib.workset_state_db import WorksetStateDB
from daylib.workset_integration import WorksetIntegration

state_db = WorksetStateDB(table_name="daylily-worksets")
integration = WorksetIntegration(
    state_db=state_db,
    bucket="your-control-bucket-name",
    prefix="daylily_monitoring/active_worksets/",
)
app = create_app(state_db=state_db, integration=integration)
```

## Verification

1. Check environment variables:
   ```bash
   echo $DAYLILY_CONTROL_BUCKET
   ```

2. Verify bucket exists:
   ```bash
   aws s3 ls s3://your-control-bucket-name/ --profile lsmc
   ```

3. Check API logs for:
   - "Integration layer initialized successfully"
   - Or helpful error message with configuration instructions

## Control-Plane Architecture Compliance

✅ Worksets are registered to the **control bucket** (not customer data buckets)
✅ **DynamoDB** is authoritative for state, locking, customer_id, parameters
✅ **S3 workset folder** is artifact storage + optional compatibility interface
✅ Integration layer properly bridges DynamoDB and S3 systems

## Files Modified
- `bin/daylily-workset-api` - Added CLI arguments and integration initialization
- `daylib/workset_api.py` - Improved error messages
- `CONTROL_BUCKET_CONFIGURATION_GUIDE.md` - New configuration guide
- `CONTROL_BUCKET_FIX_SUMMARY.md` - This summary

