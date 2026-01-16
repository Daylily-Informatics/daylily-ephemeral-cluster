#!/usr/bin/env python3
"""Fix Cognito App Client to enable ADMIN_USER_PASSWORD_AUTH flow.

This script updates the Cognito App Client configuration to enable the
ADMIN_USER_PASSWORD_AUTH authentication flow, which is required for
server-side password validation.

Usage:
    export COGNITO_USER_POOL_ID=us-west-2_XXXXXXXXX
    export COGNITO_APP_CLIENT_ID=XXXXXXXXXXXXXXXXXXXXXXXXXX
    python examples/fix_cognito_auth_flow.py
"""

import os
import sys
import boto3
from botocore.exceptions import ClientError

def main():
    """Enable ADMIN_USER_PASSWORD_AUTH flow for the Cognito App Client."""
    
    # Get configuration from environment
    user_pool_id = os.getenv("COGNITO_USER_POOL_ID")
    app_client_id = os.getenv("COGNITO_APP_CLIENT_ID")
    region = os.getenv("AWS_REGION", "us-west-2")
    
    if not user_pool_id:
        print("ERROR: COGNITO_USER_POOL_ID environment variable not set")
        sys.exit(1)
    
    if not app_client_id:
        print("ERROR: COGNITO_APP_CLIENT_ID environment variable not set")
        sys.exit(1)
    
    print(f"Updating Cognito App Client configuration...")
    print(f"  Region: {region}")
    print(f"  User Pool ID: {user_pool_id}")
    print(f"  App Client ID: {app_client_id}")
    print()
    
    # Initialize Cognito client
    cognito = boto3.client('cognito-idp', region_name=region)
    
    try:
        # Get current app client configuration
        print("Fetching current configuration...")
        response = cognito.describe_user_pool_client(
            UserPoolId=user_pool_id,
            ClientId=app_client_id
        )
        
        current_config = response['UserPoolClient']
        current_flows = current_config.get('ExplicitAuthFlows', [])
        
        print(f"Current auth flows: {current_flows}")

        # Check if ALLOW_ADMIN_USER_PASSWORD_AUTH is already enabled
        if 'ALLOW_ADMIN_USER_PASSWORD_AUTH' in current_flows:
            print("✓ ALLOW_ADMIN_USER_PASSWORD_AUTH is already enabled!")
            return

        # Add ALLOW_ADMIN_USER_PASSWORD_AUTH to the list of flows
        new_flows = list(current_flows)
        new_flows.append('ALLOW_ADMIN_USER_PASSWORD_AUTH')
        
        print(f"Updating to: {new_flows}")
        
        # Update the app client
        cognito.update_user_pool_client(
            UserPoolId=user_pool_id,
            ClientId=app_client_id,
            ExplicitAuthFlows=new_flows
        )
        
        print()
        print("✓ Successfully enabled ALLOW_ADMIN_USER_PASSWORD_AUTH flow!")
        print()
        print("You can now use password authentication in the portal.")
        
    except ClientError as e:
        error_code = e.response['Error']['Code']
        error_msg = e.response['Error']['Message']
        print(f"ERROR: {error_code} - {error_msg}")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

