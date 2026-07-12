"""Vibration signal — RMS velocity (mm/s). Higher is worse. ISO 10816 bands."""

from generators.base import SignalGenerator


class VibrationGenerator(SignalGenerator):
    kind = "vibration"
    unit = "mm/s"

    def __init__(self, machine_id: str, label: str):
        super().__init__(
            machine_id=machine_id, label=label,
            baseline=2.8, noise=0.35, warn=4.5, critical=7.1,
            higher_is_worse=True, daily_amplitude=0.4, drift=0.12,
        )
