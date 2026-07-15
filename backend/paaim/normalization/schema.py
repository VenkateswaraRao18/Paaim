"""
Canonical signal schema — the target every data source is mapped INTO.

The whole point of the normalization layer: a Modbus register, an MQTT payload,
an OPC-UA node and a vendor JSON blob all look different, but they must all end
up speaking ONE vocabulary before entering the pipeline. This file defines that
vocabulary and the canonical reading shape.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Dict


# ── Controlled signal vocabulary ───────────────────────────────────────────────
# There is deliberately no SIGNAL_VOCAB here any more.
#
# It was a module-level dict seeded with the CNC pack, which the vocabulary store
# then "replaced in place" so that every importer picked the plant's signals up
# for free. Convenient, and single-tenant by construction: one process serving a
# dairy and a machine shop had exactly one vocabulary, and whichever tenant
# configured theirs last silently redefined the other's signals — no error, no
# log, just a filling line whose tags suddenly meant spindle torque.
#
# A vocabulary belongs to a factory. Ask for one by tenant:
#
#     from paaim.normalization.vocabulary import vocab_for, direction_for
#     vocab = vocab_for(factory_id)
#
# and pass it to whatever needs to resolve a signal. Starter packs live in
# paaim.normalization.vocabulary; plants edit their own copy.


# ── Unit transforms ────────────────────────────────────────────────────────────
# Every transform must be monotonically increasing. Thresholds and learned
# baselines are converted through these same functions, and an order-reversing
# transform would silently invert "over the limit" into "under it".
def _identity(v: float) -> float: return v
def _celsius_to_k(v: float) -> float: return v + 273.15
def _kelvin_to_c(v: float) -> float: return v - 273.15
# Fahrenheit is not an edge case: most US plants publish it, and a mapping that
# cannot carry °F into a °C signal would reject them as an unresolvable conflict.
def _f_to_c(v: float) -> float: return (v - 32.0) * 5.0 / 9.0
def _c_to_f(v: float) -> float: return v * 9.0 / 5.0 + 32.0
def _f_to_k(v: float) -> float: return (v - 32.0) * 5.0 / 9.0 + 273.15
def _k_to_f(v: float) -> float: return (v - 273.15) * 9.0 / 5.0 + 32.0
def _scale_1000(v: float) -> float: return v / 1000.0    # W → kW
def _scale_0_001(v: float) -> float: return v * 1000.0   # kW → W
def _psi_to_bar(v: float) -> float: return v * 0.0689475729
def _bar_to_psi(v: float) -> float: return v / 0.0689475729
def _kpa_to_bar(v: float) -> float: return v / 100.0
def _bar_to_kpa(v: float) -> float: return v * 100.0

TRANSFORMS: Dict[str, Callable[[float], float]] = {
    "identity": _identity,
    "celsius_to_k": _celsius_to_k,
    "kelvin_to_c": _kelvin_to_c,
    "fahrenheit_to_c": _f_to_c,
    "celsius_to_f": _c_to_f,
    "fahrenheit_to_k": _f_to_k,
    "kelvin_to_f": _k_to_f,
    "scale_1000": _scale_1000,
    "scale_0_001": _scale_0_001,
    "psi_to_bar": _psi_to_bar,
    "bar_to_psi": _bar_to_psi,
    "kpa_to_bar": _kpa_to_bar,
    "bar_to_kpa": _bar_to_kpa,
}


@dataclass
class CanonicalReading:
    """One reading in PAAIM's own language, ready for the pipeline."""
    factory_id: str
    machine_id: str
    signal_name: str      # a key from SIGNAL_VOCAB
    value: float
    unit: str
    raw_field: str        # provenance: the original source field name
    event_type: str = "maintenance"
    quality: str = "good"
    timestamp: str = ""

    def to_dict(self) -> dict:
        return {
            "factory_id": self.factory_id,
            "machine_id": self.machine_id,
            "signal_name": self.signal_name,
            "value": self.value,
            "unit": self.unit,
            "raw_field": self.raw_field,
            "event_type": self.event_type,
            "quality": self.quality,
            "timestamp": self.timestamp or datetime.utcnow().isoformat(),
        }

    def to_event(self, confidence: float = 0.9) -> dict:
        """Shape the reading as a pipeline event (matches what StreamAgent publishes)."""
        return {
            "event_type": self.event_type,
            "source_agent": f"connector::{self.raw_field}",
            "factory_id": self.factory_id,
            "machine_id": self.machine_id,
            "signal_value": float(self.value),
            "signal_name": self.signal_name,
            "confidence": confidence,
            "timestamp": self.timestamp or datetime.utcnow().isoformat(),
            "context": {"source": "normalizer", "unit": self.unit, "raw_field": self.raw_field},
        }
