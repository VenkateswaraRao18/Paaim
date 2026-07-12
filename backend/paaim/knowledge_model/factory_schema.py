"""
Factory Knowledge Model - Equipment hierarchy, zones, and operational context.

Provides structured knowledge about the factory that agents can use to make
more context-aware recommendations. Replaces pure hardcoded heuristics with
a queryable factory model.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum


class ZoneType(str, Enum):
    PRODUCTION = "production"
    RESTRICTED = "restricted"
    MAINTENANCE = "maintenance"
    STORAGE = "storage"
    QUALITY_CONTROL = "quality_control"
    ENERGY = "energy"


class MachineStatus(str, Enum):
    RUNNING = "running"
    IDLE = "idle"
    MAINTENANCE = "maintenance"
    FAULT = "fault"
    OFFLINE = "offline"


class CriticalityLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class Sensor:
    """Individual sensor attached to a machine."""
    id: str
    name: str
    type: str                  # vibration, temperature, pressure, current, vision
    unit: str                  # m/s², °C, bar, A, bool
    normal_min: float
    normal_max: float
    warning_threshold: float
    critical_threshold: float
    sampling_rate_hz: float = 1.0
    enabled: bool = True

    def is_in_normal_range(self, value: float) -> bool:
        return self.normal_min <= value <= self.normal_max

    def get_severity(self, value: float) -> str:
        if abs(value) >= abs(self.critical_threshold):
            return "critical"
        if abs(value) >= abs(self.warning_threshold):
            return "warning"
        return "normal"


@dataclass
class Machine:
    """Individual machine or asset in the factory."""
    id: str
    name: str
    type: str                  # robot_arm, cnc_mill, conveyor, press, etc.
    zone_id: str
    criticality: CriticalityLevel
    sensors: List[Sensor] = field(default_factory=list)
    status: MachineStatus = MachineStatus.RUNNING
    oem_model: Optional[str] = None
    install_year: Optional[int] = None
    mean_time_between_failures_hours: float = 720.0  # MTBF
    mean_time_to_repair_hours: float = 2.0           # MTTR
    hourly_production_value_usd: float = 0.0         # value of output per hour
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get_sensor_by_type(self, sensor_type: str) -> Optional[Sensor]:
        for s in self.sensors:
            if s.type == sensor_type:
                return s
        return None

    def estimated_downtime_cost_usd(self, hours: float) -> float:
        return hours * self.hourly_production_value_usd


@dataclass
class Zone:
    """Factory zone grouping machines."""
    id: str
    name: str
    type: ZoneType
    machines: List[Machine] = field(default_factory=list)
    max_occupancy: int = 10
    requires_ppe: bool = False
    safety_level: CriticalityLevel = CriticalityLevel.MEDIUM
    description: str = ""

    def get_machine(self, machine_id: str) -> Optional[Machine]:
        for m in self.machines:
            if m.id == machine_id:
                return m
        return None

    def get_critical_machines(self) -> List[Machine]:
        return [m for m in self.machines if m.criticality == CriticalityLevel.CRITICAL]


@dataclass
class Factory:
    """Top-level factory knowledge model."""
    id: str
    name: str
    location: str
    zones: List[Zone] = field(default_factory=list)
    shift_hours: List[int] = field(default_factory=lambda: [6, 14, 22])  # shift starts
    production_target_units_per_shift: int = 1000
    daily_operating_budget_usd: float = 50_000.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get_zone(self, zone_id: str) -> Optional[Zone]:
        for z in self.zones:
            if z.id == zone_id:
                return z
        return None

    def get_machine(self, machine_id: str) -> Optional[Machine]:
        for z in self.zones:
            m = z.get_machine(machine_id)
            if m:
                return m
        return None

    def get_all_machines(self) -> List[Machine]:
        return [m for z in self.zones for m in z.machines]

    def get_critical_machines(self) -> List[Machine]:
        return [m for z in self.zones for m in z.get_critical_machines()]

    def to_context_dict(self, machine_id: Optional[str] = None) -> Dict[str, Any]:
        """Return a JSON-serialisable context dict for agent prompts."""
        ctx: Dict[str, Any] = {
            "factory_id": self.id,
            "factory_name": self.name,
            "location": self.location,
            "total_zones": len(self.zones),
            "total_machines": len(self.get_all_machines()),
            "critical_machine_count": len(self.get_critical_machines()),
            "production_target_per_shift": self.production_target_units_per_shift,
        }
        if machine_id:
            m = self.get_machine(machine_id)
            if m:
                ctx["machine"] = {
                    "id": m.id,
                    "name": m.name,
                    "type": m.type,
                    "criticality": m.criticality.value,
                    "status": m.status.value,
                    "mtbf_hours": m.mean_time_between_failures_hours,
                    "mttr_hours": m.mean_time_to_repair_hours,
                    "hourly_value_usd": m.hourly_production_value_usd,
                }
        return ctx


# ─── Default demo factory ─────────────────────────────────────────

def build_demo_factory() -> Factory:
    """Build a realistic demo factory for development and testing."""

    # Zone A: Assembly line
    zone_a = Zone(
        id="zone_a",
        name="Main Assembly Line",
        type=ZoneType.PRODUCTION,
        requires_ppe=True,
        safety_level=CriticalityLevel.HIGH,
        description="High-speed robot-assisted assembly",
    )
    zone_a.machines = [
        Machine(
            id="robot_arm_01",
            name="Robot Arm 1",
            type="robot_arm",
            zone_id="zone_a",
            criticality=CriticalityLevel.CRITICAL,
            hourly_production_value_usd=8_000,
            mean_time_between_failures_hours=480,
            mean_time_to_repair_hours=1.5,
            oem_model="FANUC M-20iA",
            install_year=2022,
            sensors=[
                Sensor("ra01_vib", "Vibration", "vibration", "m/s²", 0.0, 2.5, 3.0, 5.0, 100),
                Sensor("ra01_tmp", "Joint Temperature", "temperature", "°C", 20, 65, 75, 90, 1),
                Sensor("ra01_cur", "Motor Current", "current", "A", 0, 15, 18, 22, 10),
            ],
        ),
        Machine(
            id="robot_arm_02",
            name="Robot Arm 2",
            type="robot_arm",
            zone_id="zone_a",
            criticality=CriticalityLevel.CRITICAL,
            hourly_production_value_usd=8_000,
            mean_time_between_failures_hours=520,
            mean_time_to_repair_hours=1.5,
            oem_model="FANUC M-20iA",
            install_year=2022,
            sensors=[
                Sensor("ra02_vib", "Vibration", "vibration", "m/s²", 0.0, 2.5, 3.0, 5.0, 100),
                Sensor("ra02_tmp", "Joint Temperature", "temperature", "°C", 20, 65, 75, 90, 1),
            ],
        ),
        Machine(
            id="conveyor_01",
            name="Main Conveyor",
            type="conveyor",
            zone_id="zone_a",
            criticality=CriticalityLevel.HIGH,
            hourly_production_value_usd=5_000,
            mean_time_between_failures_hours=2000,
            mean_time_to_repair_hours=0.5,
            sensors=[
                Sensor("cv01_spd", "Belt Speed", "speed", "m/min", 0, 120, 130, 150, 10),
                Sensor("cv01_tmp", "Motor Temp", "temperature", "°C", 20, 55, 65, 80, 1),
            ],
        ),
    ]

    # Zone B: CNC machining
    zone_b = Zone(
        id="zone_b",
        name="CNC Machining Cell",
        type=ZoneType.PRODUCTION,
        requires_ppe=True,
        safety_level=CriticalityLevel.HIGH,
        description="Precision CNC milling and turning",
    )
    zone_b.machines = [
        Machine(
            id="cnc_mill_01",
            name="CNC Mill 1",
            type="cnc_mill",
            zone_id="zone_b",
            criticality=CriticalityLevel.HIGH,
            hourly_production_value_usd=3_500,
            mean_time_between_failures_hours=600,
            mean_time_to_repair_hours=3.0,
            oem_model="Haas VF-4",
            sensors=[
                Sensor("cnc01_vib", "Spindle Vibration", "vibration", "m/s²", 0, 1.5, 2.5, 4.0, 500),
                Sensor("cnc01_tmp", "Spindle Temp", "temperature", "°C", 20, 60, 70, 85, 1),
                Sensor("cnc01_cur", "Spindle Current", "current", "A", 0, 25, 30, 38, 10),
                Sensor("cnc01_tl", "Tool Wear", "tool_wear", "%", 0, 80, 90, 100, 0.1),
            ],
        ),
        Machine(
            id="cnc_lathe_01",
            name="CNC Lathe 1",
            type="cnc_lathe",
            zone_id="zone_b",
            criticality=CriticalityLevel.MEDIUM,
            hourly_production_value_usd=2_000,
            mean_time_between_failures_hours=800,
            mean_time_to_repair_hours=2.0,
            sensors=[
                Sensor("lt01_vib", "Vibration", "vibration", "m/s²", 0, 1.0, 2.0, 3.5, 200),
                Sensor("lt01_tmp", "Coolant Temp", "temperature", "°C", 15, 35, 45, 60, 1),
            ],
        ),
    ]

    # Zone C: Quality inspection
    zone_c = Zone(
        id="zone_c",
        name="Quality Control",
        type=ZoneType.QUALITY_CONTROL,
        requires_ppe=False,
        safety_level=CriticalityLevel.MEDIUM,
        description="Automated vision inspection + CMM",
    )
    zone_c.machines = [
        Machine(
            id="vision_sys_01",
            name="Vision Inspection System",
            type="vision_system",
            zone_id="zone_c",
            criticality=CriticalityLevel.HIGH,
            hourly_production_value_usd=0,  # quality gate, no direct production value
            sensors=[
                Sensor("vs01_def", "Defect Rate", "defect_rate", "%", 0, 1.5, 2.5, 5.0, 60),
                Sensor("vs01_thr", "Throughput", "throughput", "parts/hr", 50, 500, None, None, 1),
            ],
        ),
    ]

    # Zone D: Restricted / safety zone
    zone_d = Zone(
        id="zone_d",
        name="Restricted Safety Zone",
        type=ZoneType.RESTRICTED,
        requires_ppe=True,
        max_occupancy=2,
        safety_level=CriticalityLevel.CRITICAL,
        description="High-voltage / high-pressure equipment area",
    )
    zone_d.machines = [
        Machine(
            id="hydraulic_press_01",
            name="Hydraulic Press",
            type="hydraulic_press",
            zone_id="zone_d",
            criticality=CriticalityLevel.CRITICAL,
            hourly_production_value_usd=6_000,
            mean_time_between_failures_hours=350,
            mean_time_to_repair_hours=4.0,
            sensors=[
                Sensor("hp01_prs", "Pressure", "pressure", "bar", 0, 200, 220, 250, 10),
                Sensor("hp01_tmp", "Hydraulic Fluid Temp", "temperature", "°C", 20, 55, 65, 80, 1),
            ],
        ),
    ]

    return Factory(
        id="factory_001",
        name="Precision Manufacturing Plant A",
        location="Austin, TX",
        zones=[zone_a, zone_b, zone_c, zone_d],
        shift_hours=[6, 14, 22],
        production_target_units_per_shift=850,
        daily_operating_budget_usd=48_000,
    )


# Singleton factory model (load once, shared across requests)
_factory_registry: Dict[str, Factory] = {}


def get_factory(factory_id: str = "factory_001") -> Factory:
    """Get or initialise a factory model by ID."""
    if factory_id not in _factory_registry:
        if factory_id == "factory_001":
            _factory_registry[factory_id] = build_demo_factory()
        else:
            raise KeyError(f"Unknown factory: {factory_id}")
    return _factory_registry[factory_id]
