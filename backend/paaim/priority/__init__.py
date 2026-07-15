"""Incident triage — deterministic L1/L2/L3 prioritisation.

Ranks the attention queue so the manager works incidents in the order that
protects the most money and the most on-time deliveries. The scoring is fully
transparent (no LLM in the path) and emits its own drivers, so every tier is
explainable.
"""

from paaim.priority.engine import score_incident, PriorityResult

__all__ = ["score_incident", "PriorityResult"]
