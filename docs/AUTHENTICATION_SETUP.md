# Authentication Setup Guide

This guide explains how to run the Workset Monitor API with or without authentication.

Pool ID: us-west-2_ipMpPcnrm
Client ID: 3ff96u2ern8thsiv9cq1j2s87p
## Overview

The Workset Monitor API supports two modes:

1. **Without Authentication** (default) - No authentication required, suitable for:
   - Development and testing
   - Internal deployments behind VPN/firewall
   - Environments with network-level security

2. **With Authentication** - AWS Cognito JWT-based authentication, suitable for:
   - Production deployments
   - Multi-tenant environments
   - Public-facing APIs

## Running Without Authentication

### Installation

```bash
# Install base dependencies (no authentication)
pip install -e .
```

### Running the Server

```bash
# Using the example script
python examples/run_api_without_auth.py

# Or using uvicorn directly
uvicorn daylib.workset_api:app --host 0.0.0.0 --port 8000
```

### Python Code Example

```python
from daylib.workset_api import create_app
from daylib.workset_state_db import WorksetStateDB

# Initialize components
state_db = WorksetStateDB("daylily-worksets", "us-west-2")

# Create app WITHOUT authentication
app = create_app(
    state_db=state_db,
    enable_auth=False,  # Disable authentication
)

# Run with uvicorn
import uvicorn
uvicorn.run(app, host="0.0.0.0", port=8000)
```

### Testing Without Authentication

```bash
# All endpoints work without authentication
curl http://localhost:8001/worksets
curl http://localhost:8001/queue/stats
curl -X POST http://localhost:8001/customers \
  -H "Content-Type: application/json" \
  -d '{"customer_name": "Test", "email": "test@example.com"}'
```

## Running With Authentication

### Installation

```bash
# Install with authentication support
pip install -e ".[auth]"

# Or install python-jose separately
pip install 'python-jose[cryptography]'
```

### AWS Cognito Setup

#### 1. Create User Pool

```bash
aws cognito-idp create-user-pool \
  --pool-name daylily-workset-users \
  --policies "PasswordPolicy={MinimumLength=8,RequireUppercase=true,RequireLowercase=true,RequireNumbers=true}" \
  --auto-verified-attributes email \
  --username-attributes email
```

Save the `UserPoolId` from the response.

#### 2. Create App Client

```bash
aws cognito-idp create-user-pool-client \
  --user-pool-id us-west-2_XXXXXXXXX \
  --client-name daylily-workset-api \
  --explicit-auth-flows ALLOW_USER_PASSWORD_AUTH ALLOW_REFRESH_TOKEN_AUTH \
  --generate-secret false
```

Save the `ClientId` from the response.

#### 3. Create Test User

```bash
aws cognito-idp admin-create-user \
  --user-pool-id us-west-2_XXXXXXXXX \
  --username test@example.com \
  --user-attributes Name=email,Value=test@example.com \
  --temporary-password TempPass123!
```

### Running the Server

```bash
# Set environment variables
export COGNITO_USER_POOL_ID=us-west-2_XXXXXXXXX
export COGNITO_APP_CLIENT_ID=XXXXXXXXXXXXXXXXXXXXXXXXXX

# Run the server
python examples/run_api_with_auth.py
```

### Python Code Example

```python
from daylib.workset_api import create_app
from daylib.workset_state_db import WorksetStateDB
from daylib.workset_auth import CognitoAuth

# Initialize components
state_db = WorksetStateDB("daylily-worksets", "us-west-2")

# Initialize Cognito authentication
cognito_auth = CognitoAuth(
    region="us-west-2",
    user_pool_id="us-west-2_XXXXXXXXX",
    app_client_id="XXXXXXXXXXXXXXXXXXXXXXXXXX",
)

# Create app WITH authentication
app = create_app(
    state_db=state_db,
    cognito_auth=cognito_auth,
    enable_auth=True,  # Enable authentication
)

# Run with uvicorn
import uvicorn
uvicorn.run(app, host="0.0.0.0", port=8000)
```

### Getting a JWT Token

```bash
# Authenticate and get token
aws cognito-idp initiate-auth \
  --auth-flow USER_PASSWORD_AUTH \
  --client-id XXXXXXXXXXXXXXXXXXXXXXXXXX \
  --auth-parameters USERNAME=test@example.com,PASSWORD=YourPassword123! \
  --query 'AuthenticationResult.IdToken' \
  --output text
```

Save the token for API requests.

### Testing With Authentication

```bash
# Set token variable
TOKEN="eyJraWQiOiJ..."

# Make authenticated requests
curl http://localhost:8001/worksets \
  -H "Authorization: Bearer $TOKEN"

curl -X POST http://localhost:8001/customers \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"customer_name": "Test", "email": "test@example.com"}'
```

## Configuration Comparison

| Feature | Without Auth | With Auth |
|---------|-------------|-----------|
| Installation | `pip install -e .` | `pip install -e ".[auth]"` |
| Dependencies | Base only | Base + python-jose |
| AWS Cognito | Not required | Required |
| JWT Tokens | Not required | Required |
| User Management | Not available | Available |
| Multi-tenant | Basic | Full support |
| Production Ready | Internal only | Yes |

## Security Considerations

### Without Authentication

**Pros:**
- Simple setup
- No external dependencies
- Fast development

**Cons:**
- No user tracking
- No access control
- Requires network-level security

**Best Practices:**
- Deploy behind VPN or firewall
- Use network security groups
- Enable CloudWatch logging
- Monitor API access

### With Authentication

**Pros:**
- User tracking and audit logs
- Fine-grained access control
- Multi-tenant isolation
- Production-ready security

**Cons:**
- More complex setup
- Additional AWS costs
- Token management required

**Best Practices:**
- Enable MFA for users
- Rotate credentials regularly
- Use HTTPS in production
- Monitor failed auth attempts
- Set token expiration appropriately

## Switching Between Modes

You can switch between authentication modes by changing the `enable_auth` parameter:

```python
# Development: No auth
app = create_app(state_db=state_db, enable_auth=False)

# Production: With auth
app = create_app(
    state_db=state_db,
    cognito_auth=cognito_auth,
    enable_auth=True,
)
```

## Troubleshooting

### "Incompatible 'jose' package found" Warning

**Problem:** Wrong `jose` package installed (need `python-jose`).

**Symptoms:**
```
SyntaxError: Missing parentheses in call to 'print'
```
or
```
Incompatible 'jose' package found. Please uninstall it and install 'python-jose' instead.
```

**Solution:**
```bash
# Uninstall the incompatible jose package
pip uninstall jose

# Install the correct python-jose package
pip install 'python-jose[cryptography]'
```

**Note:** The API will work without authentication even with the incompatible `jose` package installed. The warning is only relevant if you want to enable authentication.

### "No module named 'jose'" Error

**Problem:** Authentication enabled but python-jose not installed.

**Solution:**
```bash
pip install 'python-jose[cryptography]'
# Or install with auth extras
pip install -e ".[auth]"
```

### "Authentication requires python-jose" Error

**Problem:** Trying to create CognitoAuth without python-jose.

**Solution:** Either install python-jose or disable authentication:
```python
# Option 1: Install python-jose
pip install 'python-jose[cryptography]'

# Option 2: Disable authentication
app = create_app(state_db=state_db, enable_auth=False)
```

### "Invalid token" Error

**Problem:** JWT token is expired or invalid.

**Solution:** Get a new token:
```bash
aws cognito-idp initiate-auth \
  --auth-flow USER_PASSWORD_AUTH \
  --client-id XXXXXXXXXXXXXXXXXXXXXXXXXX \
  --auth-parameters USERNAME=user@example.com,PASSWORD=password
```

### "User pool not found" Error

**Problem:** Cognito User Pool ID is incorrect.

**Solution:** Verify the User Pool ID:
```bash
aws cognito-idp list-user-pools --max-results 10
```

## Environment Variables

```bash
# AWS Configuration
export AWS_REGION=us-west-2
export AWS_PROFILE=my-profile

# DynamoDB Tables
export WORKSET_TABLE_NAME=daylily-worksets
export CUSTOMER_TABLE_NAME=daylily-customers

# Cognito Configuration (only if using authentication)
export COGNITO_USER_POOL_ID=us-west-2_XXXXXXXXX
export COGNITO_APP_CLIENT_ID=XXXXXXXXXXXXXXXXXXXXXXXXXX

# API Configuration
export API_HOST=0.0.0.0
export API_PORT=8000
export ENABLE_AUTH=false  # or true
```

## See Also

- [Customer Portal Guide](CUSTOMER_PORTAL.md)
- [Quick Reference](QUICK_REFERENCE.md)
- [Feature Summary](FEATURE_SUMMARY.md)

