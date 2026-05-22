from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from paaim.models import ActionRecommendation, RiskLevel, ApprovalLevel


class AgentAnalysis(BaseModel):
    """Analysis result from an agent."""
    agent_name: str
    event_type: str
    confidence: float
    recommendations: List[ActionRecommendation]
    reasoning: str
    assumptions: List[str]
    timestamp: datetime = None

    def __init__(self, **data):
        super().__init__(**data)
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()


class BaseAgent(ABC):
    """Abstract base class for all manufacturing agents."""

    def __init__(self, name: str, role: str, event_types: List[str]):
        """
        Initialize agent.

        Args:
            name: Unique agent identifier (e.g., "safety_agent")
            role: Agent role description (e.g., "Safety risk assessment")
            event_types: List of event types this agent handles (e.g., ["safety", "compliance"])
        """
        self.name = name
        self.role = role
        self.event_types = event_types

    @abstractmethod
    async def analyze(self, event_data: Dict[str, Any]) -> AgentAnalysis:
        """
        Analyze an event and produce recommendations.

        Args:
            event_data: Event data from manufacturing system

        Returns:
            AgentAnalysis with recommendations
        """
        pass

    @abstractmethod
    def get_schema(self) -> Dict[str, Any]:
        """Return agent schema for registry and discovery."""
        return {
            "name": self.name,
            "role": self.role,
            "event_types": self.event_types,
            "version": "0.1.0"
        }


class SafetyAgent(BaseAgent):
    """Safety event analysis agent."""

    def __init__(self):
        super().__init__(
            name="safety_agent",
            role="Assess safety risks and coordinate safety-critical actions",
            event_types=["safety"]
        )

    async def analyze(self, event_data: Dict[str, Any]) -> AgentAnalysis:
        """Analyze safety event."""
        confidence = event_data.get("confidence", 0.5)
        signal_name = event_data.get("signal_name", "")

        recommendations = []
        reasoning = ""

        if signal_name == "zone_intrusion" and confidence > 0.9:
            recommendations.append(ActionRecommendation(
                action_name="stop_line",
                description="Stop production line due to safety zone intrusion",
                risk_level=RiskLevel.CRITICAL,
                confidence=confidence,
                approval_required=ApprovalLevel.SAFETY_OFFICER,
                assumptions=["Zone intrusion is genuine", "No safety override active"],
                evidence_signals=["zone_intrusion"],
                estimated_impact={"downtime_hours": 0.5}
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
                estimated_impact={"immediate_stop": True}
            ))
            reasoning = "E-stop activated. Immediate action taken."
        else:
            reasoning = "Safety event detected but confidence too low for action."

        return AgentAnalysis(
            agent_name=self.name,
            event_type="safety",
            confidence=confidence,
            recommendations=recommendations,
            reasoning=reasoning,
            assumptions=["Sensor data is accurate", "Factory is in normal operating mode"]
        )

    def get_schema(self) -> Dict[str, Any]:
        return {
            **super().get_schema(),
            "inputs": ["zone_intrusion", "e_stop_signal", "anomaly_detection"],
            "outputs": ["stop_line", "acknowledge_estop", "notify_supervisor"]
        }


class QualityAgent(BaseAgent):
    """Quality event analysis agent."""

    def __init__(self):
        super().__init__(
            name="quality_agent",
            role="Detect quality defects and coordinate containment actions",
            event_types=["quality"]
        )

    async def analyze(self, event_data: Dict[str, Any]) -> AgentAnalysis:
        """Analyze quality event."""
        confidence = event_data.get("confidence", 0.5)
        signal_name = event_data.get("signal_name", "")

        recommendations = []
        reasoning = ""

        if signal_name == "defect_detection" and confidence > 0.85:
            recommendations.append(ActionRecommendation(
                action_name="contain_batch",
                description="Contain affected batch for inspection",
                risk_level=RiskLevel.HIGH,
                confidence=confidence,
                approval_required=ApprovalLevel.SUPERVISOR,
                assumptions=["Defect detection is accurate", "Batch traceable"],
                evidence_signals=["defect_detection"],
                estimated_impact={"scrap_units": 50, "containment_time_hours": 0.25}
            ))
            reasoning = "Quality defect detected with high confidence. Batch containment recommended."
        else:
            reasoning = "Quality signal detected but confidence too low for action."

        return AgentAnalysis(
            agent_name=self.name,
            event_type="quality",
            confidence=confidence,
            recommendations=recommendations,
            reasoning=reasoning,
            assumptions=["Quality sensors are calibrated", "Defect thresholds are set correctly"]
        )

    def get_schema(self) -> Dict[str, Any]:
        return {
            **super().get_schema(),
            "inputs": ["defect_detection", "oqs_parameter", "surface_finish"],
            "outputs": ["contain_batch", "inspect_root_cause", "recommend_line_action"]
        }


class MaintenanceAgent(BaseAgent):
    """Maintenance event analysis agent."""

    def __init__(self):
        super().__init__(
            name="maintenance_agent",
            role="Predict failures and coordinate maintenance actions",
            event_types=["maintenance"]
        )

    async def analyze(self, event_data: Dict[str, Any]) -> AgentAnalysis:
        """Analyze maintenance event."""
        confidence = event_data.get("confidence", 0.5)
        signal_name = event_data.get("signal_name", "")

        recommendations = []
        reasoning = ""

        if signal_name == "vibration_anomaly" and confidence > 0.8:
            recommendations.append(ActionRecommendation(
                action_name="schedule_maintenance",
                description="Schedule predictive maintenance for bearing degradation",
                risk_level=RiskLevel.MEDIUM,
                confidence=confidence,
                approval_required=ApprovalLevel.OPERATOR,
                assumptions=["Vibration sensor is accurate", "Bearing degradation model is valid"],
                evidence_signals=["vibration_anomaly"],
                estimated_impact={"estimated_failure_hours": 48, "maintenance_time_hours": 2}
            ))
            reasoning = "Bearing degradation predicted. Schedule maintenance within 48 hours."
        else:
            reasoning = "Maintenance signal detected but confidence too low for action."

        return AgentAnalysis(
            agent_name=self.name,
            event_type="maintenance",
            confidence=confidence,
            recommendations=recommendations,
            reasoning=reasoning,
            assumptions=["Predictive models are accurate", "Maintenance windows are available"]
        )

    def get_schema(self) -> Dict[str, Any]:
        return {
            **super().get_schema(),
            "inputs": ["vibration_anomaly", "temperature_trend", "oil_analysis"],
            "outputs": ["schedule_maintenance", "escalate_critical", "coordinate_downtime"]
        }


class ProductionAgent(BaseAgent):
    """Production event analysis agent."""

    def __init__(self):
        super().__init__(
            name="production_agent",
            role="Track production status and coordinate recovery actions",
            event_types=["production"]
        )

    async def analyze(self, event_data: Dict[str, Any]) -> AgentAnalysis:
        """Analyze production event."""
        confidence = event_data.get("confidence", 0.5)
        signal_name = event_data.get("signal_name", "")

        recommendations = []
        reasoning = ""

        if signal_name == "order_at_risk" and confidence > 0.75:
            recommendations.append(ActionRecommendation(
                action_name="propose_recovery_plan",
                description="Propose recovery plan to meet order deadline",
                risk_level=RiskLevel.MEDIUM,
                confidence=confidence,
                approval_required=ApprovalLevel.SUPERVISOR,
                assumptions=["Order deadline is fixed", "Alternative resources available"],
                evidence_signals=["order_at_risk", "throughput_trend"],
                estimated_impact={"recovery_hours": 8, "overtime_cost": 500}
            ))
            reasoning = "Production order at risk. Recovery plan proposed."
        else:
            reasoning = "Production signal detected but confidence too low for action."

        return AgentAnalysis(
            agent_name=self.name,
            event_type="production",
            confidence=confidence,
            recommendations=recommendations,
            reasoning=reasoning,
            assumptions=["Production schedule is accurate", "WIP data is current"]
        )

    def get_schema(self) -> Dict[str, Any]:
        return {
            **super().get_schema(),
            "inputs": ["order_at_risk", "throughput_trend", "bottleneck_detection"],
            "outputs": ["propose_recovery_plan", "estimate_quota_impact", "suggest_rerouting"]
        }


class EnergyAgent(BaseAgent):
    """Energy cost optimization agent."""

    def __init__(self):
        super().__init__(
            name="energy_agent",
            role="Optimize energy costs and coordinate load shifting",
            event_types=["energy"]
        )

    async def analyze(self, event_data: Dict[str, Any]) -> AgentAnalysis:
        """Analyze energy event."""
        confidence = event_data.get("confidence", 0.5)
        signal_name = event_data.get("signal_name", "")

        recommendations = []
        reasoning = ""

        if signal_name == "peak_pricing_window" and confidence > 0.9:
            recommendations.append(ActionRecommendation(
                action_name="shift_non_critical_load",
                description="Shift non-critical production loads to off-peak window",
                risk_level=RiskLevel.LOW,
                confidence=confidence,
                approval_required=ApprovalLevel.OPERATOR,
                assumptions=["Non-critical loads are flexible", "Off-peak window available"],
                evidence_signals=["peak_pricing_window"],
                estimated_impact={"cost_savings": 1500, "delay_hours": 2}
            ))
            reasoning = "Peak pricing window detected. Load shifting recommended."
        else:
            reasoning = "Energy signal detected but confidence too low for action."

        return AgentAnalysis(
            agent_name=self.name,
            event_type="energy",
            confidence=confidence,
            recommendations=recommendations,
            reasoning=reasoning,
            assumptions=["Energy pricing is accurate", "Load profiles are flexible"]
        )

    def get_schema(self) -> Dict[str, Any]:
        return {
            **super().get_schema(),
            "inputs": ["peak_pricing_window", "grid_signal", "load_trend"],
            "outputs": ["shift_non_critical_load", "reduce_consumption", "notify_energy_mgmt"]
        }
