"""
Seed script for the Factory Context Layer (Phase 3).

Populates the 6 new tables with realistic synthetic data for factory_001:
  - machine_assets
  - products
  - work_orders
  - customer_orders
  - material_batches
  - maintenance_records
  - cost_configs
  - ncr_records

Run:
    cd backend && source venv/bin/activate
    python seed_context.py
    python seed_context.py --clear   # wipe and re-seed
"""

import asyncio
import sys
import uuid
from datetime import datetime, timedelta
import random

# ── Bootstrap SQLAlchemy before importing models ──────────────────────────────
import os
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./paaim_dev.db")

from paaim.models import (
    engine, Base,
    MachineAssetModel, ProductModel, WorkOrderModel,
    CustomerOrderModel, MaterialBatchModel, MaintenanceRecordModel,
    CostConfigModel, NCRRecordModel,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker

AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

NOW = datetime.utcnow()


def days_ago(n): return NOW - timedelta(days=n)
def hours_from_now(h): return NOW + timedelta(hours=h)
def days_from_now(d): return NOW + timedelta(days=d)


async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def clear_context_tables(session):
    from sqlalchemy import text
    tables = [
        "ncr_records", "maintenance_records", "material_batches",
        "work_orders", "customer_orders", "products",
        "machine_assets", "cost_configs",
    ]
    for t in tables:
        await session.execute(text(f"DELETE FROM {t}"))
    await session.commit()
    print("  Context tables cleared.")


async def seed_machines(session):
    machines = [
        MachineAssetModel(
            id="robot_arm_01", factory_id="factory_001",
            name="Robot Arm 1 (FANUC M-20iA)", asset_type="robot_arm",
            zone_id="zone_a", criticality="critical", status="running",
            oem_model="FANUC M-20iA", install_year=2022,
            mtbf_hours=480, mttr_hours=1.5,
            hourly_production_value_usd=8_000,
            last_maintenance_date=days_ago(12),
            next_scheduled_maintenance=days_from_now(18),
        ),
        MachineAssetModel(
            id="robot_arm_02", factory_id="factory_001",
            name="Robot Arm 2 (FANUC M-20iA)", asset_type="robot_arm",
            zone_id="zone_a", criticality="critical", status="running",
            oem_model="FANUC M-20iA", install_year=2022,
            mtbf_hours=520, mttr_hours=1.5,
            hourly_production_value_usd=8_000,
            last_maintenance_date=days_ago(45),
            next_scheduled_maintenance=days_from_now(5),
            extra_data={"alert": "overdue_for_maintenance"},
        ),
        MachineAssetModel(
            id="conveyor_01", factory_id="factory_001",
            name="Main Conveyor Belt", asset_type="conveyor",
            zone_id="zone_a", criticality="high", status="running",
            install_year=2020, mtbf_hours=2000, mttr_hours=0.5,
            hourly_production_value_usd=5_000,
            last_maintenance_date=days_ago(7),
            next_scheduled_maintenance=days_from_now(23),
        ),
        MachineAssetModel(
            id="cnc_mill_01", factory_id="factory_001",
            name="CNC Mill 1 (Haas VF-4)", asset_type="cnc_mill",
            zone_id="zone_b", criticality="high", status="running",
            oem_model="Haas VF-4", install_year=2021,
            mtbf_hours=600, mttr_hours=3.0,
            hourly_production_value_usd=3_500,
            last_maintenance_date=days_ago(30),
            next_scheduled_maintenance=days_from_now(60),
        ),
        MachineAssetModel(
            id="cnc_lathe_01", factory_id="factory_001",
            name="CNC Lathe 1", asset_type="cnc_lathe",
            zone_id="zone_b", criticality="medium", status="running",
            install_year=2019, mtbf_hours=800, mttr_hours=2.0,
            hourly_production_value_usd=2_000,
            last_maintenance_date=days_ago(60),
            next_scheduled_maintenance=days_from_now(30),
        ),
        MachineAssetModel(
            id="vision_sys_01", factory_id="factory_001",
            name="Vision Inspection System", asset_type="vision_system",
            zone_id="zone_c", criticality="high", status="running",
            install_year=2023, mtbf_hours=4000, mttr_hours=0.5,
            hourly_production_value_usd=0,
            last_maintenance_date=days_ago(5),
            next_scheduled_maintenance=days_from_now(85),
        ),
        MachineAssetModel(
            id="hydraulic_press_01", factory_id="factory_001",
            name="Hydraulic Press", asset_type="hydraulic_press",
            zone_id="zone_d", criticality="critical", status="running",
            install_year=2018, mtbf_hours=350, mttr_hours=4.0,
            hourly_production_value_usd=6_000,
            last_maintenance_date=days_ago(8),
            next_scheduled_maintenance=days_from_now(22),
        ),
    ]
    for m in machines:
        session.add(m)
    await session.commit()
    print(f"  {len(machines)} machines seeded.")
    return machines


async def seed_products(session):
    products = [
        ProductModel(
            id="part_4521", factory_id="factory_001",
            name="Precision Bearing Housing", part_number="BH-4521",
            customer_id="ford_motor",
            quality_specs={
                "tolerance_mm": 0.02,
                "surface_finish_ra": 0.8,
                "hardness_hrc": "58-62",
                "material": "4140 steel",
            },
            defect_taxonomy=[
                {"type": "dimensional_deviation", "severity": "major", "acceptance": "reject"},
                {"type": "surface_scratch", "severity": "minor", "acceptance": "rework"},
                {"type": "porosity", "severity": "critical", "acceptance": "scrap"},
                {"type": "tool_mark", "severity": "minor", "acceptance": "rework"},
            ],
            rework_allowed=True,
            scrap_cost_usd=85.0,
            rework_cost_usd=25.0,
            cycle_time_seconds=45.0,
        ),
        ProductModel(
            id="part_7830", factory_id="factory_001",
            name="Drive Shaft Assembly", part_number="DS-7830",
            customer_id="toyota",
            quality_specs={
                "runout_tolerance_mm": 0.05,
                "balance_g_mm": 10,
                "material": "EN36 steel",
                "heat_treatment": "case_hardened",
            },
            defect_taxonomy=[
                {"type": "runout_deviation", "severity": "critical", "acceptance": "scrap"},
                {"type": "balance_failure", "severity": "major", "acceptance": "rework"},
                {"type": "surface_crack", "severity": "critical", "acceptance": "scrap"},
            ],
            rework_allowed=False,
            scrap_cost_usd=220.0,
            rework_cost_usd=0.0,
            cycle_time_seconds=120.0,
        ),
        ProductModel(
            id="part_2210", factory_id="factory_001",
            name="Valve Body Casting", part_number="VB-2210",
            customer_id="caterpillar",
            quality_specs={
                "pressure_rating_bar": 350,
                "leak_test": "required",
                "material": "ductile_iron",
            },
            defect_taxonomy=[
                {"type": "porosity", "severity": "critical", "acceptance": "scrap"},
                {"type": "dimensional_deviation", "severity": "major", "acceptance": "rework"},
                {"type": "surface_crack", "severity": "critical", "acceptance": "scrap"},
            ],
            rework_allowed=True,
            scrap_cost_usd=140.0,
            rework_cost_usd=45.0,
            cycle_time_seconds=90.0,
        ),
    ]
    for p in products:
        session.add(p)
    await session.commit()
    print(f"  {len(products)} products seeded.")
    return products


async def seed_customer_orders(session):
    orders = [
        CustomerOrderModel(
            id="PO-8823", factory_id="factory_001",
            customer_name="Ford Motor Company", customer_id="ford_motor",
            product_id="part_4521", quantity=2000,
            quantity_delivered=0,
            order_date=days_ago(15),
            promised_delivery=days_from_now(3),   # tight deadline
            status="open", priority="strategic",
            late_delivery_penalty_usd=15_000.0,
            contract_value_usd=220_000.0,
            notes="Q2 production launch — no delay acceptable",
        ),
        CustomerOrderModel(
            id="PO-7741", factory_id="factory_001",
            customer_name="Toyota Manufacturing", customer_id="toyota",
            product_id="part_7830", quantity=500,
            quantity_delivered=200,
            order_date=days_ago(30),
            promised_delivery=days_from_now(14),
            status="open", priority="high",
            late_delivery_penalty_usd=8_000.0,
            contract_value_usd=185_000.0,
        ),
        CustomerOrderModel(
            id="PO-6612", factory_id="factory_001",
            customer_name="Caterpillar Inc.", customer_id="caterpillar",
            product_id="part_2210", quantity=300,
            quantity_delivered=300,
            order_date=days_ago(45),
            promised_delivery=days_ago(2),
            status="fulfilled", priority="normal",
            late_delivery_penalty_usd=3_000.0,
            contract_value_usd=78_000.0,
        ),
        CustomerOrderModel(
            id="PO-9001", factory_id="factory_001",
            customer_name="Ford Motor Company", customer_id="ford_motor",
            product_id="part_4521", quantity=1500,
            quantity_delivered=0,
            order_date=days_ago(5),
            promised_delivery=days_from_now(30),
            status="open", priority="normal",
            late_delivery_penalty_usd=10_000.0,
            contract_value_usd=165_000.0,
        ),
    ]
    for o in orders:
        session.add(o)
    await session.commit()
    print(f"  {len(orders)} customer orders seeded.")
    return orders


async def seed_work_orders(session):
    work_orders = [
        # Active on robot_arm_01 — making bearing housings for Ford PO-8823
        WorkOrderModel(
            id="WO-2234", factory_id="factory_001",
            machine_id="robot_arm_01", product_id="part_4521",
            customer_order_id="PO-8823",
            quantity_planned=800, quantity_completed=612, quantity_scrapped=8,
            status="in_progress", priority="urgent",
            scheduled_start=days_ago(3),
            scheduled_end=hours_from_now(28),  # tight
            actual_start=days_ago(3),
            shift="day", operator_id="operator_001",
            notes="Ford launch-critical run. Monitor scrap rate closely.",
        ),
        # Active on cnc_mill_01 — making bearing housings for Ford PO-9001
        WorkOrderModel(
            id="WO-2235", factory_id="factory_001",
            machine_id="cnc_mill_01", product_id="part_4521",
            customer_order_id="PO-9001",
            quantity_planned=500, quantity_completed=120, quantity_scrapped=2,
            status="in_progress", priority="normal",
            scheduled_start=days_ago(1),
            scheduled_end=days_from_now(8),
            actual_start=days_ago(1),
            shift="day", operator_id="operator_002",
        ),
        # Active on cnc_lathe_01 — drive shafts for Toyota
        WorkOrderModel(
            id="WO-2236", factory_id="factory_001",
            machine_id="cnc_lathe_01", product_id="part_7830",
            customer_order_id="PO-7741",
            quantity_planned=300, quantity_completed=245, quantity_scrapped=5,
            status="in_progress", priority="high",
            scheduled_start=days_ago(7),
            scheduled_end=days_from_now(6),
            actual_start=days_ago(7),
            shift="day", operator_id="operator_003",
        ),
        # Active on hydraulic_press_01 — valve bodies for Caterpillar (new order)
        WorkOrderModel(
            id="WO-2237", factory_id="factory_001",
            machine_id="hydraulic_press_01", product_id="part_2210",
            customer_order_id=None,
            quantity_planned=100, quantity_completed=0, quantity_scrapped=0,
            status="scheduled", priority="normal",
            scheduled_start=days_from_now(2),
            scheduled_end=days_from_now(10),
            shift="day", operator_id="operator_001",
        ),
        # Completed work order (historical)
        WorkOrderModel(
            id="WO-2230", factory_id="factory_001",
            machine_id="robot_arm_02", product_id="part_2210",
            customer_order_id="PO-6612",
            quantity_planned=300, quantity_completed=298, quantity_scrapped=2,
            status="completed", priority="normal",
            scheduled_start=days_ago(45),
            scheduled_end=days_ago(5),
            actual_start=days_ago(45),
            actual_end=days_ago(3),
            shift="day", operator_id="operator_002",
        ),
    ]
    for wo in work_orders:
        session.add(wo)
    await session.commit()
    print(f"  {len(work_orders)} work orders seeded.")
    return work_orders


async def seed_material_batches(session):
    batches = [
        # Active batch on robot_arm_01
        MaterialBatchModel(
            id="LOT-991", factory_id="factory_001",
            material_name="4140 Steel Bar Stock", material_type="raw_material",
            supplier="Metals USA", quantity_total=500.0, quantity_remaining=285.0,
            unit="kg", work_order_id="WO-2234", machine_id="robot_arm_01",
            location="zone_b_rack_3", status="in_use",
            quality_cert=True, received_date=days_ago(10),
            cost_per_unit_usd=3.20,
        ),
        # Active batch on cnc_mill_01
        MaterialBatchModel(
            id="LOT-992", factory_id="factory_001",
            material_name="4140 Steel Bar Stock", material_type="raw_material",
            supplier="Metals USA", quantity_total=300.0, quantity_remaining=245.0,
            unit="kg", work_order_id="WO-2235", machine_id="cnc_mill_01",
            location="zone_b_rack_4", status="in_use",
            quality_cert=True, received_date=days_ago(2),
            cost_per_unit_usd=3.20,
        ),
        # Quarantined batch — quality issue flagged
        MaterialBatchModel(
            id="LOT-988", factory_id="factory_001",
            material_name="EN36 Steel Round Bar", material_type="raw_material",
            supplier="North Steel", quantity_total=200.0, quantity_remaining=200.0,
            unit="kg", machine_id="cnc_lathe_01",
            location="quarantine_area", status="quarantined",
            quality_cert=False, received_date=days_ago(14),
            cost_per_unit_usd=5.10,
            extra_data={"quarantine_reason": "certification_missing", "supplier_ticket": "NS-4421"},
        ),
        # Cutting fluid consumable on cnc_mill_01
        MaterialBatchModel(
            id="LOT-993", factory_id="factory_001",
            material_name="Castrol Hysol 9R Cutting Fluid", material_type="consumable",
            supplier="Castrol Industrial", quantity_total=200.0, quantity_remaining=140.0,
            unit="liters", machine_id="cnc_mill_01",
            location="zone_b_fluid_station", status="in_use",
            quality_cert=True, received_date=days_ago(20),
            cost_per_unit_usd=8.50,
        ),
    ]
    for b in batches:
        session.add(b)
    await session.commit()
    print(f"  {len(batches)} material batches seeded.")
    return batches


async def seed_maintenance_records(session):
    records = []

    # robot_arm_01 — recent planned maintenance
    records.append(MaintenanceRecordModel(
        id=f"MR-{uuid.uuid4().hex[:8]}",
        factory_id="factory_001", machine_id="robot_arm_01",
        maintenance_type="planned",
        description="Scheduled lubrication, joint inspection, encoder calibration",
        technician="tech_003",
        started_at=days_ago(12), completed_at=days_ago(12) + timedelta(hours=2),
        downtime_hours=2.0, cost_usd=450.0,
        parts_replaced=[], outcome="resolved",
    ))

    # robot_arm_02 — overdue, last maintenance was 45 days ago + an unplanned one
    records.append(MaintenanceRecordModel(
        id=f"MR-{uuid.uuid4().hex[:8]}",
        factory_id="factory_001", machine_id="robot_arm_02",
        maintenance_type="planned",
        description="Periodic lubrication and vision calibration",
        technician="tech_001",
        started_at=days_ago(45), completed_at=days_ago(45) + timedelta(hours=1.5),
        downtime_hours=1.5, cost_usd=350.0,
        parts_replaced=[], outcome="resolved",
    ))
    records.append(MaintenanceRecordModel(
        id=f"MR-{uuid.uuid4().hex[:8]}",
        factory_id="factory_001", machine_id="robot_arm_02",
        maintenance_type="unplanned",
        description="Gripper actuator failure — emergency replacement",
        technician="tech_002",
        started_at=days_ago(20), completed_at=days_ago(20) + timedelta(hours=3.5),
        downtime_hours=3.5, cost_usd=1_850.0,
        parts_replaced=["gripper_actuator_v2"], outcome="resolved",
        extra_data={"failure_mode": "actuator_seal_leak"},
    ))

    # cnc_mill_01 — 30 days ago planned
    records.append(MaintenanceRecordModel(
        id=f"MR-{uuid.uuid4().hex[:8]}",
        factory_id="factory_001", machine_id="cnc_mill_01",
        maintenance_type="planned",
        description="Spindle bearing inspection, coolant flush, tool calibration",
        technician="tech_004",
        started_at=days_ago(30), completed_at=days_ago(30) + timedelta(hours=4),
        downtime_hours=4.0, cost_usd=1_200.0,
        parts_replaced=["coolant_filter", "spindle_seal"],
        outcome="resolved",
    ))

    # hydraulic_press_01 — recent check
    records.append(MaintenanceRecordModel(
        id=f"MR-{uuid.uuid4().hex[:8]}",
        factory_id="factory_001", machine_id="hydraulic_press_01",
        maintenance_type="planned",
        description="Hydraulic fluid change, seal inspection, pressure test",
        technician="tech_003",
        started_at=days_ago(8), completed_at=days_ago(8) + timedelta(hours=3),
        downtime_hours=3.0, cost_usd=800.0,
        parts_replaced=["hydraulic_filter"], outcome="resolved",
    ))

    # cnc_lathe_01 — old and an unplanned
    records.append(MaintenanceRecordModel(
        id=f"MR-{uuid.uuid4().hex[:8]}",
        factory_id="factory_001", machine_id="cnc_lathe_01",
        maintenance_type="planned",
        description="Annual overhaul — spindle, turret, coolant system",
        technician="tech_001",
        started_at=days_ago(60), completed_at=days_ago(58),
        downtime_hours=16.0, cost_usd=4_500.0,
        parts_replaced=["spindle_bearing_set", "turret_index_disc"],
        outcome="resolved",
    ))

    for r in records:
        session.add(r)
    await session.commit()
    print(f"  {len(records)} maintenance records seeded.")
    return records


async def seed_cost_config(session):
    config = CostConfigModel(
        id=f"cc_{uuid.uuid4().hex[:8]}",
        factory_id="factory_001",
        downtime_cost_per_hour_usd=6_200.0,   # blended across all lines
        scrap_cost_per_unit_usd=65.0,
        rework_cost_per_unit_usd=28.0,
        late_delivery_penalty_per_day_usd=3_500.0,
        energy_cost_per_kwh_usd=0.14,
        labor_cost_per_hour_usd=82.0,
        planned_maintenance_cost_per_hour_usd=210.0,
        unplanned_failure_multiplier=5.5,
        overtime_rate_multiplier=1.5,
        extra_data={
            "currency": "USD",
            "last_reviewed": days_ago(90).isoformat(),
            "source": "finance_team_q1_2026",
        },
    )
    session.add(config)
    await session.commit()
    print("  Cost config seeded.")
    return config


async def seed_ncr_records(session):
    records = [
        # Open NCR — dimensional deviation on robot_arm_01, current product
        NCRRecordModel(
            id="NCR-0041", factory_id="factory_001",
            machine_id="robot_arm_01", product_id="part_4521",
            work_order_id="WO-2234",
            defect_type="dimensional_deviation",
            severity="major", quantity_affected=8,
            disposition="rework", root_cause="tool_wear",
            corrective_action="Replace insert, re-inspect first 20 parts of next run",
            status="in_progress",
            opened_at=days_ago(2),
            cost_impact_usd=200.0, recurrence_count=2,
        ),
        # Closed NCR — previous run
        NCRRecordModel(
            id="NCR-0039", factory_id="factory_001",
            machine_id="robot_arm_01", product_id="part_4521",
            work_order_id="WO-2230",
            defect_type="dimensional_deviation",
            severity="major", quantity_affected=5,
            disposition="scrap", root_cause="tool_wear",
            corrective_action="Tool life limit reduced from 800 to 650 parts",
            status="closed",
            opened_at=days_ago(18), closed_at=days_ago(15),
            cost_impact_usd=425.0, recurrence_count=1,
        ),
        # Open NCR — surface scratch on CNC lathe (Toyota part)
        NCRRecordModel(
            id="NCR-0042", factory_id="factory_001",
            machine_id="cnc_lathe_01", product_id="part_7830",
            work_order_id="WO-2236",
            defect_type="surface_scratch",
            severity="minor", quantity_affected=3,
            disposition="rework",
            root_cause="chip_management",
            corrective_action="Increase coolant flow pressure, add chip brush",
            status="open",
            opened_at=days_ago(4),
            cost_impact_usd=84.0, recurrence_count=0,
        ),
        # Critical closed NCR — porosity on valve bodies
        NCRRecordModel(
            id="NCR-0035", factory_id="factory_001",
            machine_id="hydraulic_press_01", product_id="part_2210",
            work_order_id="WO-2230",
            defect_type="porosity",
            severity="critical", quantity_affected=12,
            disposition="scrap",
            root_cause="raw_material_quality",
            corrective_action="Supplier qualification audit completed. New batch certified.",
            status="closed",
            opened_at=days_ago(40), closed_at=days_ago(30),
            cost_impact_usd=1_680.0, recurrence_count=0,
        ),
    ]
    for r in records:
        session.add(r)
    await session.commit()
    print(f"  {len(records)} NCR records seeded.")
    return records


async def main():
    clear = "--clear" in sys.argv

    print("\nPAAIM — Factory Context Layer seed")
    print("=" * 40)

    await create_tables()

    async with AsyncSessionLocal() as session:
        if clear:
            await clear_context_tables(session)

        print("Seeding factory context data...")
        await seed_machines(session)
        await seed_products(session)
        await seed_customer_orders(session)
        await seed_work_orders(session)
        await seed_material_batches(session)
        await seed_maintenance_records(session)
        await seed_cost_config(session)
        await seed_ncr_records(session)

    print("\nFactory context seeded successfully.")
    print("The next event on robot_arm_01 will show:")
    print("  Machine: Robot Arm 1 (critical, last maintained 12 days ago)")
    print("  Work Order: WO-2234 — Bearing Housing for Ford PO-8823")
    print("  Customer: Ford Motor Company — delivery in ~3 days, $15K penalty")
    print("  Quality: NCR-0041 open (dimensional deviation, 2 recurrences)")
    print("  Cost: $6,200/hr downtime, $65/unit scrap\n")


if __name__ == "__main__":
    asyncio.run(main())
