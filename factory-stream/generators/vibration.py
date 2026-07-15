"""Vibration — RMS velocity. ISO 10816 bands where the plant uses them."""

from generators.base import SignalGenerator


class VibrationGenerator(SignalGenerator):
    kind = "vibration"
    unit = "mm/s"
