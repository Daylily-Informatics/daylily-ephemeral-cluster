"""Tests for multi-region workset state management."""

from unittest.mock import MagicMock, patch, PropertyMock
import datetime as dt

import pytest
from botocore.exceptions import ClientError, EndpointConnectionError

from daylib.workset_multi_region import (
    WorksetMultiRegionDB,
    MultiRegionConfig,
    RegionStatus,
    RegionHealth,
)
from daylib.workset_state_db import WorksetState, WorksetPriority


@pytest.fixture
def mock_state_db():
    """Create mock WorksetStateDB."""
    mock_db = MagicMock()
    mock_db.table = MagicMock()
    mock_db.get_workset.return_value = {
        "workset_id": "test-ws-001",
        "state": "ready",
        "priority": "normal",
    }
    mock_db.list_worksets_by_state.return_value = []
    mock_db.get_queue_depth.return_value = {"ready": 5, "in_progress": 2}
    return mock_db


@pytest.fixture
def multi_region_config():
    """Create test multi-region config."""
    return MultiRegionConfig(
        primary_region="us-west-2",
        replica_regions=["us-east-1", "eu-west-1"],
        table_name="test-worksets",
        health_check_interval_seconds=5,
        failover_threshold=2,
    )


@pytest.fixture
def multi_region_db(multi_region_config, mock_state_db):
    """Create multi-region DB with mocked connections."""
    with patch("daylib.workset_multi_region.WorksetStateDB") as MockDB:
        MockDB.return_value = mock_state_db
        db = WorksetMultiRegionDB(multi_region_config)
        return db


class TestRegionHealth:
    """Test RegionHealth dataclass."""

    def test_healthy_region_is_available(self):
        """Test healthy region is available."""
        health = RegionHealth(region="us-west-2", status=RegionStatus.HEALTHY)
        assert health.is_available()

    def test_degraded_region_is_available(self):
        """Test degraded region is still available."""
        health = RegionHealth(region="us-west-2", status=RegionStatus.DEGRADED)
        assert health.is_available()

    def test_unhealthy_region_not_available(self):
        """Test unhealthy region is not available."""
        health = RegionHealth(region="us-west-2", status=RegionStatus.UNHEALTHY)
        assert not health.is_available()

    def test_unknown_region_not_available(self):
        """Test unknown region is not available."""
        health = RegionHealth(region="us-west-2", status=RegionStatus.UNKNOWN)
        assert not health.is_available()


class TestMultiRegionConfig:
    """Test MultiRegionConfig."""

    def test_default_values(self):
        """Test default config values."""
        config = MultiRegionConfig(primary_region="us-west-2")
        assert config.table_name == "daylily-worksets"
        assert config.health_check_interval_seconds == 30
        assert config.failover_threshold == 3
        assert config.latency_threshold_ms == 500.0
        assert config.enable_global_tables is True
        assert config.replica_regions == []


class TestMultiRegionDBInitialization:
    """Test WorksetMultiRegionDB initialization."""

    def test_init_all_regions(self, multi_region_db, multi_region_config):
        """Test all regions are initialized."""
        assert len(multi_region_db._connections) == 3
        assert len(multi_region_db._region_health) == 3
        assert multi_region_db._active_region == multi_region_config.primary_region

    def test_init_creates_health_records(self, multi_region_db):
        """Test health records created for all regions."""
        assert "us-west-2" in multi_region_db._region_health
        assert "us-east-1" in multi_region_db._region_health
        assert "eu-west-1" in multi_region_db._region_health


class TestHealthMonitoring:
    """Test health monitoring functionality."""

    def test_check_region_health_success(self, multi_region_db, mock_state_db):
        """Test successful health check updates status."""
        multi_region_db._check_region_health("us-west-2")
        
        health = multi_region_db._region_health["us-west-2"]
        assert health.status == RegionStatus.HEALTHY
        assert health.consecutive_failures == 0
        assert health.last_check is not None

    def test_check_region_health_failure(self, multi_region_db, mock_state_db):
        """Test failed health check updates status."""
        mock_state_db.table.load.side_effect = ClientError(
            {"Error": {"Code": "ServiceUnavailable", "Message": "test"}},
            "DescribeTable",
        )
        
        multi_region_db._check_region_health("us-west-2")
        
        health = multi_region_db._region_health["us-west-2"]
        assert health.status == RegionStatus.DEGRADED
        assert health.consecutive_failures == 1

    def test_consecutive_failures_mark_unhealthy(self, multi_region_db, mock_state_db):
        """Test consecutive failures mark region unhealthy."""
        mock_state_db.table.load.side_effect = ClientError(
            {"Error": {"Code": "ServiceUnavailable", "Message": "test"}},
            "DescribeTable",
        )

        # Fail enough times to trigger unhealthy status
        for _ in range(3):
            multi_region_db._check_region_health("us-west-2")

        health = multi_region_db._region_health["us-west-2"]
        assert health.status == RegionStatus.UNHEALTHY
        assert health.consecutive_failures == 3


class TestFailover:
    """Test failover functionality."""

    def test_update_active_region_prefers_primary(self, multi_region_db):
        """Test active region prefers healthy primary."""
        multi_region_db._region_health["us-west-2"].status = RegionStatus.HEALTHY
        multi_region_db._region_health["us-east-1"].status = RegionStatus.HEALTHY
        multi_region_db._active_region = "us-east-1"

        multi_region_db._update_active_region()

        assert multi_region_db._active_region == "us-west-2"

    def test_failover_to_replica_when_primary_unhealthy(self, multi_region_db):
        """Test failover to replica when primary is unhealthy."""
        multi_region_db._region_health["us-west-2"].status = RegionStatus.UNHEALTHY
        multi_region_db._region_health["us-east-1"].status = RegionStatus.HEALTHY
        multi_region_db._region_health["eu-west-1"].status = RegionStatus.HEALTHY

        multi_region_db._update_active_region()

        assert multi_region_db._active_region == "us-east-1"

    def test_force_failover(self, multi_region_db):
        """Test forced failover."""
        result = multi_region_db.force_failover("eu-west-1")

        assert result is True
        assert multi_region_db._active_region == "eu-west-1"

    def test_force_failover_unknown_region(self, multi_region_db):
        """Test forced failover to unknown region fails."""
        result = multi_region_db.force_failover("ap-southeast-1")

        assert result is False


class TestLatencyBasedRouting:
    """Test latency-based routing."""

    def test_get_best_read_region_by_latency(self, multi_region_db):
        """Test best read region selection by latency."""
        multi_region_db._region_health["us-west-2"].status = RegionStatus.HEALTHY
        multi_region_db._region_health["us-west-2"].latency_ms = 100.0
        multi_region_db._region_health["us-east-1"].status = RegionStatus.HEALTHY
        multi_region_db._region_health["us-east-1"].latency_ms = 50.0
        multi_region_db._region_health["eu-west-1"].status = RegionStatus.HEALTHY
        multi_region_db._region_health["eu-west-1"].latency_ms = 200.0

        best = multi_region_db.get_best_read_region()

        assert best == "us-east-1"

    def test_get_best_read_region_skips_unhealthy(self, multi_region_db):
        """Test best read region skips unhealthy regions."""
        multi_region_db._region_health["us-west-2"].status = RegionStatus.UNHEALTHY
        multi_region_db._region_health["us-west-2"].latency_ms = 10.0
        multi_region_db._region_health["us-east-1"].status = RegionStatus.HEALTHY
        multi_region_db._region_health["us-east-1"].latency_ms = 100.0

        best = multi_region_db.get_best_read_region()

        assert best == "us-east-1"


class TestProxiedMethods:
    """Test proxied state DB methods."""

    def test_get_workset_uses_best_region(self, multi_region_db, mock_state_db):
        """Test get_workset uses best region for reads."""
        multi_region_db._region_health["us-west-2"].status = RegionStatus.HEALTHY

        result = multi_region_db.get_workset("test-ws-001")

        assert result is not None
        assert result["workset_id"] == "test-ws-001"

    def test_register_workset_uses_active_region(self, multi_region_db, mock_state_db):
        """Test register_workset uses active region."""
        mock_state_db.register_workset.return_value = True
        multi_region_db._region_health["us-west-2"].status = RegionStatus.HEALTHY

        result = multi_region_db.register_workset(
            "new-ws",
            "test-bucket",
            "prefix/",
        )

        assert result is True

    def test_operation_retries_on_failure(self, multi_region_db, mock_state_db):
        """Test operation retries with different region on failure."""
        multi_region_db._region_health["us-west-2"].status = RegionStatus.HEALTHY
        multi_region_db._region_health["us-east-1"].status = RegionStatus.HEALTHY

        # First call fails, second succeeds
        call_count = [0]
        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise ClientError(
                    {"Error": {"Code": "ServiceUnavailable", "Message": "test"}},
                    "GetItem",
                )
            return {"workset_id": "test-ws-001", "state": "ready"}

        mock_state_db.get_workset.side_effect = side_effect

        result = multi_region_db.get_workset("test-ws-001")

        assert result is not None
        assert call_count[0] == 2


class TestRegionStatus:
    """Test region status reporting."""

    def test_get_region_status(self, multi_region_db):
        """Test region status includes all fields."""
        multi_region_db._region_health["us-west-2"].status = RegionStatus.HEALTHY
        multi_region_db._region_health["us-west-2"].latency_ms = 50.0
        multi_region_db._region_health["us-west-2"].last_check = dt.datetime.now(dt.timezone.utc)

        status = multi_region_db.get_region_status()

        assert "us-west-2" in status
        assert status["us-west-2"]["status"] == "healthy"
        assert status["us-west-2"]["latency_ms"] == 50.0
        assert status["us-west-2"]["is_primary"] is True
        assert status["us-west-2"]["is_active"] is True

    def test_get_active_region(self, multi_region_db):
        """Test get_active_region returns current active."""
        assert multi_region_db.get_active_region() == "us-west-2"

        multi_region_db._active_region = "us-east-1"
        assert multi_region_db.get_active_region() == "us-east-1"

