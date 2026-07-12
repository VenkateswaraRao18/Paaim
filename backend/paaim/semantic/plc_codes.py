"""
PLC / machine error-code catalogue — the "semantic disconnect" lookup.

A junior operator sees `Error 0x4F3` and is stuck. This maps cryptic codes to
what they actually mean, which machine/signal they relate to, and the PAAIM
failure mode — so the rest of the pipeline can act on it.

In a real plant this table is the OEM/PLC documentation (often a 15-year-old PDF
in someone's head). Here it's a representative catalogue tied to the seeded
machines and the AI4I failure modes.
"""

from typing import Dict, List, Optional

# code → meaning. event_type/signal_name align with PAAIM's pipeline vocabulary.
PLC_CODES: Dict[str, Dict] = {
    "0x4F3": {
        "machine_id": "cnc_mill_01",
        "event_type": "maintenance",
        "signal_name": "heat_dissipation_loss",
        "plain_meaning": "Spindle is overheating — coolant is not removing heat fast enough.",
        "severity": "high",
        "raw_register": "TEMP_DELTA < 8.6K @ RPM<1380",
    },
    "E-201": {
        "machine_id": "robot_arm_01",
        "event_type": "maintenance",
        "signal_name": "tool_wear_degradation",
        "plain_meaning": "Cutting tool has reached its wear limit and needs changing.",
        "severity": "high",
        "raw_register": "TOOL_WEAR ≥ 200 min",
    },
    "P-FAIL": {
        "machine_id": "cnc_cluster_03",
        "event_type": "energy",
        "signal_name": "power_envelope_breach",
        "plain_meaning": "Power draw is outside the safe band — drive may be straining or failing.",
        "severity": "high",
        "raw_register": "POWER ∉ [3500,9000] W",
    },
    "VIB-HH": {
        "machine_id": "robot_arm_01",
        "event_type": "maintenance",
        "signal_name": "vibration_anomaly",
        "plain_meaning": "Vibration is very high — likely a worn bearing starting to fail.",
        "severity": "critical",
        "raw_register": "RMS_VELOCITY > 7.1 mm/s",
    },
    "OS-12": {
        "machine_id": "cnc_lathe_01",
        "event_type": "production",
        "signal_name": "mechanical_overstrain",
        "plain_meaning": "The machine is overstrained — load × tool wear past the safe limit.",
        "severity": "high",
        "raw_register": "TOOL_WEAR·TORQUE > 11000 min·Nm",
    },
    "HYD-LO": {
        "machine_id": "press_line_01",
        "event_type": "maintenance",
        "signal_name": "coolant_pressure",
        "plain_meaning": "Hydraulic pressure has dropped — possible leak or pump fault.",
        "severity": "high",
        "raw_register": "PRESSURE < 2.2 bar",
    },
}


def lookup_code(code: str) -> Optional[Dict]:
    """Resolve a cryptic code to its meaning (case-insensitive)."""
    if not code:
        return None
    key = code.strip().upper()
    # tolerate '0X4F3' vs '0x4F3'
    for k, v in PLC_CODES.items():
        if k.upper() == key:
            return {"code": k, **v}
    return None


def list_codes() -> List[Dict]:
    return [{"code": k, **v} for k, v in PLC_CODES.items()]
