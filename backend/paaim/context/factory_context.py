"""
Factory Context Service — the "Factory Event Graph"

Given an event + machine_id, assembles the full operational context:
  - Which work order is running on that machine
  - Which customer order that work order fulfils
  - The active material batch on that machine
  - Recent maintenance history
  - NCR/quality history for the product
  - Factory cost config

This context is injected into every agent prompt so agents reason about
real business tradeoffs, not just raw sensor signals.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from paaim.models import (
    MachineAssetModel,
    WorkOrderModel,
    CustomerOrderModel,
    MaterialBatchModel,
    MaintenanceRecordModel,
    CostConfigModel,
    NCRRecordModel,
    ProductModel,
)


# ── Context data classes ───────────────────────────────────────────────────────

@dataclass
class MachineContext:
    machine_id: str
    name: str
    asset_type: str
    criticality: str
    status: str
    hourly_production_value_usd: float
    days_since_last_maintenance: Optional[float]
    next_scheduled_maintenance: Optional[str]
    mtbf_hours: float
    mttr_hours: float


@dataclass
class WorkOrderContext:
    work_order_id: str
    product_name: str
    product_id: str
    quantity_planned: int
    quantity_completed: int
    quantity_scrapped: int
    completion_pct: float
    scheduled_end: Optional[str]
    hours_until_deadline: Optional[float]
    priority: str
    status: str
    rework_allowed: bool


@dataclass
class CustomerOrderContext:
    order_id: str
    customer_name: str
    quantity: int
    promised_delivery: str
    hours_until_delivery: float
    status: str
    priority: str
    late_delivery_penalty_usd: float
    contract_value_usd: float
    is_at_risk: bool                # < 24h to deadline


@dataclass
class MaterialContext:
    batch_id: str
    material_name: str
    quantity_remaining: float
    unit: str
    status: str
    quality_cert: bool
    supplier: str


@dataclass
class MaintenanceHistoryContext:
    last_3_records: List[Dict[str, Any]]
    total_downtime_last_30d_hours: float
    unplanned_events_last_30d: int
    avg_repair_cost_usd: float


@dataclass
class QualityHistoryContext:
    open_ncrs: int
    recurring_defects: List[str]
    scrap_rate_pct: float
    rework_rate_pct: float
    worst_defect_type: Optional[str]


@dataclass
class CostContext:
    """
    What this factory told us its economics are. Any field may be None: a plant
    that configured downtime cost but never priced scrap has one, not both, and
    the difference must survive all the way into the agents' prompt.
    """
    downtime_cost_per_hour_usd: Optional[float]
    scrap_cost_per_unit_usd: Optional[float]
    rework_cost_per_unit_usd: Optional[float]
    late_delivery_penalty_per_day_usd: Optional[float]
    labor_cost_per_hour_usd: Optional[float]
    unplanned_failure_multiplier: float          # a ratio, always known


@dataclass
class FactoryContext:
    """Full operational context for one event — passed to all agents."""
    factory_id: str
    machine: Optional[MachineContext] = None
    active_work_order: Optional[WorkOrderContext] = None
    customer_order: Optional[CustomerOrderContext] = None
    material_batch: Optional[MaterialContext] = None
    maintenance_history: Optional[MaintenanceHistoryContext] = None
    quality_history: Optional[QualityHistoryContext] = None
    costs: Optional[CostContext] = None
    context_fetched_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_prompt_text(self) -> str:
        """Human-readable context block for agent prompts."""
        lines = ["=== FACTORY OPERATIONAL CONTEXT ==="]

        if self.machine:
            m = self.machine
            lines.append(f"\nMACHINE: {m.name} ({m.machine_id})")
            lines.append(f"  Type: {m.asset_type} | Criticality: {m.criticality.upper()} | Status: {m.status}")
            lines.append(f"  Production value: ${m.hourly_production_value_usd:,.0f}/hr")
            if m.days_since_last_maintenance is not None:
                lines.append(f"  Last maintenance: {m.days_since_last_maintenance:.0f} days ago")
            if m.next_scheduled_maintenance:
                lines.append(f"  Next scheduled maintenance: {m.next_scheduled_maintenance}")

        if self.active_work_order:
            wo = self.active_work_order
            lines.append(f"\nACTIVE WORK ORDER: {wo.work_order_id}")
            lines.append(f"  Product: {wo.product_name} ({wo.product_id})")
            lines.append(f"  Progress: {wo.quantity_completed}/{wo.quantity_planned} units ({wo.completion_pct:.0f}%)")
            lines.append(f"  Scrapped so far: {wo.quantity_scrapped} units")
            lines.append(f"  Priority: {wo.priority.upper()} | Status: {wo.status}")
            if wo.hours_until_deadline is not None:
                urgency = "URGENT" if wo.hours_until_deadline < 8 else ("AT RISK" if wo.hours_until_deadline < 24 else "OK")
                lines.append(f"  Work order deadline: {wo.hours_until_deadline:.1f}h from now [{urgency}]")
            lines.append(f"  Rework allowed: {'Yes' if wo.rework_allowed else 'NO — scrap only'}")

        if self.customer_order:
            co = self.customer_order
            risk_flag = " *** DELIVERY AT RISK ***" if co.is_at_risk else ""
            lines.append(f"\nCUSTOMER ORDER: {co.order_id} — {co.customer_name}{risk_flag}")
            lines.append(f"  Delivery deadline: {co.promised_delivery} ({co.hours_until_delivery:.0f}h from now)")
            lines.append(f"  Priority: {co.priority.upper()} | Status: {co.status}")
            if co.late_delivery_penalty_usd > 0:
                lines.append(f"  Late delivery penalty: ${co.late_delivery_penalty_usd:,.0f}")
            if co.contract_value_usd > 0:
                lines.append(f"  Contract value: ${co.contract_value_usd:,.0f}")

        if self.material_batch:
            b = self.material_batch
            lines.append(f"\nMATERIAL BATCH: {b.batch_id} — {b.material_name}")
            lines.append(f"  Remaining: {b.quantity_remaining} {b.unit} | Status: {b.status}")
            if not b.quality_cert:
                lines.append(f"  *** QUALITY CERT MISSING — use with caution ***")

        if self.maintenance_history:
            mh = self.maintenance_history
            lines.append(f"\nMAINTENANCE HISTORY (last 30 days):")
            lines.append(f"  Total downtime: {mh.total_downtime_last_30d_hours:.1f}h")
            lines.append(f"  Unplanned events: {mh.unplanned_events_last_30d}")
            lines.append(f"  Avg repair cost: ${mh.avg_repair_cost_usd:,.0f}")
            for rec in mh.last_3_records[:2]:
                lines.append(f"  • {rec.get('date', '?')}: {rec.get('type', '?')} — {rec.get('description', '?')} ({rec.get('downtime_hours', 0):.1f}h)")

        if self.quality_history:
            qh = self.quality_history
            lines.append(f"\nQUALITY HISTORY:")
            lines.append(f"  Open NCRs: {qh.open_ncrs}")
            lines.append(f"  Scrap rate: {qh.scrap_rate_pct:.1f}% | Rework rate: {qh.rework_rate_pct:.1f}%")
            if qh.recurring_defects:
                lines.append(f"  Recurring defects: {', '.join(qh.recurring_defects)}")
            if qh.worst_defect_type:
                lines.append(f"  Most severe recent defect: {qh.worst_defect_type}")

        if self.costs:
            c = self.costs
            # Per-field, because a partially configured plant is the normal case
            # and each missing figure must read as missing. Formatting a None
            # here would also crash the whole context build.
            def _usd(v, suffix: str) -> str:
                return f"${v:,.0f}{suffix}" if v is not None else "not configured"

            lines.append(f"\nCOST ASSUMPTIONS (this factory):")
            lines.append(f"  Downtime: {_usd(c.downtime_cost_per_hour_usd, '/hr')}")
            lines.append(f"  Scrap: {_usd(c.scrap_cost_per_unit_usd, '/unit')} | "
                         f"Rework: {_usd(c.rework_cost_per_unit_usd, '/unit')}")
            lines.append(f"  Late delivery: {_usd(c.late_delivery_penalty_per_day_usd, '/day')}")
            lines.append(f"  Unplanned failure multiplier: {c.unplanned_failure_multiplier}x planned maintenance cost")
            if any(v is None for v in (c.downtime_cost_per_hour_usd, c.scrap_cost_per_unit_usd,
                                       c.late_delivery_penalty_per_day_usd)):
                lines.append("  Do not estimate the figures marked 'not configured' — say they are unknown.")
        else:
            # Stated, not omitted. Left silent, the model fills the gap with a
            # plausible-sounding figure of its own and the recommendation ends up
            # resting on a number nobody supplied.
            lines.append("\nCOST ASSUMPTIONS (this factory):")
            lines.append("  NOT CONFIGURED — this factory has no cost model.")
            lines.append("  Do not estimate or assume any financial figures. Reason from")
            lines.append("  safety, physical evidence and delivery impact only, and say")
            lines.append("  plainly that cost impact is unknown.")

        lines.append("\n=== END FACTORY CONTEXT ===")
        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        """JSON-serialisable dict for API responses and audit records."""
        def _safe(obj):
            if obj is None:
                return None
            if hasattr(obj, "__dict__"):
                return {k: v for k, v in obj.__dict__.items() if not k.startswith("_")}
            return obj

        return {
            "factory_id": self.factory_id,
            "machine": _safe(self.machine),
            "active_work_order": _safe(self.active_work_order),
            "customer_order": _safe(self.customer_order),
            "material_batch": _safe(self.material_batch),
            "maintenance_history": _safe(self.maintenance_history),
            "quality_history": _safe(self.quality_history),
            "costs": _safe(self.costs),
            "context_fetched_at": self.context_fetched_at,
        }


# ── Service ────────────────────────────────────────────────────────────────────

class FactoryContextService:
    """
    Assembles the full operational context for an event.

    Call build_context(factory_id, machine_id, db) before routing to agents.
    Returns a FactoryContext object that each agent receives in its prompt.
    """

    async def build_context(
        self,
        factory_id: str,
        machine_id: Optional[str],
        db: AsyncSession,
    ) -> FactoryContext:
        ctx = FactoryContext(factory_id=factory_id)

        if not machine_id:
            ctx.costs = await self._get_costs(factory_id, db)
            return ctx

        ctx.machine = await self._get_machine(factory_id, machine_id, db)
        ctx.active_work_order = await self._get_active_work_order(factory_id, machine_id, db)
        ctx.material_batch = await self._get_material_batch(factory_id, machine_id, db)
        ctx.maintenance_history = await self._get_maintenance_history(factory_id, machine_id, db)
        ctx.costs = await self._get_costs(factory_id, db)

        if ctx.active_work_order:
            ctx.customer_order = await self._get_customer_order(
                factory_id, ctx.active_work_order.work_order_id, db
            )
            ctx.quality_history = await self._get_quality_history(
                factory_id, machine_id, ctx.active_work_order.product_id, db
            )

        return ctx

    # ── Private fetch methods ──────────────────────────────────────────────────

    async def _get_machine(
        self, factory_id: str, machine_id: str, db: AsyncSession
    ) -> Optional[MachineContext]:
        row = await db.get(MachineAssetModel, machine_id)
        if not row or row.factory_id != factory_id:
            return None

        days_since = None
        if row.last_maintenance_date:
            delta = datetime.utcnow() - row.last_maintenance_date
            days_since = delta.total_seconds() / 86400

        next_maint = None
        if row.next_scheduled_maintenance:
            next_maint = row.next_scheduled_maintenance.strftime("%Y-%m-%d")

        return MachineContext(
            machine_id=row.id,
            name=row.name,
            asset_type=row.asset_type,
            criticality=row.criticality,
            status=row.status,
            hourly_production_value_usd=row.hourly_production_value_usd,
            days_since_last_maintenance=days_since,
            next_scheduled_maintenance=next_maint,
            mtbf_hours=row.mtbf_hours,
            mttr_hours=row.mttr_hours,
        )

    async def _get_active_work_order(
        self, factory_id: str, machine_id: str, db: AsyncSession
    ) -> Optional[WorkOrderContext]:
        q = (
            select(WorkOrderModel)
            .where(and_(
                WorkOrderModel.factory_id == factory_id,
                WorkOrderModel.machine_id == machine_id,
                WorkOrderModel.status == "in_progress",
            ))
            .order_by(WorkOrderModel.scheduled_end.asc())
            .limit(1)
        )
        row = (await db.execute(q)).scalar_one_or_none()
        if not row:
            return None

        product = await db.get(ProductModel, row.product_id) if row.product_id else None
        product_name = product.name if product else row.product_id or "Unknown"
        rework_allowed = product.rework_allowed if product else True
        completion_pct = (row.quantity_completed / row.quantity_planned * 100) if row.quantity_planned else 0

        hours_until = None
        if row.scheduled_end:
            delta = row.scheduled_end - datetime.utcnow()
            hours_until = delta.total_seconds() / 3600

        return WorkOrderContext(
            work_order_id=row.id,
            product_name=product_name,
            product_id=row.product_id or "",
            quantity_planned=row.quantity_planned,
            quantity_completed=row.quantity_completed,
            quantity_scrapped=row.quantity_scrapped,
            completion_pct=completion_pct,
            scheduled_end=row.scheduled_end.isoformat() if row.scheduled_end else None,
            hours_until_deadline=hours_until,
            priority=row.priority,
            status=row.status,
            rework_allowed=rework_allowed,
        )

    async def _get_customer_order(
        self, factory_id: str, work_order_id: str, db: AsyncSession
    ) -> Optional[CustomerOrderContext]:
        wo = await db.get(WorkOrderModel, work_order_id)
        if not wo or not wo.customer_order_id:
            return None

        co = await db.get(CustomerOrderModel, wo.customer_order_id)
        if not co:
            return None

        delta = co.promised_delivery - datetime.utcnow()
        hours_until = delta.total_seconds() / 3600
        is_at_risk = hours_until < 24

        return CustomerOrderContext(
            order_id=co.id,
            customer_name=co.customer_name,
            quantity=co.quantity,
            promised_delivery=co.promised_delivery.strftime("%Y-%m-%d %H:%M"),
            hours_until_delivery=hours_until,
            status=co.status,
            priority=co.priority,
            late_delivery_penalty_usd=co.late_delivery_penalty_usd,
            contract_value_usd=co.contract_value_usd,
            is_at_risk=is_at_risk,
        )

    async def _get_material_batch(
        self, factory_id: str, machine_id: str, db: AsyncSession
    ) -> Optional[MaterialContext]:
        q = (
            select(MaterialBatchModel)
            .where(and_(
                MaterialBatchModel.factory_id == factory_id,
                MaterialBatchModel.machine_id == machine_id,
                MaterialBatchModel.status == "in_use",
            ))
            .limit(1)
        )
        row = (await db.execute(q)).scalar_one_or_none()
        if not row:
            return None

        return MaterialContext(
            batch_id=row.id,
            material_name=row.material_name,
            quantity_remaining=row.quantity_remaining or 0,
            unit=row.unit,
            status=row.status,
            quality_cert=row.quality_cert,
            supplier=row.supplier or "Unknown",
        )

    async def _get_maintenance_history(
        self, factory_id: str, machine_id: str, db: AsyncSession
    ) -> Optional[MaintenanceHistoryContext]:
        from datetime import timedelta
        cutoff = datetime.utcnow() - timedelta(days=30)

        q = (
            select(MaintenanceRecordModel)
            .where(and_(
                MaintenanceRecordModel.factory_id == factory_id,
                MaintenanceRecordModel.machine_id == machine_id,
                MaintenanceRecordModel.started_at >= cutoff,
            ))
            .order_by(desc(MaintenanceRecordModel.started_at))
        )
        rows = (await db.execute(q)).scalars().all()

        if not rows:
            return None

        total_downtime = sum(r.downtime_hours for r in rows)
        unplanned = sum(1 for r in rows if r.maintenance_type == "unplanned")
        costs = [r.cost_usd for r in rows if r.cost_usd]
        avg_cost = sum(costs) / len(costs) if costs else 0

        recent_3 = [
            {
                "date": r.started_at.strftime("%Y-%m-%d"),
                "type": r.maintenance_type,
                "description": r.description or "",
                "downtime_hours": r.downtime_hours,
                "cost_usd": r.cost_usd,
            }
            for r in rows[:3]
        ]

        return MaintenanceHistoryContext(
            last_3_records=recent_3,
            total_downtime_last_30d_hours=total_downtime,
            unplanned_events_last_30d=unplanned,
            avg_repair_cost_usd=avg_cost,
        )

    async def _get_quality_history(
        self, factory_id: str, machine_id: str, product_id: str, db: AsyncSession
    ) -> Optional[QualityHistoryContext]:
        q = (
            select(NCRRecordModel)
            .where(and_(
                NCRRecordModel.factory_id == factory_id,
                NCRRecordModel.machine_id == machine_id,
            ))
            .order_by(desc(NCRRecordModel.opened_at))
            .limit(20)
        )
        rows = (await db.execute(q)).scalars().all()

        if not rows:
            return None

        open_ncrs = sum(1 for r in rows if r.status == "open")
        recurring = [r.defect_type for r in rows if r.recurrence_count > 0]
        defect_counts: Dict[str, int] = {}
        for r in rows:
            defect_counts[r.defect_type] = defect_counts.get(r.defect_type, 0) + r.quantity_affected

        total_affected = sum(defect_counts.values())
        scrap = sum(r.quantity_affected for r in rows if r.disposition == "scrap")
        rework = sum(r.quantity_affected for r in rows if r.disposition == "rework")
        scrap_rate = (scrap / total_affected * 100) if total_affected else 0
        rework_rate = (rework / total_affected * 100) if total_affected else 0

        worst = max(rows, key=lambda r: r.quantity_affected, default=None)

        return QualityHistoryContext(
            open_ncrs=open_ncrs,
            recurring_defects=list(set(recurring))[:3],
            scrap_rate_pct=scrap_rate,
            rework_rate_pct=rework_rate,
            worst_defect_type=worst.defect_type if worst else None,
        )

    async def _get_costs(
        self, factory_id: str, db: AsyncSession
    ) -> Optional[CostContext]:
        q = select(CostConfigModel).where(CostConfigModel.factory_id == factory_id).limit(1)
        row = (await db.execute(q)).scalar_one_or_none()
        if not row:
            # No cost model → None. These used to be six invented numbers under
            # the heading "sensible defaults", and they went into the agents'
            # prompt as "COST ASSUMPTIONS (this factory)". A plant that had told
            # PAAIM nothing about its economics had Gemini reasoning about its
            # $5,000/hour downtime and recommending line stops on the strength
            # of it. A default is only sensible where being wrong is cheap.
            return None
        return CostContext(
            downtime_cost_per_hour_usd=row.downtime_cost_per_hour_usd,
            scrap_cost_per_unit_usd=row.scrap_cost_per_unit_usd,
            rework_cost_per_unit_usd=row.rework_cost_per_unit_usd,
            late_delivery_penalty_per_day_usd=row.late_delivery_penalty_per_day_usd,
            labor_cost_per_hour_usd=row.labor_cost_per_hour_usd,
            unplanned_failure_multiplier=row.unplanned_failure_multiplier,
        )


# ── Singleton ──────────────────────────────────────────────────────────────────

_service: Optional[FactoryContextService] = None


def get_context_service() -> FactoryContextService:
    global _service
    if _service is None:
        _service = FactoryContextService()
    return _service
