#!/usr/bin/env python3
"""Fix existing Cognito App Client to enable ADMIN_USER_PASSWORD_AUTH flow.

This script updates the app client configuration to add the missing auth flow
that's required for admin_initiate_auth to work.

Usage:
    python bin/fix_cognito_app_client.py
"""

import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from daylib.workset_auth import CognitoAuth


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
        # Initialize CognitoAuth
        auth = CognitoAuth(
            region=region,
            user_pool_id=user_pool_id,
            app_client_id=app_client_id,
            profile=profile,
        )
        
        # Update the app client
        print("Updating app client to enable ADMIN_USER_PASSWORD_AUTH...")
        auth.update_app_client_auth_flows()
        
        print("\n✅ SUCCESS! App client updated successfully.")
        print("\nThe following auth flows are now enabled:")
        print("  - ALLOW_USER_PASSWORD_AUTH")
        print("  - ALLOW_ADMIN_USER_PASSWORD_AUTH")
        print("  - ALLOW_REFRESH_TOKEN_AUTH")
        print("\nYou can now use admin_initiate_auth for login.")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

