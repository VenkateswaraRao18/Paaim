"""
factory-stream — a standalone live factory sensor feed (SSE).

Generates realistic readings for every signal in the catalogue every TICK and
fans them out to any number of SSE subscribers. Inject an anomaly via
POST /anomaly to make a value breach its threshold on demand.

Run:  python main.py   →   http://localhost:9100
"""

import asyncio
import json
from contextlib import asynccontextmanager
from typing import Dict, List, Set

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse

import config
from generators import build_fleet

# ── State ───────────────────────────────────────────────────────────────────
fleet = build_fleet(config.SIGNALS)
latest: Dict[str, dict] = {}                 # "machine::signal" -> last reading
subscribers: Set[asyncio.Queue] = set()      # each SSE client has a queue


def _key(machine_id: str, signal: str) -> str:
    return f"{machine_id}::{signal}"


async def _generate_loop():
    """Every tick, produce a reading per signal and fan out to subscribers."""
    while True:
        batch: List[dict] = []
        for (machine_id, signal), gen in fleet.items():
            reading = gen.next().to_dict()
            latest[_key(machine_id, signal)] = reading
            batch.append(reading)

        for q in list(subscribers):
            for reading in batch:
                try:
                    q.put_nowait(reading)
                except asyncio.QueueFull:
                    pass
        await asyncio.sleep(config.TICK_SECONDS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(_generate_loop())
    yield
    task.cancel()


app = FastAPI(title="factory-stream", version="1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)


# ── Meta ────────────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "streaming", "signals": len(fleet), "subscribers": len(subscribers)}


@app.get("/signals")
async def signals():
    return {
        "factory_id": config.FACTORY_ID,
        "tick_seconds": config.TICK_SECONDS,
        "signals": [
            {
                "machine_id": m, "signal": s, "label": g.label,
                "unit": g.unit, "warn": g.warn, "critical": g.critical,
                "higher_is_worse": g.higher_is_worse,
                "stream_url": f"/stream/{m}/{s}",
            }
            for (m, s), g in fleet.items()
        ],
    }


@app.get("/latest")
async def latest_snapshot():
    return {"readings": list(latest.values())}


# ── Anomaly injection (the demo lever) ──────────────────────────────────────
@app.post("/anomaly")
async def inject_anomaly(machine_id: str, signal: str, duration: int = 15, magnitude: float = 1.0):
    gen = fleet.get((machine_id, signal))
    if not gen:
        raise HTTPException(status_code=404, detail=f"No such signal: {machine_id}/{signal}")
    gen.inject_anomaly(duration=duration, magnitude=magnitude)
    return {
        "status": "anomaly_injected",
        "machine_id": machine_id, "signal": signal,
        "duration_ticks": duration, "magnitude": magnitude,
        "note": f"{gen.label} will breach its threshold for ~{duration} readings.",
    }


# ── SSE streams ─────────────────────────────────────────────────────────────
def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


async def _stream(filter_fn=None):
    q: asyncio.Queue = asyncio.Queue(maxsize=200)
    subscribers.add(q)
    try:
        # prime with current snapshot so a new subscriber sees data immediately
        for reading in latest.values():
            if filter_fn is None or filter_fn(reading):
                yield _sse(reading)
        while True:
            reading = await q.get()
            if filter_fn is None or filter_fn(reading):
                yield _sse(reading)
    finally:
        subscribers.discard(q)


@app.get("/stream")
async def stream_all():
    return StreamingResponse(_stream(), media_type="text/event-stream")


@app.get("/stream/{machine_id}/{signal}")
async def stream_one(machine_id: str, signal: str):
    if (machine_id, signal) not in fleet:
        raise HTTPException(status_code=404, detail=f"No such signal: {machine_id}/{signal}")

    def _match(r: dict) -> bool:
        return r["machine_id"] == machine_id and r["signal"] == signal

    return StreamingResponse(_stream(_match), media_type="text/event-stream")


@app.get("/")
async def root():
    return JSONResponse({
        "service": "factory-stream",
        "description": "Standalone live factory sensor feed (SSE).",
        "endpoints": ["/health", "/signals", "/latest", "/stream", "/stream/{machine}/{signal}", "POST /anomaly"],
    })


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=config.HOST, port=config.PORT)
