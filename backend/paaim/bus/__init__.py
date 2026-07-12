"""
PAAIM Event Bus — the reliable ingestion backbone.

Decouples event producers (SCADA / MES / sensors / dataset replay) from the
orchestration consumer, and gives durability, replay and at-least-once
delivery so PAAIM is a decision control tower, not a best-effort alerter.

Two interchangeable backends behind one interface:
  - "memory" : durable append-only JSONL log on local disk (runs anywhere,
               real durability + replay + offset commit, zero infra)
  - "kafka"  : Apache Kafka via aiokafka (production backbone)

Select with EVENT_BUS in settings. Application code never imports a concrete
backend — it calls get_event_bus().
"""

from paaim.bus.base import EventBus, BusRecord
from paaim.bus.factory import get_event_bus

__all__ = ["EventBus", "BusRecord", "get_event_bus"]
