from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from paaim.models import get_db, EventData, EventModel
from paaim.agents.registry import get_registry
from datetime import datetime
import uuid

router = APIRouter()


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
