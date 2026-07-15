"""
Recovery Decision Twin API — the what-if model, the Facility Gate board, the
audit strip, and the Factory Memory / 8D pack.

Everything here is computed for one real incident. There is deliberately no
scripted-scenario fallback: serving a fixed scenario when the incident is
unknown is how the same Line 3 restart plan ended up displayed as the analysis
of every machine in the plant. A 404 is the honest answer to "simulate an
incident I cannot find".
"""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from paaim.models import get_db
from paaim.twin import append_event, list_events
from paaim.twin.gate_incident import build_incident_gate
from paaim.twin.incident import build_config, simulate_incident
from paaim.twin.memory_incident import build_incident_memory

router = APIRouter()

_NEEDS_INCIDENT = (
    "This model is computed from a specific incident. Pass ?decision_id=… "
    "(or decision_id in the body) for the incident you want."
)


class SimulateRequest(BaseModel):
    factors: Dict[str, Any] = {}
    decision_id: str = ""


class AuditRequest(BaseModel):
    scenario_id: str = ""
    changed_factors: list = []
    recommended_option: str = ""
    blocked_actions: list = []
    generated_drafts: list = []
    user: str = "operator"


def _require(value, decision_id: str):
    if not decision_id:
        raise HTTPException(status_code=400, detail=_NEEDS_INCIDENT)
    if value is None:
        raise HTTPException(status_code=404, detail=f"No incident '{decision_id}'.")
    return value


@router.get("/config")
async def config(decision_id: str = "", db: AsyncSession = Depends(get_db)) -> dict:
    """Controls, presets and options, built from this incident's own actions and order."""
    return _require(await build_config(db, decision_id) if decision_id else None, decision_id)


@router.post("/simulate")
async def run_simulate(req: SimulateRequest, db: AsyncSession = Depends(get_db)) -> dict:
    """Deterministic what-if: adjusted factors → option metrics + recommendation + explanation."""
    return _require(
        await simulate_incident(db, req.decision_id, req.factors) if req.decision_id else None,
        req.decision_id,
    )


@router.get("/gate")
async def gate(decision_id: str = "", db: AsyncSession = Depends(get_db)) -> dict:
    """The facility-gate board for this incident's risk and approval route."""
    return _require(await build_incident_gate(db, decision_id) if decision_id else None, decision_id)


@router.get("/memory")
async def memory(decision_id: str = "", db: AsyncSession = Depends(get_db)) -> dict:
    """Factory Memory / 8D pack, derived from this machine's real history."""
    return _require(await build_incident_memory(db, decision_id) if decision_id else None, decision_id)


@router.post("/audit")
async def audit(req: AuditRequest) -> dict:
    return append_event(req.dict())


@router.get("/audit")
async def audit_list(limit: int = 20) -> dict:
    return {"events": list_events(limit)}
