"""
AI4I 2020 Predictive Maintenance Dataset → PAAIM EventData adapter.

Source : UCI Machine Learning Repository, dataset #601
         "AI4I 2020 Predictive Maintenance Dataset" (S. Matzka, 2020)
         https://archive.ics.uci.edu/dataset/601/ai4i+2020+predictive+maintenance+dataset
License: CC BY 4.0  (free for research/education)

The dataset has 10,000 rows. Each row is one snapshot of a milling machine
with these columns (units are stripped/normalised by `_norm_key`):

    UDI, Product ID, Type, Air temperature [K], Process temperature [K],
    Rotational speed [rpm], Torque [Nm], Tool wear [min],
    Machine failure, TWF, HDF, PWF, OSF, RNF

It encodes 5 independent failure modes, each with documented physics. We use
those exact thresholds to derive PAAIM signals + a graded confidence so the
events are faithful to the research, not arbitrary:

  TWF  Tool Wear Failure       tool wear in 200–240 min          → maintenance
  HDF  Heat Dissipation        (proc−air) < 8.6 K & speed<1380   → maintenance
  PWF  Power Failure           power = torque·ω  ∉ [3500, 9000] W → energy
  OSF  Overstrain Failure      tool_wear·torque > type threshold  → production
  RNF  Random Failure          0.1% random                        → quality

The machine `Type` (L/M/H quality variant) is mapped onto the seeded factory
machines so events flow through the Factory Context Layer too.
"""

from __future__ import annotations

import math
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from paaim.models import EventData, EventType


# ── Type → seeded machine mapping (ties dataset into Factory Context Layer) ──

TYPE_TO_MACHINE = {
    "L": "cnc_lathe_01",   # low-grade variant
    "M": "cnc_mill_01",    # medium-grade variant
    "H": "robot_arm_01",   # high-grade variant (critical, Ford work order)
}

# Overstrain (OSF) tool_wear·torque thresholds per the Matzka 2020 paper.
OSF_THRESHOLD = {"L": 11000, "M": 12000, "H": 13000}


def _norm_key(key: str) -> str:
    """'Air temperature [K]' -> 'air_temperature'."""
    key = re.sub(r"\[.*?\]", "", key)          # drop units in brackets
    key = key.strip().lower()
    key = re.sub(r"[^a-z0-9]+", "_", key)
    return key.strip("_")


def _f(row: Dict[str, str], *names: str, default: float = 0.0) -> float:
    """Fetch the first matching normalised key as float."""
    for n in names:
        if n in row and row[n] not in ("", None):
            try:
                return float(row[n])
            except (TypeError, ValueError):
                continue
    return default


def _flag(row: Dict[str, str], name: str) -> bool:
    val = row.get(name, "0")
    return str(val).strip() in ("1", "1.0", "true", "True", "yes")


def normalise_row(raw: Dict[str, str]) -> Dict[str, str]:
    """Normalise column names so the adapter is robust to header variants."""
    return {_norm_key(k): v for k, v in raw.items()}


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def row_to_events(
    raw_row: Dict[str, str],
    factory_id: str = "factory_001",
    timestamp: Optional[datetime] = None,
    warn_only: bool = True,
) -> List[EventData]:
    """
    Convert one AI4I row into zero or more PAAIM events.

    A healthy machine produces no events (PAAIM reacts to anomalies, not every
    reading). An event is emitted when a failure flag is set OR a signal crosses
    its documented *warning* band (approaching failure). `signal_value` is the
    raw physical reading; `confidence` grades how far into the danger zone it is.

    Set warn_only=False to emit only on actual labelled failures.
    """
    row = normalise_row(raw_row)
    ts = timestamp or datetime.utcnow()

    mtype = str(row.get("type", "M")).strip().upper() or "M"
    machine_id = TYPE_TO_MACHINE.get(mtype, "cnc_mill_01")
    product_id = row.get("product_id") or row.get("productid") or f"{mtype}-?"

    air = _f(row, "air_temperature")
    proc = _f(row, "process_temperature")
    speed = _f(row, "rotational_speed")
    torque = _f(row, "torque")
    wear = _f(row, "tool_wear")
    udi = row.get("udi") or row.get("uid") or "?"

    base_ctx: Dict[str, Any] = {
        "dataset": "ai4i2020",
        "udi": udi,
        "product_id": product_id,
        "machine_variant": mtype,
        "air_temperature_k": air,
        "process_temperature_k": proc,
        "rotational_speed_rpm": speed,
        "torque_nm": torque,
        "tool_wear_min": wear,
    }

    events: List[EventData] = []

    def emit(event_type: EventType, signal_name: str, signal_value: float,
             confidence: float, extra: Dict[str, Any]) -> None:
        events.append(EventData(
            event_type=event_type,
            source_agent="dataset_ingestor",
            factory_id=factory_id,
            machine_id=machine_id,
            signal_value=round(signal_value, 3),
            signal_name=signal_name,
            confidence=round(_clamp01(confidence), 3),
            timestamp=ts,
            context={**base_ctx, **extra, "failure_mode": signal_name},
        ))

    # ── TWF — Tool Wear Failure (fails 200–240 min) ─────────────────────────
    twf = _flag(row, "twf")
    if twf or (warn_only and wear >= 180):
        # 180 → warning, 200 → action, 240 → certain failure
        conf = 0.95 if twf else _clamp01((wear - 180) / (240 - 180)) * 0.6 + 0.3
        emit(EventType.MAINTENANCE, "tool_wear_degradation", wear, conf,
             {"labelled_failure": twf, "threshold_min": 200})

    # ── HDF — Heat Dissipation Failure ((proc−air)<8.6 & speed<1380) ────────
    hdf = _flag(row, "hdf")
    temp_diff = proc - air
    if hdf or (warn_only and temp_diff < 9.0 and speed < 1450 and air > 0):
        # closer to (8.6, 1380) => higher confidence
        margin = _clamp01((9.0 - temp_diff) / 9.0) * 0.5 + _clamp01((1450 - speed) / 1450) * 0.5
        conf = 0.96 if hdf else _clamp01(margin) * 0.55 + 0.3
        emit(EventType.MAINTENANCE, "heat_dissipation_loss", temp_diff, conf,
             {"labelled_failure": hdf, "temp_diff_k": round(temp_diff, 2),
              "speed_rpm": speed, "threshold_temp_diff_k": 8.6})

    # ── PWF — Power Failure (power ∉ [3500, 9000] W) ────────────────────────
    pwf = _flag(row, "pwf")
    omega = speed * 2 * math.pi / 60.0          # rpm → rad/s
    power = torque * omega                       # W
    out_of_band = power < 3500 or power > 9000
    if pwf or (warn_only and (power < 3800 or power > 8700)):
        if power < 3500 or power > 9000:
            conf = 0.94
        else:
            # in the warning margin band
            low = _clamp01((3800 - power) / 300) if power < 3800 else 0.0
            high = _clamp01((power - 8700) / 300) if power > 8700 else 0.0
            conf = max(low, high) * 0.5 + 0.35
        conf = 0.94 if pwf else conf
        emit(EventType.ENERGY, "power_envelope_breach", round(power, 1), conf,
             {"labelled_failure": pwf, "power_w": round(power, 1),
              "band_w": [3500, 9000], "out_of_band": out_of_band})

    # ── OSF — Overstrain Failure (tool_wear·torque > type threshold) ────────
    osf = _flag(row, "osf")
    strain = wear * torque
    osf_limit = OSF_THRESHOLD.get(mtype, 12000)
    if osf or (warn_only and strain > osf_limit * 0.85):
        conf = 0.95 if osf else _clamp01((strain - osf_limit * 0.85) / (osf_limit * 0.15)) * 0.55 + 0.3
        emit(EventType.PRODUCTION, "mechanical_overstrain", round(strain, 1), conf,
             {"labelled_failure": osf, "strain_min_nm": round(strain, 1),
              "threshold_min_nm": osf_limit})

    # ── RNF — Random Failure (0.1%) ─────────────────────────────────────────
    if _flag(row, "rnf"):
        emit(EventType.QUALITY, "unexplained_quality_fault", 1.0, 0.80,
             {"labelled_failure": True, "note": "random failure mode (RNF)"})

    # ── Fallback: machine flagged failed but no specific mode mapped ────────
    if _flag(row, "machine_failure") and not events:
        emit(EventType.QUALITY, "general_machine_failure", 1.0, 0.85,
             {"labelled_failure": True})

    return events


def summarise_mapping() -> Dict[str, Any]:
    """Describe how the adapter maps the dataset — used by the API/docs."""
    return {
        "dataset": "AI4I 2020 Predictive Maintenance Dataset (UCI #601)",
        "rows": 10000,
        "license": "CC BY 4.0",
        "failure_modes": {
            "TWF": {"signal": "tool_wear_degradation", "event_type": "maintenance",
                    "physics": "tool wear 200–240 min"},
            "HDF": {"signal": "heat_dissipation_loss", "event_type": "maintenance",
                    "physics": "(proc−air) < 8.6 K and speed < 1380 rpm"},
            "PWF": {"signal": "power_envelope_breach", "event_type": "energy",
                    "physics": "power = torque·ω outside [3500, 9000] W"},
            "OSF": {"signal": "mechanical_overstrain", "event_type": "production",
                    "physics": "tool_wear·torque > 11000/12000/13000 (L/M/H)"},
            "RNF": {"signal": "unexplained_quality_fault", "event_type": "quality",
                    "physics": "0.1% random"},
        },
        "type_to_machine": TYPE_TO_MACHINE,
    }
