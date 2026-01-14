#!/bin/bash
#
# Customize IAM Policy for Daylily Workset Monitor
#
# This script helps you customize the iam-policy.json file with your
# actual AWS resource names.
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=========================================="
echo "IAM Policy Customization Script"
echo "=========================================="
echo ""

# Check if iam-policy.json exists
if [ ! -f "iam-policy.json" ]; then
    echo -e "${RED}Error: iam-policy.json not found${NC}"
    exit 1
fi

# Backup original
if [ ! -f "iam-policy.json.original" ]; then
    cp iam-policy.json iam-policy.json.original
    echo -e "${GREEN}✓${NC} Created backup: iam-policy.json.original"
fi

# Get AWS Account ID
echo "Getting AWS Account ID..."
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text 2>/dev/null || echo "")
if [ -z "$ACCOUNT_ID" ]; then
    echo -e "${YELLOW}Warning: Could not get AWS Account ID. AWS CLI may not be configured.${NC}"
    echo "You can still customize the policy, but account-specific ARNs will use wildcards."
    ACCOUNT_ID="*"
else
    echo -e "${GREEN}✓${NC} AWS Account ID: $ACCOUNT_ID"
fi

echo ""
echo "=========================================="
echo "Configuration"
echo "=========================================="
echo ""

# Get S3 bucket name
echo -e "${YELLOW}Required:${NC} S3 Bucket Name"
echo "This is the bucket where your workset data is stored."
read -p "Enter S3 bucket name: " S3_BUCKET
if [ -z "$S3_BUCKET" ]; then
    echo -e "${RED}Error: S3 bucket name is required${NC}"
    exit 1
fi

# Get DynamoDB table name
echo ""
echo -e "${YELLOW}Optional:${NC} DynamoDB Table Name"
echo "Default: daylily-worksets"
read -p "Enter table name (or press Enter for default): " TABLE_NAME
TABLE_NAME=${TABLE_NAME:-daylily-worksets}

# Get AWS region
echo ""
echo -e "${YELLOW}Optional:${NC} AWS Region"
echo "Default: * (all regions)"
echo "Recommended: Specify your region for better security (e.g., us-west-2)"
read -p "Enter region (or press Enter for all regions): " REGION
REGION=${REGION:-*}

# Get SNS topic pattern
echo ""
echo -e "${YELLOW}Optional:${NC} SNS Topic Pattern"
echo "Default: daylily-workset-*"
read -p "Enter SNS topic pattern (or press Enter for default): " SNS_PATTERN
SNS_PATTERN=${SNS_PATTERN:-daylily-workset-*}

echo ""
echo "=========================================="
echo "Summary"
echo "=========================================="
echo "S3 Bucket:       $S3_BUCKET"
echo "Table Name:      $TABLE_NAME"
echo "Region:          $REGION"
echo "Account ID:      $ACCOUNT_ID"
echo "SNS Pattern:     $SNS_PATTERN"
echo ""
read -p "Proceed with customization? (y/n): " CONFIRM

if [ "$CONFIRM" != "y" ] && [ "$CONFIRM" != "Y" ]; then
    echo "Aborted."
    exit 0
fi

# Create customized policy
echo ""
echo "Customizing policy..."

# Use Python for more reliable JSON manipulation
python3 << EOF
import json
import sys

# Read original policy
with open('iam-policy.json', 'r') as f:
    policy = json.load(f)

# Update S3 resources
for statement in policy['Statement']:
    if statement.get('Sid') == 'S3WorksetAccess':
        statement['Resource'] = [
            f"arn:aws:s3:::${S3_BUCKET}",
            f"arn:aws:s3:::${S3_BUCKET}/*"
        ]
    
    # Update DynamoDB resources
    elif statement.get('Sid') == 'DynamoDBTableAccess':
        if '${REGION}' != '*' and '${ACCOUNT_ID}' != '*':
            statement['Resource'] = [
                f"arn:aws:dynamodb:${REGION}:${ACCOUNT_ID}:table/${TABLE_NAME}",
                f"arn:aws:dynamodb:${REGION}:${ACCOUNT_ID}:table/${TABLE_NAME}/index/*"
            ]
        else:
            statement['Resource'] = [
                f"arn:aws:dynamodb:*:*:table/${TABLE_NAME}",
                f"arn:aws:dynamodb:*:*:table/${TABLE_NAME}/index/*"
            ]
    
    # Update SNS resources
    elif statement.get('Sid') == 'SNSPublish':
        if '${REGION}' != '*' and '${ACCOUNT_ID}' != '*':
            statement['Resource'] = f"arn:aws:sns:${REGION}:${ACCOUNT_ID}:${SNS_PATTERN}"
        else:
            statement['Resource'] = f"arn:aws:sns:*:*:${SNS_PATTERN}"

# Write customized policy
with open('iam-policy.json', 'w') as f:
    json.dump(policy, f, indent=2)

print("✓ Policy customized successfully")
EOF

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓${NC} Policy customized successfully"
    echo ""
    echo "Next steps:"
    echo "1. Review the customized policy: cat iam-policy.json"
    echo "2. Validate JSON syntax: python3 -m json.tool iam-policy.json > /dev/null"
    echo "3. Deploy the policy (see DEPLOYMENT_CHECKLIST.md)"
    echo ""
    echo "To restore original: cp iam-policy.json.original iam-policy.json"
else
    echo -e "${RED}✗${NC} Failed to customize policy"
    exit 1
fi

