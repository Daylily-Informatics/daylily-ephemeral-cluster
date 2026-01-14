# Multi-Region Support

The multi-region system enables global deployment with automatic failover and latency-based routing using DynamoDB Global Tables.

## Overview

Multi-region support provides:
- **High availability**: Automatic failover on region outages
- **Low latency**: Route to nearest healthy region
- **Disaster recovery**: Data replicated across regions
- **Global scale**: Support users worldwide

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    DynamoDB Global Tables                        │
├─────────────────┬─────────────────┬─────────────────────────────┤
│   us-west-2     │   us-east-1     │      eu-west-1              │
│   (Primary)     │   (Secondary)   │      (Secondary)            │
├─────────────────┼─────────────────┼─────────────────────────────┤
│  ┌───────────┐  │  ┌───────────┐  │  ┌───────────┐              │
│  │ Worksets  │◄─┼──│ Worksets  │◄─┼──│ Worksets  │              │
│  │   Table   │──┼─►│   Table   │──┼─►│   Table   │              │
│  └───────────┘  │  └───────────┘  │  └───────────┘              │
└─────────────────┴─────────────────┴─────────────────────────────┘
```

## Supported Regions

| Region | Role | Description |
|--------|------|-------------|
| us-west-2 | Primary | Main region, always preferred when healthy |
| us-east-1 | Secondary | Failover for US users |
| eu-west-1 | Secondary | Low latency for EU users |

## Usage

### Initialize Multi-Region Database

```python
from daylib.workset_multi_region import WorksetMultiRegionDB

db = WorksetMultiRegionDB(
    table_name="daylily-worksets",
    regions=["us-west-2", "us-east-1", "eu-west-1"],
    primary_region="us-west-2",
)
```

### Register a Workset

```python
# Automatically routes to best region
result = db.register_workset(
    workset_id="ws-001",
    bucket="my-bucket",
    prefix="worksets/ws-001/",
)
```

### Get Workset (with failover)

```python
# Tries primary region first, fails over if needed
workset = db.get_workset("ws-001")
```

### Check Region Health

```python
# Get health status of all regions
health = db.get_all_region_health()
for region, status in health.items():
    print(f"{region}: {status.status} (latency: {status.latency_ms}ms)")
```

### Force Specific Region

```python
# Use specific region for an operation
workset = db.get_workset("ws-001", region="eu-west-1")
```

## Region Health Tracking

The system continuously monitors region health:

```python
from daylib.workset_multi_region import RegionHealth, RegionStatus

# Health status includes:
# - status: HEALTHY, DEGRADED, or UNHEALTHY
# - latency_ms: Response time in milliseconds
# - last_check: Timestamp of last health check
# - error_count: Number of recent errors
```

### Health Status Levels

| Status | Description | Action |
|--------|-------------|--------|
| HEALTHY | Region responding normally | Use for requests |
| DEGRADED | High latency or occasional errors | Use with caution |
| UNHEALTHY | Region unavailable | Failover to another region |

## Failover Behavior

1. **Automatic failover**: When primary region fails, requests route to secondary
2. **Latency-based routing**: Choose region with lowest latency
3. **Sticky sessions**: Once a region is selected, prefer it for consistency
4. **Health recovery**: Automatically return to primary when healthy

## Configuration

### Environment Variables

```bash
# Primary region
export DAYLILY_PRIMARY_REGION=us-west-2

# Enable multi-region
export DAYLILY_MULTI_REGION=true

# Health check interval (seconds)
export DAYLILY_HEALTH_CHECK_INTERVAL=30
```

### Programmatic Configuration

```python
db = WorksetMultiRegionDB(
    table_name="daylily-worksets",
    regions=["us-west-2", "us-east-1", "eu-west-1"],
    primary_region="us-west-2",
    health_check_interval=30,
    failover_threshold=3,  # Errors before failover
)
```

## DynamoDB Global Tables Setup

### Prerequisites

1. DynamoDB table must exist in primary region
2. Table must have on-demand capacity or provisioned with auto-scaling
3. Streams must be enabled

### Create Global Table

```bash
# Create table in primary region
aws dynamodb create-table \
    --table-name daylily-worksets \
    --attribute-definitions AttributeName=workset_id,AttributeType=S \
    --key-schema AttributeName=workset_id,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST \
    --stream-specification StreamEnabled=true,StreamViewType=NEW_AND_OLD_IMAGES \
    --region us-west-2

# Add replicas
aws dynamodb update-table \
    --table-name daylily-worksets \
    --replica-updates \
        'Create={RegionName=us-east-1}' \
        'Create={RegionName=eu-west-1}' \
    --region us-west-2
```

## Consistency Model

- **Writes**: Strongly consistent in the region where written
- **Reads**: Eventually consistent across regions (typically < 1 second)
- **Conflicts**: Last-writer-wins based on timestamp

## Monitoring

### CloudWatch Metrics

- `RegionLatency`: Response time per region
- `FailoverCount`: Number of failovers
- `RegionHealth`: Health status per region

### Logging

```python
import logging
logging.getLogger("daylily.workset_multi_region").setLevel(logging.DEBUG)
```

## Best Practices

1. **Use primary region for writes**: Ensures consistency
2. **Enable health checks**: Detect issues early
3. **Monitor replication lag**: Watch for delays
4. **Test failover**: Regularly verify failover works
5. **Set appropriate timeouts**: Balance latency vs reliability

