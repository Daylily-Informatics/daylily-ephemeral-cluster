#!/bin/bash
# Run the API server with the newly created Cognito credentials

export COGNITO_USER_POOL_ID=us-west-2_uKYbgcDW3
export COGNITO_APP_CLIENT_ID=5leifnicigfa4pu4f47so6etkr
export AWS_REGION=us-west-2

echo "Starting Daylily Portal API with Cognito authentication..."
echo "User Pool ID: $COGNITO_USER_POOL_ID"
echo "App Client ID: $COGNITO_APP_CLIENT_ID"
echo ""
echo "Test credentials:"
echo "  Email: john@dyly.bio"
echo "  Password: C4un3y!!"
echo ""
echo "Portal URL: http://localhost:8000/portal"
echo ""

python examples/run_api_with_auth.py

