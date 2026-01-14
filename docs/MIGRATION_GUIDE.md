# Migration Guide: S3 Sentinel Files to DynamoDB State Management

This guide walks through migrating from the legacy S3 sentinel file-based state management to the new DynamoDB-based system.

## Overview

### Before (S3 Sentinel Files)
```
s3://bucket/worksets/ws-001/
├── _READY              # Empty file indicating state
├── _LOCKED             # Empty file indicating lock
├── samples.tsv
└── data/
```

### After (DynamoDB State Management)
```
DynamoDB Table: daylily-worksets
{
  "workset_id": "ws-001",
  "state": "ready",
  "priority": "normal",
  "bucket": "bucket",
  "prefix": "worksets/ws-001/",
  "created_at": "2024-01-15T10:00:00Z",
  "state_history": [...]
}
```

## Migration Strategy

We recommend a **phased migration** approach:

1. **Phase 1**: Deploy DynamoDB system alongside S3 (dual-write)
2. **Phase 2**: Migrate existing worksets to DynamoDB
3. **Phase 3**: Switch reads to DynamoDB (S3 as backup)
4. **Phase 4**: Deprecate S3 sentinel files

## Phase 1: Deploy DynamoDB System

### Step 1.1: Create DynamoDB Table

```bash
# Using Python API
python3 << 'EOF'
from daylib.workset_state_db import WorksetStateDB

db = WorksetStateDB(
    table_name="daylily-worksets",
    region="us-west-2",
)
db.create_table_if_not_exists()
print("✓ DynamoDB table created")
EOF
```

### Step 1.2: Deploy API Server

```bash
# Start API server
./bin/daylily-workset-api \
    --table-name daylily-worksets \
    --region us-west-2 \
    --port 8000 \
    --create-table \
    --verbose &

# Verify API is running
curl http://localhost:8000/
```

### Step 1.3: Configure IAM Permissions

```bash
# Attach IAM policy to monitor role
aws iam put-role-policy \
    --role-name daylily-monitor-role \
    --policy-name DynamoDBAccess \
    --policy-document file://iam-policy.json
```

See [WORKSET_MONITOR_ENHANCEMENTS.md](./WORKSET_MONITOR_ENHANCEMENTS.md#iam-permissions) for complete IAM policy.

## Phase 2: Migrate Existing Worksets

### Step 2.1: Create Migration Script

```python
#!/usr/bin/env python3
"""Migrate existing S3 sentinel files to DynamoDB."""

import boto3
from daylib.workset_state_db import WorksetStateDB, WorksetState, WorksetPriority

def get_state_from_s3(s3_client, bucket, prefix):
    """Determine state from S3 sentinel files."""
    try:
        # Check for sentinel files
        response = s3_client.list_objects_v2(
            Bucket=bucket,
            Prefix=prefix,
            MaxKeys=100,
        )
        
        files = {obj['Key'].split('/')[-1] for obj in response.get('Contents', [])}
        
        if '_COMPLETE' in files:
            return WorksetState.COMPLETE
        elif '_ERROR' in files:
            return WorksetState.ERROR
        elif '_LOCKED' in files:
            return WorksetState.LOCKED
        elif '_READY' in files:
            return WorksetState.READY
        else:
            return WorksetState.READY  # Default
    except Exception as e:
        print(f"Error checking S3 state: {e}")
        return WorksetState.READY

def migrate_workset(db, s3_client, bucket, prefix, workset_id):
    """Migrate a single workset."""
    # Get current state from S3
    state = get_state_from_s3(s3_client, bucket, prefix)
    
    # Register in DynamoDB
    success = db.register_workset(
        workset_id=workset_id,
        bucket=bucket,
        prefix=prefix,
        priority=WorksetPriority.NORMAL,
        metadata={"migrated_from_s3": True},
    )
    
    if success:
        # Update to correct state if not READY
        if state != WorksetState.READY:
            db.update_state(
                workset_id=workset_id,
                new_state=state,
                reason="Migrated from S3 sentinel files",
            )
        print(f"✓ Migrated {workset_id} (state: {state.value})")
    else:
        print(f"✗ Failed to migrate {workset_id} (already exists?)")

def main():
    """Main migration function."""
    # Initialize clients
    db = WorksetStateDB("daylily-worksets", "us-west-2")
    s3_client = boto3.client('s3', region_name='us-west-2')
    
    # List all worksets in S3
    bucket = "your-workset-bucket"
    prefix = "worksets/"
    
    response = s3_client.list_objects_v2(
        Bucket=bucket,
        Prefix=prefix,
        Delimiter='/',
    )
    
    # Migrate each workset
    for common_prefix in response.get('CommonPrefixes', []):
        workset_prefix = common_prefix['Prefix']
        workset_id = workset_prefix.rstrip('/').split('/')[-1]
        
        migrate_workset(db, s3_client, bucket, workset_prefix, workset_id)
    
    print("\n✓ Migration complete")

if __name__ == "__main__":
    main()
```

### Step 2.2: Run Migration

```bash
# Dry run (check what would be migrated)
python3 migrate_worksets.py --dry-run

# Actual migration
python3 migrate_worksets.py

# Verify migration
curl http://localhost:8000/worksets | jq '.[] | {workset_id, state}'
```

## Phase 3: Switch to DynamoDB

### Step 3.1: Update Monitor to Use DynamoDB

```python
# Old code (S3 sentinel files)
def check_workset_state(bucket, prefix):
    s3 = boto3.client('s3')
    try:
        s3.head_object(Bucket=bucket, Key=f"{prefix}_READY")
        return "ready"
    except:
        return "unknown"

# New code (DynamoDB)
from daylib.workset_state_db import WorksetStateDB

db = WorksetStateDB("daylily-worksets", "us-west-2")

def check_workset_state(workset_id):
    workset = db.get_workset(workset_id)
    return workset['state'] if workset else "unknown"
```

### Step 3.2: Update Lock Acquisition

```python
# Old code (S3 sentinel files - race conditions!)
def acquire_lock(bucket, prefix):
    s3 = boto3.client('s3')
    try:
        s3.put_object(Bucket=bucket, Key=f"{prefix}_LOCKED", Body=b'')
        return True
    except:
        return False

# New code (DynamoDB - atomic!)
def acquire_lock(workset_id, owner_id):
    return db.acquire_lock(workset_id, owner_id)
```

### Step 3.3: Dual-Write Period

During transition, write to both systems:

```python
def update_workset_state(workset_id, new_state):
    # Write to DynamoDB (primary)
    db.update_state(
        workset_id=workset_id,
        new_state=new_state,
        reason="State update",
    )
    
    # Write to S3 (backup - for rollback)
    workset = db.get_workset(workset_id)
    s3 = boto3.client('s3')
    s3.put_object(
        Bucket=workset['bucket'],
        Key=f"{workset['prefix']}_{new_state.value.upper()}",
        Body=b'',
    )
```

## Phase 4: Deprecate S3 Sentinel Files

### Step 4.1: Monitor for Issues

```bash
# Check for discrepancies
python3 << 'EOF'
from daylib.workset_state_db import WorksetStateDB
import boto3

db = WorksetStateDB("daylily-worksets", "us-west-2")
s3 = boto3.client('s3')

# Compare states
worksets = db.list_worksets_by_state(WorksetState.READY, limit=100)
for ws in worksets:
    # Check S3 state matches
    # ... comparison logic ...
EOF
```

### Step 4.2: Remove S3 Sentinel File Code

```bash
# Remove old S3 sentinel file functions
git rm lib/s3_sentinel_utils.py

# Update monitor to use only DynamoDB
# ... code changes ...

# Commit changes
git commit -m "Remove S3 sentinel file support"
```

### Step 4.3: Clean Up S3 Sentinel Files (Optional)

```bash
# Remove sentinel files from S3
aws s3 rm s3://your-bucket/worksets/ \
    --recursive \
    --exclude "*" \
    --include "*/_READY" \
    --include "*/_LOCKED" \
    --include "*/_COMPLETE" \
    --include "*/_ERROR"
```

## Rollback Plan

If issues arise, you can rollback:

### Rollback to S3 Sentinel Files

```python
# Re-enable S3 sentinel file code
git revert <commit-hash>

# Sync DynamoDB state back to S3
python3 << 'EOF'
from daylib.workset_state_db import WorksetStateDB
import boto3

db = WorksetStateDB("daylily-worksets", "us-west-2")
s3 = boto3.client('s3')

# For each workset in DynamoDB
for state in [WorksetState.READY, WorksetState.LOCKED, WorksetState.IN_PROGRESS]:
    worksets = db.list_worksets_by_state(state, limit=1000)
    for ws in worksets:
        # Create S3 sentinel file
        s3.put_object(
            Bucket=ws['bucket'],
            Key=f"{ws['prefix']}_{state.value.upper()}",
            Body=b'',
        )
EOF
```

## Validation Checklist

- [ ] DynamoDB table created and accessible
- [ ] IAM permissions configured
- [ ] API server running and healthy
- [ ] All existing worksets migrated
- [ ] Monitor updated to use DynamoDB
- [ ] Locks working correctly (no race conditions)
- [ ] State transitions recorded in audit trail
- [ ] Notifications configured and working
- [ ] CloudWatch metrics publishing
- [ ] No S3 sentinel file dependencies remain

## Troubleshooting

### Migration Issues

**Problem**: Worksets not appearing in DynamoDB
```bash
# Check migration script logs
# Verify IAM permissions
# Manually register missing worksets
```

**Problem**: State mismatches between S3 and DynamoDB
```bash
# Run comparison script
# Manually reconcile differences
# Update DynamoDB to match S3 (or vice versa)
```

### Performance Issues

**Problem**: Slow queries
```bash
# Check DynamoDB capacity
# Verify GSI is being used
# Consider increasing provisioned capacity
```

**Problem**: Lock contention
```bash
# Check lock timeout settings
# Verify stale lock cleanup is working
# Review monitor instance count
```

## Post-Migration

After successful migration:

1. **Monitor metrics** for 1-2 weeks
2. **Review audit trails** for anomalies
3. **Optimize DynamoDB capacity** based on usage
4. **Set up CloudWatch alarms** for queue depth
5. **Document any custom configurations**
6. **Train team** on new system

## Support

For migration assistance:
- GitHub Issues: https://github.com/Daylily-Informatics/daylily-ephemeral-cluster/issues
- Email: daylily@daylilyinformatics.com

