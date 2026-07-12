"""
ERP Connector - Enterprise Resource Planning integration.

Pulls production schedules, active work orders, cost data, and inventory
context from ERP systems (SAP, Oracle, Infor, etc.) via REST API.
"""

import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import logging

from paaim.connectors.base import ManufacturingConnector, ConnectorConfig, ConnectorStatus

logger = logging.getLogger(__name__)


class ERPConnector(ManufacturingConnector):
    """
    Connector for ERP systems (SAP, Oracle, Infor, Microsoft Dynamics).

    Fetches:
    - Active production orders and schedules
    - Work order priorities and deadlines
    - Bill-of-materials and material availability
    - Cost centre budgets and actuals
    - Demand forecasts
    """

    CONNECTOR_TYPE = "erp"

    def __init__(self, name: str, config: ConnectorConfig):
        super().__init__(name, config)
        self.base_url = f"http://{config.host}:{config.port}"
        self.api_prefix = config.extra_config.get("api_prefix", "/api/v1")
        self.client_id = config.extra_config.get("client_id", "")
        self.client_secret = config.extra_config.get("client_secret", "")
        self._token: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None

    # ─── Connection lifecycle ─────────────────────────────────────

    async def connect(self) -> bool:
        try:
            await self._refresh_token()
            self.status = ConnectorStatus.CONNECTED
            logger.info(f"ERP connector '{self.name}' connected to {self.base_url}")
            return True
        except Exception as e:
            logger.error(f"ERP connector '{self.name}' failed to connect: {e}")
            self.status = ConnectorStatus.ERROR
            return False

    async def disconnect(self) -> None:
        self._token = None
        self.status = ConnectorStatus.DISCONNECTED
        logger.info(f"ERP connector '{self.name}' disconnected")

    async def health_check(self) -> bool:
        try:
            await self._get("/health")
            return True
        except Exception:
            return False

    # ─── Token management ─────────────────────────────────────────

    async def _refresh_token(self) -> None:
        """Fetch / refresh OAuth2 token from ERP."""
        if self.client_id and self.client_secret:
            response = await self._post(
                "/oauth/token",
                {
                    "grant_type": "client_credentials",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                },
            )
            self._token = response.get("access_token", "")
            expires_in = response.get("expires_in", 3600)
            self._token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in - 60)
        else:
            self._token = self.config.extra_config.get("api_key", "demo_token")

    async def _ensure_token(self) -> None:
        if not self._token or (
            self._token_expires_at and datetime.utcnow() >= self._token_expires_at
        ):
            await self._refresh_token()

    # ─── HTTP helpers ─────────────────────────────────────────────

    async def _get(self, path: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        await self._ensure_token()
        import httpx

        url = f"{self.base_url}{self.api_prefix}{path}"
        headers = {"Authorization": f"Bearer {self._token}"}
        async with httpx.AsyncClient(timeout=self.config.timeout_seconds) as client:
            resp = await client.get(url, headers=headers, params=params or {})
            resp.raise_for_status()
            return resp.json()

    async def _post(self, path: str, data: Dict[str, Any]) -> Dict[str, Any]:
        import httpx

        url = f"{self.base_url}{self.api_prefix}{path}"
        async with httpx.AsyncClient(timeout=self.config.timeout_seconds) as client:
            resp = await client.post(url, json=data)
            resp.raise_for_status()
            return resp.json()

    # ─── Production data ──────────────────────────────────────────

    async def get_production_orders(
        self,
        factory_id: str,
        status: str = "active",
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Fetch active production orders for a factory.

        Returns list of orders with: id, product, quantity, due_date, priority, status.
        """
        try:
            data = await self._get(
                "/production-orders",
                {"factory_id": factory_id, "status": status, "limit": limit},
            )
            return data.get("orders", [])
        except Exception as e:
            logger.warning(f"ERP get_production_orders failed: {e}. Using fallback data.")
            return self._mock_production_orders(factory_id)

    async def get_work_orders(
        self,
        factory_id: str,
        machine_id: Optional[str] = None,
        status: str = "open",
    ) -> List[Dict[str, Any]]:
        """
        Fetch open work orders (maintenance, changeover, etc.).

        Returns list with: id, type, machine_id, priority, estimated_duration_hours.
        """
        try:
            params = {"factory_id": factory_id, "status": status}
            if machine_id:
                params["machine_id"] = machine_id
            data = await self._get("/work-orders", params)
            return data.get("work_orders", [])
        except Exception as e:
            logger.warning(f"ERP get_work_orders failed: {e}. Using fallback data.")
            return self._mock_work_orders(factory_id, machine_id)

    async def get_cost_context(self, factory_id: str) -> Dict[str, Any]:
        """
        Fetch cost context: budget vs. actuals, cost centre status.
        """
        try:
            return await self._get("/cost-context", {"factory_id": factory_id})
        except Exception as e:
            logger.warning(f"ERP get_cost_context failed: {e}. Using fallback data.")
            return self._mock_cost_context(factory_id)

    async def get_demand_forecast(
        self,
        factory_id: str,
        horizon_days: int = 7,
    ) -> List[Dict[str, Any]]:
        """
        Fetch demand forecast for the next N days.
        """
        try:
            data = await self._get(
                "/demand-forecast",
                {"factory_id": factory_id, "horizon_days": horizon_days},
            )
            return data.get("forecast", [])
        except Exception as e:
            logger.warning(f"ERP get_demand_forecast failed: {e}. Using fallback data.")
            return self._mock_demand_forecast(horizon_days)

    async def get_material_availability(
        self,
        factory_id: str,
        materials: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Fetch material and inventory availability.
        """
        try:
            params: Dict[str, Any] = {"factory_id": factory_id}
            if materials:
                params["materials"] = ",".join(materials)
            return await self._get("/inventory/availability", params)
        except Exception as e:
            logger.warning(f"ERP get_material_availability failed: {e}. Using fallback data.")
            return self._mock_material_availability()

    # ─── Composite context builder ────────────────────────────────

    async def get_decision_context(
        self,
        factory_id: str,
        machine_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Fetch all ERP context needed to inform a decision.

        Combines production orders, work orders, cost context, and demand
        into a single dict that agents can reference in their analysis.
        """
        orders_task = asyncio.create_task(self.get_production_orders(factory_id))
        work_orders_task = asyncio.create_task(self.get_work_orders(factory_id, machine_id))
        cost_task = asyncio.create_task(self.get_cost_context(factory_id))
        demand_task = asyncio.create_task(self.get_demand_forecast(factory_id, horizon_days=3))

        orders, work_orders, cost, demand = await asyncio.gather(
            orders_task, work_orders_task, cost_task, demand_task
        )

        urgent_orders = [o for o in orders if o.get("priority") in ("high", "critical")]

        return {
            "factory_id": factory_id,
            "machine_id": machine_id,
            "production_context": {
                "active_orders": len(orders),
                "urgent_orders": len(urgent_orders),
                "urgent_order_ids": [o["id"] for o in urgent_orders[:3]],
                "open_work_orders": len(work_orders),
                "demand_trend": demand[0].get("trend", "stable") if demand else "stable",
            },
            "cost_context": cost,
            "risk_of_stoppage": "high" if urgent_orders else "low",
        }

    # ─── Mock / fallback data ─────────────────────────────────────

    def _mock_production_orders(self, factory_id: str) -> List[Dict[str, Any]]:
        return [
            {
                "id": f"PO-{factory_id}-001",
                "product": "Widget A",
                "quantity": 2500,
                "produced": 1200,
                "due_date": (datetime.utcnow() + timedelta(hours=18)).isoformat(),
                "priority": "critical",
                "status": "in_progress",
                "customer": "Acme Corp",
            },
            {
                "id": f"PO-{factory_id}-002",
                "product": "Gear Assembly B",
                "quantity": 500,
                "produced": 480,
                "due_date": (datetime.utcnow() + timedelta(hours=36)).isoformat(),
                "priority": "normal",
                "status": "in_progress",
                "customer": "TechCo",
            },
            {
                "id": f"PO-{factory_id}-003",
                "product": "Bracket C",
                "quantity": 10000,
                "produced": 0,
                "due_date": (datetime.utcnow() + timedelta(days=5)).isoformat(),
                "priority": "low",
                "status": "scheduled",
                "customer": "IndustrialGroup",
            },
        ]

    def _mock_work_orders(
        self, factory_id: str, machine_id: Optional[str]
    ) -> List[Dict[str, Any]]:
        orders = [
            {
                "id": "WO-0421",
                "type": "preventive_maintenance",
                "machine_id": "cnc_mill_01",
                "priority": "normal",
                "estimated_duration_hours": 2.0,
                "scheduled_for": (datetime.utcnow() + timedelta(hours=48)).isoformat(),
                "technician": "Mike S.",
            },
            {
                "id": "WO-0422",
                "type": "calibration",
                "machine_id": "vision_sys_01",
                "priority": "normal",
                "estimated_duration_hours": 0.5,
                "scheduled_for": (datetime.utcnow() + timedelta(hours=72)).isoformat(),
                "technician": "Sarah L.",
            },
        ]
        if machine_id:
            return [o for o in orders if o["machine_id"] == machine_id]
        return orders

    def _mock_cost_context(self, factory_id: str) -> Dict[str, Any]:
        return {
            "factory_id": factory_id,
            "period": "current_month",
            "budget_usd": 1_200_000,
            "actual_usd": 980_000,
            "variance_usd": 220_000,
            "variance_pct": 18.3,
            "scrap_cost_usd": 45_000,
            "downtime_cost_usd": 28_000,
            "maintenance_cost_usd": 95_000,
            "status": "on_budget",
        }

    def _mock_demand_forecast(self, horizon_days: int) -> List[Dict[str, Any]]:
        forecast = []
        for i in range(horizon_days):
            date = (datetime.utcnow() + timedelta(days=i)).strftime("%Y-%m-%d")
            forecast.append({
                "date": date,
                "expected_units": 850 + (i * 15),
                "trend": "increasing" if i > 0 else "stable",
                "confidence": 0.85 - (i * 0.05),
            })
        return forecast

    def _mock_material_availability(self) -> Dict[str, Any]:
        return {
            "status": "adequate",
            "materials": [
                {"id": "MAT-001", "name": "Steel Sheet 2mm", "stock_units": 5000, "reorder_point": 1000, "status": "ok"},
                {"id": "MAT-002", "name": "Aluminium Bar 20mm", "stock_units": 800, "reorder_point": 500, "status": "ok"},
                {"id": "MAT-003", "name": "Bearing 6205", "stock_units": 45, "reorder_point": 50, "status": "low"},
            ],
            "alerts": ["Bearing 6205 is below reorder point — procurement advised"],
        }
