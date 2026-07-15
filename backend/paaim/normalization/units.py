"""
Unit reconciliation — does the number mean what the vocabulary thinks it means?

The mapper used to choose a canonical signal purely by name and leave the
transform at `identity`. On a live plant that produced this, silently:

    source:     TT_101  =  64.5  °C           (a warm weld tip)
    vocabulary: process_temperature is in K
    transform:  identity
    result:     "process_temperature = 64.5 K"   → −209 °C, liquid nitrogen

Detection survived, because the watcher compared a raw °C reading against raw
°C limits. The reasoning did not: the agents were handed a weld tip at 64 Kelvin
and asked what to do about it. That is the worst shape a bug can take — every
number plausible, every conclusion wrong, nothing to alert on.

The unit is not decoration. A canonical signal is a name *and* a unit, and a
mapping is only correct if the value is carried into that unit. So resolution
answers three questions, not one: which signal, in what unit, and what has to
happen to the number on the way.

`reconcile` is deliberately conservative. It converts only across pairs it truly
knows, and calls everything else a conflict for a human to settle — guessing at
a unit is how you get the bug above.
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple

# What the mapping concluded about a field's unit.
MATCH = "match"          # source and vocabulary already agree
CONVERTED = "converted"  # they differ, and a known conversion bridges them
CONFLICT = "conflict"    # they differ and nothing bridges them — a human must look
UNKNOWN = "unknown"      # the source never said what unit it publishes

# Plants write the same unit a dozen ways. Fold them onto one token so "°C",
# "degC" and "Celsius" are not three different units.
_ALIASES: Dict[str, str] = {
    "c": "C", "°c": "C", "degc": "C", "deg_c": "C", "celsius": "C", "cel": "C",
    "k": "K", "°k": "K", "degk": "K", "kelvin": "K",
    "f": "F", "°f": "F", "degf": "F", "fahrenheit": "F",
    "bar": "bar", "bars": "bar",
    "psi": "psi", "psig": "psi", "lbf/in2": "psi",
    "kpa": "kPa", "pa": "Pa", "mpa": "MPa",
    "w": "W", "watt": "W", "watts": "W",
    "kw": "kW", "kilowatt": "kW", "kilowatts": "kW",
    "kwh": "kWh", "wh": "Wh",
    "a": "A", "amp": "A", "amps": "A", "ampere": "A",
    "nm": "Nm", "n·m": "Nm", "n-m": "Nm", "newton_metre": "Nm",
    "rpm": "rpm", "r/min": "rpm",
    "mm/s": "mm/s", "mms": "mm/s", "m/s": "m/s",
    "mm": "mm", "m": "m",
    "min": "min", "mins": "min", "minute": "min", "minutes": "min",
    "s": "s", "sec": "s", "secs": "s", "second": "s", "seconds": "s",
    "h": "h", "hr": "h", "hour": "h", "hours": "h",
    "%": "%", "pct": "%", "percent": "%",
    "g": "g", "gram": "g", "grams": "g", "kg": "kg",
    "ml": "ml", "l": "L", "litre": "L", "liter": "L",
    "ph": "pH",
    "cp": "cP", "centipoise": "cP",
    "kn": "kN", "t": "t", "spm": "spm",
    "units/min": "units/min", "upm": "units/min",
}

# (source, target) -> transform name in schema.TRANSFORMS.
# Only pairs whose conversion is exact and monotonic. Anything absent here is a
# conflict on purpose: an approximate guess would reintroduce the original bug
# wearing a lab coat.
_CONVERSIONS: Dict[Tuple[str, str], str] = {
    ("C", "K"): "celsius_to_k",
    ("K", "C"): "kelvin_to_c",
    ("F", "C"): "fahrenheit_to_c",
    ("C", "F"): "celsius_to_f",
    ("F", "K"): "fahrenheit_to_k",
    ("K", "F"): "kelvin_to_f",
    ("W", "kW"): "scale_1000",
    ("kW", "W"): "scale_0_001",
    ("psi", "bar"): "psi_to_bar",
    ("bar", "psi"): "bar_to_psi",
    ("kPa", "bar"): "kpa_to_bar",
    ("bar", "kPa"): "bar_to_kpa",
}


def canonical_unit(unit: Optional[str]) -> str:
    """Fold a source's spelling of a unit onto one token. '' when unrecognised."""
    if not unit:
        return ""
    u = str(unit).strip()
    return _ALIASES.get(u.lower(), u if u in _ALIASES.values() else "")


def reconcile(source_unit: Optional[str], target_unit: Optional[str]) -> Tuple[str, str]:
    """
    How to carry a reading from the source's unit into the vocabulary's.

    Returns (transform_name, status). The transform is always safe to apply:
    on UNKNOWN or CONFLICT it is `identity`, so the number is left exactly as the
    source sent it rather than being mangled by a guess — and the status is what
    tells the operator the mapping needs their eyes.
    """
    su, tu = canonical_unit(source_unit), canonical_unit(target_unit)
    if not su or not tu:
        return "identity", UNKNOWN
    if su == tu:
        return "identity", MATCH
    conv = _CONVERSIONS.get((su, tu))
    if conv:
        return conv, CONVERTED
    return "identity", CONFLICT


def describe(source_unit: Optional[str], target_unit: Optional[str], status: str) -> str:
    """A one-line explanation, for the operator reviewing the mapping."""
    su, tu = source_unit or "?", target_unit or "?"
    if status == MATCH:
        return f"source and signal agree ({tu})"
    if status == CONVERTED:
        return f"converted {su} → {tu}"
    if status == CONFLICT:
        return (f"source sends {su}, signal expects {tu} — no known conversion. "
                f"Pick a signal in {su}, or change this signal's unit in your vocabulary.")
    return f"source did not declare a unit; assuming it is already {tu}"
