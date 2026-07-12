# factory-stream

A **standalone streaming data source** that simulates a factory's live sensor
feed. It represents the *external* equipment/SCADA layer — PAAIM ingests from
it exactly as it would from real machines.

It is intentionally **isolated** from the main app:
- Runs as its own service on its own port (`9100`).
- Has its own dependencies.
- Talks to nothing in `backend/` directly — agents *subscribe to it*, not the
  other way round. You can start, stop, or break it and the main PAAIM app is
  unaffected.

## What it does
- Generates realistic, continuously-updating sensor readings (temperature,
  vibration, pressure, energy) for the factory's machines.
- Streams them over **Server-Sent Events (SSE)** so any client — the PAAIM
  "Live Feed" page or an agent connector — can subscribe and receive live data.
- Lets you **inject an anomaly on demand** (spike a temperature, etc.) — the
  lever that makes a decision appear live during a demo.

## Run
```bash
cd factory-stream
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python main.py            # serves on http://localhost:9100
```

## Endpoints
| Method | Path | Purpose |
|---|---|---|
| GET  | `/health` | liveness |
| GET  | `/signals` | catalogue of machines + signals being streamed |
| GET  | `/latest` | snapshot of the most recent reading per signal |
| GET  | `/stream` | SSE — all signals, live |
| GET  | `/stream/{machine_id}/{signal}` | SSE — one signal, live |
| POST | `/anomaly` | inject an anomaly (e.g. `?machine_id=robot_arm_01&signal=temperature&duration=15`) |

## How PAAIM connects
An agent's connector is pointed at a `/stream/...` URL here. On connect it
opens the SSE stream and receives readings live. When a reading breaches the
agent's rule, the agent raises an event into PAAIM's pipeline → a decision.
