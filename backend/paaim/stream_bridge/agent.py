"""
StreamAgent — subscribes to one live signal and raises events on breach.

Flow:
    factory-stream SSE  →  StreamAgent (applies rule)  →  Event Bus  →  pipeline  →  decision

The factory-stream feed already classifies each reading (normal/warning/critical),
so the agent's rule is simply "trigger on `trigger_level` or worse". To avoid
flooding the pipeline while a fault persists, it only fires on the *rising edge*
(normal → breach) and then respects a cooldown.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime
from typing import Optional

import httpx

from paaim.bus.factory import get_event_bus
from paaim.config import settings

logger = logging.getLogger(__name__)

# Map a stream signal kind → how it enters the PAAIM pipeline.
SIGNAL_MAP = {
    "temperature": ("maintenance", "heat_dissipation_loss"),
    "vibration":   ("maintenance", "vibration_anomaly"),
    "pressure":    ("maintenance", "coolant_pressure"),
    "energy":      ("energy",      "power_envelope_breach"),
}

_SEVERITY = {"normal": 0, "warning": 1, "critical": 2}


class StreamAgent:
    def __init__(self, machine_id: str, signal: str, *,
                 trigger_level: str = "critical", cooldown_seconds: float = 45.0,
                 source_url: Optional[str] = None):
        self.machine_id = machine_id
        self.signal = signal
        self.trigger_level = trigger_level
        self.cooldown = cooldown_seconds
        self.source_url = (source_url or settings.STREAM_SOURCE_URL).rstrip("/")
        self.stream_url = f"{self.source_url}/stream/{machine_id}/{signal}"

        # live status (surfaced by the API)
        self.connected = False
        self.readings_received = 0
        self.last_value: Optional[float] = None
        self.last_status: str = "normal"
        self.last_unit: str = ""
        self.label: str = f"{machine_id} {signal}"
        self.events_raised = 0
        self.last_event_at: Optional[str] = None
        self.error: Optional[str] = None

        self._task: Optional[asyncio.Task] = None
        self._stop = False
        self._in_breach = False
        self._last_fire = 0.0

    @property
    def key(self) -> str:
        return f"{self.machine_id}::{self.signal}"

    # ── lifecycle ────────────────────────────────────────────────────────────
    async def start(self) -> None:
        self._stop = False
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        self._stop = True
        if self._task:
            self._task.cancel()
        self.connected = False

    # ── main loop ────────────────────────────────────────────────────────────
    async def _run(self) -> None:
        while not self._stop:
            try:
                async with httpx.AsyncClient(timeout=None) as client:
                    async with client.stream("GET", self.stream_url) as resp:
                        self.connected = True
                        self.error = None
                        async for line in resp.aiter_lines():
                            if self._stop:
                                break
                            if not line.startswith("data:"):
                                continue
                            await self._on_reading(json.loads(line[5:].strip()))
            except asyncio.CancelledError:
                break
            except Exception as e:                       # feed down → retry (reliability)
                self.connected = False
                self.error = str(e)
                logger.warning(f"StreamAgent {self.key} reconnecting: {e}")
                await asyncio.sleep(3)

    async def _on_reading(self, r: dict) -> None:
        self.readings_received += 1
        self.last_value = r.get("value")
        self.last_status = r.get("status", "normal")
        self.last_unit = r.get("unit", "")
        self.label = r.get("label", self.label)

        sev = _SEVERITY.get(self.last_status, 0)
        threshold = _SEVERITY.get(self.trigger_level, 2)
        breaching = sev >= threshold

        # rising edge + cooldown → raise one event per fault episode
        if breaching and not self._in_breach and (time.time() - self._last_fire) > self.cooldown:
            await self._raise_event(r)
            self._last_fire = time.time()
        self._in_breach = breaching

    async def _raise_event(self, r: dict) -> None:
        event_type, signal_name = SIGNAL_MAP.get(self.signal, ("maintenance", self.signal))
        confidence = 0.97 if self.last_status == "critical" else 0.85
        bus = get_event_bus()
        await bus.publish(
            settings.BUS_EVENTS_TOPIC,
            {
                "event_type": event_type,
                "source_agent": f"stream::{self.signal}",
                "factory_id": settings.FACTORY_ID if hasattr(settings, "FACTORY_ID") else "factory_001",
                "machine_id": self.machine_id,
                "signal_value": float(r.get("value", 0.0)),
                "signal_name": signal_name,
                "confidence": confidence,
                "timestamp": datetime.utcnow().isoformat(),
                "context": {
                    "source": "factory-stream",
                    "live_status": self.last_status,
                    "unit": self.last_unit,
                    "label": self.label,
                },
            },
            key=self.machine_id,
        )
        self.events_raised += 1
        self.last_event_at = datetime.utcnow().isoformat()
        logger.info(f"StreamAgent {self.key} raised event ({self.last_status} @ {r.get('value')})")

    # ── status snapshot ──────────────────────────────────────────────────────
    def status(self) -> dict:
        return {
            "key": self.key,
            "machine_id": self.machine_id,
            "signal": self.signal,
            "label": self.label,
            "connected": self.connected,
            "trigger_level": self.trigger_level,
            "readings_received": self.readings_received,
            "last_value": self.last_value,
            "last_status": self.last_status,
            "unit": self.last_unit,
            "events_raised": self.events_raised,
            "last_event_at": self.last_event_at,
            "error": self.error,
        }
