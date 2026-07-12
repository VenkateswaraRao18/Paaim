"""
Base signal generator.

Produces a realistic, continuously-wandering sensor value:
    value = baseline + daily_cycle + slow_drift + gaussian_noise

…and supports inject_anomaly(), which ramps the value into the warning/critical
band for a number of ticks and then recovers — the lever used to make a
decision appear live during a demo.
"""

from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Reading:
    machine_id: str
    signal: str
    label: str
    value: float
    unit: str
    status: str           # "normal" | "warning" | "critical"
    timestamp: str

    def to_dict(self) -> dict:
        return {
            "machine_id": self.machine_id,
            "signal": self.signal,
            "label": self.label,
            "value": round(self.value, 2),
            "unit": self.unit,
            "status": self.status,
            "timestamp": self.timestamp,
        }


class SignalGenerator:
    """Generic wandering-signal generator with anomaly injection."""

    kind: str = "generic"
    unit: str = ""

    def __init__(
        self,
        machine_id: str,
        label: str,
        baseline: float,
        noise: float,
        warn: float,
        critical: float,
        *,
        higher_is_worse: bool = True,
        daily_amplitude: float = 0.0,
        drift: float = 0.0,
    ):
        self.machine_id = machine_id
        self.label = label
        self.baseline = baseline
        self.noise = noise
        self.warn = warn
        self.critical = critical
        self.higher_is_worse = higher_is_worse
        self.daily_amplitude = daily_amplitude
        self.drift = drift

        self._t0 = time.time()
        self._drift_accum = 0.0
        self._anomaly_ticks = 0
        self._anomaly_target: Optional[float] = None

    # ── anomaly control ─────────────────────────────────────────────────────
    def inject_anomaly(self, duration: int = 12, magnitude: float = 1.0) -> None:
        """
        Drive the signal past its critical threshold for `duration` ticks.
        magnitude 1.0 ≈ sits just past critical; >1 pushes further.
        """
        span = abs(self.critical - self.baseline)
        if self.higher_is_worse:
            self._anomaly_target = self.critical + span * 0.25 * magnitude
        else:
            self._anomaly_target = self.critical - span * 0.25 * magnitude
        self._anomaly_ticks = max(1, duration)

    @property
    def in_anomaly(self) -> bool:
        return self._anomaly_ticks > 0

    # ── classification ──────────────────────────────────────────────────────
    def _status(self, value: float) -> str:
        if self.higher_is_worse:
            if value >= self.critical:
                return "critical"
            if value >= self.warn:
                return "warning"
        else:
            if value <= self.critical:
                return "critical"
            if value <= self.warn:
                return "warning"
        return "normal"

    # ── next reading ────────────────────────────────────────────────────────
    def next(self) -> Reading:
        elapsed = time.time() - self._t0

        # gentle daily cycle (compressed: a "day" every ~5 min so it's visible)
        cycle = self.daily_amplitude * math.sin(elapsed / 300.0 * 2 * math.pi)
        # slow random drift
        self._drift_accum += random.uniform(-self.drift, self.drift)
        self._drift_accum = max(-3 * self.noise, min(3 * self.noise, self._drift_accum))
        noise = random.gauss(0, self.noise)

        value = self.baseline + cycle + self._drift_accum + noise

        # if an anomaly is active, ramp toward the danger target then decay
        if self._anomaly_ticks > 0 and self._anomaly_target is not None:
            value = value * 0.4 + self._anomaly_target * 0.6 + random.gauss(0, self.noise)
            self._anomaly_ticks -= 1
            if self._anomaly_ticks == 0:
                self._anomaly_target = None

        return Reading(
            machine_id=self.machine_id,
            signal=self.kind,
            label=self.label,
            value=value,
            unit=self.unit,
            status=self._status(value),
            timestamp=datetime.utcnow().isoformat(),
        )
