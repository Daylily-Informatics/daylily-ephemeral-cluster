#!/usr/bin/env python3
"""Automated setup of AWS Cognito for Daylily Portal.

This script creates:
1. A Cognito User Pool for user authentication
2. An App Client with ALLOW_ADMIN_USER_PASSWORD_AUTH enabled
3. Creates users for all existing customers in DynamoDB

Usage:
    python examples/setup_cognito_auto.py
"""

import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import boto3
from botocore.exceptions import ClientError
from daylib.workset_customer import CustomerManager

def main():
    """Setup Cognito for Daylily Portal."""
    region = os.getenv("AWS_REGION", "us-west-2")
    default_password = "C4un3y!!"  # Default password for all users
    
    print("=" * 60)
    print("Daylily Portal - Cognito Automated Setup")
    print("=" * 60)
    print(f"Region: {region}")
    print(f"Default Password: {default_password}")
    print()
    
    # Initialize clients
    cognito = boto3.client('cognito-idp', region_name=region)
    
    # Create User Pool
    print("Creating User Pool: daylily-portal-users")
    try:
        response = cognito.create_user_pool(
            PoolName="daylily-portal-users",
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
            UsernameConfiguration={'CaseSensitive': False},
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
    except ClientError as e:
        print(f"ERROR: {e.response['Error']['Message']}")
        sys.exit(1)
    
    # Create App Client
    print("Creating App Client: daylily-portal-client")
    try:
        response = cognito.create_user_pool_client(
            UserPoolId=user_pool_id,
            ClientName="daylily-portal-client",
            ExplicitAuthFlows=[
                'ALLOW_ADMIN_USER_PASSWORD_AUTH',
                'ALLOW_REFRESH_TOKEN_AUTH',
            ],
            PreventUserExistenceErrors='ENABLED',
            EnableTokenRevocation=True,
        )
        app_client_id = response['UserPoolClient']['ClientId']
        print(f"✓ Created App Client: {app_client_id}")
    except ClientError as e:
        print(f"ERROR: {e.response['Error']['Message']}")
        sys.exit(1)
    
    # Create users for existing customers
    print()
    print("Creating users for existing customers...")
    try:
        customer_mgr = CustomerManager(region=region)
        customers = customer_mgr.list_customers()
        
        if not customers:
            print("No customers found in DynamoDB")
        else:
            print(f"Found {len(customers)} customers")
            
            for customer in customers:
                try:
                    cognito.admin_create_user(
                        UserPoolId=user_pool_id,
                        Username=customer.email,
                        UserAttributes=[
                            {'Name': 'email', 'Value': customer.email},
                            {'Name': 'email_verified', 'Value': 'true'},
                            {'Name': 'custom:customer_id', 'Value': customer.customer_id},
                        ],
                        TemporaryPassword=default_password,
                        MessageAction='SUPPRESS',
                    )
                    
                    # Set permanent password
                    cognito.admin_set_user_password(
                        UserPoolId=user_pool_id,
                        Username=customer.email,
                        Password=default_password,
                        Permanent=True
                    )
                    
                    print(f"  ✓ Created user: {customer.email}")
                    
                except ClientError as e:
                    if e.response['Error']['Code'] == 'UsernameExistsException':
                        print(f"  - User already exists: {customer.email}")
                    else:
                        print(f"  ERROR: {customer.email}: {e.response['Error']['Message']}")
    
    except Exception as e:
        print(f"ERROR: Failed to create users: {e}")
    
    # Print configuration
    print()
    print("=" * 60)
    print("Setup Complete!")
    print("=" * 60)
    print()
    print("Add these to your environment:")
    print(f"  export COGNITO_USER_POOL_ID={user_pool_id}")
    print(f"  export COGNITO_APP_CLIENT_ID={app_client_id}")
    print()
    print("Users can log in with:")
    print(f"  Email: <their email from DynamoDB>")
    print(f"  Password: {default_password}")
    print()

if __name__ == "__main__":
    main()

