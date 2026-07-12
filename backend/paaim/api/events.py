from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from paaim.models import get_db, EventData, EventModel, DecisionModel, ApprovalWorkflowModel, AuditLogModel
from paaim.agents.registry import get_registry
from paaim.event_input.simulator import EventSimulator, ScenarioDifficulty
from paaim.orchestrator import get_orchestrator
from paaim.governance.audit_logger import AuditStore
from paaim.streaming import get_publisher
from paaim.config import settings
from datetime import datetime
from typing import List, Dict, Any
import uuid


def _write_audit_entries(decision: Dict[str, Any], factory_id: str) -> List[AuditLogModel]:
    """Build AuditLogModel rows from an orchestration decision result."""
    dec_id = decision["decision_id"]
    ep = decision.get("evidence_pack", {})
    orch = decision.get("orchestration_result", {})
    entries: List[AuditLogModel] = []

    # 1. Event detected
    evt = ep.get("event_data", {})
    entries.append(AuditLogModel(
        id=f"audit_{dec_id}_detect",
        decision_id=dec_id,
        event_type="event_detected",
        actor="System",
        action="event_detected",
        details={"factory_id": factory_id, "signal_name": evt.get("signal_name"),
                 "event_type": evt.get("event_type"), "confidence": evt.get("confidence")},
    ))

    # 2. One entry per agent
    for analysis in ep.get("agent_analyses", []):
        agent_name = analysis.get("agent", "unknown")
        entries.append(AuditLogModel(
            id=f"audit_{dec_id}_agent_{agent_name}",
            decision_id=dec_id,
            event_type="agent_analyzed",
            actor=agent_name,
            action="analyze",
            details={"factory_id": factory_id, "confidence": analysis.get("confidence"),
                     "reasoning": (analysis.get("reasoning") or "")[:200]},
        ))

    # 3. Policy evaluated
    entries.append(AuditLogModel(
        id=f"audit_{dec_id}_policy",
        decision_id=dec_id,
        event_type="policy_evaluated",
        actor="PolicyEngine",
        action="policy_evaluated",
        details={"factory_id": factory_id, "policy_result": ep.get("policy_evaluation", {})},
    ))

    # 4. Decision recommended / auto-approved
    status = "approved" if not orch.get("approval_required", True) else "recommended"
    entries.append(AuditLogModel(
        id=f"audit_{dec_id}_decision",
        decision_id=dec_id,
        event_type=status,
        actor="Orchestrator",
        action="recommend_action",
        details={"factory_id": factory_id, "selected_action": orch.get("selected_action"),
                 "approval_required": orch.get("approval_required"),
                 "approval_route": orch.get("approval_route"), "status": status},
    ))

    return entries


def _build_manager_options(analysis_layers: Dict[str, Any], selected_action: str,
                           cost_ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Turn the raw agent analyses + impact estimates + red-team review into a
    manager-facing set of options with cost/downtime tradeoffs — what the
    approver is actually choosing between. Computed from already-stored data,
    so it works for every decision without re-running the pipeline.
    """
    agent_analyses = analysis_layers.get("agent_analyses", []) or []
    impacts = analysis_layers.get("impact_estimates", {}) or {}
    red_team = analysis_layers.get("red_team_reviews", {}) or {}

    # Collect unique candidate actions across all agents.
    options: Dict[str, Dict[str, Any]] = {}
    for a in agent_analyses:
        if "error" in a:
            continue
        for r in a.get("recommendations", []) or []:
            name = r.get("action_name")
            if not name or name in options:
                continue
            imp = impacts.get(name, {}) or r.get("estimated_impact", {}) or {}
            options[name] = {
                "action": name,
                "description": r.get("description", ""),
                "risk_level": r.get("risk_level"),
                "confidence": r.get("confidence"),
                "proposed_by": a.get("agent"),
                "downtime_hours": imp.get("downtime_hours"),
                "scrap_units": imp.get("scrap_units"),
                "cost_impact_usd": imp.get("cost_impact"),
                "is_recommended": name == selected_action,
            }

    # Ensure the selected action is present and first.
    ordered = sorted(options.values(), key=lambda o: (not o["is_recommended"]))

    # "If no action" — quantify the cost of inaction from the cost model.
    downtime_cost = (cost_ctx or {}).get("downtime_cost_per_hour_usd")
    failure_mult = (cost_ctx or {}).get("unplanned_failure_multiplier", 5.0)
    inaction = None
    if downtime_cost:
        inaction = {
            "headline": "Do nothing",
            "consequence": f"Unplanned failure typically costs ~{failure_mult:g}× a planned stop "
                           f"(≈ ${int(downtime_cost * failure_mult):,}/hr) plus any missed-deadline penalty.",
        }

    rt = red_team.get(selected_action, {}) or {}
    return {
        "options": ordered,
        "alternatives_considered": rt.get("suggested_alternatives", []) or [],
        "risk_factors": rt.get("risk_factors", []) or [],
        "if_no_action": inaction,
    }


def persist_decision(db, decision: Dict[str, Any], event: EventData) -> str:
    """
    Persist a full orchestration result: the event row, the decision row
    (with the complete evidence pack stored in `outcome`), and audit entries.

    Storing event + analysis_layers in `outcome` is what lets the Decision
    Detail page show the signal, agent reasoning, policy, impact and red-team
    review instead of 'unknown'/0.
    """
    event_id = decision["event_id"]
    db.add(EventModel(
        id=event_id, event_type=event.event_type.value,
        factory_id=event.factory_id, machine_id=event.machine_id,
        signal_value=event.signal_value, signal_name=event.signal_name,
        confidence=event.confidence, context=event.context,
        created_at=event.timestamp,
    ))
    orch = decision.get("orchestration_result", {})
    status = "approved" if not orch.get("approval_required", True) else "recommended"
    db.add(DecisionModel(
        id=decision["decision_id"], event_id=event_id,
        factory_id=event.factory_id, status=status,
        recommended_action=orch,
        outcome={
            "event": decision.get("event"),
            "analysis_layers": decision.get("analysis_layers"),
        },
        layer_latencies=decision.get("layer_latencies"),
    ))
    for entry in _write_audit_entries(decision, event.factory_id):
        db.add(entry)
    return event_id


router = APIRouter()
simulator = EventSimulator()


@router.post("/ingest")
async def ingest_event(event: EventData, db: AsyncSession = Depends(get_db)):
    """Ingest a manufacturing event into PAAIM."""
    event_id = f"evt_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"

    db_event = EventModel(
        id=event_id,
        event_type=event.event_type.value,
        factory_id=event.factory_id,
        machine_id=event.machine_id,
        signal_value=event.signal_value,
        signal_name=event.signal_name,
        confidence=event.confidence,
        context=event.context,
        created_at=event.timestamp,
    )
    db.add(db_event)

    return {
        "event_id": event_id,
        "status": "ingested",
        "event_type": event.event_type.value,
        "confidence": event.confidence,
    }


# ── Reliable streaming ingestion (Event Bus) ───────────────────────────────────

@router.post("/stream/publish")
async def publish_to_bus(event: EventData):
    """
    Durably publish an event to the reliable ingestion backbone.

    Unlike /orchestrate (synchronous), this just appends to the durable log and
    returns immediately. The background consumer drains it through the full
    pipeline with at-least-once delivery — so the event survives a restart and
    is never silently dropped under load.
    """
    from paaim.bus.factory import get_event_bus
    bus = get_event_bus()
    await bus.start()
    offset = await bus.publish(
        settings.BUS_EVENTS_TOPIC,
        {
            "event_type": event.event_type.value,
            "source_agent": event.source_agent,
            "factory_id": event.factory_id,
            "machine_id": event.machine_id,
            "signal_value": event.signal_value,
            "signal_name": event.signal_name,
            "confidence": event.confidence,
            "timestamp": event.timestamp.isoformat(),
            "context": event.context,
        },
        key=event.machine_id,
    )
    return {"status": "published", "topic": settings.BUS_EVENTS_TOPIC, "offset": offset,
            "delivery": "at-least-once", "backend": settings.EVENT_BUS}


@router.get("/stream/status")
async def bus_status():
    """Event bus health: backend, topic sizes, consumer lag, committed offsets."""
    from paaim.bus.factory import get_event_bus
    return await get_event_bus().stats()


@router.post("/stream/replay")
async def replay_stream(from_offset: int = 0):
    """Reset the orchestrator consumer group to reprocess from an offset (replay)."""
    from paaim.bus.factory import get_event_bus
    bus = get_event_bus()
    await bus.replay(settings.BUS_EVENTS_TOPIC, settings.BUS_CONSUMER_GROUP, from_offset)
    return {"status": "replay_scheduled", "topic": settings.BUS_EVENTS_TOPIC,
            "group": settings.BUS_CONSUMER_GROUP, "from_offset": from_offset}


@router.get("/list")
async def list_events(
    factory_id: str,
    limit: int = 100,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    """List events for a factory."""
    result = await db.execute(
        select(EventModel)
        .where(EventModel.factory_id == factory_id)
        .order_by(EventModel.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    events = result.scalars().all()

    return {
        "events": [
            {
                "id": e.id,
                "event_type": e.event_type,
                "signal_name": e.signal_name,
                "confidence": e.confidence,
                "created_at": e.created_at,
            }
            for e in events
        ],
        "count": len(events),
        "limit": limit,
        "offset": offset,
    }


@router.get("/scenarios/catalog")
async def get_scenario_catalog():
    """Get available event scenarios."""
    return simulator.get_scenario_catalog()


@router.post("/scenarios/generate/{scenario_name}")
async def generate_scenario(scenario_name: str, db: AsyncSession = Depends(get_db)):
    """Generate events for a named scenario."""
    try:
        events = await simulator.generate_scenario_by_name(scenario_name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    ingested = []
    for event in events:
        event_id = f"evt_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        db.add(EventModel(
            id=event_id,
            event_type=event.event_type.value,
            factory_id=event.factory_id,
            machine_id=event.machine_id,
            signal_value=event.signal_value,
            signal_name=event.signal_name,
            confidence=event.confidence,
            context=event.context,
            created_at=event.timestamp,
        ))
        ingested.append({"event_id": event_id, "event_type": event.event_type.value,
                         "signal_name": event.signal_name, "confidence": event.confidence})

    return {"scenario": scenario_name, "event_count": len(ingested), "events": ingested,
            "status": "generated and ingested"}


@router.post("/scenarios/generate/difficulty/{difficulty}")
async def generate_scenario_by_difficulty(difficulty: str, db: AsyncSession = Depends(get_db)):
    """Generate events for a scenario matching difficulty level."""
    try:
        difficulty_enum = ScenarioDifficulty(difficulty)
        events = await simulator.generate_scenario_by_difficulty(difficulty_enum)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid difficulty. Must be: {', '.join([d.value for d in ScenarioDifficulty])}",
        )

    ingested = []
    for event in events:
        event_id = f"evt_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        db.add(EventModel(
            id=event_id,
            event_type=event.event_type.value,
            factory_id=event.factory_id,
            machine_id=event.machine_id,
            signal_value=event.signal_value,
            signal_name=event.signal_name,
            confidence=event.confidence,
            context=event.context,
            created_at=event.timestamp,
        ))
        ingested.append({"event_id": event_id, "event_type": event.event_type.value,
                         "signal_name": event.signal_name, "confidence": event.confidence})

    return {"difficulty": difficulty, "event_count": len(ingested), "events": ingested,
            "status": "generated and ingested"}


@router.post("/orchestrate")
async def orchestrate_event(event: EventData, db: AsyncSession = Depends(get_db)):
    """
    Full orchestration pipeline: Event → Decision.

    Runs a single event through the complete 7-layer PAAIM pipeline and
    persists both the event and the decision to the database.
    """
    orchestrator = get_orchestrator()
    decision = await orchestrator.orchestrate(event, db=db)
    persist_decision(db, decision, event)
    return decision


@router.post("/orchestrate/scenario/{scenario_name}")
async def orchestrate_scenario(scenario_name: str, db: AsyncSession = Depends(get_db)):
    """Run full orchestration on a complete scenario."""
    try:
        events = await simulator.generate_scenario_by_name(scenario_name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    orchestrator = get_orchestrator()
    decisions = []

    for event in events:
        decision = await orchestrator.orchestrate(event, db=db)
        persist_decision(db, decision, event)
        decisions.append(decision)

    return {
        "scenario": scenario_name,
        "event_count": len(events),
        "decisions": decisions,
        "status": "orchestration complete",
    }


# ── Research dataset ingestion ────────────────────────────────────────────────

@router.get("/dataset/info")
async def dataset_info():
    """Describe the supported research dataset and how it maps to PAAIM events."""
    from data_adapters.ai4i2020 import summarise_mapping
    return summarise_mapping()


@router.post("/dataset/ingest")
async def ingest_dataset(
    limit: int = 50,
    failures_only: bool = False,
    sample: bool = True,
    db: AsyncSession = Depends(get_db),
):
    """
    Stream rows from the AI4I 2020 dataset through the full pipeline.

    sample=True uses the bundled 12-row sample; sample=False expects the full
    CSV at data_adapters/ai4i2020.csv. Each qualifying row → events → decisions,
    persisted so they appear on the Dashboard, Analytics and Audit Trail.
    """
    import csv as _csv
    import os as _os
    from datetime import timedelta
    from data_adapters.ai4i2020 import row_to_events

    path = "data_adapters/ai4i2020_sample.csv" if sample else "data_adapters/ai4i2020.csv"
    if not _os.path.exists(path):
        raise HTTPException(
            status_code=404,
            detail=f"Dataset file not found: {path}. Download the AI4I 2020 CSV "
                   f"from UCI #601 and place it at data_adapters/ai4i2020.csv.",
        )

    orchestrator = get_orchestrator()
    base_ts = datetime.utcnow() - timedelta(hours=24)
    made = 0
    breakdown: Dict[str, int] = {}

    with open(path, newline="") as fh:
        for i, raw in enumerate(_csv.DictReader(fh)):
            if limit > 0 and made >= limit:
                break
            for event in row_to_events(raw, timestamp=base_ts + timedelta(seconds=i * 8),
                                       warn_only=not failures_only):
                if limit > 0 and made >= limit:
                    break
                decision = await orchestrator.orchestrate(event, db=db)
                persist_decision(db, decision, event)
                made += 1
                breakdown[event.signal_name] = breakdown.get(event.signal_name, 0) + 1

    return {
        "dataset": "ai4i2020" + ("_sample" if sample else ""),
        "decisions_created": made,
        "failure_mode_breakdown": breakdown,
        "status": "ingested",
    }


# ── Audit ─────────────────────────────────────────────────────────────────────

@router.get("/audit/search")
async def search_audit_logs(
    factory_id: str,
    event_type: str = None,
    start_date: str = None,
    end_date: str = None,
    limit: int = 100,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    try:
        start = datetime.fromisoformat(start_date) if start_date else None
        end = datetime.fromisoformat(end_date) if end_date else None
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use ISO format.")

    store = AuditStore(db)
    logs, total = await store.search_audit_logs(
        factory_id=factory_id, event_type=event_type,
        start_date=start, end_date=end, limit=limit, offset=offset,
    )
    return {"factory_id": factory_id, "logs": logs, "total": total,
            "limit": limit, "offset": offset}


@router.get("/audit/decisions/{decision_id}")
async def get_decision_timeline(decision_id: str, db: AsyncSession = Depends(get_db)):
    store = AuditStore(db)
    timeline = await store.get_decision_timeline(decision_id)
    if not timeline:
        raise HTTPException(status_code=404, detail="Decision not found")
    return {"decision_id": decision_id, "timeline": timeline, "event_count": len(timeline)}


@router.get("/audit/report/{factory_id}")
async def get_compliance_report(
    factory_id: str,
    start_date: str = None,
    end_date: str = None,
    db: AsyncSession = Depends(get_db),
):
    try:
        start = (
            datetime.fromisoformat(start_date)
            if start_date
            else datetime(datetime.now().year, datetime.now().month, 1)
        )
        end = datetime.fromisoformat(end_date) if end_date else datetime.now()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use ISO format.")

    store = AuditStore(db)
    return await store.generate_compliance_report(factory_id, start, end)


# ── WebSocket ─────────────────────────────────────────────────────────────────

@router.websocket("/ws/orchestrate/{decision_id}")
async def websocket_orchestration_stream(websocket: WebSocket, decision_id: str):
    """Real-time orchestration pipeline stream via WebSocket."""
    await websocket.accept()
    publisher = get_publisher()

    async def send_event(event):
        try:
            await websocket.send_json(event.to_dict())
        except Exception:
            pass

    publisher.subscribe(decision_id, send_event)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        publisher.unsubscribe(decision_id, send_event)
    except Exception:
        publisher.unsubscribe(decision_id, send_event)
        await websocket.close(code=1000)


# ── Approvals ─────────────────────────────────────────────────────────────────

from pydantic import BaseModel as _BaseModel
from typing import Optional as _Optional


class ApprovalRequest(_BaseModel):
    action: str
    approved_by: str = "operator"
    notes: _Optional[str] = None


@router.post("/decisions/{decision_id}/approve")
async def approve_decision(
    decision_id: str,
    body: ApprovalRequest,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(DecisionModel).where(DecisionModel.id == decision_id))
    decision = result.scalar_one_or_none()
    if not decision:
        raise HTTPException(status_code=404, detail="Decision not found")

    if body.action not in ("approve", "reject"):
        raise HTTPException(status_code=400, detail="action must be 'approve' or 'reject'")

    decision.status = "approved" if body.action == "approve" else "rejected"
    decision.approved_by = body.approved_by
    decision.approval_timestamp = datetime.utcnow()

    # Back-fill decision outcome into short-term memory
    try:
        from paaim.memory.short_term import get_memory_store
        rec_action = decision.recommended_action or {}
        machine_id = rec_action.get("machine_id") or rec_action.get("event_data", {}).get("machine_id")
        signal_name = rec_action.get("signal_name") or rec_action.get("event_data", {}).get("signal_name")
        if machine_id and signal_name:
            get_memory_store().update_decision_status(
                decision.factory_id, machine_id, signal_name, decision.status
            )
    except Exception:
        pass

    db.add(ApprovalWorkflowModel(
        id=f"wf_{uuid.uuid4().hex[:8]}",
        decision_id=decision_id,
        approver_role=body.approved_by,
        status=decision.status,
        notes=body.notes,
        approved_at=decision.approval_timestamp,
    ))

    db.add(AuditLogModel(
        id=f"audit_{decision_id}_{body.action}_{uuid.uuid4().hex[:6]}",
        decision_id=decision_id,
        event_type=decision.status,
        actor=body.approved_by,
        action=body.action,
        details={"status": decision.status, "notes": body.notes,
                 "approver": body.approved_by},
    ))

    return {
        "decision_id": decision_id,
        "status": decision.status,
        "approved_by": decision.approved_by,
        "approval_timestamp": decision.approval_timestamp.isoformat(),
    }


@router.get("/decisions")
async def list_decisions(
    factory_id: str = "factory_001",
    status: str = None,
    limit: int = 100,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    """List decisions for a factory, optionally filtered by status."""
    q = select(DecisionModel).where(DecisionModel.factory_id == factory_id)
    if status:
        q = q.where(DecisionModel.status == status)
    q = q.order_by(DecisionModel.created_at.desc()).offset(offset).limit(limit)
    rows = (await db.execute(q)).scalars().all()
    return {
        "decisions": [
            {
                "decision_id": d.id,
                "event_id": d.event_id,
                "factory_id": d.factory_id,
                "status": d.status,
                "recommended_action": d.recommended_action,
                "approved_by": d.approved_by,
                "approval_timestamp": d.approval_timestamp.isoformat() if d.approval_timestamp else None,
                "created_at": d.created_at.isoformat(),
            }
            for d in rows
        ],
        "count": len(rows),
        "factory_id": factory_id,
    }


@router.get("/decisions/{decision_id}")
async def get_decision(decision_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(DecisionModel).where(DecisionModel.id == decision_id))
    decision = result.scalar_one_or_none()
    if not decision:
        raise HTTPException(status_code=404, detail="Decision not found")
    outcome = decision.outcome or {}
    stored_event = outcome.get("event") or {}
    # Normalise event shape for the detail page (orchestrator stores `type`).
    event_block = {
        "event_type": stored_event.get("type") or stored_event.get("event_type") or "unknown",
        "signal_name": stored_event.get("signal_name", "—"),
        "signal_value": stored_event.get("signal_value", 0),
        "confidence": stored_event.get("confidence", 0),
        "machine_id": stored_event.get("machine_id")
            or (stored_event.get("context") or {}).get("machine_id"),
        "context": stored_event.get("context", {}),
        "factory_id": decision.factory_id,
        "timestamp": decision.created_at.isoformat(),
    }
    analysis_layers = outcome.get("analysis_layers") or {
        "agent_analyses": [], "policy_evaluations": {},
        "impact_estimates": {}, "red_team_reviews": {},
    }
    selected = (decision.recommended_action or {}).get("selected_action") or ""
    # Pull the factory cost model so we can quantify the cost of inaction.
    from paaim.models import CostConfigModel
    cc = (await db.execute(
        select(CostConfigModel).where(CostConfigModel.factory_id == decision.factory_id).limit(1)
    )).scalar_one_or_none()
    cost_ctx = {
        "downtime_cost_per_hour_usd": cc.downtime_cost_per_hour_usd if cc else None,
        "unplanned_failure_multiplier": cc.unplanned_failure_multiplier if cc else 5.0,
    }
    manager_options = _build_manager_options(analysis_layers, selected, cost_ctx)

    return {
        "decision_id": decision.id,
        "event_id": decision.event_id,
        "factory_id": decision.factory_id,
        "status": decision.status,
        "recommended_action": decision.recommended_action,
        "event": event_block,
        "manager_options": manager_options,
        "analysis_layers": analysis_layers,
        "approved_by": decision.approved_by,
        "approval_timestamp": decision.approval_timestamp.isoformat() if decision.approval_timestamp else None,
        "layer_latencies": decision.layer_latencies,
        "created_at": decision.created_at.isoformat(),
    }
