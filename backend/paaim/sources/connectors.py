"""
Source connectors — reach a real system, prove it, and pull a real sample.

Two rules here, both learned the hard way:

1. **Never claim success you did not verify.** A connector that answers
   "connection OK" without a round-trip is worse than no connector: a plant
   wires up a wrong host, PAAIM says fine, and then quietly ingests nothing.
   Every check below performs an actual request and reports what came back.

2. **An unsupported protocol says so.** OPC-UA and Modbus need real drivers
   (`asyncua`, `pymodbus`). Until those are in, they fail loudly with the reason
   rather than pretending — an honest "not supported yet" is a fixable problem;
   a silent lie is a plant trial that fails on day one for unknown reasons.

`discover` returns a payload in exactly the shape the source really sends, so
the mapping layer maps against reality instead of a hand-typed guess.
"""

from __future__ import annotations

import importlib
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx

# type → (label, what the endpoint means, whether we can do it today)
SOURCE_TYPES: List[Dict[str, Any]] = [
    {
        "type": "sse_stream",
        "label": "Live stream (SSE)",
        "endpoint_hint": "http://host:9100",
        "supported": True,
        "description": "Server-sent events feed. PAAIM subscribes and watches each signal live.",
    },
    {
        "type": "rest_poll",
        "label": "REST API (polled)",
        "endpoint_hint": "https://host/api/readings",
        "supported": True,
        "description": "PAAIM calls this URL on an interval and reads the JSON it returns.",
    },
    {
        "type": "rest_push",
        "label": "REST push (historian → PAAIM)",
        "endpoint_hint": "(no endpoint — your system posts to PAAIM)",
        "supported": True,
        "description": "Your historian/middleware POSTs readings to /api/normalization/ingest.",
    },
    {
        "type": "opcua",
        "label": "OPC-UA",
        "endpoint_hint": "opc.tcp://host:4840",
        "supported": False,
        "requires": "asyncua",
        "description": "Not available yet: the asyncua driver is not installed.",
    },
    {
        "type": "modbus",
        "label": "Modbus TCP",
        "endpoint_hint": "host:502",
        "supported": False,
        "requires": "pymodbus",
        "description": "Not available yet: the pymodbus driver is not installed.",
    },
    {
        "type": "mqtt",
        "label": "MQTT",
        "endpoint_hint": "mqtt://host:1883",
        "supported": False,
        "requires": "paho-mqtt",
        "description": "Not available yet: the paho-mqtt driver is not installed.",
    },
]

_BY_TYPE = {t["type"]: t for t in SOURCE_TYPES}


@dataclass
class ConnectionResult:
    ok: bool
    detail: str
    latency_ms: Optional[float] = None
    checked_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> dict:
        return self.__dict__.copy()


@dataclass
class DiscoveryResult:
    ok: bool
    detail: str
    sample_payload: Dict[str, Any] = field(default_factory=dict)
    machine_id_field: Optional[str] = None
    fields_found: List[str] = field(default_factory=list)
    # What the source says each field is measured in, where it says anything.
    # Discovery used to read this straight off the wire and drop it, leaving the
    # mapper to assume the source already spoke the vocabulary's units — which
    # is how a °C tag became a Kelvin signal with no conversion. See
    # paaim.normalization.units.
    field_units: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return self.__dict__.copy()


def unwrap_payloads(body: Any) -> List[Dict[str, Any]]:
    """
    Pull the reading objects out of whatever shape a source answers with.

    Historians rarely return a bare object: PI, Ignition and most REST layers
    wrap their rows in an envelope ({"readings": [...]}, {"data": [...]}).
    Handling only dict-or-list meant such a source connected, mapped and polled
    happily while yielding zero readings — healthy-looking and inert.

    Covers the common shapes. A genuinely odd schema needs an operator-supplied
    path, which is honest to say rather than guess at.
    """
    if isinstance(body, list):
        return [x for x in body if isinstance(x, dict)]
    if not isinstance(body, dict):
        return []
    # a single-key envelope around the rows
    if len(body) == 1:
        only = next(iter(body.values()))
        if isinstance(only, list):
            return [x for x in only if isinstance(x, dict)]
        if isinstance(only, dict):
            return [only]
    # a well-known envelope key alongside metadata
    for key in ("readings", "data", "items", "results", "values", "rows"):
        v = body.get(key)
        if isinstance(v, list) and v and isinstance(v[0], dict):
            return [x for x in v if isinstance(x, dict)]
    return [body]          # already flat


# Field names a source might use to say "this row is about this tag".
_TAG_KEYS = ("signal", "tag", "tag_name", "name", "point", "pointid", "item")
_VALUE_KEYS = ("value", "val", "reading", "v")
_MACHINE_KEYS = ("machine_id", "device_id", "asset_id", "equipment_id", "asset")
# ...and what it is measured in. Historians commonly carry engineering units on
# each row; a wide payload almost never does.
_UNIT_KEYS = ("unit", "units", "uom", "engineering_units", "eu")


def units_from_long(rows: List[Dict[str, Any]]) -> Dict[str, str]:
    """
    The declared unit per tag, from long-format rows.

    Separate from `pivot_long_to_wide` because the pivot's job is to produce the
    payload shape the mapper reads, and units are not part of that shape — they
    are what decides whether the mapping of it is correct.
    """
    def _key(row, candidates):
        return next((c for c in candidates if c in row), None)

    out: Dict[str, str] = {}
    for row in rows:
        tag_k, unit_k = _key(row, _TAG_KEYS), _key(row, _UNIT_KEYS)
        if tag_k and unit_k and isinstance(row.get(tag_k), str) and row.get(unit_k):
            out[row[tag_k]] = str(row[unit_k])
    return out


def pivot_long_to_wide(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Turn long-format readings into the wide rows the mapping layer expects.

    Two conventions exist in the wild and PAAIM only understood one:

        wide  {"machine_id": "m1", "TT_101": 68.1, "PT_HYD": 5.2}   ← assumed
        long  [{"machine_id": "m1", "tag": "TT_101", "value": 68.1},
               {"machine_id": "m1", "tag": "PT_HYD", "value": 5.2}]  ← ignored

    Long is what most historians and tag-query APIs return (PI Web API among
    them), and against it every mapped field missed and the source ingested
    nothing. Rows are grouped by machine so one poll yields one payload per
    machine, exactly as if the source had answered wide.

    Rows that are already wide are passed through untouched.
    """
    def _key(row: Dict[str, Any], candidates) -> Optional[str]:
        for c in candidates:
            if c in row:
                return c
        return None

    out: List[Dict[str, Any]] = []
    grouped: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        tag_k = _key(row, _TAG_KEYS)
        val_k = _key(row, _VALUE_KEYS)
        # Long only if the tag field names a tag and the value field holds a number.
        if not tag_k or not val_k or not isinstance(row.get(tag_k), str):
            out.append(row)
            continue
        try:
            value = float(row[val_k])
        except (TypeError, ValueError):
            out.append(row)
            continue

        mach_k = _key(row, _MACHINE_KEYS)
        mach_id = str(row.get(mach_k)) if mach_k else "unknown"
        bucket = grouped.setdefault(mach_id, {mach_k or "machine_id": mach_id})
        bucket[row[tag_k]] = value

    out.extend(grouped.values())
    return out


def _auth_headers(auth_type: Optional[str], auth_config: Optional[Dict[str, str]]) -> Dict[str, str]:
    cfg = auth_config or {}
    if auth_type == "bearer" and cfg.get("token"):
        return {"Authorization": f"Bearer {cfg['token']}"}
    if auth_type == "api_key" and cfg.get("key"):
        return {cfg.get("header", "X-API-Key"): cfg["key"]}
    return {}


def _unsupported(type_: str) -> ConnectionResult:
    meta = _BY_TYPE.get(type_)
    if not meta:
        return ConnectionResult(False, f"Unknown source type '{type_}'.")
    driver = meta.get("requires")
    installed = False
    if driver:
        try:
            importlib.import_module(driver.replace("-", "_"))
            installed = True
        except ImportError:
            installed = False
    if installed:
        return ConnectionResult(
            False,
            f"{meta['label']}: driver '{driver}' is installed but PAAIM has no "
            f"implementation for it yet.",
        )
    return ConnectionResult(
        False,
        f"{meta['label']} is not supported yet — requires the '{driver}' driver, "
        f"which is not installed. Use REST push or a live stream for now.",
    )


async def test_connection(
    type: str,
    endpoint: str = "",
    auth_type: Optional[str] = None,
    auth_config: Optional[Dict[str, str]] = None,
    timeout: float = 8.0,
) -> ConnectionResult:
    """Actually reach the source. No result here is ever assumed."""
    meta = _BY_TYPE.get(type)
    if not meta:
        return ConnectionResult(False, f"Unknown source type '{type}'.")
    if not meta.get("supported"):
        return _unsupported(type)

    if type == "rest_push":
        return ConnectionResult(
            True,
            "Push source: PAAIM makes no outbound connection. Your system POSTs "
            "readings to /api/normalization/ingest — nothing to test from here.",
        )

    if not endpoint:
        return ConnectionResult(False, "An endpoint is required for this source type.")

    url = endpoint.rstrip("/")
    if type == "sse_stream":
        url = f"{url}/health"

    t0 = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(url, headers=_auth_headers(auth_type, auth_config))
        ms = round((time.perf_counter() - t0) * 1000, 1)
    except httpx.ConnectError as e:
        return ConnectionResult(False, f"Cannot reach {url} — {e}")
    except httpx.TimeoutException:
        return ConnectionResult(False, f"Timed out after {timeout:.0f}s reaching {url}")
    except Exception as e:
        return ConnectionResult(False, f"Connection failed: {e}")

    if resp.status_code >= 400:
        return ConnectionResult(
            False, f"{url} answered HTTP {resp.status_code} — check the URL or credentials.",
            latency_ms=ms,
        )
    return ConnectionResult(True, f"Reached {url} — HTTP {resp.status_code}.", latency_ms=ms)


async def discover(
    type: str,
    endpoint: str = "",
    auth_type: Optional[str] = None,
    auth_config: Optional[Dict[str, str]] = None,
    timeout: float = 8.0,
) -> DiscoveryResult:
    """Pull one real sample so the mapping is made against what the source sends."""
    meta = _BY_TYPE.get(type)
    if not meta:
        return DiscoveryResult(False, f"Unknown source type '{type}'.")
    if not meta.get("supported"):
        return DiscoveryResult(False, _unsupported(type).detail)

    if type == "rest_push":
        return DiscoveryResult(
            False,
            "Push sources cannot be sampled — PAAIM cannot call them. Paste one "
            "example reading from your system instead.",
        )

    if not endpoint:
        return DiscoveryResult(False, "An endpoint is required to sample this source.")

    headers = _auth_headers(auth_type, auth_config)
    base = endpoint.rstrip("/")

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            if type == "sse_stream":
                resp = await client.get(f"{base}/latest", headers=headers)
                resp.raise_for_status()
                readings = resp.json().get("readings", [])
                if not readings:
                    return DiscoveryResult(False, "The feed is reachable but published no readings yet.")
                # Flatten to the shape the feed emits per machine: {machine_id, <tag>: value}
                sample: Dict[str, Any] = {"machine_id": readings[0].get("machine_id", "unknown")}
                units: Dict[str, str] = {}
                for r in readings:
                    if r.get("signal") is not None:
                        sample[r["signal"]] = r.get("value")
                        # The feed states the unit on every reading. Keeping it is
                        # the difference between mapping a tag and mapping it right.
                        if r.get("unit"):
                            units[r["signal"]] = str(r["unit"])
                declared = len(units)
                return DiscoveryResult(
                    True,
                    f"Found {len(sample) - 1} live signals on the feed"
                    + (f", {declared} with a declared unit." if declared else
                       " — none declare a unit, so their mapping cannot be unit-checked."),
                    sample_payload=sample,
                    machine_id_field="machine_id",
                    fields_found=[k for k in sample if k != "machine_id"],
                    field_units=units,
                )

            # rest_poll — whatever JSON object the endpoint returns is the sample
            resp = await client.get(base, headers=headers)
            resp.raise_for_status()
            body = resp.json()
    except httpx.HTTPStatusError as e:
        return DiscoveryResult(False, f"{base} answered HTTP {e.response.status_code}.")
    except httpx.ConnectError as e:
        return DiscoveryResult(False, f"Cannot reach {base} — {e}")
    except Exception as e:
        return DiscoveryResult(False, f"Could not sample the source: {e}")

    # Pivot here as well as in the poller: if onboarding samples a different
    # shape than runtime reads, the operator maps fields that never arrive.
    unwrapped = unwrap_payloads(body)
    rows = pivot_long_to_wide(unwrapped)
    if not rows:
        return DiscoveryResult(False, "Expected JSON readings from this endpoint; found none.")
    # Units survive only in the long form — the pivot is what discards them.
    units = units_from_long(unwrapped)
    body = rows[0]

    machine_field = next(
        (k for k in ("machine_id", "device_id", "asset_id", "equipment_id") if k in body), None
    )
    return DiscoveryResult(
        True,
        f"Sampled {len(body)} fields from the endpoint"
        + (f", {len(units)} with a declared unit." if units else
           " — no units declared, so their mapping cannot be unit-checked."),
        sample_payload=body,
        machine_id_field=machine_field,
        fields_found=[k for k in body if k != machine_field],
        field_units=units,
    )
