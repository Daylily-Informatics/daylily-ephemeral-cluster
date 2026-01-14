# Billing Integration

This document describes how the Daylily customer portal integrates with AWS billing and cost management services for accurate cost tracking and customer billing.

## Overview

The billing integration provides:
- **Cost allocation tags**: Automatic tagging for cost attribution
- **Per-customer budgets**: AWS Budgets for spending limits
- **Usage monitoring**: Real-time cost and usage tracking
- **Cost optimization**: Lifecycle policies and recommendations

## Cost Allocation Tags

### Automatic Tagging

When a customer is onboarded, their S3 bucket and resources are automatically tagged:

```python
from daylib.workset_customer import CustomerManager

manager = CustomerManager(region="us-west-2")
config = manager.onboard_customer(
    customer_name="Acme Genomics",
    email="admin@acme.com",
    billing_account_id="123456789012",
    cost_center="CC-GENOMICS-001",
)
```

### Applied Tags

| Tag Key | Description | Example Value |
|---------|-------------|---------------|
| `daylily:customer_id` | Unique customer identifier | `cust_abc123` |
| `daylily:customer_name` | Customer display name | `Acme Genomics` |
| `daylily:cost_center` | Cost center code | `CC-GENOMICS-001` |
| `daylily:billing_account` | AWS billing account | `123456789012` |
| `daylily:environment` | Environment type | `production` |
| `daylily:service` | Service name | `daylily-worksets` |

### Enabling Cost Allocation Tags

To use tags in AWS Cost Explorer, activate them in the AWS Billing console:

1. Go to **AWS Billing** → **Cost Allocation Tags**
2. Select the `daylily:*` tags
3. Click **Activate**

Tags become available in Cost Explorer within 24 hours.

## AWS Budgets Integration

### Per-Customer Budgets

Create AWS Budgets to track and alert on customer spending:

```python
import boto3

budgets = boto3.client('budgets')

# Create monthly budget for customer
budgets.create_budget(
    AccountId='123456789012',
    Budget={
        'BudgetName': f'daylily-{customer_id}-monthly',
        'BudgetLimit': {
            'Amount': '1000',
            'Unit': 'USD',
        },
        'BudgetType': 'COST',
        'TimeUnit': 'MONTHLY',
        'CostFilters': {
            'TagKeyValue': [
                f'user:daylily:customer_id${customer_id}',
            ],
        },
    },
    NotificationsWithSubscribers=[
        {
            'Notification': {
                'NotificationType': 'ACTUAL',
                'ComparisonOperator': 'GREATER_THAN',
                'Threshold': 80,
                'ThresholdType': 'PERCENTAGE',
            },
            'Subscribers': [
                {'SubscriptionType': 'EMAIL', 'Address': customer_email},
            ],
        },
    ],
)
```

### Budget Alerts

| Threshold | Alert Type | Action |
|-----------|------------|--------|
| 50% | Warning | Email notification |
| 80% | Warning | Email + SNS notification |
| 100% | Critical | Email + SNS + pause new worksets |

## Cost Reporting

### Customer Usage API

The portal provides usage statistics through the API:

```python
# GET /customers/{customer_id}/usage
{
    "customer_id": "cust_abc123",
    "period": "2024-01",
    "storage": {
        "current_gb": 245.5,
        "max_gb": 5000,
        "cost_usd": 5.64
    },
    "compute": {
        "worksets_completed": 15,
        "vcpu_hours": 1250.5,
        "cost_usd": 312.63
    },
    "data_transfer": {
        "ingress_gb": 125.0,
        "egress_gb": 45.2,
        "cost_usd": 4.07
    },
    "total_cost_usd": 322.34
}
```

### Cost Breakdown by Service

```
┌─────────────────────────────────────────────────────────┐
│              Monthly Cost Breakdown                      │
├─────────────────────────────────────────────────────────┤
│ Service          │ Usage        │ Cost (USD)            │
├──────────────────┼──────────────┼───────────────────────┤
│ EC2 Compute      │ 1,250 vCPU-h │ $312.63               │
│ S3 Storage       │ 245.5 GB     │ $5.64                 │
│ S3 Requests      │ 125,000      │ $0.63                 │
│ Data Transfer    │ 170.2 GB     │ $4.07                 │
│ FSx Lustre       │ 500 GB-h     │ $45.00                │
├──────────────────┼──────────────┼───────────────────────┤
│ TOTAL            │              │ $367.97               │
└─────────────────────────────────────────────────────────┘
```

## Billing Account Association

### Customer Record Schema

Each customer has billing information stored in DynamoDB:

```python
{
    "customer_id": "cust_abc123",
    "customer_name": "Acme Genomics",
    "billing_account_id": "123456789012",  # AWS account for billing
    "cost_center": "CC-GENOMICS-001",       # Internal cost center
    "billing_email": "billing@acme.com",    # Billing contact
    "payment_terms": "net-30",              # Payment terms
    "discount_percent": 10,                 # Negotiated discount
    "created_at": "2024-01-15T10:00:00Z",
}
```

### Cost Center Tracking

Cost centers enable internal accounting and chargebacks:

```python
# Query costs by cost center
ce = boto3.client('ce')

response = ce.get_cost_and_usage(
    TimePeriod={'Start': '2024-01-01', 'End': '2024-02-01'},
    Granularity='MONTHLY',
    Filter={
        'Tags': {
            'Key': 'daylily:cost_center',
            'Values': ['CC-GENOMICS-001'],
        }
    },
    Metrics=['UnblendedCost'],
    GroupBy=[{'Type': 'DIMENSION', 'Key': 'SERVICE'}],
)
```

## Lifecycle Policies for Cost Optimization

### Automatic Data Lifecycle

Customer buckets are configured with lifecycle policies to reduce costs:

```python
lifecycle_config = {
    'Rules': [
        {
            'ID': 'TransitionToIA',
            'Status': 'Enabled',
            'Filter': {'Prefix': 'results/'},
            'Transitions': [
                {'Days': 30, 'StorageClass': 'STANDARD_IA'},
                {'Days': 90, 'StorageClass': 'GLACIER'},
            ],
        },
        {
            'ID': 'DeleteOldLogs',
            'Status': 'Enabled',
            'Filter': {'Prefix': 'logs/'},
            'Expiration': {'Days': 90},
        },
        {
            'ID': 'CleanupIncomplete',
            'Status': 'Enabled',
            'AbortIncompleteMultipartUpload': {'DaysAfterInitiation': 7},
        },
    ],
}
```

### Storage Class Transitions

| Age | Storage Class | Cost per GB/month |
|-----|---------------|-------------------|
| 0-30 days | S3 Standard | $0.023 |
| 30-90 days | S3 Standard-IA | $0.0125 |
| 90+ days | S3 Glacier | $0.004 |

### Cost Savings Estimate

For a typical customer with 1TB of data:

| Scenario | Monthly Cost |
|----------|--------------|
| All Standard | $23.00 |
| With Lifecycle | $8.50 |
| **Savings** | **63%** |

## Portal Usage Dashboard

### Viewing Costs in the Portal

Customers can view their usage and costs at `/portal/usage`:

```
┌─────────────────────────────────────────────────────────────────┐
│                    Usage & Billing Dashboard                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Current Month: January 2024                                     │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │
│                                                                  │
│  Storage Usage          Worksets Processed                       │
│  ┌────────────┐         ┌────────────┐                          │
│  │ 245.5 GB   │         │    15      │                          │
│  │ of 5 TB    │         │ completed  │                          │
│  └────────────┘         └────────────┘                          │
│                                                                  │
│  Month-to-Date Cost     Budget Status                           │
│  ┌────────────┐         ┌────────────────────────┐              │
│  │  $322.34   │         │ ████████░░░░ 64%       │              │
│  │            │         │ $322 of $500 budget    │              │
│  └────────────┘         └────────────────────────┘              │
│                                                                  │
│  Cost Trend (Last 6 Months)                                     │
│  $500 ┤                                                         │
│  $400 ┤                    ╭───╮                                │
│  $300 ┤              ╭─────╯   ╰───●                            │
│  $200 ┤        ╭─────╯                                          │
│  $100 ┤   ╭────╯                                                │
│    $0 ┼───┴────┴────┴────┴────┴────┴                            │
│       Aug  Sep  Oct  Nov  Dec  Jan                              │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Usage API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /customers/{id}/usage` | Current usage statistics |
| `GET /customers/{id}/usage/history` | Historical usage data |
| `GET /customers/{id}/usage/forecast` | Projected costs |
| `GET /customers/{id}/invoices` | Invoice history |

### Sample Usage Response

```json
{
  "customer_id": "cust_abc123",
  "period": {
    "start": "2024-01-01",
    "end": "2024-01-31"
  },
  "summary": {
    "total_cost_usd": 322.34,
    "budget_limit_usd": 500.00,
    "budget_used_percent": 64.5
  },
  "storage": {
    "current_bytes": 263568523264,
    "quota_bytes": 5368709120000,
    "objects_count": 15234,
    "cost_usd": 5.64
  },
  "compute": {
    "worksets_submitted": 18,
    "worksets_completed": 15,
    "worksets_failed": 2,
    "worksets_pending": 1,
    "vcpu_hours": 1250.5,
    "cost_usd": 312.63
  },
  "by_workset": [
    {
      "workset_id": "ws-001",
      "status": "completed",
      "duration_minutes": 45,
      "cost_usd": 18.50
    }
  ]
}
```

## Setting Up Billing Integration

### Prerequisites

1. AWS Cost Explorer enabled
2. Cost allocation tags activated
3. AWS Budgets configured
4. IAM permissions for cost APIs

### Required IAM Permissions

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ce:GetCostAndUsage",
        "ce:GetCostForecast",
        "budgets:ViewBudget",
        "budgets:CreateBudget",
        "budgets:ModifyBudget"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetBucketTagging",
        "s3:PutBucketTagging"
      ],
      "Resource": "arn:aws:s3:::daylily-customer-*"
    }
  ]
}
```

### Configuration

```python
# config/billing_config.yaml
billing:
  enabled: true
  cost_allocation_tags:
    - "daylily:customer_id"
    - "daylily:cost_center"
  budgets:
    default_monthly_limit: 500
    alert_thresholds: [50, 80, 100]
  lifecycle:
    transition_to_ia_days: 30
    transition_to_glacier_days: 90
    delete_logs_days: 90
```

## Best Practices

1. **Tag everything**: Ensure all resources have customer tags
2. **Set budgets early**: Create budgets during onboarding
3. **Monitor alerts**: Act on budget alerts promptly
4. **Review lifecycle policies**: Adjust based on access patterns
5. **Audit costs monthly**: Review cost allocation reports

## Troubleshooting

### Tags Not Appearing in Cost Explorer

- Tags take 24 hours to appear after activation
- Verify tags are activated in Billing console
- Check tag key/value formatting

### Budget Alerts Not Sending

- Verify subscriber email is confirmed
- Check SNS topic permissions
- Review CloudWatch Logs for errors

### Cost Discrepancies

- Cost Explorer data has 24-48 hour delay
- Check for untagged resources
- Verify tag filter syntax

## See Also

- [Customer Portal](CUSTOMER_PORTAL.md)
- [IAM Setup Guide](IAM_SETUP_GUIDE.md)
- [AWS Cost Explorer Documentation](https://docs.aws.amazon.com/cost-management/latest/userguide/ce-what-is.html)
- [AWS Budgets Documentation](https://docs.aws.amazon.com/cost-management/latest/userguide/budgets-managing-costs.html)
- [S3 Lifecycle Policies](https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lifecycle-mgmt.html)

