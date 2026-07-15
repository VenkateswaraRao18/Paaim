"""
Factory learning — builds a knowledge profile from uploaded historical data.

A factory uploads its past events/readings; this computes what "normal" looks
like for each machine, how often things fail, and which problems recur. The
profile becomes the factory's learned memory — agents can then judge a new
reading against the machine's own history instead of a generic threshold.

Input rows are tolerant of header variants; recognised fields:
    machine_id, signal_name, signal_value, event_type, is_failure, timestamp
"""

from __future__ import annotations

import re
import statistics
from collections import Counter, defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional

FAILURE_EVENT_TYPES = {"failure", "fault", "breakdown", "ncr", "defect"}


def _norm_key(k: str) -> str:
    k = re.sub(r"\[.*?\]", "", k).strip().lower()
    return re.sub(r"[^a-z0-9]+", "_", k).strip("_")


def _f(row: Dict[str, str], *names: str) -> Optional[float]:
    for n in names:
        v = row.get(n)
        if v not in (None, ""):
            try:
                return float(v)
            except (TypeError, ValueError):
                pass
    return None


def _is_failure(row: Dict[str, str]) -> bool:
    flag = str(row.get("is_failure", "")).strip().lower()
    if flag in ("1", "true", "yes"):
        return True
    et = str(row.get("event_type", "")).strip().lower()
    return et in FAILURE_EVENT_TYPES


def _parse_ts(row: Dict[str, str]) -> Optional[datetime]:
    v = row.get("timestamp")
    if not v:
        return None
    try:
        return datetime.fromisoformat(str(v).replace("Z", "+00:00").replace("+00:00", ""))
    except ValueError:
        return None


def normalize_history(rows: List[Dict[str, str]], mapping) -> Dict[str, Any]:
    """
    Translate a plant's raw history export into the canonical vocabulary before
    anything is learned from it.

    A history CSV is an export from the plant's historian: its own tag names, in
    its own units. The profile built from it is looked up by the watchers using
    `baseline_for(profile, machine_id, canonical_signal)` — so learning straight
    from the raw rows was broken twice over, and both failures were silent:

      · **Name.** History learned `PSTR1_PROD_TEMP_F`; the watcher asked for
        `product_temperature` and got None. The upload reported "learned", and
        every watcher went on judging by declared limits forever.
      · **Unit.** Had the names lined up, the baseline would have been a mean of
        165 (°F) against live readings of 73.9 (°C) — every reading ~100σ from
        normal, i.e. critical, permanently.

    So the same mapping the live feed uses is applied here. Rows whose tag the
    plant never mapped are dropped and reported rather than learned under a name
    nothing will ever ask for.
    """
    from paaim.normalization.schema import TRANSFORMS

    out: List[Dict[str, str]] = []
    unmapped: Counter = Counter()
    for r in rows:
        r = {_norm_key(k): v for k, v in r.items()}
        tag = r.get("signal_name") or r.get("signal")
        fm = (mapping.fields or {}).get(tag) if tag else None
        if not fm:
            if tag:
                unmapped[tag] += 1
            continue
        val = _f(r, "signal_value", "value")
        if val is None:
            continue
        r["signal_name"] = fm.signal
        r["signal_value"] = TRANSFORMS.get(fm.transform, TRANSFORMS["identity"])(val)
        out.append(r)

    return {
        "rows": out,
        "unmapped_tags": [{"tag": t, "rows": n} for t, n in unmapped.most_common()],
        "mapped_rows": len(out),
    }


def compute_profile(rows: List[Dict[str, str]]) -> Dict[str, Any]:
    """Compute the learned factory knowledge profile from historical rows."""
    rows = [{_norm_key(k): v for k, v in r.items()} for r in rows]

    by_machine: Dict[str, List[Dict[str, str]]] = defaultdict(list)
    for r in rows:
        mid = r.get("machine_id") or r.get("machine") or "unknown"
        by_machine[mid].append(r)

    machines: Dict[str, Any] = {}
    total_failures = 0

    for mid, mrows in by_machine.items():
        # per-signal baselines
        signal_values: Dict[str, List[float]] = defaultdict(list)
        for r in mrows:
            sig = r.get("signal_name") or r.get("signal")
            val = _f(r, "signal_value", "value")
            if sig and val is not None:
                signal_values[sig].append(val)

        signals = {}
        for sig, vals in signal_values.items():
            if not vals:
                continue
            vals_sorted = sorted(vals)
            signals[sig] = {
                "mean": round(statistics.fmean(vals), 2),
                "std": round(statistics.pstdev(vals), 2) if len(vals) > 1 else 0.0,
                "min": round(min(vals), 2),
                "max": round(max(vals), 2),
                "p95": round(vals_sorted[int(len(vals_sorted) * 0.95) - 1], 2),
                "samples": len(vals),
                "normal_range": [
                    round(statistics.fmean(vals) - 2 * (statistics.pstdev(vals) if len(vals) > 1 else 0), 2),
                    round(statistics.fmean(vals) + 2 * (statistics.pstdev(vals) if len(vals) > 1 else 0), 2),
                ],
            }

        # failures + recurrence + MTBF
        failures = [r for r in mrows if _is_failure(r)]
        total_failures += len(failures)
        recurring = Counter()
        for r in failures:
            label = r.get("signal_name") or r.get("event_type") or "unknown"
            recurring[label] += 1

        fail_times = sorted([t for t in (_parse_ts(r) for r in failures) if t])
        mtbf_hours = None
        if len(fail_times) >= 2:
            deltas = [(fail_times[i + 1] - fail_times[i]).total_seconds() / 3600
                      for i in range(len(fail_times) - 1)]
            mtbf_hours = round(statistics.fmean(deltas), 1)

        machines[mid] = {
            "records": len(mrows),
            "signals": signals,
            "failure_count": len(failures),
            "mtbf_hours": mtbf_hours,
            "recurring_issues": [{"issue": k, "count": v} for k, v in recurring.most_common(5)],
        }

    return {
        "computed_at": datetime.utcnow().isoformat(),
        "records_analyzed": len(rows),
        "machines_learned": len(machines),
        "total_failures": total_failures,
        "machines": machines,
    }


def baseline_for(profile: Dict[str, Any], machine_id: str, signal_name: str) -> Optional[Dict[str, Any]]:
    """Look up a learned baseline — used to enrich live decisions."""
    m = (profile or {}).get("machines", {}).get(machine_id)
    if not m:
        return None
    return m.get("signals", {}).get(signal_name)
