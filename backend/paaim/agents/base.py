"""
Manufacturing specialist agents — Gemini-powered reasoning with rule-based fallback.

Each agent sends the full event context to Gemini and receives structured JSON
back with action recommendations. Rule-based logic kicks in when the API is
unavailable or returns unparseable output.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Dict, Any, Optional
import json
import os
import logging

from pydantic import BaseModel
from paaim.models import ActionRecommendation, RiskLevel, ApprovalLevel
from paaim.model_router.router import get_router, ModelTier
from paaim.observability.tracing import trace_agent

logger = logging.getLogger(__name__)

# ── Allowed action catalogue (Industrial Constitution) ─────────────────────────
# Agents must recommend ONLY from these actions, otherwise the policy engine
# prohibits the recommendation and the decision yields NO_VALID_ACTIONS.

_allowed_actions_cache: Optional[List[Dict[str, str]]] = None


def _get_allowed_actions() -> List[Dict[str, str]]:
    global _allowed_actions_cache
    if _allowed_actions_cache is not None:
        return _allowed_actions_cache
    actions: List[Dict[str, str]] = []
    try:
        from paaim.policy.engine import PolicyEngine
        db = PolicyEngine().actions_db
        for name, meta in db.items():
            actions.append({
                "action_name": name,
                "category": meta.get("category", ""),
                "description": meta.get("description", ""),
                "approval_required": meta.get("approval_required", "operator"),
            })
    except Exception as e:  # pragma: no cover - defensive
        logger.warning(f"Could not load allowed actions: {e}")
    _allowed_actions_cache = actions
    return actions


def _allowed_actions_block() -> str:
    lines = []
    for a in _get_allowed_actions():
        lines.append(
            f"  - {a['action_name']} ({a['category']}, approval: {a['approval_required']}): {a['description']}"
        )
    return "\n".join(lines)


# ── Gemini client (lazy singleton) ────────────────────────────────────────────

_gemini_client = None
_gemini_available = False
_gemini_model_name = ""   # the model actually instantiated, for honest provenance


def _get_gemini():
    global _gemini_client, _gemini_available
    if _gemini_client is not None:
        return _gemini_client, _gemini_available
    try:
        import google.generativeai as genai
        # Prefer the process env, but fall back to the loaded Settings (.env)
        # so the key works for both the API server and offline scripts.
        api_key = os.getenv("GEMINI_API_KEY", "")
        model_name = os.getenv("GEMINI_MODEL", "")
        if not api_key:
            try:
                from paaim.config import settings
                api_key = getattr(settings, "GEMINI_API_KEY", "") or ""
                model_name = model_name or getattr(settings, "GEMINI_MODEL", "")
            except Exception:
                pass
        if api_key:
            genai.configure(api_key=api_key)
            model_name = model_name or "gemini-2.0-flash"
            _gemini_client = genai.GenerativeModel(model_name)
            _gemini_available = True
            global _gemini_model_name
            _gemini_model_name = model_name
            logger.info("Gemini client initialised", extra={"model": model_name})
        else:
            logger.warning("GEMINI_API_KEY not set — agents will use rule-based fallback")
    except ImportError:
        logger.warning("google-generativeai not installed — agents will use rule-based fallback")
    return _gemini_client, _gemini_available


# ── Agent analysis data model ──────────────────────────────────────────────────

class AgentAnalysis(BaseModel):
    # `model_used` collides with pydantic's protected `model_` prefix; the field
    # name is worth keeping because it is what the evidence pack calls it.
    model_config = {"protected_namespaces": ()}

    agent_name: str
    event_type: str
    confidence: float
    recommendations: List[ActionRecommendation]
    reasoning: str
    assumptions: List[str]
    timestamp: Optional[datetime] = None
    # Which model produced this, or None when the deterministic rules did. The
    # product's claim is auditability, but this was dropped during parsing — so
    # the stored evidence could not answer "was this actually AI?".
    model_used: Optional[str] = None

    def __init__(self, **data):
        super().__init__(**data)
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()


# ── Base agent ────────────────────────────────────────────────────────────────

class BaseAgent(ABC):
    def __init__(self, name: str, role: str, event_types: List[str]):
        self.name = name
        self.role = role
        self.event_types = event_types

    @abstractmethod
    async def analyze(self, event_data: Dict[str, Any]) -> AgentAnalysis:
        pass

    @abstractmethod
    def get_schema(self) -> Dict[str, Any]:
        return {"name": self.name, "role": self.role, "event_types": self.event_types, "version": "1.0.0"}

    def _build_prompt(self, event_data: Dict[str, Any], domain_context: str) -> str:
        factory_ctx_block = ""
        if event_data.get("factory_context_text"):
            factory_ctx_block = f"\n{event_data['factory_context_text']}\n"

        memory_block = ""
        if event_data.get("memory_pattern_text"):
            memory_block = f"\n{event_data['memory_pattern_text']}\n"

        # Exclude bulky nested dicts from the JSON dump
        event_for_json = {k: v for k, v in event_data.items()
                          if k not in ("factory_context", "factory_context_text", "memory_pattern_text")}

        return f"""You are a {self.role} in a manufacturing plant.

DOMAIN CONTEXT:
{domain_context}
{factory_ctx_block}{memory_block}
EVENT DATA:
{json.dumps(event_for_json, indent=2, default=str)}

ALLOWED ACTIONS — you MUST set every "action_name" to EXACTLY one of these
(do not invent new action names; pick the closest fit):
{_allowed_actions_block()}

IMPORTANT:
- Use the FACTORY OPERATIONAL CONTEXT to reference real order numbers, deadlines, costs, and machine names.
- Use the AGENT MEMORY to detect patterns: escalating signals, repeated dismissals, concurrent issues.
- If memory shows this signal is escalating or has been dismissed before, increase your confidence and recommend escalation.

Analyse this manufacturing event and respond with ONLY valid JSON:
{{
  "confidence": <float 0.0-1.0>,
  "reasoning": "<one concise sentence explaining your assessment>",
  "assumptions": ["<assumption 1>", "<assumption 2>"],
  "recommendations": [
    {{
      "action_name": "<MUST be one of the ALLOWED ACTIONS above>",
      "description": "<what this action does>",
      "risk_level": "<low|medium|high|critical>",
      "confidence": <float 0.0-1.0>,
      "approval_required": "<auto|operator|supervisor|manager|safety_officer>",
      "assumptions": ["<specific assumption>"],
      "evidence_signals": ["<signal name>"],
      "estimated_impact": {{"downtime_hours": 0, "cost_impact": 0}}
    }}
  ]
}}

Rules:
- action_name MUST be one of the ALLOWED ACTIONS listed above — never invent one.
- Give the approver OPTIONS: list your single best action FIRST, then, when a
  reasonable safer/cheaper/faster alternative exists, add it as a SECOND
  recommendation so the manager can weigh the tradeoff. 1–2 recommendations.
- Make `description` decision-useful: say what the action does AND why, citing
  the real cost, customer order, deadline or recurrence from the context.
- Fill `estimated_impact` with realistic downtime_hours and cost_impact so the
  options can be compared.
- For tool wear / bearing / degradation / heat issues → schedule_maintenance or inspect_root_cause.
- For quality defects → contain_batch or inspect_root_cause.
- For imminent safety/equipment failure → stop_line or escalate_critical.
- For energy/load issues → reduce_consumption or shift_non_critical_load.
- critical risk → approval_required must be safety_officer
- high risk → supervisor or above
- medium risk → operator or above
- low risk → auto
- If confidence < 0.7, return empty recommendations array
- Respond with ONLY the JSON, no markdown, no explanation."""

    async def _call_gemini(self, event_data: Dict[str, Any], domain_context: str) -> Optional[Dict[str, Any]]:
        # ── Model routing decision ──────────────────────────────────────────
        router = get_router()
        has_pattern = bool(event_data.get("memory_pattern_text"))
        has_order = bool(
            event_data.get("factory_context", {}) and
            (event_data.get("factory_context") or {}).get("customer_order") is not None
        )
        risk = event_data.get("risk_level") or "medium"
        model_decision = router.select(
            event_type=event_data.get("event_type", "unknown"),
            risk_level=risk,
            confidence=event_data.get("confidence", 0.8),
            has_memory_pattern=has_pattern,
            has_active_customer_order=has_order,
        )

        # If router says RULES tier — skip LLM entirely, return None (triggers rule-based)
        if model_decision.tier == ModelTier.RULES:
            logger.info(f"{self.name}: routed to RULES tier — {model_decision.reason}")
            return None

        client, available = _get_gemini()
        if not available or client is None:
            return None

        logger.info(
            f"{self.name}: model={_gemini_model_name} tier={model_decision.tier} "
            f"reason='{model_decision.reason}'"
            + ("" if _gemini_model_name == model_decision.model_id
               else f" (router preferred {model_decision.model_id}; one client is configured)")
        )

        prompt = self._build_prompt(event_data, domain_context)
        try:
            response = client.generate_content(prompt)
            text = response.text.strip()
            # Strip markdown code fences if present
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            result = json.loads(text)
            # Attach routing metadata so it appears in the evidence pack
            result["_model_used"] = _gemini_model_name
            result["_model_tier"] = model_decision.tier.value
            result["_routing_reason"] = model_decision.reason
            result["_model_preferred"] = model_decision.model_id
            return result
        except Exception as e:
            logger.warning(f"Gemini call failed for {self.name}: {e}")
            return None

    def _parse_gemini_response(
        self, data: Dict[str, Any], event_type: str
    ) -> AgentAnalysis:
        recommendations = []
        for r in data.get("recommendations", []):
            try:
                recommendations.append(ActionRecommendation(
                    action_name=r["action_name"],
                    description=r.get("description", ""),
                    risk_level=RiskLevel(r.get("risk_level", "medium")),
                    confidence=float(r.get("confidence", 0.8)),
                    approval_required=ApprovalLevel(r.get("approval_required", "operator")),
                    assumptions=r.get("assumptions", []),
                    evidence_signals=r.get("evidence_signals", []),
                    estimated_impact=r.get("estimated_impact", {}),
                ))
            except Exception as e:
                logger.warning(f"Could not parse recommendation: {e}")

        return AgentAnalysis(
            agent_name=self.name,
            event_type=event_type,
            confidence=float(data.get("confidence", 0.8)),
            recommendations=recommendations,
            reasoning=data.get("reasoning", "Gemini analysis"),
            assumptions=data.get("assumptions", []),
            model_used=data.get("_model_used"),
        )


# ── Safety Agent ──────────────────────────────────────────────────────────────

class SafetyAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="safety_agent",
            role="Safety Risk Officer — assess safety risks, prevent worker harm, enforce safety-critical procedures",
            event_types=["safety"],
        )

    @trace_agent("safety_agent")
    async def analyze(self, event_data: Dict[str, Any]) -> AgentAnalysis:
        domain_context = (
            "Safety events require immediate assessment. Zone intrusions with confidence > 0.9 "
            "always trigger line-stop recommendations. E-stop signals are auto-acknowledged. "
            "False positives can cause production loss; false negatives can cause worker injury. "
            "Err on the side of caution."
        )
        gemini_data = await self._call_gemini(event_data, domain_context)
        if gemini_data:
            return self._parse_gemini_response(gemini_data, "safety")
        return self._rule_based(event_data)

    def _rule_based(self, event_data: Dict[str, Any]) -> AgentAnalysis:
        confidence = event_data.get("confidence", 0.5)
        signal_name = event_data.get("signal_name", "")
        recommendations = []
        reasoning = "Safety event detected — rule-based assessment."

        if signal_name == "zone_intrusion" and confidence > 0.9:
            recommendations.append(ActionRecommendation(
                action_name="stop_line",
                description="Stop production line due to safety zone intrusion",
                risk_level=RiskLevel.CRITICAL,
                confidence=confidence,
                approval_required=ApprovalLevel.SAFETY_OFFICER,
                assumptions=["Zone intrusion is genuine", "No safety override active"],
                evidence_signals=["zone_intrusion"],
                estimated_impact={"downtime_hours": 0.5},
            ))
            reasoning = "Critical safety hazard detected. Immediate line stop required."
        elif signal_name == "e_stop_signal":
            recommendations.append(ActionRecommendation(
                action_name="acknowledge_estop",
                description="Acknowledge emergency stop signal",
                risk_level=RiskLevel.CRITICAL,
                confidence=1.0,
                approval_required=ApprovalLevel.AUTO,
                assumptions=["E-stop button activated"],
                evidence_signals=["e_stop_signal"],
                estimated_impact={"immediate_stop": True},
            ))
            reasoning = "E-stop activated. Immediate acknowledgment."

        return AgentAnalysis(
            agent_name=self.name, event_type="safety", confidence=confidence,
            recommendations=recommendations, reasoning=reasoning,
            assumptions=["Sensor data is accurate"],
        )

    def get_schema(self) -> Dict[str, Any]:
        return {**super().get_schema(),
                "inputs": ["zone_intrusion", "e_stop_signal", "anomaly_detection"],
                "outputs": ["stop_line", "acknowledge_estop", "notify_supervisor"]}


# ── Quality Agent ─────────────────────────────────────────────────────────────

class QualityAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="quality_agent",
            role="Quality Control Engineer — detect defects, prevent scrap, coordinate containment and root-cause analysis",
            event_types=["quality"],
        )

    @trace_agent("quality_agent")
    async def analyze(self, event_data: Dict[str, Any]) -> AgentAnalysis:
        domain_context = (
            "Quality events require balancing production continuity with defect prevention. "
            "Defect detection confidence > 0.85 warrants batch containment. Consider scrap rate, "
            "first-pass yield impact, and customer order commitments when recommending actions. "
            "Root cause analysis is preferred over immediate line stop for quality issues."
        )
        gemini_data = await self._call_gemini(event_data, domain_context)
        if gemini_data:
            return self._parse_gemini_response(gemini_data, "quality")
        return self._rule_based(event_data)

    def _rule_based(self, event_data: Dict[str, Any]) -> AgentAnalysis:
        confidence = event_data.get("confidence", 0.5)
        signal_name = event_data.get("signal_name", "")
        recommendations = []
        reasoning = "Quality signal detected — rule-based assessment."

        if signal_name == "defect_detection" and confidence > 0.85:
            recommendations.append(ActionRecommendation(
                action_name="contain_batch",
                description="Contain affected batch for inspection",
                risk_level=RiskLevel.HIGH,
                confidence=confidence,
                approval_required=ApprovalLevel.SUPERVISOR,
                assumptions=["Defect detection is accurate", "Batch is traceable"],
                evidence_signals=["defect_detection"],
                estimated_impact={"scrap_units": 50, "containment_time_hours": 0.25},
            ))
            reasoning = "Quality defect detected. Batch containment recommended."

        return AgentAnalysis(
            agent_name=self.name, event_type="quality", confidence=confidence,
            recommendations=recommendations, reasoning=reasoning,
            assumptions=["Quality sensors are calibrated"],
        )

    def get_schema(self) -> Dict[str, Any]:
        return {**super().get_schema(),
                "inputs": ["defect_detection", "oqs_parameter", "surface_finish"],
                "outputs": ["contain_batch", "inspect_root_cause", "recommend_line_action"]}


# ── Maintenance Agent ─────────────────────────────────────────────────────────

class MaintenanceAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="maintenance_agent",
            role="Predictive Maintenance Engineer — predict equipment failures, optimise maintenance windows, minimise unplanned downtime",
            event_types=["maintenance"],
        )

    @trace_agent("maintenance_agent")
    async def analyze(self, event_data: Dict[str, Any]) -> AgentAnalysis:
        domain_context = (
            "Maintenance events require distinguishing transient anomalies from genuine degradation trends. "
            "Vibration anomalies above 3σ indicate bearing failure within 48-72h. Temperature trends "
            "exceeding normal range by 15°C require immediate attention. Balance planned downtime cost "
            "against unplanned failure cost (typically 5-10x more expensive)."
        )
        gemini_data = await self._call_gemini(event_data, domain_context)
        if gemini_data:
            return self._parse_gemini_response(gemini_data, "maintenance")
        return self._rule_based(event_data)

    def _rule_based(self, event_data: Dict[str, Any]) -> AgentAnalysis:
        confidence = event_data.get("confidence", 0.5)
        signal_name = event_data.get("signal_name", "")
        recommendations = []
        reasoning = "Maintenance signal detected — rule-based assessment."

        if signal_name == "vibration_anomaly" and confidence > 0.8:
            recommendations.append(ActionRecommendation(
                action_name="schedule_maintenance",
                description="Schedule predictive maintenance for bearing degradation",
                risk_level=RiskLevel.MEDIUM,
                confidence=confidence,
                approval_required=ApprovalLevel.OPERATOR,
                assumptions=["Vibration sensor is accurate", "Bearing degradation model is valid"],
                evidence_signals=["vibration_anomaly"],
                estimated_impact={"estimated_failure_hours": 48, "maintenance_time_hours": 2},
            ))
            reasoning = "Bearing degradation predicted. Schedule maintenance within 48h."

        return AgentAnalysis(
            agent_name=self.name, event_type="maintenance", confidence=confidence,
            recommendations=recommendations, reasoning=reasoning,
            assumptions=["Predictive models are accurate"],
        )

    def get_schema(self) -> Dict[str, Any]:
        return {**super().get_schema(),
                "inputs": ["vibration_anomaly", "temperature_trend", "oil_analysis"],
                "outputs": ["schedule_maintenance", "escalate_critical", "coordinate_downtime"]}


# ── Production Agent ──────────────────────────────────────────────────────────

class ProductionAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="production_agent",
            role="Production Scheduler — track order status, identify bottlenecks, coordinate recovery plans to protect delivery commitments",
            event_types=["production"],
        )

    @trace_agent("production_agent")
    async def analyze(self, event_data: Dict[str, Any]) -> AgentAnalysis:
        domain_context = (
            "Production events require balancing order commitments against resource constraints. "
            "An order at risk means it will miss its delivery window without intervention. "
            "Consider overtime cost, resource availability, quality-under-rush risks, and "
            "customer relationship impact when recommending recovery actions."
        )
        gemini_data = await self._call_gemini(event_data, domain_context)
        if gemini_data:
            return self._parse_gemini_response(gemini_data, "production")
        return self._rule_based(event_data)

    def _rule_based(self, event_data: Dict[str, Any]) -> AgentAnalysis:
        confidence = event_data.get("confidence", 0.5)
        signal_name = event_data.get("signal_name", "")
        recommendations = []
        reasoning = "Production signal detected — rule-based assessment."

        if signal_name == "order_at_risk" and confidence > 0.75:
            recommendations.append(ActionRecommendation(
                action_name="propose_recovery_plan",
                description="Propose recovery plan to meet order deadline",
                risk_level=RiskLevel.MEDIUM,
                confidence=confidence,
                approval_required=ApprovalLevel.SUPERVISOR,
                assumptions=["Order deadline is fixed", "Alternative resources available"],
                evidence_signals=["order_at_risk", "throughput_trend"],
                estimated_impact={"recovery_hours": 8, "overtime_cost": 500},
            ))
            reasoning = "Production order at risk. Recovery plan proposed."

        return AgentAnalysis(
            agent_name=self.name, event_type="production", confidence=confidence,
            recommendations=recommendations, reasoning=reasoning,
            assumptions=["Production schedule is accurate"],
        )

    def get_schema(self) -> Dict[str, Any]:
        return {**super().get_schema(),
                "inputs": ["order_at_risk", "throughput_trend", "bottleneck_detection"],
                "outputs": ["propose_recovery_plan", "estimate_quota_impact", "suggest_rerouting"]}


# ── Energy Agent ──────────────────────────────────────────────────────────────

class EnergyAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="energy_agent",
            role="Energy Optimisation Engineer — minimise energy costs through demand response, load shifting, and consumption reduction",
            event_types=["energy"],
        )

    @trace_agent("energy_agent")
    async def analyze(self, event_data: Dict[str, Any]) -> AgentAnalysis:
        domain_context = (
            "Energy events are cost-optimisation opportunities. Peak pricing windows (>2x base rate) "
            "warrant shifting deferrable loads to off-peak hours. Evaluate: which loads are truly "
            "non-critical, what delay is acceptable, and whether shifting violates any customer "
            "commitments. Grid signals may indicate demand-response programme participation."
        )
        gemini_data = await self._call_gemini(event_data, domain_context)
        if gemini_data:
            return self._parse_gemini_response(gemini_data, "energy")
        return self._rule_based(event_data)

    def _rule_based(self, event_data: Dict[str, Any]) -> AgentAnalysis:
        confidence = event_data.get("confidence", 0.5)
        signal_name = event_data.get("signal_name", "")
        recommendations = []
        reasoning = "Energy signal detected — rule-based assessment."

        if signal_name == "peak_pricing_window" and confidence > 0.9:
            recommendations.append(ActionRecommendation(
                action_name="shift_non_critical_load",
                description="Shift non-critical loads to off-peak window",
                risk_level=RiskLevel.LOW,
                confidence=confidence,
                approval_required=ApprovalLevel.OPERATOR,
                assumptions=["Non-critical loads are flexible", "Off-peak window available"],
                evidence_signals=["peak_pricing_window"],
                estimated_impact={"cost_savings": 1500, "delay_hours": 2},
            ))
            reasoning = "Peak pricing window detected. Load shifting recommended."

        return AgentAnalysis(
            agent_name=self.name, event_type="energy", confidence=confidence,
            recommendations=recommendations, reasoning=reasoning,
            assumptions=["Energy pricing data is accurate"],
        )

    def get_schema(self) -> Dict[str, Any]:
        return {**super().get_schema(),
                "inputs": ["peak_pricing_window", "grid_signal", "load_trend"],
                "outputs": ["shift_non_critical_load", "reduce_consumption", "notify_energy_mgmt"]}
