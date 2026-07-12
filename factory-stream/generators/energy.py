"""Power draw (kW). Higher is worse — a spike signals overconsumption."""

from generators.base import SignalGenerator


class EnergyGenerator(SignalGenerator):
    kind = "energy"
    unit = "kW"

    def __init__(self, machine_id: str, label: str):
        super().__init__(
            machine_id=machine_id, label=label,
            baseline=560.0, noise=22.0, warn=780.0, critical=880.0,
            higher_is_worse=True, daily_amplitude=60.0, drift=8.0,
        )
