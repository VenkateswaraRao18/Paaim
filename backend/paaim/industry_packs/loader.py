"""
Industry Pack Loader

Reads YAML pack files and makes them available to the orchestrator,
model router, and cost config. A factory can be bootstrapped from a
pack with one call: apply_pack(factory_id, pack_id, db).
"""

import os
import yaml
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

PACKS_DIR = Path(__file__).parent

_cache: Dict[str, Dict[str, Any]] = {}


def list_packs() -> List[Dict[str, Any]]:
    """Return summary of all available industry packs."""
    packs = []
    for yaml_file in sorted(PACKS_DIR.glob("*.yaml")):
        try:
            data = _load_file(yaml_file)
            packs.append({
                "pack_id": data.get("pack_id", yaml_file.stem),
                "display_name": data.get("display_name", yaml_file.stem),
                "description": data.get("description", "").strip(),
                "version": data.get("version", "1.0"),
                "compliance": data.get("compliance", []),
                "file": yaml_file.name,
            })
        except Exception as e:
            logger.warning(f"Failed to load pack {yaml_file.name}: {e}")
    return packs


def get_pack(pack_id: str) -> Dict[str, Any]:
    """Load and return a full pack by ID."""
    if pack_id in _cache:
        return _cache[pack_id]

    for yaml_file in PACKS_DIR.glob("*.yaml"):
        try:
            data = _load_file(yaml_file)
            if data.get("pack_id") == pack_id:
                _cache[pack_id] = data
                return data
        except Exception:
            continue

    raise KeyError(f"Industry pack not found: {pack_id}")


async def apply_pack(factory_id: str, pack_id: str, db) -> Dict[str, Any]:
    """
    Apply an industry pack to a factory:
    - Updates CostConfigModel with pack cost assumptions
    - Returns the full pack for use in model router / agent config

    Does NOT overwrite existing DB records — upserts cost config only.
    """
    from sqlalchemy import select
    from paaim.models import CostConfigModel
    from datetime import datetime
    import uuid

    pack = get_pack(pack_id)
    costs = pack.get("costs", {})

    # Upsert cost config
    q = select(CostConfigModel).where(CostConfigModel.factory_id == factory_id).limit(1)
    existing = (await db.execute(q)).scalar_one_or_none()

    if existing:
        existing.downtime_cost_per_hour_usd = costs.get("downtime_cost_per_hour_usd", existing.downtime_cost_per_hour_usd)
        existing.scrap_cost_per_unit_usd = costs.get("scrap_cost_per_unit_usd", existing.scrap_cost_per_unit_usd)
        existing.rework_cost_per_unit_usd = costs.get("rework_cost_per_unit_usd", existing.rework_cost_per_unit_usd)
        existing.late_delivery_penalty_per_day_usd = costs.get("late_delivery_penalty_per_day_usd", existing.late_delivery_penalty_per_day_usd)
        existing.labor_cost_per_hour_usd = costs.get("labor_cost_per_hour_usd", existing.labor_cost_per_hour_usd)
        existing.unplanned_failure_multiplier = costs.get("unplanned_failure_multiplier", existing.unplanned_failure_multiplier)
        existing.updated_at = datetime.utcnow()
        db.add(existing)
    else:
        # Only what the pack actually states. The old fallbacks ($5,000/hr,
        # $50/unit …) meant a pack that omitted a cost still produced a
        # confident number indistinguishable from a configured one. A pack is a
        # starting point the plant confirms, not a source of facts about it.
        db.add(CostConfigModel(
            id=f"cc_{uuid.uuid4().hex[:8]}",
            factory_id=factory_id,
            downtime_cost_per_hour_usd=costs.get("downtime_cost_per_hour_usd"),
            scrap_cost_per_unit_usd=costs.get("scrap_cost_per_unit_usd"),
            rework_cost_per_unit_usd=costs.get("rework_cost_per_unit_usd"),
            late_delivery_penalty_per_day_usd=costs.get("late_delivery_penalty_per_day_usd"),
            labor_cost_per_hour_usd=costs.get("labor_cost_per_hour_usd"),
            unplanned_failure_multiplier=costs.get("unplanned_failure_multiplier", 5.0),
            extra_data={"applied_pack": pack_id, "source": "industry pack — typical figures, confirm against your own"},
        ))

    logger.info(f"Applied industry pack '{pack_id}' to factory '{factory_id}'")
    return pack


def _load_file(path: Path) -> Dict[str, Any]:
    with open(path) as f:
        return yaml.safe_load(f)
