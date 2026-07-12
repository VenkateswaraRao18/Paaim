"""
Ground-truth evaluation harness.

Runs known inputs through PAAIM's deterministic capabilities and checks the output
against expected facts — PASS / REVIEW per row, like the Rescue scoreboard but a
real run, not a mockup. This is the credibility centrepiece: it proves the system
captures known truths (it's evidence-backed, not guessing).

All checks are deterministic (no LLM required) so the scoreboard is stable and
reproducible.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional


def _case(category: str, name: str, expected: Any, got: Any, ok: Optional[bool] = None) -> Dict[str, Any]:
    passed = ok if ok is not None else (got == expected)
    return {
        "category": category,
        "name": name,
        "expected": str(expected),
        "got": str(got),
        "status": "PASS" if passed else "REVIEW",
    }


async def run_eval() -> Dict[str, Any]:
    from paaim.normalization import resolve_field
    from paaim.semantic.plc_codes import list_codes
    from paaim.semantic.maintenance_logs import get_historian
    from paaim.agents.custom_framework import (
        CustomAgentRegistry, CustomAgentDefinition, Rule, RuleOperator,
    )

    results: List[Dict[str, Any]] = []

    # 1 — Normalization: messy field names map to the right canonical signal
    for raw, expected in [("MTR03_TORQUE", "torque"), ("temp_c", "temperature"),
                          ("vib", "vibration"), ("SpindleSpeed", "rotational_speed"),
                          ("power_kw", "power")]:
        fm = resolve_field(raw)
        results.append(_case("Normalization", f"{raw} → {expected}", expected, fm.signal if fm else None))

    # 2 — Semantic decode: a cryptic code resolves to a plain meaning
    codes = {c.get("code"): c for c in list_codes()}
    meaning = (codes.get("0x4F3") or {}).get("plain_meaning", "")
    results.append(_case("Semantic decode", "0x4F3 → plain meaning", "non-empty", meaning, ok=bool(meaning)))

    # Isolated registry so we never touch the user's custom_agents.json
    tmp = "/tmp/paaim_eval_agents.json"
    reg = CustomAgentRegistry(persist_path=tmp)
    try:
        # 3 — Agent firing: a breach triggers the expected action
        reg.register_agent(CustomAgentDefinition(
            id="eval_thermal", name="Eval Thermal", description="", domain="thermal",
            rules=[Rule(field="temperature", operator=RuleOperator.GREATER_THAN, value=80, action="schedule_maintenance")],
            actions=["schedule_maintenance"], watch_signals=["temperature"], scope={"type": "all"},
        ))
        recs = await reg.evaluate_signal_event("temperature", 92, "m1")
        results.append(_case("Agent firing", "temp 92 → schedule_maintenance",
                             "schedule_maintenance", recs[0]["action_name"] if recs else None))

        # 4 — Learned baseline: 83° is normal FOR A FURNACE (silent), 95° fires
        reg.register_agent(CustomAgentDefinition(
            id="eval_adaptive", name="Eval Adaptive", description="", domain="thermal",
            rules=[Rule(field="temperature", operator=RuleOperator.OUTSIDE_NORMAL, value="", action="inspect_root_cause")],
            actions=["inspect_root_cause"], watch_signals=["temperature"], scope={"type": "all"},
        ))
        bl = {"mean": 83, "std": 2.5, "normal_range": [78, 88]}
        r83 = await reg.evaluate_signal_event("temperature", 83, "furnace", baseline=bl)
        r95 = await reg.evaluate_signal_event("temperature", 95, "furnace", baseline=bl)
        fired83 = any(x["agent_id"] == "eval_adaptive" for x in r83)
        fired95 = any(x["agent_id"] == "eval_adaptive" for x in r95)
        adaptive_ok = (not fired83) and fired95
        results.append(_case("Learned baseline", "83° normal-for-furnace silent · 95° fires",
                             "silent@83, fire@95",
                             f"{'fire' if fired83 else 'silent'}@83, {'fire' if fired95 else 'silent'}@95",
                             ok=adaptive_ok))
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)

    # 5 — Tribal knowledge (RAG/keyword): retrieves a coolant-related prior fix
    hist = get_historian()
    hits = hist.search("cnc_mill_01", "heat_dissipation_loss", "spindle overheating coolant flow", limit=1)
    blob = ((hits[0].get("raw_note") or "") + " " + (hits[0].get("resolution") or "")).lower() if hits else ""
    results.append(_case("Tribal knowledge", "retrieves a coolant-related prior fix",
                         "coolant fix", hits[0].get("raw_note") if hits else "—",
                         ok=("coolant" in blob or "clnt" in blob)))

    passed = sum(1 for r in results if r["status"] == "PASS")
    return {
        "passed": passed,
        "total": len(results),
        "pass_rate": round(100 * passed / len(results)) if results else 0,
        "rag_enabled": hist.stats().get("rag_enabled", False),
        "results": results,
    }
