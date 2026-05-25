import uuid
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple

from paaim.models import EventData, Decision, EvidencePack, DecisionStatus, EventType, RiskLevel
from paaim.agents.registry import get_registry
from paaim.policy.engine import PolicyEngine
from paaim.decision_twin.simulator import DecisionTwin
from paaim.governance.red_team import RedTeamAgent
from paaim.streaming import get_publisher, PipelineEventType, PipelineEvent
from paaim.agents.custom_framework import get_custom_agent_registry


class OrchestrationContext:
    """Context for a single orchestration execution."""

    def __init__(self, event: EventData):
        self.event = event
        self.event_id = event.event_type.value + "_" + str(uuid.uuid4())[:8]
        self.decision_id = "dec_" + datetime.utcnow().strftime("%Y%m%d_%H%M%S") + "_" + str(uuid.uuid4())[:8]
        self.timestamp_start = datetime.utcnow()

        # Results from each layer
        self.agent_analyses = []
        self.policy_evaluations = {}
        self.impact_estimates = {}
        self.red_team_reviews = {}
        self.selected_action = None
        self.approval_required = False
        self.approval_route = None

    def to_evidence_pack(self) -> Dict[str, Any]:
        """Convert context to evidence pack for audit trail."""
        return {
            "event_data": {
                "event_type": self.event.event_type.value,
                "source_agent": self.event.source_agent,
                "factory_id": self.event.factory_id,
                "signal_name": self.event.signal_name,
                "signal_value": self.event.signal_value,
                "confidence": self.event.confidence,
                "timestamp": self.event.timestamp.isoformat(),
                "context": self.event.context,
            },
            "agent_analyses": self.agent_analyses,
            "policy_evaluation": self.policy_evaluations,
            "decision_twin_simulation": self.impact_estimates,
            "red_team_challenges": self.red_team_reviews,
            "approval_decision": {
                "required": self.approval_required,
                "route": self.approval_route,
            },
        }


class Orchestrator:
    """
    Master orchestration layer: coordinates event → decision pipeline.

    Wires together all layers:
    1. Event ingestion
    2. Agent analysis
    3. Policy evaluation
    4. Decision Twin simulation
    5. Red-Team challenge
    6. Approval routing
    7. Audit trail
    """

    def __init__(self):
        """Initialize orchestrator with all components."""
        self.policy_engine = PolicyEngine()
        self.decision_twin = DecisionTwin()
        self.red_team = RedTeamAgent()
        self.registry = get_registry()
        self.custom_registry = get_custom_agent_registry()
        self.publisher = get_publisher()

    async def orchestrate(self, event: EventData) -> Dict[str, Any]:
        """
        Full orchestration pipeline: event → decision.

        Args:
            event: Manufacturing event from simulator or real system

        Returns:
            Complete decision with all analysis layers
        """
        ctx = OrchestrationContext(event)

        # Emit orchestration start
        await self._emit_event(
            PipelineEventType.ORCHESTRATION_STARTED,
            ctx.decision_id,
            "pipeline",
            {
                "event_type": event.event_type.value,
                "signal_name": event.signal_name,
                "factory_id": event.factory_id,
            },
        )

        try:
            # Layer 2: Route to specialist agents
            await self._emit_event(
                PipelineEventType.AGENTS_ROUTING,
                ctx.decision_id,
                "agents",
                {"status": "routing"},
            )
            await self._route_to_agents(ctx)
            if not ctx.agent_analyses:
                return self._error_response("No agents matched event type", ctx)

            await self._emit_event(
                PipelineEventType.AGENTS_COMPLETE,
                ctx.decision_id,
                "agents",
                {"agent_count": len(ctx.agent_analyses)},
            )

            # Layer 3: Policy evaluation
            await self._emit_event(
                PipelineEventType.POLICY_CHECKING,
                ctx.decision_id,
                "policy",
                {"status": "evaluating"},
            )
            self._evaluate_policy(ctx)
            await self._emit_event(
                PipelineEventType.POLICY_COMPLETE,
                ctx.decision_id,
                "policy",
                {"evaluations": len(ctx.policy_evaluations)},
            )

            # Layer 4: Decision Twin simulation
            await self._emit_event(
                PipelineEventType.TWIN_SIMULATING,
                ctx.decision_id,
                "twin",
                {"status": "simulating"},
            )
            self._simulate_impacts(ctx)
            await self._emit_event(
                PipelineEventType.TWIN_COMPLETE,
                ctx.decision_id,
                "twin",
                {"simulations": len(ctx.impact_estimates)},
            )

            # Layer 5: Red-Team challenge
            await self._emit_event(
                PipelineEventType.RED_TEAM_CHALLENGING,
                ctx.decision_id,
                "red_team",
                {"status": "challenging"},
            )
            self._challenge_recommendations(ctx)
            await self._emit_event(
                PipelineEventType.RED_TEAM_COMPLETE,
                ctx.decision_id,
                "red_team",
                {"reviews": len(ctx.red_team_reviews)},
            )

            # Layer 6: Approval routing
            await self._emit_event(
                PipelineEventType.APPROVAL_ROUTING,
                ctx.decision_id,
                "approval",
                {"status": "routing"},
            )
            self._route_to_approval(ctx)
            await self._emit_event(
                PipelineEventType.APPROVAL_COMPLETE,
                ctx.decision_id,
                "approval",
                {"approval_route": ctx.approval_route},
            )

            # Layer 7: Build decision and audit trail
            response = self._build_decision_response(ctx)

            await self._emit_event(
                PipelineEventType.ORCHESTRATION_COMPLETED,
                ctx.decision_id,
                "pipeline",
                {"status": "success", "latency_ms": (datetime.utcnow() - ctx.timestamp_start).total_seconds() * 1000},
            )

            return response

        except Exception as e:
            await self._emit_event(
                PipelineEventType.ORCHESTRATION_ERROR,
                ctx.decision_id,
                "pipeline",
                {"error": str(e)},
            )
            raise

    async def _emit_event(
        self,
        event_type: PipelineEventType,
        decision_id: str,
        layer: str,
        data: Dict[str, Any],
    ) -> None:
        """Emit a pipeline event if there are subscribers."""
        if self.publisher.has_subscribers(decision_id):
            event = PipelineEvent(event_type, decision_id, layer, data)
            await self.publisher.emit(event)

    async def _route_to_agents(self, ctx: OrchestrationContext) -> None:
        """Layer 2: Route event to matching specialist agents and custom agents."""
        agents = self.registry.get_agents_for_event_type(ctx.event.event_type.value)

        # Run built-in agents
        for agent in agents:
            try:
                analysis = await agent.analyze({
                    "event_type": ctx.event.event_type.value,
                    "signal_name": ctx.event.signal_name,
                    "signal_value": ctx.event.signal_value,
                    "confidence": ctx.event.confidence,
                    "context": ctx.event.context,
                })

                ctx.agent_analyses.append({
                    "agent": analysis.agent_name,
                    "confidence": analysis.confidence,
                    "reasoning": analysis.reasoning,
                    "recommendations": [
                        {
                            "action_name": r.action_name,
                            "description": r.description,
                            "risk_level": r.risk_level.value,
                            "confidence": r.confidence,
                            "approval_required": r.approval_required.value,
                            "assumptions": r.assumptions,
                            "evidence_signals": r.evidence_signals,
                            "estimated_impact": r.estimated_impact,
                        }
                        for r in analysis.recommendations
                    ],
                })
            except Exception as e:
                ctx.agent_analyses.append({
                    "agent": agent.name,
                    "error": str(e),
                })

        # Run custom agents
        for custom_agent in self.custom_registry.list_agents():
            if not custom_agent.enabled:
                continue

            try:
                # Prepare event data for custom agent
                event_data = {
                    "event_type": ctx.event.event_type.value,
                    "signal_name": ctx.event.signal_name,
                    "signal_value": ctx.event.signal_value,
                    "confidence": ctx.event.confidence,
                }
                event_data.update(ctx.event.context)

                # Execute custom agent
                recommendations = await self.custom_registry.execute_agent_async(
                    custom_agent.id,
                    event_data
                )

                if recommendations:
                    ctx.agent_analyses.append({
                        "agent": custom_agent.name,
                        "confidence": 0.8,  # Average confidence from custom agent rules
                        "reasoning": f"Custom agent {custom_agent.domain} evaluated event",
                        "recommendations": recommendations,
                    })
            except Exception as e:
                ctx.agent_analyses.append({
                    "agent": custom_agent.name,
                    "error": str(e),
                })

    def _evaluate_policy(self, ctx: OrchestrationContext) -> None:
        """Layer 3: Evaluate each recommendation against policy."""
        for analysis in ctx.agent_analyses:
            if "error" in analysis:
                continue

            for rec in analysis["recommendations"]:
                action_name = rec["action_name"]

                # Check policy
                policy_eval = self.policy_engine.evaluate_action(
                    action_name=action_name,
                    event_type=ctx.event.event_type.value,
                    confidence=rec["confidence"],
                    existing_actions=[],  # TODO: check approved actions
                )

                # Validate evidence
                evidence_valid, evidence_reason = self.policy_engine.validate_evidence_requirements(
                    action_name=action_name,
                    provided_signals=rec["evidence_signals"],
                    confidence=rec["confidence"],
                )

                ctx.policy_evaluations[action_name] = {
                    "policy_decision": policy_eval.decision.value,
                    "approval_level": policy_eval.approval_level.value,
                    "reason": policy_eval.reason,
                    "constraints_violated": policy_eval.constraints_violated,
                    "evidence_valid": evidence_valid,
                    "evidence_reason": evidence_reason,
                }

    def _simulate_impacts(self, ctx: OrchestrationContext) -> None:
        """Layer 4: Simulate impact of each action."""
        action_names = [
            rec["action_name"]
            for analysis in ctx.agent_analyses
            if "error" not in analysis
            for rec in analysis["recommendations"]
        ]

        for action_name in action_names:
            impact = self.decision_twin.simulate_action(action_name)
            if impact:
                ctx.impact_estimates[action_name] = {
                    "downtime_hours": impact.downtime_hours,
                    "scrap_units": impact.scrap_units,
                    "oee_impact": impact.oee_impact,
                    "cost_impact": impact.cost_impact,
                    "safety_improvement": impact.safety_improvement,
                    "impact_score": impact.calculate_impact_score(),
                    "summary": self.decision_twin.get_impact_summary(impact),
                }

    def _challenge_recommendations(self, ctx: OrchestrationContext) -> None:
        """Layer 5: Red-Team challenges risky recommendations."""
        for analysis in ctx.agent_analyses:
            if "error" in analysis:
                continue

            for rec in analysis["recommendations"]:
                action_name = rec["action_name"]

                review = self.red_team.challenge(
                    action_name=action_name,
                    confidence=rec["confidence"],
                    evidence_signals=rec["evidence_signals"],
                    event_context=ctx.event.context,
                    risk_level=RiskLevel(rec["risk_level"]),
                )

                ctx.red_team_reviews[action_name] = {
                    "risk_factors": review.risk_factors,
                    "assumptions_challenged": review.assumptions_challenged,
                    "suggested_alternatives": review.suggested_alternatives,
                    "confidence_adjustment": review.confidence_adjustment,
                    "overall_risk_assessment": review.overall_risk_assessment,
                    "should_escalate": self.red_team.should_escalate(review),
                    "summary": self.red_team.get_red_team_summary(review),
                }

    def _route_to_approval(self, ctx: OrchestrationContext) -> None:
        """Layer 6: Determine approval routing."""
        # Find highest-priority action that passed policy check
        candidates = []

        for analysis in ctx.agent_analyses:
            if "error" in analysis:
                continue

            for rec in analysis["recommendations"]:
                action_name = rec["action_name"]

                # Only consider policy-allowed actions
                policy_result = ctx.policy_evaluations.get(action_name, {})
                if policy_result.get("policy_decision") == "prohibited":
                    continue

                candidates.append({
                    "action": action_name,
                    "priority": self.policy_engine.actions_db.get(action_name, {}).get("priority", 50),
                    "approval_level": policy_result.get("approval_level"),
                })

        if not candidates:
            ctx.selected_action = None
            ctx.approval_required = False
            ctx.approval_route = "NO_VALID_ACTIONS"
            return

        # Select highest-priority action
        selected = max(candidates, key=lambda x: x["priority"])
        ctx.selected_action = selected["action"]

        # Determine approval routing
        approval_level = selected["approval_level"]
        if approval_level == "auto":
            ctx.approval_required = False
            ctx.approval_route = "AUTO_APPROVED"
        else:
            ctx.approval_required = True
            ctx.approval_route = approval_level

    def _build_decision_response(self, ctx: OrchestrationContext) -> Dict[str, Any]:
        """Layer 7: Build complete decision response with audit trail."""
        return {
            "decision_id": ctx.decision_id,
            "event_id": ctx.event_id,
            "factory_id": ctx.event.factory_id,
            "timestamp": datetime.utcnow().isoformat(),
            "event": {
                "type": ctx.event.event_type.value,
                "signal_name": ctx.event.signal_name,
                "signal_value": ctx.event.signal_value,
                "confidence": ctx.event.confidence,
                "context": ctx.event.context,
            },
            "orchestration_result": {
                "selected_action": ctx.selected_action,
                "approval_required": ctx.approval_required,
                "approval_route": ctx.approval_route,
            },
            "analysis_layers": {
                "agent_analyses": ctx.agent_analyses,
                "policy_evaluations": ctx.policy_evaluations,
                "impact_estimates": ctx.impact_estimates,
                "red_team_reviews": ctx.red_team_reviews,
            },
            "evidence_pack": ctx.to_evidence_pack(),
        }

    def _error_response(self, error: str, ctx: OrchestrationContext) -> Dict[str, Any]:
        """Build error response."""
        return {
            "decision_id": ctx.decision_id,
            "event_id": ctx.event_id,
            "factory_id": ctx.event.factory_id,
            "status": "error",
            "error": error,
            "timestamp": datetime.utcnow().isoformat(),
        }


# Global orchestrator instance
_orchestrator = None


def get_orchestrator() -> Orchestrator:
    """Get or create global orchestrator instance."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = Orchestrator()
    return _orchestrator
