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

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from paaim.auth.deps import tenant_id
from paaim.config import settings
from paaim.normalization import (
    SourceMapping, apply, auto_map, get_mapping_store, vocab_for,
)
from paaim.normalization.vocabulary import get_vocabulary_store

router = APIRouter()


class ProposeRequest(BaseModel):
    source_id: str
    sample_payload: Dict[str, Any]
    machine_id_field: Optional[str] = None
    machine_id: str = "unknown"
    use_llm: bool = False
    # What the source declared each field's unit to be, as returned by
    # /sources/discover. Optional: a source that declares nothing still maps,
    # the mapping is just marked as unit-unverified rather than silently assumed
    # correct.
    field_units: Optional[Dict[str, str]] = None


class ConfirmRequest(BaseModel):
    mapping: Dict[str, Any]


class IngestRequest(BaseModel):
    source_id: str
    payload: Dict[str, Any]
    # No factory_id. It used to be a request field defaulting to "factory_001",
    # which meant a caller chose whose factory their readings landed in — or,
    # by saying nothing, landed them in someone else's. The tenant comes from
    # the token now, and a caller cannot state it.


@router.get("/vocab")
async def get_vocab(factory: str = Depends(tenant_id)) -> dict:
    """The plant's signal vocabulary — what raw tags get mapped INTO."""
    from paaim.normalization.vocabulary import get_vocabulary_store
    store = get_vocabulary_store(factory)
    return {
        "pack_id": store.pack_id,
        "signals": [
            {
                "signal": s,
                "unit": meta.get("unit"),
                "event_type": meta.get("event_type"),
                "higher_is_worse": meta.get("higher_is_worse", True),
                "description": meta.get("description", ""),
                "synonyms": meta.get("synonyms", []),
            }
            for s, meta in vocab_for(factory).items()
        ],
    }


@router.get("/vocab/packs")
async def list_packs(factory: str = Depends(tenant_id)) -> dict:
    """
    Starter vocabularies. A plant picks the closest and edits it — adding an
    industry must never require a release.
    """
    from paaim.normalization.vocabulary import STARTER_PACKS, get_vocabulary_store
    active = get_vocabulary_store(factory).pack_id
    return {
        "active": active,
        "packs": [
            {
                "pack_id": pid,
                "label": p["label"],
                "description": p["description"],
                "signal_count": len(p["signals"]),
                "signals": list(p["signals"].keys()),
                "active": pid == active,
            }
            for pid, p in STARTER_PACKS.items()
        ],
    }


class ApplyPackRequest(BaseModel):
    pack_id: str


@router.post("/vocab/pack")
async def apply_pack(req: ApplyPackRequest, factory: str = Depends(tenant_id)) -> dict:
    """
    Adopt a starter vocabulary.

    Saved mappings are never rewritten — the operator confirmed those, and
    guessing a new signal for them would be worse than leaving them. But a
    mapping pointing at a signal this pack does not define stops routing
    correctly, so report exactly which ones are now orphaned instead of letting
    them degrade quietly to the default discipline.
    """
    from paaim.normalization.vocabulary import get_vocabulary_store
    try:
        signals = get_vocabulary_store(factory).apply_pack(req.pack_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))

    orphaned = []
    for m in get_mapping_store(factory).list():
        for raw, fm in (m.fields or {}).items():
            if fm.signal not in signals:
                orphaned.append({"source_id": m.source_id, "raw_field": raw, "signal": fm.signal})

    return {
        "ok": True,
        "pack_id": req.pack_id,
        "signals": len(signals),
        "orphaned_mappings": orphaned,
        "warning": (
            f"{len(orphaned)} mapped field(s) point at signals this vocabulary does not "
            f"define — they will not route correctly until remapped."
        ) if orphaned else None,
    }


class SignalRequest(BaseModel):
    signal: str
    unit: str = ""
    event_type: str = "maintenance"
    higher_is_worse: bool = True
    synonyms: List[str] = []
    description: str = ""


@router.put("/vocab/signal")
async def upsert_signal(req: SignalRequest, factory: str = Depends(tenant_id)) -> dict:
    """Add or edit one signal — how a plant extends its own vocabulary."""
    from paaim.normalization.vocabulary import get_vocabulary_store
    get_vocabulary_store(factory).upsert(req.signal, req.dict(exclude={"signal"}))
    return {"ok": True, "signal": req.signal, "signals": len(vocab_for(factory))}


@router.delete("/vocab/signal/{signal}")
async def delete_signal(signal: str, factory: str = Depends(tenant_id)) -> dict:
    from paaim.normalization.vocabulary import get_vocabulary_store
    if not get_vocabulary_store(factory).remove(signal):
        raise HTTPException(status_code=404, detail=f"No such signal: {signal}")
    return {"ok": True, "removed": signal}


@router.post("/propose")
async def propose_mapping(req: ProposeRequest, factory: str = Depends(tenant_id)) -> dict:
    """Run the tiered resolver on a sample payload and return a proposed mapping.
    This is the ONLY place AI may run (Tier 4), and only if use_llm=True."""
    mapping = auto_map(
        source_id=req.source_id,
        sample_payload=req.sample_payload,
        machine_id=req.machine_id,
        machine_id_field=req.machine_id_field,
        use_llm=req.use_llm,
        field_units=req.field_units,
        factory_id=factory,
    )
    d = mapping.to_dict()
    # Explain each unit verdict where the operator will read it. A conflict is
    # the one thing on this screen that cannot be resolved by the machine.
    from paaim.normalization.units import describe
    for raw, fm in mapping.fields.items():
        d["fields"][raw]["unit_note"] = describe(fm.source_unit, fm.unit, fm.unit_status)

    counts: Dict[str, int] = {}
    for fm in mapping.fields.values():
        counts[fm.unit_status] = counts.get(fm.unit_status, 0) + 1
    d["stats"] = {
        "mapped": len(mapping.fields),
        "unmapped": len(mapping.unmapped),
        "by_tier": _tier_counts(mapping),
        "by_unit_status": counts,
        "unit_conflicts": counts.get("conflict", 0),
    }
    return d


class ReconcileRequest(BaseModel):
    signal: str
    source_unit: str = ""


@router.post("/reconcile")
async def reconcile_field_unit(req: ReconcileRequest, factory: str = Depends(tenant_id)) -> dict:
    """
    Re-settle one field's unit after an operator picks a different signal.

    Exists so the conversion table has exactly one home. The obvious alternative
    — mirroring it in the UI — drifts the moment either side gains a unit, and a
    drifted conversion is invisible: the number still looks like a number.
    """
    from paaim.normalization.units import describe, reconcile
    target = vocab_for(factory).get(req.signal, {}).get("unit", "")
    transform, status = reconcile(req.source_unit, target)
    return {
        "signal": req.signal,
        "source_unit": req.source_unit,
        "unit": target,
        "transform": transform,
        "unit_status": status,
        "unit_note": describe(req.source_unit, target, status),
    }


@router.post("/confirm")
async def confirm_mapping(req: ConfirmRequest, factory: str = Depends(tenant_id)) -> dict:
    """Persist a (human-reviewed) mapping. Runtime uses this — no AI."""
    try:
        mapping = SourceMapping.from_dict(req.mapping)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid mapping: {e}")
    # Confirm carries only the field mapping — the operator is editing signals,
    # not the connection. Without this, saving a mapping silently discards the
    # verified connection that was established in the connect step.
    existing = get_mapping_store(factory).get(mapping.source_id)
    if mapping.connection is None and existing is not None:
        mapping.connection = existing.connection

    mapping.confirmed = True
    mapping.version += 1
    get_mapping_store(factory).put(mapping)

    # Connecting a source is what puts it under watch: deploy a watcher for every
    # field the operator flagged, and retire any it no longer wants. Best-effort —
    # a feed that is down must not fail the mapping the operator just confirmed.
    watchers = {}
    try:
        from paaim.stream_bridge.bridge import get_stream_bridge
        watchers = await get_stream_bridge().sync_from_mapping(
            factory, mapping.source_id, settings.STREAM_TRIGGER_LEVEL
        )
    except Exception as e:
        watchers = {"error": str(e)}

    # A polled source is asked, not listened to — it needs a poller rather than
    # a watcher. Without this it would sit here mapped and healthy-looking,
    # ingesting nothing.
    pollers = {}
    try:
        from paaim.sources.poller import get_poller_registry
        pollers = await get_poller_registry().sync(factory)
    except Exception as e:
        pollers = {"error": str(e)}

    return {
        "ok": True,
        "source_id": mapping.source_id,
        "version": mapping.version,
        "fields": len(mapping.fields),
        "watching": len(watchers.get("connected", [])),
        "watchers": watchers,
        "pollers": pollers,
    }


@router.get("/mappings")
async def list_mappings(factory: str = Depends(tenant_id)) -> dict:
    return {"mappings": [m.to_dict() for m in get_mapping_store(factory).list()]}


@router.post("/ingest")
async def ingest(req: IngestRequest, factory: str = Depends(tenant_id)) -> dict:
    """Normalize a raw payload through the saved mapping and publish canonical
    events onto the bus (which the pipeline consumes into decisions)."""
    mapping = get_mapping_store(factory).get(req.source_id)
    if not mapping:
        raise HTTPException(status_code=404, detail=f"No confirmed mapping for source '{req.source_id}'. Propose + confirm one first.")

    readings = apply(mapping, req.payload, factory_id=factory)
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
