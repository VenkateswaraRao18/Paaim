"""
Red-Team Agent — challenges risky recommendations using Gemini with rule-based fallback.
"""

from typing import Dict, List, Any, Optional
from datetime import datetime
import json
import logging

from paaim.models import RiskLevel

logger = logging.getLogger(__name__)


class RedTeamReview:
    def __init__(
        self,
        action_name: str,
        risk_factors: List[str],
        suggested_alternatives: Optional[List[str]] = None,
        assumptions_challenged: Optional[List[str]] = None,
        confidence_adjustment: float = 0.0,
        overall_risk_assessment: str = "acceptable",
    ):
        self.action_name = action_name
        self.risk_factors = risk_factors
        self.suggested_alternatives = suggested_alternatives or []
        self.assumptions_challenged = assumptions_challenged or []
        self.confidence_adjustment = confidence_adjustment
        self.overall_risk_assessment = overall_risk_assessment
        self.timestamp = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
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
    Challenges agent recommendations by asking Gemini to play a skeptical safety engineer.
    Falls back to curated rule-based challenges when Gemini is unavailable.
    """

    def __init__(self):
        self._challenge_rules = self._load_challenge_rules()
        self._gemini_client = None
        self._gemini_available = None  # None = not yet checked

    def _get_gemini(self):
        if self._gemini_available is not None:
            return self._gemini_client, self._gemini_available
        try:
            import google.generativeai as genai
            import os
            api_key = os.getenv("GEMINI_API_KEY", "")
            if api_key:
                model_name = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
                self._gemini_client = genai.GenerativeModel(model_name)
                self._gemini_available = True
            else:
                self._gemini_available = False
        except ImportError:
            self._gemini_available = False
        return self._gemini_client, self._gemini_available

    def _load_challenge_rules(self) -> Dict[str, Dict[str, Any]]:
        return {
            "stop_line": {
                "risk_factors": [
                    "Sudden line stop may cause in-process material waste",
                    "Restarting is harder and riskier than staying running",
                    "Zone intrusion sensor may be giving a false positive",
                ],
                "assumptions_to_check": [
                    "Zone intrusion sensor is calibrated",
                    "Worker is actually in the zone (not a sensor fault)",
                    "Safety override is not legitimately active",
                ],
                "suggested_alternatives": [
                    "Verify sensor confidence > 0.95 before issuing stop",
                    "Alert operator to zone hazard first",
                ],
            },
            "contain_batch": {
                "risk_factors": [
                    "Containment delays production and has a cost",
                    "Defect detection may be a false positive",
                    "Root cause is unknown — batch may be conforming",
                ],
                "assumptions_to_check": [
                    "Defect detection confidence > 0.85",
                    "Batch is traceable and physically containable",
                    "Quality thresholds are correctly calibrated",
                ],
                "suggested_alternatives": [
                    "Sample inspection before committing to full containment",
                    "Inspect root cause while line continues on good parts",
                ],
            },
            "schedule_maintenance": {
                "risk_factors": [
                    "Planned maintenance window costs production time",
                    "Vibration anomaly may be transient (loose fixture, not bearing)",
                    "Bearing may have more life than the model predicts",
                ],
                "assumptions_to_check": [
                    "Vibration sensor is functioning correctly",
                    "Degradation model is calibrated for this machine",
                    "A maintenance window is actually available",
                ],
                "suggested_alternatives": [
                    "Monitor vibration trend for 24h before scheduling",
                    "Increase inspection frequency as an intermediate step",
                ],
            },
            "propose_recovery_plan": {
                "risk_factors": [
                    "Recovery plans often require overtime, raising cost",
                    "Quality may suffer under rushed production conditions",
                    "Customer deadline may actually be negotiable",
                ],
                "assumptions_to_check": [
                    "Order deadline is truly fixed",
                    "Recovery resources are confirmed available",
                    "Quality standards can be maintained under acceleration",
                ],
                "suggested_alternatives": [
                    "Negotiate a 24h deadline extension with the customer",
                    "Accept partial order completion and communicate proactively",
                ],
            },
            "shift_non_critical_load": {
                "risk_factors": [
                    "Load classified as non-critical may have hidden dependencies",
                    "Off-peak window may already be at capacity",
                    "Delay may violate a downstream customer commitment",
                ],
                "assumptions_to_check": [
                    "Off-peak window capacity is confirmed",
                    "Loads are correctly classified as non-critical",
                    "No customer commitments are violated by the delay",
                ],
                "suggested_alternatives": [
                    "Negotiate staggered load shifting with the grid operator",
                    "Accept peak pricing and preserve production schedule",
                ],
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
        """Challenge a recommendation — tries Gemini first, falls back to rules."""
        client, available = self._get_gemini()
        if available and client:
            try:
                return self._challenge_with_gemini(
                    client, action_name, confidence, evidence_signals, event_context, risk_level
                )
            except Exception as e:
                logger.warning(f"Gemini red-team call failed: {e} — using rule fallback")

        return self._challenge_with_rules(action_name, confidence, evidence_signals, event_context, risk_level)

    def _build_prompt(
        self,
        action_name: str,
        confidence: float,
        evidence_signals: List[str],
        event_context: Dict[str, Any],
        risk_level: RiskLevel,
    ) -> str:
        return f"""You are a safety-first red-team engineer at a manufacturing plant.
Your job is to challenge AI-generated action recommendations before they are executed.

ACTION TO CHALLENGE:
- Action: {action_name}
- Agent confidence: {confidence:.0%}
- Risk level: {risk_level.value}
- Evidence signals: {json.dumps(evidence_signals)}
- Event context: {json.dumps(event_context, default=str)}

Provide a skeptical but fair assessment. Respond with ONLY valid JSON:
{{
  "risk_factors": ["<specific concern 1>", "<specific concern 2>"],
  "assumptions_challenged": ["<assumption that may be wrong>"],
  "suggested_alternatives": ["<safer alternative>"],
  "confidence_adjustment": <float between -0.3 and 0.05>,
  "overall_risk_assessment": "<acceptable|marginal|elevated|critical>"
}}

Focus on: sensor reliability, false positives, resource constraints, hidden side effects.
Respond with ONLY the JSON."""

    def _challenge_with_gemini(
        self,
        client,
        action_name: str,
        confidence: float,
        evidence_signals: List[str],
        event_context: Dict[str, Any],
        risk_level: RiskLevel,
    ) -> RedTeamReview:
        prompt = self._build_prompt(action_name, confidence, evidence_signals, event_context, risk_level)
        response = client.generate_content(prompt)
        text = response.text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        data = json.loads(text)
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
        risk_level: RiskLevel,
    ) -> RedTeamReview:
        rules = self._challenge_rules.get(action_name, {})
        risk_factors = list(rules.get("risk_factors", []))

        if confidence > 0.95 and risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL):
            risk_factors.append(
                f"Confidence {confidence:.0%} seems high for a {risk_level.value}-risk action — verify sensor data"
            )

        assumptions_challenged = []
        for assumption in rules.get("assumptions_to_check", []):
            if "available" in assumption.lower() and "available" not in str(event_context).lower():
                assumptions_challenged.append(f"Cannot verify: {assumption}")

        confidence_adjustment = -0.1 if len(assumptions_challenged) > 2 else 0.0

        if len(assumptions_challenged) > 3 or len(risk_factors) > 3:
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

    def should_escalate(self, review: RedTeamReview) -> bool:
        return (
            len(review.assumptions_challenged) > 3
            or len(review.risk_factors) > 4
            or review.overall_risk_assessment not in ("acceptable", "marginal")
        )

    def get_red_team_summary(self, review: RedTeamReview) -> str:
        parts = []
        if review.risk_factors:
            parts.append(f"Risks: {'; '.join(review.risk_factors[:2])}")
        if review.assumptions_challenged:
            parts.append(f"Assumptions questioned: {len(review.assumptions_challenged)}")
        if review.suggested_alternatives:
            parts.append(f"Consider: {review.suggested_alternatives[0]}")
        if review.confidence_adjustment < -0.05:
            parts.append(f"Confidence: -{abs(review.confidence_adjustment):.0%}")
        if review.overall_risk_assessment != "acceptable":
            parts.append(f"Risk level: {review.overall_risk_assessment}")
        return " | ".join(parts) if parts else "Red-team: No concerns"
