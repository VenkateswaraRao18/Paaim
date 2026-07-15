"""
Facility Gate for the incident in hand.

The gate's job is to be the thing an operator cannot argue with, so it must be
computed from that incident's own risk and approval route — a fixed board that
shows the same holds for every machine teaches people to click past it, which
defeats the entire point of having a gate.

Every row here traces to a real fact: the agents' risk level, the policy
engine's approval route, and the red-team's own objections.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from paaim.models import DecisionModel

# Actions that physically restart or keep production running: these are what a
# gate exists to hold back.
_RESTART_ACTIONS = {"restart_now", "resume_production", "continue_production", "restart"}


async def build_incident_gate(db: AsyncSession, decision_id: str) -> Optional[Dict[str, Any]]:
    decision = (await db.execute(
        select(DecisionModel).where(DecisionModel.id == decision_id)
    )).scalar_one_or_none()
    if decision is None:
        return None

    outcome = decision.outcome or {}
    event = outcome.get("event") or {}
    layers = outcome.get("analysis_layers") or {}
    ra = decision.recommended_action or {}

    machine_id = event.get("machine_id") or (event.get("context") or {}).get("machine_id") or "unknown"
    signal = (event.get("signal_name") or "signal").replace("_", " ")
    risk = str(ra.get("risk_level") or "medium").lower()
    route = (ra.get("approval_route") or "operator").replace("_", " ")
    selected = ra.get("selected_action") or ""
    approved = decision.status in ("approved", "executed")

    gates: List[Dict[str, Any]] = []

    # 1 — the signal itself
    gates.append({
        "gate_id": "signal_breach",
        "label": f"{signal.capitalize()} on {machine_id}",
        "status": "hold" if risk in ("critical", "high") else "review",
        "reason": (
            f"{signal.capitalize()} breached its threshold"
            + (f" at {event.get('signal_value')}" if event.get("signal_value") is not None else "")
            + f" — assessed {risk} risk."
        ),
        "owner": route,
        "source": "live signal + agent assessment",
        "allowed_actions": ["inspect_root_cause", "schedule_maintenance"],
    })

    # 2 — human authority
    gates.append({
        "gate_id": "approval",
        "label": f"{route.title()} approval",
        "status": "pass" if approved else ("hold" if risk in ("critical", "high") else "review"),
        "reason": (
            f"Approved by {decision.approved_by}." if approved
            else f"{risk.capitalize()} risk routes to {route}; not yet approved."
        ),
        "owner": route,
        "source": "policy engine approval route",
        "allowed_actions": [selected] if approved else [],
    })

    # 3 — the red team's own objections, if it raised any
    rt = (layers.get("red_team_reviews") or {}).get(selected) or {}
    factors = rt.get("risk_factors") or []
    if factors:
        gates.append({
            "gate_id": "red_team",
            "label": "Red-team challenge",
            "status": "review",
            "reason": str(factors[0])[:160],
            "owner": route,
            "source": "red-team review of the recommended action",
            "allowed_actions": [],
        })

    restart_blocked = any(g["status"] == "hold" for g in gates)
    blocked = sorted(_RESTART_ACTIONS) if restart_blocked else []
    allowed_drafts = sorted({a for g in gates for a in g["allowed_actions"]})

    overall = "blocked" if restart_blocked else ("review" if any(g["status"] == "review" for g in gates) else "clear")
    return {
        "decision_id": decision_id,
        "overall_status": overall,
        "restart_blocked": restart_blocked,
        "gates": gates,
        "blocked_actions": blocked,
        "allowed_draft_actions": allowed_drafts,
        "trust_banner": (
            f"Restart is held on {machine_id} until {route} signs off."
            if restart_blocked else
            f"No hold on {machine_id} — {route} review outstanding."
            if overall == "review" else
            f"{machine_id} is clear to proceed."
        ),
    }
