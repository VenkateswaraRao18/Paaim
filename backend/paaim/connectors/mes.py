"""Manufacturing Execution System (MES) connector implementation."""

from typing import Dict, List, Any, Optional
from datetime import datetime
import httpx
import logging

from paaim.connectors.base import (
    ManufacturingConnector,
    ConnectorConfig,
    ConnectorStatus,
    ConnectorAuthException,
    ConnectorException,
)

logger = logging.getLogger(__name__)


class MESConnector(ManufacturingConnector):
    """
    Connector for Manufacturing Execution Systems (MES).

    Handles:
    - Real-time production order status
    - Machine availability and status
    - Quality metrics and defect reports
    - Equipment maintenance schedules
    - Worker/shift information
    """

    def __init__(self, config: ConnectorConfig):
        """Initialize MES connector."""
        super().__init__(config)
        self.client: Optional[httpx.AsyncClient] = None
        self.base_url = f"http://{config.host}:{config.port}"
        self.auth_token: Optional[str] = None

    async def connect(self) -> bool:
        """Establish connection to MES."""
        try:
            self.client = httpx.AsyncClient(
                timeout=self.config.timeout_seconds,
                verify=False,  # For test environments
            )

            # Attempt authentication
            await self._authenticate()
            self.health.status = ConnectorStatus.HEALTHY
            self.health.last_check = datetime.utcnow()
            logger.info(f"Connected to MES at {self.base_url}")
            return True

        except Exception as e:
            self.health.status = ConnectorStatus.UNHEALTHY
            self.health.last_error = str(e)
            logger.error(f"Failed to connect to MES: {e}")
            return False

    async def disconnect(self) -> None:
        """Close connection to MES."""
        if self.client:
            await self.client.aclose()
            logger.info("Disconnected from MES")

    async def health_check(self) -> bool:
        """Check MES health status."""
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
            self.health.last_check = datetime.utcnow()
            return False

    async def _authenticate(self) -> None:
        """Authenticate with MES."""
        auth_url = f"{self.base_url}/auth/token"
        credentials = {
            "username": self.config.extra_config.get("username", "paaim"),
            "password": self.config.extra_config.get("password", "password"),
        }

        try:
            response = await self.client.post(auth_url, json=credentials)
            if response.status_code != 200:
                raise ConnectorAuthException(f"MES auth failed: {response.text}")

            self.auth_token = response.json().get("token")
            logger.info("MES authentication successful")

        except Exception as e:
            raise ConnectorAuthException(f"MES authentication failed: {e}")

    def _get_headers(self) -> Dict[str, str]:
        """Get HTTP headers with authentication."""
        headers = {"Content-Type": "application/json"}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        return headers

    async def fetch_events(
        self,
        since: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch events from MES."""
        events = []

        # Fetch production orders
        events.extend(await self._fetch_production_orders(since))

        # Fetch equipment status
        events.extend(await self._fetch_equipment_status(since))

        # Fetch quality metrics
        events.extend(await self._fetch_quality_metrics(since))

        return events

    async def _fetch_production_orders(
        self,
        since: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch production orders from MES."""
        try:
            params = {}
            if since:
                params["since"] = since.isoformat()

            response = await self.execute_with_retry(
                self.client.get(
                    f"{self.base_url}/api/production-orders",
                    headers=self._get_headers(),
                    params=params,
                ),
                operation_name="fetch_production_orders",
            )

            if response.status_code != 200:
                logger.error(
                    f"Failed to fetch production orders: {response.text}"
                )
                return []

            orders = response.json()
            events = []

            for order in orders:
                # Convert MES order to PAAIM event format
                if order.get("status") == "at_risk":
                    events.append({
                        "event_type": "production",
                        "signal_name": "order_at_risk",
                        "signal_value": order.get("completion_percentage", 0),
                        "confidence": 0.95,
                        "factory_id": order.get("factory_id", "factory_001"),
                        "machine_id": order.get("line_id"),
                        "source": "mes",
                        "context": {
                            "order_id": order.get("id"),
                            "deadline": order.get("deadline"),
                            "current_progress_pct": order.get("completion_percentage"),
                            "required_progress_pct": order.get("required_progress"),
                            "time_remaining_hours": order.get("hours_remaining"),
                        },
                        "timestamp": datetime.utcnow().isoformat(),
                    })

            return events

        except ConnectorException as e:
            logger.error(f"Error fetching production orders: {e}")
            return []

    async def _fetch_equipment_status(
        self,
        since: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch equipment status from MES."""
        try:
            params = {}
            if since:
                params["since"] = since.isoformat()

            response = await self.execute_with_retry(
                self.client.get(
                    f"{self.base_url}/api/equipment",
                    headers=self._get_headers(),
                    params=params,
                ),
                operation_name="fetch_equipment_status",
            )

            if response.status_code != 200:
                return []

            equipment_list = response.json()
            events = []

            for equipment in equipment_list:
                # Convert to maintenance/production events
                if equipment.get("health_status") == "warning":
                    events.append({
                        "event_type": "maintenance",
                        "signal_name": "equipment_degradation",
                        "signal_value": equipment.get("utilization", 50),
                        "confidence": 0.85,
                        "factory_id": "factory_001",
                        "machine_id": equipment.get("id"),
                        "source": "mes",
                        "context": {
                            "equipment_id": equipment.get("id"),
                            "health_status": equipment.get("health_status"),
                            "last_maintenance": equipment.get("last_maintenance"),
                            "mtbf_hours": equipment.get("mtbf_hours"),
                        },
                        "timestamp": datetime.utcnow().isoformat(),
                    })

            return events

        except ConnectorException as e:
            logger.error(f"Error fetching equipment status: {e}")
            return []

    async def _fetch_quality_metrics(
        self,
        since: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch quality metrics from MES."""
        try:
            params = {}
            if since:
                params["since"] = since.isoformat()

            response = await self.execute_with_retry(
                self.client.get(
                    f"{self.base_url}/api/quality-metrics",
                    headers=self._get_headers(),
                    params=params,
                ),
                operation_name="fetch_quality_metrics",
            )

            if response.status_code != 200:
                return []

            metrics = response.json()
            events = []

            for metric in metrics:
                if metric.get("status") == "alert":
                    events.append({
                        "event_type": "quality",
                        "signal_name": "defect_detection",
                        "signal_value": metric.get("defect_rate", 0),
                        "confidence": 0.92,
                        "factory_id": "factory_001",
                        "machine_id": metric.get("line_id"),
                        "source": "mes",
                        "context": {
                            "batch_id": metric.get("batch_id"),
                            "defect_type": metric.get("defect_type"),
                            "defect_count": metric.get("defect_count"),
                            "baseline": metric.get("baseline_defect_rate"),
                        },
                        "timestamp": datetime.utcnow().isoformat(),
                    })

            return events

        except ConnectorException as e:
            logger.error(f"Error fetching quality metrics: {e}")
            return []

    async def push_decision_result(
        self,
        decision_id: str,
        action: str,
        result: Dict[str, Any],
    ) -> bool:
        """
        Push decision result back to MES for logging/tracking.

        Args:
            decision_id: PAAIM decision ID
            action: Action taken
            result: Outcome of action

        Returns:
            True if successful
        """
        try:
            payload = {
                "decision_id": decision_id,
                "action": action,
                "result": result,
                "timestamp": datetime.utcnow().isoformat(),
            }

            response = await self.execute_with_retry(
                self.client.post(
                    f"{self.base_url}/api/decisions",
                    headers=self._get_headers(),
                    json=payload,
                ),
                operation_name="push_decision_result",
            )

            return response.status_code == 200

        except Exception as e:
            logger.error(f"Failed to push decision result to MES: {e}")
            return False
