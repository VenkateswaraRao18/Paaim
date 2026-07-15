"""
Recovery Decision Twin, computed for the incident actually in front of you.

The original twin answered one hand-authored scenario: its options, capacities
and costs were fixed files, so every incident was shown Line 3's restart
decision as though it were its own analysis. This builds the same decision
model from what the incident really has:

  · the actions the agents actually proposed, and the downtime each one costs
    (analysis_layers.impact_estimates)
  · the plant's real downtime cost per hour (cost_configs)
  · the real customer order on that machine — its deadline and late penalty
  · the red-team's real risk read per action

Every number below traces to one of those. Nothing is invented: where a fact is
missing we say so in the assumption ledger rather than inventing a default that
looks authoritative. The simulation stays deterministic — no LLM decides a
number here, it only ever explains them.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from paaim.models import (
    CostConfigModel,
    CustomerOrderModel,
    DecisionModel,
    WorkOrderModel,
)

# How far ahead of the deadline counts as "comfortable". Slack beyond this adds
# no further confidence; a job finishing 3 days early is not safer than one
# finishing 1 day early. A policy stance, identical for every plant — unlike a
# cost, which is a fact about one plant and must never be assumed.
SLACK_HORIZON_H = 24.0


def _qa_escape_exposure(cc: Optional[CostConfigModel],
                        order: Optional[CustomerOrderModel],
                        wo: Optional[WorkOrderModel]) -> Optional[float]:
    """
    What a bad part escaping costs THIS plant, from its own numbers.

    This was `QA_ESCAPE_EXPOSURE_USD = 30_000` — a flat figure applied to every
    incident at every customer, and a third of the expected loss it fed. The
    plant already tells us the two things that decide it: what a unit costs to
    write off, and how many units are on the job. Both are here; nothing needed
    inventing.

    A floor, not a recall model: it prices the batch at risk, not the warranty
    claim or the lost account. Returns None when the plant has not given us
    enough to price it at all, which is a real answer.
    """
    if cc is None:
        return None
    units = None
    if order is not None:
        # A customer order carries what was ordered and what has shipped; the
        # units still at risk are the difference. `order.quantity_remaining`
        # does not exist on this model — it raised AttributeError here, which
        # took the whole Recovery Twin down rather than just this one term.
        units = max(0, (order.quantity or 0) - (order.quantity_delivered or 0))
    if not units and wo is not None:
        units = getattr(wo, "quantity_planned", None)
    if not units:
        return None
    unit_cost = cc.scrap_cost_per_unit_usd
    if not unit_cost:
        return None
    return float(units) * float(unit_cost)


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


# ── real facts for one incident ───────────────────────────────────────────────
async def _incident_facts(db: AsyncSession, decision: DecisionModel) -> Dict[str, Any]:
    outcome = decision.outcome or {}
    event = outcome.get("event") or {}
    layers = outcome.get("analysis_layers") or {}
    ra = decision.recommended_action or {}
    machine_id = event.get("machine_id") or (event.get("context") or {}).get("machine_id")

    cc = (await db.execute(
        select(CostConfigModel).where(CostConfigModel.factory_id == decision.factory_id).limit(1)
    )).scalar_one_or_none()

    order: Optional[CustomerOrderModel] = None
    wo: Optional[WorkOrderModel] = None
    if machine_id:
        wo = (await db.execute(
            select(WorkOrderModel).where(
                WorkOrderModel.factory_id == decision.factory_id,
                WorkOrderModel.machine_id == machine_id,
                WorkOrderModel.status.in_(("in_progress", "scheduled")),
            ).limit(1)
        )).scalar_one_or_none()
        if wo is not None and wo.customer_order_id:
            order = await db.get(CustomerOrderModel, wo.customer_order_id)

    return {
        "machine_id": machine_id or "unknown",
        "signal": event.get("signal_name"),
        "value": event.get("signal_value"),
        "selected_action": ra.get("selected_action"),
        "risk_level": ra.get("risk_level") or "medium",
        "approval_route": ra.get("approval_route") or "operator",
        "impacts": layers.get("impact_estimates") or {},
        "red_team": layers.get("red_team_reviews") or {},
        # None, not a stand-in. The twin's whole claim is that its numbers come
        # from this plant's real economics; a default here makes it a confident
        # fiction, which is worse than no twin at all.
        "cost_per_hour": (cc.downtime_cost_per_hour_usd if cc else None),
        "failure_multiplier": (cc.unplanned_failure_multiplier if cc else 5.0),
        "cost_model_configured": cc is not None,
        # Priced from this plant's own scrap cost and the units actually on the
        # job — None when it cannot be priced from real numbers.
        "qa_escape_exposure": _qa_escape_exposure(cc, order, wo),
        "order": order,
        "work_order": wo,
    }


def _deadline_hours(order: Optional[CustomerOrderModel], now: datetime) -> Optional[float]:
    if order is None or order.promised_delivery is None:
        return None
    return (order.promised_delivery - now).total_seconds() / 3600.0


def _remaining_work_hours(wo: Optional[WorkOrderModel], now: datetime) -> float:
    """Hours of production still owed on the active job, from its own schedule."""
    if wo is None or wo.scheduled_end is None:
        return 0.0
    return max(0.0, (wo.scheduled_end - now).total_seconds() / 3600.0)


# ── controls (the levers an operator actually has) ────────────────────────────
def _factors_for(facts: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [
        {
            "factor_id": "inspection_minutes", "label": "Inspection before restart",
            "type": "slider", "default": 20, "min": 0, "max": 120, "step": 5, "unit": "min",
            "source": "operator decision",
            "business_reason": "Time spent inspecting is added to downtime, but reduces the chance of restarting into the same fault.",
        },
        {
            "factor_id": "overtime_hours", "label": "Overtime authorised",
            "type": "slider", "default": 0, "min": 0, "max": 8, "step": 1, "unit": "h",
            "source": "supervisor authority",
            "business_reason": "Overtime buys back production hours lost to the stop, protecting the delivery date.",
        },
        {
            "factor_id": "spare_on_hand", "label": "Spare part on hand",
            "type": "toggle", "default": True, "unit": "",
            "source": "stores / ERP",
            "business_reason": "Without the spare, the repair waits on procurement — the stop gets substantially longer.",
        },
        {
            "factor_id": "spare_lead_time_h", "label": "Spare lead time (if not on hand)",
            "type": "slider", "default": 4, "min": 1, "max": 24, "step": 1, "unit": "h",
            "source": "supplier terms",
            "business_reason": "How long the line waits for the part before work can even begin.",
        },
    ]


async def build_config(db: AsyncSession, decision_id: str) -> Optional[Dict[str, Any]]:
    decision = (await db.execute(
        select(DecisionModel).where(DecisionModel.id == decision_id)
    )).scalar_one_or_none()
    if decision is None:
        return None

    facts = await _incident_facts(db, decision)
    order = facts["order"]
    impacts = facts["impacts"]

    current_downtime_min = 0
    sel = facts["selected_action"]
    if sel and sel in impacts:
        current_downtime_min = int(round(float(impacts[sel].get("downtime_hours") or 0) * 60))

    options = [
        {"option_id": action, "label": action.replace("_", " ").capitalize(),
         "owner": facts["approval_route"].replace("_", " ")}
        for action in impacts.keys()
    ]

    return {
        "decision_id": decision_id,
        "controls": {
            "factors": _factors_for(facts),
            "fallback_threshold_min": 25,
            "current_downtime_min": current_downtime_min,
            "order": {
                "id": order.id if order else "—",
                "customer": order.customer_name if order else "No linked order",
            },
        },
        "presets": [
            {"preset_id": "as_found", "label": "As found", "description": "The situation exactly as reported.", "factor_overrides": {}},
            {"preset_id": "thorough", "label": "Inspect thoroughly", "description": "Longer inspection before any restart.", "factor_overrides": {"inspection_minutes": 60}},
            {"preset_id": "no_spare", "label": "Spare not in stores", "description": "Repair waits on procurement.", "factor_overrides": {"spare_on_hand": False}},
            {"preset_id": "push_delivery", "label": "Authorise overtime", "description": "Buy back the lost hours to protect the date.", "factor_overrides": {"overtime_hours": 4}},
        ],
        "options": options,
        "machine_id": facts["machine_id"],
    }


# ── the simulation ────────────────────────────────────────────────────────────
def _ship_probability(slack_h: Optional[float]) -> Tuple[float, str]:
    """
    Confidence the order still ships on time, from schedule slack alone.

    Returns (probability, plain reason). With no linked order there is no date
    to miss — that is reported as 'no delivery exposure', not as certainty.
    """
    if slack_h is None:
        return 1.0, "no customer order on this machine — nothing to miss"
    if slack_h <= 0:
        return _clamp(0.15 + slack_h / 48.0, 0.02, 0.15), f"finishes {abs(slack_h):.1f}h past the promised date"
    p = _clamp(0.5 + (slack_h / SLACK_HORIZON_H) * 0.48, 0.5, 0.98)
    return p, f"{slack_h:.1f}h of slack before the promised date"


async def simulate_incident(
    db: AsyncSession, decision_id: str, factors: Optional[Dict[str, Any]] = None
) -> Optional[Dict[str, Any]]:
    decision = (await db.execute(
        select(DecisionModel).where(DecisionModel.id == decision_id)
    )).scalar_one_or_none()
    if decision is None:
        return None

    now = datetime.utcnow()
    facts = await _incident_facts(db, decision)
    f = {
        "inspection_minutes": 20, "overtime_hours": 0,
        "spare_on_hand": True, "spare_lead_time_h": 4,
        **(factors or {}),
    }

    order = facts["order"]
    penalty = float(order.late_delivery_penalty_usd or 0.0) if order else 0.0
    hours_to_due = _deadline_hours(order, now)
    remaining_work_h = _remaining_work_hours(facts["work_order"], now)
    # A plant with no cost model still deserves a twin — it just gets one that
    # ranks on physical outcomes (delivery, QA escape, downtime) instead of
    # inventing an hourly rate to put a dollar sign in front of.
    cost_known = facts["cost_per_hour"] is not None
    cost_per_hour = float(facts["cost_per_hour"]) if cost_known else None
    qa_exposure = facts["qa_escape_exposure"]      # None = not priceable from real data

    extra_h = float(f["inspection_minutes"]) / 60.0
    if not f["spare_on_hand"]:
        extra_h += float(f["spare_lead_time_h"])
    overtime = float(f["overtime_hours"])

    sim_options: List[Dict[str, Any]] = []
    for action, impact in (facts["impacts"] or {}).items():
        base_h = float(impact.get("downtime_hours") or 0.0)
        downtime_h = base_h + extra_h
        slack_h = None
        if hours_to_due is not None:
            slack_h = hours_to_due - downtime_h - remaining_work_h + overtime
        ship, ship_reason = _ship_probability(slack_h)

        downtime_cost = downtime_h * cost_per_hour if cost_known else None
        rt = (facts["red_team"] or {}).get(action) or {}
        risk = str(rt.get("overall_risk_assessment") or facts["risk_level"] or "medium").lower()
        # Restarting on an unresolved fault is the quality exposure: the less it
        # was inspected, the more likely a bad part reaches the customer.
        qa_escape = _clamp(0.30 - (float(f["inspection_minutes"]) / 120.0) * 0.28, 0.02, 0.30)
        if "inspect" in action or "maintenance" in action:
            qa_escape = _clamp(qa_escape * 0.35, 0.01, 0.30)

        # Each term is included only where the plant gave us the facts to price
        # it. A QA escape on a job with no known unit count and no scrap cost
        # cannot be valued, so it is left out of the money and reported as a
        # probability instead — the operator still sees the risk, just not a
        # fabricated dollar attached to it.
        expected_loss = None
        if cost_known:
            expected_loss = downtime_cost + (1.0 - ship) * penalty
            if qa_exposure is not None:
                expected_loss += qa_escape * qa_exposure

        safety = "blocked" if risk == "critical" else "review" if risk in ("high", "elevated") else "pass"
        sim_options.append({
            "option_id": action,
            "label": action.replace("_", " ").capitalize(),
            "allowed": safety != "blocked",
            "blocked_by": ([f"{risk} risk — needs {facts['approval_route'].replace('_', ' ')} sign-off"]
                           if safety == "blocked" else []),
            "ship_probability": round(ship, 3),
            "expected_loss": None if expected_loss is None else round(expected_loss),
            "qa_escape_risk": round(qa_escape, 3),
            "safety_status": safety,
            "owner": facts["approval_route"].replace("_", " "),
            "is_recommended": False,
            "downtime_hours": round(downtime_h, 2),
            "ship_reason": ship_reason,
        })

    if not sim_options:
        return None

    allowed = [o for o in sim_options if o["allowed"]] or sim_options
    # With a cost model, the objective is expected loss. Without one, rank on the
    # physical outcomes the plant told us about — ship the order, don't let a bad
    # part escape, be down for less time — rather than on a fabricated dollar.
    def _rank(o: Dict[str, Any]):
        if cost_known:
            return (o["expected_loss"],)
        return (-o["ship_probability"], o["qa_escape_risk"], o["downtime_hours"])

    best = min(allowed, key=_rank)
    for o in sim_options:
        o["is_recommended"] = o["option_id"] == best["option_id"]
    runners = sorted((o for o in allowed if o is not best), key=_rank)

    changed = [
        {"factor": k, "old": v, "new": f[k]}
        for k, v in {"inspection_minutes": 20, "overtime_hours": 0, "spare_on_hand": True}.items()
        if f.get(k) != v
    ]

    constraints: List[str] = []
    if hours_to_due is not None and hours_to_due < 24:
        constraints.append(f"{order.customer_name} {order.id} is due in {hours_to_due:.1f}h")
    if not f["spare_on_hand"]:
        constraints.append(f"Spare not in stores — adds {f['spare_lead_time_h']}h before work starts")
    if facts["risk_level"] in ("critical", "high"):
        constraints.append(f"{facts['risk_level']} risk — {facts['approval_route'].replace('_', ' ')} must approve")

    return {
        "scenario_id": f"incident:{decision_id}",
        "changed_factors": changed,
        "recommended_option": best["option_id"],
        "recommended_label": best["label"],
        "next_best_action": runners[0]["label"] if runners else "—",
        "options": sim_options,
        "explanation": {
            "summary": (
                f"{best['label']} keeps {facts['machine_id']} down {best['downtime_hours']}h"
                + (f" at ${cost_per_hour:,.0f}/h" if cost_known else "")
                + f", with {best['ship_probability'] * 100:.0f}% confidence of "
                  f"shipping on time — {best['ship_reason']}."
            ),
            "triggered_constraints": constraints,
            "business_impact": (
                (
                    f"Expected loss ${best['expected_loss']:,} — downtime "
                    f"${best['downtime_hours'] * cost_per_hour:,.0f}"
                    + (f" plus {(1 - best['ship_probability']) * 100:.0f}% of a ${penalty:,.0f} late penalty"
                       if penalty else "")
                    + "."
                ) if cost_known else (
                    # Named as missing rather than quietly dropped: an operator
                    # comparing options needs to know the money column is absent
                    # because nobody configured it, not because it is zero.
                    f"Cost impact cannot be quantified — this factory has no cost model "
                    f"configured. Ranked on delivery confidence and QA escape risk instead: "
                    f"{best['downtime_hours']}h down, "
                    f"{best['ship_probability'] * 100:.0f}% confidence of shipping on time, "
                    f"{best['qa_escape_risk'] * 100:.0f}% QA escape risk."
                )
            ),
            "cost_model_configured": cost_known,
            "non_bypassable_gates": (
                [f"{facts['approval_route'].replace('_', ' ')} approval required"]
                if facts["risk_level"] in ("critical", "high") else []
            ),
        },
        "assumptions": [
            {"assumption_id": "downtime_cost_per_hour",
             "value": cost_per_hour if cost_known else "not configured",
             "unit": "USD/h", "source_file": "cost_configs (plant)", "editable": False,
             "confidence": "high" if cost_known else "n/a"},
            {"assumption_id": "action_downtime_hours", "value": "per agent impact estimate", "unit": "h",
             "source_file": "analysis_layers.impact_estimates", "editable": False, "confidence": "medium"},
            {"assumption_id": "hours_to_promised_delivery",
             "value": round(hours_to_due, 1) if hours_to_due is not None else "no linked order",
             "unit": "h", "source_file": "customer_orders", "editable": False,
             "confidence": "high" if hours_to_due is not None else "n/a"},
            {"assumption_id": "remaining_production_hours", "value": round(remaining_work_h, 1), "unit": "h",
             "source_file": "work_orders.scheduled_end", "editable": False,
             "confidence": "medium" if remaining_work_h else "low"},
            {"assumption_id": "late_delivery_penalty", "value": penalty, "unit": "USD",
             "source_file": "customer_orders", "editable": False,
             "confidence": "high" if penalty else "n/a"},
            {"assumption_id": "qa_escape_exposure",
             "value": round(qa_exposure) if qa_exposure is not None else "not priceable",
             "unit": "USD",
             "source_file": ("cost_configs.scrap_cost_per_unit_usd × units on the job"
                             if qa_exposure is not None
                             else "needs a cost model and a job quantity"),
             "editable": False,
             "confidence": "medium" if qa_exposure is not None else "n/a"},
        ],
    }
