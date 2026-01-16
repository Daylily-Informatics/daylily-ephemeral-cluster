#!/usr/bin/env python3
"""Example: Run the Workset Monitor API without authentication.

This example shows how to run the API server without requiring authentication.
This is useful for development, testing, or internal deployments where
authentication is handled at a different layer (e.g., VPN, network security).

Prerequisites:
    pip install -e .

Usage:
    python examples/run_api_without_auth.py

Then access the API at:
    http://localhost:8001
    http://localhost:8001/docs  (Swagger UI)
    http://localhost:8001/redoc (ReDoc)
"""

import logging
import sys
from pathlib import Path

# Add parent directory to path to import daylib
sys.path.insert(0, str(Path(__file__).parent.parent))

# Check for required dependencies
try:
    from daylib.workset_api import create_app
except ModuleNotFoundError as e:
    print("ERROR: Required dependencies not installed")
    print(f"Missing module: {e.name}")
    print()
    print("Please install the package first:")
    print("  pip install -e .")
    print()
    print("Or install specific dependencies:")
    print("  pip install fastapi uvicorn boto3 pyyaml pydantic")
    sys.exit(1)
from daylib.workset_state_db import WorksetStateDB
from daylib.workset_scheduler import WorksetScheduler
from daylib.workset_validation import WorksetValidator
from daylib.workset_customer import CustomerManager

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


def main():
    """Run the API server without authentication."""
    
    # Configuration
    REGION = "us-west-2"
    WORKSET_TABLE = "daylily-worksets"
    
    LOGGER.info("Initializing Workset Monitor API (no authentication)")
    
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

    # Initialize file registry (optional)
    file_registry = None
    if FILE_MANAGEMENT_AVAILABLE:
        LOGGER.info("Initializing file registry")
        try:
            import boto3
            dynamodb = boto3.resource('dynamodb', region_name=REGION)
            file_registry = FileRegistry()
            LOGGER.info("File registry initialized - file management endpoints will be available")
        except Exception as e:
            LOGGER.warning("Failed to initialize file registry: %s", e)
            LOGGER.warning("File management endpoints will not be available")
    else:
        LOGGER.info("File management not available - install file management modules to enable")

    # Create FastAPI app WITHOUT authentication
    LOGGER.info("Creating FastAPI application (authentication disabled)")
    app = create_app(
        state_db=state_db,
        scheduler=scheduler,
        cognito_auth=None,  # No authentication
        customer_manager=customer_manager,
        validator=validator,
        file_registry=file_registry,
        enable_auth=False,  # Disable authentication
    )
    
    LOGGER.info("=" * 60)
    LOGGER.info("Workset Monitor API Server")
    LOGGER.info("=" * 60)
    LOGGER.info("Authentication: DISABLED")
    LOGGER.info("Region: %s", REGION)
    LOGGER.info("DynamoDB Table: %s", WORKSET_TABLE)
    LOGGER.info("")
    LOGGER.info("Starting server on http://0.0.0.0:8001")
    LOGGER.info("API Documentation: http://localhost:8001/docs")
    LOGGER.info("Alternative Docs: http://localhost:8001/redoc")
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

