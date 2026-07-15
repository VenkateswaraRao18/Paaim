"""Pressure. Direction is the plant's to state — a hydraulic press fails low,
a vessel can fail high."""

from generators.base import SignalGenerator


class PressureGenerator(SignalGenerator):
    kind = "pressure"
    unit = "bar"
