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
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class FieldMapping:
    raw: str                 # source field name, e.g. "MTR03_TORQUE"
    signal: str              # canonical signal, e.g. "torque"
    unit: str
    transform: str = "identity"
    resolved_by: str = "heuristic"   # standards | dictionary | heuristic | llm | manual
    confidence: float = 0.0
    confirmed_by: Optional[str] = None

    def to_dict(self) -> dict:
        return self.__dict__.copy()

    @classmethod
    def from_dict(cls, d: dict) -> "FieldMapping":
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
        }

    @classmethod
    def from_dict(cls, d: dict) -> "SourceMapping":
        return cls(
            source_id=d["source_id"],
            machine_id_strategy=d.get("machine_id_strategy", "static"),
            machine_id_value=d.get("machine_id_value", "unknown"),
            fields={k: FieldMapping.from_dict(v) for k, v in (d.get("fields") or {}).items()},
            unmapped=d.get("unmapped", []),
            version=d.get("version", 1),
            confirmed=d.get("confirmed", False),
        )


class MappingStore:
    """JSON-backed store of SourceMappings, keyed by source_id."""

    def __init__(self, path: str = "source_mappings.json"):
        self.path = path
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


_store: Optional[MappingStore] = None


def get_mapping_store() -> MappingStore:
    global _store
    if _store is None:
        _store = MappingStore()
    return _store
