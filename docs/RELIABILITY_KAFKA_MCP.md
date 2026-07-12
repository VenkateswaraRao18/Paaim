# Reliable Data Feeds & Processing — Event Bus + MCP

Addresses the professor's note: *"see how we can make the data feeds and
processing reliable — perhaps Apache Kafka with MCP."*

Two additions move PAAIM from a best-effort alerter to a dependable decision
control tower:

1. **Event Bus** — a reliable, durable, replayable ingestion backbone.
2. **MCP server** — standardised, auditable access to the Factory Context Graph.

---

## 1. Event Bus — reliable ingestion

### Before
```
SCADA / MES / sensors ──HTTP POST──▶ /orchestrate  (synchronous, in-request)
```
If PAAIM was down, slow, or restarted, events were **silently lost**. No replay,
no back-pressure, no decoupling.

### After
```
producers ──▶  factory.events  (durable, ordered-per-machine, replayable)
                     │
        PAAIM consumer group ──▶ orchestrate ──▶ persist ──▶ commit offset
                     │                                  │
            handler fails                         factory.decisions
                     ▼
            factory.events.dlq  (dead-letter — poison events can't wedge the line)
```

**Guarantees**
- **Durability** — every event is appended to a log *before* processing.
- **At-least-once** — the consumer commits its offset only *after* the pipeline
  succeeds; a crash mid-processing re-delivers the event instead of dropping it.
- **Replay** — reset the consumer offset to reprocess history (e.g. after a
  policy change) — `POST /api/events/stream/replay?from_offset=0`.
- **Ordering** — partition key = `machine_id`, so one machine's events stay ordered.
- **Back-pressure & decoupling** — producers just append; the consumer drains at
  its own pace.

### Pluggable backends (one interface, `paaim/bus/`)
| Backend | When | Infra |
|---|---|---|
| `memory` (default) — `DurableLocalBus` | dev / demo / single node | none — durable JSONL log on disk |
| `kafka` — `KafkaEventBus` (aiokafka) | production | Kafka broker |

The "memory" backend is **genuinely durable** (append-only log + persisted
offsets), so the full reliability story — durability, at-least-once, replay,
DLQ — is demonstrable today with zero infrastructure. Switching to Kafka is a
config change, no application-code change:

```bash
# .env
EVENT_BUS=kafka
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
```
The Kafka producer uses `acks=all` + idempotence (no loss / no dupes on retry);
the consumer uses manual commit (at-least-once); failures route to the DLQ.

### Try it
```bash
# publish an event to the durable log (returns immediately)
curl -X POST localhost:8000/api/events/stream/publish -H 'Content-Type: application/json' -d '{
  "event_type":"maintenance","source_agent":"sensor","factory_id":"factory_001",
  "machine_id":"robot_arm_01","signal_value":210,"signal_name":"tool_wear_degradation",
  "confidence":0.95,"timestamp":"2026-06-15T11:00:00"}'

# watch it get consumed → decision produced; check lag / offsets
curl localhost:8000/api/events/stream/status

# replay everything from the start
curl -X POST 'localhost:8000/api/events/stream/replay?from_offset=0'
```
The background consumer (started on app startup) drains `factory.events`,
runs the 7-layer pipeline, persists the decision, and publishes a summary to
`factory.decisions` keyed by machine.

### Production path with Kafka (when ready)
`docker compose` a broker, set `EVENT_BUS=kafka`, create topics
`factory.events` (N partitions), `factory.decisions`, `factory.events.dlq`.
Scale by adding consumer instances (one per partition).

---

## 2. MCP server — standardised context access

The **Factory Context Graph** (machines, work orders, customers, materials,
maintenance, NCRs, costs) is exposed over the **Model Context Protocol** so any
MCP client — Claude Desktop, external agents, or our own agents — reads the same
operational truth through one open, auditable interface instead of bespoke calls.

`paaim/mcp_server/` — spec-compliant JSON-RPC 2.0 over stdio, hand-rolled
(the official `mcp` SDK needs Python ≥3.10; this runs on 3.9, no new dependency).

**Resources** (read-only context)
- `factory://summary` · `factory://machines` · `factory://work-orders` · `factory://ncrs`

**Tools** (callable)
- `get_factory_summary(factory_id)`
- `get_machine_context(factory_id, machine_id)` — the full context an agent sees
- `list_open_ncrs(factory_id)`
- `simulate_action_cost(action_name)` — Decision Twin impact estimate

### Run / register
```bash
cd backend && source venv/bin/activate
python -m paaim.mcp_server          # speaks MCP over stdio
```
Claude Desktop (`claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "paaim-factory": {
      "command": "/abs/path/backend/venv/bin/python",
      "args": ["-m", "paaim.mcp_server"],
      "cwd": "/abs/path/backend"
    }
  }
}
```
Then ask Claude things like *"What's the operational context on robot_arm_01?"*
and it pulls live factory data through the protocol.

---

## How they fit together
```
   sensors/MES ─▶ Event Bus (reliable feed) ─▶ Orchestrator ─▶ Decisions
                                                    ▲
                                                    │ context via
                                          MCP server (Factory Context Graph)
                                                    ▲
                                   agents / Claude Desktop / external tools
```
Reliable **in** (bus), standardised **context** (MCP), governed decisions **out**.
