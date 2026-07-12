"""
Demo seed script — populates 30 days of realistic manufacturing events, decisions,
approvals, and audit logs so the analytics dashboard shows meaningful numbers.

Usage:
    cd backend
    python seed_demo.py [--clear]   # --clear wipes existing data first
"""

import asyncio
import random
import sys
import uuid
from datetime import datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

DATABASE_URL = "sqlite+aiosqlite:///./paaim_dev.db"

# ── Realistic manufacturing data pools ───────────────────────────────────────

FACTORIES = ["factory_001"]

EVENT_TYPES = ["safety", "quality", "maintenance", "production", "energy"]

MACHINES = {
    "safety":      ["robot_arm_01", "robot_arm_02", "conveyor_belt_a", "press_machine_3"],
    "quality":     ["cmm_sensor_01", "vision_system_b", "inline_qc_02", "laser_scanner_1"],
    "maintenance": ["cnc_mill_07", "hydraulic_press_2", "spindle_drive_04", "coolant_pump_3"],
    "production":  ["assembly_line_1", "stamping_press_5", "weld_station_3", "paint_booth_2"],
    "energy":      ["compressor_01", "hvac_unit_b", "transformer_02", "chiller_plant_1"],
}

SIGNALS = {
    "safety":      ["zone_intrusion", "estop_triggered", "guard_open", "collision_detected"],
    "quality":     ["surface_defect", "dimension_out_of_spec", "color_variance", "weld_porosity"],
    "maintenance": ["vibration_anomaly", "bearing_wear", "oil_temperature_high", "seal_leak"],
    "production":  ["throughput_drop", "cycle_time_increase", "buffer_overflow", "jam_detected"],
    "energy":      ["power_spike", "compressed_air_leak", "idle_overconsumption", "voltage_sag"],
}

ACTIONS = {
    "safety":      ["stop_line", "acknowledge_estop", "alert_safety_officer", "lockout_tagout"],
    "quality":     ["quarantine_batch", "recalibrate_sensor", "rework_parts", "notify_qc_team"],
    "maintenance": ["schedule_maintenance", "dispatch_technician", "order_spare_part", "reduce_load"],
    "production":  ["adjust_schedule", "activate_buffer", "notify_supervisor", "speed_reduction"],
    "energy":      ["load_shift", "repair_leak", "enable_power_saver", "notify_facilities"],
}

AGENTS = ["SafetyAgent", "QualityAgent", "MaintenanceAgent", "ProductionAgent", "EnergyAgent", "DigitalTwinAgent"]

APPROVERS = ["operator_001", "supervisor_jane", "manager_tom", "safety_officer_kim", "auto_system"]

LAYERS = ["signal_ingestion", "agent_analysis", "policy_engine", "digital_twin", "red_team", "approval_chain", "outcome_recorder"]

# Status distribution: 65% approved, 15% auto-approved (recommended=False), 12% recommended (pending), 8% rejected
STATUS_WEIGHTS = [("approved", 65), ("approved", 15), ("recommended", 12), ("rejected", 8)]

def _make_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"

def _rand_dt(base: datetime, hours_ago_max: int) -> datetime:
    delta_hours = random.uniform(0, hours_ago_max)
    return base - timedelta(hours=delta_hours)

def _make_latencies() -> dict:
    return {
        layer: round(random.uniform(20, 400), 1)
        for layer in LAYERS
    }

def _make_event_row(factory_id: str, event_type: str, created_at: datetime):
    machines = MACHINES[event_type]
    signals = SIGNALS[event_type]
    eid = f"evt_{created_at.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    return {
        "id": eid,
        "event_type": event_type,
        "factory_id": factory_id,
        "machine_id": random.choice(machines),
        "signal_value": round(random.uniform(0.5, 1.0), 3),
        "signal_name": random.choice(signals),
        "confidence": round(random.uniform(0.72, 0.99), 3),
        "context": {"zone": f"zone_{random.randint(1,5)}", "shift": random.choice(["A","B","C"])},
        "created_at": created_at,
    }

def _make_decision_row(event_id: str, factory_id: str, event_type: str, created_at: datetime, status: str):
    action = random.choice(ACTIONS[event_type])
    approved_by = None
    approval_ts = None
    if status in ("approved", "executed", "rejected"):
        approved_by = random.choice(APPROVERS[:-1]) if status != "rejected" else random.choice(APPROVERS[:4])
        approval_ts = created_at + timedelta(minutes=random.uniform(2, 120))

    return {
        "id": _make_id("dec"),
        "event_id": event_id,
        "factory_id": factory_id,
        "status": status,
        "recommended_action": {
            "selected_action": action,
            "approval_required": status == "recommended",
            "approval_route": "operator" if status == "recommended" else "auto",
            "confidence": round(random.uniform(0.78, 0.97), 3),
            "risk_level": random.choice(["low", "medium", "high"]),
        },
        "layer_latencies": _make_latencies(),
        "approved_by": approved_by,
        "approval_timestamp": approval_ts,
        "created_at": created_at,
    }

def _make_audit_rows(decision_id: str, event_id: str, event_type: str, status: str, created_at: datetime):
    rows = []
    signal = random.choice(SIGNALS[event_type])
    agent = random.choice(AGENTS)

    # 1. event detected
    rows.append({
        "id": f"audit_{decision_id}_detect",
        "decision_id": decision_id,
        "event_type": "event_detected",
        "actor": "System",
        "action": "event_detected",
        "details": {"event_id": event_id, "event_type": event_type, "signal_name": signal},
        "timestamp": created_at + timedelta(seconds=0.1),
    })
    # 2. agent analyzed
    rows.append({
        "id": f"audit_{decision_id}_agent_{agent}",
        "decision_id": decision_id,
        "event_type": "agent_analyzed",
        "actor": agent,
        "action": "analyze",
        "details": {"confidence": round(random.uniform(0.8, 0.99), 3), "reasoning": f"Detected anomaly in {event_type} subsystem."},
        "timestamp": created_at + timedelta(seconds=0.5),
    })
    # 3. policy evaluated
    rows.append({
        "id": f"audit_{decision_id}_policy",
        "decision_id": decision_id,
        "event_type": "policy_evaluated",
        "actor": "PolicyEngine",
        "action": "policy_evaluated",
        "details": {"approval_required": status == "recommended"},
        "timestamp": created_at + timedelta(seconds=1.0),
    })
    # 4. decision outcome
    rows.append({
        "id": f"audit_{decision_id}_decision",
        "decision_id": decision_id,
        "event_type": status,
        "actor": "Orchestrator",
        "action": "recommend_action",
        "details": {"status": status},
        "timestamp": created_at + timedelta(seconds=1.5),
    })
    return rows


async def seed(clear: bool = False):
    from paaim.models import Base, EventModel, DecisionModel, AuditLogModel, ApprovalWorkflowModel

    engine = create_async_engine(DATABASE_URL, echo=False)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with Session() as db:
        if clear:
            print("Clearing existing data…")
            await db.execute(text("DELETE FROM audit_logs"))
            await db.execute(text("DELETE FROM approval_workflows"))
            await db.execute(text("DELETE FROM decisions"))
            await db.execute(text("DELETE FROM events"))
            await db.commit()
            print("  ✓ Cleared.")

        now = datetime.utcnow()
        days = 30
        # Target: ~130 events/decisions spread over 30 days
        total = 130
        print(f"Seeding {total} events + decisions across {days} days…")

        for i in range(total):
            factory_id = "factory_001"
            event_type = random.choices(
                EVENT_TYPES,
                weights=[20, 25, 30, 15, 10],   # maintenance-heavy factory
            )[0]
            created_at = _rand_dt(now, days * 24)

            # Status distribution
            roll = random.randint(1, 100)
            if roll <= 65:
                status = "approved"
            elif roll <= 80:
                status = "approved"   # auto-approved (same DB status)
            elif roll <= 92:
                status = "recommended"
            else:
                status = "rejected"

            evt = _make_event_row(factory_id, event_type, created_at)
            db.add(EventModel(**evt))

            dec = _make_decision_row(evt["id"], factory_id, event_type, created_at, status)
            dec_id = dec["id"]
            db.add(DecisionModel(**dec))

            for audit_row in _make_audit_rows(dec_id, evt["id"], event_type, status, created_at):
                db.add(AuditLogModel(**audit_row))

            if status in ("approved", "rejected"):
                db.add(ApprovalWorkflowModel(
                    id=_make_id("wf"),
                    decision_id=dec_id,
                    approver_role=dec["approved_by"] or "operator",
                    status=status,
                    notes=None,
                    approved_at=dec["approval_timestamp"],
                ))

            if (i + 1) % 25 == 0:
                await db.commit()
                print(f"  {i+1}/{total} committed…")

        await db.commit()
        print(f"  ✓ All {total} records committed.")

    await engine.dispose()

    # Verify
    engine2 = create_async_engine(DATABASE_URL, echo=False)
    Session2 = async_sessionmaker(engine2, expire_on_commit=False)
    async with Session2() as db:
        from sqlalchemy import select, func
        ev_count = (await db.execute(select(func.count(EventModel.id)))).scalar()
        dec_count = (await db.execute(select(func.count(DecisionModel.id)))).scalar()
        approved_count = (await db.execute(
            select(func.count(DecisionModel.id)).where(DecisionModel.status.in_(["approved", "executed"]))
        )).scalar()
        audit_count = (await db.execute(select(func.count(AuditLogModel.id)))).scalar()
        print(f"\nDB state:")
        print(f"  Events:    {ev_count}")
        print(f"  Decisions: {dec_count}  (approved: {approved_count})")
        print(f"  Audit logs:{audit_count}")
        est = approved_count * 4500
        rate = round(approved_count / dec_count * 100, 1) if dec_count else 0
        print(f"\nExpected analytics preview:")
        print(f"  Approval rate:         {rate}%")
        print(f"  Est. cost savings:     ${est:,.0f}")
    await engine2.dispose()


if __name__ == "__main__":
    clear_flag = "--clear" in sys.argv
    asyncio.run(seed(clear=clear_flag))
