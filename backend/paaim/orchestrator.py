import asyncio
import uuid
import time
from datetime import datetime
from typing import Dict, List, Any, Optional

from paaim.models import EventData, DecisionStatus, RiskLevel
from paaim.agents.registry import get_registry
from paaim.policy.engine import PolicyEngine
from paaim.decision_twin.simulator import DecisionTwin
from paaim.governance.red_team import RedTeamAgent
from paaim.streaming import get_publisher, PipelineEventType, PipelineEvent
from paaim.agents.custom_framework import get_custom_agent_registry
from paaim.context.factory_context import FactoryContext
from paaim.memory.short_term import get_memory_store, MemoryEntry
from paaim.observability.tracing import trace_pipeline, trace_async


class OrchestrationContext:
    """Holds state across the 7-layer pipeline for a single event."""

    def __init__(self, event: EventData):
        self.event = event
        self.event_id = f"{event.event_type.value}_{uuid.uuid4().hex[:8]}"
        self.decision_id = f"dec_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        self.timestamp_start = datetime.utcnow()

        self.agent_analyses: List[Dict[str, Any]] = []
        self.policy_evaluations: Dict[str, Any] = {}
        self.impact_estimates: Dict[str, Any] = {}
        self.red_team_reviews: Dict[str, Any] = {}
        self.selected_action: Optional[str] = None
        self.selected_risk_level: Optional[str] = None
        self.approval_required: bool = False
        self.approval_route: Optional[str] = None
        self.factory_context: Optional[FactoryContext] = None  # injected by Layer 1.5
        self.memory_pattern = None                             # injected by Layer 1.8

        # Per-layer wall-clock timing in milliseconds
        self.layer_latencies: Dict[str, float] = {}

    def to_evidence_pack(self) -> Dict[str, Any]:
        pack = {
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
            "factory_context": self.factory_context.to_dict() if self.factory_context else None,
            "memory_pattern": {
                "occurrence_count": self.memory_pattern.occurrence_count,
                "value_trend": self.memory_pattern.value_trend,
                "value_delta": self.memory_pattern.value_delta,
                "dismissed_count": self.memory_pattern.dismissed_count,
                "approved_count": self.memory_pattern.approved_count,
                "hours_since_first": self.memory_pattern.hours_since_first,
                "other_recent_events": self.memory_pattern.other_recent_events,
            } if self.memory_pattern else None,
            "agent_analyses": self.agent_analyses,
            "policy_evaluation": self.policy_evaluations,
            "decision_twin_simulation": self.impact_estimates,
            "red_team_challenges": self.red_team_reviews,
            "approval_decision": {
                "required": self.approval_required,
                "route": self.approval_route,
            },
        }
        return pack


class Orchestrator:
    """
    Coordinates the 7-layer event → decision pipeline.

    Layers:
    1. Event ingestion (caller)
    2. Agent routing + analysis
    3. Policy evaluation
    4. Decision Twin simulation
    5. Red-Team challenge
    6. Approval routing
    7. Audit trail + response
    """

    def __init__(self):
        self.policy_engine = PolicyEngine()
        self.decision_twin = DecisionTwin()
        self.red_team = RedTeamAgent()
        self.registry = get_registry()
        self.custom_registry = get_custom_agent_registry()
        self.publisher = get_publisher()

    @trace_pipeline("paaim_orchestrate")
    async def orchestrate(self, event: EventData, db=None) -> Dict[str, Any]:
        ctx = OrchestrationContext(event)

        await self._emit(PipelineEventType.ORCHESTRATION_STARTED, ctx.decision_id, "pipeline", {
            "event_type": event.event_type.value,
            "signal_name": event.signal_name,
            "factory_id": event.factory_id,
        })

        try:
            # Layer 1.5 — Factory Context enrichment
            if db is not None:
                try:
                    from paaim.context.factory_context import get_context_service
                    t0 = time.perf_counter()
                    ctx.factory_context = await get_context_service().build_context(
                        event.factory_id, event.machine_id, db
                    )
                    ctx.layer_latencies["factory_context"] = round((time.perf_counter() - t0) * 1000, 1)
                    await self._emit(PipelineEventType.AGENTS_ROUTING, ctx.decision_id, "context", {
                        "status": "context_loaded",
                        "has_work_order": ctx.factory_context.active_work_order is not None,
                        "has_customer_order": ctx.factory_context.customer_order is not None,
                    })
                except Exception as e:
                    import logging
                    logging.getLogger(__name__).warning(f"Factory context fetch failed: {e}")

            # Layer 1.8 — Short-term memory: record event + fetch pattern for this machine
            memory = get_memory_store()
            if event.machine_id:
                memory.record(MemoryEntry(
                    machine_id=event.machine_id,
                    factory_id=event.factory_id,
                    event_type=event.event_type.value,
                    signal_name=event.signal_name,
                    signal_value=event.signal_value,
                    confidence=event.confidence,
                ))
                ctx.memory_pattern = memory.get_pattern(
                    event.factory_id, event.machine_id, event.signal_name
                )
            else:
                ctx.memory_pattern = None

            # Layer 2 — Agent analysis
            await self._emit(PipelineEventType.AGENTS_ROUTING, ctx.decision_id, "agents", {"status": "routing"})
            t0 = time.perf_counter()
            await self._route_to_agents(ctx)
            ctx.layer_latencies["agent_analysis"] = round((time.perf_counter() - t0) * 1000, 1)

            if not ctx.agent_analyses:
                return self._error_response("No agents matched event type", ctx)

            await self._emit(PipelineEventType.AGENTS_COMPLETE, ctx.decision_id, "agents",
                             {"agent_count": len(ctx.agent_analyses),
                              "latency_ms": ctx.layer_latencies["agent_analysis"]})

            # Layer 3 — Policy evaluation
            await self._emit(PipelineEventType.POLICY_CHECKING, ctx.decision_id, "policy", {"status": "evaluating"})
            t0 = time.perf_counter()
            self._evaluate_policy(ctx)
            ctx.layer_latencies["policy_engine"] = round((time.perf_counter() - t0) * 1000, 1)
            await self._emit(PipelineEventType.POLICY_COMPLETE, ctx.decision_id, "policy",
                             {"evaluations": len(ctx.policy_evaluations),
                              "latency_ms": ctx.layer_latencies["policy_engine"]})

            # Layer 4 — Decision Twin simulation
            await self._emit(PipelineEventType.TWIN_SIMULATING, ctx.decision_id, "twin", {"status": "simulating"})
            t0 = time.perf_counter()
            self._simulate_impacts(ctx)
            ctx.layer_latencies["decision_twin"] = round((time.perf_counter() - t0) * 1000, 1)
            await self._emit(PipelineEventType.TWIN_COMPLETE, ctx.decision_id, "twin",
                             {"simulations": len(ctx.impact_estimates),
                              "latency_ms": ctx.layer_latencies["decision_twin"]})

            # Layer 5 — Red-Team challenge
            await self._emit(PipelineEventType.RED_TEAM_CHALLENGING, ctx.decision_id, "red_team", {"status": "challenging"})
            t0 = time.perf_counter()
            self._challenge_recommendations(ctx)
            ctx.layer_latencies["red_team"] = round((time.perf_counter() - t0) * 1000, 1)
            await self._emit(PipelineEventType.RED_TEAM_COMPLETE, ctx.decision_id, "red_team",
                             {"reviews": len(ctx.red_team_reviews),
                              "latency_ms": ctx.layer_latencies["red_team"]})

            # Layer 6 — Approval routing
            await self._emit(PipelineEventType.APPROVAL_ROUTING, ctx.decision_id, "approval", {"status": "routing"})
            t0 = time.perf_counter()
            self._route_to_approval(ctx)
            ctx.layer_latencies["approval_gate"] = round((time.perf_counter() - t0) * 1000, 1)
            await self._emit(PipelineEventType.APPROVAL_COMPLETE, ctx.decision_id, "approval",
                             {"approval_route": ctx.approval_route,
                              "latency_ms": ctx.layer_latencies["approval_gate"]})

            # Layer 7 — Build response
            t0 = time.perf_counter()
            response = self._build_decision_response(ctx)
            ctx.layer_latencies["audit_logger"] = round((time.perf_counter() - t0) * 1000, 1)

            total_ms = round((datetime.utcnow() - ctx.timestamp_start).total_seconds() * 1000, 1)
            ctx.layer_latencies["total"] = total_ms

            await self._emit(PipelineEventType.ORCHESTRATION_COMPLETED, ctx.decision_id, "pipeline",
                             {"status": "success", "latency_ms": total_ms})

            response["layer_latencies"] = ctx.layer_latencies
            return response

        except Exception as e:
            await self._emit(PipelineEventType.ORCHESTRATION_ERROR, ctx.decision_id, "pipeline", {"error": str(e)})
            raise

    async def _emit(self, event_type: PipelineEventType, decision_id: str, layer: str, data: Dict[str, Any]) -> None:
        if self.publisher.has_subscribers(decision_id):
            await self.publisher.emit(PipelineEvent(event_type, decision_id, layer, data))

    async def _route_to_agents(self, ctx: OrchestrationContext) -> None:
        agents = self.registry.get_agents_for_event_type(ctx.event.event_type.value)

        # Build enriched event data with factory context + memory
        memory_text = (
            ctx.memory_pattern.to_prompt_text(ctx.event.signal_name, ctx.event.machine_id or "unknown")
            if ctx.memory_pattern else None
        )
        enriched_event = {
            "event_type": ctx.event.event_type.value,
            "signal_name": ctx.event.signal_name,
            "signal_value": ctx.event.signal_value,
            "confidence": ctx.event.confidence,
            "context": ctx.event.context,
            "machine_id": ctx.event.machine_id,
            "factory_id": ctx.event.factory_id,
            "factory_context": ctx.factory_context.to_dict() if ctx.factory_context else None,
            "factory_context_text": ctx.factory_context.to_prompt_text() if ctx.factory_context else None,
            "memory_pattern_text": memory_text,
        }

        # Run all specialist agents concurrently — each makes its own LLM call,
        # so gathering them cuts per-event latency from sum() to max().
        agent_results = await asyncio.gather(
            *(agent.analyze(enriched_event) for agent in agents),
            return_exceptions=True,
        )
        for agent, analysis in zip(agents, agent_results):
            if isinstance(analysis, Exception):
                ctx.agent_analyses.append({"agent": agent.name, "error": str(analysis)})
                continue
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

        # Custom agents
        for custom_agent in self.custom_registry.list_agents():
            if not custom_agent.enabled:
                continue
            try:
                event_data = {
                    "event_type": ctx.event.event_type.value,
                    "signal_name": ctx.event.signal_name,
                    "signal_value": ctx.event.signal_value,
                    "confidence": ctx.event.confidence,
                }
                event_data.update(ctx.event.context)
                recommendations = await self.custom_registry.execute_agent_async(custom_agent.id, event_data)
                if recommendations:
                    ctx.agent_analyses.append({
                        "agent": custom_agent.name,
                        "confidence": 0.8,
                        "reasoning": f"Custom agent {custom_agent.domain} evaluated event",
                        "recommendations": recommendations,
                    })
            except Exception as e:
                ctx.agent_analyses.append({"agent": custom_agent.name, "error": str(e)})

    def _evaluate_policy(self, ctx: OrchestrationContext) -> None:
        for analysis in ctx.agent_analyses:
            if "error" in analysis:
                continue
            for rec in analysis["recommendations"]:
                action_name = rec["action_name"]
                policy_eval = self.policy_engine.evaluate_action(
                    action_name=action_name,
                    event_type=ctx.event.event_type.value,
                    confidence=rec["confidence"],
                    existing_actions=[],
                )
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
                    risk_level=RiskLevel(rec["risk_level"].lower()),
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
        candidates = []
        for analysis in ctx.agent_analyses:
            if "error" in analysis:
                continue
            for rec in analysis["recommendations"]:
                action_name = rec["action_name"]
                policy_result = ctx.policy_evaluations.get(action_name, {})
                if policy_result.get("policy_decision") == "prohibited":
                    continue
                candidates.append({
                    "action": action_name,
                    "priority": self.policy_engine.actions_db.get(action_name, {}).get("priority", 50),
                    "approval_level": policy_result.get("approval_level"),
                    "risk_level": rec.get("risk_level"),
                })

        if not candidates:
            ctx.selected_action = None
            ctx.selected_risk_level = None
            ctx.approval_required = False
            ctx.approval_route = "NO_VALID_ACTIONS"
            return

        selected = max(candidates, key=lambda x: x["priority"])
        ctx.selected_action = selected["action"]
        ctx.selected_risk_level = selected.get("risk_level")
        approval_level = selected["approval_level"]

        if approval_level == "auto":
            ctx.approval_required = False
            ctx.approval_route = "AUTO_APPROVED"
        else:
            ctx.approval_required = True
            ctx.approval_route = approval_level

    def _build_decision_response(self, ctx: OrchestrationContext) -> Dict[str, Any]:
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
                "machine_id": ctx.event.machine_id,
                "context": ctx.event.context,
            },
            "orchestration_result": {
                "selected_action": ctx.selected_action,
                "risk_level": ctx.selected_risk_level,
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
        return {
            "decision_id": ctx.decision_id,
            "event_id": ctx.event_id,
            "factory_id": ctx.event.factory_id,
            "status": "error",
            "error": error,
            "timestamp": datetime.utcnow().isoformat(),
        }


_orchestrator: Optional[Orchestrator] = None


def get_orchestrator() -> Orchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = Orchestrator()
    return _orchestrator
