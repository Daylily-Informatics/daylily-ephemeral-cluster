# Deployment Checklist - Workset Monitor Enhancements

Use this checklist to deploy the enhanced workset monitoring system to production.

## Pre-Deployment

### Code Review
- [ ] Review all production code changes
- [ ] Review test coverage (19/19 tests passing)
- [ ] Review documentation completeness
- [ ] Check for security vulnerabilities
- [ ] Verify IAM permissions are minimal and correct

### Environment Setup
- [ ] AWS account access configured
- [ ] AWS CLI installed and configured
- [ ] Python 3.9+ available
- [ ] Conda environment (DAY-EC) activated
- [ ] All dependencies installed (`pip install -e .`)

### AWS Resources
- [ ] DynamoDB table name decided: `________________`
- [ ] AWS region selected: `________________`
- [ ] SNS topic ARN (optional): `________________`
- [ ] Linear API key (optional): `________________`
- [ ] IAM role/user for monitor: `________________`

## Deployment Steps

### Step 1: Create DynamoDB Table
```bash
# Option A: Using Python API
python3 << 'EOF'
from daylib.workset_state_db import WorksetStateDB
db = WorksetStateDB("daylily-worksets", "us-west-2")
db.create_table_if_not_exists()
print("✓ Table created")
EOF
```

- [ ] DynamoDB table created successfully
- [ ] Table name: `________________`
- [ ] Region: `________________`
- [ ] GSI created: `state-priority-index`
- [ ] Provisioned capacity configured (or on-demand)

### Step 2: Configure IAM Permissions

**Note**: See `docs/IAM_SETUP_GUIDE.md` for detailed instructions.

```bash
# Option A: Create managed policy (recommended)
aws iam create-policy \
    --policy-name DaylilyWorksetMonitorPolicy \
    --policy-document file://iam-policy.json \
    --description "Permissions for Daylily Workset Monitor"

# Get Your Account ID
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text  --profile $AWS_PROFILE )


# Then attach to role
aws iam attach-role-policy \
    --role-name YOUR_MONITOR_ROLE \
    --policy-arn arn:aws:iam::${YOUR_ACCOUNT_ID}:policy/DaylilyWorksetMonitorPolicy

# Option B: Inline policy
aws iam put-role-policy \
    --role-name YOUR_MONITOR_ROLE \
    --policy-name DaylilyWorksetMonitorPolicy \
    --policy-document file://iam-policy.json
```

**Before running**: Update `iam-policy.json` with your actual:
- S3 bucket name (replace `your-workset-bucket`)
- AWS account ID (optional, for stricter security)
- Region (optional, for stricter security)

- [ ] IAM policy file customized (`iam-policy.json`)
- [ ] IAM policy created in AWS
- [ ] DynamoDB permissions granted
- [ ] SNS permissions granted (if using)
- [ ] CloudWatch permissions granted
- [ ] S3 permissions granted (for workset data)
- [ ] Policy attached to monitor role/user
- [ ] Permissions tested (see IAM_SETUP_GUIDE.md)

### Step 3: Set Up SNS (Optional)
```bash
# Create SNS topic
aws sns create-topic \
    --name daylily-workset-alerts \
    --region us-west-2

# Subscribe email
aws sns subscribe \
    --topic-arn YOUR_TOPIC_ARN \
    --protocol email \
    --notification-endpoint your-email@example.com
```

- [ ] SNS topic created
- [ ] Topic ARN: `________________`
- [ ] Email subscriptions configured
- [ ] Subscription confirmed

### Step 4: Configure Linear (Optional)
- [ ] Linear API key obtained
- [ ] Team ID identified: `________________`
- [ ] Test issue creation works

### Step 5: Deploy API Server
```bash
# Start API server
./bin/daylily-workset-api \
    --table-name daylily-worksets \
    --region us-west-2 \
    --port 8000 \
    --enable-scheduler \
    --verbose
```

- [ ] API server started successfully
- [ ] Health check passes: `curl http://localhost:8001/`
- [ ] API docs accessible: `http://localhost:8001/docs`
- [ ] Scheduler enabled (if desired)

### Step 6: Test Basic Operations
```bash
# Register test workset
curl -X POST http://localhost:8001/worksets \
  -H "Content-Type: application/json" \
  -d '{
    "workset_id": "test-001",
    "bucket": "test-bucket",
    "prefix": "test/",
    "priority": "normal"
  }'

# Get workset
curl http://localhost:8001/worksets/test-001

# Get queue stats
curl http://localhost:8001/queue/stats
```

- [ ] Workset registration works
- [ ] Workset retrieval works
- [ ] Queue stats work
- [ ] State updates work
- [ ] Lock acquisition works

### Step 7: Test Notifications
```python
from daylib.workset_notifications import (
    NotificationManager,
    SNSNotificationChannel,
    NotificationEvent,
)

manager = NotificationManager()
manager.add_channel(SNSNotificationChannel(
    topic_arn="YOUR_TOPIC_ARN",
    region="us-west-2",
))

manager.notify(NotificationEvent(
    workset_id="test-001",
    event_type="state_change",
    state="ready",
    message="Test notification",
    priority="normal",
))
```

- [ ] SNS notifications received
- [ ] Linear issues created (if configured)
- [ ] Notification formatting correct

### Step 8: Run Integration Tests
```bash
# Run all tests
~/miniconda3/envs/DAY-EC/bin/python -m pytest tests/ -v
```

- [ ] All tests pass (19/19)
- [ ] No errors in logs
- [ ] No warnings in logs

## Post-Deployment

### Monitoring Setup
- [ ] CloudWatch dashboard created
- [ ] Alarms configured for:
  - [ ] Queue depth > threshold
  - [ ] Error rate > threshold
  - [ ] Lock failures > threshold
  - [ ] API errors > threshold
- [ ] Log aggregation configured
- [ ] Metrics publishing verified

### Documentation
- [ ] Team trained on new system
- [ ] Runbook created for common operations
- [ ] Troubleshooting guide reviewed
- [ ] On-call procedures updated

### Migration (if applicable)
- [ ] Migration script tested
- [ ] Existing worksets migrated
- [ ] Dual-write period started
- [ ] Validation checks passing
- [ ] Rollback plan documented

## Validation

### Functional Tests
- [ ] Register new workset
- [ ] Acquire and release lock
- [ ] Update workset state
- [ ] Query by state and priority
- [ ] Get queue statistics
- [ ] Receive notifications
- [ ] Schedule workset execution

### Performance Tests
- [ ] DynamoDB read/write latency acceptable
- [ ] API response times < 200ms
- [ ] Lock acquisition < 100ms
- [ ] Notification delivery < 5s
- [ ] Queue queries < 500ms

### Reliability Tests
- [ ] Stale lock auto-release works
- [ ] Concurrent lock attempts handled correctly
- [ ] State transitions are atomic
- [ ] Audit trail is complete
- [ ] Error handling works correctly

## Rollback Plan

If issues arise:

1. **Stop API server**
   ```bash
   pkill -f daylily-workset-api
   ```

2. **Revert to S3 sentinel files** (if migrating)
   ```bash
   git revert <commit-hash>
   ```

3. **Restore from backup** (if needed)
   ```bash
   # Restore DynamoDB table from backup
   aws dynamodb restore-table-from-backup ...
   ```

4. **Document issues**
   - [ ] Issue description
   - [ ] Error logs
   - [ ] Steps to reproduce
   - [ ] Impact assessment

## Sign-Off

- [ ] Development team approval
- [ ] QA team approval
- [ ] Operations team approval
- [ ] Security team approval (if required)
- [ ] Product owner approval

**Deployed by**: `________________`  
**Date**: `________________`  
**Environment**: `________________`  
**Version**: `________________`

## Notes

Additional deployment notes:

```
[Add any environment-specific notes here]
```

