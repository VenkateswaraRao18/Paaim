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


def build_fleet(catalogue) -> Dict[Tuple[str, str], SignalGenerator]:
    """catalogue: list of (machine_id, kind, label) → {(machine_id, kind): generator}."""
    fleet: Dict[Tuple[str, str], SignalGenerator] = {}
    for machine_id, kind, label in catalogue:
        cls = _KIND_MAP.get(kind)
        if not cls:
            continue
        fleet[(machine_id, kind)] = cls(machine_id, label)
    return fleet


__all__ = ["build_fleet", "SignalGenerator", "Reading"]
