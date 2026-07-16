"""
SourceMapping — the cached, deterministic artifact.

Built ONCE per source (by the resolver, optionally with LLM help), confirmed by
a human, then used forever at runtime as a pure lookup table. No AI ever reads
this — it's just a dict. Persisted to JSON so it survives restarts (no DB
migration needed for this first slice).
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


def _safe_id(factory_id: str) -> str:
    """A factory id becomes a filename here, so it must not escape the directory."""
    s = re.sub(r"[^A-Za-z0-9_.-]", "_", (factory_id or "").strip())
    if not s or s in (".", ".."):
        raise ValueError(f"Unusable factory id: {factory_id!r}")
    return s


@dataclass
class FieldMapping:
    raw: str                 # source field name, e.g. "MTR03_TORQUE"
    signal: str              # canonical signal, e.g. "torque"
    unit: str                # the canonical unit — what `transform` converts INTO
    transform: str = "identity"
    resolved_by: str = "heuristic"   # standards | dictionary | heuristic | llm | manual
    confidence: float = 0.0
    confirmed_by: Optional[str] = None
    # What the source said it publishes, and what came of comparing that to the
    # signal's unit. A mapping used to record only the canonical unit, so a °C
    # tag mapped onto a Kelvin signal looked identical to a correct one — and
    # the reasoning downstream was handed a weld tip at 64 K. See units.py.
    source_unit: str = ""
    unit_status: str = "unknown"     # match | converted | conflict | unknown
    # Knowing what a tag MEANS and wanting an incident when it breaches are two
    # different intents: a plant maps hundreds of tags for context but only
    # alarms on a handful. Watching every mapped tag is the sane default for a
    # small line; large sites turn most of them off.
    watch: bool = True

    def to_dict(self) -> dict:
        return self.__dict__.copy()

    @classmethod
    def from_dict(cls, d: dict) -> "FieldMapping":
        return cls(**{k: d.get(k) for k in cls.__dataclass_fields__ if k in d})


@dataclass
class SourceConnection:
    """How PAAIM reaches a source. See paaim.sources.connectors for the drivers."""
    type: str = "rest_push"                 # sse_stream | rest_poll | rest_push | opcua | modbus | mqtt
    endpoint: str = ""                      # URL, or host:port
    auth_type: Optional[str] = None         # none | basic | bearer | api_key
    auth_config: Dict[str, str] = field(default_factory=dict)
    poll_interval_seconds: int = 30
    verified_at: Optional[str] = None       # last time a real connection test passed

    def to_dict(self) -> dict:
        """Full fidelity — this is what gets persisted, secrets included."""
        return self.__dict__.copy()

    def to_public_dict(self) -> dict:
        """For API responses: same shape, credentials redacted."""
        d = self.to_dict()
        d["auth_config"] = {k: "***" for k in (self.auth_config or {})}
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "SourceConnection":
        return cls(**{k: d.get(k) for k in cls.__dataclass_fields__ if k in d})


@dataclass
class SourceMapping:
    source_id: str
    machine_id_strategy: str = "static"     # static | field
    machine_id_value: str = "unknown"       # static id, OR the field name to read
    fields: Dict[str, FieldMapping] = field(default_factory=dict)  # raw -> FieldMapping
    unmapped: List[str] = field(default_factory=list)
    version: int = 1
    confirmed: bool = False
    # How the data physically arrives. None for sources that only ever push to
    # /normalization/ingest, where there is no outbound connection to make.
    connection: Optional[SourceConnection] = None

    def machine_id_for(self, raw_dict: dict) -> str:
        if self.machine_id_strategy == "field":
            return str(raw_dict.get(self.machine_id_value, "unknown"))
        return self.machine_id_value

    def to_dict(self) -> dict:
        return {
            "source_id": self.source_id,
            "machine_id_strategy": self.machine_id_strategy,
            "machine_id_value": self.machine_id_value,
            "fields": {k: v.to_dict() for k, v in self.fields.items()},
            "unmapped": self.unmapped,
            "version": self.version,
            "confirmed": self.confirmed,
            "connection": self.connection.to_dict() if self.connection else None,
        }

    def to_public_dict(self) -> dict:
        d = self.to_dict()
        d["connection"] = self.connection.to_public_dict() if self.connection else None
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "SourceMapping":
        conn = d.get("connection")
        return cls(
            source_id=d["source_id"],
            machine_id_strategy=d.get("machine_id_strategy", "static"),
            machine_id_value=d.get("machine_id_value", "unknown"),
            fields={k: FieldMapping.from_dict(v) for k, v in (d.get("fields") or {}).items()},
            unmapped=d.get("unmapped", []),
            version=d.get("version", 1),
            confirmed=d.get("confirmed", False),
            connection=SourceConnection.from_dict(conn) if conn else None,
        )


class MappingStore:
    """
    One factory's SourceMappings, JSON-backed and keyed by source_id.

    Per factory, not global. Two tenants routinely name a source the same
    obvious thing — "scada", "historian", "line1" — so a single store meant the
    second plant to connect silently overwrote the first's mapping, and every
    watcher built from it started translating one plant's tags with another
    plant's vocabulary.
    """

    def __init__(self, factory_id: str, dir_: Optional[str] = None):
        # Honour the tenant-state dir the container mounts as a volume, the same
        # one the vocabulary and monitor stores already use. Defaulting to the
        # relative "tenant_state" put mappings inside the container's working
        # directory — ephemeral — so every image rebuild silently wiped every
        # source mapping, and the watchers built from them, while vocab and
        # monitors (which read this env var) survived. That mismatch is why one
        # tenant kept losing its watchers across restarts and another did not.
        dir_ = dir_ or os.getenv("PAAIM_TENANT_STATE_DIR", "tenant_state")
        self.factory_id = factory_id
        os.makedirs(dir_, exist_ok=True)
        self.path = os.path.join(dir_, f"mappings_{_safe_id(factory_id)}.json")
        self._cache: Dict[str, SourceMapping] = {}
        self._load()

    def _load(self) -> None:
        try:
            with open(self.path, "r") as f:
                data = json.load(f)
            self._cache = {sid: SourceMapping.from_dict(m) for sid, m in data.items()}
            logger.info("Loaded %d source mappings", len(self._cache))
        except FileNotFoundError:
            pass
        except Exception as e:
            logger.warning("Could not load mappings: %s", e)

    def _save(self) -> None:
        try:
            with open(self.path, "w") as f:
                json.dump({sid: m.to_dict() for sid, m in self._cache.items()}, f, indent=2)
        except Exception as e:
            logger.error("Could not save mappings: %s", e)

    def get(self, source_id: str) -> Optional[SourceMapping]:
        return self._cache.get(source_id)

    def put(self, mapping: SourceMapping) -> None:
        self._cache[mapping.source_id] = mapping
        self._save()

    def list(self) -> List[SourceMapping]:
        return list(self._cache.values())


_stores: Dict[str, MappingStore] = {}


def get_mapping_store(factory_id: str) -> MappingStore:
    """This factory's mapping store. `factory_id` is required, deliberately."""
    if not factory_id:
        raise ValueError(
            "A source mapping belongs to a factory — pass the tenant's id. "
            "There is deliberately no global mapping store to fall back on."
        )
    if factory_id not in _stores:
        _stores[factory_id] = MappingStore(factory_id)
    return _stores[factory_id]


def all_mapping_stores() -> Dict[str, MappingStore]:
    """Every tenant loaded so far — for startup rehydration, not request paths."""
    return _stores


def load_all_tenants(dir_: Optional[str] = None) -> Dict[str, MappingStore]:
    dir_ = dir_ or os.getenv("PAAIM_TENANT_STATE_DIR", "tenant_state")
    """
    Discover every factory with saved mappings and load its store.

    Needed on boot: watchers are in-memory, so they are rebuilt from confirmed
    mappings at startup — and with the stores now per tenant, nothing would
    know which tenants exist until someone happened to log in.
    """
    try:
        names = os.listdir(dir_)
    except FileNotFoundError:
        return _stores
    for name in names:
        m = re.match(r"^mappings_(.+)\.json$", name)
        if m:
            get_mapping_store(m.group(1))
    return _stores
