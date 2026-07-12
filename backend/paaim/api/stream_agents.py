"""API for connecting agents to the live factory-stream feed."""

from fastapi import APIRouter, HTTPException
import httpx

from paaim.stream_bridge.bridge import get_stream_bridge

router = APIRouter()


@router.get("/signals")
async def available_signals():
    """List signals on the live feed that an agent can connect to."""
    try:
        return {"signals": await get_stream_bridge().available_signals()}
    except (httpx.HTTPError, Exception) as e:
        raise HTTPException(
            status_code=502,
            detail=f"Factory-stream feed not reachable: {e}. Is it running on 9100?",
        )


@router.get("")
@router.get("/")
async def list_stream_agents():
    """Live status of every connected stream agent."""
    agents = get_stream_bridge().list_status()
    return {
        "agents": agents,
        "count": len(agents),
        "connected": sum(1 for a in agents if a["connected"]),
        "events_raised": sum(a["events_raised"] for a in agents),
    }


@router.post("/connect")
async def connect_stream_agent(machine_id: str, signal: str, trigger_level: str = "critical"):
    """Connect an agent to one live signal; it starts receiving immediately."""
    status = await get_stream_bridge().connect(machine_id, signal, trigger_level)
    return {"status": "connected", "agent": status}


@router.post("/auto-connect")
async def auto_connect(trigger_level: str = "critical"):
    """Connect an agent to every available signal — one-click demo setup."""
    try:
        agents = await get_stream_bridge().auto_connect_default(trigger_level)
        return {"status": "connected", "count": len(agents), "agents": agents}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Feed not reachable: {e}")


@router.post("/disconnect/{machine_id}/{signal}")
async def disconnect_stream_agent(machine_id: str, signal: str):
    ok = await get_stream_bridge().disconnect(f"{machine_id}::{signal}")
    if not ok:
        raise HTTPException(status_code=404, detail="No such connected agent")
    return {"status": "disconnected", "key": f"{machine_id}::{signal}"}
