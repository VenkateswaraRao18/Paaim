"""Knowledge Model API - Factory schema, equipment, KPI, and context graph endpoints."""

import csv
import io
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from paaim.knowledge_model.factory_schema import get_factory
from paaim.knowledge_model.kpis import KPI_CATALOGUE, get_demo_kpi_snapshot, evaluate_kpis
from paaim.knowledge_model.learning import compute_profile
from paaim.models import (
    get_db, MachineAssetModel, WorkOrderModel, CustomerOrderModel,
    MaterialBatchModel, MaintenanceRecordModel, CostConfigModel, NCRRecordModel,
    ProductModel, FactoryKnowledgeModel,
)
from paaim.context.factory_context import get_context_service
from paaim.industry_packs.loader import list_packs, get_pack, apply_pack

router = APIRouter()


# ── Historical learning ────────────────────────────────────────────────────────

@router.post("/history/upload/{factory_id}")
async def upload_history(factory_id: str, file: UploadFile = File(...),
                         db: AsyncSession = Depends(get_db)):
    """
    Upload a factory's historical data (CSV). The system learns from it:
    per-machine baselines (normal ranges), failure frequency, MTBF and
    recurring issues — stored as the factory's knowledge profile.
    """
    raw = (await file.read()).decode("utf-8", errors="ignore")
    rows = list(csv.DictReader(io.StringIO(raw)))
    if not rows:
        raise HTTPException(status_code=400, detail="CSV is empty or unparseable.")

    profile = compute_profile(rows)

    existing = (await db.execute(
        select(FactoryKnowledgeModel).where(FactoryKnowledgeModel.factory_id == factory_id).limit(1)
    )).scalar_one_or_none()
    if existing:
        existing.profile = profile
        existing.records_analyzed = profile["records_analyzed"]
        existing.source_filename = file.filename
        existing.computed_at = datetime.utcnow()
        db.add(existing)
    else:
        db.add(FactoryKnowledgeModel(
            id=f"fk_{uuid.uuid4().hex[:8]}", factory_id=factory_id,
            profile=profile, records_analyzed=profile["records_analyzed"],
            source_filename=file.filename,
        ))
    await db.commit()

    return {
        "status": "learned",
        "factory_id": factory_id,
        "filename": file.filename,
        "records_analyzed": profile["records_analyzed"],
        "machines_learned": profile["machines_learned"],
        "total_failures": profile["total_failures"],
    }


@router.get("/history/profile/{factory_id}")
async def get_knowledge_profile(factory_id: str, db: AsyncSession = Depends(get_db)):
    """Return the learned factory knowledge profile (or empty if none yet)."""
    row = (await db.execute(
        select(FactoryKnowledgeModel).where(FactoryKnowledgeModel.factory_id == factory_id).limit(1)
    )).scalar_one_or_none()
    if not row:
        return {"factory_id": factory_id, "learned": False, "profile": None}
    return {
        "factory_id": factory_id, "learned": True,
        "records_analyzed": row.records_analyzed,
        "source_filename": row.source_filename,
        "computed_at": row.computed_at.isoformat(),
        "profile": row.profile,
    }


# ── Industry Packs ─────────────────────────────────────────────────────────────

@router.get("/packs")
async def list_industry_packs():
    """List all available industry pack templates."""
    return {"packs": list_packs(), "count": len(list_packs())}


@router.get("/packs/{pack_id}")
async def get_industry_pack(pack_id: str):
    """Get full detail for one industry pack."""
    try:
        return get_pack(pack_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Pack '{pack_id}' not found")


@router.post("/packs/{pack_id}/apply/{factory_id}")
async def apply_industry_pack(pack_id: str, factory_id: str, db: AsyncSession = Depends(get_db)):
    """Apply an industry pack to a factory — updates cost config and agent settings."""
    try:
        pack = await apply_pack(factory_id, pack_id, db)
        return {
            "applied": True,
            "pack_id": pack_id,
            "factory_id": factory_id,
            "display_name": pack.get("display_name"),
            "message": f"Pack '{pack.get('display_name')}' applied to factory '{factory_id}'",
        }
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/factory/{factory_id}")
async def get_factory_model(factory_id: str):
    """Get the full factory knowledge model."""
    try:
        factory = get_factory(factory_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Factory '{factory_id}' not found")

    return {
        "factory_id": factory.id,
        "name": factory.name,
        "location": factory.location,
        "zones": [
            {
                "id": z.id,
                "name": z.name,
                "type": z.type.value,
                "requires_ppe": z.requires_ppe,
                "safety_level": z.safety_level.value,
                "machine_count": len(z.machines),
                "machines": [
                    {
                        "id": m.id,
                        "name": m.name,
                        "type": m.type,
                        "criticality": m.criticality.value,
                        "status": m.status.value,
                        "mtbf_hours": m.mean_time_between_failures_hours,
                        "mttr_hours": m.mean_time_to_repair_hours,
                        "hourly_value_usd": m.hourly_production_value_usd,
                        "sensor_count": len(m.sensors),
                    }
                    for m in z.machines
                ],
            }
            for z in factory.zones
        ],
        "stats": {
            "total_zones": len(factory.zones),
            "total_machines": len(factory.get_all_machines()),
            "critical_machines": len(factory.get_critical_machines()),
            "production_target_per_shift": factory.production_target_units_per_shift,
            "daily_budget_usd": factory.daily_operating_budget_usd,
        },
    }


@router.get("/factory/{factory_id}/machine/{machine_id}")
async def get_machine_detail(factory_id: str, machine_id: str):
    """Get detailed machine information including sensors."""
    try:
        factory = get_factory(factory_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Factory '{factory_id}' not found")

    machine = factory.get_machine(machine_id)
    if not machine:
        raise HTTPException(status_code=404, detail=f"Machine '{machine_id}' not found")

    return {
        "id": machine.id,
        "name": machine.name,
        "type": machine.type,
        "zone_id": machine.zone_id,
        "criticality": machine.criticality.value,
        "status": machine.status.value,
        "oem_model": machine.oem_model,
        "install_year": machine.install_year,
        "mtbf_hours": machine.mean_time_between_failures_hours,
        "mttr_hours": machine.mean_time_to_repair_hours,
        "hourly_production_value_usd": machine.hourly_production_value_usd,
        "sensors": [
            {
                "id": s.id,
                "name": s.name,
                "type": s.type,
                "unit": s.unit,
                "normal_range": [s.normal_min, s.normal_max],
                "warning_threshold": s.warning_threshold,
                "critical_threshold": s.critical_threshold,
                "sampling_rate_hz": s.sampling_rate_hz,
                "enabled": s.enabled,
            }
            for s in machine.sensors
        ],
    }


@router.get("/kpis")
async def list_kpis():
    """List all KPI definitions in the catalogue."""
    return {
        "kpis": [
            {
                "id": kpi.id,
                "name": kpi.name,
                "description": kpi.description,
                "unit": kpi.unit,
                "target": kpi.target,
                "warning_threshold": kpi.warning_threshold,
                "critical_threshold": kpi.critical_threshold,
                "higher_is_better": kpi.higher_is_better,
                "category": kpi.category,
            }
            for kpi in KPI_CATALOGUE.values()
        ],
        "total": len(KPI_CATALOGUE),
        "categories": list({kpi.category for kpi in KPI_CATALOGUE.values()}),
    }


@router.get("/kpis/snapshot/{factory_id}")
async def get_kpi_snapshot(factory_id: str):
    """Get current KPI snapshot for a factory (demo data if no real data)."""
    return get_demo_kpi_snapshot(factory_id)


@router.post("/kpis/evaluate")
async def evaluate_factory_kpis(measurements: dict):
    """Evaluate provided KPI measurements against targets."""
    if not measurements:
        raise HTTPException(status_code=400, detail="No measurements provided")
    results = evaluate_kpis(measurements)
    return {
        "evaluations": results,
        "critical_count": sum(1 for r in results if r["status"] == "critical"),
        "at_risk_count": sum(1 for r in results if r["status"] == "at_risk"),
        "on_target_count": sum(1 for r in results if r["status"] == "on_target"),
    }


# ── Factory Context Graph endpoints ───────────────────────────────────────────

@router.get("/context/{factory_id}/machines")
async def list_machines(factory_id: str, db: AsyncSession = Depends(get_db)):
    """List all machines with current status and work order linkage."""
    q = select(MachineAssetModel).where(MachineAssetModel.factory_id == factory_id)
    machines = (await db.execute(q)).scalars().all()
    return {"machines": [
        {
            "id": m.id, "name": m.name, "asset_type": m.asset_type,
            "zone_id": m.zone_id, "criticality": m.criticality, "status": m.status,
            "hourly_production_value_usd": m.hourly_production_value_usd,
            "last_maintenance_date": m.last_maintenance_date.isoformat() if m.last_maintenance_date else None,
            "next_scheduled_maintenance": m.next_scheduled_maintenance.isoformat() if m.next_scheduled_maintenance else None,
            "mtbf_hours": m.mtbf_hours, "mttr_hours": m.mttr_hours,
        }
        for m in machines
    ], "count": len(machines)}


@router.get("/context/{factory_id}/work-orders")
async def list_work_orders(
    factory_id: str,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """List work orders with linked product and customer order info."""
    q = select(WorkOrderModel).where(WorkOrderModel.factory_id == factory_id)
    if status:
        q = q.where(WorkOrderModel.status == status)
    rows = (await db.execute(q)).scalars().all()

    result = []
    for wo in rows:
        product = await db.get(ProductModel, wo.product_id) if wo.product_id else None
        co = await db.get(CustomerOrderModel, wo.customer_order_id) if wo.customer_order_id else None
        pct = (wo.quantity_completed / wo.quantity_planned * 100) if wo.quantity_planned else 0
        result.append({
            "id": wo.id,
            "machine_id": wo.machine_id,
            "product_name": product.name if product else wo.product_id,
            "product_id": wo.product_id,
            "customer_order_id": wo.customer_order_id,
            "customer_name": co.customer_name if co else None,
            "quantity_planned": wo.quantity_planned,
            "quantity_completed": wo.quantity_completed,
            "quantity_scrapped": wo.quantity_scrapped,
            "completion_pct": round(pct, 1),
            "status": wo.status,
            "priority": wo.priority,
            "scheduled_end": wo.scheduled_end.isoformat() if wo.scheduled_end else None,
        })
    return {"work_orders": result, "count": len(result)}


@router.get("/context/{factory_id}/customer-orders")
async def list_customer_orders(
    factory_id: str,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """List customer orders with delivery risk flags."""
    from datetime import datetime, timedelta
    q = select(CustomerOrderModel).where(CustomerOrderModel.factory_id == factory_id)
    if status:
        q = q.where(CustomerOrderModel.status == status)
    rows = (await db.execute(q)).scalars().all()
    now = datetime.utcnow()
    return {"customer_orders": [
        {
            "id": co.id,
            "customer_name": co.customer_name,
            "product_id": co.product_id,
            "quantity": co.quantity,
            "quantity_delivered": co.quantity_delivered,
            "promised_delivery": co.promised_delivery.isoformat(),
            "hours_until_delivery": round((co.promised_delivery - now).total_seconds() / 3600, 1),
            "status": co.status,
            "priority": co.priority,
            "late_delivery_penalty_usd": co.late_delivery_penalty_usd,
            "contract_value_usd": co.contract_value_usd,
            "is_at_risk": (co.promised_delivery - now).total_seconds() / 3600 < 24 and co.status == "open",
        }
        for co in rows
    ], "count": len(rows)}


@router.get("/context/{factory_id}/machine/{machine_id}/context")
async def get_machine_context(factory_id: str, machine_id: str, db: AsyncSession = Depends(get_db)):
    """Get full operational context for a specific machine (what agents see)."""
    svc = get_context_service()
    ctx = await svc.build_context(factory_id, machine_id, db)
    return ctx.to_dict()


@router.get("/context/{factory_id}/ncrs")
async def list_ncrs(
    factory_id: str,
    status: Optional[str] = "open",
    db: AsyncSession = Depends(get_db)
):
    """List NCR/quality records."""
    q = select(NCRRecordModel).where(NCRRecordModel.factory_id == factory_id)
    if status:
        q = q.where(NCRRecordModel.status == status)
    rows = (await db.execute(q)).scalars().all()
    return {"ncrs": [
        {
            "id": r.id, "machine_id": r.machine_id, "product_id": r.product_id,
            "defect_type": r.defect_type, "severity": r.severity,
            "quantity_affected": r.quantity_affected, "disposition": r.disposition,
            "root_cause": r.root_cause, "status": r.status,
            "opened_at": r.opened_at.isoformat(), "recurrence_count": r.recurrence_count,
            "cost_impact_usd": r.cost_impact_usd,
        }
        for r in rows
    ], "count": len(rows)}


@router.get("/context/{factory_id}/summary")
async def get_context_summary(factory_id: str, db: AsyncSession = Depends(get_db)):
    """High-level summary of the factory context layer — for the dashboard."""
    from datetime import datetime
    now = datetime.utcnow()

    machines = (await db.execute(select(MachineAssetModel).where(MachineAssetModel.factory_id == factory_id))).scalars().all()
    work_orders = (await db.execute(select(WorkOrderModel).where(WorkOrderModel.factory_id == factory_id, WorkOrderModel.status == "in_progress"))).scalars().all()
    customer_orders = (await db.execute(select(CustomerOrderModel).where(CustomerOrderModel.factory_id == factory_id, CustomerOrderModel.status == "open"))).scalars().all()
    open_ncrs = (await db.execute(select(NCRRecordModel).where(NCRRecordModel.factory_id == factory_id, NCRRecordModel.status == "open"))).scalars().all()

    at_risk_orders = [co for co in customer_orders if (co.promised_delivery - now).total_seconds() / 3600 < 48]

    return {
        "factory_id": factory_id,
        "machines": {"total": len(machines), "running": sum(1 for m in machines if m.status == "running"), "fault": sum(1 for m in machines if m.status == "fault")},
        "work_orders": {"active": len(work_orders), "urgent": sum(1 for wo in work_orders if wo.priority in ("urgent", "high"))},
        "customer_orders": {"open": len(customer_orders), "at_risk": len(at_risk_orders), "total_penalty_exposure_usd": sum(co.late_delivery_penalty_usd for co in at_risk_orders)},
        "quality": {"open_ncrs": len(open_ncrs), "critical_ncrs": sum(1 for r in open_ncrs if r.severity == "critical")},
    }
