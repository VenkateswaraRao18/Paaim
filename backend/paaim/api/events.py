from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from paaim.models import get_db, EventData, EventModel
from paaim.agents.registry import get_registry
from paaim.event_input.simulator import EventSimulator, ScenarioDifficulty
from paaim.orchestrator import get_orchestrator
from paaim.governance.audit_logger import AuditStore
from paaim.streaming import get_publisher
from datetime import datetime
import uuid
import json

router = APIRouter()
simulator = EventSimulator()


@router.post("/ingest")
async def ingest_event(
    event: EventData,
    db: Session = Depends(get_db)
):
    """Ingest a manufacturing event into PAAIM."""
    event_id = f"evt_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"

    # Store event in database
    db_event = EventModel(
        id=event_id,
        event_type=event.event_type.value,
        factory_id=event.factory_id,
        machine_id=event.machine_id,
        signal_value=event.signal_value,
        signal_name=event.signal_name,
        confidence=event.confidence,
        context=event.context,
        created_at=event.timestamp
    )
    db.add(db_event)
    db.commit()

    return {
        "event_id": event_id,
        "status": "ingested",
        "event_type": event.event_type.value,
        "confidence": event.confidence
    }


@router.get("/list")
async def list_events(
    factory_id: str,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """List events for a factory."""
    events = db.query(EventModel).filter(
        EventModel.factory_id == factory_id
    ).order_by(EventModel.created_at.desc()).offset(offset).limit(limit).all()

    return {
        "events": [
            {
                "id": e.id,
                "event_type": e.event_type,
                "signal_name": e.signal_name,
                "confidence": e.confidence,
                "created_at": e.created_at
            } for e in events
        ],
        "count": len(events),
        "limit": limit,
        "offset": offset
    }


@router.get("/scenarios/catalog")
async def get_scenario_catalog():
    """Get available event scenarios for demo."""
    return simulator.get_scenario_catalog()


@router.post("/scenarios/generate/{scenario_name}")
async def generate_scenario(
    scenario_name: str,
    db: Session = Depends(get_db)
):
    """Generate events for a named scenario and ingest into database."""
    try:
        events = await simulator.generate_scenario_by_name(scenario_name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Ingest all events
    ingested_events = []
    for event in events:
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
            created_at=event.timestamp
        )
        db.add(db_event)
        ingested_events.append({
            "event_id": event_id,
            "event_type": event.event_type.value,
            "signal_name": event.signal_name,
            "confidence": event.confidence
        })

    db.commit()

    return {
        "scenario": scenario_name,
        "event_count": len(ingested_events),
        "events": ingested_events,
        "status": "generated and ingested"
    }


@router.post("/scenarios/generate/difficulty/{difficulty}")
async def generate_scenario_by_difficulty(
    difficulty: str,
    db: Session = Depends(get_db)
):
    """Generate events for a scenario matching difficulty level."""
    try:
        difficulty_enum = ScenarioDifficulty(difficulty)
        events = await simulator.generate_scenario_by_difficulty(difficulty_enum)
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid difficulty. Must be: {', '.join([d.value for d in ScenarioDifficulty])}"
        )

    # Ingest all events
    ingested_events = []
    for event in events:
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
            created_at=event.timestamp
        )
        db.add(db_event)
        ingested_events.append({
            "event_id": event_id,
            "event_type": event.event_type.value,
            "signal_name": event.signal_name,
            "confidence": event.confidence
        })

    db.commit()

    return {
        "difficulty": difficulty,
        "event_count": len(ingested_events),
        "events": ingested_events,
        "status": "generated and ingested"
    }


@router.post("/orchestrate")
async def orchestrate_event(event: EventData, db: Session = Depends(get_db)):
    """
    Full orchestration pipeline: Event → Decision.

    This endpoint runs a single event through the complete PAAIM pipeline:
    1. Route to specialist agents
    2. Evaluate against policy
    3. Simulate impacts with Decision Twin
    4. Challenge with Red-Team
    5. Route to approval gate
    6. Generate audit trail

    Returns complete decision with all analysis layers.
    """
    orchestrator = get_orchestrator()

    # Run orchestration pipeline
    decision = await orchestrator.orchestrate(event)

    # Store event in database
    event_id = decision["event_id"]
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
    db.commit()

    return decision


@router.post("/orchestrate/scenario/{scenario_name}")
async def orchestrate_scenario(
    scenario_name: str,
    db: Session = Depends(get_db)
):
    """
    Run full orchestration on a complete scenario.

    Generates all events for a scenario and orchestrates each one,
    returning full decision trail for demo/testing.
    """
    try:
        events = await simulator.generate_scenario_by_name(scenario_name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    orchestrator = get_orchestrator()
    decisions = []

    # Orchestrate each event
    for event in events:
        decision = await orchestrator.orchestrate(event)

        # Store event
        event_id = decision["event_id"]
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
        decisions.append(decision)

    db.commit()

    return {
        "scenario": scenario_name,
        "event_count": len(events),
        "decisions": decisions,
        "status": "orchestration complete",
    }


# ===== AUDIT ENDPOINTS =====

@router.get("/audit/search")
async def search_audit_logs(
    factory_id: str,
    event_type: str = None,
    start_date: str = None,
    end_date: str = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """
    Search audit logs with optional filters.

    Query parameters:
    - factory_id: Required factory ID
    - event_type: Optional event type filter
    - start_date: ISO format date string
    - end_date: ISO format date string
    - limit: Results per page (default 100)
    - offset: Pagination offset (default 0)
    """
    try:
        start = datetime.fromisoformat(start_date) if start_date else None
        end = datetime.fromisoformat(end_date) if end_date else None
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use ISO format.")

    store = AuditStore(db)
    logs, total = store.search_audit_logs(
        factory_id=factory_id,
        event_type=event_type,
        start_date=start,
        end_date=end,
        limit=limit,
        offset=offset,
    )

    return {
        "factory_id": factory_id,
        "logs": logs,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/audit/decisions/{decision_id}")
async def get_decision_timeline(
    decision_id: str,
    db: Session = Depends(get_db)
):
    """
    Get complete audit timeline for a specific decision.

    Returns all events in chronological order.
    """
    store = AuditStore(db)
    timeline = store.get_decision_timeline(decision_id)

    if not timeline:
        raise HTTPException(status_code=404, detail="Decision not found")

    return {
        "decision_id": decision_id,
        "timeline": timeline,
        "event_count": len(timeline),
    }


@router.get("/audit/report/{factory_id}")
async def get_compliance_report(
    factory_id: str,
    start_date: str = None,
    end_date: str = None,
    db: Session = Depends(get_db)
):
    """
    Generate compliance report for a factory.

    Returns statistics on approvals, actions, and events.
    """
    try:
        start = (
            datetime.fromisoformat(start_date)
            if start_date
            else datetime(datetime.now().year, datetime.now().month, 1)
        )
        end = (
            datetime.fromisoformat(end_date)
            if end_date
            else datetime.now()
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use ISO format.")

    store = AuditStore(db)
    report = store.generate_compliance_report(factory_id, start, end)

    return report


# ===== WEBSOCKET STREAMING =====

@router.websocket("/ws/orchestrate/{decision_id}")
async def websocket_orchestration_stream(
    websocket: WebSocket,
    decision_id: str,
):
    """
    WebSocket endpoint for real-time orchestration pipeline streaming.

    Clients connect with a decision_id and receive live events as the
    orchestration pipeline executes:
    - agents_routing → agents_complete
    - policy_checking → policy_complete
    - twin_simulating → twin_complete
    - red_team_challenging → red_team_complete
    - approval_routing → approval_complete
    - orchestration_completed or orchestration_error
    """
    await websocket.accept()
    publisher = get_publisher()

    async def send_event(event):
        """Send event to WebSocket client."""
        try:
            await websocket.send_json(event.to_dict())
        except Exception:
            # Connection closed, will be caught by disconnect handler
            pass

    # Subscribe to events for this decision
    publisher.subscribe(decision_id, send_event)

    try:
        # Keep connection open until client disconnects
        while True:
            # Receive (and ignore) any messages from client
            # This is just to keep the connection alive and detect disconnections
            await websocket.receive_text()
    except WebSocketDisconnect:
        # Client disconnected, unsubscribe
        publisher.unsubscribe(decision_id, send_event)
    except Exception as e:
        publisher.unsubscribe(decision_id, send_event)
        await websocket.close(code=1000)
