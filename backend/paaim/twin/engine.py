"""
Interactive Recovery Decision Twin — deterministic scenario engine.

NOT a physics simulator: a transparent, repeatable decision-support engine. It
takes the user's adjusted factors, computes option metrics with simple explainable
rules, applies the (non-bypassable) facility gate, and returns the recommendation
+ explanation as the JSON contract in the brief. The LLM may later rephrase the
explanation, but it never invents these numbers.
"""

from __future__ import annotations

import csv
import json
import os
from typing import Any, Dict, List

_DATA = os.path.join(os.path.dirname(__file__), "..", "..", "data", "demo_scenario", "line3_rescue")


def _load_json(name: str) -> dict:
    with open(os.path.join(_DATA, name)) as f:
        return json.load(f)


def _load_csv(name: str) -> List[dict]:
    with open(os.path.join(_DATA, name), newline="") as f:
        return list(csv.DictReader(f))


def defaults() -> Dict[str, Any]:
    return {c["factor_id"]: c["default"] for c in _load_json("scenario_controls.json")["factors"]}


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def simulate(factors: Dict[str, Any]) -> Dict[str, Any]:
    """Run the deterministic scenario and return the full decision contract."""
    ctrl = _load_json("scenario_controls.json")
    opt_defs = {o["option_id"]: o for o in _load_json("decision_options.json")["options"]}
    d = defaults()
    f = {**d, **(factors or {})}

    current_downtime = ctrl["current_downtime_min"]
    threshold = ctrl["fallback_threshold_min"]

    insp   = float(f["inspection_duration_min"])
    maint  = float(f["maintenance_arrival_min"])
    cap    = float(f["line2_capacity_pct"])
    qahold = float(f["qa_hold_units"])
    cost   = float(f["cost_per_min"])
    buffer = float(f["deadline_buffer_min"])
    spare  = bool(f["spare_actuator_available"])
    tol    = str(f["qa_risk_tolerance"])

    repair_time = 20 if spare else 40
    buffer_pen = 0.002 * max(0, 90 - buffer)
    shipment_failure_cost = 60000   # exposure if PO-4817 misses its window
    escape_exposure = 30000         # exposure if a quality escape ships

    # ── ship probability per option (transparent rules) ──
    ship_inspect = _clamp(0.88 - 0.0113 * max(0, insp - 20) - 0.004 * maint
                          - (0.08 if not spare else 0) - buffer_pen, 0.15, 0.92)
    line2_feasible = cap >= 30
    ship_line2 = _clamp(0.86 * min(1.0, cap / 70) - buffer_pen, 0.05, 0.90) if line2_feasible else 0.0
    ship_restart = 0.62

    # ── recovery time & expected loss ──
    inspect_recovery = insp + maint + repair_time
    line2_recovery = 25 + 0.3 * max(0, 70 - cap)
    recov = {"restart_now": 0, "inspect_then_restart": inspect_recovery, "prepare_line2_fallback": line2_recovery}
    ship = {"restart_now": ship_restart, "inspect_then_restart": ship_inspect, "prepare_line2_fallback": ship_line2}

    def qa_escape(oid: str) -> float:
        base = opt_defs[oid]["base_qa_escape"]
        r = base * (1 + 0.003 * max(0, qahold - 47))
        return round(_clamp(r, 0.0, 0.6), 2)

    def expected_loss(oid: str) -> int:
        # downtime paid so far + risk-weighted shipment failure + quality-escape exposure.
        # Recommended (highest ship prob) naturally lands at the lowest expected loss.
        loss_so_far = current_downtime * cost
        return int(round(loss_so_far
                         + (1 - ship[oid]) * shipment_failure_cost
                         + qa_escape(oid) * escape_exposure, -2))

    # ── gate: restart is blocked while Safety/LOTO or Quality release HOLD ──
    safety_status = {"restart_now": "blocked", "inspect_then_restart": "review", "prepare_line2_fallback": "review"}
    allowed = {"restart_now": False,
               "inspect_then_restart": True,
               "prepare_line2_fallback": line2_feasible}

    options = []
    for oid, od in opt_defs.items():
        o = {
            "option_id": oid, "label": od["label"],
            "allowed": allowed[oid],
            "blocked_by": od.get("blocked_by", []) if oid == "restart_now" else ([] if allowed[oid] else ["line2_capacity"]),
            "ship_probability": round(ship[oid], 2),
            "expected_loss": expected_loss(oid),
            "qa_escape_risk": qa_escape(oid),
            "safety_status": safety_status[oid],
            "owner": od["owner"],
        }
        options.append(o)

    # ── recommendation = highest ship prob among ALLOWED options ──
    allowed_opts = [o for o in options if o["allowed"]]
    recommended = max(allowed_opts, key=lambda o: o["ship_probability"])
    rec_id = recommended["option_id"]
    for o in options:
        o["is_recommended"] = (o["option_id"] == rec_id)

    changed = _changed_factors(d, f)
    from paaim.twin.explanation import build_explanation, next_best_action
    explanation = build_explanation(rec_id, changed, f, threshold, line2_feasible)

    return {
        "scenario_id": "line3_rescue_default" if not changed else "line3_rescue_whatif",
        "changed_factors": changed,
        "recommended_option": rec_id,
        "recommended_label": recommended["label"],
        "next_best_action": next_best_action(rec_id, f, threshold),
        "options": options,
        "explanation": explanation,
        "assumptions": _load_json("assumption_ledger.json")["assumptions"],
    }


def _changed_factors(defaults_: Dict[str, Any], f: Dict[str, Any]) -> List[dict]:
    out = []
    for k, dv in defaults_.items():
        if f.get(k) != dv:
            out.append({"factor": k, "old": dv, "new": f.get(k)})
    return out
