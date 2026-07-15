"""
StreamBridge — the set of live watchers, derived from what the plant connected.

A watcher exists for exactly one reason: an operator connected a source, mapped
a tag to a canonical signal, and ticked it to be watched. There is deliberately
no other way to make one.

That used to be untrue, and it produced the worst class of bug in this product:
a UI offering an "Attach" button that created a watcher out of thin air. Such a
watcher had no mapping behind it, so on breach `_to_canonical()` returned None
and the event was dropped — it could never raise an incident, while reporting
itself connected and healthy. A blank PAAIM listed seven machines it had never
been told about and let you attach to them, because the feed's address was
hardcoded in config rather than read from a source someone actually connected.

Hence two rules here, and they are the whole design:

  · watchers come from `sync_from_mapping` and nowhere else.
  · a source's address comes from that source's own connection record.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple

import httpx

from paaim.stream_bridge.agent import StreamAgent

logger = logging.getLogger(__name__)


class StreamBridge:
    def __init__(self):
        self._agents: Dict[str, StreamAgent] = {}

    # ── resolving a source ───────────────────────────────────────────────────
    @staticmethod
    def _resolve(factory_id: str, source_id: str) -> Tuple[object, str]:
        """
        The confirmed mapping and endpoint for one factory's source.

        Every address in this class comes through here. Falling back to a
        configured default would reintroduce the original bug in a quieter form:
        a watcher silently pointed at the wrong plant. `factory_id` scopes the
        lookup — two tenants both calling a source "scada" is the normal case,
        not a collision to be resolved by luck.
        """
        from paaim.normalization.mapping import get_mapping_store

        mapping = get_mapping_store(factory_id).get(source_id)
        if not mapping:
            raise LookupError(
                f"No data source '{source_id}'. Connect it under Data Sources first."
            )
        conn = getattr(mapping, "connection", None)
        endpoint = getattr(conn, "endpoint", None) if conn else None
        if not endpoint:
            raise LookupError(
                f"Data source '{source_id}' has no verified connection endpoint. "
                f"Re-run Test connection under Data Sources."
            )
        return mapping, endpoint.rstrip("/")

    async def available_signals(self, factory_id: str, source_id: str) -> List[dict]:
        """
        The tags a connected source publishes.

        Asks the source the operator connected — not a URL baked into config.
        This is discovery, and it is right that the plant's SCADA is the one that
        answers: nobody hand-types five hundred tags.
        """
        _, endpoint = self._resolve(factory_id, source_id)
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{endpoint}/signals")
            resp.raise_for_status()
            return resp.json().get("signals", [])

    # ── watchers ─────────────────────────────────────────────────────────────
    @staticmethod
    def key_for(factory_id: str, machine_id: str, signal: str) -> str:
        """
        A watcher's identity, namespaced by tenant.

        This was `machine_id::signal`. Two plants both running a `mixer_01` —
        which is to say, two ordinary plants — would have shared one watcher:
        the second tenant's would find the first's already present and quietly
        reuse it, feeding one factory's readings into the other's pipeline.
        """
        return f"{factory_id}::{machine_id}::{signal}"

    async def _connect(self, machine_id: str, signal: str, *, factory_id: str,
                       source_id: str, source_url: str, trigger_level: str) -> dict:
        """
        Start one watcher. Private on purpose — see the module docstring.

        Everything it needs to know about its own identity is passed in: a
        watcher that guesses its factory, source or address ends up reading the
        wrong mapping and translating its tag with the wrong plant's vocabulary.
        """
        key = self.key_for(factory_id, machine_id, signal)
        existing = self._agents.get(key)
        if existing:
            # Re-confirming a mapping is how an operator corrects it — a changed
            # signal, unit or transform. A watcher started before that edit is
            # still judging by the old one, so reload rather than returning it
            # untouched: the fix would appear saved and do nothing.
            await existing.refresh_thresholds()
            return existing.status()
        agent = StreamAgent(
            machine_id, signal, factory_id=factory_id,
            trigger_level=trigger_level, source_id=source_id, source_url=source_url,
        )
        await agent.start()
        self._agents[key] = agent
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

    def list_status(self, factory_id: str, include_series: bool = False) -> List[dict]:
        """
        One factory's watchers. `factory_id` is required — an unfiltered list is
        every tenant's live process data, and this feeds an API response.
        """
        return [
            a.status(include_series=include_series)
            for a in self._agents.values() if a.factory_id == factory_id
        ]

    async def sync_from_mapping(self, factory_id: str, source_id: str,
                                trigger_level: str = "critical") -> dict:
        """
        Make the live watchers match what the operator configured for a source.

        The only door through which a watcher is created. Fields ticked `watch`
        get one; everything else is retired. Idempotent, so it is safe on every
        confirm and on startup (watchers are in-memory and do not survive a
        restart — which is why an empty PAAIM must show zero of them).
        """
        try:
            mapping, endpoint = self._resolve(factory_id, source_id)
        except LookupError as e:
            return {"connected": [], "detached": [], "error": str(e)}

        wanted_tags = {raw for raw, fm in mapping.fields.items() if getattr(fm, "watch", True)}
        try:
            available = await self.available_signals(factory_id, source_id)
        except Exception as e:
            logger.warning(f"[{factory_id}] cannot reach '{source_id}' to sync watchers: {e}")
            return {"connected": [], "detached": [], "error": str(e)}

        connected: List[str] = []
        for s in available:
            if s["signal"] in wanted_tags:
                await self._connect(
                    s["machine_id"], s["signal"], factory_id=factory_id,
                    source_id=source_id, source_url=endpoint, trigger_level=trigger_level,
                )
                connected.append(f"{s['machine_id']}::{s['signal']}")

        # Retire watchers for tags this source no longer wants watched — this
        # factory's only. Without the factory check, re-confirming one tenant's
        # mapping would detach another tenant's watchers on a same-named source.
        detached: List[str] = []
        for key, agent in list(self._agents.items()):
            if (agent.factory_id == factory_id and agent.source_id == source_id
                    and agent.signal not in wanted_tags):
                await self.disconnect(key)
                detached.append(key)

        logger.info(f"[{factory_id}] synced '{source_id}': "
                    f"{len(connected)} watching, {len(detached)} detached")
        return {"connected": connected, "detached": detached}


_bridge: Optional[StreamBridge] = None


def get_stream_bridge() -> StreamBridge:
    global _bridge
    if _bridge is None:
        _bridge = StreamBridge()
    return _bridge
