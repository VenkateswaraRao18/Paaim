"""Event bus selector — returns the configured backend as a singleton."""

import logging
from typing import Optional

from paaim.bus.base import EventBus
from paaim.config import settings

logger = logging.getLogger(__name__)

_bus: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    global _bus
    if _bus is not None:
        return _bus

    backend = (settings.EVENT_BUS or "memory").lower()
    if backend == "kafka":
        from paaim.bus.kafka import KafkaEventBus
        _bus = KafkaEventBus(settings.KAFKA_BOOTSTRAP_SERVERS)
        logger.info("Event bus: kafka")
    else:
        from paaim.bus.memory import DurableLocalBus
        _bus = DurableLocalBus(settings.BUS_DATA_DIR)
        logger.info("Event bus: durable_local")
    return _bus
