"""
SOP Dispatcher — turns a diagnosed failure + past fixes into a plain,
step-by-step action plan a junior operator can follow right now.

This is the "human-readable action" end of the Semantic Disconnect: the cryptic
code is already decoded; here we produce the SOP. Uses Gemini when available,
with a deterministic fallback so it always returns something.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def _build_prompt(diagnosis: Dict[str, Any], past_cases: List[Dict],
                  context: Dict[str, Any]) -> str:
    cases_txt = "\n".join(
        f"- {c['date']} ({c['technician']}): \"{c['raw_note']}\" → FIXED BY: {c['resolution']} "
        f"({c['downtime_min']} min)"
        for c in past_cases
    ) or "- (no similar past cases on record)"

    ctx_txt = ""
    if context:
        wo = context.get("active_work_order") or {}
        co = context.get("customer_order") or {}
        costs = context.get("costs") or {}
        if wo or co or costs:
            ctx_txt = (
                f"\nOPERATIONAL CONTEXT:\n"
                f"- Work order: {wo.get('work_order_id','n/a')} for {co.get('customer_name','n/a')}\n"
                f"- Downtime cost: ${costs.get('downtime_cost_per_hour_usd','n/a')}/hr\n"
            )

    return f"""You are an expert maintenance engineer writing instructions for a JUNIOR operator
who does NOT understand machine codes. Be clear, safe and concrete.

DECODED ALARM:
- Machine: {diagnosis.get('machine_id')}
- Code: {diagnosis.get('code','(raw signal)')}
- What it means (plain): {diagnosis.get('plain_meaning')}
- Severity: {diagnosis.get('severity')}
{ctx_txt}
WHAT FIXED THIS BEFORE (from maintenance logs):
{cases_txt}

Write the action plan as ONLY valid JSON:
{{
  "summary": "<one plain sentence: what's wrong and how urgent>",
  "steps": ["<step 1 — concrete, safe, in order>", "<step 2>", "..."],
  "do_not": ["<a key safety/quality 'do not' for a junior>"],
  "escalate_if": "<when the operator should stop and call a senior/manager>",
  "estimated_time_min": <number from past cases>
}}

Rules:
- Steps must be doable by a junior operator; safety first.
- Reuse what worked in the past cases where relevant.
- Plain language, no jargon, no codes. Respond with ONLY the JSON."""


def _fallback_sop(diagnosis: Dict[str, Any], past_cases: List[Dict]) -> Dict[str, Any]:
    first_fix = past_cases[0]["resolution"] if past_cases else "Inspect the machine and call maintenance."
    avg_time = None
    times = [int(c["downtime_min"]) for c in past_cases if str(c.get("downtime_min", "")).isdigit()]
    if times:
        avg_time = round(sum(times) / len(times))
    return {
        "summary": diagnosis.get("plain_meaning", "Fault detected — action needed."),
        "steps": [
            "Stop feeding new parts to the machine and put it in a safe state.",
            f"Check the most likely cause: {diagnosis.get('plain_meaning','')}",
            f"Apply the proven fix: {first_fix}",
            "Confirm the reading returns to normal before restarting.",
        ],
        "do_not": ["Do not override the alarm and keep running the line."],
        "escalate_if": "the reading does not return to normal after the fix, or you are unsure at any step.",
        "estimated_time_min": avg_time or 30,
        "_source": "rule_fallback",
    }


def dispatch_sop(diagnosis: Dict[str, Any], past_cases: List[Dict],
                 context: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Produce the operator action plan (SOP)."""
    context = context or {}
    try:
        from paaim.agents.base import _get_gemini
        client, available = _get_gemini()
        if available and client:
            prompt = _build_prompt(diagnosis, past_cases, context)
            resp = client.generate_content(prompt)
            text = (resp.text or "").strip()
            if text.startswith("```"):
                text = text.split("```")[1].replace("json", "", 1).strip()
            sop = json.loads(text)
            sop["_source"] = "gemini"
            return sop
    except Exception as e:
        logger.warning(f"SOP dispatcher fell back to rules: {e}")
    return _fallback_sop(diagnosis, past_cases)
