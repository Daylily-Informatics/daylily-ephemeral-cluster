#!/usr/bin/env python3
"""Fix existing Cognito App Client to enable ADMIN_USER_PASSWORD_AUTH flow.

This script updates the app client configuration to add the missing auth flow
that's required for admin_initiate_auth to work.

Usage:
    python bin/fix_cognito_app_client.py
"""

import os
import sys
import boto3
from botocore.exceptions import ClientError


def main():
    """Fix the Cognito app client configuration."""
    # Get configuration from environment
    user_pool_id = os.environ.get("COGNITO_USER_POOL_ID")
    app_client_id = os.environ.get("COGNITO_APP_CLIENT_ID")
    region = os.environ.get("AWS_REGION", "us-west-2")
    profile = os.environ.get("AWS_PROFILE")
    
    if not user_pool_id:
        print("ERROR: COGNITO_USER_POOL_ID environment variable not set")
        print("\nUsage:")
        print("  export COGNITO_USER_POOL_ID=us-west-2_xxxxxxxxx")
        print("  export COGNITO_APP_CLIENT_ID=xxxxxxxxxxxxxxxxxx")
        print("  python bin/fix_cognito_app_client.py")
        sys.exit(1)
    
    if not app_client_id:
        print("ERROR: COGNITO_APP_CLIENT_ID environment variable not set")
        print("\nUsage:")
        print("  export COGNITO_USER_POOL_ID=us-west-2_xxxxxxxxx")
        print("  export COGNITO_APP_CLIENT_ID=xxxxxxxxxxxxxxxxxx")
        print("  python bin/fix_cognito_app_client.py")
        sys.exit(1)
    
    print(f"Fixing Cognito App Client configuration...")
    print(f"  User Pool ID: {user_pool_id}")
    print(f"  App Client ID: {app_client_id}")
    print(f"  Region: {region}")
    if profile:
        print(f"  Profile: {profile}")
    print()
    
    try:
        # Initialize boto3 client
        session_kwargs = {"region_name": region}
        if profile:
            session_kwargs["profile_name"] = profile

        session = boto3.Session(**session_kwargs)
        cognito = session.client("cognito-idp")

        # Get current client configuration
        print("Fetching current app client configuration...")
        response = cognito.describe_user_pool_client(
            UserPoolId=user_pool_id,
            ClientId=app_client_id,
        )
        client_config = response["UserPoolClient"]

        print(f"Current auth flows: {client_config.get('ExplicitAuthFlows', [])}")

        # Update with required auth flows
        print("\nUpdating app client to enable ADMIN_USER_PASSWORD_AUTH...")
        cognito.update_user_pool_client(
            UserPoolId=user_pool_id,
            ClientId=app_client_id,
            ClientName=client_config["ClientName"],
            ExplicitAuthFlows=[
                "ALLOW_USER_PASSWORD_AUTH",
                "ALLOW_ADMIN_USER_PASSWORD_AUTH",
                "ALLOW_REFRESH_TOKEN_AUTH",
            ],
            ReadAttributes=client_config.get("ReadAttributes", ["email", "custom:customer_id"]),
            WriteAttributes=client_config.get("WriteAttributes", ["email"]),
        )

        print("\n✅ SUCCESS! App client updated successfully.")
        print("\nThe following auth flows are now enabled:")
        print("  - ALLOW_USER_PASSWORD_AUTH")
        print("  - ALLOW_ADMIN_USER_PASSWORD_AUTH")
        print("  - ALLOW_REFRESH_TOKEN_AUTH")
        print("\nYou can now use admin_initiate_auth for login.")

    except ClientError as e:
        print(f"\n❌ AWS ERROR: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

