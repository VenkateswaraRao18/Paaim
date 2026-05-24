import asyncio
import json
import random
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, AsyncGenerator
from enum import Enum

from paaim.models import EventType, EventData


class ScenarioDifficulty(str, Enum):
    """Difficulty levels for event scenarios."""
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class EventSimulator:
    """Generates synthetic factory event streams for demo and testing."""

    def __init__(self):
        self.base_timestamp = datetime.utcnow()
        self.event_counter = 0
        self.factory_id = "factory_001"

    def generate_event_id(self) -> str:
        """Generate unique event ID."""
        self.event_counter += 1
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        return f"evt_{timestamp}_{self.event_counter:04d}"

    def _create_event(
        self,
        event_type: EventType,
        signal_name: str,
        signal_value: float,
        confidence: float,
        machine_id: str = "machine_001",
        context: Optional[Dict[str, Any]] = None,
    ) -> EventData:
        """Create a single event."""
        if context is None:
            context = {}

        return EventData(
            event_type=event_type,
            source_agent=f"{event_type.value}_agent",
            factory_id=self.factory_id,
            machine_id=machine_id,
            signal_value=signal_value,
            signal_name=signal_name,
            confidence=confidence,
            timestamp=datetime.utcnow(),
            context=context,
        )

    # ===== SAFETY EVENT GENERATORS =====
    def generate_zone_intrusion(self) -> EventData:
        """Worker enters restricted zone."""
        return self._create_event(
            event_type=EventType.SAFETY,
            signal_name="zone_intrusion",
            signal_value=1.0,
            confidence=0.98,
            machine_id="robot_arm_02",
            context={
                "zone_id": "restricted_zone_a",
                "worker_id": "W123",
                "breach_duration_ms": 500,
            },
        )

    def generate_estop_signal(self) -> EventData:
        """Emergency stop button activated."""
        return self._create_event(
            event_type=EventType.SAFETY,
            signal_name="e_stop_signal",
            signal_value=1.0,
            confidence=1.0,
            machine_id="control_panel_01",
            context={
                "button_id": "estop_main",
                "activation_reason": "manual_override",
            },
        )

    # ===== QUALITY EVENT GENERATORS =====
    def generate_defect_detection(self) -> EventData:
        """High defect rate detected."""
        return self._create_event(
            event_type=EventType.QUALITY,
            signal_name="defect_detection",
            signal_value=8.5,  # defects per 100 units
            confidence=0.92,
            machine_id="vision_system_03",
            context={
                "batch_id": "B20260521_001",
                "defect_type": "surface_scratch",
                "defect_count": 17,
                "baseline": 2.0,
            },
        )

    def generate_oqs_parameter_drift(self) -> EventData:
        """Quality parameter drifting."""
        return self._create_event(
            event_type=EventType.QUALITY,
            signal_name="oqs_parameter",
            signal_value=95.2,  # target 98.0 +/- 2.0
            confidence=0.88,
            machine_id="qms_sensor_04",
            context={
                "parameter_name": "dimension_tolerance",
                "target": 98.0,
                "tolerance": 2.0,
                "trend": "declining",
            },
        )

    # ===== MAINTENANCE EVENT GENERATORS =====
    def generate_vibration_anomaly(self) -> EventData:
        """Bearing vibration above threshold."""
        return self._create_event(
            event_type=EventType.MAINTENANCE,
            signal_name="vibration_anomaly",
            signal_value=7.5,  # mm/s (normal < 4.5)
            confidence=0.87,
            machine_id="pump_motor_05",
            context={
                "sensor_id": "vibration_sensor_05a",
                "frequency_hz": 2400,  # bearing defect frequency
                "baseline": 2.3,
                "trend": "escalating",
            },
        )

    def generate_temperature_trend(self) -> EventData:
        """Component temperature rising."""
        return self._create_event(
            event_type=EventType.MAINTENANCE,
            signal_name="temperature_trend",
            signal_value=68.5,  # celsius (normal < 55)
            confidence=0.85,
            machine_id="hydraulic_unit_06",
            context={
                "component": "hydraulic_pump",
                "baseline": 48.0,
                "rate_per_hour": 2.1,
                "estimated_failure_hours": 48,
            },
        )

    # ===== PRODUCTION EVENT GENERATORS =====
    def generate_order_at_risk(self) -> EventData:
        """Production order falling behind schedule."""
        return self._create_event(
            event_type=EventType.PRODUCTION,
            signal_name="order_at_risk",
            signal_value=0.72,  # completion percentage
            confidence=0.83,
            machine_id="line_controller_07",
            context={
                "order_id": "ORD_20260521_042",
                "deadline": "2026-05-22T14:00:00Z",
                "current_progress_pct": 72,
                "required_progress_pct": 85,
                "time_remaining_hours": 16,
            },
        )

    def generate_throughput_degradation(self) -> EventData:
        """Line throughput lower than baseline."""
        return self._create_event(
            event_type=EventType.PRODUCTION,
            signal_name="throughput_trend",
            signal_value=78.5,  # units/hour
            confidence=0.81,
            machine_id="line_controller_07",
            context={
                "baseline_uph": 95.0,
                "current_uph": 78.5,
                "degradation_pct": 17.4,
                "duration_minutes": 45,
            },
        )

    # ===== ENERGY EVENT GENERATORS =====
    def generate_peak_pricing_window(self) -> EventData:
        """High-cost energy pricing window."""
        return self._create_event(
            event_type=EventType.ENERGY,
            signal_name="peak_pricing_window",
            signal_value=0.45,  # $/kWh (normal 0.12)
            confidence=0.99,
            machine_id="energy_mgmt_system_08",
            context={
                "pricing_tier": "peak",
                "window_start": "2026-05-22T14:00:00Z",
                "window_end": "2026-05-22T20:00:00Z",
                "estimated_cost_delta": 3500,
                "flexible_load_available": 150,
            },
        )

    # ===== SCENARIO GENERATORS (multi-event) =====
    async def generate_scenario_1_safety_quality(self) -> List[EventData]:
        """
        Scenario 1: Worker zone breach + simultaneous quality defect spike.
        Tests: Safety prioritization, multi-event coordination.
        """
        events = [
            self.generate_zone_intrusion(),  # T+0s - Safety alert
            self.generate_defect_detection(),  # T+0.5s - Quality alert (same instant)
        ]
        return events

    async def generate_scenario_2_maintenance_production(self) -> List[EventData]:
        """
        Scenario 2: Bearing degradation + order falling behind.
        Tests: Maintenance vs production priority, recovery planning.
        """
        events = [
            self.generate_vibration_anomaly(),  # T+0s - Maintenance alert
            self.generate_order_at_risk(),  # T+1s - Production alert
        ]
        return events

    async def generate_scenario_3_multi_event_chaos(self) -> List[EventData]:
        """
        Scenario 3: Everything at once - safety + quality + maintenance + production + energy.
        Tests: Full orchestration, complex conflict resolution.
        """
        events = [
            self.generate_zone_intrusion(),  # T+0s - Critical safety
            self.generate_defect_detection(),  # T+0.5s - High quality impact
            self.generate_vibration_anomaly(),  # T+1s - Maintenance concern
            self.generate_order_at_risk(),  # T+1.5s - Production risk
            self.generate_peak_pricing_window(),  # T+2s - Cost optimization
        ]
        return events

    async def generate_scenario_4_estop_cascade(self) -> List[EventData]:
        """
        Scenario 4: E-stop + cascading effects.
        Tests: Emergency response, immediate action, notifications.
        """
        events = [
            self.generate_estop_signal(),  # T+0s - Emergency
            self.generate_order_at_risk(),  # T+0.5s - Impact on production
            self.generate_temperature_trend(),  # T+1s - Equipment stress
        ]
        return events

    async def generate_scenario_5_maintenance_chain(self) -> List[EventData]:
        """
        Scenario 5: Maintenance escalation - from anomaly to critical.
        Tests: Escalation logic, maintenance priority, window planning.
        """
        events = [
            self.generate_vibration_anomaly(),  # T+0s - Vibration detected
            self.generate_temperature_trend(),  # T+0.5s - Temperature also rising
        ]
        return events

    async def generate_scenario_by_name(self, scenario_name: str) -> List[EventData]:
        """Generate events for named scenario."""
        scenario_map = {
            "safety_quality": self.generate_scenario_1_safety_quality,
            "maintenance_production": self.generate_scenario_2_maintenance_production,
            "multi_event": self.generate_scenario_3_multi_event_chaos,
            "estop": self.generate_scenario_4_estop_cascade,
            "maintenance_chain": self.generate_scenario_5_maintenance_chain,
        }

        generator = scenario_map.get(scenario_name)
        if not generator:
            raise ValueError(f"Unknown scenario: {scenario_name}")

        return await generator()

    async def generate_scenario_by_difficulty(
        self, difficulty: ScenarioDifficulty
    ) -> List[EventData]:
        """Generate scenario matching difficulty level."""
        scenario_map = {
            ScenarioDifficulty.EASY: self.generate_scenario_1_safety_quality,
            ScenarioDifficulty.MEDIUM: self.generate_scenario_2_maintenance_production,
            ScenarioDifficulty.HARD: self.generate_scenario_3_multi_event_chaos,
        }

        generator = scenario_map.get(difficulty)
        if not generator:
            raise ValueError(f"Unknown difficulty: {difficulty}")

        return await generator()

    async def stream_events(
        self, events: List[EventData], interval_ms: int = 500
    ) -> AsyncGenerator[EventData, None]:
        """
        Stream events with delay between them (simulates real-time arrival).
        Useful for dashboard real-time updates.
        """
        for event in events:
            yield event
            await asyncio.sleep(interval_ms / 1000.0)

    def get_scenario_catalog(self) -> Dict[str, Dict[str, Any]]:
        """Return available scenarios with descriptions."""
        return {
            "safety_quality": {
                "name": "Safety-Quality Collision",
                "description": "Worker zone breach + quality defect spike",
                "difficulty": "easy",
                "event_count": 2,
                "key_decisions": ["prioritize_safety", "contain_batch"],
            },
            "maintenance_production": {
                "name": "Maintenance vs Production Tradeoff",
                "description": "Bearing degradation while order at risk",
                "difficulty": "medium",
                "event_count": 2,
                "key_decisions": ["schedule_maintenance", "propose_recovery"],
            },
            "multi_event": {
                "name": "Multi-Event Chaos",
                "description": "Safety + Quality + Maintenance + Production + Energy",
                "difficulty": "hard",
                "event_count": 5,
                "key_decisions": [
                    "stop_line",
                    "contain_batch",
                    "schedule_maintenance",
                    "propose_recovery",
                    "shift_load",
                ],
            },
            "estop": {
                "name": "E-Stop Emergency",
                "description": "Emergency stop + cascading effects",
                "difficulty": "easy",
                "event_count": 3,
                "key_decisions": ["acknowledge_estop", "manage_cascade"],
            },
            "maintenance_chain": {
                "name": "Maintenance Escalation Chain",
                "description": "Multiple maintenance signals escalating",
                "difficulty": "medium",
                "event_count": 2,
                "key_decisions": ["schedule_maintenance", "escalate_critical"],
            },
        }
