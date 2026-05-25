"""Real-time event streaming for orchestration pipeline."""

from typing import Dict, Any, List, Callable, Optional
from datetime import datetime
from enum import Enum
import asyncio
import json


class PipelineEventType(str, Enum):
    """Types of events in the orchestration pipeline."""
    # Pipeline lifecycle
    ORCHESTRATION_STARTED = "orchestration_started"
    ORCHESTRATION_COMPLETED = "orchestration_completed"
    ORCHESTRATION_ERROR = "orchestration_error"

    # Layer events
    EVENT_RECEIVED = "event_received"
    AGENTS_ROUTING = "agents_routing"
    AGENTS_ANALYZING = "agents_analyzing"
    AGENTS_COMPLETE = "agents_complete"

    POLICY_CHECKING = "policy_checking"
    POLICY_COMPLETE = "policy_complete"

    TWIN_SIMULATING = "twin_simulating"
    TWIN_COMPLETE = "twin_complete"

    RED_TEAM_CHALLENGING = "red_team_challenging"
    RED_TEAM_COMPLETE = "red_team_complete"

    APPROVAL_ROUTING = "approval_routing"
    APPROVAL_COMPLETE = "approval_complete"

    # Action events
    ACTION_SELECTED = "action_selected"
    ACTION_APPROVED = "action_approved"
    ACTION_REJECTED = "action_rejected"


class PipelineEvent:
    """Event emitted during orchestration pipeline execution."""

    def __init__(
        self,
        event_type: PipelineEventType,
        decision_id: str,
        layer: str,
        data: Dict[str, Any],
    ):
        self.event_type = event_type
        self.decision_id = decision_id
        self.layer = layer
        self.data = data
        self.timestamp = datetime.utcnow().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        return {
            "event_type": self.event_type.value,
            "decision_id": self.decision_id,
            "layer": self.layer,
            "data": self.data,
            "timestamp": self.timestamp,
        }

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict())


class PipelineEventPublisher:
    """
    Publishes events during orchestration pipeline execution.

    Supports multiple subscribers (WebSocket connections, logging, etc.)
    """

    def __init__(self):
        """Initialize publisher."""
        self.subscribers: Dict[str, List[Callable]] = {}

    def subscribe(
        self,
        decision_id: str,
        callback: Callable[[PipelineEvent], None],
    ) -> None:
        """
        Subscribe to events for a specific decision.

        Args:
            decision_id: Decision to monitor
            callback: Async function to call on each event
        """
        if decision_id not in self.subscribers:
            self.subscribers[decision_id] = []
        self.subscribers[decision_id].append(callback)

    def unsubscribe(self, decision_id: str, callback: Callable) -> None:
        """Unsubscribe from events."""
        if decision_id in self.subscribers:
            self.subscribers[decision_id] = [
                cb for cb in self.subscribers[decision_id] if cb != callback
            ]
            if not self.subscribers[decision_id]:
                del self.subscribers[decision_id]

    async def emit(self, event: PipelineEvent) -> None:
        """
        Emit event to all subscribers for this decision.

        Args:
            event: Event to publish
        """
        if event.decision_id not in self.subscribers:
            return

        # Call all subscribers concurrently
        tasks = [
            cb(event) for cb in self.subscribers[event.decision_id]
        ]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    def has_subscribers(self, decision_id: str) -> bool:
        """Check if decision has active subscribers."""
        return decision_id in self.subscribers and bool(self.subscribers[decision_id])


# Global publisher instance
_publisher: Optional[PipelineEventPublisher] = None


def get_publisher() -> PipelineEventPublisher:
    """Get or create global publisher."""
    global _publisher
    if _publisher is None:
        _publisher = PipelineEventPublisher()
    return _publisher


def reset_publisher() -> None:
    """Reset publisher (for testing)."""
    global _publisher
    _publisher = None
