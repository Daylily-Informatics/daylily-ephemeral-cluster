"""Tests for saved manifest API endpoints in workset_api.

These endpoints allow the customer portal to persist/reload stage_samples.tsv
manifests using a ManifestRegistry backend.
"""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from daylib.manifest_registry import ManifestTooLargeError, SavedManifest, parse_tsv_to_samples
from daylib.workset_api import create_app
from daylib.workset_state_db import WorksetStateDB


# ============================================================================
# Tests for parse_tsv_to_samples helper function
# ============================================================================


def test_parse_tsv_to_samples_basic():
    """Test parsing a basic TSV with required columns."""
    tsv = "RUN_ID\tSAMPLE_ID\tR1_FQ\tR2_FQ\nrun1\tsample1\ts3://bucket/r1.fq.gz\ts3://bucket/r2.fq.gz\n"
    samples = parse_tsv_to_samples(tsv)
    assert len(samples) == 1
    assert samples[0]["sample_id"] == "sample1"
    assert samples[0]["r1_file"] == "s3://bucket/r1.fq.gz"
    assert samples[0]["r2_file"] == "s3://bucket/r2.fq.gz"
    assert samples[0]["run_id"] == "run1"
    assert samples[0]["status"] == "pending"


def test_parse_tsv_to_samples_multiple_rows():
    """Test parsing TSV with multiple samples."""
    tsv = """RUN_ID\tSAMPLE_ID\tR1_FQ\tR2_FQ
run1\tsample1\ts3://bucket/s1_r1.fq.gz\ts3://bucket/s1_r2.fq.gz
run1\tsample2\ts3://bucket/s2_r1.fq.gz\ts3://bucket/s2_r2.fq.gz
run1\tsample3\ts3://bucket/s3_r1.fq.gz\ts3://bucket/s3_r2.fq.gz"""
    samples = parse_tsv_to_samples(tsv)
    assert len(samples) == 3
    assert samples[0]["sample_id"] == "sample1"
    assert samples[1]["sample_id"] == "sample2"
    assert samples[2]["sample_id"] == "sample3"


def test_parse_tsv_to_samples_with_optional_columns():
    """Test parsing TSV with optional columns like SAMPLE_TYPE and LIB_PREP."""
    tsv = "RUN_ID\tSAMPLE_ID\tR1_FQ\tR2_FQ\tSAMPLE_TYPE\tLIB_PREP\tEXTERNAL_SAMPLE_ID\nrun1\tsample1\tr1.fq\tr2.fq\tWGS\tILLUMINA\text-001\n"
    samples = parse_tsv_to_samples(tsv)
    assert len(samples) == 1
    assert samples[0]["sample_type"] == "WGS"
    assert samples[0]["lib_prep"] == "ILLUMINA"
    assert samples[0]["external_sample_id"] == "ext-001"


def test_parse_tsv_to_samples_empty_content():
    """Test parsing empty TSV content."""
    samples = parse_tsv_to_samples("")
    assert samples == []


def test_parse_tsv_to_samples_header_only():
    """Test parsing TSV with only header row."""
    tsv = "RUN_ID\tSAMPLE_ID\tR1_FQ\tR2_FQ\n"
    samples = parse_tsv_to_samples(tsv)
    assert samples == []


def test_parse_tsv_to_samples_skips_malformed_lines():
    """Test that malformed lines (too few columns) are skipped."""
    tsv = "RUN_ID\tSAMPLE_ID\tR1_FQ\tR2_FQ\nrun1\tsample1\tr1.fq\tr2.fq\nx\n"
    samples = parse_tsv_to_samples(tsv)
    # Should only have the valid sample, malformed line skipped
    assert len(samples) == 1
    assert samples[0]["sample_id"] == "sample1"


def test_parse_tsv_to_samples_missing_sample_id_skipped():
    """Test that rows without sample_id are skipped."""
    tsv = "RUN_ID\tSAMPLE_ID\tR1_FQ\tR2_FQ\nrun1\t\tr1.fq\tr2.fq\nrun1\tsample2\tr1.fq\tr2.fq\n"
    samples = parse_tsv_to_samples(tsv)
    # First row has empty sample_id, should be skipped
    assert len(samples) == 1
    assert samples[0]["sample_id"] == "sample2"


# ============================================================================
# Tests for manifest API endpoints
# ============================================================================


@pytest.fixture
def mock_state_db():
    db = MagicMock(spec=WorksetStateDB)
    db.get_workset.return_value = None
    db.list_worksets_by_state.return_value = []
    db.list_archived_worksets.return_value = []
    return db


@pytest.fixture
def mock_customer_manager():
    mgr = MagicMock()
    cfg = MagicMock()
    cfg.customer_id = "cust-001"
    cfg.s3_bucket = "test-bucket"
    mgr.get_customer_config.side_effect = lambda cid: cfg if cid == "cust-001" else None
    return mgr


@pytest.fixture
def mock_manifest_registry():
    registry = MagicMock()
    registry.list_customer_manifests.return_value = [
        {
            "manifest_id": "m-1",
            "customer_id": "cust-001",
            "name": "Run 1",
            "description": None,
            "created_at": "2026-01-01T00:00:00Z",
            "sample_count": 1,
            "tsv_sha256": "abc",
        }
    ]
    registry.get_manifest.return_value = SavedManifest(
        manifest_id="m-1",
        customer_id="cust-001",
        name="Run 1",
        description=None,
        created_at="2026-01-01T00:00:00Z",
        sample_count=1,
        tsv_sha256="abc",
        tsv_gzip_b64="Z3o=",  # not used in these API tests
    )
    registry.get_manifest_tsv.return_value = "RUN_ID\tSAMPLE_ID\nR0\tHG002\n"
    registry.save_manifest.return_value = SavedManifest(
        manifest_id="m-2",
        customer_id="cust-001",
        name="Saved",
        description=None,
        created_at="2026-01-02T00:00:00Z",
        sample_count=1,
        tsv_sha256="def",
        tsv_gzip_b64="Z3o=",
    )
    return registry


@pytest.fixture
def client(mock_state_db, mock_customer_manager, mock_manifest_registry):
    app = create_app(
        state_db=mock_state_db,
        customer_manager=mock_customer_manager,
        manifest_registry=mock_manifest_registry,
        enable_auth=False,
    )
    return TestClient(app)


def test_list_customer_manifests(client, mock_manifest_registry):
    resp = client.get("/api/customers/cust-001/manifests")
    assert resp.status_code == 200
    data = resp.json()
    assert "manifests" in data
    assert len(data["manifests"]) == 1
    mock_manifest_registry.list_customer_manifests.assert_called_once()


def test_save_customer_manifest(client, mock_manifest_registry):
    payload = {"tsv_content": "RUN_ID\tSAMPLE_ID\nR0\tHG002\n", "name": "Saved"}
    resp = client.post("/api/customers/cust-001/manifests", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["manifest"]["manifest_id"] == "m-2"
    assert data["download_url"].endswith("/m-2/download")
    mock_manifest_registry.save_manifest.assert_called_once()


def test_download_customer_manifest(client, mock_manifest_registry):
    resp = client.get("/api/customers/cust-001/manifests/m-1/download")
    assert resp.status_code == 200
    assert resp.text.startswith("RUN_ID")
    assert "attachment" in resp.headers.get("content-disposition", "")
    mock_manifest_registry.get_manifest_tsv.assert_called_once_with(
        customer_id="cust-001", manifest_id="m-1"
    )


def test_save_customer_manifest_413_when_too_large(client, mock_manifest_registry):
    mock_manifest_registry.save_manifest.side_effect = ManifestTooLargeError("too big")
    resp = client.post(
        "/api/customers/cust-001/manifests",
        json={"tsv_content": "X" * 10, "name": "big"},
    )
    assert resp.status_code == 413


def test_manifest_storage_not_configured_returns_503(mock_state_db, mock_customer_manager, monkeypatch):
    import daylib.workset_api as workset_api

    # Ensure create_app does not auto-initialize manifest registry.
    monkeypatch.setattr(workset_api, "MANIFEST_STORAGE_AVAILABLE", False)

    app = create_app(
        state_db=mock_state_db,
        customer_manager=mock_customer_manager,
        manifest_registry=None,
        enable_auth=False,
    )
    test_client = TestClient(app)
    resp = test_client.get("/api/customers/cust-001/manifests")
    assert resp.status_code == 503


# ====================================================================================
# Tests for workset creation using manifest_id / manifest_tsv_content
# ============================================================================


@pytest.fixture
def mock_integration():
    """Mock WorksetIntegration used by create_app for workset registration."""

    integ = MagicMock()
    integ.bucket = "control-bucket"
    integ.register_workset.return_value = True
    return integ


@pytest.fixture
def client_with_integration(
    mock_state_db, mock_customer_manager, mock_manifest_registry, mock_integration
):
    """FastAPI TestClient with manifest registry and integration layer wired up."""

    app = create_app(
        state_db=mock_state_db,
        customer_manager=mock_customer_manager,
        manifest_registry=mock_manifest_registry,
        integration=mock_integration,
        enable_auth=False,
    )
    return TestClient(app)


def _build_workset_payload(**overrides):
    """Helper to build minimum payload for /worksets endpoint."""

    base = {
        "workset_name": "HG002 WGS",
        "pipeline_type": "wgs",
        "reference_genome": "hg38",
        "s3_prefix": "",
        "priority": "normal",
        "notification_email": None,
        "enable_qc": True,
        "archive_results": True,
    }
    base.update(overrides)
    return base


def test_create_workset_from_saved_manifest_id(
    client_with_integration, mock_manifest_registry, mock_integration
):
    """create_customer_workset should load TSV via manifest_id and pass to integration.

    Verifies that:
    - ManifestRegistry.get_manifest_tsv is called with customer_id and manifest_id
    - Samples are parsed and included in metadata
    - Raw TSV content is attached as metadata['stage_samples_tsv']
    - Control bucket from integration is used for registration
    """

    payload = _build_workset_payload(manifest_id="m-1")

    resp = client_with_integration.post("/api/customers/cust-001/worksets", json=payload)
    assert resp.status_code == 200

    mock_manifest_registry.get_manifest_tsv.assert_called_once_with(
        customer_id="cust-001", manifest_id="m-1"
    )

    # Integration layer should receive normalized samples and raw TSV
    assert mock_integration.register_workset.called
    call_kwargs = mock_integration.register_workset.call_args.kwargs

    assert call_kwargs["bucket"] == "control-bucket"  # control-plane bucket
    assert call_kwargs["customer_id"] == "cust-001"
    assert call_kwargs["write_s3"] is True
    assert call_kwargs["write_dynamodb"] is True

    metadata = call_kwargs["metadata"]
    assert metadata["sample_count"] == 1
    assert len(metadata["samples"]) == 1
    # TSV from mock_manifest_registry has SAMPLE_ID=HG002
    assert metadata["samples"][0]["sample_id"] == "HG002"
    assert metadata["stage_samples_tsv"].startswith("RUN_ID\tSAMPLE_ID")

    # S3 prefix should follow worksets/<safe-name>-<uuid>/ pattern
    prefix = call_kwargs["prefix"]
    assert prefix.startswith("worksets/hg002-wgs-")
    assert prefix.endswith("/")


def test_create_workset_from_raw_manifest_tsv_content(client_with_integration, mock_integration):
    """create_customer_workset should accept raw TSV content and parse it.

    Ensures that manifest_tsv_content is parsed into samples and that the
    original TSV is written to metadata['stage_samples_tsv'].
    """

    tsv_content = (
        "RUN_ID\tSAMPLE_ID\tR1_FQ\tR2_FQ\n"
        "run1\tsample1\ts3://bucket/r1.fq.gz\ts3://bucket/r2.fq.gz\n"
    )

    payload = _build_workset_payload(manifest_tsv_content=tsv_content)

    resp = client_with_integration.post("/api/customers/cust-001/worksets", json=payload)
    assert resp.status_code == 200

    # When using raw TSV content, ManifestRegistry is not consulted
    # (only parse_tsv_to_samples is used inside the endpoint).
    assert mock_integration.register_workset.called
    call_kwargs = mock_integration.register_workset.call_args.kwargs

    metadata = call_kwargs["metadata"]
    assert metadata["sample_count"] == 1
    assert len(metadata["samples"]) == 1
    assert metadata["samples"][0]["sample_id"] == "sample1"
    assert metadata["samples"][0]["r1_file"].endswith("r1.fq.gz")
    assert metadata["samples"][0]["r2_file"].endswith("r2.fq.gz")
    assert metadata["stage_samples_tsv"] == tsv_content

    # Prefix pattern should be the same for raw TSV-driven worksets
    prefix = call_kwargs["prefix"]
    assert prefix.startswith("worksets/hg002-wgs-")
    assert prefix.endswith("/")


