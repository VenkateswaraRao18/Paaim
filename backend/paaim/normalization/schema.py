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
# Every canonical signal declares its expected unit, the pipeline event_type it
# maps to, and the raw field-name synonyms the heuristic resolver recognises.
SIGNAL_VOCAB: Dict[str, dict] = {
    "torque":              {"unit": "Nm",   "event_type": "maintenance", "synonyms": ["trq", "torque", "mtr_torque", "spindle_torque", "motor_torque"]},
    "process_temperature": {"unit": "K",    "event_type": "maintenance", "synonyms": ["proc_temp", "process_temp", "process_t", "process_temperature"]},
    "air_temperature":     {"unit": "K",    "event_type": "maintenance", "synonyms": ["air_temp", "ambient_temp", "air_temperature", "ambient"]},
    "temperature":         {"unit": "C",    "event_type": "maintenance", "synonyms": ["temp", "temperature", "temp_c", "tempc"]},
    "rotational_speed":    {"unit": "rpm",  "event_type": "maintenance", "synonyms": ["rpm", "speed", "rot_speed", "spindle_speed", "rotational_speed"]},
    "tool_wear":           {"unit": "min",  "event_type": "maintenance", "synonyms": ["wear", "tool_life", "tool_wear", "toolwear"]},
    "vibration":           {"unit": "mm/s", "event_type": "maintenance", "synonyms": ["vib", "vibration", "vibration_rms", "vibr"]},
    "pressure":            {"unit": "bar",  "event_type": "maintenance", "synonyms": ["press", "pressure", "hyd_pressure", "hydraulic_pressure"]},
    "coolant_pressure":    {"unit": "bar",  "event_type": "maintenance", "synonyms": ["coolant_press", "coolant_pressure", "coolant"]},
    "power":               {"unit": "kW",   "event_type": "energy",      "synonyms": ["kw", "power", "power_draw", "load_kw", "power_kw"]},
    "energy":              {"unit": "kWh",  "event_type": "energy",      "synonyms": ["kwh", "energy", "consumption", "energy_kwh"]},
}


# ── Unit transforms ────────────────────────────────────────────────────────────
def _identity(v: float) -> float: return v
def _celsius_to_k(v: float) -> float: return v + 273.15
def _kelvin_to_c(v: float) -> float: return v - 273.15
def _scale_1000(v: float) -> float: return v / 1000.0  # e.g. W → kW

TRANSFORMS: Dict[str, Callable[[float], float]] = {
    "identity": _identity,
    "celsius_to_k": _celsius_to_k,
    "kelvin_to_c": _kelvin_to_c,
    "scale_1000": _scale_1000,
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
