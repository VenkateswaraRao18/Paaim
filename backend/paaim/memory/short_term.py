"""
Agent Short-Term Memory

Stores recent event + decision history per machine in an in-memory ring buffer.
Each entry has a TTL (default 8 hours = one shift). When agents analyse a new
event, they receive the last N entries for that machine as context so they can
detect patterns: repeated anomalies, escalating values, dismissed signals.

No external infrastructure required — pure Python, thread-safe, zero config.
"""

import threading
from collections import deque
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any


# ── Memory entry ──────────────────────────────────────────────────────────────

class MemoryEntry:
    __slots__ = (
        "timestamp", "machine_id", "factory_id",
        "event_type", "signal_name", "signal_value", "confidence",
        "recommended_action", "risk_level", "decision_status",
        "agent_reasoning",
    )

    def __init__(
        self,
        machine_id: str,
        factory_id: str,
        event_type: str,
        signal_name: str,
        signal_value: float,
        confidence: float,
        recommended_action: Optional[str] = None,
        risk_level: Optional[str] = None,
        decision_status: Optional[str] = None,
        agent_reasoning: Optional[str] = None,
    ):
        self.timestamp = datetime.utcnow()
        self.machine_id = machine_id
        self.factory_id = factory_id
        self.event_type = event_type
        self.signal_name = signal_name
        self.signal_value = signal_value
        self.confidence = confidence
        self.recommended_action = recommended_action
        self.risk_level = risk_level
        self.decision_status = decision_status      # approved / rejected / recommended
        self.agent_reasoning = agent_reasoning

    def is_expired(self, ttl_hours: float) -> bool:
        return (datetime.utcnow() - self.timestamp).total_seconds() > ttl_hours * 3600

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "machine_id": self.machine_id,
            "event_type": self.event_type,
            "signal_name": self.signal_name,
            "signal_value": round(self.signal_value, 3),
            "confidence": round(self.confidence, 2),
            "recommended_action": self.recommended_action,
            "risk_level": self.risk_level,
            "decision_status": self.decision_status,
            "agent_reasoning": self.agent_reasoning,
        }


# ── Pattern detector ──────────────────────────────────────────────────────────

class PatternAnalysis:
    """Derived insights from a sequence of memory entries for one machine."""

    def __init__(self, entries: List[MemoryEntry], signal_name: str):
        same_signal = [e for e in entries if e.signal_name == signal_name]
        all_recent = list(entries)

        self.occurrence_count = len(same_signal)
        self.dismissed_count = sum(1 for e in same_signal if e.decision_status == "rejected")
        self.approved_count = sum(1 for e in same_signal if e.decision_status == "approved")
        self.pending_count = sum(1 for e in same_signal if e.decision_status == "recommended")

        # Value trend for this signal
        values = [e.signal_value for e in same_signal]
        if len(values) >= 2:
            self.value_trend = "escalating" if values[-1] > values[0] else (
                "decreasing" if values[-1] < values[0] else "stable"
            )
            self.value_delta = round(values[-1] - values[0], 3)
        else:
            self.value_trend = "first_occurrence"
            self.value_delta = 0.0

        # Confidence trend
        confs = [e.confidence for e in same_signal]
        self.avg_confidence = round(sum(confs) / len(confs), 2) if confs else 0.0

        # Hours since first occurrence
        if same_signal:
            first = same_signal[0].timestamp
            self.hours_since_first = round(
                (datetime.utcnow() - first).total_seconds() / 3600, 1
            )
        else:
            self.hours_since_first = 0.0

        # Other recent events on this machine
        other_events = [e for e in all_recent if e.signal_name != signal_name]
        self.other_recent_events = [
            f"{e.signal_name} ({e.event_type}, {e.risk_level or '?'})"
            for e in other_events[:3]
        ]

    def to_prompt_text(self, signal_name: str, machine_id: str) -> str:
        if self.occurrence_count == 0:
            return f"AGENT MEMORY: No prior history for '{signal_name}' on {machine_id}."

        lines = [f"=== AGENT MEMORY: {machine_id} ==="]

        lines.append(
            f"Signal '{signal_name}' has occurred {self.occurrence_count}× "
            f"in the last shift (past {self.hours_since_first:.1f}h)."
        )

        if self.occurrence_count > 1:
            lines.append(f"Value trend: {self.value_trend} (Δ {self.value_delta:+.3f})")
            lines.append(f"Avg confidence: {self.avg_confidence:.0%}")

        if self.dismissed_count > 0:
            lines.append(
                f"⚠  {self.dismissed_count} prior occurrence(s) were REJECTED/dismissed. "
                f"Consider whether the situation has changed."
            )
        if self.approved_count > 0:
            lines.append(f"✓  {self.approved_count} prior occurrence(s) were approved and actioned.")
        if self.pending_count > 0:
            lines.append(f"⏳  {self.pending_count} prior occurrence(s) still awaiting approval.")

        if self.value_trend == "escalating" and self.occurrence_count >= 2:
            lines.append(
                "PATTERN DETECTED: Signal is escalating across repeated occurrences. "
                "Raise confidence and consider higher escalation level."
            )

        if self.dismissed_count >= 2:
            lines.append(
                "PATTERN DETECTED: This signal has been dismissed multiple times. "
                "If values continue to rise, override past dismissals and escalate."
            )

        if self.other_recent_events:
            lines.append(
                f"Other recent events on this machine: {'; '.join(self.other_recent_events)}"
            )

        lines.append("=== END MEMORY ===")
        return "\n".join(lines)


# ── Ring-buffer store ─────────────────────────────────────────────────────────

class MachineMemoryStore:
    """
    Thread-safe in-memory store of recent events per machine.

    Layout: {factory_id: {machine_id: deque[MemoryEntry]}}
    """

    def __init__(self, max_entries_per_machine: int = 20, ttl_hours: float = 8.0):
        self._lock = threading.Lock()
        self._store: Dict[str, Dict[str, deque]] = {}
        self._max = max_entries_per_machine
        self._ttl = ttl_hours

    def record(self, entry: MemoryEntry) -> None:
        key_f = entry.factory_id
        key_m = entry.machine_id
        with self._lock:
            if key_f not in self._store:
                self._store[key_f] = {}
            if key_m not in self._store[key_f]:
                self._store[key_f][key_m] = deque(maxlen=self._max)
            self._store[key_f][key_m].append(entry)

    def get_recent(
        self,
        factory_id: str,
        machine_id: str,
        limit: int = 10,
    ) -> List[MemoryEntry]:
        with self._lock:
            buf = self._store.get(factory_id, {}).get(machine_id, deque())
            # Return most-recent first, skip expired
            entries = [e for e in reversed(buf) if not e.is_expired(self._ttl)]
            return entries[:limit]

    def get_pattern(
        self,
        factory_id: str,
        machine_id: str,
        signal_name: str,
    ) -> PatternAnalysis:
        recent = self.get_recent(factory_id, machine_id, limit=self._max)
        return PatternAnalysis(recent, signal_name)

    def update_decision_status(
        self,
        factory_id: str,
        machine_id: str,
        signal_name: str,
        status: str,
    ) -> None:
        """Back-fill decision outcome onto the most recent matching entry."""
        with self._lock:
            buf = self._store.get(factory_id, {}).get(machine_id)
            if not buf:
                return
            for entry in reversed(buf):
                if entry.signal_name == signal_name and entry.decision_status is None:
                    entry.decision_status = status
                    break

    def flush_expired(self) -> int:
        """Remove expired entries across all machines. Returns count removed."""
        removed = 0
        with self._lock:
            for factory_machines in self._store.values():
                for machine_id, buf in factory_machines.items():
                    before = len(buf)
                    fresh = deque(
                        (e for e in buf if not e.is_expired(self._ttl)),
                        maxlen=self._max,
                    )
                    factory_machines[machine_id] = fresh
                    removed += before - len(fresh)
        return removed

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            total = sum(
                len(buf)
                for fm in self._store.values()
                for buf in fm.values()
            )
            return {
                "factories": len(self._store),
                "machines": sum(len(fm) for fm in self._store.values()),
                "total_entries": total,
                "ttl_hours": self._ttl,
                "max_per_machine": self._max,
            }


# ── Singleton ─────────────────────────────────────────────────────────────────

_store: Optional[MachineMemoryStore] = None


def get_memory_store() -> MachineMemoryStore:
    global _store
    if _store is None:
        _store = MachineMemoryStore(max_entries_per_machine=20, ttl_hours=8.0)
    return _store
