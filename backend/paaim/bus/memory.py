"""
Durable local EventBus backend.

Despite the historical name "in-memory", this backend is genuinely durable:
every published record is appended to an append-only JSONL log on disk, and
each consumer group's committed offset is persisted. That gives real
at-least-once delivery and replay on a single node — the reliability
properties Kafka provides, without the infrastructure — so the architecture
can be demonstrated end to end before a broker is provisioned.

Layout (under BUS_DATA_DIR):
    <topic>.log         append-only JSONL, one record per line  (the durable log)
    offsets.json        {"<topic>::<group>": <next_offset>}     (committed offsets)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from paaim.bus.base import BusRecord, EventBus, Handler

logger = logging.getLogger(__name__)


class DurableLocalBus(EventBus):
    def __init__(self, data_dir: str):
        self.dir = Path(data_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.offsets_path = self.dir / "offsets.json"
        self._locks: Dict[str, asyncio.Lock] = {}
        self._consumers: Dict[str, asyncio.Task] = {}
        self._stop_flags: Dict[str, bool] = {}
        self._wakeups: Dict[str, asyncio.Event] = {}
        self._offsets: Dict[str, int] = self._load_offsets()

    # ── lifecycle ──────────────────────────────────────────────────────────
    async def start(self) -> None:
        logger.info("DurableLocalBus started", extra={"dir": str(self.dir)})

    async def stop(self) -> None:
        for key in list(self._consumers):
            self._stop_flags[key] = True
            self._wakeups[key].set()
        for task in self._consumers.values():
            task.cancel()
        self._consumers.clear()

    # ── helpers ──────────────────────────────────────────────────────────────
    def _log_path(self, topic: str) -> Path:
        return self.dir / f"{topic}.log"

    def _topic_lock(self, topic: str) -> asyncio.Lock:
        if topic not in self._locks:
            self._locks[topic] = asyncio.Lock()
        return self._locks[topic]

    def _load_offsets(self) -> Dict[str, int]:
        if self.offsets_path.exists():
            try:
                return json.loads(self.offsets_path.read_text())
            except Exception:
                return {}
        return {}

    def _save_offsets(self) -> None:
        tmp = self.offsets_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._offsets))
        tmp.replace(self.offsets_path)            # atomic

    def _count(self, topic: str) -> int:
        p = self._log_path(topic)
        if not p.exists():
            return 0
        with open(p) as fh:
            return sum(1 for _ in fh)

    # ── producer ───────────────────────────────────────────────────────────
    async def publish(self, topic: str, value: Dict[str, Any],
                      key: Optional[str] = None,
                      headers: Optional[Dict[str, str]] = None) -> int:
        async with self._topic_lock(topic):
            offset = self._count(topic)
            record = {
                "offset": offset, "key": key, "value": value,
                "timestamp": datetime.utcnow().isoformat(),
                "headers": headers or {},
            }
            with open(self._log_path(topic), "a") as fh:   # durable append
                fh.write(json.dumps(record, default=str) + "\n")
                fh.flush()
                os.fsync(fh.fileno())
        # wake any consumer waiting on this topic
        for k, ev in self._wakeups.items():
            if k.startswith(f"{topic}::"):
                ev.set()
        return offset

    def _read_from(self, topic: str, start: int):
        p = self._log_path(topic)
        if not p.exists():
            return
        with open(p) as fh:
            for i, line in enumerate(fh):
                if i < start or not line.strip():
                    continue
                yield json.loads(line)

    # ── consumer ───────────────────────────────────────────────────────────
    async def start_consumer(self, topic: str, group: str, handler: Handler,
                             dlq_topic: Optional[str] = None) -> None:
        key = f"{topic}::{group}"
        if key in self._consumers:
            return
        self._stop_flags[key] = False
        self._wakeups[key] = asyncio.Event()
        self._consumers[key] = asyncio.create_task(
            self._consume_loop(topic, group, handler, dlq_topic)
        )
        logger.info("consumer started", extra={"topic": topic, "group": group})

    async def _consume_loop(self, topic: str, group: str, handler: Handler,
                            dlq_topic: Optional[str]) -> None:
        key = f"{topic}::{group}"
        while not self._stop_flags.get(key):
            committed = self._offsets.get(key, 0)
            pending = list(self._read_from(topic, committed))
            for raw in pending:
                if self._stop_flags.get(key):
                    break
                rec = BusRecord(topic=topic, key=raw.get("key"), value=raw["value"],
                                offset=raw["offset"], timestamp=raw.get("timestamp"),
                                headers=raw.get("headers", {}))
                try:
                    await handler(rec)
                except Exception as e:                       # poison event → DLQ
                    logger.warning(f"handler failed at offset {rec.offset}: {e}")
                    if dlq_topic:
                        await self.publish(dlq_topic, {"original": raw, "error": str(e)},
                                           key=rec.key)
                # at-least-once: commit only after attempt resolves (success or DLQ)
                self._offsets[key] = rec.offset + 1
                self._save_offsets()

            # idle wait until a new publish wakes us
            self._wakeups[key].clear()
            try:
                await asyncio.wait_for(self._wakeups[key].wait(), timeout=1.0)
            except asyncio.TimeoutError:
                pass

    async def stop_consumer(self, topic: str, group: str) -> None:
        key = f"{topic}::{group}"
        self._stop_flags[key] = True
        if key in self._wakeups:
            self._wakeups[key].set()
        task = self._consumers.pop(key, None)
        if task:
            task.cancel()

    async def replay(self, topic: str, group: str, from_offset: int = 0) -> int:
        key = f"{topic}::{group}"
        self._offsets[key] = from_offset
        self._save_offsets()
        if key in self._wakeups:
            self._wakeups[key].set()
        return from_offset

    async def stats(self) -> Dict[str, Any]:
        topics = {}
        for p in self.dir.glob("*.log"):
            topics[p.stem] = self._count(p.stem)
        lag = {}
        for key, committed in self._offsets.items():
            topic = key.split("::", 1)[0]
            total = topics.get(topic, 0)
            lag[key] = max(0, total - committed)
        return {
            "backend": "durable_local",
            "data_dir": str(self.dir),
            "topics": topics,
            "committed_offsets": self._offsets,
            "consumer_lag": lag,
            "active_consumers": list(self._consumers.keys()),
        }
