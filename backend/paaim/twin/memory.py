"""
Factory Memory / 8D Recurrence Loop — converts the incident into prevention.

Deterministic: assembles the 8D/CAPA draft, the pending learned rule, similar
prior incidents, the recurrence-risk trajectory, and the verification plan from
the scenario data files. Nothing auto-enforces — the learned rule stays pending
until a human owner approves it.
"""

from __future__ import annotations

import csv
import json
import os
from typing import Any, Dict, List

_DATA = os.path.join(os.path.dirname(__file__), "..", "..", "data", "demo_scenario", "line3_rescue")


def _j(name):
    with open(os.path.join(_DATA, name)) as f:
        return json.load(f)


def _csv(name):
    with open(os.path.join(_DATA, name), newline="") as f:
        return list(csv.DictReader(f))


EIGHT_D = [
    ("D1", "Team", "Maintenance Lead, QA Lead, Production Manager, OT Engineer.", "Draft"),
    ("D2", "Problem", "Line 3 / Station C3 fault 0x4F3 during Apex Motors PO-4817; active torque/interlock/camera anomaly.", "Draft"),
    ("D3", "Containment", "Hold last 47 units from 8:03-8:17; do not restart before inspection.", "In progress"),
    ("D4", "Root cause hypothesis", "Clamp binding / torque tool overload; possible air-line issue; visual anomaly requires QA review.", "Draft"),
    ("D5", "Corrective action", "Inspect clamp actuator, torque tool calibration, and air-line; replace actuator seal if confirmed.", "Draft"),
    ("D6", "Implement", "Assign maintenance work order; prepare Line 2 fallback if inspection exceeds 25 minutes.", "Pending approval"),
    ("D7", "Prevent recurrence", "Add learned rule and watch 0x4F3 + high torque + camera anomaly pattern for 72 hours.", "Pending validation"),
    ("D8", "Close / recognize", "Review outcome in 9 AM meeting and close after verification.", "Pending"),
]


def build_factory_memory() -> Dict[str, Any]:
    fm = _j("factory_memory.json")["rules"][0]
    similar = _csv("similar_incidents.csv")
    verification = _csv("verification_plan.csv")
    return {
        "memory_run_id": "memory_line3_0817_001",
        "eight_d": [{"id": d[0], "discipline": d[1], "content": d[2], "status": d[3]} for d in EIGHT_D],
        "similar_incidents_found": len(similar),
        "similar_incidents": similar,
        "recurrence_pattern": "0x4F3 + high torque + camera anomaly + reset failed",
        "learned_rule": {
            "rule_text": fm["rule_text"],
            "status": fm["status"],
            "applies_to": fm["applies_to"],
        },
        "recurrence_risk": {"before_action": 0.38, "after_corrective_action": 0.18, "after_verified_rule": 0.07},
        "verification_plan": verification,
    }
