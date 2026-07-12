"""
MCP resources + tools backed by the Factory Context Graph.

Resources are read-only context the model can pull in; tools are callable
functions. Both delegate to the same services the orchestrator uses, so an
external MCP client sees exactly the operational truth PAAIM's own agents do.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

from sqlalchemy import select

from paaim.models import (
    AsyncSessionLocal, MachineAssetModel, WorkOrderModel,
    CustomerOrderModel, NCRRecordModel,
)
from paaim.context.factory_context import get_context_service

DEFAULT_FACTORY = "factory_001"


# ── Resources ──────────────────────────────────────────────────────────────────

RESOURCES = [
    {
        "uri": "factory://summary",
        "name": "Factory operations summary",
        "description": "Machines running, active work orders, orders at risk, open NCRs.",
        "mimeType": "application/json",
    },
    {
        "uri": "factory://machines",
        "name": "Machine asset registry",
        "description": "All machines with status, criticality and maintenance dates.",
        "mimeType": "application/json",
    },
    {
        "uri": "factory://work-orders",
        "name": "Active work orders",
        "description": "Work orders with product, customer, completion % and deadline.",
        "mimeType": "application/json",
    },
    {
        "uri": "factory://ncrs",
        "name": "Open quality issues (NCRs)",
        "description": "Open non-conformance reports with severity and recurrence.",
        "mimeType": "application/json",
    },
]


async def read_resource(uri: str) -> Dict[str, Any]:
    """Return the JSON body for a factory:// resource URI."""
    if uri.startswith("factory://summary"):
        return await _summary(DEFAULT_FACTORY)
    if uri.startswith("factory://machines"):
        return await _machines(DEFAULT_FACTORY)
    if uri.startswith("factory://work-orders"):
        return await _work_orders(DEFAULT_FACTORY)
    if uri.startswith("factory://ncrs"):
        return await _open_ncrs(DEFAULT_FACTORY)
    raise ValueError(f"Unknown resource: {uri}")


# ── Tools ──────────────────────────────────────────────────────────────────────

TOOLS = [
    {
        "name": "get_factory_summary",
        "description": "High-level factory state: machines, work orders, at-risk orders, open NCRs.",
        "inputSchema": {
            "type": "object",
            "properties": {"factory_id": {"type": "string", "default": DEFAULT_FACTORY}},
        },
    },
    {
        "name": "get_machine_context",
        "description": "Full operational context for one machine — exactly what PAAIM's "
                       "agents see: active work order, customer order + penalty, material "
                       "batch, maintenance history, quality history, cost model.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "factory_id": {"type": "string", "default": DEFAULT_FACTORY},
                "machine_id": {"type": "string"},
            },
            "required": ["machine_id"],
        },
    },
    {
        "name": "list_open_ncrs",
        "description": "Open non-conformance reports (quality issues) for a factory.",
        "inputSchema": {
            "type": "object",
            "properties": {"factory_id": {"type": "string", "default": DEFAULT_FACTORY}},
        },
    },
    {
        "name": "simulate_action_cost",
        "description": "Estimate the impact (downtime, scrap, cost) of a recommended action "
                       "using the Decision Twin.",
        "inputSchema": {
            "type": "object",
            "properties": {"action_name": {"type": "string"}},
            "required": ["action_name"],
        },
    },
]


async def call_tool(name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    factory_id = args.get("factory_id", DEFAULT_FACTORY)
    if name == "get_factory_summary":
        return await _summary(factory_id)
    if name == "get_machine_context":
        return await _machine_context(factory_id, args["machine_id"])
    if name == "list_open_ncrs":
        return await _open_ncrs(factory_id)
    if name == "simulate_action_cost":
        return _simulate(args["action_name"])
    raise ValueError(f"Unknown tool: {name}")


# ── Implementations ──────────────────────────────────────────────────────────

async def _summary(factory_id: str) -> Dict[str, Any]:
    from datetime import datetime
    now = datetime.utcnow()
    async with AsyncSessionLocal() as db:
        machines = (await db.execute(select(MachineAssetModel).where(
            MachineAssetModel.factory_id == factory_id))).scalars().all()
        wos = (await db.execute(select(WorkOrderModel).where(
            WorkOrderModel.factory_id == factory_id,
            WorkOrderModel.status == "in_progress"))).scalars().all()
        cos = (await db.execute(select(CustomerOrderModel).where(
            CustomerOrderModel.factory_id == factory_id,
            CustomerOrderModel.status == "open"))).scalars().all()
        ncrs = (await db.execute(select(NCRRecordModel).where(
            NCRRecordModel.factory_id == factory_id,
            NCRRecordModel.status == "open"))).scalars().all()
        at_risk = [c for c in cos if (c.promised_delivery - now).total_seconds() / 3600 < 48]
        return {
            "factory_id": factory_id,
            "machines": {"total": len(machines),
                         "running": sum(1 for m in machines if m.status == "running")},
            "work_orders_active": len(wos),
            "customer_orders_open": len(cos),
            "orders_at_risk": len(at_risk),
            "open_ncrs": len(ncrs),
        }


async def _machines(factory_id: str) -> Dict[str, Any]:
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(select(MachineAssetModel).where(
            MachineAssetModel.factory_id == factory_id))).scalars().all()
        return {"machines": [
            {"id": m.id, "name": m.name, "type": m.asset_type, "status": m.status,
             "criticality": m.criticality,
             "hourly_value_usd": m.hourly_production_value_usd}
            for m in rows
        ]}


async def _work_orders(factory_id: str) -> Dict[str, Any]:
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(select(WorkOrderModel).where(
            WorkOrderModel.factory_id == factory_id))).scalars().all()
        return {"work_orders": [
            {"id": w.id, "machine_id": w.machine_id, "product_id": w.product_id,
             "customer_order_id": w.customer_order_id, "status": w.status,
             "priority": w.priority,
             "completion_pct": round((w.quantity_completed / w.quantity_planned * 100)
                                     if w.quantity_planned else 0, 1)}
            for w in rows
        ]}


async def _open_ncrs(factory_id: str) -> Dict[str, Any]:
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(select(NCRRecordModel).where(
            NCRRecordModel.factory_id == factory_id,
            NCRRecordModel.status == "open"))).scalars().all()
        return {"ncrs": [
            {"id": r.id, "machine_id": r.machine_id, "defect_type": r.defect_type,
             "severity": r.severity, "recurrence_count": r.recurrence_count,
             "cost_impact_usd": r.cost_impact_usd}
            for r in rows
        ]}


async def _machine_context(factory_id: str, machine_id: str) -> Dict[str, Any]:
    async with AsyncSessionLocal() as db:
        ctx = await get_context_service().build_context(factory_id, machine_id, db)
        return ctx.to_dict()


def _simulate(action_name: str) -> Dict[str, Any]:
    from paaim.decision_twin.simulator import DecisionTwin
    impact = DecisionTwin().simulate_action(action_name)
    if not impact:
        return {"action_name": action_name, "known": False,
                "note": "Action not in the Decision Twin impact model."}
    return {
        "action_name": action_name, "known": True,
        "downtime_hours": impact.downtime_hours,
        "scrap_units": impact.scrap_units,
        "cost_impact_usd": getattr(impact, "cost_impact", None),
    }
