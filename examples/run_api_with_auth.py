#!/usr/bin/env python3
"""Example: Run the Workset Monitor API with AWS Cognito authentication.

This example shows how to run the API server with authentication enabled.
Requires python-jose to be installed and AWS Cognito to be configured.

Prerequisites:
    pip install 'python-jose[cryptography]'
    
    AWS Cognito User Pool and App Client must be created.

Usage:
    # Set environment variables
    export COGNITO_USER_POOL_ID=us-west-2_XXXXXXXXX
    export COGNITO_APP_CLIENT_ID=XXXXXXXXXXXXXXXXXXXXXXXXXX
    
    # Run the server
    python examples/run_api_with_auth.py

Then access the API at:
    http://localhost:8000
    http://localhost:8000/docs  (Swagger UI with authentication)
"""

import logging
import os
import sys
from pathlib import Path

# Add parent directory to path to import daylib
sys.path.insert(0, str(Path(__file__).parent.parent))

from daylib.workset_api import create_app
from daylib.workset_state_db import WorksetStateDB
from daylib.workset_scheduler import WorksetScheduler
from daylib.workset_validation import WorksetValidator
from daylib.workset_customer import CustomerManager

# Try to import authentication (requires python-jose)
try:
    from daylib.workset_auth import CognitoAuth
    AUTH_AVAILABLE = True
except ImportError:
    AUTH_AVAILABLE = False
    print("ERROR: python-jose not installed")
    print("Install with: pip install 'python-jose[cryptography]'")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

LOGGER = logging.getLogger(__name__)


def main():
    """Run the API server with authentication."""
    
    # Configuration from environment
    REGION = os.getenv("AWS_REGION", "us-west-2")
    WORKSET_TABLE = os.getenv("WORKSET_TABLE_NAME", "daylily-worksets")
    USER_POOL_ID = os.getenv("COGNITO_USER_POOL_ID")
    APP_CLIENT_ID = os.getenv("COGNITO_APP_CLIENT_ID")
    
    # Validate required configuration
    if not USER_POOL_ID:
        LOGGER.error("COGNITO_USER_POOL_ID environment variable not set")
        sys.exit(1)
    
    if not APP_CLIENT_ID:
        LOGGER.error("COGNITO_APP_CLIENT_ID environment variable not set")
        sys.exit(1)
    
    LOGGER.info("Initializing Workset Monitor API (with authentication)")
    
    # Initialize state database
    LOGGER.info(f"Connecting to DynamoDB table: {WORKSET_TABLE}")
    state_db = WorksetStateDB(
        table_name=WORKSET_TABLE,
        region=REGION,
    )
    
    # Initialize scheduler (optional)
    LOGGER.info("Initializing workset scheduler")
    scheduler = WorksetScheduler(state_db)
    
    # Initialize validator (optional)
    LOGGER.info("Initializing workset validator")
    validator = WorksetValidator(region=REGION)
    
    # Initialize customer manager (optional)
    LOGGER.info("Initializing customer manager")
    customer_manager = CustomerManager(region=REGION)
    
    # Initialize Cognito authentication
    LOGGER.info("Initializing AWS Cognito authentication")
    cognito_auth = CognitoAuth(
        region=REGION,
        user_pool_id=USER_POOL_ID,
        app_client_id=APP_CLIENT_ID,
    )
    
    # Create FastAPI app WITH authentication
    LOGGER.info("Creating FastAPI application (authentication enabled)")
    app = create_app(
        state_db=state_db,
        scheduler=scheduler,
        cognito_auth=cognito_auth,
        customer_manager=customer_manager,
        validator=validator,
        enable_auth=True,  # Enable authentication
    )
    
    LOGGER.info("=" * 60)
    LOGGER.info("Workset Monitor API Server")
    LOGGER.info("=" * 60)
    LOGGER.info("Authentication: ENABLED (AWS Cognito)")
    LOGGER.info("Region: %s", REGION)
    LOGGER.info("DynamoDB Table: %s", WORKSET_TABLE)
    LOGGER.info("User Pool ID: %s", USER_POOL_ID)
    LOGGER.info("App Client ID: %s", APP_CLIENT_ID)
    LOGGER.info("")
    LOGGER.info("Starting server on http://0.0.0.0:8000")
    LOGGER.info("API Documentation: http://localhost:8000/docs")
    LOGGER.info("")
    LOGGER.info("NOTE: All API requests require a valid JWT token")
    LOGGER.info("Include token in Authorization header: Bearer <token>")
    LOGGER.info("=" * 60)
    
    # Run the server
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
    )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        LOGGER.info("\nShutting down server...")
    except Exception as e:
        LOGGER.error("Failed to start server: %s", e, exc_info=True)
        sys.exit(1)

