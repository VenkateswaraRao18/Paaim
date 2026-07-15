"""DB glue for prioritisation.

Builds the shared lookups (cost model + machine→customer-order map) once per
request, then scores individual stored decisions against them. Kept separate
from the pure engine so the engine stays trivially testable.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from paaim.models import CostConfigModel, CustomerOrderModel, WorkOrderModel
from paaim.priority.engine import score_incident, resolve_downtime_hours, PriorityResult

_ACTIVE_WO = ("in_progress", "scheduled")
_OPEN_ORDER = ("open", "at_risk")


async def build_priority_context(db: AsyncSession, factory_id: str) -> Dict[str, Any]:
    """Resolve the per-factory facts every incident is scored against.

    Two queries total (not per decision): the cost model, and the open orders
    joined to their machine via active work orders.
    """
    cc = (await db.execute(
        select(CostConfigModel).where(CostConfigModel.factory_id == factory_id).limit(1)
    )).scalar_one_or_none()
    # No cost model → None, never a stand-in. The old default of $5,000/hour was
    # indistinguishable from a configured one downstream, so a factory that had
    # told PAAIM nothing about its economics still got "$12K at risk" printed as
    # a reason to stop a line. The engine knows how to score without this; it
    # cannot know that a number is fictional.
    cost_ctx = {
        "cost_per_hour": cc.downtime_cost_per_hour_usd if cc else None,
        "failure_multiplier": cc.unplanned_failure_multiplier if cc else 5.0,
        "configured": cc is not None,
    }

    orders = (await db.execute(
        select(CustomerOrderModel).where(
            CustomerOrderModel.factory_id == factory_id,
            CustomerOrderModel.status.in_(_OPEN_ORDER),
        )
    )).scalars().all()
    order_by_id = {o.id: o for o in orders}

    wos = (await db.execute(
        select(WorkOrderModel).where(
            WorkOrderModel.factory_id == factory_id,
            WorkOrderModel.status.in_(_ACTIVE_WO),
        )
    )).scalars().all()

    # machine → the soonest-due open order it is currently producing
    order_by_machine: Dict[str, CustomerOrderModel] = {}
    for wo in wos:
        if not wo.machine_id or not wo.customer_order_id:
            continue
        o = order_by_id.get(wo.customer_order_id)
        if not o:
            continue
        cur = order_by_machine.get(wo.machine_id)
        if cur is None or o.promised_delivery < cur.promised_delivery:
            order_by_machine[wo.machine_id] = o

    return {"cost": cost_ctx, "order_by_machine": order_by_machine}


def _confidence_from_outcome(outcome: Dict[str, Any], event: Dict[str, Any]) -> Optional[float]:
    analyses = ((outcome or {}).get("analysis_layers") or {}).get("agent_analyses") or []
    confs = [a.get("confidence") for a in analyses if isinstance(a.get("confidence"), (int, float))]
    if confs:
        return sum(confs) / len(confs)
    c = event.get("confidence")
    return c if isinstance(c, (int, float)) else None


def priority_for_decision(
    *,
    recommended_action: Dict[str, Any],
    outcome: Dict[str, Any],
    ctx: Dict[str, Any],
    now: Optional[datetime] = None,
) -> PriorityResult:
    """Score one stored decision (recommended_action + outcome) against ctx."""
    now = now or datetime.utcnow()
    ra = recommended_action or {}
    outcome = outcome or {}
    event = outcome.get("event") or {}

    risk = ra.get("risk_level") or "low"
    selected = ra.get("selected_action") or ""
    impacts = (outcome.get("analysis_layers") or {}).get("impact_estimates") or {}
    downtime_h = resolve_downtime_hours(impacts, selected, risk)

    machine_id = event.get("machine_id") or (event.get("context") or {}).get("machine_id")
    order = ctx["order_by_machine"].get(machine_id) if machine_id else None
    if order is not None:
        hours_to_due = (order.promised_delivery - now).total_seconds() / 3600.0
        penalty = order.late_delivery_penalty_usd or 0.0
        cust, oid = order.customer_name, order.id
    else:
        hours_to_due, penalty, cust, oid = None, 0.0, None, None

    return score_incident(
        risk_level=risk,
        downtime_hours=downtime_h,
        cost_per_hour=ctx["cost"]["cost_per_hour"],
        failure_multiplier=ctx["cost"]["failure_multiplier"],
        confidence=_confidence_from_outcome(outcome, event),
        hours_to_due=hours_to_due,
        penalty_usd=penalty,
        customer_name=cust,
        order_id=oid,
    )
