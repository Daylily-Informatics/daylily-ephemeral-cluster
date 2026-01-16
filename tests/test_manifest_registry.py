"""Unit tests for daylib.manifest_registry.

These tests exercise DynamoDB manifest storage helpers including:
- gzip+base64 encoding/decoding via save_manifest / get_manifest_tsv
- listing manifests by customer
- TSV parsing is covered in test_manifest_api.py
"""

from unittest.mock import MagicMock, patch

import pytest

from daylib.manifest_registry import (
    ManifestRegistry,
    SavedManifest,
    _estimate_sample_count,
    _gzip_b64_decode,
    _gzip_b64_encode,
    _sha256_hex,
)


@pytest.fixture
def mock_dynamodb():
    """Mock boto3 DynamoDB session/resource used by ManifestRegistry.

    We patch boto3.Session at the module level so __init__ does not talk to AWS.
    """

    with patch("daylib.manifest_registry.boto3.Session") as mock_session:
        mock_resource = MagicMock()
        mock_session.return_value.resource.return_value = mock_resource
        yield mock_resource


@pytest.fixture
def manifest_registry(mock_dynamodb):
    """Create a ManifestRegistry instance with a mocked DynamoDB table."""

    registry = ManifestRegistry(table_name="test-manifests")
    # Replace the real DynamoDB table handle with a MagicMock for unit testing
    registry.table = MagicMock()
    return registry


class TestSaveManifestEncoding:
    """Tests for save_manifest() encoding and stored metadata."""

    def test_save_manifest_encodes_tsv_and_stores_metadata(self, manifest_registry):
        """save_manifest should gzip+base64 encode TSV and persist metadata.

        This indirectly verifies _gzip_b64_encode / _gzip_b64_decode and
        sample counting / sha256 helpers.
        """

        tsv_content = "RUN_ID\tSAMPLE_ID\nR0\tHG002\n"
        manifest_registry.table.put_item.return_value = {}

        saved = manifest_registry.save_manifest(
            customer_id="cust-001",
            tsv_content=tsv_content,
            name="Run 1",
            description="Test manifest",
        )

        # Basic SavedManifest properties
        assert isinstance(saved, SavedManifest)
        assert saved.customer_id == "cust-001"
        assert saved.manifest_id.startswith("m-")

        # Helpers should produce consistent metadata
        assert saved.sample_count == _estimate_sample_count(tsv_content)
        assert saved.tsv_sha256 == _sha256_hex(tsv_content)
        assert _gzip_b64_decode(saved.tsv_gzip_b64) == tsv_content

        # Verify what was written to DynamoDB
        manifest_registry.table.put_item.assert_called_once()
        kwargs = manifest_registry.table.put_item.call_args.kwargs
        item = kwargs["Item"]

        assert item["customer_id"] == "cust-001"
        assert item["sample_count"] == saved.sample_count
        assert item["tsv_sha256"] == saved.tsv_sha256
        # Stored payload round-trips via gzip+base64
        assert _gzip_b64_decode(item["tsv_gzip_b64"]) == tsv_content


class TestListCustomerManifests:
    """Tests for listing manifests by customer_id."""

    def test_list_customer_manifests_normalizes_fields(self, manifest_registry):
        """list_customer_manifests should coerce types and normalize empty strings."""

        manifest_registry.table.query.return_value = {
            "Items": [
                {
                    "manifest_id": "m-1",
                    "customer_id": "cust-001",
                    "name": "Run 1",
                    "description": "",  # should be normalized to None
                    "created_at": "2026-01-01T00:00:00Z",
                    "sample_count": "3",  # stored as string in DynamoDB
                }
            ]
        }

        manifests = manifest_registry.list_customer_manifests("cust-001")

        assert len(manifests) == 1
        m = manifests[0]
        assert m["manifest_id"] == "m-1"
        assert m["customer_id"] == "cust-001"
        assert m["name"] == "Run 1"
        assert m["description"] is None  # empty string normalized
        assert m["sample_count"] == 3  # coerced to int


class TestGetManifestAndTsv:
    """Tests for get_manifest() and get_manifest_tsv()."""

    def test_get_manifest_and_tsv_round_trip(self, manifest_registry):
        """get_manifest_tsv should decode the stored gzip+base64 payload."""

        tsv_content = "RUN_ID\tSAMPLE_ID\tR1_FQ\tR2_FQ\nrun1\tsample1\tr1.fq\tr2.fq\n"
        encoded = _gzip_b64_encode(tsv_content)

        manifest_registry.table.get_item.return_value = {
            "Item": {
                "manifest_id": "m-1",
                "customer_id": "cust-001",
                "name": "Run 1",
                "description": "",
                "created_at": "2026-01-01T00:00:00Z",
                "sample_count": 1,
                "tsv_sha256": _sha256_hex(tsv_content),
                "tsv_gzip_b64": encoded,
            }
        }

        saved = manifest_registry.get_manifest(customer_id="cust-001", manifest_id="m-1")

        assert isinstance(saved, SavedManifest)
        assert saved.manifest_id == "m-1"
        assert saved.customer_id == "cust-001"
        assert saved.sample_count == 1
        assert saved.tsv_sha256 == _sha256_hex(tsv_content)

        round_tripped = manifest_registry.get_manifest_tsv(
            customer_id="cust-001", manifest_id="m-1"
        )
        assert round_tripped == tsv_content


    def test_get_manifest_returns_none_when_not_found(self, manifest_registry):
        """If DynamoDB returns no Item, get_manifest should return None."""

        manifest_registry.table.get_item.return_value = {}

        result = manifest_registry.get_manifest(customer_id="cust-001", manifest_id="m-missing")
        assert result is None


class TestCreateTableIfNotExists:
    """Tests for ManifestRegistry.create_table_if_not_exists behavior."""

    def test_create_table_if_not_exists_noop_when_table_exists(self, mock_dynamodb):
        """If table.load() succeeds, create_table_if_not_exists should not call create_table."""

        # Bind registry to mocked DynamoDB; leave table as the default from __init__
        registry = ManifestRegistry(table_name="test-manifests-existing")
        registry.dynamodb = mock_dynamodb

        # Simulate table already existing: .load() does not raise
        registry.table.load = MagicMock(return_value=None)

        registry.create_table_if_not_exists()

        # When table exists, we must not attempt to create it again
        assert not mock_dynamodb.create_table.called

    def test_create_table_if_not_exists_creates_when_missing(self, mock_dynamodb):
        """If table.load() raises ResourceNotFoundException, create the table and wait."""

        from botocore.exceptions import ClientError

        registry = ManifestRegistry(table_name="test-manifests-missing")
        registry.dynamodb = mock_dynamodb

        # Configure table.load() to raise ResourceNotFoundException
        error_response = {"Error": {"Code": "ResourceNotFoundException", "Message": "Not found"}}
        registry.table.load = MagicMock(
            side_effect=ClientError(error_response, "DescribeTable")
        )

        # Mock create_table to return an object with wait_until_exists()
        mock_table_obj = MagicMock()
        mock_dynamodb.create_table.return_value = mock_table_obj

        registry.create_table_if_not_exists()

        mock_dynamodb.create_table.assert_called_once()
        mock_table_obj.wait_until_exists.assert_called_once()
