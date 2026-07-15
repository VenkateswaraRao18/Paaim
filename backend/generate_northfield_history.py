"""
Generate Northfield Foods' historian export — the plant's memory.

This is what a real site hands over: 30 days of its own tags, in its own units,
exported from the historian. Deliberately NOT canonical — °F, psi, raw tag names
— because that is what an export actually looks like, and because a history
upload that only works on pre-canonicalised data is a history upload no plant
can use.

The numbers are drawn around each instrument's true operating point with a
little machine-to-machine character (mixer_01 runs rougher than mixer_02, as an
older agitator would), so the learned baselines are per-machine rather than a
single fleet-wide number. That per-machine spread is the entire point of
learning: 4.0 mm/s is unremarkable on one agitator and a fault on another.
"""

from __future__ import annotations

import csv
import random
from datetime import datetime, timedelta

random.seed(7)   # reproducible: the same plant memory every run

OUT = "northfield_foods_history.csv"
DAYS = 30
SAMPLES_PER_DAY = 24          # hourly

# (machine_id, raw tag, mean, sigma) — the plant's own tags and units.
# Drawn from the SAME generators that drive the live feed, not hand-typed
# sigmas beside them.
#
# Hand-typing them was wrong in a way that only showed up live: fill weight got
# sd=2.1, while the live signal carries noise 2.2 AND a daily cycle on top. The
# learned 3σ band came out NARROWER than normal operation, so every filler was
# judged critical on a perfectly ordinary reading — a permanent incident storm,
# each one costing a 44-second Gemini call.
#
# A plant's history and its live feed come from the same machine. Here they must
# come from the same generator, or the baseline describes a factory that does
# not exist.
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "factory-stream"))
os.environ.setdefault("STREAM_PLANT", "food")
import config as _plant                      # noqa: E402
from generators import build_fleet           # noqa: E402

_FLEET = build_fleet(_plant.SIGNALS)
INSTRUMENTS = [(m, tag) for (m, tag) in _FLEET]

# Real history contains real failures — that is where MTBF and recurrence come
# from. Without any, the profile learns a normal but nothing about how this
# plant actually breaks.
FAILURES = [
    ("mixer_01",       "MIXR1_AGIT_VIB",       6, 7.4, "failure"),    # bearing, 6 days ago
    ("mixer_01",       "MIXR1_AGIT_VIB",      19, 7.2, "failure"),    # same fault, recurring
    ("pasteuriser_01", "PSTR1_HOLD_PRESS_PSI", 11, 28.5, "failure"),  # hold pressure lost
    ("filler_01",      "FILR1_NET_WT_G",       3, 515.8, "defect"),   # overfill event
]


def main() -> None:
    now = datetime.utcnow()
    rows = []

    for machine_id, tag in INSTRUMENTS:
        gen = _FLEET[(machine_id, tag)]
        for d in range(DAYS):
            # Re-centre each day. The generator's slow drift is meant to wander
            # over minutes; run 720 ticks straight and it walks the mean away
            # from the operating point entirely — filler_02 learned a normal of
            # 496.9 g for a filler that actually runs at 500. The learned band
            # then describes a machine the plant does not own.
            gen._drift_accum = 0.0
            gen._last_value = None
            for h in range(SAMPLES_PER_DAY):
                ts = now - timedelta(days=DAYS - d, hours=SAMPLES_PER_DAY - h)
                r = gen.next()               # the real physics, in the plant's own unit
                rows.append({
                    "timestamp": ts.isoformat(timespec="seconds"),
                    "machine_id": machine_id,
                    "signal_name": tag,
                    "signal_value": round(r.value, 2),
                    "event_type": "reading",
                    "is_failure": 0,
                })

    for machine_id, tag, days_ago, value, event_type in FAILURES:
        rows.append({
            "timestamp": (now - timedelta(days=days_ago)).isoformat(timespec="seconds"),
            "machine_id": machine_id,
            "signal_name": tag,
            "signal_value": value,
            "event_type": event_type,
            "is_failure": 1,
        })

    rows.sort(key=lambda r: r["timestamp"])
    with open(OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    print(f"{OUT}: {len(rows)} rows, {DAYS} days, {len(INSTRUMENTS)} instruments, "
          f"{len(FAILURES)} failures")
    print("\nthe plant's own tags and units — nothing canonical:")
    for machine_id, tag in INSTRUMENTS:
        g = _FLEET[(machine_id, tag)]
        print(f"   {machine_id:16} {tag:22} baseline {g.baseline} {g.unit:9} "
              f"warn {g.warn} crit {g.critical}")


if __name__ == "__main__":
    main()
