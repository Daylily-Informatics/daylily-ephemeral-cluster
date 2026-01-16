#!/usr/bin/env python3
"""Create Cognito users for existing customers."""

import boto3

cognito = boto3.client('cognito-idp', region_name='us-west-2')
user_pool_id = 'us-west-2_uKYbgcDW3'
password = 'C4un3y!!'

# Create users for the two customers we saw in the logs
users = [
    {'email': 'john@dyly.bio', 'customer_id': 'blah-80e7c8b2'},
    {'email': 'john@lsmc.life', 'customer_id': 'aaaaa-396ababc'},
]

for user in users:
    try:
        cognito.admin_create_user(
            UserPoolId=user_pool_id,
            Username=user['email'],
            UserAttributes=[
                {'Name': 'email', 'Value': user['email']},
                {'Name': 'email_verified', 'Value': 'true'},
                {'Name': 'custom:customer_id', 'Value': user['customer_id']},
            ],
            TemporaryPassword=password,
            MessageAction='SUPPRESS',
        )
        
        cognito.admin_set_user_password(
            UserPoolId=user_pool_id,
            Username=user['email'],
            Password=password,
            Permanent=True
        )
        
        print(f"✓ Created user: {user['email']}")
    except Exception as e:
        print(f"Error creating {user['email']}: {e}")

