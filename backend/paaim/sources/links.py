"""
Which source feeds which monitor.

Agents deliberately do not reference a data source — they watch canonical
signals, so any source mapped to those signals feeds them. That decoupling is
what lets one Thermal agent cover a whole plant, but it also makes the link
invisible: looking at an agent, you cannot see where its data comes from.

Nothing new is stored here. The link already exists implicitly and is simply
derived: source --(mapping)--> signal <--(watch_signals)-- agent, narrowed to
the machines the agent's scope covers.
"""

from __future__ import annotations

from typing import Any, Dict, List

from paaim.agents.custom_framework import CustomAgentDefinition, get_custom_agent_registry
from paaim.normalization.mapping import get_mapping_store
from paaim.stream_bridge.bridge import get_stream_bridge


def _live_watchers(factory_id: str) -> List[dict]:
    try:
        return get_stream_bridge().list_status(factory_id)
    except Exception:
        return []


def sources_feeding_agent(agent: CustomAgentDefinition, factory_id: str) -> List[Dict[str, Any]]:
    """Every mapped field that reaches this agent, and whether it is live."""
    watchers = _live_watchers(factory_id)
    watched = set(agent.watch_signals or [])
    out: List[Dict[str, Any]] = []

    for mapping in get_mapping_store(factory_id).list():
        for raw, fm in (mapping.fields or {}).items():
            if fm.signal not in watched:
                continue
            # Machines this tag actually arrives on, limited to the agent's scope.
            machines = [
                w["machine_id"] for w in watchers
                if w.get("signal") == raw
                and w.get("source_id") == mapping.source_id
                and agent.covers(w.get("machine_id") or "")
            ]
            out.append({
                "source_id": mapping.source_id,
                "raw_field": raw,
                "signal": fm.signal,
                "machines": machines,
                "watched": bool(getattr(fm, "watch", True)),
                # live == a watcher is deployed, so a breach can actually reach the agent
                "live": bool(machines) and bool(getattr(fm, "watch", True)),
            })
    return out


def agents_fed_by_source(source_id: str, factory_id: str) -> List[Dict[str, Any]]:
    """Every enabled monitor this source can reach, via the signals it maps to."""
    mapping = get_mapping_store(factory_id).get(source_id)
    if not mapping:
        return []

    signals = {
        fm.signal for fm in (mapping.fields or {}).values()
        if getattr(fm, "watch", True)
    }
    out: List[Dict[str, Any]] = []
    for agent in get_custom_agent_registry(factory_id).list_agents():
        matched = sorted(signals.intersection(agent.watch_signals or []))
        if matched:
            out.append({
                "id": agent.id,
                "name": agent.name,
                "domain": agent.domain,
                "enabled": agent.enabled,
                "via_signals": matched,
            })
    return out
