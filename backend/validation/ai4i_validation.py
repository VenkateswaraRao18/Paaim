"""AI4I 2020 blind-detection validation.

Runs PAAIM's physics-based detection over the real AI4I 2020 dataset and scores
the incidents it triggers against the dataset's own failure labels.

The key move: we ZERO OUT the failure-flag columns before detection, so PAAIM
must catch failures from the raw signals alone (torque, tool wear, temperatures,
speed) using its documented physics thresholds — exactly as it would on a live
PLC stream where no ground-truth label exists. We then compare what it triggered
against the real labels to get true precision / recall / F1 per failure mode.

Usage:
    python -m validation.ai4i_validation             # full CSV if present, else sample
    python -m validation.ai4i_validation --sample    # force the bundled sample
    python -m validation.ai4i_validation --path X.csv

AI4I rows are independent snapshots (not per-machine time series), so a warning
that does not coincide with a labelled failure in the same row counts as a false
positive here — this is a deliberately strict read of PAAIM's early-warning bands.
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List

# allow `python validation/ai4i_validation.py` as well as `-m`
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_adapters.ai4i2020 import row_to_events, normalise_row  # noqa: E402

FULL_PATH = "data_adapters/ai4i2020.csv"
SAMPLE_PATH = "data_adapters/ai4i2020_sample.csv"

# failure flag → (human label, the signal_name the adapter emits, discipline)
MODES = {
    "twf": ("Tool Wear Failure",   "tool_wear_degradation",     "maintenance"),
    "hdf": ("Heat Dissipation",    "heat_dissipation_loss",     "maintenance"),
    "pwf": ("Power Failure",       "power_envelope_breach",     "energy"),
    "osf": ("Overstrain Failure",  "mechanical_overstrain",     "production"),
    "rnf": ("Random Failure",      "unexplained_quality_fault", "quality"),
}
FLAG_COLS = ["Machine failure", "TWF", "HDF", "PWF", "OSF", "RNF"]


@dataclass
class Confusion:
    tp: int = 0  # labelled failure, PAAIM triggered the right incident
    fn: int = 0  # labelled failure, PAAIM missed it
    fp: int = 0  # PAAIM triggered, not labelled a failure this snapshot
    tn: int = 0  # not labelled, PAAIM stayed silent

    def precision(self) -> float:
        d = self.tp + self.fp
        return self.tp / d if d else 1.0

    def recall(self) -> float:
        d = self.tp + self.fn
        return self.tp / d if d else 1.0

    def f1(self) -> float:
        p, r = self.precision(), self.recall()
        return 2 * p * r / (p + r) if (p + r) else 0.0


@dataclass
class Report:
    dataset: str
    path: str
    is_sample: bool
    rows: int = 0
    labelled_failures: int = 0
    per_mode: Dict[str, Confusion] = field(default_factory=lambda: {m: Confusion() for m in MODES})
    overall: Confusion = field(default_factory=Confusion)  # "did we catch the machine failure at all"


def _flag(row: Dict[str, str], col: str) -> bool:
    n = normalise_row(row)
    key = col.lower().replace(" ", "_")
    v = str(n.get(key, "0")).strip().lower()
    return v in ("1", "true", "yes")


def _blind(row: Dict[str, str]) -> Dict[str, str]:
    """Copy of the row with every failure-label column forced to 0."""
    out = dict(row)
    for k in list(out.keys()):
        if k.strip().lower().replace(" ", "_") in ("machine_failure", "twf", "hdf", "pwf", "osf", "rnf"):
            out[k] = "0"
    return out


def run(path: str, is_sample: bool) -> Report:
    rep = Report(dataset="AI4I 2020 Predictive Maintenance (UCI #601)", path=path, is_sample=is_sample)
    with open(path, newline="") as fh:
        for raw in csv.DictReader(fh):
            rep.rows += 1
            truth = {m: _flag(raw, m.upper()) for m in MODES}
            machine_failed = _flag(raw, "Machine failure") or any(truth.values())
            if machine_failed:
                rep.labelled_failures += 1

            # blind detection: physics only, no peeking at labels
            events = row_to_events(_blind(raw), timestamp=datetime.utcnow(), warn_only=True)
            fired = {e.signal_name for e in events}
            any_fired = bool(events)

            for m, (_, signal, _disc) in MODES.items():
                c = rep.per_mode[m]
                predicted = signal in fired
                labelled = truth[m]
                if labelled and predicted:
                    c.tp += 1
                elif labelled and not predicted:
                    c.fn += 1
                elif not labelled and predicted:
                    c.fp += 1
                else:
                    c.tn += 1

            # overall: did we raise ANY incident on a truly-failed machine
            if machine_failed and any_fired:
                rep.overall.tp += 1
            elif machine_failed and not any_fired:
                rep.overall.fn += 1
            elif not machine_failed and any_fired:
                rep.overall.fp += 1
            else:
                rep.overall.tn += 1
    return rep


def _pct(x: float) -> str:
    return f"{x * 100:5.1f}%"


def render(rep: Report) -> str:
    L: List[str] = []
    L.append("=" * 72)
    L.append("PAAIM PRE-PRODUCTION VALIDATION — AI4I 2020")
    L.append("=" * 72)
    tag = "SAMPLE (bundled 12-row slice)" if rep.is_sample else "FULL DATASET"
    L.append(f"Dataset : {rep.dataset}")
    L.append(f"Source  : {rep.path}  [{tag}]")
    L.append(f"Rows    : {rep.rows}    Labelled failures: {rep.labelled_failures}")
    L.append("Method  : failure-label columns zeroed; detection from raw signals only")
    L.append("")
    L.append("Per failure mode (PAAIM's physics detection vs. real labels)")
    L.append("-" * 72)
    L.append(f"{'Mode':22} {'route':11} {'TP':>3} {'FN':>3} {'FP':>3}  {'recall':>7} {'prec':>7} {'F1':>6}")
    for m, (label, _sig, disc) in MODES.items():
        c = rep.per_mode[m]
        if c.tp + c.fn == 0 and c.fp == 0:
            continue  # mode absent in this slice
        L.append(f"{label:22} {disc:11} {c.tp:>3} {c.fn:>3} {c.fp:>3}  "
                 f"{_pct(c.recall())} {_pct(c.precision())} {c.f1()*100:5.1f}%")
    L.append("-" * 72)
    o = rep.overall
    L.append(f"{'OVERALL failure catch':22} {'—':11} {o.tp:>3} {o.fn:>3} {o.fp:>3}  "
             f"{_pct(o.recall())} {_pct(o.precision())} {o.f1()*100:5.1f}%")
    L.append("")
    L.append("Reading it:")
    L.append(f"  • Recall {_pct(o.recall())} — of real machine failures, how many PAAIM caught.")
    L.append(f"  • Precision {_pct(o.precision())} — of PAAIM's alerts, how many hit a real failure")
    L.append("    (the rest are early-warning leads on snapshots not yet labelled failed).")
    if rep.is_sample:
        L.append("")
        L.append("  ⚠ SAMPLE run — numbers are indicative only. Drop the real 10k CSV at")
        L.append(f"    {FULL_PATH} (UCI #601 / Kaggle 'AI4I 2020') for a production-grade result.")
    L.append("=" * 72)
    return "\n".join(L)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", default=None)
    ap.add_argument("--sample", action="store_true")
    args = ap.parse_args()

    if args.path:
        path, is_sample = args.path, False
    elif not args.sample and os.path.exists(FULL_PATH):
        path, is_sample = FULL_PATH, False
    else:
        path, is_sample = SAMPLE_PATH, True

    if not os.path.exists(path):
        sys.exit(f"Dataset not found: {path}")

    rep = run(path, is_sample)
    out = render(rep)
    print(out)

    os.makedirs("validation/reports", exist_ok=True)
    stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    report_path = f"validation/reports/ai4i_{'sample' if is_sample else 'full'}_{stamp}.txt"
    with open(report_path, "w") as fh:
        fh.write(out + "\n")
    print(f"\nSaved: {report_path}")


if __name__ == "__main__":
    main()
