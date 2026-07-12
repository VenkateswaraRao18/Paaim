"""Temperature signal — welding/spindle stations (°C). Higher is worse."""

from generators.base import SignalGenerator


class TemperatureGenerator(SignalGenerator):
    kind = "temperature"
    unit = "°C"

    def __init__(self, machine_id: str, label: str):
        super().__init__(
            machine_id=machine_id, label=label,
            baseline=68.0, noise=1.6, warn=82.0, critical=90.0,
            higher_is_worse=True, daily_amplitude=2.5, drift=0.4,
        )
