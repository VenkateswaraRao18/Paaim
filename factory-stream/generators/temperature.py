"""Thermal signal. Baseline, limits, unit and direction come from the plant."""

from generators.base import SignalGenerator


class TemperatureGenerator(SignalGenerator):
    # Only the shape of the physics lives here now. This class used to hardcode
    # 68 °C / warn 82 / crit 90 / higher-is-worse, which meant it could simulate
    # a CNC spindle and nothing else — not a 38 °F chiller, not a 500 g filler.
    kind = "temperature"
    unit = "°C"          # fallback only; the catalogue states the real unit
