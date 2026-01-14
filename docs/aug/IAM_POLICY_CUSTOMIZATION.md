# IAM Policy Customization Quick Reference

Before deploying, you **must** customize `iam-policy.json` with your actual AWS resource names.

## Required Changes

### 1. S3 Bucket Name ⚠️ REQUIRED

**Find this section** (lines 47-51):
```json
"Resource": [
  "arn:aws:s3:::your-workset-bucket",
  "arn:aws:s3:::your-workset-bucket/*"
]
```

**Replace with your actual bucket**:
```json
"Resource": [
  "arn:aws:s3:::my-actual-workset-bucket",
  "arn:aws:s3:::my-actual-workset-bucket/*"
]
```

## Optional Changes (Recommended for Production)

### 2. DynamoDB Table Name

**Default** (lines 14-17):
```json
"Resource": [
  "arn:aws:dynamodb:*:*:table/daylily-worksets",
  "arn:aws:dynamodb:*:*:table/daylily-worksets/index/*"
]
```

**If using different table name**:
```json
"Resource": [
  "arn:aws:dynamodb:*:*:table/YOUR_TABLE_NAME",
  "arn:aws:dynamodb:*:*:table/YOUR_TABLE_NAME/index/*"
]
```

### 3. Restrict to Specific Region

**Default** (allows all regions):
```json
"arn:aws:dynamodb:*:*:table/daylily-worksets"
```

**Restrict to us-west-2**:
```json
"arn:aws:dynamodb:us-west-2:YOUR_ACCOUNT_ID:table/daylily-worksets"
```

### 4. SNS Topic Pattern

**Default** (lines 38):
```json
"Resource": "arn:aws:sns:*:*:daylily-workset-*"
```

**If using specific topic**:
```json
"Resource": "arn:aws:sns:us-west-2:YOUR_ACCOUNT_ID:my-specific-topic"
```

## Quick Customization Script

Use this script to automatically customize the policy:

```bash
#!/bin/bash

# Configuration
S3_BUCKET="my-workset-bucket"
TABLE_NAME="daylily-worksets"
REGION="us-west-2"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

# Backup original
cp iam-policy.json iam-policy.json.backup

# Customize
sed -i.bak \
  -e "s/your-workset-bucket/${S3_BUCKET}/g" \
  -e "s/daylily-worksets/${TABLE_NAME}/g" \
  -e "s/\*:*:table/${REGION}:${ACCOUNT_ID}:table/g" \
  -e "s/\*:*:daylily-workset/${REGION}:${ACCOUNT_ID}:daylily-workset/g" \
  iam-policy.json

echo "✓ Policy customized"
echo "  S3 Bucket: ${S3_BUCKET}"
echo "  Table: ${TABLE_NAME}"
echo "  Region: ${REGION}"
echo "  Account: ${ACCOUNT_ID}"
```

Save as `customize-iam-policy.sh` and run:
```bash
chmod +x customize-iam-policy.sh
./customize-iam-policy.sh
```

## Validation

After customizing, validate the JSON:

```bash
# Check JSON syntax
python3 -m json.tool iam-policy.json > /dev/null && echo "✓ Valid JSON" || echo "✗ Invalid JSON"

# Validate with AWS
aws iam create-policy \
    --policy-name DaylilyWorksetMonitorPolicy-Test \
    --policy-document file://iam-policy.json \
    --dry-run 2>&1 | grep -q "DryRunOperation" && echo "✓ Policy valid" || echo "✗ Policy invalid"
```

## Common Mistakes

### ❌ Mistake 1: Forgot to replace S3 bucket
```json
"Resource": [
  "arn:aws:s3:::your-workset-bucket",  // ❌ Still has placeholder
```

### ✅ Correct:
```json
"Resource": [
  "arn:aws:s3:::my-actual-bucket",  // ✅ Real bucket name
```

### ❌ Mistake 2: Wrong region format
```json
"arn:aws:dynamodb:us-west-2:*:table/..."  // ❌ Mixed specific region with wildcard account
```

### ✅ Correct (choose one):
```json
// Option A: All regions and accounts (less secure)
"arn:aws:dynamodb:*:*:table/..."

// Option B: Specific region and account (more secure)
"arn:aws:dynamodb:us-west-2:123456789012:table/..."
```

### ❌ Mistake 3: Typo in table name
```json
"arn:aws:dynamodb:*:*:table/daylily-workset"  // ❌ Missing 's'
```

### ✅ Correct:
```json
"arn:aws:dynamodb:*:*:table/daylily-worksets"  // ✅ Correct name
```

## Testing After Deployment

Test each permission:

```bash
# Test DynamoDB
aws dynamodb describe-table --table-name daylily-worksets --region us-west-2

# Test S3
aws s3 ls s3://YOUR_BUCKET/

# Test CloudWatch
aws cloudwatch put-metric-data \
    --namespace Daylily/Worksets \
    --metric-name TestMetric \
    --value 1

# Test SNS (if configured)
aws sns publish \
    --topic-arn YOUR_TOPIC_ARN \
    --message "Test message"
```

## Need Help?

- **Full guide**: See `docs/IAM_SETUP_GUIDE.md`
- **Deployment**: See `DEPLOYMENT_CHECKLIST.md`
- **Troubleshooting**: See `docs/IAM_SETUP_GUIDE.md` → Troubleshooting section

## Summary Checklist

Before deploying:
- [ ] Replaced `your-workset-bucket` with actual S3 bucket name
- [ ] Verified table name matches your DynamoDB table
- [ ] (Optional) Restricted to specific region
- [ ] (Optional) Restricted to specific AWS account
- [ ] Validated JSON syntax
- [ ] Tested policy creation (dry-run)
- [ ] Backed up original policy file

