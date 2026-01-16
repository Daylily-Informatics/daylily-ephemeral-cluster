#!/bin/bash
# =============================================================================
# workset_build_all.sh - Create all Daylily DynamoDB tables and Cognito resources
# =============================================================================
# This script creates:
#   - DynamoDB tables (daylily-worksets, daylily-customers, daylily-files, etc.)
#   - Cognito User Pool (if --cognito flag is passed)
#   - Cognito App Client with proper auth flows
#
# Usage:
#   ./bin/workset_build_all.sh              # Create DynamoDB tables only
#   ./bin/workset_build_all.sh --cognito    # Also create Cognito pool
#   ./bin/workset_build_all.sh --dry-run    # Show what would be created
# =============================================================================

set -e

# Configuration
export AWS_PROFILE="${AWS_PROFILE:-lsmc}"
REGION="${AWS_REGION:-us-west-2}"
CREATE_COGNITO=false
DRY_RUN=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --cognito)
            CREATE_COGNITO=true
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--cognito] [--dry-run]"
            exit 1
            ;;
    esac
done

echo "=============================================="
echo "  Daylily Workset BUILD ALL"
echo "=============================================="
echo "AWS Profile: $AWS_PROFILE"
echo "Region: $REGION"
echo "Create Cognito: $CREATE_COGNITO"
echo "Dry Run: $DRY_RUN"
echo "=============================================="
echo ""

# Export for Python
export AWS_REGION="$REGION"
export CREATE_COGNITO="$CREATE_COGNITO"
export DRY_RUN="$DRY_RUN"

# Run the Python build script
python3 << 'PYTHON_SCRIPT'
import boto3
import sys
import os
import time

profile = os.environ.get('AWS_PROFILE', 'lsmc')
region = os.environ.get('AWS_REGION', 'us-west-2')
create_cognito = os.environ.get('CREATE_COGNITO', 'false') == 'true'
dry_run = os.environ.get('DRY_RUN', 'false') == 'true'

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

session = boto3.Session(profile_name=profile, region_name=region)

print("=" * 50)
print("  STEP 1: Create DynamoDB Tables")
print("=" * 50)

if dry_run:
    print("  [DRY-RUN] Would create all DynamoDB tables")
else:
    # Create worksets table
    from daylib.workset_state_db import WorksetStateDB
    print("  Creating daylily-worksets table...")
    db = WorksetStateDB("daylily-worksets", region, profile=profile)
    db.create_table_if_not_exists()
    print("  ✓ daylily-worksets")

    # Create customers table
    from daylib.workset_customer import CustomerManager
    print("  Creating daylily-customers table...")
    cm = CustomerManager(region=region, profile=profile)
    cm.create_customer_table_if_not_exists()
    print("  ✓ daylily-customers")

    # Create file registry tables
    from daylib.file_registry import FileRegistry
    print("  Creating file registry tables...")
    fr = FileRegistry(region=region, profile=profile)
    fr.create_tables_if_not_exist()
    print("  ✓ daylily-files")
    print("  ✓ daylily-filesets")
    print("  ✓ daylily-file-workset-usage")

print()
print("=" * 50)
print("  STEP 2: Cognito User Pool")
print("=" * 50)

if not create_cognito:
    print("  Skipped (use --cognito to create)")
elif dry_run:
    print("  [DRY-RUN] Would create Cognito user pool and app client")
else:
    cognito = session.client('cognito-idp')
    
    # Check if pool already exists
    pools = cognito.list_user_pools(MaxResults=20)['UserPools']
    existing = [p for p in pools if p['Name'] == 'daylily-workset-users']
    
    if existing:
        pool_id = existing[0]['Id']
        print(f"  User pool already exists: {pool_id}")
    else:
        # Create user pool
        print("  Creating user pool: daylily-workset-users")
        response = cognito.create_user_pool(
            PoolName='daylily-workset-users',
            Policies={
                'PasswordPolicy': {
                    'MinimumLength': 8,
                    'RequireUppercase': True,
                    'RequireLowercase': True,
                    'RequireNumbers': True,
                    'RequireSymbols': False,
                }
            },
            AutoVerifiedAttributes=['email'],
            UsernameAttributes=['email'],
            UsernameConfiguration={'CaseSensitive': False},
            Schema=[
                {'Name': 'email', 'AttributeDataType': 'String', 'Required': True, 'Mutable': True},
                {'Name': 'customer_id', 'AttributeDataType': 'String', 'Mutable': True},
            ],
            AccountRecoverySetting={
                'RecoveryMechanisms': [{'Priority': 1, 'Name': 'verified_email'}]
            }
        )
        pool_id = response['UserPool']['Id']
        print(f"  ✓ Created user pool: {pool_id}")
    
    # Check/create app client
    clients = cognito.list_user_pool_clients(UserPoolId=pool_id, MaxResults=10)
    existing_clients = [c for c in clients.get('UserPoolClients', []) if c['ClientName'] == 'daylily-workset-api']
    
    if existing_clients:
        client_id = existing_clients[0]['ClientId']
        print(f"  App client already exists: {client_id}")
        # Update auth flows
        cognito.update_user_pool_client(
            UserPoolId=pool_id,
            ClientId=client_id,
            ClientName='daylily-workset-api',
            ExplicitAuthFlows=[
                'ALLOW_USER_PASSWORD_AUTH',
                'ALLOW_ADMIN_USER_PASSWORD_AUTH',
                'ALLOW_REFRESH_TOKEN_AUTH',
            ],
        )
        print(f"  ✓ Updated app client auth flows")
    else:
        # Create app client
        print("  Creating app client: daylily-workset-api")
        response = cognito.create_user_pool_client(
            UserPoolId=pool_id,
            ClientName='daylily-workset-api',
            GenerateSecret=False,
            ExplicitAuthFlows=[
                'ALLOW_USER_PASSWORD_AUTH',
                'ALLOW_ADMIN_USER_PASSWORD_AUTH',
                'ALLOW_REFRESH_TOKEN_AUTH',
            ],
            ReadAttributes=['email', 'custom:customer_id'],
            WriteAttributes=['email'],
        )
        client_id = response['UserPoolClient']['ClientId']
        print(f"  ✓ Created app client: {client_id}")
    
    print()
    print("  ─────────────────────────────────────────")
    print(f"  COGNITO_USER_POOL_ID={pool_id}")
    print(f"  COGNITO_APP_CLIENT_ID={client_id}")
    print("  ─────────────────────────────────────────")

print()
print("=" * 50)
if dry_run:
    print("  DRY RUN COMPLETE - No changes made")
else:
    print("  ✅ BUILD COMPLETE!")
print("=" * 50)
PYTHON_SCRIPT

echo ""
echo "Done! You can now start the API server:"
echo "  ./examples/run_api_with_new_cognito.sh"

