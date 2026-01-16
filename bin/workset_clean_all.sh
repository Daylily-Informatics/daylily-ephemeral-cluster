#!/bin/bash
# =============================================================================
# workset_clean_all.sh - Delete all Daylily DynamoDB tables and Cognito resources
# =============================================================================
# WARNING: This is DESTRUCTIVE! It will delete:
#   - All DynamoDB tables (daylily-*)
#   - All Cognito users (but keep the pool and app client)
#   - Optionally: the Cognito user pool itself
#
# Usage:
#   ./bin/workset_clean_all.sh              # Clean tables and users only
#   ./bin/workset_clean_all.sh --all        # Also delete Cognito pool
#   ./bin/workset_clean_all.sh --dry-run    # Show what would be deleted
# =============================================================================

set -e

# Configuration
export AWS_PROFILE="${AWS_PROFILE:-lsmc}"
REGION="${AWS_REGION:-us-west-2}"
DELETE_COGNITO_POOL=false
DRY_RUN=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --all)
            DELETE_COGNITO_POOL=true
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--all] [--dry-run]"
            exit 1
            ;;
    esac
done

echo "=============================================="
echo "  Daylily Workset CLEAN ALL"
echo "=============================================="
echo "AWS Profile: $AWS_PROFILE"
echo "Region: $REGION"
echo "Delete Cognito Pool: $DELETE_COGNITO_POOL"
echo "Dry Run: $DRY_RUN"
echo "=============================================="
echo ""

if [[ "$DRY_RUN" == "false" ]]; then
    echo "⚠️  WARNING: This will DELETE all Daylily resources!"
    echo ""
    read -p "Type 'DELETE' to confirm: " confirm
    if [[ "$confirm" != "DELETE" ]]; then
        echo "Aborted."
        exit 1
    fi
    echo ""
fi

# Run the Python cleanup script
python3 << 'PYTHON_SCRIPT'
import boto3
import sys
import os

profile = os.environ.get('AWS_PROFILE', 'lsmc')
region = os.environ.get('AWS_REGION', 'us-west-2')
delete_cognito_pool = os.environ.get('DELETE_COGNITO_POOL', 'false') == 'true'
dry_run = os.environ.get('DRY_RUN', 'false') == 'true'

session = boto3.Session(profile_name=profile, region_name=region)
dynamodb = session.client('dynamodb')
cognito = session.client('cognito-idp')

# DynamoDB tables to delete
TABLES = [
    'daylily-worksets',
    'daylily-customers',
    'daylily-files',
    'daylily-filesets',
    'daylily-file-workset-usage',
    'daylily-linked-buckets',
    # Biospecimen tables
    'daylily-subjects',
    'daylily-biosamples',
    'daylily-libraries',
    # Manifest storage table
    'daylily-manifests',
]

print("=" * 50)
print("  STEP 1: Delete DynamoDB Tables")
print("=" * 50)

for table_name in TABLES:
    try:
        if dry_run:
            print(f"  [DRY-RUN] Would delete table: {table_name}")
        else:
            dynamodb.delete_table(TableName=table_name)
            print(f"  ✓ Deleted table: {table_name}")
    except dynamodb.exceptions.ResourceNotFoundException:
        print(f"  - Table not found (skipped): {table_name}")
    except Exception as e:
        print(f"  ✗ Error deleting {table_name}: {e}")

print()
print("=" * 50)
print("  STEP 2: Clean Cognito Users")
print("=" * 50)

# Find daylily user pools
pools = cognito.list_user_pools(MaxResults=20)['UserPools']
daylily_pools = [p for p in pools if 'daylily' in p['Name'].lower()]

for pool in daylily_pools:
    pool_id = pool['Id']
    pool_name = pool['Name']
    print(f"\n  Processing pool: {pool_name} ({pool_id})")
    
    # List and delete all users
    try:
        paginator = cognito.get_paginator('list_users')
        for page in paginator.paginate(UserPoolId=pool_id):
            for user in page['Users']:
                username = user['Username']
                if dry_run:
                    print(f"    [DRY-RUN] Would delete user: {username}")
                else:
                    cognito.admin_delete_user(UserPoolId=pool_id, Username=username)
                    print(f"    ✓ Deleted user: {username}")
    except Exception as e:
        print(f"    ✗ Error listing/deleting users: {e}")
    
    # Optionally delete the pool itself
    if delete_cognito_pool:
        try:
            # First delete all app clients
            clients = cognito.list_user_pool_clients(UserPoolId=pool_id, MaxResults=20)
            for client in clients.get('UserPoolClients', []):
                client_id = client['ClientId']
                if dry_run:
                    print(f"    [DRY-RUN] Would delete app client: {client_id}")
                else:
                    cognito.delete_user_pool_client(UserPoolId=pool_id, ClientId=client_id)
                    print(f"    ✓ Deleted app client: {client_id}")
            
            # Then delete the pool
            if dry_run:
                print(f"    [DRY-RUN] Would delete user pool: {pool_id}")
            else:
                cognito.delete_user_pool(UserPoolId=pool_id)
                print(f"    ✓ Deleted user pool: {pool_id}")
        except Exception as e:
            print(f"    ✗ Error deleting pool: {e}")

print()
print("=" * 50)
if dry_run:
    print("  DRY RUN COMPLETE - No changes made")
else:
    print("  ✅ CLEANUP COMPLETE!")
print("=" * 50)
PYTHON_SCRIPT

echo ""
echo "Done! Run ./bin/workset_build_all.sh to recreate resources."

