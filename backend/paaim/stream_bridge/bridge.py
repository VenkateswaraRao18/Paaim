"""StreamBridge — manages the set of connected StreamAgents."""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

import httpx

from paaim.config import settings
from paaim.stream_bridge.agent import StreamAgent

logger = logging.getLogger(__name__)


class StreamBridge:
    def __init__(self):
        self._agents: Dict[str, StreamAgent] = {}

    async def available_signals(self) -> List[dict]:
        """Ask factory-stream what signals can be connected."""
        url = f"{settings.STREAM_SOURCE_URL.rstrip('/')}/signals"
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.json().get("signals", [])

    async def connect(self, machine_id: str, signal: str,
                      trigger_level: str = "critical") -> dict:
        key = f"{machine_id}::{signal}"
        if key in self._agents:
            return self._agents[key].status()
        agent = StreamAgent(machine_id, signal, trigger_level=trigger_level)
        await agent.start()
        self._agents[key] = agent
        logger.info(f"StreamBridge connected {key}")
        return agent.status()

    async def disconnect(self, key: str) -> bool:
        agent = self._agents.pop(key, None)
        if not agent:
            return False
        await agent.stop()
        return True

    async def disconnect_all(self) -> None:
        for agent in list(self._agents.values()):
            await agent.stop()
        self._agents.clear()

    def list_status(self) -> List[dict]:
        return [a.status() for a in self._agents.values()]

    async def auto_connect_default(self, trigger_level: str = "critical") -> List[dict]:
        """Connect one agent per available signal — quick demo setup."""
        signals = await self.available_signals()
        out = []
        for s in signals:
            out.append(await self.connect(s["machine_id"], s["signal"], trigger_level))
        return out


_bridge: Optional[StreamBridge] = None


def get_stream_bridge() -> StreamBridge:
    global _bridge
    if _bridge is None:
        _bridge = StreamBridge()
    return _bridge
