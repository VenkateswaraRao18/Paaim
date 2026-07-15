"""
Scenario Explanation Agent — deterministic "why the recommendation changed".

Uses the exact management copy from the brief (§8) plus the trigger rules (§3.4).
Numbers come from the engine; this only phrases the reasoning. An LLM could later
rewrite `summary` for tone, but must not change triggered constraints or numbers.
"""

from __future__ import annotations

from typing import Any, Dict, List

NON_BYPASSABLE = ["Safety / LOTO", "Quality release"]


def build_explanation(rec_id: str, changed: List[dict], f: Dict[str, Any],
                      threshold: int, line2_feasible: bool) -> Dict[str, Any]:
    insp = float(f["inspection_duration_min"])
    triggered: List[str] = []
    if insp > threshold:
        triggered.append(f"SOP-PLAN-003 fallback threshold: {threshold} min")
    if not line2_feasible:
        triggered.append("Line 2 reroute unavailable (capacity below feasibility)")
    if not bool(f["spare_actuator_available"]):
        triggered.append("Spare actuator unavailable — repair duration risk increased")
    if float(f["deadline_buffer_min"]) <= 30:
        triggered.append("Customer deadline buffer critically low")
    if float(f["qa_hold_units"]) >= 80:
        triggered.append("QA containment burden increased — quality release delayed")

    if not changed:
        summary = ("Recommended: inspect then restart. This protects safety and quality while preserving "
                   "shipment probability. Prepare Line 2 fallback only if inspection exceeds 25 minutes.")
        business = "Default incident: inspection is within the fallback threshold and the shipment buffer is adequate."
    elif rec_id == "prepare_line2_fallback":
        summary = ("Recommendation updated: prepare Line 2 fallback now. The changed assumptions pushed Line 3 "
                   "recovery beyond the safe shipment window. Continue inspection, but prepare reroute in parallel.")
        business = "Waiting for Line 3 alone reduces shipment probability for Apex Motors PO-4817."
    elif rec_id == "inspect_then_restart" and not line2_feasible:
        summary = ("Recommendation updated: inspect then restart remains the only feasible path. Reroute is "
                   "unavailable. Escalate maintenance priority and notify operations that shipment risk is rising.")
        business = "Line 2 cannot absorb the order; on-time delivery depends on Line 3 recovery."
    else:
        summary = ("Recommended: inspect then restart. Assumptions changed but the safe restart path still "
                   "preserves the best shipment probability.")
        business = "Shipment probability remains highest via inspect-then-restart under current assumptions."

    return {
        "summary": summary,
        "triggered_constraints": triggered,
        "business_impact": business,
        "non_bypassable_gates": NON_BYPASSABLE,
    }


def next_best_action(rec_id: str, f: Dict[str, Any], threshold: int) -> str:
    if rec_id == "prepare_line2_fallback":
        return "Continue inspection and prepare Line 2 reroute in parallel."
    if rec_id == "inspect_then_restart":
        if float(f["inspection_duration_min"]) > threshold:
            return "Inspect now; prepare Line 2 fallback if reroute becomes feasible."
        return "Inspect Station C3, then restart after sign-off; hold the last units for QA."
    return "Prepare drafts; restart remains blocked by safety and quality gates."
