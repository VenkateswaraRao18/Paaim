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
from collections import deque
from datetime import datetime
from typing import Optional

import httpx

from paaim.bus.factory import get_event_bus
from paaim.stream_bridge.judge import judge
from paaim.config import settings

logger = logging.getLogger(__name__)

_SEVERITY = {"unknown": -1, "normal": 0, "warning": 1, "critical": 2}


class StreamAgent:
    def __init__(self, machine_id: str, signal: str, *, factory_id: str,
                 source_id: str, source_url: str,
                 trigger_level: str = "critical", cooldown_seconds: float = 45.0):
        self.machine_id = machine_id
        self.signal = signal          # the plant's raw PLC tag, e.g. "PT_HYD_01"
        # All three required, none defaulted. A watcher that infers its own
        # origin reads the wrong mapping and translates its tag with the wrong
        # plant's vocabulary — and `factory_id` defaulting to "factory_001"
        # meant every tenant's readings were filed under the first one. The
        # bridge knows which factory and source it is building for; it must say.
        self.source_id = source_id
        self.factory_id = factory_id
        self.trigger_level = trigger_level
        self.cooldown = cooldown_seconds
        self.source_url = source_url.rstrip("/")
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

        self.last_reason: str = ""
        self.last_raw_value: Optional[float] = None   # as the source sent it
        # What this watcher judges against. The learned baseline is this
        # machine's own history (SPC); declared limits are whatever the source
        # publishes for the instrument. Loaded once on start, refreshed as the
        # profile is relearned.
        self._baseline: Optional[dict] = None
        self._declared_limits: Optional[dict] = None
        self._direction: Optional[bool] = None   # higher_is_worse, from the vocabulary
        # The mapping's unit conversion. Judging happens in canonical units:
        # the baseline is learned from canonical readings, so comparing a raw
        # °C reading against a baseline in K would be catastrophic and quiet.
        # Everything — reading, declared limits, buffer — is carried through
        # this one function first.
        self._transform: str = "identity"
        self._canonical_unit: str = ""

        self._task: Optional[asyncio.Task] = None
        self._stop = False
        self._in_breach = False
        self._last_fire = 0.0
        # Rolling window of what this agent actually observed. The feed keeps no
        # history, and only the breach itself is persisted as an event — without
        # this buffer the pre-fault ramp is lost and the evidence timeline has
        # nothing to plot. ~2 min at a 2s tick.
        self._buffer: deque = deque(maxlen=60)

    @property
    def key(self) -> str:
        return f"{self.machine_id}::{self.signal}"

    # ── lifecycle ────────────────────────────────────────────────────────────
    async def start(self) -> None:
        self._stop = False
        await self.refresh_thresholds()
        self._task = asyncio.create_task(self._run())

    async def refresh_thresholds(self) -> None:
        """
        Load what this watcher judges against: the machine's learned normal, and
        any limits the source declares for the instrument. Best-effort — a
        watcher with neither still runs, it just reports `unknown` instead of
        pretending everything is fine.
        """
        # 1 — the canonical signal this tag becomes, so the baseline lookup (which
        #     is keyed by canonical signal) matches — and the conversion into that
        #     signal's unit, which everything below is then measured in.
        canonical = None
        try:
            from paaim.normalization.mapping import get_mapping_store
            mapping = get_mapping_store(self.factory_id).get(self.source_id)
            fm = (mapping.fields or {}).get(self.signal) if mapping else None
            canonical = fm.signal if fm else None
            if fm:
                self._transform = fm.transform or "identity"
                self._canonical_unit = fm.unit or ""
        except Exception:
            pass

        # Which direction is a fault for this signal — the plant's vocabulary
        # owns that, so it holds even for a feed that sends bare numbers.
        if canonical:
            try:
                from paaim.normalization.vocabulary import direction_for
                self._direction = direction_for(canonical, self.factory_id)
            except Exception:
                pass

        # 2 — the machine's own learned normal (SPC mean ± σ)
        if canonical:
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
                    self._baseline = baseline_for(fk.profile, self.machine_id, canonical)
            except Exception as e:
                logger.debug(f"{self.key}: no learned baseline ({e})")

        # 3 — limits the source publishes for this instrument, if any.
        #     Carried through the same conversion as the readings: a limit of
        #     90 °C and a reading of 363 K are the same fact, and comparing them
        #     as they stand would never fire.
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{self.source_url}/signals")
            for s in resp.json().get("signals", []):
                if s.get("machine_id") == self.machine_id and s.get("signal") == self.signal:
                    if s.get("warn") is not None or s.get("critical") is not None:
                        self._declared_limits = {
                            "warn": self._to_canonical_value(s.get("warn")),
                            "critical": self._to_canonical_value(s.get("critical")),
                            "higher_is_worse": s.get("higher_is_worse", True),
                        }
                    if self._direction is None:
                        self._direction = s.get("higher_is_worse")
                    break
        except Exception:
            pass

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

    def _to_canonical_value(self, value):
        """Carry one number from the source's unit into the signal's."""
        if value is None:
            return None
        try:
            from paaim.normalization.schema import TRANSFORMS
            return TRANSFORMS.get(self._transform, TRANSFORMS["identity"])(float(value))
        except (TypeError, ValueError):
            return None

    async def _on_reading(self, r: dict) -> None:
        self.readings_received += 1
        self.last_raw_value = r.get("value")
        # Judge, buffer and report in canonical units — the same space the
        # learned baseline lives in, and the space the agents reason in.
        self.last_value = self._to_canonical_value(r.get("value"))
        self.last_unit = self._canonical_unit or r.get("unit", "")
        self.label = r.get("label", self.label)

        # Judge the reading with PAAIM's own knowledge of this machine rather
        # than trusting the feed. `r.get("status", "normal")` looked harmless and
        # meant that any source which sends plain values — i.e. every real
        # historian and SCADA — reported "normal" forever and never raised a
        # thing. Falling back to the source's verdict only if it sent one.
        self.last_status, self.last_reason = judge(
            value=self.last_value,
            baseline=self._baseline,
            declared=self._declared_limits,
            source_status=r.get("status"),
            # Direction is the signal's own property, from the plant's
            # vocabulary. Only fall back to the instrument's declared limits —
            # a source that sends bare values knows nothing about direction.
            higher_is_worse=self._direction,
        )
        self._buffer.append({
            "t": r.get("timestamp") or datetime.utcnow().isoformat(),
            "v": self.last_value,
            "s": self.last_status,
        })

        sev = _SEVERITY.get(self.last_status, 0)
        threshold = _SEVERITY.get(self.trigger_level, 2)
        breaching = sev >= threshold

        # rising edge + cooldown → raise one event per fault episode
        if breaching and not self._in_breach and (time.time() - self._last_fire) > self.cooldown:
            await self._raise_event(r)
            self._last_fire = time.time()
        self._in_breach = breaching

    def _to_canonical(self, value: float):
        """
        Translate this plant's PLC tag into the canonical vocabulary.

        The feed publishes raw site tags ("PT_HYD_01"), and every plant names
        its instruments differently — so the translation cannot live here. It
        comes from the mapping the operator confirmed for this source on the
        Data Sources screen, which is the same path a REST/SCADA source uses.
        Returns None when the source has not been mapped yet: the reading is
        then dropped on purpose rather than published under a raw tag no agent
        watches (which would look like a silent failure).
        """
        from paaim.normalization.mapping import get_mapping_store
        from paaim.normalization.normalizer import apply

        mapping = get_mapping_store(self.factory_id).get(self.source_id)
        if not mapping:
            return None

        # The feed identifies the machine per-subscription, so hand it under
        # whichever field this mapping was told to read it from. Assuming
        # "machine_id" silently produced machine="unknown" on every incident
        # whenever an operator named that field something else.
        payload = {self.signal: value}
        if mapping.machine_id_strategy == "field":
            payload[mapping.machine_id_value] = self.machine_id
        else:
            payload["machine_id"] = self.machine_id

        readings = apply(mapping, payload, factory_id=self.factory_id)
        return readings[0] if readings else None

    async def _raise_event(self, r: dict) -> None:
        value = float(r.get("value", 0.0))
        canonical = self._to_canonical(value)
        if canonical is None:
            self.error = (
                f"'{self.signal}' is not mapped yet — connect this source on "
                f"Data Sources (source '{self.source_id}') so PAAIM knows what it means."
            )
            logger.info(f"StreamAgent {self.key} breached but source is unmapped — no event raised")
            return

        confidence = 0.97 if self.last_status == "critical" else 0.85
        bus = get_event_bus()
        await bus.publish(
            settings.BUS_EVENTS_TOPIC,
            {
                "event_type": canonical.event_type,
                "source_agent": f"stream::{self.signal}",
                "factory_id": self.factory_id,
                "machine_id": self.machine_id,
                "signal_value": canonical.value,
                "signal_name": canonical.signal_name,
                "confidence": confidence,
                "timestamp": datetime.utcnow().isoformat(),
                "context": {
                    "source": "factory-stream",
                    "source_id": self.source_id,
                    "raw_field": self.signal,      # the PLC tag it arrived as
                    "live_status": self.last_status,
                    "unit": canonical.unit or self.last_unit,
                    "label": self.label,
                    # the readings this agent observed leading into the breach,
                    # so the evidence timeline can plot the real ramp
                    "pre_fault_series": list(self._buffer),
                },
            },
            key=self.machine_id,
        )
        self.events_raised += 1
        self.last_event_at = datetime.utcnow().isoformat()
        self.error = None
        logger.info(
            f"StreamAgent {self.key} raised event: {self.signal} -> "
            f"{canonical.signal_name} ({self.last_status} @ {value})"
        )

    # ── status snapshot ──────────────────────────────────────────────────────
    def status(self, include_series: bool = False) -> dict:
        d = {
            "key": self.key,
            "machine_id": self.machine_id,
            "signal": self.signal,
            "source_id": self.source_id,
            "label": self.label,
            "connected": self.connected,
            "trigger_level": self.trigger_level,
            "readings_received": self.readings_received,
            "last_value": self.last_value,
            "last_status": self.last_status,
            "last_reason": self.last_reason,
            "judged_by": ("learned baseline" if self._baseline
                          else "declared limits" if self._declared_limits
                          else "source status"),
            "unit": self.last_unit,
            # The reading as the source sent it. Shown alongside the canonical
            # value so an operator whose HMI reads 64 °C is not left wondering
            # why PAAIM says 337 — the conversion should be visible, not a
            # discrepancy they have to discover.
            "raw_value": self.last_raw_value,
            "transform": self._transform,
            "events_raised": self.events_raised,
            "last_event_at": self.last_event_at,
            "error": self.error,
        }
        if include_series:
            # What this watcher observed and judged — not what the feed claimed.
            # Opt-in: ~40 points per watcher is real payload once a plant watches
            # hundreds of tags.
            d["series"] = list(self._buffer)[-40:]
        return d
