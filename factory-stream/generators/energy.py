"""Rate-like signal — power draw, line speed. Direction is the plant's."""

from generators.base import SignalGenerator


class EnergyGenerator(SignalGenerator):
    kind = "energy"
    unit = "kW"
