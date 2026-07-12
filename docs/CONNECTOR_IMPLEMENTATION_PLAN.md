# PAAIM Connector Implementation Plan

## Context

PAAIM is an **on-premise product** deployed inside the factory's own network.
PAAIM's server runs on the same LAN as SCADA, PLCs, MES, and IoT brokers — so direct
TCP connections to industrial protocols are valid and expected.

This is NOT a cloud product. No edge agent needed. No VPN tunnels.

---

## Current State (as of Phase 3)

The connector classes exist in `backend/paaim/agents/custom_framework.py` and
`backend/paaim/connectors/` but use **stub implementations** — they simulate
connection success and return hardcoded/mock data instead of reading real signals.

| Connector | File | Status |
|---|---|---|
| `SCADAConnector` | `custom_framework.py` | Stub — returns `0.0` for every tag |
| `CMSConnector` | `custom_framework.py` | Stub — returns hardcoded orders |
| `IoTConnector` | `custom_framework.py` | Stub — returns `25.5` for every topic |
| `RESTAPIConnector` | `custom_framework.py` | **Real** — uses `httpx`, works now |
| `ERPConnector` | `connectors/erp.py` | Real OAuth2 + mock fallback |
| `MESConnector` | `connectors/mes.py` | Check current state |
| `CMMSConnector` | `connectors/cmms.py` | Check current state |

---

## What Needs to Be Built

### 1. SCADA Connector — Modbus TCP + OPC-UA

**Library choices:**
- Modbus TCP: `pymodbus` (most mature, async support)
- OPC-UA: `asyncua` (async, actively maintained)

**Config fields the UI already collects:**
- `host`, `port`, `timeout`, `tags` (comma-separated tag names)

**Implementation sketch:**

```python
# Modbus TCP path
from pymodbus.client import AsyncModbusTcpClient

class SCADAConnector(DataSourceConnector):
    async def connect(self) -> bool:
        protocol = self.config.get("protocol", "modbus")
        if protocol == "modbus":
            self.client = AsyncModbusTcpClient(
                host=self.config["host"],
                port=int(self.config.get("port", 502)),
                timeout=int(self.config.get("timeout", 5)),
            )
            return await self.client.connect()
        elif protocol == "opcua":
            from asyncua import Client
            self.client = Client(url=f"opc.tcp://{self.config['host']}:{self.config.get('port', 4840)}")
            await self.client.connect()
            return True

    async def fetch_data(self, query=None) -> dict:
        tags = self.config.get("tags", "").split(",")
        data = {}
        for tag in tags:
            tag = tag.strip()
            # Modbus: read holding register by address
            # OPC-UA: read node by NodeId
            result = await self.client.read_holding_registers(address=0, count=1)
            data[tag] = result.registers[0] if result else None
        return data
```

**pip packages to add:**
```
pymodbus>=3.6.0
asyncua>=1.0.0
```

---

### 2. CMS / MES Connector — HTTP

The MES already has a connector at `backend/paaim/connectors/mes.py`. The custom
agent `CMSConnector` in `custom_framework.py` should delegate to it or be replaced.

**Config fields collected:**
- `host`, `port`, `username`, `password`, `api_prefix`

**Implementation:** straightforward `httpx.AsyncClient` with Basic auth or session token.
The existing `mes.py` connector is the reference.

---

### 3. IoT Connector — MQTT

**Library choice:** `asyncio-mqtt` (wraps `paho-mqtt` with async support)

**Config fields collected:**
- `broker_host`, `broker_port`, `topics` (comma-separated), `client_id`, `username`, `password`

**Implementation sketch:**

```python
import asyncio_mqtt as mqtt

class IoTConnector(DataSourceConnector):
    async def connect(self) -> bool:
        self._client = mqtt.Client(
            hostname=self.config["broker_host"],
            port=int(self.config.get("broker_port", 1883)),
            username=self.config.get("username"),
            password=self.config.get("password"),
        )
        # Connection tested in fetch_data via async context manager
        return True

    async def fetch_data(self, query=None) -> dict:
        topics = self.config.get("topics", "sensors/#").split(",")
        data = {}
        async with self._client as client:
            async with client.messages() as messages:
                for topic in topics:
                    await client.subscribe(topic.strip())
                # Collect one message per topic with timeout
                async with asyncio.timeout(5):
                    async for msg in messages:
                        data[str(msg.topic)] = msg.payload.decode()
                        if len(data) >= len(topics):
                            break
        return data
```

**pip package to add:**
```
asyncio-mqtt>=0.16.0
```

---

### 4. Database Connector

Not yet implemented. Config field `connection_string` is already collected in the UI.

**Implementation sketch:**

```python
import asyncpg  # for PostgreSQL
# or use SQLAlchemy async engine for multi-DB support

class DatabaseConnector(DataSourceConnector):
    async def connect(self) -> bool:
        self.pool = await asyncpg.create_pool(self.config["connection_string"])
        return self.pool is not None

    async def fetch_data(self, query=None) -> dict:
        sql = query or self.config.get("query", "SELECT 1")
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(sql)
            return {"rows": [dict(r) for r in rows]}
```

**pip package to add:**
```
asyncpg>=0.29.0
```

---

## Where to Make Changes

| File | Change |
|---|---|
| `backend/paaim/agents/custom_framework.py` | Replace stub `SCADAConnector`, `CMSConnector`, `IoTConnector` with real implementations |
| `backend/paaim/agents/custom_framework.py` | Add `DatabaseConnector` class + register it in `get_connector_for_source()` |
| `backend/requirements.txt` | Add `pymodbus`, `asyncua`, `asyncio-mqtt`, `asyncpg` |
| `frontend/app/custom-agents/page.tsx` | UI already has all config fields — no changes needed |
| `backend/paaim/api/custom_agents.py` | No changes needed — test-connection endpoint already wired |

---

## Testing Plan (per connector)

Once implemented, test each connector against a local simulator before factory deployment:

- **Modbus**: run `pymodbus.simulator` or `diagslave` locally
- **OPC-UA**: run `python-opcua` demo server
- **MQTT**: run `mosquitto` locally (`brew install mosquitto`)
- **Database**: use the existing PostgreSQL from `docker-compose.yml`

---

## Professor Review Notes

- Defer real protocol implementation until after professor review
- Current stubs are sufficient for demo: test-connection returns `success: true`, 
  data-stream SSE sends simulated values, rules engine evaluates against mock data
- The architecture decision (on-prem, direct TCP to SCADA) is correct and should 
  be highlighted in the review as a differentiator vs cloud-first IIoT platforms

---

## Resume Checklist

- [ ] Install protocol libraries in `requirements.txt`
- [ ] Implement `SCADAConnector` (Modbus first, OPC-UA second)
- [ ] Implement `IoTConnector` with `asyncio-mqtt`
- [ ] Implement `DatabaseConnector` with `asyncpg`
- [ ] Update `CMSConnector` to delegate to existing `mes.py`
- [ ] Test each connector against local simulators
- [ ] Add protocol field to UI (Modbus vs OPC-UA for SCADA type)
- [ ] Update `DataSourceType` enum to add `OPC_UA` as separate entry
