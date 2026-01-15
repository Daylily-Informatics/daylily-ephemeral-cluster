"""Tests for customer management."""

from unittest.mock import MagicMock, patch

import pytest

from daylib.workset_customer import CustomerManager, CustomerConfig


@pytest.fixture
def mock_aws():
    """Mock AWS services."""
    with patch("daylib.workset_customer.boto3.Session") as mock_session:
        mock_s3 = MagicMock()
        mock_dynamodb = MagicMock()
        mock_table = MagicMock()

        mock_session.return_value.client.return_value = mock_s3
        mock_session.return_value.resource.return_value = mock_dynamodb
        mock_dynamodb.Table.return_value = mock_table

        yield {
            "session": mock_session,
            "s3": mock_s3,
            "dynamodb": mock_dynamodb,
            "table": mock_table,
        }


@pytest.fixture
def customer_manager(mock_aws):
    """Create CustomerManager instance."""
    return CustomerManager(
        region="us-west-2",
        profile=None,
        bucket_prefix="test-customer",
    )


def test_generate_customer_id(customer_manager):
    """Test customer ID generation."""
    customer_id = customer_manager._generate_customer_id("Test Customer")

    assert customer_id.startswith("test-customer-")
    assert len(customer_id) > len("test-customer-")


def test_onboard_customer(customer_manager, mock_aws):
    """Test customer onboarding."""
    mock_table = mock_aws["table"]

    config = customer_manager.onboard_customer(
        customer_name="Test Customer",
        email="test@example.com",
        max_concurrent_worksets=10,
        max_storage_gb=2000,
        cost_center="CC-123",
    )

    assert isinstance(config, CustomerConfig)
    assert config.customer_name == "Test Customer"
    assert config.email == "test@example.com"
    assert config.max_concurrent_worksets == 10
    assert config.max_storage_gb == 2000
    assert config.cost_center == "CC-123"
    assert config.s3_bucket.startswith("test-customer-")

    # Verify S3 bucket creation was called
    mock_aws["s3"].create_bucket.assert_called_once()

    # Verify DynamoDB put_item was called
    mock_table.put_item.assert_called_once()


def test_save_customer_config(customer_manager, mock_aws):
    """Test saving customer configuration."""
    mock_table = mock_aws["table"]

    config = CustomerConfig(
        customer_id="test-123",
        customer_name="Test Customer",
        email="test@example.com",
        s3_bucket="test-bucket",
        max_concurrent_worksets=5,
        max_storage_gb=1000,
        billing_account_id="BA-456",
        cost_center="CC-789",
    )

    customer_manager._save_customer_config(config)

    mock_table.put_item.assert_called_once()
    call_args = mock_table.put_item.call_args
    item = call_args[1]["Item"]

    assert item["customer_id"] == "test-123"
    assert item["customer_name"] == "Test Customer"
    assert item["email"] == "test@example.com"
    assert item["billing_account_id"] == "BA-456"
    assert item["cost_center"] == "CC-789"


def test_get_customer_config(customer_manager, mock_aws):
    """Test getting customer configuration."""
    mock_table = mock_aws["table"]
    mock_table.get_item.return_value = {
        "Item": {
            "customer_id": "test-123",
            "customer_name": "Test Customer",
            "email": "test@example.com",
            "s3_bucket": "test-bucket",
            "max_concurrent_worksets": 5,
            "max_storage_gb": 1000,
        }
    }

    config = customer_manager.get_customer_config("test-123")

    assert config is not None
    assert config.customer_id == "test-123"
    assert config.customer_name == "Test Customer"
    assert config.email == "test@example.com"


def test_get_customer_config_not_found(customer_manager, mock_aws):
    """Test getting non-existent customer."""
    mock_table = mock_aws["table"]
    mock_table.get_item.return_value = {}

    config = customer_manager.get_customer_config("nonexistent")

    assert config is None


def test_list_customers(customer_manager, mock_aws):
    """Test listing customers."""
    mock_table = mock_aws["table"]
    mock_table.scan.return_value = {
        "Items": [
            {
                "customer_id": "test-1",
                "customer_name": "Customer 1",
                "email": "customer1@example.com",
                "s3_bucket": "bucket-1",
                "max_concurrent_worksets": 5,
                "max_storage_gb": 1000,
            },
            {
                "customer_id": "test-2",
                "customer_name": "Customer 2",
                "email": "customer2@example.com",
                "s3_bucket": "bucket-2",
                "max_concurrent_worksets": 10,
                "max_storage_gb": 2000,
            },
        ]
    }

    customers = customer_manager.list_customers()

    assert len(customers) == 2
    assert customers[0].customer_id == "test-1"
    assert customers[1].customer_id == "test-2"

