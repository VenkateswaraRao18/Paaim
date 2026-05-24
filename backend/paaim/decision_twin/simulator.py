from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime


@dataclass
class ImpactEstimate:
    """Estimated impact of an action."""

    action_name: str
    downtime_hours: float
    scrap_units: int
    oee_impact: float  # percentage change
    cost_impact: float  # dollars (negative = savings)
    safety_improvement: Optional[str] = None
    quality_improvement: Optional[str] = None
    recovery_hours: Optional[float] = None
    delay_hours: Optional[float] = None
    confidence: float = 0.75  # Confidence in estimate
    notes: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            k: v
            for k, v in asdict(self).items()
            if v is not None
        }

    def calculate_impact_score(self) -> float:
        """
        Calculate normalized impact score (0.0-1.0).

        Higher score = better outcome.
        Considers downtime, scrap, cost, and safety.
        """
        score = 0.5  # Base score

        # Downtime impact (negative): each hour reduces score by 0.05
        score -= min(self.downtime_hours * 0.05, 0.3)

        # Scrap impact (negative): each 50 units reduces score by 0.05
        score -= min((self.scrap_units / 50) * 0.05, 0.2)

        # Cost impact (negative if cost > 0): each $1000 reduces score by 0.05
        if self.cost_impact > 0:
            score -= min((self.cost_impact / 1000) * 0.05, 0.2)
        elif self.cost_impact < 0:
            # Positive (savings): each $1000 saved increases score by 0.02
            score += min(abs(self.cost_impact / 1000) * 0.02, 0.15)

        # Safety improvement (positive): safety always adds
        if self.safety_improvement == "critical":
            score += 0.2
        elif self.safety_improvement == "high":
            score += 0.1
        elif self.safety_improvement == "low_hazard_removed":
            score += 0.05

        # OEE impact
        if self.oee_impact > 0:
            score += min((self.oee_impact / 10) * 0.05, 0.1)
        else:
            score -= min(abs(self.oee_impact / 10) * 0.05, 0.1)

        # Clamp to 0-1
        return max(0.0, min(1.0, score))


class DecisionTwin:
    """
    Decision Twin: simulates action impact before execution.

    MVP version uses hardcoded impact rules for startup speed.
    Phase 2 will add real digital twin with detailed simulation.
    """

    def __init__(self):
        """Initialize Decision Twin with impact rules."""
        self.impact_rules = self._load_impact_rules()

    def _load_impact_rules(self) -> Dict[str, ImpactEstimate]:
        """Load hardcoded impact rules for each action."""
        return {
            # Safety actions
            "stop_line": ImpactEstimate(
                action_name="stop_line",
                downtime_hours=0.5,
                scrap_units=0,
                oee_impact=-5.0,
                cost_impact=-2000,
                safety_improvement="critical",
                notes="Immediate line stop for safety hazard",
            ),
            "acknowledge_estop": ImpactEstimate(
                action_name="acknowledge_estop",
                downtime_hours=0.25,
                scrap_units=0,
                oee_impact=-2.0,
                cost_impact=-1000,
                safety_improvement="critical",
                notes="Emergency stop acknowledgment",
            ),
            # Quality actions
            "contain_batch": ImpactEstimate(
                action_name="contain_batch",
                downtime_hours=0.25,
                scrap_units=-50,  # Negative = prevented
                oee_impact=-1.0,
                cost_impact=-500,
                quality_improvement="high",
                notes="Hold batch for inspection, prevent scrap",
            ),
            "inspect_root_cause": ImpactEstimate(
                action_name="inspect_root_cause",
                downtime_hours=1.0,
                scrap_units=0,
                oee_impact=-2.0,
                cost_impact=-300,
                quality_improvement="high",
                notes="Quality root cause analysis",
            ),
            "release_batch": ImpactEstimate(
                action_name="release_batch",
                downtime_hours=0.0,
                scrap_units=50,  # Risk: defective units released
                oee_impact=2.0,
                cost_impact=1500,
                quality_improvement=None,
                notes="Release batch - carries quality risk",
            ),
            # Maintenance actions
            "schedule_maintenance": ImpactEstimate(
                action_name="schedule_maintenance",
                downtime_hours=2.0,
                scrap_units=0,
                oee_impact=-3.0,
                cost_impact=-1500,
                recovery_hours=2.0,
                notes="Predictive maintenance prevents failure",
            ),
            "escalate_critical": ImpactEstimate(
                action_name="escalate_critical",
                downtime_hours=0.5,
                scrap_units=0,
                oee_impact=-2.0,
                cost_impact=-500,
                recovery_hours=4.0,
                notes="Escalate to management for critical maintenance",
            ),
            # Production actions
            "propose_recovery_plan": ImpactEstimate(
                action_name="propose_recovery_plan",
                downtime_hours=0.0,
                scrap_units=0,
                oee_impact=3.0,
                cost_impact=500,  # Overtime cost
                recovery_hours=8.0,
                notes="Plan recovery to meet deadline",
            ),
            "adjust_schedule": ImpactEstimate(
                action_name="adjust_schedule",
                downtime_hours=0.0,
                scrap_units=0,
                oee_impact=1.0,
                cost_impact=0.0,
                recovery_hours=2.0,
                notes="Adjust production schedule",
            ),
            # Energy actions
            "shift_non_critical_load": ImpactEstimate(
                action_name="shift_non_critical_load",
                downtime_hours=0.0,
                scrap_units=0,
                oee_impact=-1.0,
                cost_impact=-1500,  # Savings
                delay_hours=2.0,
                notes="Shift load to off-peak for cost savings",
            ),
            "reduce_consumption": ImpactEstimate(
                action_name="reduce_consumption",
                downtime_hours=0.0,
                scrap_units=0,
                oee_impact=-0.5,
                cost_impact=-500,
                notes="Reduce energy consumption",
            ),
        }

    def simulate_action(self, action_name: str) -> Optional[ImpactEstimate]:
        """Get impact estimate for an action."""
        return self.impact_rules.get(action_name)

    def simulate_multiple_actions(
        self, actions: List[str]
    ) -> Dict[str, ImpactEstimate]:
        """Simulate multiple actions and return impact for each."""
        results = {}
        for action in actions:
            impact = self.simulate_action(action)
            if impact:
                results[action] = impact
        return results

    def compare_alternatives(
        self, action_candidates: List[Tuple[str, float]]
    ) -> List[Dict[str, Any]]:
        """
        Compare alternative actions and score them.

        Args:
            action_candidates: List of (action_name, confidence) tuples

        Returns:
            Sorted list of actions with impacts and scores
        """
        results = []

        for action_name, confidence in action_candidates:
            impact = self.simulate_action(action_name)
            if not impact:
                continue

            # Adjust confidence-based on impact estimate confidence
            adjusted_confidence = (confidence + impact.confidence) / 2

            score = impact.calculate_impact_score()

            results.append({
                "action_name": action_name,
                "confidence": adjusted_confidence,
                "impact": impact.to_dict(),
                "impact_score": score,
                "downtime_hours": impact.downtime_hours,
                "scrap_units": impact.scrap_units,
                "cost_impact": impact.cost_impact,
                "safety_improvement": impact.safety_improvement,
            })

        # Sort by impact score (descending)
        return sorted(results, key=lambda x: x["impact_score"], reverse=True)

    def estimate_downtime_avoided(
        self,
        without_action: Dict[str, Any],
        with_action: Dict[str, Any],
    ) -> float:
        """
        Calculate downtime avoided by taking an action.

        Args:
            without_action: Impact if action NOT taken
            with_action: Impact if action IS taken

        Returns:
            Hours of downtime avoided (positive = beneficial)
        """
        return without_action.get("downtime_hours", 0) - with_action.get("downtime_hours", 0)

    def estimate_scrap_prevented(
        self,
        without_action: Dict[str, Any],
        with_action: Dict[str, Any],
    ) -> int:
        """
        Calculate scrap prevented by taking an action.

        Args:
            without_action: Scrap if action NOT taken
            with_action: Scrap if action IS taken

        Returns:
            Units of scrap prevented (positive = beneficial)
        """
        return without_action.get("scrap_units", 0) - with_action.get("scrap_units", 0)

    def get_impact_summary(self, impact: ImpactEstimate) -> str:
        """Get human-readable summary of impact."""
        parts = []

        if impact.downtime_hours > 0:
            parts.append(f"Downtime: {impact.downtime_hours:.1f}h")
        elif impact.delay_hours:
            parts.append(f"Delay: {impact.delay_hours:.1f}h")

        if impact.scrap_units > 0:
            parts.append(f"Scrap: {impact.scrap_units} units")
        elif impact.scrap_units < 0:
            parts.append(f"Scrap prevented: {abs(impact.scrap_units)} units")

        if impact.cost_impact < 0:
            parts.append(f"Savings: ${abs(impact.cost_impact):.0f}")
        elif impact.cost_impact > 0:
            parts.append(f"Cost: ${impact.cost_impact:.0f}")

        if impact.safety_improvement:
            parts.append(f"Safety: {impact.safety_improvement}")

        if impact.oee_impact > 0:
            parts.append(f"OEE +{impact.oee_impact:.1f}%")
        elif impact.oee_impact < 0:
            parts.append(f"OEE {impact.oee_impact:.1f}%")

        return " | ".join(parts) if parts else "Neutral impact"
