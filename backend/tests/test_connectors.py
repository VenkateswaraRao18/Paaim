"""Tests for manufacturing connectors."""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from paaim.connectors.base import (
    ConnectorConfig,
    CircuitBreaker,
    ConnectorException,
    ConnectorTimeoutException,
)
from paaim.connectors.mes import MESConnector
from paaim.connectors.cmms import CMMSConnector
from paaim.connectors.manager import ConnectorManager


class TestCircuitBreaker:
    """Test circuit breaker pattern."""

    def test_circuit_breaker_initial_state(self):
        """Circuit breaker should be closed initially."""
        cb = CircuitBreaker(threshold=3, timeout_seconds=60)
        assert not cb.is_open
        assert cb.can_execute()

    def test_circuit_breaker_opens_after_threshold(self):
        """Circuit breaker should open after threshold failures."""
        cb = CircuitBreaker(threshold=3)
        cb.record_failure()
        cb.record_failure()
        assert not cb.is_open
        cb.record_failure()
        assert cb.is_open
        assert not cb.can_execute()

    def test_circuit_breaker_resets_on_success(self):
        """Circuit breaker should reset on success."""
        cb = CircuitBreaker(threshold=2)
        cb.record_failure()
        cb.record_failure()
        assert cb.is_open
        cb.record_success()
        assert not cb.is_open
        assert cb.can_execute()

    @pytest.mark.asyncio
    async def test_circuit_breaker_recovery_timeout(self):
        """Circuit breaker should attempt recovery after timeout."""
        cb = CircuitBreaker(threshold=1, timeout_seconds=0.1)
        cb.record_failure()
        assert cb.is_open

        await asyncio.sleep(0.15)
        assert cb.can_execute()


class TestMESConnector:
    """Test MES connector."""

    @pytest.fixture
    def mes_config(self):
        """Create test MES config."""
        return ConnectorConfig(
            name="test_mes",
            host="localhost",
            port=8001,
            extra_config={"username": "test", "password": "test"},
        )

    @pytest.fixture
    def mes_connector(self, mes_config):
        """Create test MES connector."""
        return MESConnector(mes_config)

    @pytest.mark.asyncio
    async def test_mes_connector_initialization(self, mes_connector):
        """Connector should initialize correctly."""
        assert mes_connector.config.name == "test_mes"
        assert mes_connector.client is None

    @pytest.mark.asyncio
    async def test_mes_fetch_events_structure(self, mes_connector):
        """Fetched events should have required structure."""
        # Mock the HTTP client
        with patch("paaim.connectors.mes.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client

            # Mock authentication
            mock_client.post.return_value.status_code = 200
            mock_client.post.return_value.json.return_value = {"token": "test_token"}

            # Mock production orders
            mock_client.get.return_value.status_code = 200
            mock_client.get.return_value.json.return_value = [
                {
                    "id": "order_001",
                    "factory_id": "factory_001",
                    "line_id": "line_01",
                    "status": "at_risk",
                    "completion_percentage": 72,
                    "required_progress": 85,
                    "hours_remaining": 16,
                    "deadline": "2026-05-22T14:00:00Z",
                }
            ]

            await mes_connector.connect()
            events = await mes_connector.fetch_events()

            assert len(events) > 0
            assert "event_type" in events[0]
            assert "signal_name" in events[0]
            assert "confidence" in events[0]


class TestCMMSConnector:
    """Test CMMS connector."""

    @pytest.fixture
    def cmms_config(self):
        """Create test CMMS config."""
        return ConnectorConfig(
            name="test_cmms",
            host="localhost",
            port=8002,
        )

    @pytest.fixture
    def cmms_connector(self, cmms_config):
        """Create test CMMS connector."""
        return CMMSConnector(cmms_config)

    @pytest.mark.asyncio
    async def test_cmms_connector_initialization(self, cmms_connector):
        """Connector should initialize correctly."""
        assert cmms_connector.config.name == "test_cmms"


class TestConnectorManager:
    """Test connector manager."""

    @pytest.fixture
    def manager(self):
        """Create test manager."""
        return ConnectorManager()

    def test_manager_register_connector(self, manager):
        """Manager should register connectors."""
        config = ConnectorConfig(
            name="test_mes",
            host="localhost",
            port=8001,
            extra_config={"username": "test", "password": "test"},
        )
        manager.register_connector("mes_prod", "mes", config)
        assert "mes_prod" in manager.connectors

    def test_manager_register_unknown_type(self, manager):
        """Manager should reject unknown connector types."""
        config = ConnectorConfig(
            name="test",
            host="localhost",
            port=8000,
        )
        with pytest.raises(ValueError):
            manager.register_connector("unknown", "unknown_type", config)

    def test_manager_get_connector(self, manager):
        """Manager should retrieve registered connectors."""
        config = ConnectorConfig(
            name="test_mes",
            host="localhost",
            port=8001,
            extra_config={"username": "test", "password": "test"},
        )
        manager.register_connector("mes_prod", "mes", config)
        connector = manager.get_connector("mes_prod")
        assert isinstance(connector, MESConnector)

    def test_manager_get_nonexistent_connector(self, manager):
        """Manager should return None for nonexistent connector."""
        connector = manager.get_connector("nonexistent")
        assert connector is None

    @pytest.mark.asyncio
    async def test_manager_connect_all(self, manager):
        """Manager should connect all registered connectors."""
        config = ConnectorConfig(
            name="test_mes",
            host="localhost",
            port=8001,
            extra_config={"username": "test", "password": "test"},
        )
        manager.register_connector("mes_prod", "mes", config)

        # Mock the connector
        with patch.object(manager.connectors["mes_prod"], "connect", new_callable=AsyncMock) as mock_connect:
            mock_connect.return_value = True
            results = await manager.connect_all()
            assert results["mes_prod"] is True

    @pytest.mark.asyncio
    async def test_manager_health_check(self, manager):
        """Manager should check health of all connectors."""
        config = ConnectorConfig(
            name="test_mes",
            host="localhost",
            port=8001,
            extra_config={"username": "test", "password": "test"},
        )
        manager.register_connector("mes_prod", "mes", config)

        # Mock health check
        with patch.object(manager.connectors["mes_prod"], "health_check", new_callable=AsyncMock) as mock_health:
            mock_health.return_value = True
            health_status = await manager.check_health()
            assert "mes_prod" in health_status
