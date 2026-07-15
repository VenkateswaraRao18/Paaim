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
from paaim.normalization.schema import TRANSFORMS, CanonicalReading
from paaim.normalization.vocabulary import vocab_for


def _reconcile_units(mapping: SourceMapping, field_units: Optional[Dict[str, str]],
                     vocab: Dict[str, dict]) -> None:
    """
    Settle each field's unit against its signal's, and set the transform.

    Runs after every tier, including the LLM's. Picking a signal by name alone is
    only half a mapping: the resolver chose `process_temperature` for a °C tag —
    a defensible reading of the name, and wrong by 273 degrees until the number
    is carried into Kelvin. Which tier proposed the signal makes no difference to
    that, so this is applied to all of them in one place.
    """
    from paaim.normalization.units import reconcile

    for raw_field, fm in mapping.fields.items():
        target = vocab.get(fm.signal, {}).get("unit", "")
        source_unit = (field_units or {}).get(raw_field, "")
        transform, status = reconcile(source_unit, target)
        fm.source_unit = source_unit
        fm.unit_status = status
        fm.unit = target or fm.unit
        # Only claim the transform when the units actually decided one. A source
        # that declares nothing leaves whatever the resolver set, rather than
        # having a guess overwrite it.
        if status in ("match", "converted"):
            fm.transform = transform


def auto_map(
    source_id: str,
    sample_payload: Dict,
    machine_id: str = "unknown",
    machine_id_field: Optional[str] = None,
    dictionary: Optional[Dict[str, str]] = None,
    use_llm: bool = False,
    field_units: Optional[Dict[str, str]] = None,
    factory_id: str = "",
) -> SourceMapping:
    """Build a SourceMapping from ONE sample payload.

    Deterministic tiers (2-3) run first for $0. Anything left over is escalated
    to the Tier-4 LLM ONLY if use_llm=True (and Gemini is configured); otherwise
    it stays in `unmapped` for a human to resolve. Either way, resolution happens
    exactly once — afterwards it's all cached.

    `field_units` is what the source declared each field's unit to be, where it
    declares anything at all (an SSE feed and most historians do; a bare JSON
    endpoint does not). Without it a mapping can only assume the source already
    speaks the vocabulary's units — an assumption that is invisible when wrong.

    `factory_id` selects the vocabulary being mapped INTO. It is required: a
    signal name means nothing except relative to one plant's vocabulary, and
    resolving against a global one mapped every tenant onto whichever plant had
    configured theirs most recently.
    """
    vocab = vocab_for(factory_id)
    mapping = SourceMapping(
        source_id=source_id,
        machine_id_strategy="field" if machine_id_field else "static",
        machine_id_value=machine_id_field or machine_id,
    )
    leftovers: Dict[str, object] = {}
    for raw_field, value in sample_payload.items():
        if machine_id_field and raw_field == machine_id_field:
            continue
        fm = resolve_field(raw_field, vocab, sample_value=value, dictionary=dictionary)
        if fm:
            mapping.fields[raw_field] = fm
        elif isinstance(value, (int, float)):   # only numeric fields matter as signals
            leftovers[raw_field] = value

    # ── Tier 4: LLM, only for what the free tiers couldn't resolve ──
    if leftovers and use_llm:
        from paaim.normalization.llm_mapper import llm_resolve_fields
        resolved = llm_resolve_fields(leftovers, vocab, sibling_fields=list(mapping.fields.keys()))
        for raw_field, fm in resolved.items():
            mapping.fields[raw_field] = fm
            leftovers.pop(raw_field, None)

    _reconcile_units(mapping, field_units, vocab)
    mapping.unmapped = list(leftovers.keys())
    return mapping


def apply(mapping: SourceMapping, raw_dict: Dict, factory_id: str) -> List[CanonicalReading]:
    """
    Runtime: turn a raw source dict into canonical readings. No AI. Microseconds.

    `factory_id` is required rather than defaulting to "factory_001" — a reading
    that guesses its own tenant is a reading filed under the wrong plant, and the
    vocabulary it is resolved against decides what its signal even means.
    """
    ts = datetime.utcnow().isoformat()
    vocab = vocab_for(factory_id)
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
        meta = vocab.get(fm.signal, {})
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
