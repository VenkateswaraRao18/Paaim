"""
Tier 4 — LLM-assisted field mapping (the LAST resort, used ONCE per source).

Only fields that the deterministic tiers (1-3) could not resolve reach here.
Gemini is shown the leftover field names + sample values + sibling context, and
asked to map each to the fixed canonical vocabulary or say "none". The result is
cached in the SourceMapping, so the model is never called again at runtime.

Guarded: if no Gemini key is configured, this returns {} and the field simply
stays unmapped — the deterministic path has ZERO AI dependency.
"""

from __future__ import annotations

import json
import logging
from typing import Dict, Optional

from paaim.normalization.mapping import FieldMapping
from paaim.normalization.schema import SIGNAL_VOCAB

logger = logging.getLogger(__name__)


def _extract_json(text: str) -> Optional[dict]:
    if not text:
        return None
    t = text.strip()
    if t.startswith("```"):
        t = t.split("```", 2)[1] if "```" in t[3:] else t.strip("`")
        t = t[4:].strip() if t.lower().startswith("json") else t.strip()
    start, end = t.find("{"), t.rfind("}")
    if start == -1 or end == -1:
        return None
    try:
        return json.loads(t[start:end + 1])
    except Exception:
        return None


def llm_resolve_fields(
    unresolved: Dict[str, object],
    sibling_fields: Optional[list] = None,
) -> Dict[str, FieldMapping]:
    """Resolve leftover fields with Gemini. Returns {raw_field: FieldMapping} for
    confidently-mapped fields only. Empty dict if Gemini is unavailable."""
    if not unresolved:
        return {}

    try:
        from paaim.agents.base import _get_gemini
        client, available = _get_gemini()
    except Exception:
        available, client = False, None
    if not (available and client):
        logger.info("Tier-4 skipped — Gemini not configured; %d field(s) left unmapped", len(unresolved))
        return {}

    vocab = list(SIGNAL_VOCAB.keys())
    prompt = f"""You map raw industrial sensor field names to a FIXED canonical vocabulary.

Canonical signals (choose EXACTLY one of these, or "none" if no good match):
{vocab}

For each raw field below you are given a sample value. Decide the best canonical
signal. If a field is a flag/id/status/unrelated value, use "none".

Raw fields (name: sample_value):
{json.dumps(unresolved, default=str)}

Other fields present on this source (context): {sibling_fields or []}

Return STRICT JSON only, mapping each raw field to an object:
{{"<raw_field>": {{"signal": "<canonical or none>", "confidence": 0.0-1.0}}}}
JSON:"""

    try:
        resp = client.generate_content(prompt)
        data = _extract_json(resp.text or "")
    except Exception as e:
        logger.warning("Tier-4 LLM mapping failed: %s", e)
        return {}
    if not isinstance(data, dict):
        return {}

    out: Dict[str, FieldMapping] = {}
    for raw, info in data.items():
        if raw not in unresolved or not isinstance(info, dict):
            continue
        signal = str(info.get("signal", "none"))
        conf = float(info.get("confidence", 0) or 0)
        if signal in SIGNAL_VOCAB and conf >= 0.5:
            meta = SIGNAL_VOCAB[signal]
            out[raw] = FieldMapping(
                raw=raw, signal=signal, unit=meta.get("unit", ""),
                resolved_by="llm", confidence=round(conf, 3),
            )
    logger.info("Tier-4 LLM resolved %d/%d leftover field(s)", len(out), len(unresolved))
    return out
