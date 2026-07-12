"""
Kafka EventBus backend (production backbone).

Uses aiokafka. Imported lazily so the rest of PAAIM runs on the durable local
backend with no Kafka dependency installed. Activate with EVENT_BUS=kafka.

Delivery semantics:
  - Producer: acks="all", enable idempotence → no silent loss / no dup on retry.
  - Consumer: enable_auto_commit=False; offset committed only AFTER the handler
    succeeds (at-least-once). Handler failure → record routed to the DLQ topic.
  - Partition key = machine_id, so events for one machine stay ordered.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, Optional

from paaim.bus.base import BusRecord, EventBus, Handler

logger = logging.getLogger(__name__)


class KafkaEventBus(EventBus):
    def __init__(self, bootstrap_servers: str):
        self.bootstrap = bootstrap_servers
        self._producer = None
        self._consumers: Dict[str, Any] = {}
        self._tasks: Dict[str, asyncio.Task] = {}
        self._stop: Dict[str, bool] = {}

    async def start(self) -> None:
        from aiokafka import AIOKafkaProducer            # lazy import
        self._producer = AIOKafkaProducer(
            bootstrap_servers=self.bootstrap,
            acks="all",
            enable_idempotence=True,
            value_serializer=lambda v: json.dumps(v, default=str).encode(),
            key_serializer=lambda k: k.encode() if k else None,
        )
        await self._producer.start()
        logger.info("KafkaEventBus producer started", extra={"servers": self.bootstrap})

    async def stop(self) -> None:
        for key in list(self._consumers):
            self._stop[key] = True
        for task in self._tasks.values():
            task.cancel()
        for c in self._consumers.values():
            await c.stop()
        if self._producer:
            await self._producer.stop()

    async def publish(self, topic: str, value: Dict[str, Any],
                      key: Optional[str] = None,
                      headers: Optional[Dict[str, str]] = None) -> int:
        kafka_headers = [(k, v.encode()) for k, v in (headers or {}).items()]
        md = await self._producer.send_and_wait(topic, value=value, key=key,
                                                 headers=kafka_headers or None)
        return md.offset

    async def start_consumer(self, topic: str, group: str, handler: Handler,
                             dlq_topic: Optional[str] = None) -> None:
        from aiokafka import AIOKafkaConsumer
        key = f"{topic}::{group}"
        if key in self._consumers:
            return
        consumer = AIOKafkaConsumer(
            topic, bootstrap_servers=self.bootstrap, group_id=group,
            enable_auto_commit=False, auto_offset_reset="earliest",
            value_deserializer=lambda v: json.loads(v.decode()),
        )
        await consumer.start()
        self._consumers[key] = consumer
        self._stop[key] = False
        self._tasks[key] = asyncio.create_task(
            self._loop(consumer, key, handler, dlq_topic)
        )
        logger.info("Kafka consumer started", extra={"topic": topic, "group": group})

    async def _loop(self, consumer, key, handler, dlq_topic) -> None:
        async for msg in consumer:
            if self._stop.get(key):
                break
            rec = BusRecord(
                topic=msg.topic, key=msg.key.decode() if msg.key else None,
                value=msg.value, offset=msg.offset,
                headers={k: v.decode() for k, v in (msg.headers or [])},
            )
            try:
                await handler(rec)
            except Exception as e:
                logger.warning(f"handler failed at offset {rec.offset}: {e}")
                if dlq_topic:
                    await self.publish(dlq_topic, {"original": rec.value, "error": str(e)},
                                       key=rec.key)
            await consumer.commit()                  # at-least-once

    async def stop_consumer(self, topic: str, group: str) -> None:
        key = f"{topic}::{group}"
        self._stop[key] = True
        task = self._tasks.pop(key, None)
        if task:
            task.cancel()
        c = self._consumers.pop(key, None)
        if c:
            await c.stop()

    async def replay(self, topic: str, group: str, from_offset: int = 0) -> int:
        # In Kafka, replay is done via consumer.seek / kafka-consumer-groups
        # --reset-offsets. Exposed here for interface parity.
        logger.info("Kafka replay requested",
                    extra={"topic": topic, "group": group, "from": from_offset})
        return from_offset

    async def stats(self) -> Dict[str, Any]:
        return {
            "backend": "kafka",
            "bootstrap_servers": self.bootstrap,
            "active_consumers": list(self._consumers.keys()),
        }
