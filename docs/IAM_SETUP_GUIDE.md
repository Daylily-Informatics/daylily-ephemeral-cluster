# IAM Setup Guide for Workset Monitor

This guide explains how to set up IAM permissions for the Daylily Workset Monitor system.

## Overview

The workset monitor requires permissions to:
- **DynamoDB**: Read/write workset state
- **CloudWatch**: Publish metrics and logs
- **SNS**: Send notifications (optional)
- **S3**: Read workset data
- **EC2**: Query cluster status

## Quick Setup

### Option 1: Using AWS CLI

```bash

AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text  --profile $AWS_PROFILE )



# 1. Create the IAM policy
aws iam create-policy \
    --policy-name DaylilyWorksetMonitorPolicy \
    --policy-document file://iam-policy.json \
    --description "Permissions for Daylily Workset Monitor"

# 2. Attach to existing role
aws iam attach-role-policy \
    --role-name YOUR_MONITOR_ROLE \
    --policy-arn arn:aws:iam::YOUR_ACCOUNT_ID:policy/DaylilyWorksetMonitorPolicy

# 3. Or attach to existing user
aws iam attach-user-policy \
    --user-name daylily-service \
    --policy-arn arn:aws:iam::${AWS_ACCOUNT_ID}:policy/DaylilyWorksetMonitorPolicy
```
 
### Option 2: Using AWS Console

1. Go to **IAM Console** → **Policies** → **Create Policy**
2. Click **JSON** tab
3. Copy contents from `iam-policy.json`
4. Click **Next: Tags** → **Next: Review**
5. Name: `DaylilyWorksetMonitorPolicy`
6. Click **Create Policy**
7. Go to **Roles** or **Users** → Select your role/user
8. Click **Add permissions** → **Attach policies**
9. Search for `DaylilyWorksetMonitorPolicy` and attach

## Customizing the Policy

### 1. Update DynamoDB Table Name

If your table name is different from `daylily-worksets`, update:

```json
"Resource": [
  "arn:aws:dynamodb:*:*:table/YOUR_TABLE_NAME",
  "arn:aws:dynamodb:*:*:table/YOUR_TABLE_NAME/index/*"
]
```

### 2. Update S3 Bucket Name

Replace `your-workset-bucket` with your actual bucket:

```json
"Resource": [
  "arn:aws:s3:::YOUR_ACTUAL_BUCKET",
  "arn:aws:s3:::YOUR_ACTUAL_BUCKET/*"
]
```

### 3. Update SNS Topic Pattern

If your SNS topics have a different naming pattern:

```json
"Resource": "arn:aws:sns:*:*:YOUR_TOPIC_PATTERN*"
```

### 4. Restrict to Specific Region

To limit to a specific region (e.g., us-west-2):

```json
"Resource": [
  "arn:aws:dynamodb:us-west-2:YOUR_ACCOUNT_ID:table/daylily-worksets",
  "arn:aws:dynamodb:us-west-2:YOUR_ACCOUNT_ID:table/daylily-worksets/index/*"
]
```

## Minimal Permissions (Core Only)

If you only need core functionality without notifications:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:GetItem",
        "dynamodb:PutItem",
        "dynamodb:UpdateItem",
        "dynamodb:Query"
      ],
      "Resource": [
        "arn:aws:dynamodb:*:*:table/daylily-worksets",
        "arn:aws:dynamodb:*:*:table/daylily-worksets/index/*"
      ]
    }
  ]
}
```

## Testing Permissions

After setting up IAM, test the permissions:

```bash
# Test DynamoDB access
aws dynamodb describe-table \
    --table-name daylily-worksets \
    --region us-west-2

# Test CloudWatch metrics
aws cloudwatch list-metrics \
    --namespace Daylily/Worksets \
    --region us-west-2

# Test SNS (if configured)
aws sns list-topics --region us-west-2
```

## Troubleshooting

### Error: AccessDeniedException

**Problem**: Missing DynamoDB permissions

**Solution**: Verify the policy is attached and the table ARN is correct

```bash
aws iam list-attached-role-policies --role-name YOUR_ROLE
```

### Error: InvalidClientTokenId

**Problem**: AWS credentials not configured

**Solution**: Configure AWS CLI credentials

```bash
aws configure
```

### Error: ValidationException

**Problem**: Table doesn't exist or wrong region

**Solution**: Create table first or check region

```bash
python3 -c "
from daylib.workset_state_db import WorksetStateDB
db = WorksetStateDB('daylily-worksets', 'us-west-2')
db.create_table_if_not_exists()
"
```

## Security Best Practices

### 1. Use Least Privilege

Only grant permissions that are actually needed. Start with minimal permissions and add more as needed.

### 2. Use IAM Roles (Not Users)

For EC2 instances or containers, use IAM roles instead of embedding credentials:

```bash
# Attach role to EC2 instance
aws ec2 associate-iam-instance-profile \
    --instance-id i-1234567890abcdef0 \
    --iam-instance-profile Name=DaylilyWorksetMonitorRole
```

### 3. Enable CloudTrail

Monitor API calls for security auditing:

```bash
aws cloudtrail create-trail \
    --name daylily-workset-audit \
    --s3-bucket-name your-audit-bucket
```

### 4. Rotate Credentials Regularly

If using IAM users, rotate access keys every 90 days.

### 5. Use Resource Tags

Tag resources for better access control:

```bash
aws dynamodb tag-resource \
    --resource-arn arn:aws:dynamodb:us-west-2:ACCOUNT:table/daylily-worksets \
    --tags Key=Project,Value=Daylily Key=Component,Value=WorksetMonitor
```

## Example: EC2 Instance Role

For running the monitor on EC2:

```bash
# 1. Create trust policy
cat > trust-policy.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {"Service": "ec2.amazonaws.com"},
    "Action": "sts:AssumeRole"
  }]
}
EOF

# 2. Create role
aws iam create-role \
    --role-name DaylilyWorksetMonitorRole \
    --assume-role-policy-document file://trust-policy.json

# 3. Attach policy
aws iam attach-role-policy \
    --role-name DaylilyWorksetMonitorRole \
    --policy-arn arn:aws:iam::YOUR_ACCOUNT:policy/DaylilyWorksetMonitorPolicy

# 4. Create instance profile
aws iam create-instance-profile \
    --instance-profile-name DaylilyWorksetMonitorProfile

# 5. Add role to instance profile
aws iam add-role-to-instance-profile \
    --instance-profile-name DaylilyWorksetMonitorProfile \
    --role-name DaylilyWorksetMonitorRole
```

## Next Steps

After setting up IAM:
1. ✅ Create DynamoDB table
2. ✅ Configure SNS topics (optional)
3. ✅ Start the API server
4. ✅ Test with sample workset

See `DEPLOYMENT_CHECKLIST.md` for complete deployment steps.

