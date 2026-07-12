"""
Normalizer — the runtime hot path (pure code, ZERO AI) + the onboarding builder.

    auto_map(sample)  -> SourceMapping   (onboarding, runs the tiered resolver once)
    apply(mapping, raw) -> [CanonicalReading]   (runtime, O(n) dict lookups)

`apply` is what runs millions of times/sec. It never calls a model — it just
looks each raw field up in the cached mapping and transforms the value.
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from paaim.normalization.mapping import SourceMapping
from paaim.normalization.resolver import resolve_field
from paaim.normalization.schema import SIGNAL_VOCAB, TRANSFORMS, CanonicalReading


def auto_map(
    source_id: str,
    sample_payload: Dict,
    machine_id: str = "unknown",
    machine_id_field: Optional[str] = None,
    dictionary: Optional[Dict[str, str]] = None,
    use_llm: bool = False,
) -> SourceMapping:
    """Build a SourceMapping from ONE sample payload.

    Deterministic tiers (2-3) run first for $0. Anything left over is escalated
    to the Tier-4 LLM ONLY if use_llm=True (and Gemini is configured); otherwise
    it stays in `unmapped` for a human to resolve. Either way, resolution happens
    exactly once — afterwards it's all cached.
    """
    mapping = SourceMapping(
        source_id=source_id,
        machine_id_strategy="field" if machine_id_field else "static",
        machine_id_value=machine_id_field or machine_id,
    )
    leftovers: Dict[str, object] = {}
    for raw_field, value in sample_payload.items():
        if machine_id_field and raw_field == machine_id_field:
            continue
        fm = resolve_field(raw_field, sample_value=value, dictionary=dictionary)
        if fm:
            mapping.fields[raw_field] = fm
        elif isinstance(value, (int, float)):   # only numeric fields matter as signals
            leftovers[raw_field] = value

    # ── Tier 4: LLM, only for what the free tiers couldn't resolve ──
    if leftovers and use_llm:
        from paaim.normalization.llm_mapper import llm_resolve_fields
        resolved = llm_resolve_fields(leftovers, sibling_fields=list(mapping.fields.keys()))
        for raw_field, fm in resolved.items():
            mapping.fields[raw_field] = fm
            leftovers.pop(raw_field, None)

    mapping.unmapped = list(leftovers.keys())
    return mapping


def apply(mapping: SourceMapping, raw_dict: Dict, factory_id: str = "factory_001") -> List[CanonicalReading]:
    """Runtime: turn a raw source dict into canonical readings. No AI. Microseconds."""
    ts = datetime.utcnow().isoformat()
    machine_id = mapping.machine_id_for(raw_dict)
    out: List[CanonicalReading] = []
    for raw_field, value in raw_dict.items():
        fm = mapping.fields.get(raw_field)
        if not fm:
            continue
        try:
            v = TRANSFORMS.get(fm.transform, TRANSFORMS["identity"])(float(value))
        except (TypeError, ValueError):
            continue
        meta = SIGNAL_VOCAB.get(fm.signal, {})
        out.append(CanonicalReading(
            factory_id=factory_id,
            machine_id=machine_id,
            signal_name=fm.signal,
            value=v,
            unit=fm.unit,
            raw_field=raw_field,
            event_type=meta.get("event_type", "maintenance"),
            timestamp=ts,
        ))
    return out
