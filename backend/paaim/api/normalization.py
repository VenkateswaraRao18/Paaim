"""
Normalization API — onboard a data source, then ingest through it.

    POST /normalization/propose   raw sample  -> proposed mapping (tiers 1-3, opt. LLM)
    POST /normalization/confirm   edited mapping -> saved (deterministic runtime artifact)
    GET  /normalization/mappings  list saved mappings
    GET  /normalization/vocab     the canonical signal vocabulary (for UI dropdowns)
    POST /normalization/ingest    raw payload -> normalize -> publish to bus -> pipeline

The ingest endpoint is the "wire it live" path: a raw, source-specific payload
goes in, canonical events come out onto the Event Bus, and the 7-layer pipeline
turns them into governed decisions.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from paaim.config import settings
from paaim.normalization import (
    SIGNAL_VOCAB, SourceMapping, apply, auto_map, get_mapping_store,
)

router = APIRouter()


class ProposeRequest(BaseModel):
    source_id: str
    sample_payload: Dict[str, Any]
    machine_id_field: Optional[str] = None
    machine_id: str = "unknown"
    use_llm: bool = False


class ConfirmRequest(BaseModel):
    mapping: Dict[str, Any]


class IngestRequest(BaseModel):
    source_id: str
    payload: Dict[str, Any]
    factory_id: str = "factory_001"


@router.get("/vocab")
async def get_vocab() -> dict:
    """Canonical signal vocabulary — what raw fields get mapped INTO."""
    return {
        "signals": [
            {"signal": s, "unit": meta.get("unit"), "event_type": meta.get("event_type")}
            for s, meta in SIGNAL_VOCAB.items()
        ]
    }


@router.post("/propose")
async def propose_mapping(req: ProposeRequest) -> dict:
    """Run the tiered resolver on a sample payload and return a proposed mapping.
    This is the ONLY place AI may run (Tier 4), and only if use_llm=True."""
    mapping = auto_map(
        source_id=req.source_id,
        sample_payload=req.sample_payload,
        machine_id=req.machine_id,
        machine_id_field=req.machine_id_field,
        use_llm=req.use_llm,
    )
    d = mapping.to_dict()
    d["stats"] = {
        "mapped": len(mapping.fields),
        "unmapped": len(mapping.unmapped),
        "by_tier": _tier_counts(mapping),
    }
    return d


@router.post("/confirm")
async def confirm_mapping(req: ConfirmRequest) -> dict:
    """Persist a (human-reviewed) mapping. Runtime uses this — no AI."""
    try:
        mapping = SourceMapping.from_dict(req.mapping)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid mapping: {e}")
    mapping.confirmed = True
    mapping.version += 1
    get_mapping_store().put(mapping)
    return {"ok": True, "source_id": mapping.source_id, "version": mapping.version, "fields": len(mapping.fields)}


@router.get("/mappings")
async def list_mappings() -> dict:
    return {"mappings": [m.to_dict() for m in get_mapping_store().list()]}


@router.post("/ingest")
async def ingest(req: IngestRequest) -> dict:
    """Normalize a raw payload through the saved mapping and publish canonical
    events onto the bus (which the pipeline consumes into decisions)."""
    mapping = get_mapping_store().get(req.source_id)
    if not mapping:
        raise HTTPException(status_code=404, detail=f"No confirmed mapping for source '{req.source_id}'. Propose + confirm one first.")

    readings = apply(mapping, req.payload, factory_id=req.factory_id)
    if not readings:
        return {"published": 0, "readings": [], "note": "No mapped fields in payload."}

    published = 0
    try:
        from paaim.bus.factory import get_event_bus
        bus = get_event_bus()
        for r in readings:
            await bus.publish(settings.BUS_EVENTS_TOPIC, r.to_event(confidence=0.9), key=r.machine_id)
            published += 1
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Publish failed: {e}")

    return {
        "published": published,
        "readings": [r.to_dict() for r in readings],
        "note": "Canonical events published to the pipeline.",
    }


def _tier_counts(mapping: SourceMapping) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for fm in mapping.fields.values():
        counts[fm.resolved_by] = counts.get(fm.resolved_by, 0) + 1
    return counts
