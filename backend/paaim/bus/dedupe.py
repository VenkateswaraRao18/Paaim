"""
One fault, one incident — regardless of how many sources reported it.

Watchers and pollers each cool down on their own, which stops a single feed
re-firing while a fault persists. It does nothing across feeds. A plant that
runs a live stream *and* a historian carrying the same tag — an ordinary
arrangement, not an edge case — reported one physical fault twice:

    L3 | robot_arm_01 | vibration = 4.32   via rest_poll
    L3 | robot_arm_01 | vibration = 4.37   via factory-stream

Two incidents, two approvals, two triage entries, two Gemini chains, for one
bearing. Operators lose trust in a queue that double-counts, and the LLM bill
doubles for nothing.

The real identity of an incident is the physical thing that is wrong —
(factory, machine, signal) — not the wire it arrived on. So the guard lives here,
after the bus and before orchestration, where every source converges.

Deliberately in-memory: this is a short window (minutes) of live state, and a
restart re-detecting an ongoing fault is the safe failure — it costs one extra
decision, whereas persisting it risks suppressing a real incident after a crash.
"""

from __future__ import annotations

import logging
import time
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class IncidentDeduper:
    """Suppresses repeats of the same physical fault inside a time window."""

    def __init__(self, window_seconds: float = 120.0):
        self.window = window_seconds
        # (factory, machine, signal) -> (last_seen_epoch, source, suppressed_count)
        self._seen: Dict[Tuple[str, str, str], Tuple[float, str, int]] = {}

    @staticmethod
    def _key(factory_id: str, machine_id: Optional[str], signal: Optional[str]):
        return (factory_id or "", machine_id or "unknown", signal or "unknown")

    def check(
        self, factory_id: str, machine_id: Optional[str], signal: Optional[str],
        source: str = "unknown", raw_field: Optional[str] = None,
    ) -> Tuple[bool, Optional[str]]:
        """
        Return (is_duplicate, why).

        Matched two ways, because one fault can arrive wearing two names:

          canonical  (machine, signal)     — two feeds agreeing on what it is
          physical   (machine, raw_field)  — the same instrument, whatever each
                                             mapping happened to call it

        The second key exists because mapping is AI-assisted and not
        deterministic: the same tag TT_101 on robot_arm_01 was resolved to
        `process_temperature` for one source and `temperature` for another, so a
        canonical-only key saw two distinct faults and raised two incidents for
        one hot bearing. The instrument is the ground truth; the canonical name
        is an interpretation of it.

        First report wins — it is already queued with its evidence, and a second
        copy tells the operator nothing new.
        """
        now = time.time()
        keys = [self._key(factory_id, machine_id, signal)]
        if raw_field:
            keys.append(self._key(factory_id, machine_id, f"tag:{raw_field}"))

        for key in keys:
            prev = self._seen.get(key)
            if prev is None:
                continue
            last_seen, first_source, count = prev
            age = now - last_seen
            if age < self.window:
                for k in keys:
                    ls, fs, c = self._seen.get(k, (now, source, 0))
                    self._seen[k] = (ls, fs, c + 1)
                same_tag = key[2].startswith("tag:")
                return True, (
                    f"{machine_id}::{signal} was already raised {age:.0f}s ago"
                    + (f" by '{first_source}'" if first_source != source else "")
                    + (f" — same instrument ({raw_field}), reported again by '{source}'"
                       if same_tag else
                       f" — same fault, reported again by '{source}'")
                )

        for key in keys:
            self._seen[key] = (now, source, 0)
        return False, None

    def stats(self) -> dict:
        now = time.time()
        live = {k: v for k, v in self._seen.items() if now - v[0] < self.window}
        return {
            "window_seconds": self.window,
            "tracked": len(live),
            "suppressed_total": sum(v[2] for v in self._seen.values()),
            "active": [
                {
                    "machine_id": k[1], "signal": k[2], "first_source": v[1],
                    "age_seconds": round(now - v[0], 1), "suppressed": v[2],
                }
                for k, v in live.items()
            ],
        }

    def prune(self) -> None:
        now = time.time()
        for k in [k for k, v in self._seen.items() if now - v[0] > self.window * 5]:
            del self._seen[k]


_deduper: Optional[IncidentDeduper] = None


def get_deduper() -> IncidentDeduper:
    global _deduper
    if _deduper is None:
        from paaim.config import settings
        _deduper = IncidentDeduper(getattr(settings, "INCIDENT_DEDUPE_WINDOW_S", 120.0))
    return _deduper
