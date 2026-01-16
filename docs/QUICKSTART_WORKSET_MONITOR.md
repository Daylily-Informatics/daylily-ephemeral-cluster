# Quick Start: Enhanced Workset Monitor

Get started with the enhanced workset monitoring system in 5 minutes.

## Prerequisites

- Python 3.9+
- AWS credentials configured
- DynamoDB access
- (Optional) SNS topic for notifications
- (Optional) Linear API key for issue tracking

## Installation

```bash
# Clone repository
git clone https://github.com/Daylily-Informatics/daylily-ephemeral-cluster.git
cd daylily-ephemeral-cluster

# Install dependencies
pip install -e .

# Or with development dependencies
pip install -e ".[dev]"
```

## Quick Setup

### 1. Create DynamoDB Table

```bash
# Using the Python API (easiest)
python3 << 'EOF'
from daylib.workset_state_db import WorksetStateDB

db = WorksetStateDB(
    table_name="daylily-worksets",
    region="us-west-2",
)
db.create_table_if_not_exists()
print("✓ DynamoDB table created successfully")
EOF
```

### 2. Register Your First Workset

```python
from daylib.workset_state_db import WorksetStateDB, WorksetPriority

# Initialize database
db = WorksetStateDB(
    table_name="daylily-worksets",
    region="us-west-2",
)

# Register workset
db.register_workset(
    workset_id="my-first-workset",
    bucket="my-s3-bucket",
    prefix="worksets/my-first-workset/",
    priority=WorksetPriority.NORMAL,
    metadata={
        "samples": 5,
        "estimated_cost_usd": 25.0,
        "description": "Test workset",
    },
)

print("✓ Workset registered successfully")
```

### 3. Start the Web API

```bash
# Basic usage
./bin/daylily-workset-api \
    --table-name daylily-worksets \
    --region us-west-2 \
    --port 8000 \
    --verbose

# The API will be available at http://localhost:8001
# API docs at http://localhost:8001/docs
```

### 4. Test the API

```bash
# Check health
curl http://localhost:8001/

# Get workset details
curl http://localhost:8001/worksets/my-first-workset

# List all worksets
curl http://localhost:8001/worksets

# Get queue statistics
curl http://localhost:8001/queue/stats
```

## Basic Usage Examples

### Working with Worksets

```python
from daylib.workset_state_db import WorksetStateDB, WorksetState

db = WorksetStateDB("daylily-worksets", "us-west-2")

# Get workset details
workset = db.get_workset("my-first-workset")
print(f"State: {workset['state']}")
print(f"Priority: {workset['priority']}")

# Update state
db.update_state(
    workset_id="my-first-workset",
    new_state=WorksetState.IN_PROGRESS,
    reason="Processing started",
    cluster_name="my-cluster",
)

# List ready worksets
ready = db.get_ready_worksets_prioritized(limit=10)
for ws in ready:
    print(f"Ready: {ws['workset_id']} (priority: {ws['priority']})")

# Get queue depth
depth = db.get_queue_depth()
print(f"Queue depth: {depth}")
```

### Using Locks

```python
from daylib.workset_state_db import WorksetStateDB

db = WorksetStateDB("daylily-worksets", "us-west-2")

# Acquire lock
if db.acquire_lock("my-first-workset", owner_id="monitor-1"):
    print("✓ Lock acquired")
    
    # Do work...
    
    # Release lock
    db.release_lock("my-first-workset", owner_id="monitor-1")
    print("✓ Lock released")
else:
    print("✗ Failed to acquire lock (already locked)")
```

### Setting Up Notifications

```python
from daylib.workset_notifications import (
    NotificationManager,
    SNSNotificationChannel,
    NotificationEvent,
)

# Create notification manager
manager = NotificationManager()

# Add SNS channel
sns = SNSNotificationChannel(
    topic_arn="arn:aws:sns:us-west-2:123456789:daylily-alerts",
    region="us-west-2",
)
manager.add_channel(sns)

# Send notification
event = NotificationEvent(
    workset_id="my-first-workset",
    event_type="state_change",
    state="in_progress",
    message="Workset processing started",
    priority="normal",
)
manager.notify(event)
```

## Next Steps

1. **Read the full documentation**: [WORKSET_MONITOR_ENHANCEMENTS.md](./WORKSET_MONITOR_ENHANCEMENTS.md)
2. **Set up notifications**: Configure SNS topics and Linear integration
3. **Enable scheduling**: Use the scheduler for intelligent workset execution
4. **Monitor metrics**: Set up CloudWatch dashboards
5. **Run tests**: `pytest tests/ -v`

## Common Tasks

### Check Queue Status

```bash
curl http://localhost:8001/queue/stats | jq
```

### Get Next Workset to Process

```bash
curl http://localhost:8001/worksets/next | jq
```

### Update Workset State via API

```bash
curl -X PUT http://localhost:8001/worksets/my-first-workset/state \
  -H "Content-Type: application/json" \
  -d '{
    "state": "complete",
    "reason": "Processing finished successfully",
    "metrics": {"duration_seconds": 3600, "cost_usd": 25.50}
  }'
```

## Troubleshooting

### Table doesn't exist
```bash
# Create it
python3 -c "from daylib.workset_state_db import WorksetStateDB; WorksetStateDB('daylily-worksets', 'us-west-2').create_table_if_not_exists()"
```

### Permission denied
Check your AWS credentials and IAM permissions. See [WORKSET_MONITOR_ENHANCEMENTS.md](./WORKSET_MONITOR_ENHANCEMENTS.md#iam-permissions) for required permissions.

### API won't start
```bash
# Check if port is in use
lsof -i :8001

# Try a different port
./bin/daylily-workset-api --port 8080
```

## Support

For issues and questions:
- GitHub Issues: https://github.com/Daylily-Informatics/daylily-ephemeral-cluster/issues
- Documentation: [docs/](../docs/)

