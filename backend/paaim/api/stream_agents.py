"""
Live watchers — read-only, plus fault injection for commissioning.

There is no endpoint here to create a watcher, and that absence is the point.
Watchers are derived from a source's confirmed mapping (POST /normalization/confirm
→ StreamBridge.sync_from_mapping). The `/connect`, `/auto-connect` and
`/disconnect` endpoints that used to live here let the UI mint a watcher with no
mapping behind it: it reported itself connected, and dropped every event it ever
judged, because there was nothing to translate its raw tag into a canonical
signal. One honest path is worth more than two paths where one silently lies.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
import httpx

from paaim.auth.deps import tenant_id
from paaim.stream_bridge.bridge import get_stream_bridge

router = APIRouter()


@router.get("/signals")
async def available_signals(
    source_id: str = Query(..., description="A connected source, from Data Sources."),
    factory: str = Depends(tenant_id),
):
    """
    The tags a connected source publishes.

    `source_id` is required. It used to be implicit — the feed's address was read
    from config — so this answered with a hardcoded plant's signals even when no
    source was connected at all.
    """
    try:
        return {"source_id": source_id,
                "signals": await get_stream_bridge().available_signals(factory, source_id)}
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Source '{source_id}' is not reachable: {e}")


@router.get("")
@router.get("/")
async def list_stream_agents(
    include_series: bool = Query(
        False, description="Include each watcher's recent judged readings (for sparklines)."
    ),
    factory: str = Depends(tenant_id),
):
    """
    Live status of every watcher.

    `include_series` is opt-in: the readings buffer is ~40 points per watcher, so
    a plant with hundreds of watched tags must not pay for it on every poll of a
    list view that only needs the current value.
    """
    agents = get_stream_bridge().list_status(factory, include_series=include_series)
    return {
        "agents": agents,
        "count": len(agents),
        "connected": sum(1 for a in agents if a["connected"]),
        "events_raised": sum(a["events_raised"] for a in agents),
    }


@router.post("/simulate-fault")
async def simulate_fault(
    source_id: str = Query(..., description="The source to inject into."),
    machine_id: str = Query(...),
    signal: str = Query(..., description="The raw tag, e.g. TT_101."),
    duration: int = Query(15, ge=1, le=300, description="Seconds to hold the anomaly."),
    factory: str = Depends(tenant_id),
):
    """
    Ask a source to inject a fault, for commissioning and alert testing.

    PAAIM cannot fabricate a reading — it only observes. So this is a capability
    of the *source*, and only a source that exposes an injection endpoint (the
    bundled simulator does; a real historian does not) can honour it. Sources
    that cannot are told so plainly rather than failing as a dead button.
    """
    try:
        _, endpoint = get_stream_bridge()._resolve(factory, source_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))

    try:
        async with httpx.AsyncClient(timeout=8) as client:
            resp = await client.post(
                f"{endpoint}/anomaly",
                params={"machine_id": machine_id, "signal": signal, "duration": duration},
            )
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Source '{source_id}' is not reachable: {e}")

    if resp.status_code == 404:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Source '{source_id}' does not support fault injection — it has no "
                f"/anomaly endpoint. This is expected for a real historian or SCADA: "
                f"you can only test with a source that can generate readings on demand."
            ),
        )
    if resp.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"Source rejected the injection: HTTP {resp.status_code}")

    return {"ok": True, "source_id": source_id, "machine_id": machine_id,
            "signal": signal, "duration_s": duration}
