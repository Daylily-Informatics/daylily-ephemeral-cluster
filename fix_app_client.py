#!/usr/bin/env python3
"""Fix the Cognito app client to enable ADMIN_USER_PASSWORD_AUTH."""
import boto3

# Use lsmc profile
session = boto3.Session(profile_name='lsmc', region_name='us-west-2')
cognito = session.client('cognito-idp')

# YOUR actual pool and client IDs
pool_id = 'us-west-2_ipMpPcnrm'
client_id = '3ff96u2ern8thsiv9cq1j2s87p'

print(f'Checking app client {client_id} in pool {pool_id}...')

response = cognito.describe_user_pool_client(
    UserPoolId=pool_id,
    ClientId=client_id
)

client = response['UserPoolClient']
print(f'Client Name: {client["ClientName"]}')
print(f'Current Auth Flows: {client.get("ExplicitAuthFlows", [])}')

# Update to add the auth flow
print('\nUpdating app client...')
cognito.update_user_pool_client(
    UserPoolId=pool_id,
    ClientId=client_id,
    ClientName=client['ClientName'],
    ExplicitAuthFlows=[
        'ALLOW_USER_PASSWORD_AUTH',
        'ALLOW_ADMIN_USER_PASSWORD_AUTH',
        'ALLOW_REFRESH_TOKEN_AUTH',
    ],
    ReadAttributes=client.get('ReadAttributes', ['email', 'custom:customer_id']),
    WriteAttributes=client.get('WriteAttributes', ['email']),
)
print('✅ Done! ADMIN_USER_PASSWORD_AUTH is now ENABLED')

# Verify
response2 = cognito.describe_user_pool_client(UserPoolId=pool_id, ClientId=client_id)
print(f'\nNew Auth Flows: {response2["UserPoolClient"].get("ExplicitAuthFlows", [])}')

