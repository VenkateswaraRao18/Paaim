"""
LLM reasoning for user-created agents.

The built-in specialists (safety, quality, maintenance, …) reason with Gemini,
while user-created agents used to run bare threshold rules and report a
templated string. Manufacturing plants differ, so the agents a plant needs must
be created by its own people — and those agents have to be as capable as the
built-ins, not second-class.

`BaseAgent`'s Gemini path is already generic: it takes a `role` and a
`domain_context` and does the rest. This wraps a user's `CustomAgentDefinition`
so it plugs straight into that path — the operator's description becomes the
role, and their rules/signals become the domain context. Their rules stay
authoritative as guardrails and as the deterministic fallback when the LLM is
unavailable, so an agent never goes silent just because Gemini is down.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from paaim.agents.base import (
    ActionRecommendation,
    AgentAnalysis,
    ApprovalLevel,
    BaseAgent,
    RiskLevel,
)
from paaim.agents.custom_framework import CustomAgentDefinition, Rule

logger = logging.getLogger(__name__)


class LLMCustomAgent(BaseAgent):
    """A user-defined agent that reasons with Gemini, guarded by its own rules."""

    def __init__(self, definition: CustomAgentDefinition):
        super().__init__(
            name=definition.name,
            role=_role_for(definition),
            event_types=[definition.domain or "custom"],
        )
        self.definition = definition

    # ── prompt material ──────────────────────────────────────────────────────
    def _domain_context(self) -> str:
        """Turn what the operator configured into instructions for the model."""
        d = self.definition
        parts: List[str] = []

        if d.description:
            parts.append(d.description)
        if d.watch_signals:
            parts.append(
                "You are responsible for these signals: " + ", ".join(d.watch_signals) + "."
            )

        scope = d.scope or {"type": "all"}
        if scope.get("type") == "machines" and scope.get("machines"):
            parts.append("Your scope is limited to: " + ", ".join(scope["machines"]) + ".")
        elif scope.get("type") == "zone" and scope.get("zone"):
            parts.append(f"Your scope is the '{scope['zone']}' zone.")
        else:
            parts.append("Your scope is every machine in the plant.")

        if d.rules:
            parts.append(
                "The plant's engineers configured these thresholds. Treat them as "
                "authoritative: if one is breached, say so and act on it."
            )
            parts.extend(f"  - {_rule_text(r)}" for r in d.rules)

        if d.actions:
            parts.append(
                "For this domain prefer these actions when they fit: " + ", ".join(d.actions) + "."
            )
        return "\n".join(parts)

    # ── main entry ───────────────────────────────────────────────────────────
    async def analyze(self, event_data: Dict[str, Any]) -> AgentAnalysis:
        gemini_data = await self._call_gemini(event_data, self._domain_context())
        if gemini_data:
            return self._parse_gemini_response(
                gemini_data, event_data.get("event_type") or self.definition.domain or "custom"
            )
        return self._rule_fallback(event_data)

    def _rule_fallback(self, event_data: Dict[str, Any]) -> AgentAnalysis:
        """Deterministic path: the operator's own rules, when the LLM is unavailable."""
        from paaim.agents.custom_framework import CustomAgentExecutor

        executor = CustomAgentExecutor(self.definition)
        matched = [r for r in self.definition.rules if executor._evaluate_rule(r, event_data)]

        recommendations: List[ActionRecommendation] = []
        for r in sorted(matched, key=lambda x: x.priority, reverse=True)[:2]:
            recommendations.append(ActionRecommendation(
                action_name=r.action,
                description=f"{self.definition.name}: {_rule_text(r)}",
                risk_level=RiskLevel.MEDIUM,
                confidence=float(r.confidence),
                approval_required=ApprovalLevel.OPERATOR,
                assumptions=["Threshold configured by the plant is correct"],
                evidence_signals=[event_data.get("signal_name", r.field)],
                estimated_impact={},
            ))

        reasoning = (
            f"{_rule_text(matched[0])} — rule matched (LLM unavailable, deterministic fallback)."
            if matched else
            f"No configured threshold for {self.definition.name} was breached."
        )
        return AgentAnalysis(
            agent_name=self.name,
            event_type=event_data.get("event_type") or self.definition.domain or "custom",
            confidence=float(matched[0].confidence) if matched else 0.5,
            recommendations=recommendations,
            reasoning=reasoning,
            assumptions=[],
        )

    def get_schema(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "role": self.role,
            "event_types": self.event_types,
            "watch_signals": self.definition.watch_signals,
            "scope": self.definition.scope,
            "custom": True,
            "version": "1.0.0",
        }


def _role_for(d: CustomAgentDefinition) -> str:
    domain = (d.domain or "operations").strip()
    return f"{d.name}, a {domain} monitoring specialist"


def _rule_text(r: Rule) -> str:
    """Render a rule the way an engineer would say it."""
    op = getattr(r.operator, "value", str(r.operator)).replace("_", " ")
    target = "" if r.value in ("", None) else f" {r.value}"
    return f"{r.field} {op}{target} → {r.action}"
