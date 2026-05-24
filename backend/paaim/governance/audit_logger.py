from typing import Dict, List, Any, Optional
from datetime import datetime
from enum import Enum
import json

from paaim.models import AuditLogModel


class AuditEventType(str, Enum):
    """Types of audit events."""
    EVENT_DETECTED = "event_detected"
    AGENT_ANALYZED = "agent_analyzed"
    POLICY_EVALUATED = "policy_evaluated"
    IMPACT_SIMULATED = "impact_simulated"
    RED_TEAM_CHALLENGED = "red_team_challenged"
    APPROVAL_ROUTED = "approval_routed"
    DECISION_APPROVED = "decision_approved"
    DECISION_REJECTED = "decision_rejected"
    ACTION_EXECUTED = "action_executed"
    OUTCOME_RECORDED = "outcome_recorded"


class EvidencePack:
    """
    Complete evidence trail for a decision.

    Captures all information needed to understand, audit, and replay a decision.
    """

    def __init__(self, decision_id: str, event_id: str, factory_id: str):
        self.decision_id = decision_id
        self.event_id = event_id
        self.factory_id = factory_id
        self.created_at = datetime.utcnow()
        self.events: List[Dict[str, Any]] = []
        self.metadata: Dict[str, Any] = {}

    def add_event(
        self,
        event_type: AuditEventType,
        actor: str,
        details: Dict[str, Any],
        timestamp: Optional[datetime] = None,
    ):
        """Add an event to the evidence trail."""
        self.events.append({
            "event_type": event_type.value,
            "actor": actor,
            "details": details,
            "timestamp": (timestamp or datetime.utcnow()).isoformat(),
        })

    def set_metadata(self, key: str, value: Any):
        """Set metadata key-value pair."""
        self.metadata[key] = value

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "decision_id": self.decision_id,
            "event_id": self.event_id,
            "factory_id": self.factory_id,
            "created_at": self.created_at.isoformat(),
            "events": self.events,
            "metadata": self.metadata,
        }

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=2)


class AuditLogger:
    """
    Central audit logging system.

    Logs all decision-related events and stores complete evidence packs
    for compliance, debugging, and replay.
    """

    def __init__(self):
        self.current_pack: Optional[EvidencePack] = None

    def start_decision(self, decision_id: str, event_id: str, factory_id: str):
        """Start logging a new decision."""
        self.current_pack = EvidencePack(decision_id, event_id, factory_id)

    def log_event(
        self,
        event_type: AuditEventType,
        actor: str,
        details: Dict[str, Any],
    ):
        """Log an audit event."""
        if not self.current_pack:
            raise RuntimeError("No decision in progress")
        self.current_pack.add_event(event_type, actor, details)

    def log_agent_analysis(
        self,
        agent_name: str,
        analysis: Dict[str, Any],
    ):
        """Log agent analysis."""
        self.log_event(
            AuditEventType.AGENT_ANALYZED,
            agent_name,
            {
                "recommendations": analysis.get("recommendations", []),
                "confidence": analysis.get("confidence"),
                "reasoning": analysis.get("reasoning"),
            },
        )

    def log_policy_check(
        self,
        action_name: str,
        policy_result: Dict[str, Any],
    ):
        """Log policy evaluation."""
        self.log_event(
            AuditEventType.POLICY_EVALUATED,
            "PolicyEngine",
            {
                "action": action_name,
                "decision": policy_result.get("policy_decision"),
                "approval_level": policy_result.get("approval_level"),
                "reason": policy_result.get("reason"),
            },
        )

    def log_impact_simulation(
        self,
        action_name: str,
        impact: Dict[str, Any],
    ):
        """Log Decision Twin impact estimation."""
        self.log_event(
            AuditEventType.IMPACT_SIMULATED,
            "DecisionTwin",
            {
                "action": action_name,
                "downtime_hours": impact.get("downtime_hours"),
                "scrap_units": impact.get("scrap_units"),
                "cost_impact": impact.get("cost_impact"),
                "impact_score": impact.get("impact_score"),
            },
        )

    def log_red_team_review(
        self,
        action_name: str,
        review: Dict[str, Any],
    ):
        """Log red-team challenge."""
        self.log_event(
            AuditEventType.RED_TEAM_CHALLENGED,
            "RedTeamAgent",
            {
                "action": action_name,
                "risk_factors": review.get("risk_factors", []),
                "assumptions_challenged": review.get("assumptions_challenged", []),
                "overall_risk_assessment": review.get("overall_risk_assessment"),
            },
        )

    def log_approval_routing(
        self,
        action_name: str,
        routing: Dict[str, Any],
    ):
        """Log approval gate routing."""
        self.log_event(
            AuditEventType.APPROVAL_ROUTED,
            "ApprovalGate",
            {
                "action": action_name,
                "approver_roles": routing.get("approver_roles", []),
                "approval_deadline_seconds": routing.get("approval_deadline_seconds"),
            },
        )

    def log_approval(
        self,
        approved: bool,
        approver_role: str,
        approver_id: str,
        notes: Optional[str] = None,
    ):
        """Log approval decision."""
        event_type = AuditEventType.DECISION_APPROVED if approved else AuditEventType.DECISION_REJECTED
        self.log_event(
            event_type,
            f"{approver_role}:{approver_id}",
            {
                "status": "approved" if approved else "rejected",
                "notes": notes,
            },
        )

    def log_execution(
        self,
        action_name: str,
        success: bool,
        details: Optional[Dict[str, Any]] = None,
    ):
        """Log action execution."""
        self.log_event(
            AuditEventType.ACTION_EXECUTED,
            "System",
            {
                "action": action_name,
                "success": success,
                "details": details or {},
            },
        )

    def log_outcome(
        self,
        outcome_data: Dict[str, Any],
    ):
        """Log final decision outcome."""
        self.log_event(
            AuditEventType.OUTCOME_RECORDED,
            "System",
            outcome_data,
        )

    def finish_decision(self) -> EvidencePack:
        """Finish logging and return evidence pack."""
        if not self.current_pack:
            raise RuntimeError("No decision in progress")
        pack = self.current_pack
        self.current_pack = None
        return pack

    def get_evidence_pack(self) -> Optional[EvidencePack]:
        """Get current evidence pack (without finishing)."""
        return self.current_pack


class AuditStore:
    """
    Persistent storage for audit logs and evidence packs.
    """

    def __init__(self, db_session):
        self.db = db_session

    def store_evidence_pack(self, pack: EvidencePack) -> str:
        """
        Store evidence pack in database.

        Returns audit log ID.
        """
        audit_log = AuditLogModel(
            id=f"audit_{pack.decision_id}",
            decision_id=pack.decision_id,
            event_type="evidence_pack",
            actor="System",
            action="store_evidence_pack",
            details=pack.to_dict(),
        )
        self.db.add(audit_log)
        self.db.commit()
        return audit_log.id

    def get_evidence_pack(self, decision_id: str) -> Optional[EvidencePack]:
        """Retrieve evidence pack for a decision."""
        record = self.db.query(AuditLogModel).filter(
            (AuditLogModel.decision_id == decision_id)
            & (AuditLogModel.event_type == "evidence_pack")
        ).first()

        if not record:
            return None

        pack_data = record.details
        pack = EvidencePack(
            pack_data["decision_id"],
            pack_data["event_id"],
            pack_data["factory_id"],
        )
        pack.events = pack_data.get("events", [])
        pack.metadata = pack_data.get("metadata", {})
        return pack

    def search_audit_logs(
        self,
        factory_id: str,
        event_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[List[Dict[str, Any]], int]:
        """
        Search audit logs with filters.

        Returns (logs, total_count).
        """
        query = self.db.query(AuditLogModel).filter(
            AuditLogModel.decision_id is not None
        )

        if event_type:
            query = query.filter(AuditLogModel.event_type == event_type)

        if start_date:
            query = query.filter(AuditLogModel.timestamp >= start_date)

        if end_date:
            query = query.filter(AuditLogModel.timestamp <= end_date)

        total = query.count()

        logs = (
            query.order_by(AuditLogModel.timestamp.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

        return (
            [
                {
                    "id": log.id,
                    "decision_id": log.decision_id,
                    "event_type": log.event_type,
                    "actor": log.actor,
                    "action": log.action,
                    "details": log.details,
                    "timestamp": log.timestamp.isoformat(),
                }
                for log in logs
            ],
            total,
        )

    def get_decision_timeline(self, decision_id: str) -> List[Dict[str, Any]]:
        """Get complete timeline of events for a decision."""
        logs = self.db.query(AuditLogModel).filter(
            AuditLogModel.decision_id == decision_id
        ).order_by(AuditLogModel.timestamp).all()

        return [
            {
                "timestamp": log.timestamp.isoformat(),
                "event_type": log.event_type,
                "actor": log.actor,
                "action": log.action,
                "details": log.details,
            }
            for log in logs
        ]

    def generate_compliance_report(
        self,
        factory_id: str,
        start_date: datetime,
        end_date: datetime,
    ) -> Dict[str, Any]:
        """Generate compliance report for date range."""
        logs, total = self.search_audit_logs(
            factory_id=factory_id,
            start_date=start_date,
            end_date=end_date,
            limit=10000,
        )

        # Calculate statistics
        event_type_counts = {}
        approvals = {"approved": 0, "rejected": 0}
        actions_executed = 0

        for log in logs:
            event_type = log["event_type"]
            event_type_counts[event_type] = event_type_counts.get(event_type, 0) + 1

            if event_type == "decision_approved":
                approvals["approved"] += 1
            elif event_type == "decision_rejected":
                approvals["rejected"] += 1
            elif event_type == "action_executed":
                actions_executed += 1

        return {
            "report_date": datetime.utcnow().isoformat(),
            "factory_id": factory_id,
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
            },
            "total_events": total,
            "event_type_counts": event_type_counts,
            "approvals": approvals,
            "actions_executed": actions_executed,
            "approval_rate": (
                approvals["approved"]
                / (approvals["approved"] + approvals["rejected"])
                if (approvals["approved"] + approvals["rejected"]) > 0
                else 0
            ),
        }
