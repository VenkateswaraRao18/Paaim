from typing import Dict, List, Any, Optional
from enum import Enum
from datetime import datetime


class ApprovalStatus(str, Enum):
    """Approval workflow status."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    ESCALATED = "escalated"


class ApprovalDecision:
    """Result of approval decision."""

    def __init__(
        self,
        decision_id: str,
        approver_role: str,
        status: ApprovalStatus,
        approved_by: Optional[str] = None,
        notes: Optional[str] = None,
        escalation_reason: Optional[str] = None,
    ):
        self.decision_id = decision_id
        self.approver_role = approver_role
        self.status = status
        self.approved_by = approved_by
        self.approved_at = datetime.utcnow() if status == ApprovalStatus.APPROVED else None
        self.notes = notes
        self.escalation_reason = escalation_reason

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "decision_id": self.decision_id,
            "approver_role": self.approver_role,
            "status": self.status.value,
            "approved_by": self.approved_by,
            "approved_at": self.approved_at.isoformat() if self.approved_at else None,
            "notes": self.notes,
            "escalation_reason": self.escalation_reason,
        }


class ApprovalGate:
    """
    Human approval gate: routes decisions to appropriate approvers.

    Determines who needs to approve based on:
    - Action risk level
    - Policy approval requirements
    - Escalation rules
    """

    def __init__(self):
        """Initialize approval gate with role hierarchies."""
        self.approval_hierarchy = {
            "auto": 0,  # Automatic, no human needed
            "operator": 1,  # Line operator
            "supervisor": 2,  # Shift supervisor
            "manager": 3,  # Plant manager
            "safety_officer": 4,  # Safety officer (can override)
        }

        self.role_descriptions = {
            "operator": "Line Operator",
            "supervisor": "Shift Supervisor",
            "manager": "Plant Manager",
            "safety_officer": "Safety Officer",
        }

    def route_decision(
        self,
        decision_id: str,
        approval_level: str,
        action_name: str,
        risk_level: str,
        policy_reason: str,
    ) -> Dict[str, Any]:
        """
        Determine approval routing for a decision.

        Args:
            decision_id: Unique decision identifier
            approval_level: Required approval level from policy
            action_name: Action being approved
            risk_level: Risk level of the action
            policy_reason: Reason from policy engine

        Returns:
            Approval routing information
        """
        # Map policy approval level to approver role
        approver_roles = self._map_approval_level(approval_level, risk_level)

        if not approver_roles:
            return {
                "decision_id": decision_id,
                "status": "auto_approved",
                "approver_roles": [],
                "requires_human_approval": False,
                "reason": "Automatic approval by policy (safety-critical)",
            }

        return {
            "decision_id": decision_id,
            "action": action_name,
            "risk_level": risk_level,
            "status": "pending_approval",
            "approver_roles": approver_roles,
            "requires_human_approval": True,
            "approval_deadline_seconds": self._get_deadline(risk_level),
            "reason": policy_reason,
        }

    def _map_approval_level(self, approval_level: str, risk_level: str) -> List[str]:
        """Map policy approval level to human approver roles."""
        mapping = {
            "auto": [],  # No human approval
            "operator": ["operator"],
            "supervisor": ["supervisor"],
            "manager": ["manager"],
            "safety_officer": ["safety_officer"],
        }

        roles = mapping.get(approval_level, ["supervisor"])

        # Escalate based on risk level
        if risk_level == "critical" or risk_level == "CRITICAL":
            if "safety_officer" not in roles:
                roles.append("safety_officer")
            if "manager" not in roles:
                roles.append("manager")

        return roles

    def _get_deadline(self, risk_level: str) -> int:
        """Get approval deadline in seconds based on risk level."""
        deadlines = {
            "critical": 60,  # 1 minute for critical actions
            "high": 300,  # 5 minutes
            "medium": 900,  # 15 minutes
            "low": 3600,  # 1 hour
        }
        return deadlines.get(risk_level.lower(), 900)

    def simulate_approval(
        self,
        decision_id: str,
        approver_role: str,
        approved: bool,
        notes: Optional[str] = None,
    ) -> ApprovalDecision:
        """
        Simulate human approval (for testing/demo).

        Args:
            decision_id: Decision being approved
            approver_role: Role making the approval
            approved: True if approved, False if rejected
            notes: Approval notes

        Returns:
            ApprovalDecision with result
        """
        status = ApprovalStatus.APPROVED if approved else ApprovalStatus.REJECTED

        return ApprovalDecision(
            decision_id=decision_id,
            approver_role=approver_role,
            status=status,
            approved_by=f"{approver_role}_demo_user",
            notes=notes or ("Approved by " + self.role_descriptions.get(approver_role, approver_role)),
        )

    def escalate_decision(
        self,
        decision_id: str,
        current_role: str,
        reason: str,
        escalate_to: Optional[str] = None,
    ) -> ApprovalDecision:
        """
        Escalate decision to higher authority.

        Args:
            decision_id: Decision being escalated
            current_role: Current approval role
            reason: Reason for escalation
            escalate_to: Specific role to escalate to (optional)

        Returns:
            ApprovalDecision with escalation
        """
        if escalate_to is None:
            # Auto-escalate to next level
            escalate_to = self._get_next_role(current_role)

        return ApprovalDecision(
            decision_id=decision_id,
            approver_role=escalate_to,
            status=ApprovalStatus.ESCALATED,
            escalation_reason=f"Escalated from {current_role}: {reason}",
        )

    def _get_next_role(self, current_role: str) -> str:
        """Get the next approval role in hierarchy."""
        hierarchy_list = sorted(
            self.approval_hierarchy.items(),
            key=lambda x: x[1],
        )

        current_level = self.approval_hierarchy.get(current_role, 0)

        for role, level in hierarchy_list:
            if level > current_level:
                return role

        return "manager"  # Default escalation

    def get_approval_summary(self, routing: Dict[str, Any]) -> str:
        """Get human-readable approval routing summary."""
        if not routing.get("requires_human_approval"):
            return "Auto-approved by policy"

        roles = routing.get("approver_roles", [])
        role_names = [self.role_descriptions.get(r, r) for r in roles]
        deadline = routing.get("approval_deadline_seconds", 0)

        deadline_str = f"{deadline // 60}m" if deadline < 3600 else f"{deadline // 3600}h"

        return f"Requires approval from: {', '.join(role_names)} (deadline: {deadline_str})"
