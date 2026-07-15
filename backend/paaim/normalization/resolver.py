"""
Tiered field resolver — runs ONCE at onboarding to build a SourceMapping.

Cost-ordered, cheapest first. The deterministic tiers (1-3) resolve the majority
of fields for $0. Only leftovers reach the LLM tier (4), and only once.

    Tier 1  STANDARDS   — OPC-UA / MTConnect companion-spec semantics   ($0)
    Tier 2  DICTIONARY  — known per-vendor tag maps                      ($0)
    Tier 3  HEURISTICS  — fuzzy name match + unit inference              ($0)
    Tier 4  LLM         — only unresolved fields, once (see llm_mapper)  (cents)

This file implements tiers 2 & 3 (and the tier-1 hook). Tier 4 is optional and
lives in llm_mapper.py so the deterministic path has zero AI dependency.
"""

from __future__ import annotations

import difflib
import re
from typing import Dict, List, Optional

from paaim.normalization.mapping import FieldMapping

HEURISTIC_THRESHOLD = 0.72


def _tokens(s: str) -> List[str]:
    """Break a field name into normalised tokens: 'MTR03_TORQUE' -> ['mtr','torque']."""
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", s)      # camelCase split
    s = re.sub(r"[^a-zA-Z0-9]", " ", s)                 # separators -> space
    toks = [t.lower() for t in s.split() if t]
    return [t for t in toks if not t.isdigit()]          # drop pure-digit tokens (MTR03 -> mtr)


def _score(raw_field: str, synonyms: List[str]) -> float:
    """Best match score of a raw field against a signal's synonyms."""
    raw_tokens = set(_tokens(raw_field))
    raw_join = "".join(sorted(raw_tokens))
    best = 0.0
    for syn in synonyms:
        syn_tokens = set(_tokens(syn))
        # token overlap is the strongest signal
        overlap = raw_tokens & syn_tokens
        if overlap:
            best = max(best, 0.9 + 0.1 * (len(overlap) / max(len(syn_tokens), 1)))
        # fuzzy character ratio as a fallback
        ratio = difflib.SequenceMatcher(None, raw_join, "".join(sorted(syn_tokens))).ratio()
        best = max(best, ratio)
    return min(best, 1.0)


def resolve_field(
    raw_field: str,
    vocab: Dict[str, dict],
    sample_value=None,
    unit_hint: Optional[str] = None,
    dictionary: Optional[Dict[str, str]] = None,
) -> Optional[FieldMapping]:
    """
    Resolve ONE raw field to a canonical FieldMapping, or None if unresolved.

    `vocab` is the factory's own vocabulary and is required. It used to be the
    module-level SIGNAL_VOCAB, which meant this resolver silently answered for
    whichever tenant had configured theirs most recently.
    """
    # ── Tier 2: dictionary (exact known tag map for this vendor/source) ──
    if dictionary and raw_field in dictionary:
        signal = dictionary[raw_field]
        meta = vocab.get(signal, {})
        return FieldMapping(raw=raw_field, signal=signal, unit=meta.get("unit", ""),
                            resolved_by="dictionary", confidence=1.0)

    # ── Tier 3: heuristic fuzzy match against the vocabulary ──
    best_signal, best_score = None, 0.0
    for signal, meta in vocab.items():
        score = _score(raw_field, [signal] + meta.get("synonyms", []))
        if score > best_score:
            best_signal, best_score = signal, score

    if best_signal and best_score >= HEURISTIC_THRESHOLD:
        meta = vocab[best_signal]
        # Units are reconciled centrally (paaim.normalization.units), against the
        # unit the SOURCE declares — not a hint guessed here. This tier used to
        # carry its own copy of the conversion table, which drifted the moment
        # the real one gained °F: a mapping resolved here would claim identity
        # while the same pair converted correctly one function away.
        return FieldMapping(raw=raw_field, signal=best_signal, unit=meta.get("unit", ""),
                            transform="identity", resolved_by="heuristic",
                            confidence=round(best_score, 3))

    # Unresolved → caller may escalate to Tier 4 (LLM) or leave unmapped
    return None
