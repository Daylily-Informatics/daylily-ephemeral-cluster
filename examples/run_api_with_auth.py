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

    # Run the server (HTTP)
    python examples/run_api_with_auth.py

    # Run with custom port
    python examples/run_api_with_auth.py --port 8443

    # Run with HTTPS
    python examples/run_api_with_auth.py --https --cert /path/to/cert.pem --key /path/to/key.pem

    # Run with HTTPS on custom port
    python examples/run_api_with_auth.py --https --port 8443 --cert cert.pem --key key.pem

Then access the API at:
    http://localhost:8001  (or https:// if --https is used)
    http://localhost:8001/docs  (Swagger UI with authentication)
"""

import argparse
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

# Try to import file management (optional)
try:
    from daylib.file_registry import FileRegistry
    FILE_MANAGEMENT_AVAILABLE = True
except ImportError:
    FILE_MANAGEMENT_AVAILABLE = False
    FileRegistry = None

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

LOGGER = logging.getLogger(__name__)


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Run Workset Monitor API with authentication",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Run on default port (8001) with HTTP
    python run_api_with_auth.py

    # Run on custom port
    python run_api_with_auth.py --port 8443

    # Run with HTTPS (requires cert and key files)
    python run_api_with_auth.py --https --cert cert.pem --key key.pem

    # Run HTTPS on custom port
    python run_api_with_auth.py --https --port 8443 --cert /etc/ssl/cert.pem --key /etc/ssl/key.pem

    # Generate self-signed certificate for testing:
    openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes
        """,
    )
    parser.add_argument(
        "--port", "-p",
        type=int,
        default=8001,
        help="Port to run the server on (default: 8001)",
    )
    parser.add_argument(
        "--https",
        action="store_true",
        help="Enable HTTPS (requires --cert and --key)",
    )
    parser.add_argument(
        "--cert",
        type=str,
        help="Path to SSL certificate file (PEM format)",
    )
    parser.add_argument(
        "--key",
        type=str,
        help="Path to SSL private key file (PEM format)",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Host to bind to (default: 0.0.0.0)",
    )
    return parser.parse_args()


def main():
    """Run the API server with authentication."""
    args = parse_args()

    # Validate HTTPS configuration
    if args.https:
        if not args.cert or not args.key:
            LOGGER.error("HTTPS requires both --cert and --key options")
            sys.exit(1)
        cert_path = Path(args.cert)
        key_path = Path(args.key)
        if not cert_path.exists():
            LOGGER.error(f"Certificate file not found: {args.cert}")
            sys.exit(1)
        if not key_path.exists():
            LOGGER.error(f"Key file not found: {args.key}")
            sys.exit(1)

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

    # Initialize file registry (optional)
    file_registry = None
    if FILE_MANAGEMENT_AVAILABLE:
        LOGGER.info("Initializing file registry")
        try:
            import boto3
            import logging

            logging.basicConfig(level=logging.DEBUG)

            logging.getLogger("botocore").setLevel(logging.DEBUG)
            logging.getLogger("boto3").setLevel(logging.DEBUG)
            logging.getLogger("botocore.hooks").setLevel(logging.DEBUG)
            dynamodb = boto3.resource('dynamodb', region_name=REGION)
            file_registry = FileRegistry()
            LOGGER.info("File registry initialized - file management endpoints will be available")
        except Exception as e:
            LOGGER.warning("Failed to initialize file registry: %s", e)
            LOGGER.warning("File management endpoints will not be available")
    else:
        LOGGER.info("File management not available - install file management modules to enable")

    # Create FastAPI app WITH authentication
    LOGGER.info("Creating FastAPI application (authentication enabled)")
    app = create_app(
        state_db=state_db,
        scheduler=scheduler,
        cognito_auth=cognito_auth,
        customer_manager=customer_manager,
        validator=validator,
        file_registry=file_registry,
        enable_auth=True,  # Enable authentication
    )

    # Determine protocol and URL
    protocol = "https" if args.https else "http"
    base_url = f"{protocol}://{args.host}:{args.port}"

    LOGGER.info("=" * 60)
    LOGGER.info("Workset Monitor API Server")
    LOGGER.info("=" * 60)
    LOGGER.info("Authentication: ENABLED (AWS Cognito)")
    LOGGER.info("Protocol: %s", protocol.upper())
    LOGGER.info("Region: %s", REGION)
    LOGGER.info("DynamoDB Table: %s", WORKSET_TABLE)
    LOGGER.info("User Pool ID: %s", USER_POOL_ID)
    LOGGER.info("App Client ID: %s", APP_CLIENT_ID)
    if args.https:
        LOGGER.info("SSL Certificate: %s", args.cert)
        LOGGER.info("SSL Key: %s", args.key)
    LOGGER.info("")
    LOGGER.info("Starting server on %s", base_url)
    LOGGER.info("API Documentation: %s/docs", base_url)
    LOGGER.info("")
    LOGGER.info("NOTE: All API requests require a valid JWT token")
    LOGGER.info("Include token in Authorization header: Bearer <token>")
    LOGGER.info("=" * 60)

    # Run the server
    import uvicorn
    uvicorn_kwargs = {
        "app": app,
        "host": args.host,
        "port": args.port,
        "log_level": "trace",
    }

    if args.https:
        uvicorn_kwargs["ssl_certfile"] = args.cert
        uvicorn_kwargs["ssl_keyfile"] = args.key

    uvicorn.run(**uvicorn_kwargs)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        LOGGER.info("\nShutting down server...")
    except Exception as e:
        LOGGER.error("Failed to start server: %s", e, exc_info=True)
        sys.exit(1)

