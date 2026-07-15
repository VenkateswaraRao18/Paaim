"""
Polling runtime for REST sources.

A source could be connected, tested, discovered and mapped — and then never
ingest a single reading, because nothing existed to actually call it. It sat in
the list looking healthy forever. Most plants integrate through a historian
(PI, Ignition, Wonderware) over HTTP, so that silent dead end was the likeliest
path a real customer would take.

A poller is a watcher for sources that must be asked rather than listened to.
It has the same obligations, and they matter more than the fetching:

  · **Judge, don't relay.** Publishing every reading would run the whole LLM
    pipeline on every poll of every tag — thousands of decisions an hour and a
    ruinous bill. Only a breach is an event.
  · **Rising edge + cooldown.** A fault that persists is one incident, not one
    per poll.
  · **Keep the run-up.** The pipeline's evidence timeline needs the readings
    before the breach, and a poll response contains only 'now'.

Shares `judge` with the SSE watcher, so a plant gets identical verdicts whether
its data is pushed, streamed, or polled.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import httpx

from paaim.config import settings
from paaim.stream_bridge.judge import judge

logger = logging.getLogger(__name__)

_SEVERITY = {"unknown": -1, "normal": 0, "warning": 1, "critical": 2}


class _SignalState:
    """Per (machine, signal) breach tracking — one incident per episode."""

    def __init__(self) -> None:
        self.in_breach = False
        self.last_fire = 0.0
        self.buffer: deque = deque(maxlen=60)
        self.last_value: Optional[float] = None
        self.last_status = "unknown"
        self.last_reason = ""
        self.events_raised = 0


class PollAgent:
    """Polls one REST source, normalizes its payload, and raises real breaches."""

    def __init__(self, source_id: str, *, factory_id: str,
                 trigger_level: Optional[str] = None, cooldown_seconds: float = 45.0):
        self.source_id = source_id
        self.trigger_level = trigger_level or settings.STREAM_TRIGGER_LEVEL
        self.cooldown = cooldown_seconds
        # Required. Defaulting to "factory_001" filed every tenant's readings
        # under whichever factory happened to be seeded first.
        self.factory_id = factory_id

        self.connected = False
        self.polls = 0
        self.readings_seen = 0
        self.events_raised = 0
        self.error: Optional[str] = None
        self.last_poll_at: Optional[str] = None

        self._state: Dict[str, _SignalState] = {}
        self._baselines: Dict[str, Optional[dict]] = {}
        self._task: Optional[asyncio.Task] = None
        self._stop = False

    # ── lifecycle ────────────────────────────────────────────────────────────
    async def start(self) -> None:
        self._stop = False
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        self._stop = True
        if self._task:
            self._task.cancel()
        self.connected = False

    def status(self) -> dict:
        return {
            "source_id": self.source_id,
            "kind": "poller",
            "connected": self.connected,
            "polls": self.polls,
            "readings_seen": self.readings_seen,
            "events_raised": self.events_raised,
            "trigger_level": self.trigger_level,
            "last_poll_at": self.last_poll_at,
            "error": self.error,
            "signals": [
                {
                    "key": k, "last_value": s.last_value, "last_status": s.last_status,
                    "last_reason": s.last_reason, "events_raised": s.events_raised,
                }
                for k, s in self._state.items()
            ],
        }

    # ── the loop ─────────────────────────────────────────────────────────────
    async def _run(self) -> None:
        from paaim.normalization.mapping import get_mapping_store

        while not self._stop:
            mapping = get_mapping_store(self.factory_id).get(self.source_id)
            conn = mapping.connection if mapping else None
            if not mapping or not conn or not conn.endpoint:
                self.error = f"'{self.source_id}' has no confirmed mapping with an endpoint"
                self.connected = False
                await asyncio.sleep(10)
                continue

            interval = max(1, int(conn.poll_interval_seconds or 30))
            try:
                await self._poll_once(mapping, conn)
                self.connected = True
                self.error = None
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.connected = False
                self.error = str(e)
                logger.warning(f"Poller {self.source_id}: {e}")
            await asyncio.sleep(interval)

    async def _poll_once(self, mapping, conn) -> None:
        from paaim.normalization.normalizer import apply

        headers = {}
        cfg = conn.auth_config or {}
        if conn.auth_type == "bearer" and cfg.get("token"):
            headers["Authorization"] = f"Bearer {cfg['token']}"
        elif conn.auth_type == "api_key" and cfg.get("key"):
            headers[cfg.get("header", "X-API-Key")] = cfg["key"]

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(conn.endpoint, headers=headers)
            resp.raise_for_status()
            body = resp.json()

        self.polls += 1
        self.last_poll_at = datetime.utcnow().isoformat()

        # Historians answer in many shapes — flat, a list, or rows wrapped in an
        # envelope. Unwrap the same way discovery did, so what onboarding sampled
        # is what runtime actually reads.
        from paaim.sources.connectors import pivot_long_to_wide, unwrap_payloads

        for payload in pivot_long_to_wide(unwrap_payloads(body)):
            for reading in apply(mapping, payload, factory_id=self.factory_id):
                self.readings_seen += 1
                await self._on_reading(reading)

    async def _on_reading(self, reading) -> None:
        key = f"{reading.machine_id}::{reading.signal_name}"
        st = self._state.setdefault(key, _SignalState())
        st.last_value = reading.value

        baseline = await self._baseline_for(reading.machine_id, reading.signal_name)
        direction = None
        try:
            from paaim.normalization.vocabulary import direction_for
            direction = direction_for(reading.signal_name, self.factory_id)
        except Exception:
            pass

        st.last_status, st.last_reason = judge(
            value=reading.value, baseline=baseline, higher_is_worse=direction,
        )
        st.buffer.append({"t": reading.timestamp, "v": reading.value, "s": st.last_status})

        breaching = _SEVERITY.get(st.last_status, 0) >= _SEVERITY.get(self.trigger_level, 2)
        if breaching and not st.in_breach and (time.time() - st.last_fire) > self.cooldown:
            await self._raise(reading, st)
            st.last_fire = time.time()
        st.in_breach = breaching

    async def _baseline_for(self, machine_id: str, signal: str) -> Optional[dict]:
        """The machine's learned normal. Cached — a poll must not hit the DB per reading."""
        key = f"{machine_id}::{signal}"
        if key in self._baselines:
            return self._baselines[key]
        result = None
        try:
            from sqlalchemy import select
            from paaim.models import AsyncSessionLocal, FactoryKnowledgeModel
            from paaim.knowledge_model.learning import baseline_for
            async with AsyncSessionLocal() as db:
                fk = (await db.execute(
                    select(FactoryKnowledgeModel).where(
                        FactoryKnowledgeModel.factory_id == self.factory_id
                    ).limit(1)
                )).scalar_one_or_none()
            if fk and fk.profile:
                result = baseline_for(fk.profile, machine_id, signal)
        except Exception as e:
            logger.debug(f"poller baseline lookup failed: {e}")
        self._baselines[key] = result
        return result

    async def _raise(self, reading, st: _SignalState) -> None:
        from paaim.bus.factory import get_event_bus

        event = reading.to_event(confidence=0.97 if st.last_status == "critical" else 0.85)
        event["source_agent"] = f"poll::{self.source_id}"
        event["context"] = {
            **(event.get("context") or {}),
            "source": "rest_poll",
            "source_id": self.source_id,
            "live_status": st.last_status,
            "judged": st.last_reason,
            # the run-up, so the incident's evidence timeline has something real
            "pre_fault_series": list(st.buffer),
        }
        await get_event_bus().publish(settings.BUS_EVENTS_TOPIC, event, key=reading.machine_id)
        st.events_raised += 1
        self.events_raised += 1
        logger.info(
            f"Poller {self.source_id} raised {reading.machine_id}::{reading.signal_name} "
            f"= {reading.value} ({st.last_status}) — {st.last_reason}"
        )


class PollerRegistry:
    """
    One poller per (factory, polled source), matching the confirmed mappings.

    Keyed by tenant as well as source: "historian" is what half of all plants
    call their historian, and a source-only key meant the second factory to
    connect one found the first's poller already running and reused it —
    polling one plant's endpoint and filing the readings under the other.
    """

    def __init__(self) -> None:
        self._pollers: Dict[Tuple[str, str], PollAgent] = {}

    async def sync(self, factory_id: str) -> dict:
        """Start pollers for this factory's polled sources; retire the rest."""
        from paaim.normalization.mapping import get_mapping_store

        wanted = {
            (factory_id, m.source_id) for m in get_mapping_store(factory_id).list()
            if m.confirmed and m.connection and m.connection.type == "rest_poll"
            and m.connection.endpoint and m.fields
        }
        mine = {k for k in self._pollers if k[0] == factory_id}
        started, stopped = [], []
        for key in wanted - mine:
            p = PollAgent(key[1], factory_id=factory_id)
            await p.start()
            self._pollers[key] = p
            started.append(key[1])
        for key in mine - wanted:
            await self._pollers.pop(key).stop()
            stopped.append(key[1])
        if started or stopped:
            logger.info(f"[{factory_id}] pollers synced: started={started} stopped={stopped}")
        return {"started": started, "stopped": stopped,
                "running": [k[1] for k in self._pollers if k[0] == factory_id]}

    def list_status(self, factory_id: str) -> List[dict]:
        """One factory's pollers. Required — an unfiltered list leaks tenants."""
        return [p.status() for k, p in self._pollers.items() if k[0] == factory_id]

    async def stop_all(self) -> None:
        for p in list(self._pollers.values()):
            await p.stop()
        self._pollers.clear()


_registry: Optional[PollerRegistry] = None


def get_poller_registry() -> PollerRegistry:
    global _registry
    if _registry is None:
        _registry = PollerRegistry()
    return _registry
