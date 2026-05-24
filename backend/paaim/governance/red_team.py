from typing import Dict, List, Any, Optional
from abc import ABC
from datetime import datetime
import os
import json

from paaim.models import ActionRecommendation, RiskLevel

try:
    from anthropic import Anthropic
    CLAUDE_AVAILABLE = True
except ImportError:
    CLAUDE_AVAILABLE = False


class RedTeamReview:
    """Result of red-team challenge review."""

    def __init__(
        self,
        action_name: str,
        risk_factors: List[str],
        suggested_alternatives: List[str] = None,
        assumptions_challenged: List[str] = None,
        confidence_adjustment: float = 0.0,
        overall_risk_assessment: str = "acceptable",
    ):
        self.action_name = action_name
        self.risk_factors = risk_factors
        self.suggested_alternatives = suggested_alternatives or []
        self.assumptions_challenged = assumptions_challenged or []
        self.confidence_adjustment = confidence_adjustment  # Applied to original confidence
        self.overall_risk_assessment = overall_risk_assessment
        self.timestamp = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "action_name": self.action_name,
            "risk_factors": self.risk_factors,
            "suggested_alternatives": self.suggested_alternatives,
            "assumptions_challenged": self.assumptions_challenged,
            "confidence_adjustment": self.confidence_adjustment,
            "overall_risk_assessment": self.overall_risk_assessment,
            "timestamp": self.timestamp.isoformat(),
        }


class RedTeamAgent:
    """
    Red-Team Agent: challenges recommendations for safety and assumptions.

    Phase 2: Uses Claude API for intelligent risk assessment.
    Falls back to hardcoded rules if Claude API unavailable.
    """

    def __init__(self, use_claude: bool = True):
        """Initialize red-team agent with optional Claude API support."""
        self.challenge_rules = self._load_challenge_rules()
        self.use_claude = use_claude and CLAUDE_AVAILABLE

        if self.use_claude:
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if api_key:
                self.client = Anthropic(api_key=api_key)
            else:
                self.use_claude = False

    def _load_challenge_rules(self) -> Dict[str, Dict[str, Any]]:
        """Load hardcoded challenge rules."""
        return {
            "stop_line": {
                "risk_factors": [
                    "Sudden line stop may cause material waste",
                    "Down equipment harder to restart than stay running",
                    "Verify zone intrusion is not false positive",
                ],
                "assumptions_to_check": [
                    "Zone intrusion sensor calibrated correctly",
                    "Worker actually in zone (not sensor error)",
                    "Safety override not legitimately active",
                ],
                "suggested_alternatives": [
                    "Verify sensor confidence > 0.95 before stop",
                    "Alert operator to zone hazard first",
                ],
                "risk_level": RiskLevel.CRITICAL,
            },
            "contain_batch": {
                "risk_factors": [
                    "Containment costs money and delays production",
                    "Defect detection may be false positive",
                    "Root cause unknown - batch might be fine",
                ],
                "assumptions_to_check": [
                    "Defect detection confidence > 0.85",
                    "Batch is traceable and containerizable",
                    "Quality thresholds are calibrated",
                ],
                "suggested_alternatives": [
                    "Sample inspection before full containment",
                    "Inspect root cause while line continues",
                ],
                "risk_level": RiskLevel.HIGH,
            },
            "schedule_maintenance": {
                "risk_factors": [
                    "Maintenance window costs production time",
                    "Vibration anomaly might be transient",
                    "Bearing may run longer than predicted",
                ],
                "assumptions_to_check": [
                    "Vibration sensor working correctly",
                    "Bearing degradation model is accurate",
                    "Maintenance window available",
                    "Failure will actually occur without maintenance",
                ],
                "suggested_alternatives": [
                    "Monitor vibration for next 24h before scheduling",
                    "Increase inspection frequency instead",
                ],
                "risk_level": RiskLevel.MEDIUM,
            },
            "propose_recovery_plan": {
                "risk_factors": [
                    "Recovery plans often require overtime",
                    "Quality may suffer under rushed conditions",
                    "Order deadline may be fixed by customer",
                ],
                "assumptions_to_check": [
                    "Order deadline is truly fixed",
                    "Recovery resources are available",
                    "Quality standards relaxed or maintained",
                ],
                "suggested_alternatives": [
                    "Negotiate deadline extension with customer",
                    "Accept partial order completion",
                ],
                "risk_level": RiskLevel.MEDIUM,
            },
            "shift_non_critical_load": {
                "risk_factors": [
                    "Load shift may violate commitments",
                    "Off-peak window may fill up",
                    "Load may not actually be 'non-critical'",
                ],
                "assumptions_to_check": [
                    "Off-peak window really available",
                    "Shifted loads classified correctly",
                    "No customer commitments violated",
                ],
                "suggested_alternatives": [
                    "Negotiate staggered load shifting",
                    "Accept peak pricing instead",
                ],
                "risk_level": RiskLevel.LOW,
            },
        }

    def challenge(
        self,
        action_name: str,
        confidence: float,
        evidence_signals: List[str],
        event_context: Dict[str, Any],
        risk_level: RiskLevel = RiskLevel.MEDIUM,
    ) -> RedTeamReview:
        """
        Challenge a recommended action.

        Uses Claude API if available for intelligent risk assessment,
        falls back to hardcoded rules.

        Args:
            action_name: Name of action being challenged
            confidence: Agent confidence in recommendation (0.0-1.0)
            evidence_signals: Signals supporting this recommendation
            event_context: Context from the triggering event
            risk_level: Risk level of this action

        Returns:
            RedTeamReview with challenges and assessment
        """
        if self.use_claude:
            try:
                return self._challenge_with_claude(
                    action_name, confidence, evidence_signals, event_context, risk_level
                )
            except Exception as e:
                # Fall back to hardcoded rules if Claude call fails
                print(f"Claude API failed: {e}, falling back to hardcoded rules")
                return self._challenge_with_rules(
                    action_name, confidence, evidence_signals, event_context, risk_level
                )
        else:
            return self._challenge_with_rules(
                action_name, confidence, evidence_signals, event_context, risk_level
            )

    def _challenge_with_claude(
        self,
        action_name: str,
        confidence: float,
        evidence_signals: List[str],
        event_context: Dict[str, Any],
        risk_level: RiskLevel,
    ) -> RedTeamReview:
        """Challenge using Claude API for intelligent risk assessment."""
        prompt = self._build_challenge_prompt(
            action_name, confidence, evidence_signals, event_context, risk_level
        )

        message = self.client.messages.create(
            model="claude-opus-4-7",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}],
        )

        response_text = message.content[0].text
        return self._parse_claude_response(
            action_name, confidence, response_text, risk_level
        )

    def _build_challenge_prompt(
        self,
        action_name: str,
        confidence: float,
        evidence_signals: List[str],
        event_context: Dict[str, Any],
        risk_level: RiskLevel,
    ) -> str:
        """Build prompt for Claude to challenge an action."""
        return f"""You are a safety-first red-team engineer challenging a manufacturing decision.

ACTION BEING CHALLENGED:
- Action: {action_name}
- Agent Confidence: {confidence:.0%}
- Risk Level: {risk_level.value}

SUPPORTING EVIDENCE:
{json.dumps(evidence_signals, indent=2)}

EVENT CONTEXT:
{json.dumps(event_context, indent=2)}

Your task: Provide a concise red-team assessment in JSON format with:
1. "risk_factors": List of 2-3 specific concerns about this action
2. "assumptions_challenged": List of assumptions that might be wrong
3. "suggested_alternatives": List of 1-2 safer alternatives
4. "confidence_adjustment": Number between -0.3 and 0.1 (confidence adjustment)
5. "overall_risk_assessment": One of ["acceptable", "marginal", "elevated", "critical"]

Focus on:
- Hidden dependencies or side effects
- Sensor reliability and false positives
- Resource constraints
- Safety first principle

Respond with ONLY valid JSON, no other text."""

    def _parse_claude_response(
        self, action_name: str, confidence: float, response_text: str, risk_level: RiskLevel
    ) -> RedTeamReview:
        """Parse Claude's JSON response into RedTeamReview."""
        try:
            data = json.loads(response_text)
        except json.JSONDecodeError:
            # If parsing fails, fall back to hardcoded rules
            return self._challenge_with_rules(
                action_name, confidence, [], {}, risk_level
            )

        return RedTeamReview(
            action_name=action_name,
            risk_factors=data.get("risk_factors", []),
            suggested_alternatives=data.get("suggested_alternatives", []),
            assumptions_challenged=data.get("assumptions_challenged", []),
            confidence_adjustment=float(data.get("confidence_adjustment", 0.0)),
            overall_risk_assessment=data.get("overall_risk_assessment", "acceptable"),
        )

    def _challenge_with_rules(
        self,
        action_name: str,
        confidence: float,
        evidence_signals: List[str],
        event_context: Dict[str, Any],
        risk_level: RiskLevel = RiskLevel.MEDIUM,
    ) -> RedTeamReview:
        """Challenge using hardcoded rules (fallback)."""
        # Get challenge rules for this action
        rules = self.challenge_rules.get(action_name, {})

        # Build risk factors list
        risk_factors = rules.get("risk_factors", [])

        # Check if confidence is suspiciously high for this risk level
        if confidence > 0.95 and risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
            risk_factors.append(
                f"Confidence too high ({confidence:.0%}) for {risk_level.value} risk action"
            )

        # Check assumptions
        assumptions_challenged = []
        assumptions_to_check = rules.get("assumptions_to_check", [])
        for assumption in assumptions_to_check:
            # Check if signals support this assumption
            if not self._check_assumption(assumption, evidence_signals, event_context):
                assumptions_challenged.append(f"Cannot verify: {assumption}")

        # Count risk factors for assessment
        risk_factors_count = len(risk_factors)

        # Determine confidence adjustment
        confidence_adjustment = 0.0
        if len(assumptions_challenged) > 2:
            confidence_adjustment = -0.1  # Reduce confidence if multiple assumptions questioned

        # Determine overall risk assessment
        if len(assumptions_challenged) > 3 or risk_factors_count > 3:
            overall_risk = "elevated"
        elif confidence < 0.7:
            overall_risk = "marginal"
        else:
            overall_risk = "acceptable"

        return RedTeamReview(
            action_name=action_name,
            risk_factors=risk_factors,
            suggested_alternatives=rules.get("suggested_alternatives", []),
            assumptions_challenged=assumptions_challenged,
            confidence_adjustment=confidence_adjustment,
            overall_risk_assessment=overall_risk,
        )

    def _check_assumption(
        self, assumption: str, signals: List[str], context: Dict[str, Any]
    ) -> bool:
        """
        Check if an assumption is supported by available signals/context.

        Returns:
            True if assumption appears valid, False otherwise
        """
        assumption_lower = assumption.lower()

        # Example checks - simplified for MVP
        if "sensor" in assumption_lower and "calibr" in assumption_lower:
            # Would need sensor metadata in context - assume OK for MVP
            return True

        if "confidence" in assumption_lower:
            # Would check confidence scores in context
            return True

        if "available" in assumption_lower:
            # Check if context includes availability info
            return "available" in str(context).lower()

        # Default: assume OK if we can't determine
        return True

    def get_safer_alternatives(self, action_name: str) -> List[str]:
        """Get suggested safer alternatives for an action."""
        rules = self.challenge_rules.get(action_name, {})
        return rules.get("suggested_alternatives", [])

    def should_escalate(self, review: RedTeamReview) -> bool:
        """Determine if red-team review warrants escalation."""
        # Escalate if:
        # 1. Too many assumptions challenged
        if len(review.assumptions_challenged) > 3:
            return True

        # 2. High risk with concerns
        if len(review.risk_factors) > 4:
            return True

        # 3. Overall risk assessment is not acceptable
        if review.overall_risk_assessment != "acceptable":
            return True

        return False

    def get_red_team_summary(self, review: RedTeamReview) -> str:
        """Get human-readable summary of red-team review."""
        parts = []

        # Risk factors
        if review.risk_factors:
            factors_str = "; ".join(review.risk_factors[:2])  # Top 2 factors
            parts.append(f"Risks: {factors_str}")

        # Challenged assumptions
        if review.assumptions_challenged:
            parts.append(f"Assumptions questioned: {len(review.assumptions_challenged)}")

        # Suggested alternatives
        if review.suggested_alternatives:
            alt = review.suggested_alternatives[0]
            parts.append(f"Consider: {alt}")

        # Confidence adjustment
        if review.confidence_adjustment < -0.05:
            parts.append(f"Confidence: -{abs(review.confidence_adjustment):.0%}")

        # Risk assessment
        if review.overall_risk_assessment != "acceptable":
            parts.append(f"Risk level: {review.overall_risk_assessment}")

        return " | ".join(parts) if parts else "Red-team: No concerns"
