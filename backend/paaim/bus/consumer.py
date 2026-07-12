"""
Orchestration consumer — the bus → pipeline bridge.

Subscribes to the events topic and, for each record, runs the full 7-layer
orchestration and persists the result (event + decision + evidence + audit),
then publishes a compact decision summary to the decisions topic. Offsets are
committed by the bus only after this succeeds, so a crash mid-processing
re-delivers the event (at-least-once) instead of dropping it.

This is what makes ingestion reliable: producers just append to the log; this
worker drains it durably and can replay from any offset.
"""

import logging
from datetime import datetime
from typing import Any, Dict

from paaim.bus.base import BusRecord
from paaim.bus.factory import get_event_bus
from paaim.config import settings
from paaim.models import EventData, EventType, AsyncSessionLocal
from paaim.orchestrator import get_orchestrator

logger = logging.getLogger(__name__)


def _record_to_event(value: Dict[str, Any]) -> EventData:
    """Rebuild an EventData from a bus payload (tolerant of partial fields)."""
    ts = value.get("timestamp")
    return EventData(
        event_type=EventType(value.get("event_type", "production")),
        source_agent=value.get("source_agent", "bus_ingestor"),
        factory_id=value.get("factory_id", "factory_001"),
        machine_id=value.get("machine_id"),
        signal_value=float(value.get("signal_value", 0.0)),
        signal_name=value.get("signal_name", "unknown_signal"),
        confidence=float(value.get("confidence", 0.8)),
        timestamp=datetime.fromisoformat(ts) if isinstance(ts, str) else datetime.utcnow(),
        context=value.get("context", {}),
    )


async def _custom_agent_recs(session, event: EventData):
    """Fleet-wide dispatch: fire every signal-based custom agent that watches this
    event's signal and whose scope covers this machine. One agent covers many
    machines — the recommendation is tagged with the machine that triggered it."""
    try:
        from sqlalchemy import select
        from paaim.models import MachineAssetModel, FactoryKnowledgeModel
        from paaim.agents.custom_framework import get_custom_agent_registry
        from paaim.knowledge_model.learning import baseline_for

        zone = None
        if event.machine_id:
            m = (await session.execute(
                select(MachineAssetModel).where(MachineAssetModel.id == event.machine_id)
            )).scalar_one_or_none()
            zone = getattr(m, "zone_id", None) if m else None

        # Learned normal (SPC) for this machine+signal — lets agents judge against
        # the machine's OWN history instead of a static threshold.
        baseline = None
        fk = (await session.execute(
            select(FactoryKnowledgeModel).where(FactoryKnowledgeModel.factory_id == event.factory_id).limit(1)
        )).scalar_one_or_none()
        if fk and fk.profile:
            baseline = baseline_for(fk.profile, event.machine_id, event.signal_name)

        return await get_custom_agent_registry().evaluate_signal_event(
            event.signal_name, event.signal_value, event.machine_id, zone, baseline=baseline,
        )
    except Exception as e:
        logger.warning("custom agent eval failed", extra={"error": str(e)})
        return []


async def _handle(record: BusRecord) -> None:
    # Local import avoids a circular import at module load (events imports the bus).
    from paaim.api.events import persist_decision

    event = _record_to_event(record.value)
    orchestrator = get_orchestrator()
    bus = get_event_bus()

    async with AsyncSessionLocal() as session:
        # Signal-based custom agents run live on every event, before orchestration,
        # so their findings ride into the decision as evidence/context.
        custom_recs = await _custom_agent_recs(session, event)
        if custom_recs:
            event.context = {**(event.context or {}), "custom_agent_recommendations": custom_recs}
            logger.info("custom agents fired",
                        extra={"count": len(custom_recs), "signal": event.signal_name, "machine_id": event.machine_id})

        decision = await orchestrator.orchestrate(event, db=session)
        persist_decision(session, decision, event)
        await session.commit()

    orch = decision.get("orchestration_result", {})
    await bus.publish(
        settings.BUS_DECISIONS_TOPIC,
        {
            "decision_id": decision["decision_id"],
            "factory_id": event.factory_id,
            "machine_id": event.machine_id,
            "signal_name": event.signal_name,
            "selected_action": orch.get("selected_action"),
            "risk_level": orch.get("risk_level"),
            "approval_required": orch.get("approval_required"),
            "approval_route": orch.get("approval_route"),
            "custom_agents_fired": len(custom_recs),
            "source_offset": record.offset,
        },
        key=event.machine_id,
    )
    logger.info("processed event from bus",
                extra={"offset": record.offset, "action": orch.get("selected_action"),
                       "custom_agents_fired": len(custom_recs)})


async def start_orchestration_consumer() -> None:
    """Start the durable consumer that turns bus events into governed decisions."""
    bus = get_event_bus()
    await bus.start()
    await bus.start_consumer(
        topic=settings.BUS_EVENTS_TOPIC,
        group=settings.BUS_CONSUMER_GROUP,
        handler=_handle,
        dlq_topic=settings.BUS_DLQ_TOPIC,
    )
    logger.info("Orchestration consumer running",
                extra={"topic": settings.BUS_EVENTS_TOPIC, "group": settings.BUS_CONSUMER_GROUP})


async def stop_orchestration_consumer() -> None:
    bus = get_event_bus()
    await bus.stop_consumer(settings.BUS_EVENTS_TOPIC, settings.BUS_CONSUMER_GROUP)
    await bus.stop()
