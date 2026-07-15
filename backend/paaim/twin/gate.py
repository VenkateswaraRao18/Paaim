"""
Facility Readiness & Approval Gate — the non-bypassable safety layer.

Loads the gate rules and returns the persistent gate board plus which actions are
blocked vs. which drafts are allowed. Restart stays BLOCKED while Safety/LOTO or
Quality release is HOLD — scenario controls cannot override this.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List

_DATA = os.path.join(os.path.dirname(__file__), "..", "..", "data", "demo_scenario", "line3_rescue")


def _rules() -> dict:
    with open(os.path.join(_DATA, "facility_gate_rules.json")) as f:
        return json.load(f)


def compute_gates() -> Dict[str, Any]:
    """Return the gate board + blocked/allowed actions (brief §4.3 contract)."""
    rules = _rules()
    gates = rules["gates"]
    blocking = rules["restart_blocking_gates"]

    restart_blocked = any(g["status"] == "hold" for g in gates if g["gate_id"] in blocking)

    blocked_actions: List[str] = []
    allowed_drafts: List[str] = []
    for g in gates:
        blocked_actions.extend(g.get("blocked_actions", []))
        allowed_drafts.extend(g.get("allowed_drafts", []))
    blocked_actions = sorted(set(blocked_actions))
    allowed_drafts = sorted(set(allowed_drafts))

    return {
        "gate_run_id": "gate_line3_0817_001",
        "overall_status": "blocked_for_restart_drafts_allowed" if restart_blocked else "clear",
        "restart_blocked": restart_blocked,
        "gates": [
            {"gate_id": g["gate_id"], "label": g["label"], "status": g["status"],
             "reason": g["reason"], "owner": g["owner"], "source": g.get("source"),
             "allowed_actions": g.get("allowed_drafts", [])}
            for g in gates
        ],
        "blocked_actions": blocked_actions,
        "allowed_draft_actions": allowed_drafts,
        "trust_banner": rules["trust_banner"],
    }


def is_action_blocked(action: str) -> bool:
    return action in compute_gates()["blocked_actions"]
