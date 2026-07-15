"""Data-source connectivity API: what PAAIM can talk to, and proof that it can."""

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from paaim.normalization.mapping import SourceConnection, get_mapping_store
from paaim.sources.connectors import SOURCE_TYPES, discover, test_connection

from paaim.auth.deps import tenant_id

router = APIRouter()


class ConnectionRequest(BaseModel):
    type: str
    endpoint: str = ""
    auth_type: Optional[str] = None
    auth_config: Dict[str, str] = {}


class SaveConnectionRequest(ConnectionRequest):
    source_id: str
    poll_interval_seconds: int = 30


@router.get("/types")
async def list_types() -> dict:
    """Every source type, and honestly which ones actually work today."""
    return {
        "types": SOURCE_TYPES,
        "supported": [t["type"] for t in SOURCE_TYPES if t["supported"]],
    }


@router.post("/test-connection")
async def test(req: ConnectionRequest) -> dict:
    """Reach the source for real and report exactly what happened."""
    result = await test_connection(
        type=req.type, endpoint=req.endpoint,
        auth_type=req.auth_type, auth_config=req.auth_config,
    )
    return result.to_dict()


@router.post("/discover")
async def discover_fields(req: ConnectionRequest) -> dict:
    """Pull one live sample so the mapping is built from what the source really sends."""
    result = await discover(
        type=req.type, endpoint=req.endpoint,
        auth_type=req.auth_type, auth_config=req.auth_config,
    )
    return result.to_dict()


@router.post("/connect")
async def connect(req: SaveConnectionRequest, factory: str = Depends(tenant_id)) -> dict:
    """
    Save a source's connection after verifying it.

    The connection is only stored once a real round-trip succeeds, so a source
    can never sit in the list claiming to be connected to something unreachable.
    """
    result = await test_connection(
        type=req.type, endpoint=req.endpoint,
        auth_type=req.auth_type, auth_config=req.auth_config,
    )
    if not result.ok:
        raise HTTPException(status_code=400, detail=result.detail)

    store = get_mapping_store(factory)
    mapping = store.get(req.source_id)
    conn = SourceConnection(
        type=req.type, endpoint=req.endpoint,
        auth_type=req.auth_type, auth_config=req.auth_config,
        poll_interval_seconds=req.poll_interval_seconds,
        verified_at=result.checked_at,
    )
    if mapping:
        mapping.connection = conn
        store.put(mapping)
    else:
        # Connection recorded now; fields get mapped in the next step.
        from paaim.normalization.mapping import SourceMapping
        store.put(SourceMapping(source_id=req.source_id, connection=conn))

    return {
        "ok": True,
        "source_id": req.source_id,
        "connection": conn.to_public_dict(),
        "detail": result.detail,
        "next": "Discover this source's fields, then map them.",
    }


@router.get("/pollers")
async def list_pollers(factory: str = Depends(tenant_id)) -> dict:
    """Live status of every polling source — what it fetched and what it judged."""
    from paaim.sources.poller import get_poller_registry
    pollers = get_poller_registry().list_status(factory)
    return {
        "pollers": pollers,
        "count": len(pollers),
        "events_raised": sum(p["events_raised"] for p in pollers),
    }


@router.get("")
@router.get("/")
async def list_sources(factory: str = Depends(tenant_id)) -> dict:
    """Every data source, its connection, and how much of it is under watch."""
    from paaim.sources.links import agents_fed_by_source

    out = []
    for m in get_mapping_store(factory).list():
        watched = sum(1 for f in m.fields.values() if getattr(f, "watch", True))
        out.append({
            "source_id": m.source_id,
            "connection": m.connection.to_public_dict() if m.connection else None,
            "fields_mapped": len(m.fields),
            "fields_watched": watched,
            "confirmed": m.confirmed,
            "version": m.version,
            # Which monitors this source reaches — the same link the agent side
            # shows, so the chain is legible from either end.
            "feeds": agents_fed_by_source(m.source_id, factory),
        })
    return {"sources": out, "count": len(out)}
