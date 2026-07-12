"""Hydraulic pressure (bar). Lower is worse — a drop signals a leak/fault."""

from generators.base import SignalGenerator


class PressureGenerator(SignalGenerator):
    kind = "pressure"
    unit = "bar"

    def __init__(self, machine_id: str, label: str):
        super().__init__(
            machine_id=machine_id, label=label,
            baseline=5.4, noise=0.18, warn=3.5, critical=2.2,
            higher_is_worse=False, daily_amplitude=0.2, drift=0.08,
        )
