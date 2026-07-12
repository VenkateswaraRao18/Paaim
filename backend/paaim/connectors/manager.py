"""Connector manager for lifecycle and health monitoring."""

from typing import Dict, List, Optional
import asyncio
import logging
from datetime import datetime

from paaim.connectors.base import (
    ManufacturingConnector,
    ConnectorConfig,
    ConnectorStatus,
)
from paaim.connectors.mes import MESConnector
from paaim.connectors.cmms import CMMSConnector
from paaim.connectors.erp import ERPConnector

logger = logging.getLogger(__name__)


class ConnectorManager:
    """
    Manages lifecycle and health monitoring of all manufacturing connectors.

    Provides:
    - Initialization and connection pooling
    - Health monitoring and auto-recovery
    - Event aggregation from all sources
    - Graceful degradation
    """

    def __init__(self):
        """Initialize connector manager."""
        self.connectors: Dict[str, ManufacturingConnector] = {}
        self.health_check_interval_seconds = 60
        self._health_check_task: Optional[asyncio.Task] = None

    def register_connector(
        self,
        name: str,
        connector_type: str,
        config: ConnectorConfig,
    ) -> None:
        """
        Register a connector.

        Args:
            name: Unique name for this connector instance
            connector_type: Type of connector ('mes', 'cmms', 'erp')
            config: Connector configuration
        """
        if connector_type == "mes":
            self.connectors[name] = MESConnector(config)
        elif connector_type == "cmms":
            self.connectors[name] = CMMSConnector(config)
        elif connector_type == "erp":
            self.connectors[name] = ERPConnector(name, config)
        else:
            raise ValueError(f"Unknown connector type: {connector_type}")

        logger.info(f"Registered {connector_type} connector: {name}")

    async def connect_all(self) -> Dict[str, bool]:
        """
        Connect all registered connectors.

        Returns:
            Dict mapping connector name to connection success status
        """
        results = {}
        tasks = [
            self._connect_connector(name, connector)
            for name, connector in self.connectors.items()
        ]

        for name, success in zip(self.connectors.keys(), await asyncio.gather(*tasks)):
            results[name] = success

        return results

    async def _connect_connector(
        self,
        name: str,
        connector: ManufacturingConnector,
    ) -> bool:
        """Connect a single connector."""
        try:
            success = await connector.connect()
            if success:
                logger.info(f"Connected to {name}")
            else:
                logger.warning(f"Failed to connect to {name}")
            return success

        except Exception as e:
            logger.error(f"Error connecting to {name}: {e}")
            return False

    async def disconnect_all(self) -> None:
        """Disconnect all connectors."""
        tasks = [
            connector.disconnect() for connector in self.connectors.values()
        ]
        await asyncio.gather(*tasks, return_exceptions=True)
        logger.info("Disconnected all connectors")

    async def start_health_monitoring(self) -> None:
        """Start periodic health checking of all connectors."""
        if self._health_check_task:
            return

        async def monitor():
            while True:
                try:
                    await self.check_health()
                    await asyncio.sleep(self.health_check_interval_seconds)
                except Exception as e:
                    logger.error(f"Health monitoring error: {e}")
                    await asyncio.sleep(self.health_check_interval_seconds)

        self._health_check_task = asyncio.create_task(monitor())
        logger.info("Started health monitoring")

    async def stop_health_monitoring(self) -> None:
        """Stop health monitoring."""
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
            self._health_check_task = None
            logger.info("Stopped health monitoring")

    async def check_health(self) -> Dict[str, Dict]:
        """
        Check health of all connectors.

        Returns:
            Dict mapping connector name to health status
        """
        results = {}
        tasks = [
            self._check_connector_health(name, connector)
            for name, connector in self.connectors.items()
        ]

        for name, health in zip(self.connectors.keys(), await asyncio.gather(*tasks)):
            results[name] = health

        return results

    async def _check_connector_health(
        self,
        name: str,
        connector: ManufacturingConnector,
    ) -> Dict:
        """Check health of a single connector."""
        try:
            is_healthy = await connector.health_check()
            logger.info(
                f"Health check {name}: {'healthy' if is_healthy else 'unhealthy'}"
            )
        except Exception as e:
            logger.warning(f"Health check failed for {name}: {e}")
            connector.health.status = ConnectorStatus.UNHEALTHY
            connector.health.last_error = str(e)

        return connector.health.to_dict()

    async def fetch_all_events(self, since=None) -> List[Dict]:
        """
        Fetch events from all connected connectors.

        Args:
            since: Fetch events since this timestamp

        Returns:
            List of events from all sources
        """
        all_events = []
        tasks = [
            self._fetch_connector_events(name, connector, since)
            for name, connector in self.connectors.items()
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for name, events in zip(self.connectors.keys(), results):
            if isinstance(events, Exception):
                logger.error(f"Error fetching from {name}: {events}")
            elif events:
                logger.info(f"Fetched {len(events)} events from {name}")
                all_events.extend(events)

        return all_events

    async def _fetch_connector_events(
        self,
        name: str,
        connector: ManufacturingConnector,
        since=None,
    ) -> List[Dict]:
        """Fetch events from a single connector."""
        try:
            return await connector.fetch_events(since=since)
        except Exception as e:
            logger.error(f"Error fetching events from {name}: {e}")
            return []

    def get_connector(self, name: str) -> Optional[ManufacturingConnector]:
        """Get connector by name."""
        return self.connectors.get(name)

    def get_health_summary(self) -> Dict[str, str]:
        """
        Get health summary for all connectors.

        Returns:
            Dict mapping connector name to health status
        """
        return {
            name: connector.health.status.value
            for name, connector in self.connectors.items()
        }

    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect_all()
        await self.start_health_monitoring()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.stop_health_monitoring()
        await self.disconnect_all()


# Global connector manager instance
_manager: Optional[ConnectorManager] = None


def get_connector_manager() -> ConnectorManager:
    """Get or create global connector manager."""
    global _manager
    if _manager is None:
        _manager = ConnectorManager()
    return _manager


def reset_connector_manager() -> None:
    """Reset connector manager (for testing)."""
    global _manager
    _manager = None
