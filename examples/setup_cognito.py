#!/usr/bin/env python3
"""Setup AWS Cognito User Pool and App Client for Daylily Portal.

This script creates:
1. A Cognito User Pool for user authentication
2. An App Client with ADMIN_USER_PASSWORD_AUTH enabled
3. Optionally creates users for existing customers in DynamoDB

Usage:
    python examples/setup_cognito.py
    
    # Or with custom region
    AWS_REGION=us-west-2 python examples/setup_cognito.py
"""

import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import boto3
from botocore.exceptions import ClientError
from daylib.workset_customer import CustomerManager

def create_user_pool(cognito, pool_name="daylily-portal-users"):
    """Create a Cognito User Pool."""
    print(f"Creating User Pool: {pool_name}")
    
    try:
        response = cognito.create_user_pool(
            PoolName=pool_name,
            Policies={
                'PasswordPolicy': {
                    'MinimumLength': 8,
                    'RequireUppercase': True,
                    'RequireLowercase': True,
                    'RequireNumbers': True,
                    'RequireSymbols': True,
                }
            },
            AutoVerifiedAttributes=['email'],
            UsernameAttributes=['email'],
            UsernameConfiguration={
                'CaseSensitive': False
            },
            Schema=[
                {
                    'Name': 'email',
                    'AttributeDataType': 'String',
                    'Required': True,
                    'Mutable': True,
                },
                {
                    'Name': 'customer_id',
                    'AttributeDataType': 'String',
                    'Mutable': True,
                },
            ],
            AccountRecoverySetting={
                'RecoveryMechanisms': [
                    {'Priority': 1, 'Name': 'verified_email'},
                ]
            }
        )
        
        user_pool_id = response['UserPool']['Id']
        print(f"✓ Created User Pool: {user_pool_id}")
        return user_pool_id
        
    except ClientError as e:
        if e.response['Error']['Code'] == 'UserPoolTaggingException':
            print("ERROR: User pool with this name already exists")
        else:
            print(f"ERROR: {e.response['Error']['Code']} - {e.response['Error']['Message']}")
        sys.exit(1)

def create_app_client(cognito, user_pool_id, client_name="daylily-portal-client"):
    """Create an App Client with ADMIN_USER_PASSWORD_AUTH enabled."""
    print(f"Creating App Client: {client_name}")
    
    try:
        response = cognito.create_user_pool_client(
            UserPoolId=user_pool_id,
            ClientName=client_name,
            ExplicitAuthFlows=[
                'ALLOW_ADMIN_USER_PASSWORD_AUTH',
                'ALLOW_REFRESH_TOKEN_AUTH',
            ],
            PreventUserExistenceErrors='ENABLED',
            EnableTokenRevocation=True,
        )
        
        app_client_id = response['UserPoolClient']['ClientId']
        print(f"✓ Created App Client: {app_client_id}")
        return app_client_id
        
    except ClientError as e:
        print(f"ERROR: {e.response['Error']['Code']} - {e.response['Error']['Message']}")
        sys.exit(1)

def create_user(cognito, user_pool_id, email, customer_id, temporary_password="TempPass123!"):
    """Create a user in the Cognito User Pool."""
    try:
        cognito.admin_create_user(
            UserPoolId=user_pool_id,
            Username=email,
            UserAttributes=[
                {'Name': 'email', 'Value': email},
                {'Name': 'email_verified', 'Value': 'true'},
                {'Name': 'custom:customer_id', 'Value': customer_id},
            ],
            TemporaryPassword=temporary_password,
            MessageAction='SUPPRESS',  # Don't send email
        )
        
        # Set permanent password
        cognito.admin_set_user_password(
            UserPoolId=user_pool_id,
            Username=email,
            Password=temporary_password,
            Permanent=True
        )
        
        print(f"  ✓ Created user: {email} (password: {temporary_password})")
        return True
        
    except ClientError as e:
        if e.response['Error']['Code'] == 'UsernameExistsException':
            print(f"  - User already exists: {email}")
            return False
        else:
            print(f"  ERROR creating {email}: {e.response['Error']['Message']}")
            return False

def main():
    """Setup Cognito for Daylily Portal."""
    region = os.getenv("AWS_REGION", "us-west-2")
    
    print("=" * 60)
    print("Daylily Portal - Cognito Setup")
    print("=" * 60)
    print(f"Region: {region}")
    print()
    
    # Initialize clients
    cognito = boto3.client('cognito-idp', region_name=region)
    
    # Create User Pool
    user_pool_id = create_user_pool(cognito)
    print()
    
    # Create App Client
    app_client_id = create_app_client(cognito, user_pool_id)
    print()
    
    # Print configuration
    print("=" * 60)
    print("Configuration Complete!")
    print("=" * 60)
    print()
    print("Add these to your environment:")
    print(f"  export COGNITO_USER_POOL_ID={user_pool_id}")
    print(f"  export COGNITO_APP_CLIENT_ID={app_client_id}")
    print()
    
    # Ask if user wants to create users for existing customers
    print("=" * 60)
    response = input("Create users for existing customers in DynamoDB? (y/n): ")

    if response.lower() == 'y':
        print()
        print("Fetching customers from DynamoDB...")
        try:
            customer_mgr = CustomerManager(region=region)
            customers = customer_mgr.list_customers()

            if not customers:
                print("No customers found in DynamoDB")
            else:
                print(f"Found {len(customers)} customers")
                print()

                default_password = input("Enter default password for all users (min 8 chars, must have upper, lower, number, symbol): ")
                print()

                for customer in customers:
                    create_user(
                        cognito,
                        user_pool_id,
                        customer.email,
                        customer.customer_id,
                        default_password
                    )

                print()
                print("✓ User creation complete!")
                print()
                print("Users can now log in with:")
                print(f"  Email: <their email>")
                print(f"  Password: {default_password}")

        except Exception as e:
            print(f"ERROR: Failed to create users: {e}")

    print()
    print("=" * 60)
    print("Setup Complete!")
    print("=" * 60)

if __name__ == "__main__":
    main()

