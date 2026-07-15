"""Builds the fleet of signal generators from the config catalogue."""

from typing import Dict, Tuple

from generators.base import SignalGenerator, Reading
from generators.temperature import TemperatureGenerator
from generators.vibration import VibrationGenerator
from generators.pressure import PressureGenerator
from generators.energy import EnergyGenerator

_KIND_MAP = {
    "temperature": TemperatureGenerator,
    "vibration": VibrationGenerator,
    "pressure": PressureGenerator,
    "energy": EnergyGenerator,
}

# How lively each physics model is, and the noise it was tuned against. Only
# used to keep the wander proportional when a plant measures on a different
# scale — a 38 °F chiller and a 520 kW cluster cannot share an absolute drift.
# Transcribed from the generator classes, so the CNC plant behaves exactly as it
# did before the catalogue took over (scale == 1.0 for every CNC signal).
_SHAPE = {
    "temperature": {"daily_amplitude": 2.5, "drift": 0.4,  "ref_noise": 1.6},
    "vibration":   {"daily_amplitude": 0.4, "drift": 0.12, "ref_noise": 0.35},
    "pressure":    {"daily_amplitude": 0.2, "drift": 0.08, "ref_noise": 0.18},
    "energy":      {"daily_amplitude": 60.0, "drift": 8.0, "ref_noise": 22.0},
}


def build_fleet(catalogue) -> Dict[Tuple[str, str], SignalGenerator]:
    """
    catalogue: (machine_id, kind, tag, label, unit, baseline, noise, warn,
                critical, higher_is_worse)
        → {(machine_id, tag): generator}

    Keyed by the SCADA tag, since that is what the feed publishes and what
    subscribers address (`/stream/{machine_id}/{tag}`).

    `kind` now chooses only the *shape* of the physics. Every number — baseline,
    limits, unit, and which direction is a fault — comes from the plant's own
    catalogue. While those lived in the generator classes, the simulator could
    only ever be one factory: a temperature generator that hardcoded 68 °C and
    "higher is worse" cannot be a chiller at 38 °F or a pasteuriser whose fault
    is the pressure falling.
    """
    fleet: Dict[Tuple[str, str], SignalGenerator] = {}
    for (machine_id, kind, tag, label, unit,
         baseline, noise, warn, critical, higher_is_worse) in catalogue:
        cls = _KIND_MAP.get(kind, SignalGenerator)
        shape = _SHAPE.get(kind, {})
        scale = noise / max(shape.get("ref_noise", noise), 1e-6)
        fleet[(machine_id, tag)] = cls(
            machine_id=machine_id, label=label, tag=tag, unit=unit,
            baseline=baseline, noise=noise, warn=warn, critical=critical,
            higher_is_worse=higher_is_worse,
            daily_amplitude=shape.get("daily_amplitude", 0.0) * scale,
            drift=shape.get("drift", 0.0) * scale,
        )
    return fleet


__all__ = ["build_fleet", "SignalGenerator", "Reading"]
