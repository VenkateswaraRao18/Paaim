"""EventBus abstraction — the contract every backend implements."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, Optional


@dataclass
class BusRecord:
    """A single message on the bus."""
    topic: str
    key: Optional[str]            # partition key (e.g. machine_id) — preserves per-key order
    value: Dict[str, Any]         # JSON-serialisable payload
    offset: int = -1              # position in the log (assigned by the bus)
    timestamp: Optional[str] = None
    headers: Dict[str, str] = field(default_factory=dict)


# A consumer handler returns nothing on success and raises to signal failure
# (failed records are routed to the dead-letter topic by the bus).
Handler = Callable[[BusRecord], Awaitable[None]]


class EventBus(ABC):
    """
    Reliable publish/subscribe with durable, replayable, ordered-per-key
    delivery and at-least-once semantics (offset committed only after the
    handler succeeds).
    """

    @abstractmethod
    async def start(self) -> None:
        """Open connections / files."""

    @abstractmethod
    async def stop(self) -> None:
        """Flush and close."""

    @abstractmethod
    async def publish(self, topic: str, value: Dict[str, Any],
                      key: Optional[str] = None,
                      headers: Optional[Dict[str, str]] = None) -> int:
        """Durably append a record. Returns its offset."""

    @abstractmethod
    async def start_consumer(self, topic: str, group: str, handler: Handler,
                             dlq_topic: Optional[str] = None) -> None:
        """
        Begin consuming `topic` as `group`. For each record, call `handler`;
        commit the offset only on success. On handler failure, route the
        record to `dlq_topic` (if given) and still advance, so one poison
        event can't wedge the pipeline.
        """

    @abstractmethod
    async def stop_consumer(self, topic: str, group: str) -> None:
        """Stop a running consumer loop."""

    @abstractmethod
    async def stats(self) -> Dict[str, Any]:
        """Backend-agnostic health/lag snapshot for the observability API."""

    @abstractmethod
    async def replay(self, topic: str, group: str, from_offset: int = 0) -> int:
        """Reset a group's committed offset so it reprocesses from `from_offset`."""
