"""
Decide whether a reading is normal, warning or critical — using PAAIM's own
knowledge of the machine.

A watcher used to take the source's word for it:

    self.last_status = r.get("status", "normal")

That works for a feed that ships a verdict, and fails silently everywhere else.
A real historian or SCADA sends `{tag: 2.1}` — no opinion attached — so the
default fires: every reading is "normal", forever, on every machine. The plant
would see a connected, healthy-looking watcher that can never raise anything.

So PAAIM judges the value itself, in this order:

  1. **Learned normal (SPC)** — the machine's own mean ± σ from its history.
     Preferred: it is per machine, and a furnace running at 83°C is not a lathe
     running at 83°C.
  2. **Declared limits** — warn/critical the source publishes, if it does.
  3. **The source's own status** — only when it actually sent one.

If none of those exist we return `unknown`, not `normal`. A watcher that cannot
judge must say so rather than imply all is well.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

# Sigma multipliers for the learned band. 2σ ≈ the routine spread of a stable
# process, so beyond it is worth a look; beyond 3σ is a genuine excursion —
# standard SPC practice, and it means thresholds adapt per machine instead of
# one global number pretending to fit every asset.
WARN_SIGMA = 2.0
CRITICAL_SIGMA = 3.0


def judge(
    value: Optional[float],
    baseline: Optional[Dict[str, Any]] = None,
    declared: Optional[Dict[str, Any]] = None,
    source_status: Optional[str] = None,
    higher_is_worse: Optional[bool] = None,
) -> Tuple[str, str]:
    """
    Return (status, why).

    status ∈ {normal, warning, critical, unknown}. `why` is plain enough to put
    in front of an operator, because a threshold nobody understands is a
    threshold nobody trusts.
    """
    if value is None:
        return "unknown", "no value in the reading"

    # 1 — the machine's own learned normal
    if baseline:
        mean = baseline.get("mean")
        std = baseline.get("std")
        if mean is not None and std is not None and std > 0:
            dev = abs(value - mean) / std
            side = "above" if value > mean else "below"

            # Most signals only fail in one direction: vibration and temperature
            # are bad when high, hydraulic pressure when low. An idle machine sits
            # several sigma BELOW its running normal, so treating the band
            # symmetrically reports a stopped machine as a critical fault. Only
            # judge the direction that can actually hurt, when we know it.
            if higher_is_worse is not None:
                harmful = (value > mean) if higher_is_worse else (value < mean)
                if not harmful:
                    return "normal", (
                        f"{value:g} is {dev:.1f}σ {side} normal ({mean:g} ± {std:g}) — "
                        f"not the direction that indicates a fault"
                    )

            if dev >= CRITICAL_SIGMA:
                return "critical", (
                    f"{value:g} is {dev:.1f}σ {side} this machine's normal "
                    f"({mean:g} ± {std:g})"
                )
            if dev >= WARN_SIGMA:
                return "warning", (
                    f"{value:g} is {dev:.1f}σ {side} this machine's normal "
                    f"({mean:g} ± {std:g})"
                )
            return "normal", f"{value:g} is within {dev:.1f}σ of normal ({mean:g} ± {std:g})"

        # A learned range with no usable spread still beats nothing.
        rng = baseline.get("normal_range")
        if isinstance(rng, (list, tuple)) and len(rng) == 2 and rng[0] is not None:
            lo, hi = float(rng[0]), float(rng[1])
            if value < lo or value > hi:
                return "warning", f"{value:g} is outside the learned normal range [{lo:g}, {hi:g}]"
            return "normal", f"{value:g} is inside the learned normal range [{lo:g}, {hi:g}]"

    # 2 — limits the source publishes for this instrument
    if declared:
        warn = declared.get("warn")
        crit = declared.get("critical")
        higher_worse = declared.get("higher_is_worse", True)
        if crit is not None:
            breached = value >= crit if higher_worse else value <= crit
            if breached:
                return "critical", f"{value:g} breached the instrument's critical limit ({crit:g})"
        if warn is not None:
            breached = value >= warn if higher_worse else value <= warn
            if breached:
                return "warning", f"{value:g} breached the instrument's warning limit ({warn:g})"
        if warn is not None or crit is not None:
            return "normal", f"{value:g} is inside the instrument's declared limits"

    # 3 — the source's own verdict, but only if it really sent one
    if source_status:
        return source_status, f"reported '{source_status}' by the source"

    # Nothing to judge against. Say so — do not imply health.
    return "unknown", (
        "no learned baseline, no declared limits, and the source sends no status — "
        "PAAIM cannot tell whether this reading is normal"
    )
