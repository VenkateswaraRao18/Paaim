"""
PAAIM normalization layer — turns arbitrary source data into canonical readings.

AI-assisted onboarding, deterministic runtime:
    auto_map()  builds a mapping once (tiers 1-3 free, tier-4 LLM only for leftovers)
    apply()     runs the mapping forever with zero AI

See schema.py (canonical vocabulary), resolver.py (tiers), normalizer.py (runtime).
"""

from paaim.normalization.schema import CanonicalReading, SIGNAL_VOCAB, TRANSFORMS
from paaim.normalization.mapping import FieldMapping, SourceMapping, get_mapping_store
from paaim.normalization.resolver import resolve_field
from paaim.normalization.normalizer import auto_map, apply

__all__ = [
    "CanonicalReading", "SIGNAL_VOCAB", "TRANSFORMS",
    "FieldMapping", "SourceMapping", "get_mapping_store",
    "resolve_field", "auto_map", "apply",
]
