"""
PAAIM orchestration pipeline rebuilt as a LangGraph StateGraph (proof of concept).

This shows — agents + memory + human approval on a
standard agent framework — without touching the working 3.9 backend:

  • Each pipeline stage is a graph NODE; control flow is graph EDGES.
  • MemorySaver checkpointer = built-in MEMORY / durable state per decision
    (a decision can be paused and resumed; nothing is lost).
  • interrupt_before the approval node = native HUMAN-IN-THE-LOOP: the graph
    literally pauses for a person, then resumes with their decision — exactly
    PAAIM's approval gate.
  • Agent nodes here use simple rules so the POC needs no API key; in the real
    system these nodes call Gemini (and stream traces to LangSmith).

Run:  python run.py
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver


# ── Shared graph state (flows through every node) ───────────────────────────
class PipelineState(TypedDict, total=False):
    event: Dict[str, Any]
    context: Dict[str, Any]
    agent_analyses: List[Dict[str, Any]]
    selected_action: str
    risk_level: str
    approval_required: bool
    approver: str
    approved: Optional[bool]
    decision: Dict[str, Any]


ALLOWED_ACTIONS = {
    "schedule_maintenance": ("medium", "operator"),
    "inspect_root_cause":   ("medium", "operator"),
    "escalate_critical":    ("high",   "manager"),
    "stop_line":            ("critical", "safety_officer"),
    "reduce_consumption":   ("low",    "auto"),
}


# ── Nodes ───────────────────────────────────────────────────────────────────
def enrich_context(state: PipelineState) -> PipelineState:
    """Layer 1 — attach factory context (mocked here; real system queries the graph)."""
    ev = state["event"]
    return {"context": {
        "machine": ev.get("machine_id"),
        "work_order": "WO-2234", "customer": "Ford", "deadline_days": 3,
        "downtime_cost_per_hour": 6200, "open_ncr": "NCR-0041 (2 recurrences)",
    }}


def run_agents(state: PipelineState) -> PipelineState:
    """Layer 2 — specialist agents analyse (rule-based here; Gemini in production)."""
    ev = state["event"]
    sig, val = ev.get("signal_name", ""), ev.get("signal_value", 0)
    analyses: List[Dict[str, Any]] = []
    if "tool_wear" in sig or "vibration" in sig or "heat" in sig:
        analyses.append({"agent": "maintenance_agent", "action": "escalate_critical",
                         "confidence": 0.93, "reason": f"{sig}={val} past safe limit; recurrence on record"})
        analyses.append({"agent": "maintenance_agent", "action": "schedule_maintenance",
                         "confidence": 0.80, "reason": "Safer alternative: planned stop next shift gap"})
    elif "power" in sig:
        analyses.append({"agent": "energy_agent", "action": "reduce_consumption",
                         "confidence": 0.86, "reason": "Power envelope breach"})
    else:
        analyses.append({"agent": "quality_agent", "action": "inspect_root_cause",
                         "confidence": 0.78, "reason": "Anomaly needs investigation"})
    return {"agent_analyses": analyses}


def decide(state: PipelineState) -> PipelineState:
    """Layers 3-5 — policy check + pick the highest-priority valid action."""
    valid = [a for a in state["agent_analyses"] if a["action"] in ALLOWED_ACTIONS]
    best = max(valid, key=lambda a: a["confidence"])
    risk, approver = ALLOWED_ACTIONS[best["action"]]
    return {
        "selected_action": best["action"],
        "risk_level": risk,
        "approver": approver,
        "approval_required": approver != "auto",
    }


def finalize(state: PipelineState) -> PipelineState:
    """Layer 7 — record the outcome after the human decision (audit)."""
    if state.get("approval_required") and not state.get("approved"):
        status = "rejected" if state.get("approved") is False else "pending"
    else:
        status = "approved"
    return {"decision": {
        "action": state["selected_action"],
        "risk": state["risk_level"],
        "approver": state["approver"],
        "status": status,
        "context": state["context"],
    }}


# ── Build the graph ─────────────────────────────────────────────────────────
def build_pipeline():
    g = StateGraph(PipelineState)
    g.add_node("enrich_context", enrich_context)
    g.add_node("run_agents", run_agents)
    g.add_node("decide", decide)
    g.add_node("finalize", finalize)

    g.add_edge(START, "enrich_context")
    g.add_edge("enrich_context", "run_agents")
    g.add_edge("run_agents", "decide")
    g.add_edge("decide", "finalize")
    g.add_edge("finalize", END)

    # MemorySaver = built-in memory; interrupt_before finalize = pause for the
    # human at the approval gate, then resume with their decision.
    return g.compile(checkpointer=MemorySaver(), interrupt_before=["finalize"])
