from datetime import datetime
from enum import Enum
from typing import Optional, Any, Dict, List

from pydantic import BaseModel, Field
from sqlalchemy import (
    Column, String, Float, DateTime, JSON, Integer, Boolean,
    ForeignKey, Index, text,
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from paaim.config import settings


# ── Enums ──────────────────────────────────────────────────────────────────────

class EventType(str, Enum):
    SAFETY = "safety"
    QUALITY = "quality"
    MAINTENANCE = "maintenance"
    PRODUCTION = "production"
    ENERGY = "energy"
    COMPLIANCE = "compliance"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class DecisionStatus(str, Enum):
    RECOMMENDED = "recommended"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTED = "executed"
    FAILED = "failed"


class ApprovalLevel(str, Enum):
    AUTO = "auto"
    OPERATOR = "operator"
    SUPERVISOR = "supervisor"
    MANAGER = "manager"
    SAFETY_OFFICER = "safety_officer"


# ── Pydantic API models ────────────────────────────────────────────────────────

class EventData(BaseModel):
    event_type: EventType
    source_agent: str
    factory_id: str
    machine_id: Optional[str] = None
    signal_value: float
    signal_name: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    timestamp: datetime
    context: Dict[str, Any] = Field(default_factory=dict)

    model_config = {
        "json_schema_extra": {
            "example": {
                "event_type": "safety",
                "source_agent": "safety_agent",
                "factory_id": "factory_001",
                "machine_id": "robot_arm_02",
                "signal_value": 1.0,
                "signal_name": "zone_intrusion",
                "confidence": 0.98,
                "timestamp": "2026-05-21T10:30:00Z",
                "context": {"zone_id": "restricted_zone_a", "worker_id": "W123"},
            }
        }
    }


class ActionRecommendation(BaseModel):
    action_name: str
    description: str
    risk_level: RiskLevel
    confidence: float = Field(..., ge=0.0, le=1.0)
    approval_required: ApprovalLevel
    assumptions: List[str]
    evidence_signals: List[str]
    estimated_impact: Dict[str, Any] = Field(default_factory=dict)


class Decision(BaseModel):
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


class EvidencePack(BaseModel):
    decision_id: str
    event_data: EventData
    agent_analyses: List[Dict[str, Any]] = Field(default_factory=list)
    policy_evaluation: Dict[str, Any] = Field(default_factory=dict)
    decision_twin_simulation: Optional[Dict[str, Any]] = None
    red_team_challenges: List[str] = Field(default_factory=list)
    approval_chain: List[Dict[str, Any]] = Field(default_factory=list)
    outcome_record: Optional[Dict[str, Any]] = None


# ── SQLAlchemy async ORM ───────────────────────────────────────────────────────

class Base(DeclarativeBase):
    pass


class EventModel(Base):
    __tablename__ = "events"

    id = Column(String, primary_key=True)
    event_type = Column(String, nullable=False)
    factory_id = Column(String, nullable=False)
    machine_id = Column(String)
    signal_value = Column(Float)
    signal_name = Column(String)
    confidence = Column(Float)
    context = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_events_factory_created", "factory_id", "created_at"),
        Index("ix_events_factory_type", "factory_id", "event_type"),
    )


class DecisionModel(Base):
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
    # Layer timing — ms per pipeline stage (stored for analytics)
    layer_latencies = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_decisions_factory_created", "factory_id", "created_at"),
        Index("ix_decisions_factory_status", "factory_id", "status"),
    )


class AuditLogModel(Base):
    __tablename__ = "audit_logs"

    id = Column(String, primary_key=True)
    decision_id = Column(String, ForeignKey("decisions.id"))
    event_type = Column(String)
    actor = Column(String)
    action = Column(String)
    details = Column(JSON)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_audit_decision", "decision_id"),
    )


class FactoryModel(Base):
    __tablename__ = "factories"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    location = Column(String)
    config = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


# ── Factory Context Layer tables ───────────────────────────────────────────────

class MachineAssetModel(Base):
    """Persistent machine/asset registry with live status and linked work orders."""
    __tablename__ = "machine_assets"

    id = Column(String, primary_key=True)           # e.g. "cnc_mill_01"
    factory_id = Column(String, nullable=False)
    name = Column(String, nullable=False)
    asset_type = Column(String, nullable=False)      # cnc_mill, robot_arm, conveyor …
    zone_id = Column(String)
    criticality = Column(String, default="medium")   # low/medium/high/critical
    status = Column(String, default="running")       # running/idle/maintenance/fault
    oem_model = Column(String)
    install_year = Column(Integer)
    mtbf_hours = Column(Float, default=720.0)
    mttr_hours = Column(Float, default=2.0)
    hourly_production_value_usd = Column(Float, default=0.0)
    last_maintenance_date = Column(DateTime)
    next_scheduled_maintenance = Column(DateTime)
    extra_data = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_machine_factory", "factory_id"),
    )


class ProductModel(Base):
    """Product catalog — quality specs, defect taxonomy, customer requirements."""
    __tablename__ = "products"

    id = Column(String, primary_key=True)           # e.g. "part_4521"
    factory_id = Column(String, nullable=False)
    name = Column(String, nullable=False)
    part_number = Column(String)
    customer_id = Column(String)                    # primary customer for this product
    quality_specs = Column(JSON)                    # tolerances, surface finish, etc.
    defect_taxonomy = Column(JSON)                  # list of known defect types + severity
    rework_allowed = Column(Boolean, default=True)
    scrap_cost_usd = Column(Float, default=50.0)    # cost per scrapped unit
    rework_cost_usd = Column(Float, default=20.0)
    cycle_time_seconds = Column(Float, default=30.0)
    extra_data = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_product_factory", "factory_id"),
    )


class WorkOrderModel(Base):
    """Active and scheduled work orders — links machine, product, and schedule."""
    __tablename__ = "work_orders"

    id = Column(String, primary_key=True)           # e.g. "WO-2234"
    factory_id = Column(String, nullable=False)
    machine_id = Column(String, ForeignKey("machine_assets.id"))
    product_id = Column(String, ForeignKey("products.id"))
    customer_order_id = Column(String)              # FK to customer_orders (nullable)
    quantity_planned = Column(Integer, nullable=False)
    quantity_completed = Column(Integer, default=0)
    quantity_scrapped = Column(Integer, default=0)
    status = Column(String, default="in_progress")  # scheduled/in_progress/completed/on_hold
    priority = Column(String, default="normal")     # low/normal/high/urgent
    scheduled_start = Column(DateTime)
    scheduled_end = Column(DateTime)
    actual_start = Column(DateTime)
    actual_end = Column(DateTime)
    shift = Column(String)                          # day/night/weekend
    operator_id = Column(String)
    notes = Column(String)
    extra_data = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_wo_factory_machine", "factory_id", "machine_id"),
        Index("ix_wo_status", "factory_id", "status"),
    )


class CustomerOrderModel(Base):
    """Customer orders with deadlines and delivery risk tracking."""
    __tablename__ = "customer_orders"

    id = Column(String, primary_key=True)           # e.g. "PO-8823"
    factory_id = Column(String, nullable=False)
    customer_name = Column(String, nullable=False)
    customer_id = Column(String)
    product_id = Column(String, ForeignKey("products.id"))
    quantity = Column(Integer, nullable=False)
    quantity_delivered = Column(Integer, default=0)
    order_date = Column(DateTime)
    promised_delivery = Column(DateTime, nullable=False)
    status = Column(String, default="open")         # open/at_risk/fulfilled/cancelled
    priority = Column(String, default="normal")     # low/normal/high/strategic
    late_delivery_penalty_usd = Column(Float, default=0.0)
    contract_value_usd = Column(Float, default=0.0)
    notes = Column(String)
    extra_data = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_co_factory_status", "factory_id", "status"),
        Index("ix_co_delivery", "factory_id", "promised_delivery"),
    )


class MaterialBatchModel(Base):
    """Material inventory and lot/batch tracking linked to machines and work orders."""
    __tablename__ = "material_batches"

    id = Column(String, primary_key=True)           # e.g. "LOT-991"
    factory_id = Column(String, nullable=False)
    material_name = Column(String, nullable=False)
    material_type = Column(String)                  # raw_material/component/consumable
    supplier = Column(String)
    quantity_total = Column(Float, nullable=False)
    quantity_remaining = Column(Float)
    unit = Column(String, default="kg")
    work_order_id = Column(String, ForeignKey("work_orders.id"))
    machine_id = Column(String)
    location = Column(String)                       # warehouse zone
    status = Column(String, default="available")    # available/in_use/quarantined/consumed
    quality_cert = Column(Boolean, default=True)
    expiry_date = Column(DateTime)
    received_date = Column(DateTime)
    cost_per_unit_usd = Column(Float, default=0.0)
    extra_data = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_batch_factory_machine", "factory_id", "machine_id"),
        Index("ix_batch_status", "factory_id", "status"),
    )


class MaintenanceRecordModel(Base):
    """Full maintenance history per machine — planned and unplanned."""
    __tablename__ = "maintenance_records"

    id = Column(String, primary_key=True)
    factory_id = Column(String, nullable=False)
    machine_id = Column(String, ForeignKey("machine_assets.id"), nullable=False)
    maintenance_type = Column(String, nullable=False)  # planned/unplanned/predictive
    description = Column(String)
    technician = Column(String)
    started_at = Column(DateTime, nullable=False)
    completed_at = Column(DateTime)
    downtime_hours = Column(Float, default=0.0)
    cost_usd = Column(Float, default=0.0)
    parts_replaced = Column(JSON, default=list)
    outcome = Column(String)                        # resolved/partial/escalated
    related_decision_id = Column(String)            # link back to PAAIM decision
    extra_data = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_maint_machine", "factory_id", "machine_id"),
        Index("ix_maint_started", "factory_id", "started_at"),
    )


class CostConfigModel(Base):
    """Cost assumptions per factory — used by Decision Twin for real dollar calculations."""
    __tablename__ = "cost_configs"

    id = Column(String, primary_key=True)
    factory_id = Column(String, nullable=False, unique=True)
    downtime_cost_per_hour_usd = Column(Float, default=5_000.0)
    scrap_cost_per_unit_usd = Column(Float, default=50.0)
    rework_cost_per_unit_usd = Column(Float, default=20.0)
    late_delivery_penalty_per_day_usd = Column(Float, default=2_500.0)
    energy_cost_per_kwh_usd = Column(Float, default=0.12)
    labor_cost_per_hour_usd = Column(Float, default=75.0)
    planned_maintenance_cost_per_hour_usd = Column(Float, default=200.0)
    unplanned_failure_multiplier = Column(Float, default=5.0)  # unplanned costs 5x planned
    overtime_rate_multiplier = Column(Float, default=1.5)
    extra_data = Column(JSON, default=dict)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_cost_factory", "factory_id"),
    )


class FactoryKnowledgeModel(Base):
    """Learned knowledge profile built from a factory's uploaded historical data."""
    __tablename__ = "factory_knowledge"

    id = Column(String, primary_key=True)
    factory_id = Column(String, nullable=False, unique=True)
    profile = Column(JSON, default=dict)          # baselines, MTBF, recurring issues per machine
    records_analyzed = Column(Integer, default=0)
    source_filename = Column(String)
    computed_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_knowledge_factory", "factory_id"),
    )


class NCRRecordModel(Base):
    """Non-Conformance Reports and CAPA history per product/machine."""
    __tablename__ = "ncr_records"

    id = Column(String, primary_key=True)           # e.g. "NCR-0042"
    factory_id = Column(String, nullable=False)
    machine_id = Column(String)
    product_id = Column(String)
    work_order_id = Column(String)
    defect_type = Column(String, nullable=False)
    severity = Column(String, default="minor")      # minor/major/critical
    quantity_affected = Column(Integer, default=0)
    disposition = Column(String)                    # scrap/rework/use_as_is/return_to_vendor
    root_cause = Column(String)
    corrective_action = Column(String)
    status = Column(String, default="open")         # open/in_progress/closed/recurring
    opened_at = Column(DateTime, nullable=False)
    closed_at = Column(DateTime)
    cost_impact_usd = Column(Float, default=0.0)
    recurrence_count = Column(Integer, default=0)   # times this same defect has recurred
    extra_data = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_ncr_machine", "factory_id", "machine_id"),
        Index("ix_ncr_product", "factory_id", "product_id"),
    )


class ApprovalWorkflowModel(Base):
    __tablename__ = "approval_workflows"

    id = Column(String, primary_key=True)
    decision_id = Column(String, ForeignKey("decisions.id"))
    approver_role = Column(String, nullable=False)
    status = Column(String, nullable=False)
    notes = Column(String)
    approved_at = Column(DateTime)
    escalation_trail = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_approval_decision", "decision_id"),
    )


# ── Async engine & session factory ────────────────────────────────────────────

_connect_args: dict = {}
if settings.DATABASE_URL.startswith("sqlite"):
    _connect_args = {"check_same_thread": False}

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DB_ECHO,
    connect_args=_connect_args,
    # Pool settings are ignored for SQLite; apply for PostgreSQL
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db():
    """FastAPI dependency — yields an async DB session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def create_tables():
    """Create all tables (used on startup when Alembic is not yet run)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
