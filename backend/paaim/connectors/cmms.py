"""Computerized Maintenance Management System (CMMS) connector."""

from typing import Dict, List, Any, Optional
from datetime import datetime
import httpx
import logging

from paaim.connectors.base import (
    ManufacturingConnector,
    ConnectorConfig,
    ConnectorStatus,
    ConnectorException,
)

logger = logging.getLogger(__name__)


class CMMSConnector(ManufacturingConnector):
    """
    Connector for Computerized Maintenance Management Systems (CMMS).

    Handles:
    - Maintenance schedules and work orders
    - Asset health and condition monitoring
    - Preventive maintenance planning
    - Equipment history and downtime tracking
    """

    def __init__(self, config: ConnectorConfig):
        """Initialize CMMS connector."""
        super().__init__(config)
        self.client: Optional[httpx.AsyncClient] = None
        self.base_url = f"http://{config.host}:{config.port}"

    async def connect(self) -> bool:
        """Establish connection to CMMS."""
        try:
            self.client = httpx.AsyncClient(
                timeout=self.config.timeout_seconds,
                verify=False,
            )
            self.health.status = ConnectorStatus.HEALTHY
            logger.info(f"Connected to CMMS at {self.base_url}")
            return True

        except Exception as e:
            self.health.status = ConnectorStatus.UNHEALTHY
            self.health.last_error = str(e)
            logger.error(f"Failed to connect to CMMS: {e}")
            return False

    async def disconnect(self) -> None:
        """Close connection to CMMS."""
        if self.client:
            await self.client.aclose()
            logger.info("Disconnected from CMMS")

    async def health_check(self) -> bool:
        """Check CMMS health status."""
        try:
            response = await self.execute_with_retry(
                self.client.get(f"{self.base_url}/health"),
                operation_name="health_check",
                max_attempts=1,
            )
            is_healthy = response.status_code == 200
            self.health.status = (
                ConnectorStatus.HEALTHY
                if is_healthy
                else ConnectorStatus.UNHEALTHY
            )
            self.health.last_check = datetime.utcnow()
            return is_healthy

        except Exception as e:
            self.health.status = ConnectorStatus.UNHEALTHY
            self.health.last_error = str(e)
            return False

    async def fetch_events(
        self,
        since: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch events from CMMS."""
        events = []

        # Fetch maintenance schedules
        events.extend(await self._fetch_maintenance_schedules(since))

        # Fetch work orders
        events.extend(await self._fetch_work_orders(since))

        # Fetch asset health
        events.extend(await self._fetch_asset_health(since))

        return events

    async def _fetch_maintenance_schedules(
        self,
        since: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch planned maintenance schedules."""
        try:
            params = {}
            if since:
                params["since"] = since.isoformat()

            response = await self.execute_with_retry(
                self.client.get(
                    f"{self.base_url}/api/maintenance-schedules",
                    params=params,
                ),
                operation_name="fetch_maintenance_schedules",
            )

            if response.status_code != 200:
                return []

            schedules = response.json()
            events = []

            for schedule in schedules:
                # Convert overdue maintenance to events
                if schedule.get("status") == "overdue":
                    events.append({
                        "event_type": "maintenance",
                        "signal_name": "maintenance_overdue",
                        "signal_value": 1.0,
                        "confidence": 0.99,
                        "factory_id": "factory_001",
                        "machine_id": schedule.get("asset_id"),
                        "source": "cmms",
                        "context": {
                            "schedule_id": schedule.get("id"),
                            "asset_id": schedule.get("asset_id"),
                            "maintenance_type": schedule.get("type"),
                            "due_date": schedule.get("due_date"),
                            "days_overdue": schedule.get("days_overdue"),
                            "priority": schedule.get("priority"),
                        },
                        "timestamp": datetime.utcnow().isoformat(),
                    })

            return events

        except ConnectorException as e:
            logger.error(f"Error fetching maintenance schedules: {e}")
            return []

    async def _fetch_work_orders(
        self,
        since: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch open work orders."""
        try:
            params = {"status": "open"}
            if since:
                params["since"] = since.isoformat()

            response = await self.execute_with_retry(
                self.client.get(
                    f"{self.base_url}/api/work-orders",
                    params=params,
                ),
                operation_name="fetch_work_orders",
            )

            if response.status_code != 200:
                return []

            work_orders = response.json()
            events = []

            for wo in work_orders:
                # High-priority work orders are events
                if wo.get("priority") in ["critical", "high"]:
                    events.append({
                        "event_type": "maintenance",
                        "signal_name": "critical_work_order",
                        "signal_value": 1.0,
                        "confidence": 0.95,
                        "factory_id": "factory_001",
                        "machine_id": wo.get("asset_id"),
                        "source": "cmms",
                        "context": {
                            "work_order_id": wo.get("id"),
                            "asset_id": wo.get("asset_id"),
                            "description": wo.get("description"),
                            "priority": wo.get("priority"),
                            "estimated_hours": wo.get("estimated_hours"),
                        },
                        "timestamp": datetime.utcnow().isoformat(),
                    })

            return events

        except ConnectorException as e:
            logger.error(f"Error fetching work orders: {e}")
            return []

    async def _fetch_asset_health(
        self,
        since: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch asset health and condition data."""
        try:
            params = {}
            if since:
                params["since"] = since.isoformat()

            response = await self.execute_with_retry(
                self.client.get(
                    f"{self.base_url}/api/assets",
                    params=params,
                ),
                operation_name="fetch_asset_health",
            )

            if response.status_code != 200:
                return []

            assets = response.json()
            events = []

            for asset in assets:
                # Assets in poor condition generate maintenance events
                if asset.get("health_score", 100) < 60:
                    events.append({
                        "event_type": "maintenance",
                        "signal_name": "asset_health_degraded",
                        "signal_value": asset.get("health_score", 0),
                        "confidence": 0.88,
                        "factory_id": "factory_001",
                        "machine_id": asset.get("id"),
                        "source": "cmms",
                        "context": {
                            "asset_id": asset.get("id"),
                            "asset_name": asset.get("name"),
                            "health_score": asset.get("health_score"),
                            "last_maintenance": asset.get("last_maintenance_date"),
                            "maintenance_history_count": asset.get("maintenance_count"),
                        },
                        "timestamp": datetime.utcnow().isoformat(),
                    })

            return events

        except ConnectorException as e:
            logger.error(f"Error fetching asset health: {e}")
            return []

    async def create_work_order(
        self,
        asset_id: str,
        description: str,
        priority: str = "high",
        estimated_hours: float = 2.0,
    ) -> Optional[str]:
        """
        Create a new work order in CMMS based on PAAIM decision.

        Args:
            asset_id: ID of asset to maintain
            description: Maintenance description
            priority: Priority level
            estimated_hours: Estimated maintenance duration

        Returns:
            Work order ID if successful, None otherwise
        """
        try:
            payload = {
                "asset_id": asset_id,
                "description": description,
                "priority": priority,
                "estimated_hours": estimated_hours,
                "created_by": "paaim",
                "timestamp": datetime.utcnow().isoformat(),
            }

            response = await self.execute_with_retry(
                self.client.post(
                    f"{self.base_url}/api/work-orders",
                    json=payload,
                ),
                operation_name="create_work_order",
            )

            if response.status_code == 201:
                return response.json().get("id")
            else:
                logger.error(f"Failed to create work order: {response.text}")
                return None

        except Exception as e:
            logger.error(f"Error creating work order: {e}")
            return None
