import yaml
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum
from pathlib import Path

from paaim.models import ActionRecommendation, ApprovalLevel, RiskLevel


class PolicyDecision(Enum):
    """Policy evaluation result."""
    ALLOWED = "allowed"
    REQUIRES_APPROVAL = "requires_approval"
    PROHIBITED = "prohibited"
    ESCALATED = "escalated"


class PolicyEvaluation:
    """Result of policy evaluation on an action."""

    def __init__(
        self,
        decision: PolicyDecision,
        approval_level: ApprovalLevel,
        reason: str,
        constraints_violated: List[str] = None,
        conflicting_actions: List[str] = None,
    ):
        self.decision = decision
        self.approval_level = approval_level
        self.reason = reason
        self.constraints_violated = constraints_violated or []
        self.conflicting_actions = conflicting_actions or []

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "decision": self.decision.value,
            "approval_level": self.approval_level.value,
            "reason": self.reason,
            "constraints_violated": self.constraints_violated,
            "conflicting_actions": self.conflicting_actions,
        }


class PolicyEngine:
    """
    Core policy evaluation engine.

    Evaluates whether actions are allowed based on the Industrial Constitution.
    Handles approval routing, conflict resolution, and safety-critical rules.
    """

    def __init__(self, policy_file_path: Optional[str] = None):
        """
        Initialize policy engine with Industrial Constitution.

        Args:
            policy_file_path: Path to industrial_constitution.yaml
                             If None, uses default path
        """
        if policy_file_path is None:
            # Use default path relative to this module
            default_path = Path(__file__).parent / "industrial_constitution.yaml"
            policy_file_path = str(default_path)

        self.policy_file_path = policy_file_path
        self.constitution = self._load_constitution()
        self.actions_db = self.constitution.get("actions", {})
        self.approval_levels = self.constitution.get("approval_levels", {})
        self.safety_rules = self.constitution.get("safety_critical_rules", [])
        self.constraints = self.constitution.get("constraints", {})

    def _load_constitution(self) -> Dict[str, Any]:
        """Load Industrial Constitution from YAML file."""
        try:
            with open(self.policy_file_path, "r") as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            raise RuntimeError(f"Policy file not found: {self.policy_file_path}")
        except yaml.YAMLError as e:
            raise RuntimeError(f"Error parsing policy file: {e}")

    def evaluate_action(
        self,
        action_name: str,
        event_type: str,
        confidence: float,
        existing_actions: Optional[List[str]] = None,
    ) -> PolicyEvaluation:
        """
        Evaluate if an action is allowed based on policy.

        Args:
            action_name: Name of the action (e.g., "stop_line")
            event_type: Type of event that triggered this (e.g., "safety")
            confidence: Confidence score of the recommendation (0.0-1.0)
            existing_actions: List of already-approved actions (for conflict checking)

        Returns:
            PolicyEvaluation with decision and reasoning
        """
        existing_actions = existing_actions or []

        # 1. Check if action exists in policy
        if action_name not in self.actions_db:
            return PolicyEvaluation(
                decision=PolicyDecision.PROHIBITED,
                approval_level=ApprovalLevel.SAFETY_OFFICER,
                reason=f"Action '{action_name}' not defined in Industrial Constitution",
            )

        action_policy = self.actions_db[action_name]

        # 2. Check if action is explicitly forbidden
        if not action_policy.get("allowed", False):
            return PolicyEvaluation(
                decision=PolicyDecision.PROHIBITED,
                approval_level=ApprovalLevel.SAFETY_OFFICER,
                reason=f"Action '{action_name}' is prohibited by policy",
            )

        # 3. Check for conflicting actions (mutex constraints)
        conflicting = action_policy.get("forbidden_with", [])
        active_conflicts = [a for a in conflicting if a in existing_actions]
        if active_conflicts:
            return PolicyEvaluation(
                decision=PolicyDecision.PROHIBITED,
                approval_level=ApprovalLevel.MANAGER,
                reason=f"Action '{action_name}' conflicts with already-approved actions: {active_conflicts}",
                conflicting_actions=active_conflicts,
            )

        # 4. Check safety-critical rules
        safety_violation = self._check_safety_rules(action_name, event_type)
        if safety_violation:
            return PolicyEvaluation(
                decision=PolicyDecision.PROHIBITED,
                approval_level=ApprovalLevel.SAFETY_OFFICER,
                reason=safety_violation,
            )

        # 5. Determine approval level
        approval_required = action_policy.get("approval_required", "operator")
        try:
            approval_level = ApprovalLevel(approval_required)
        except ValueError:
            approval_level = ApprovalLevel.SUPERVISOR

        # 6. Check if auto-approval is possible
        if approval_level == ApprovalLevel.AUTO:
            return PolicyEvaluation(
                decision=PolicyDecision.ALLOWED,
                approval_level=ApprovalLevel.AUTO,
                reason=f"Action '{action_name}' is auto-approved by policy (safety-critical)",
            )

        # 7. Return requires_approval decision
        return PolicyEvaluation(
            decision=PolicyDecision.REQUIRES_APPROVAL,
            approval_level=approval_level,
            reason=f"Action '{action_name}' requires {approval_level.value} approval",
        )

    def get_approval_threshold(self, action_name: str) -> ApprovalLevel:
        """Get the approval level required for an action."""
        if action_name not in self.actions_db:
            return ApprovalLevel.MANAGER  # Default to highest for unknown actions

        approval_required = self.actions_db[action_name].get("approval_required", "operator")
        try:
            return ApprovalLevel(approval_required)
        except ValueError:
            return ApprovalLevel.SUPERVISOR

    def check_priority_conflict(
        self, actions: List[Tuple[str, float]]
    ) -> Tuple[str, str]:
        """
        Resolve priority conflict between multiple actions.

        Args:
            actions: List of (action_name, priority_score) tuples

        Returns:
            (winning_action, reason)
        """
        if not actions:
            return None, "No actions to evaluate"

        if len(actions) == 1:
            return actions[0][0], "Single action, no conflict"

        # Get priority levels from policy
        priorities = {}
        for action_name, _ in actions:
            if action_name in self.actions_db:
                action_priority = self.actions_db[action_name].get("priority", 50)
                priorities[action_name] = action_priority
            else:
                priorities[action_name] = 0

        # Find action with highest priority
        winning_action = max(actions, key=lambda x: priorities.get(x[0], 0))[0]
        winning_priority = priorities[winning_action]

        reason = f"Action '{winning_action}' prioritized (priority={winning_priority})"

        return winning_action, reason

    def get_policy_impact(self, action_name: str) -> Dict[str, Any]:
        """Get estimated impact from policy."""
        if action_name not in self.actions_db:
            return {}

        return self.actions_db[action_name].get("estimated_impact", {})

    def get_notifications_for_action(self, action_name: str) -> Dict[str, Any]:
        """Get notification requirements for an action."""
        notifications = self.constitution.get("notifications", {})
        return notifications.get(action_name, {})

    def _check_safety_rules(self, action_name: str, event_type: str) -> Optional[str]:
        """
        Check if action violates any safety-critical rules.

        Returns:
            Error message if violated, None otherwise
        """
        for rule in self.safety_rules:
            rule_id = rule.get("rule_id")
            enforcement = rule.get("enforcement", "WARN")

            # Rule: no_safety_bypass
            if rule_id == "no_safety_bypass":
                # Check if action tries to disable safety systems
                if "disable" in action_name.lower() and "safety" in action_name.lower():
                    if enforcement == "STRICT":
                        return "Cannot bypass certified safety systems (policy violation)"

            # Rule: zone_intrusion_immediate
            if rule_id == "zone_intrusion_immediate":
                if event_type == "safety" and "zone_intrusion" in event_type:
                    if action_name != "stop_line":
                        if enforcement == "STRICT":
                            return "Zone intrusion must trigger stop_line action"

            # Rule: human_override_capable
            if rule_id == "human_override_capable":
                # All actions should be overridable - just warn if not
                if enforcement == "STRICT":
                    pass  # All actions are tracked in audit, so they're overridable

        return None

    def validate_evidence_requirements(
        self, action_name: str, provided_signals: List[str], confidence: float
    ) -> Tuple[bool, str]:
        """
        Validate that an action has sufficient evidence.

        Args:
            action_name: Action name
            provided_signals: List of signal names available
            confidence: Confidence score of the recommendation

        Returns:
            (is_valid, message)
        """
        evidence_reqs = self.constitution.get("evidence_requirements", {})

        if action_name not in evidence_reqs:
            return True, "No specific evidence requirements"

        req = evidence_reqs[action_name]
        required_signals = req.get("required_signals", [])
        min_confidence = req.get("minimum_confidence", 0.0)
        min_signal_count = req.get("minimum_signal_count", 1)

        # Check confidence
        if confidence < min_confidence:
            return False, f"Confidence {confidence} below minimum {min_confidence}"

        # Check signal count
        available_signals = [s for s in provided_signals if s in required_signals]
        if len(available_signals) < min_signal_count:
            return (
                False,
                f"Only {len(available_signals)} of {min_signal_count} required signals available",
            )

        return True, "Evidence requirements met"

    def get_operating_mode_constraints(self, operating_mode: str) -> Dict[str, Any]:
        """Get action constraints based on factory operating mode."""
        modes = self.constitution.get("operating_modes", {})
        return modes.get(operating_mode, {})

    def get_audit_requirements(self, action_name: str) -> Dict[str, Any]:
        """Get audit logging requirements for an action."""
        reqs = self.constitution.get("audit_requirements", {})
        return reqs.get(action_name, reqs.get("default", {}))
