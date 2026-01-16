# DAY-EC Conda Environment

The DAY-EC (Daylily Ephemeral Cluster) conda environment is the standard development environment for this project.

## Environment Configuration

The environment is defined in `config/day/daycli.yaml` and includes:

- **Python 3.11**
- **AWS Tools**: awscli, aws-parallelcluster
- **API Framework**: FastAPI, Uvicorn
- **Data Processing**: Pydantic, YAML, JSON
- **Utilities**: jq, yq, rclone, parallel, ipython, pytest

## Creating the Environment

```bash
# Create the environment from the config file
conda env create -f config/day/daycli.yaml -n DAY-EC

# Activate the environment
conda activate DAY-EC
```

## Updating the Environment

After modifying `config/day/daycli.yaml`:

```bash
# Update the existing environment
conda env update -f config/day/daycli.yaml -n DAY-EC --prune

# Or recreate from scratch
conda env remove -n DAY-EC
conda env create -f config/day/daycli.yaml -n DAY-EC
```

## Required Dependencies for Workset Monitor API

The following packages are required for the Workset Monitor API (already included in daycli.yaml):

### Core Dependencies
- `fastapi` - Web framework
- `uvicorn` - ASGI server
- `pydantic` - Data validation
- `email-validator` - Email validation for pydantic
- `python-multipart` - File upload support
- `httpx` - HTTP client
- `jinja2` - Template engine
- `jsonschema` - JSON schema validation

### AWS Dependencies
- `boto3` - AWS SDK (via awscli)
- `botocore` - AWS core library

### Optional Dependencies
- `python-jose[cryptography]` - JWT authentication (optional, for production)
- `passlib[bcrypt]` - Password hashing (optional, for production)

## Known Issues

### Incompatible `jose` Package

**Problem:** An old, incompatible package called `jose` (version 1.0.0) may be installed in some environments. This conflicts with the correct `python-jose` package needed for authentication.

**Symptoms:**
```python
from jose import jwt
# SyntaxError: Missing parentheses in call to 'print'
```

**Detection:** The API will automatically detect this and show a warning:
```
Incompatible 'jose' package found. Please uninstall it and install 'python-jose' instead.
```

**Solution:**
```bash
# Uninstall the incompatible package
pip uninstall jose

# Install the correct package (only if you need authentication)
pip install 'python-jose[cryptography]'
```

**Note:** The API works fine without authentication even with the incompatible `jose` package installed. The warning can be safely ignored if you don't need authentication features.

## Running the API

### Without Authentication (Default)

```bash
# Activate environment
conda activate DAY-EC

# Run the API
python examples/run_api_without_auth.py

# Or use the command-line tool
daylily-workset-api --no-auth
```

### With Authentication (Optional)

```bash
# Install authentication dependencies
pip install 'python-jose[cryptography]' passlib[bcrypt]

# Set Cognito configuration
export COGNITO_USER_POOL_ID=us-west-2_XXXXXXXXX
export COGNITO_APP_CLIENT_ID=XXXXXXXXXXXXXXXXXXXXXXXXXX

# Run the API
python examples/run_api_with_auth.py
```

## Testing

```bash
# Activate environment
conda activate DAY-EC

# Run tests
pytest tests/

# Run specific test file
pytest tests/test_workset_api.py

# Run with coverage
pytest --cov=daylib tests/
```

## Troubleshooting

### Port Already in Use

**Error:** `[Errno 48] error while attempting to bind on address ('0.0.0.0', 8000): address already in use`

**Solution:**
```bash
# Find process using port 8000
lsof -i :8001

# Kill the process
kill -9 <PID>

# Or use a different port
uvicorn daylib.workset_api:app --port 8001
```

### Missing Dependencies

**Error:** `ModuleNotFoundError: No module named 'fastapi'`

**Solution:**
```bash
# Update the environment
conda env update -f config/day/daycli.yaml -n DAY-EC --prune

# Or install manually
pip install fastapi uvicorn pydantic email-validator
```

### AWS Credentials Not Found

**Error:** `NoCredentialsError: Unable to locate credentials`

**Solution:**
```bash
# Configure AWS credentials
aws configure

# Or set environment variables
export AWS_ACCESS_KEY_ID=your_access_key
export AWS_SECRET_ACCESS_KEY=your_secret_key
export AWS_DEFAULT_REGION=us-west-2
```

## Environment Variables

Common environment variables for the DAY-EC environment:

```bash
# AWS Configuration
export AWS_REGION=us-west-2
export AWS_PROFILE=daylily

# DynamoDB Tables
export WORKSET_TABLE_NAME=daylily-worksets
export CUSTOMER_TABLE_NAME=daylily-customers

# API Configuration
export API_HOST=0.0.0.0
export API_PORT=8000
export ENABLE_AUTH=false

# Cognito (only if using authentication)
export COGNITO_USER_POOL_ID=us-west-2_XXXXXXXXX
export COGNITO_APP_CLIENT_ID=XXXXXXXXXXXXXXXXXXXXXXXXXX
```

## See Also

- [Authentication Setup Guide](AUTHENTICATION_SETUP.md)
- [Optional Authentication](OPTIONAL_AUTHENTICATION.md)
- [Quick Reference](QUICK_REFERENCE.md)
- [Quickstart Guide](QUICKSTART_WORKSET_MONITOR.md)

