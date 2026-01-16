#!/usr/bin/env python3
import boto3

cognito = boto3.client('cognito-idp', region_name='us-west-2')

# Check old pool
old_pool_id = 'us-west-2_ipMpPcnrm'
try:
    response = cognito.describe_user_pool(UserPoolId=old_pool_id)
    print(f'OLD pool {old_pool_id} EXISTS: {response["UserPool"]["Name"]}')
    clients = cognito.list_user_pool_clients(UserPoolId=old_pool_id, MaxResults=10)
    print('  App clients:')
    for client in clients.get('UserPoolClients', []):
        print(f'    - {client["ClientName"]}: {client["ClientId"]}')
except Exception as e:
    print(f'OLD pool {old_pool_id} does NOT exist')

print()

# Check new pool
new_pool_id = 'us-west-2_uKYbgcDW3'
try:
    response = cognito.describe_user_pool(UserPoolId=new_pool_id)
    print(f'NEW pool {new_pool_id} EXISTS: {response["UserPool"]["Name"]}')
    clients = cognito.list_user_pool_clients(UserPoolId=new_pool_id, MaxResults=10)
    print('  App clients:')
    for client in clients.get('UserPoolClients', []):
        print(f'    - {client["ClientName"]}: {client["ClientId"]}')
except Exception as e:
    print(f'NEW pool {new_pool_id} does NOT exist')

