"""
Factory KPI Definitions - OEE, MTBF, MTTR, quality metrics.

Provides a structured KPI framework that agents can use to measure factory
performance and evaluate the business impact of decisions.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum
from datetime import datetime


class KpiStatus(str, Enum):
    ON_TARGET = "on_target"
    AT_RISK = "at_risk"
    BELOW_TARGET = "below_target"
    CRITICAL = "critical"


@dataclass
class KpiDefinition:
    """Definition of a single KPI with targets and thresholds."""
    id: str
    name: str
    description: str
    unit: str
    target: float
    warning_threshold: float      # below this = at_risk
    critical_threshold: float     # below this = critical
    higher_is_better: bool = True
    category: str = "operational"

    def get_status(self, value: float) -> KpiStatus:
        cmp = value if self.higher_is_better else -value
        tgt = self.target if self.higher_is_better else -self.target
        warn = self.warning_threshold if self.higher_is_better else -self.warning_threshold
        crit = self.critical_threshold if self.higher_is_better else -self.critical_threshold

        if cmp >= tgt:
            return KpiStatus.ON_TARGET
        if cmp >= warn:
            return KpiStatus.AT_RISK
        if cmp >= crit:
            return KpiStatus.BELOW_TARGET
        return KpiStatus.CRITICAL


@dataclass
class KpiValue:
    """A measured KPI value with timestamp."""
    kpi_id: str
    factory_id: str
    value: float
    timestamp: datetime = field(default_factory=datetime.utcnow)
    machine_id: Optional[str] = None
    zone_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "kpi_id": self.kpi_id,
            "factory_id": self.factory_id,
            "machine_id": self.machine_id,
            "zone_id": self.zone_id,
            "value": self.value,
            "timestamp": self.timestamp.isoformat(),
        }


# ─── Standard manufacturing KPI catalogue ────────────────────────

OEE = KpiDefinition(
    id="oee",
    name="Overall Equipment Effectiveness",
    description="Availability × Performance × Quality — gold standard for manufacturing efficiency",
    unit="%",
    target=85.0,
    warning_threshold=75.0,
    critical_threshold=60.0,
    higher_is_better=True,
    category="efficiency",
)

AVAILABILITY = KpiDefinition(
    id="availability",
    name="Machine Availability",
    description="Planned production time minus unplanned downtime",
    unit="%",
    target=95.0,
    warning_threshold=88.0,
    critical_threshold=75.0,
    higher_is_better=True,
    category="reliability",
)

PERFORMANCE_RATE = KpiDefinition(
    id="performance_rate",
    name="Performance Rate",
    description="Actual throughput vs. theoretical maximum throughput",
    unit="%",
    target=95.0,
    warning_threshold=85.0,
    critical_threshold=70.0,
    higher_is_better=True,
    category="efficiency",
)

QUALITY_RATE = KpiDefinition(
    id="quality_rate",
    name="Quality Rate (First-Pass Yield)",
    description="Percentage of parts produced within spec on first pass",
    unit="%",
    target=99.0,
    warning_threshold=97.0,
    critical_threshold=95.0,
    higher_is_better=True,
    category="quality",
)

SCRAP_RATE = KpiDefinition(
    id="scrap_rate",
    name="Scrap Rate",
    description="Percentage of parts scrapped (not reworkable)",
    unit="%",
    target=0.5,
    warning_threshold=1.5,
    critical_threshold=3.0,
    higher_is_better=False,
    category="quality",
)

MTBF = KpiDefinition(
    id="mtbf",
    name="Mean Time Between Failures",
    description="Average operating time between unplanned failures",
    unit="hours",
    target=500.0,
    warning_threshold=300.0,
    critical_threshold=150.0,
    higher_is_better=True,
    category="reliability",
)

MTTR = KpiDefinition(
    id="mttr",
    name="Mean Time To Repair",
    description="Average time to restore a machine after failure",
    unit="hours",
    target=1.5,
    warning_threshold=3.0,
    critical_threshold=6.0,
    higher_is_better=False,
    category="maintenance",
)

PLANNED_MAINTENANCE_COMPLIANCE = KpiDefinition(
    id="pm_compliance",
    name="Planned Maintenance Compliance",
    description="Percentage of scheduled PMs completed on time",
    unit="%",
    target=95.0,
    warning_threshold=85.0,
    critical_threshold=70.0,
    higher_is_better=True,
    category="maintenance",
)

ENERGY_INTENSITY = KpiDefinition(
    id="energy_intensity",
    name="Energy Intensity",
    description="kWh consumed per unit produced",
    unit="kWh/unit",
    target=2.5,
    warning_threshold=3.5,
    critical_threshold=5.0,
    higher_is_better=False,
    category="energy",
)

SAFETY_INCIDENT_RATE = KpiDefinition(
    id="safety_incident_rate",
    name="Safety Incident Rate",
    description="OSHA-recordable incidents per 200,000 work hours",
    unit="incidents/200k hrs",
    target=0.0,
    warning_threshold=1.0,
    critical_threshold=3.0,
    higher_is_better=False,
    category="safety",
)

NEAR_MISS_RATE = KpiDefinition(
    id="near_miss_rate",
    name="Near-Miss Reporting Rate",
    description="Near-misses reported per week (leading safety indicator)",
    unit="reports/week",
    target=5.0,      # higher = more proactive reporting culture
    warning_threshold=2.0,
    critical_threshold=0.0,
    higher_is_better=True,
    category="safety",
)

THROUGHPUT = KpiDefinition(
    id="throughput",
    name="Production Throughput",
    description="Units produced per shift",
    unit="units/shift",
    target=850.0,
    warning_threshold=720.0,
    critical_threshold=600.0,
    higher_is_better=True,
    category="production",
)

CYCLE_TIME = KpiDefinition(
    id="cycle_time",
    name="Cycle Time",
    description="Average time per unit produced",
    unit="seconds",
    target=28.0,
    warning_threshold=35.0,
    critical_threshold=45.0,
    higher_is_better=False,
    category="production",
)


# ─── KPI registry ────────────────────────────────────────────────

KPI_CATALOGUE: Dict[str, KpiDefinition] = {
    kpi.id: kpi
    for kpi in [
        OEE, AVAILABILITY, PERFORMANCE_RATE, QUALITY_RATE, SCRAP_RATE,
        MTBF, MTTR, PLANNED_MAINTENANCE_COMPLIANCE,
        ENERGY_INTENSITY,
        SAFETY_INCIDENT_RATE, NEAR_MISS_RATE,
        THROUGHPUT, CYCLE_TIME,
    ]
}


def get_kpi(kpi_id: str) -> Optional[KpiDefinition]:
    return KPI_CATALOGUE.get(kpi_id)


def evaluate_kpis(measured: Dict[str, float]) -> List[Dict[str, Any]]:
    """
    Evaluate a set of measured KPI values against their targets.

    Args:
        measured: {kpi_id: value} mapping

    Returns:
        List of evaluation dicts sorted by severity
    """
    results = []
    for kpi_id, value in measured.items():
        kpi = KPI_CATALOGUE.get(kpi_id)
        if not kpi:
            continue
        status = kpi.get_status(value)
        results.append({
            "kpi_id": kpi_id,
            "name": kpi.name,
            "value": value,
            "unit": kpi.unit,
            "target": kpi.target,
            "status": status.value,
            "category": kpi.category,
        })

    # Worst status first
    order = [KpiStatus.CRITICAL, KpiStatus.BELOW_TARGET, KpiStatus.AT_RISK, KpiStatus.ON_TARGET]
    return sorted(results, key=lambda r: order.index(KpiStatus(r["status"])))


def get_demo_kpi_snapshot(factory_id: str = "factory_001") -> Dict[str, Any]:
    """Return a realistic demo KPI snapshot for a factory."""
    measured = {
        "oee": 82.3,
        "availability": 93.1,
        "performance_rate": 91.5,
        "quality_rate": 98.4,
        "scrap_rate": 1.1,
        "mtbf": 412.0,
        "mttr": 1.8,
        "pm_compliance": 91.0,
        "energy_intensity": 2.9,
        "safety_incident_rate": 0.0,
        "near_miss_rate": 4.0,
        "throughput": 798.0,
        "cycle_time": 31.2,
    }
    evaluations = evaluate_kpis(measured)
    return {
        "factory_id": factory_id,
        "snapshot_time": datetime.utcnow().isoformat(),
        "kpis": evaluations,
        "overall_health": "at_risk" if any(e["status"] in ("critical", "below_target") for e in evaluations) else "on_target",
    }
