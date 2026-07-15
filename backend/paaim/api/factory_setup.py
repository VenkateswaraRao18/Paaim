"""
Factory context ingestion — how a plant tells PAAIM what it is.

Until this existed there was no way to do it. Machines, customer orders and the
cost model could only be written by a seed script, so a real customer could
connect every source, map every tag and build every monitor, and PAAIM would
still know nothing about their business. Triage then had no money and no
deadline to reason with, and — worse, before the defaults were removed — it
invented both.

This is the stand-in for an ERP/MES connector: the same facts, handed over as
one document instead of pulled from SAP. The shape is deliberately the plant's
own vocabulary (machines, orders, costs), not PAAIM's internals.

Two rules, both learned from bugs already in this codebase:

  · **Nothing is invented.** A cost the plant omits stays NULL. Every consumer
    now reads NULL as "unknown"; a default here would undo all of that in one
    line.
  · **Deadlines may be relative.** A seeded `promised_delivery` is a fixed date
    that silently rots: the seed used here went 17 days past due and produced 62
    fabricated L1 incidents, and a twin pinned at 2%. `due_in_hours` is anchored
    at ingest, so a plant's demo data is never accidentally a crisis.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from paaim.auth.deps import tenant_id
from paaim.models import (
    CostConfigModel, CustomerOrderModel, MachineAssetModel, WorkOrderModel, get_db,
)

router = APIRouter()


# ── the document a plant hands over ──────────────────────────────────────────
class CostModelIn(BaseModel):
    """
    Every field optional, and every omission honoured as unknown.

    Not laziness: a plant that knows its downtime cost but has never priced a
    scrap unit is the normal case, and forcing a number out of them is how the
    fiction starts.
    """
    downtime_cost_per_hour_usd: Optional[float] = None
    scrap_cost_per_unit_usd: Optional[float] = None
    rework_cost_per_unit_usd: Optional[float] = None
    late_delivery_penalty_per_day_usd: Optional[float] = None
    energy_cost_per_kwh_usd: Optional[float] = None
    labor_cost_per_hour_usd: Optional[float] = None
    planned_maintenance_cost_per_hour_usd: Optional[float] = None
    unplanned_failure_multiplier: float = 5.0     # a ratio, holds across plants
    overtime_rate_multiplier: float = 1.5


class MachineIn(BaseModel):
    id: str = Field(..., description="Must match the machine_id your data source sends.")
    name: str
    asset_type: str
    zone_id: Optional[str] = None
    criticality: Optional[str] = "medium"      # low | medium | high | safety_critical
    status: Optional[str] = "running"
    oem_model: Optional[str] = None
    install_year: Optional[int] = None
    hourly_production_value_usd: Optional[float] = None


class CustomerOrderIn(BaseModel):
    id: str
    customer_name: str
    quantity: int
    product_id: Optional[str] = None
    # Absolute, or relative to ingest time. Relative is what keeps a plant's
    # data from rotting into a fake emergency between one demo and the next.
    promised_delivery: Optional[datetime] = None
    due_in_hours: Optional[float] = None
    quantity_delivered: int = 0
    status: str = "open"                        # open | at_risk | closed
    priority: str = "normal"
    late_delivery_penalty_usd: Optional[float] = None
    contract_value_usd: Optional[float] = None


class WorkOrderIn(BaseModel):
    id: str
    machine_id: str
    quantity_planned: int
    customer_order_id: Optional[str] = None
    product_id: Optional[str] = None
    quantity_completed: int = 0
    status: str = "in_progress"                 # in_progress | scheduled | complete
    scheduled_end: Optional[datetime] = None
    ends_in_hours: Optional[float] = None
    shift: Optional[str] = None


class FactoryContextIn(BaseModel):
    # No factory_id: the tenant comes from the token. A caller who can name
    # the factory they are writing into can overwrite another plant.
    cost_model: Optional[CostModelIn] = None
    machines: List[MachineIn] = []
    customer_orders: List[CustomerOrderIn] = []
    work_orders: List[WorkOrderIn] = []
    replace: bool = True


def _resolve_when(absolute: Optional[datetime], relative_hours: Optional[float],
                  now: datetime) -> Optional[datetime]:
    """Absolute wins; otherwise anchor the relative offset at ingest time."""
    if absolute is not None:
        return absolute
    if relative_hours is not None:
        return now + timedelta(hours=relative_hours)
    return None


@router.post("/ingest")
async def ingest_factory_context(body: FactoryContextIn, factory: str = Depends(tenant_id),
                                 db: AsyncSession = Depends(get_db)) -> dict:
    """
    Load a plant's own facts: machines, cost model, orders, work orders.

    `replace=True` clears this factory's existing context first, so re-running is
    idempotent rather than accumulating duplicates (the seed script raised an
    IntegrityError on a second run, which is a worse answer than replacing).
    """
    now = datetime.utcnow()
    fid = factory
    loaded: Dict[str, int] = {}

    if body.replace:
        # Order matters only for readability; there are no FK constraints here.
        for model in (WorkOrderModel, CustomerOrderModel, MachineAssetModel, CostConfigModel):
            await db.execute(delete(model).where(model.factory_id == fid))

    # ── cost model ──────────────────────────────────────────────────────────
    missing_costs: List[str] = []
    if body.cost_model is not None:
        cm = body.cost_model
        existing = (await db.execute(
            select(CostConfigModel).where(CostConfigModel.factory_id == fid).limit(1)
        )).scalar_one_or_none()
        target = existing or CostConfigModel(id=f"cc_{uuid.uuid4().hex[:8]}", factory_id=fid)
        for field, value in cm.dict().items():
            setattr(target, field, value)
        target.updated_at = now
        db.add(target)
        loaded["cost_model"] = 1
        missing_costs = [k for k, v in cm.dict().items() if v is None]

    # ── machines ────────────────────────────────────────────────────────────
    for m in body.machines:
        db.add(MachineAssetModel(
            id=m.id, factory_id=fid, name=m.name, asset_type=m.asset_type,
            zone_id=m.zone_id, criticality=m.criticality, status=m.status,
            oem_model=m.oem_model, install_year=m.install_year,
            hourly_production_value_usd=m.hourly_production_value_usd,
        ))
    loaded["machines"] = len(body.machines)

    # ── customer orders ─────────────────────────────────────────────────────
    for o in body.customer_orders:
        due = _resolve_when(o.promised_delivery, o.due_in_hours, now)
        if due is None:
            raise HTTPException(
                status_code=400,
                detail=(f"Order '{o.id}' has neither promised_delivery nor due_in_hours. "
                        f"Delivery urgency is a third of the triage score — without a "
                        f"deadline PAAIM cannot rank this order against any other."),
            )
        db.add(CustomerOrderModel(
            id=o.id, factory_id=fid, customer_name=o.customer_name,
            product_id=o.product_id, quantity=o.quantity,
            quantity_delivered=o.quantity_delivered, order_date=now,
            promised_delivery=due, status=o.status, priority=o.priority,
            late_delivery_penalty_usd=o.late_delivery_penalty_usd,
            contract_value_usd=o.contract_value_usd,
        ))
    loaded["customer_orders"] = len(body.customer_orders)

    # ── work orders ─────────────────────────────────────────────────────────
    machine_ids = {m.id for m in body.machines}
    order_ids = {o.id for o in body.customer_orders}
    dangling: List[str] = []
    for w in body.work_orders:
        # A work order pointing at a machine or order that does not exist is the
        # link triage walks to find the money. Silently accepted, it produces an
        # incident that is quietly unpriced for no visible reason.
        if body.machines and w.machine_id not in machine_ids:
            dangling.append(f"{w.id} → machine '{w.machine_id}' not in this payload")
        if w.customer_order_id and body.customer_orders and w.customer_order_id not in order_ids:
            dangling.append(f"{w.id} → order '{w.customer_order_id}' not in this payload")
        db.add(WorkOrderModel(
            id=w.id, factory_id=fid, machine_id=w.machine_id,
            product_id=w.product_id, customer_order_id=w.customer_order_id,
            quantity_planned=w.quantity_planned, quantity_completed=w.quantity_completed,
            status=w.status, scheduled_start=now,
            scheduled_end=_resolve_when(w.scheduled_end, w.ends_in_hours, now),
            shift=w.shift,
        ))
    loaded["work_orders"] = len(body.work_orders)

    await db.commit()

    return {
        "ok": True,
        "factory_id": fid,
        "replaced": body.replace,
        "loaded": loaded,
        # Say plainly what triage can and cannot do with what it was just given,
        # rather than letting the operator discover it from a blank column.
        "triage_readiness": _readiness(loaded, missing_costs, body),
        "warnings": ([f"{len(dangling)} work order link(s) point at something not in this payload: "
                      + "; ".join(dangling[:5])] if dangling else []),
    }


def _readiness(loaded: Dict[str, int], missing_costs: List[str], body: FactoryContextIn) -> dict:
    can_price = bool(loaded.get("cost_model")) and body.cost_model is not None \
        and body.cost_model.downtime_cost_per_hour_usd is not None
    can_deadline = loaded.get("customer_orders", 0) > 0 and loaded.get("work_orders", 0) > 0
    notes: List[str] = []
    if not can_price:
        notes.append("No downtime cost — incidents will be triaged on safety and delivery only, "
                     "and reported as 'cost impact unknown'.")
    if not can_deadline:
        notes.append("No orders linked to machines via work orders — incidents cannot be tied to a "
                     "deadline, so delivery urgency falls back to a floor.")
    if missing_costs:
        notes.append(f"Not priced: {', '.join(missing_costs)}. These stay unknown rather than assumed.")
    return {
        "can_quantify_cost": can_price,
        "can_reason_about_deadlines": can_deadline,
        "notes": notes or ["Full context — triage can weigh money, deadlines and safety."],
    }


@router.get("/summary")
async def context_summary(factory_id: str = Depends(tenant_id), db: AsyncSession = Depends(get_db)) -> dict:
    """What PAAIM currently knows about this plant, and what it therefore cannot do."""
    cc = (await db.execute(
        select(CostConfigModel).where(CostConfigModel.factory_id == factory_id).limit(1)
    )).scalar_one_or_none()
    machines = (await db.execute(
        select(MachineAssetModel).where(MachineAssetModel.factory_id == factory_id)
    )).scalars().all()
    orders = (await db.execute(
        select(CustomerOrderModel).where(CustomerOrderModel.factory_id == factory_id)
    )).scalars().all()
    wos = (await db.execute(
        select(WorkOrderModel).where(WorkOrderModel.factory_id == factory_id)
    )).scalars().all()

    cost_fields = {}
    if cc:
        for f in ("downtime_cost_per_hour_usd", "scrap_cost_per_unit_usd",
                  "rework_cost_per_unit_usd", "late_delivery_penalty_per_day_usd",
                  "labor_cost_per_hour_usd"):
            cost_fields[f] = getattr(cc, f)

    return {
        "factory_id": factory_id,
        "cost_model": cost_fields or None,
        "machines": [{"id": m.id, "name": m.name, "type": m.asset_type,
                      "zone": m.zone_id, "criticality": m.criticality} for m in machines],
        "counts": {"machines": len(machines), "customer_orders": len(orders), "work_orders": len(wos)},
        "can_quantify_cost": bool(cc and cc.downtime_cost_per_hour_usd is not None),
        "can_reason_about_deadlines": bool(orders and wos),
    }
