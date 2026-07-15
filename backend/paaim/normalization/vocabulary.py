"""
The plant's signal vocabulary — configuration, not code.

`SIGNAL_VOCAB` shipped as a hardcoded dict of eleven signals: torque, tool_wear,
coolant_pressure, rotational_speed… That is not "manufacturing", it is CNC
machining — the schema of one public dataset. An injection moulder (melt temp,
clamp force), a press shop (tonnage, die temp) or a filling line (fill weight,
seal temp) shares almost none of it, so every new customer meant editing Python
in six modules. That is a bespoke build with a config screen, not a product.

So the vocabulary lives in a store the plant owns. Starter packs are seed data
they edit, not code they wait on.

Each entry carries everything the runtime needs to reason about a signal:

    unit             what it is measured in
    event_type       which specialist owns it (routing)
    higher_is_worse  which direction is a fault  ← see below
    synonyms         raw tag fragments the resolver matches on

`higher_is_worse` belongs here, not on the feed. Direction is a property of the
signal — vibration fails high, hydraulic pressure fails low — and asking the
source for it meant a plant whose historian sends bare values had no direction
at all, so an idle machine reading several sigma low was judged a critical
fault. It is the signal's own truth; store it with the signal.

## One vocabulary per factory

This store was a singleton mirrored into a module-level `SIGNAL_VOCAB` dict, and
its own docstring explained the trick: "every consumer already holds a reference
to that one dict, so the store mutates it in place". That is a fine way to reach
six modules without touching them, and it makes two tenants impossible — the
moment a dairy adopts the food pack, the machine shop sharing the process loses
its CNC vocabulary, in memory, instantly, with no error anywhere.

So vocabularies are now held per factory and passed explicitly. Every function
that resolves a signal takes the vocabulary it is resolving against, because a
signal name only means anything relative to one plant's vocabulary — and a
parameter is checkable where an ambient global is not.
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Where each factory's vocabulary is persisted. One file per tenant.
VOCAB_DIR = os.getenv("PAAIM_VOCAB_DIR", "tenant_state")


def _sig(unit: str, event_type: str, higher_is_worse: bool, synonyms: List[str],
         description: str = "") -> Dict[str, Any]:
    return {
        "unit": unit,
        "event_type": event_type,
        "higher_is_worse": higher_is_worse,
        "synonyms": synonyms,
        "description": description,
    }


# ── Starter packs ─────────────────────────────────────────────────────────────
# Seed data a plant picks once and then edits. Adding an industry is a pack,
# not a release.
STARTER_PACKS: Dict[str, Dict[str, Any]] = {
    "cnc_machining": {
        "label": "CNC machining / milling",
        "description": "Spindle-driven metal cutting. Matches the AI4I 2020 schema.",
        "signals": {
            "torque":              _sig("Nm", "maintenance", True, ["trq", "torque", "mtr_torque", "spindle_torque", "motor_torque"], "Spindle/motor torque"),
            "process_temperature": _sig("K", "maintenance", True, ["proc_temp", "process_temp", "process_t", "process_temperature"], "Temperature at the work zone"),
            "air_temperature":     _sig("K", "maintenance", True, ["air_temp", "ambient_temp", "air_temperature", "ambient"], "Ambient air temperature"),
            "temperature":         _sig("C", "maintenance", True, ["temp", "temperature", "temp_c", "tempc"], "General temperature"),
            "rotational_speed":    _sig("rpm", "maintenance", True, ["rpm", "speed", "rot_speed", "spindle_speed", "rotational_speed"], "Spindle speed"),
            "tool_wear":           _sig("min", "maintenance", True, ["wear", "tool_life", "tool_wear", "toolwear"], "Cutting-tool usage since last change"),
            "vibration":           _sig("mm/s", "maintenance", True, ["vib", "vibration", "vibration_rms", "vibr"], "Vibration RMS — bearing/imbalance"),
            "pressure":            _sig("bar", "maintenance", False, ["press", "pressure", "hyd_pressure", "hydraulic_pressure"], "Hydraulic pressure — low is the fault"),
            "coolant_pressure":    _sig("bar", "maintenance", False, ["coolant_press", "coolant_pressure", "coolant"], "Coolant delivery pressure"),
            "power":               _sig("kW", "energy", True, ["kw", "power", "power_draw", "load_kw", "power_kw"], "Instantaneous power draw"),
            "energy":              _sig("kWh", "energy", True, ["kwh", "energy", "consumption", "energy_kwh"], "Energy consumed"),
        },
    },
    "injection_moulding": {
        "label": "Injection moulding",
        "description": "Plastic moulding presses.",
        "signals": {
            "melt_temperature":    _sig("C", "maintenance", True, ["melt_temp", "barrel_temp", "melt_t", "nozzle_temp"], "Barrel/nozzle melt temperature"),
            "injection_pressure":  _sig("bar", "maintenance", True, ["inj_press", "injection_pressure", "inj_p"], "Peak injection pressure"),
            "clamp_force":         _sig("kN", "maintenance", True, ["clamp", "clamp_force", "tonnage"], "Clamping force"),
            "cycle_time":          _sig("s", "production", True, ["cycle", "cycle_time", "ct"], "Time per shot — rising means drift"),
            "cushion":             _sig("mm", "quality", False, ["cushion", "shot_cushion"], "Shot cushion — low risks short shots"),
            "mould_temperature":   _sig("C", "maintenance", True, ["mould_temp", "mold_temp", "tool_temp"], "Mould surface temperature"),
            "vibration":           _sig("mm/s", "maintenance", True, ["vib", "vibration"], "Machine vibration"),
            "power":               _sig("kW", "energy", True, ["kw", "power", "power_draw"], "Power draw"),
        },
    },
    "food_processing": {
        "label": "Food processing / filling",
        "description": "Mixers, fillers, packaging lines. Safety-critical signals are quality-routed.",
        "signals": {
            "product_temperature": _sig("C", "quality", True, ["prod_temp", "product_temp", "pasteur_temp", "cook_temp"], "Product temperature — a CCP on pasteurisation"),
            "fill_weight":         _sig("g", "quality", True, ["fill_wt", "fill_weight", "net_weight", "checkweight"], "Filled net weight — under is a legal problem, over is giveaway"),
            "fill_volume":         _sig("ml", "quality", True, ["fill_vol", "fill_volume"], "Filled volume"),
            "seal_temperature":    _sig("C", "quality", False, ["seal_temp", "sealer_temp", "jaw_temp"], "Seal jaw temperature — low means weak seals"),
            "viscosity":           _sig("cP", "quality", True, ["visc", "viscosity"], "Product viscosity"),
            "ph":                  _sig("pH", "quality", True, ["ph", "acidity"], "Product pH — a CCP for acidified foods"),
            "line_speed":          _sig("units/min", "production", False, ["line_speed", "throughput", "rate"], "Line throughput"),
            "motor_current":       _sig("A", "maintenance", True, ["amps", "current", "motor_current", "load_amps"], "Motor current — mixer load"),
            "vibration":           _sig("mm/s", "maintenance", True, ["vib", "vibration"], "Vibration — bearing wear"),
            "pressure":            _sig("bar", "maintenance", False, ["press", "pressure"], "Line/hydraulic pressure"),
            "temperature":         _sig("C", "maintenance", True, ["temp", "temperature"], "Equipment temperature"),
            "power":               _sig("kW", "energy", True, ["kw", "power"], "Power draw"),
        },
    },
    "press_stamping": {
        "label": "Press / stamping",
        "description": "Metal forming presses.",
        "signals": {
            "tonnage":             _sig("t", "maintenance", True, ["tonnage", "force", "press_force"], "Press tonnage per stroke"),
            "die_temperature":     _sig("C", "maintenance", True, ["die_temp", "tool_temp"], "Die temperature"),
            "shut_height":         _sig("mm", "quality", True, ["shut_height", "shutheight"], "Shut height — drift means dimensional loss"),
            "stroke_rate":         _sig("spm", "production", False, ["spm", "strokes", "stroke_rate"], "Strokes per minute"),
            "vibration":           _sig("mm/s", "maintenance", True, ["vib", "vibration"], "Vibration"),
            "power":               _sig("kW", "energy", True, ["kw", "power"], "Power draw"),
        },
    },
}

DEFAULT_PACK = "cnc_machining"


def _safe_id(factory_id: str) -> str:
    """A factory id is a filename here, so it must not be able to escape the dir."""
    s = re.sub(r"[^A-Za-z0-9_.-]", "_", (factory_id or "").strip())
    if not s or s in (".", ".."):
        raise ValueError(f"Unusable factory id: {factory_id!r}")
    return s


class VocabularyStore:
    """
    One factory's vocabulary, JSON-backed and owned by that factory alone.

    Holds its own dict. It used to be handed the global SIGNAL_VOCAB and mutate
    it in place, which is what made a second tenant impossible.
    """

    def __init__(self, factory_id: str, dir_: str = VOCAB_DIR):
        self.factory_id = factory_id
        os.makedirs(dir_, exist_ok=True)
        self.path = os.path.join(dir_, f"vocabulary_{_safe_id(factory_id)}.json")
        self._live: Dict[str, dict] = {}
        self.pack_id: str = DEFAULT_PACK
        self._load()

    # ── persistence ──────────────────────────────────────────────────────────
    def _load(self) -> None:
        try:
            with open(self.path) as f:
                data = json.load(f)
            self.pack_id = data.get("pack_id", DEFAULT_PACK)
            self._apply(data.get("signals") or {})
            logger.info("[%s] loaded %d signals from its vocabulary (%s)",
                        self.factory_id, len(self._live), self.pack_id)
            return
        except FileNotFoundError:
            pass
        except Exception as e:
            logger.warning("Could not load vocabulary, falling back to the default pack: %s", e)
        self.apply_pack(DEFAULT_PACK, persist=False)

    def _save(self) -> None:
        try:
            with open(self.path, "w") as f:
                json.dump({"pack_id": self.pack_id, "signals": self._live}, f, indent=2)
        except Exception as e:
            logger.error("Could not save vocabulary: %s", e)

    def _apply(self, signals: Dict[str, dict]) -> None:
        self._live.clear()
        self._live.update(signals)

    # ── operations ───────────────────────────────────────────────────────────
    def apply_pack(self, pack_id: str, persist: bool = True) -> Dict[str, dict]:
        pack = STARTER_PACKS.get(pack_id)
        if not pack:
            raise KeyError(f"No such starter pack: {pack_id}")
        self.pack_id = pack_id
        self._apply(json.loads(json.dumps(pack["signals"])))  # deep copy
        if persist:
            self._save()
        return self._live

    def upsert(self, signal: str, entry: Dict[str, Any]) -> Dict[str, dict]:
        """Add or edit one signal. This is how a plant extends its own vocabulary."""
        self._live[signal] = {
            "unit": entry.get("unit", ""),
            "event_type": entry.get("event_type", "maintenance"),
            "higher_is_worse": bool(entry.get("higher_is_worse", True)),
            "synonyms": entry.get("synonyms", []) or [],
            "description": entry.get("description", ""),
        }
        self._save()
        return self._live

    def remove(self, signal: str) -> bool:
        if signal in self._live:
            del self._live[signal]
            self._save()
            return True
        return False

    def as_dict(self) -> Dict[str, dict]:
        return self._live


class VocabularyRegistry:
    """One store per factory, created on first use."""

    def __init__(self) -> None:
        self._stores: Dict[str, VocabularyStore] = {}

    def for_factory(self, factory_id: str) -> VocabularyStore:
        if not factory_id:
            raise ValueError(
                "A vocabulary belongs to a factory — pass the tenant's id. "
                "There is deliberately no global vocabulary to fall back on."
            )
        if factory_id not in self._stores:
            self._stores[factory_id] = VocabularyStore(factory_id)
        return self._stores[factory_id]

    def drop(self, factory_id: str) -> None:
        self._stores.pop(factory_id, None)


_registry: Optional[VocabularyRegistry] = None


def get_registry() -> VocabularyRegistry:
    global _registry
    if _registry is None:
        _registry = VocabularyRegistry()
    return _registry


def get_vocabulary_store(factory_id: str) -> VocabularyStore:
    """This factory's vocabulary store. `factory_id` is required, deliberately."""
    return get_registry().for_factory(factory_id)


def vocab_for(factory_id: str) -> Dict[str, dict]:
    """This factory's signals — the dict every resolver should be handed."""
    return get_registry().for_factory(factory_id).as_dict()


def direction_for(signal: str, factory_id: str) -> Optional[bool]:
    """
    Is a HIGH reading the fault for this signal, in THIS factory's vocabulary?

    Scoped per factory because direction is not universal: `pressure` fails low
    on a dairy's hold tube and high on a vessel, and two tenants are entitled to
    disagree about their own signals.
    """
    entry = vocab_for(factory_id).get(signal)
    return entry.get("higher_is_worse") if entry else None
