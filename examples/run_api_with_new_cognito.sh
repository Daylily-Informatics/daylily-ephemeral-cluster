#!/bin/bash
# Run the API server with the newly created Cognito credentials

# Unset any existing Cognito variables to avoid conflicts
#unset COGNITO_USER_POOL_ID
#unset COGNITO_APP_CLIENT_ID

# Set the correct Cognito credentials
#export COGNITO_USER_POOL_ID=us-west-2_uKYbgcDW3 ## GETTING FROM SHELL
#export COGNITO_APP_CLIENT_ID=5leifnicigfa4pu4f47so6etkr ## GETTING FROM SHELL
export AWS_REGION=us-west-2

echo "Starting Daylily Portal API with Cognito authentication..."
echo "User Pool ID: $COGNITO_USER_POOL_ID"
echo "App Client ID: $COGNITO_APP_CLIENT_ID"
echo ""
echo "✅ App client has been updated with required auth flows"
echo ""
echo "Portal URL: http://localhost:8001/portal"
echo ""
echo "To register a new account:"
echo "  1. Go to http://localhost:8001/portal/register"
echo "  2. Fill out the registration form"
echo "  3. Check your email (including spam!) for temporary password"
echo "  4. Log in with temporary password"
echo "  5. You'll be prompted to set a new password"
echo ""

python examples/run_api_with_auth.py

