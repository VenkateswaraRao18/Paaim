"""
PAAIM normalization layer — turns arbitrary source data into canonical readings.

AI-assisted onboarding, deterministic runtime:
    auto_map()  builds a mapping once (tiers 1-3 free, tier-4 LLM only for leftovers)
    apply()     runs the mapping forever with zero AI

Both take a `factory_id`. There is no module-level SIGNAL_VOCAB, and no
import-time `get_vocabulary_store()` call: this package used to load one plant's
vocabulary as a side effect of being imported, and mutate it in place so that
every consumer picked it up without changing a line. Elegant for one tenant, and
it made a second one a silent data-corruption bug rather than a feature request.

A vocabulary is fetched per factory (`vocab_for`) and passed to whatever resolves
against it.

See vocabulary.py (per-tenant packs), resolver.py (tiers), normalizer.py (runtime).
"""

from paaim.normalization.schema import CanonicalReading, TRANSFORMS
from paaim.normalization.vocabulary import (
    STARTER_PACKS, VocabularyStore, direction_for, get_vocabulary_store, vocab_for,
)
from paaim.normalization.mapping import FieldMapping, SourceMapping, get_mapping_store
from paaim.normalization.resolver import resolve_field
from paaim.normalization.normalizer import auto_map, apply

__all__ = [
    "CanonicalReading", "TRANSFORMS",
    "STARTER_PACKS", "VocabularyStore", "get_vocabulary_store", "vocab_for", "direction_for",
    "FieldMapping", "SourceMapping", "get_mapping_store",
    "resolve_field", "auto_map", "apply",
]
