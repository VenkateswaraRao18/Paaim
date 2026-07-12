from typing import Dict, List, Any, Optional
from datetime import datetime
from enum import Enum
import json

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from paaim.models import AuditLogModel


class AuditEventType(str, Enum):
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
    """Complete evidence trail for a single decision."""

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
        self.events.append({
            "event_type": event_type.value,
            "actor": actor,
            "details": details,
            "timestamp": (timestamp or datetime.utcnow()).isoformat(),
        })

    def set_metadata(self, key: str, value: Any):
        self.metadata[key] = value

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "event_id": self.event_id,
            "factory_id": self.factory_id,
            "created_at": self.created_at.isoformat(),
            "events": self.events,
            "metadata": self.metadata,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


class AuditLogger:
    """In-memory audit logger for a single decision flow."""

    def __init__(self):
        self.current_pack: Optional[EvidencePack] = None

    def start_decision(self, decision_id: str, event_id: str, factory_id: str):
        self.current_pack = EvidencePack(decision_id, event_id, factory_id)

    def log_event(self, event_type: AuditEventType, actor: str, details: Dict[str, Any]):
        if not self.current_pack:
            raise RuntimeError("No decision in progress")
        self.current_pack.add_event(event_type, actor, details)

    def log_agent_analysis(self, agent_name: str, analysis: Dict[str, Any]):
        self.log_event(AuditEventType.AGENT_ANALYZED, agent_name, {
            "recommendations": analysis.get("recommendations", []),
            "confidence": analysis.get("confidence"),
            "reasoning": analysis.get("reasoning"),
        })

    def log_policy_check(self, action_name: str, policy_result: Dict[str, Any]):
        self.log_event(AuditEventType.POLICY_EVALUATED, "PolicyEngine", {
            "action": action_name,
            "decision": policy_result.get("policy_decision"),
            "approval_level": policy_result.get("approval_level"),
            "reason": policy_result.get("reason"),
        })

    def log_impact_simulation(self, action_name: str, impact: Dict[str, Any]):
        self.log_event(AuditEventType.IMPACT_SIMULATED, "DecisionTwin", {
            "action": action_name,
            "downtime_hours": impact.get("downtime_hours"),
            "cost_impact": impact.get("cost_impact"),
            "impact_score": impact.get("impact_score"),
        })

    def log_red_team_review(self, action_name: str, review: Dict[str, Any]):
        self.log_event(AuditEventType.RED_TEAM_CHALLENGED, "RedTeamAgent", {
            "action": action_name,
            "risk_factors": review.get("risk_factors", []),
            "assumptions_challenged": review.get("assumptions_challenged", []),
            "overall_risk_assessment": review.get("overall_risk_assessment"),
        })

    def log_approval_routing(self, action_name: str, routing: Dict[str, Any]):
        self.log_event(AuditEventType.APPROVAL_ROUTED, "ApprovalGate", {
            "action": action_name,
            "approver_roles": routing.get("approver_roles", []),
        })

    def log_approval(self, approved: bool, approver_role: str, approver_id: str, notes: Optional[str] = None):
        event_type = AuditEventType.DECISION_APPROVED if approved else AuditEventType.DECISION_REJECTED
        self.log_event(event_type, f"{approver_role}:{approver_id}", {
            "status": "approved" if approved else "rejected",
            "notes": notes,
        })

    def finish_decision(self) -> EvidencePack:
        if not self.current_pack:
            raise RuntimeError("No decision in progress")
        pack = self.current_pack
        self.current_pack = None
        return pack

    def get_evidence_pack(self) -> Optional[EvidencePack]:
        return self.current_pack


class AuditStore:
    """Async persistence for audit logs and evidence packs."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def store_evidence_pack(self, pack: EvidencePack) -> str:
        audit_log = AuditLogModel(
            id=f"audit_{pack.decision_id}",
            decision_id=pack.decision_id,
            event_type="evidence_pack",
            actor="System",
            action="store_evidence_pack",
            details=pack.to_dict(),
        )
        self.db.add(audit_log)
        return audit_log.id

    async def get_evidence_pack(self, decision_id: str) -> Optional[EvidencePack]:
        result = await self.db.execute(
            select(AuditLogModel).where(
                AuditLogModel.decision_id == decision_id,
                AuditLogModel.event_type == "evidence_pack",
            )
        )
        record = result.scalar_one_or_none()
        if not record:
            return None

        pack_data = record.details
        pack = EvidencePack(pack_data["decision_id"], pack_data["event_id"], pack_data["factory_id"])
        pack.events = pack_data.get("events", [])
        pack.metadata = pack_data.get("metadata", {})
        return pack

    async def search_audit_logs(
        self,
        factory_id: str,
        event_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[List[Dict[str, Any]], int]:
        query = select(AuditLogModel).where(AuditLogModel.decision_id.isnot(None))

        if event_type:
            query = query.where(AuditLogModel.event_type == event_type)
        if start_date:
            query = query.where(AuditLogModel.timestamp >= start_date)
        if end_date:
            query = query.where(AuditLogModel.timestamp <= end_date)

        count_result = await self.db.execute(
            select(AuditLogModel.id).where(AuditLogModel.decision_id.isnot(None))
        )
        total = len(count_result.all())

        paginated = await self.db.execute(
            query.order_by(AuditLogModel.timestamp.desc()).offset(offset).limit(limit)
        )
        logs = paginated.scalars().all()

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

    async def get_decision_timeline(self, decision_id: str) -> List[Dict[str, Any]]:
        result = await self.db.execute(
            select(AuditLogModel)
            .where(AuditLogModel.decision_id == decision_id)
            .order_by(AuditLogModel.timestamp)
        )
        logs = result.scalars().all()
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

    async def generate_compliance_report(
        self,
        factory_id: str,
        start_date: datetime,
        end_date: datetime,
    ) -> Dict[str, Any]:
        logs, total = await self.search_audit_logs(
            factory_id=factory_id, start_date=start_date, end_date=end_date, limit=10000
        )

        event_type_counts: Dict[str, int] = {}
        approvals = {"approved": 0, "rejected": 0}
        actions_executed = 0

        for log in logs:
            et = log["event_type"]
            event_type_counts[et] = event_type_counts.get(et, 0) + 1
            if et == "decision_approved":
                approvals["approved"] += 1
            elif et == "decision_rejected":
                approvals["rejected"] += 1
            elif et == "action_executed":
                actions_executed += 1

        total_approvals = approvals["approved"] + approvals["rejected"]
        return {
            "report_date": datetime.utcnow().isoformat(),
            "factory_id": factory_id,
            "period": {"start": start_date.isoformat(), "end": end_date.isoformat()},
            "total_events": total,
            "event_type_counts": event_type_counts,
            "approvals": approvals,
            "actions_executed": actions_executed,
            "approval_rate": approvals["approved"] / total_approvals if total_approvals > 0 else 0,
        }
