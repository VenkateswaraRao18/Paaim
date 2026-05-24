from datetime import datetime
from enum import Enum
from typing import Optional, Any, Dict, List
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, Column, String, Float, DateTime, JSON, Integer, Boolean, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from paaim.config import settings

# Enums
class EventType(str, Enum):
    """Manufacturing event types."""
    SAFETY = "safety"
    QUALITY = "quality"
    MAINTENANCE = "maintenance"
    PRODUCTION = "production"
    ENERGY = "energy"
    COMPLIANCE = "compliance"


class RiskLevel(str, Enum):
    """Risk levels for decisions."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class DecisionStatus(str, Enum):
    """Decision workflow status."""
    RECOMMENDED = "recommended"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTED = "executed"
    FAILED = "failed"


class ApprovalLevel(str, Enum):
    """Required approval levels."""
    AUTO = "auto"
    OPERATOR = "operator"
    SUPERVISOR = "supervisor"
    MANAGER = "manager"
    SAFETY_OFFICER = "safety_officer"


# Pydantic Models (API)
class EventData(BaseModel):
    """Manufacturing event data."""
    event_type: EventType
    source_agent: str
    factory_id: str
    machine_id: Optional[str] = None
    signal_value: float
    signal_name: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    timestamp: datetime
    context: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        json_schema_extra = {
            "example": {
                "event_type": "safety",
                "source_agent": "safety_agent",
                "factory_id": "factory_001",
                "machine_id": "robot_arm_02",
                "signal_value": 1.0,
                "signal_name": "zone_intrusion",
                "confidence": 0.98,
                "timestamp": "2026-05-21T10:30:00Z",
                "context": {"zone_id": "restricted_zone_a", "worker_id": "W123"}
            }
        }


class ActionRecommendation(BaseModel):
    """Agent action recommendation."""
    action_name: str
    description: str
    risk_level: RiskLevel
    confidence: float = Field(..., ge=0.0, le=1.0)
    approval_required: ApprovalLevel
    assumptions: List[str]
    evidence_signals: List[str]
    estimated_impact: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        json_schema_extra = {
            "example": {
                "action_name": "stop_line",
                "description": "Stop production line due to safety hazard",
                "risk_level": "critical",
                "confidence": 0.99,
                "approval_required": "safety_officer",
                "assumptions": ["zone intrusion is genuine", "worker has no safety override"],
                "evidence_signals": ["zone_intrusion", "e_stop_ready"],
                "estimated_impact": {"downtime_hours": 0.5, "production_orders_affected": 3}
            }
        }


class Decision(BaseModel):
    """Decision made by orchestration layer."""
    decision_id: str
    event_id: str
    factory_id: str
    status: DecisionStatus
    recommended_action: ActionRecommendation
    alternative_actions: List[ActionRecommendation] = Field(default_factory=list)
    policy_constraints: List[str] = Field(default_factory=list)
    decision_twin_score: Optional[float] = None
    red_team_feedback: Optional[str] = None
    approved_action: Optional[ActionRecommendation] = None
    approved_by: Optional[str] = None
    approval_timestamp: Optional[datetime] = None
    executed_at: Optional[datetime] = None
    outcome: Optional[Dict[str, Any]] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_schema_extra = {
            "example": {
                "decision_id": "dec_20260521_001",
                "event_id": "evt_20260521_001",
                "factory_id": "factory_001",
                "status": "approved",
                "recommended_action": {},
                "alternative_actions": [],
                "policy_constraints": ["must_notify_supervisor", "requires_safety_officer_approval"],
                "decision_twin_score": 0.95,
                "red_team_feedback": "Recommendation verified safe. No conflicts detected.",
                "approved_action": {},
                "approved_by": "supervisor_001",
                "approval_timestamp": "2026-05-21T10:31:00Z",
                "executed_at": None,
                "outcome": None,
                "created_at": "2026-05-21T10:30:00Z"
            }
        }


class EvidencePack(BaseModel):
    """Complete evidence trail for a decision."""
    decision_id: str
    event_data: EventData
    agent_analyses: List[Dict[str, Any]] = Field(default_factory=list)
    policy_evaluation: Dict[str, Any] = Field(default_factory=dict)
    decision_twin_simulation: Optional[Dict[str, Any]] = None
    red_team_challenges: List[str] = Field(default_factory=list)
    approval_chain: List[Dict[str, Any]] = Field(default_factory=list)
    outcome_record: Optional[Dict[str, Any]] = None


# SQLAlchemy Models (Database)
Base = declarative_base()


class EventModel(Base):
    """Event record in database."""
    __tablename__ = "events"

    id = Column(String, primary_key=True)
    event_type = Column(String, nullable=False)
    factory_id = Column(String, nullable=False)
    machine_id = Column(String)
    signal_value = Column(Float)
    signal_name = Column(String)
    confidence = Column(Float)
    context = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)


class DecisionModel(Base):
    """Decision record in database."""
    __tablename__ = "decisions"

    id = Column(String, primary_key=True)
    event_id = Column(String, ForeignKey("events.id"))
    factory_id = Column(String, nullable=False)
    status = Column(String, nullable=False)
    recommended_action = Column(JSON)
    approved_action = Column(JSON)
    approved_by = Column(String)
    approval_timestamp = Column(DateTime)
    executed_at = Column(DateTime)
    outcome = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)


class AuditLogModel(Base):
    """Audit log entry."""
    __tablename__ = "audit_logs"

    id = Column(String, primary_key=True)
    decision_id = Column(String, ForeignKey("decisions.id"))
    event_type = Column(String)
    actor = Column(String)
    action = Column(String)
    details = Column(JSON)
    timestamp = Column(DateTime, default=datetime.utcnow)


class FactoryModel(Base):
    """Factory configuration."""
    __tablename__ = "factories"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    location = Column(String)
    config = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)


class ApprovalWorkflowModel(Base):
    """Approval workflow for decisions."""
    __tablename__ = "approval_workflows"

    id = Column(String, primary_key=True)
    decision_id = Column(String, ForeignKey("decisions.id"))
    approver_role = Column(String, nullable=False)
    status = Column(String, nullable=False)  # pending, approved, rejected
    notes = Column(String)
    approved_at = Column(DateTime)
    escalation_trail = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)



# Database setup
engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """Dependency for FastAPI to get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables():
    """Create all tables in the database."""
    Base.metadata.create_all(bind=engine)
