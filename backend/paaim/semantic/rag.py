"""
Lightweight RAG — Gemini embeddings + in-memory cosine search.

Used to retrieve semantically-similar maintenance logs ("what fixed this before")
even when the wording differs ("spndl ovrheat" vs "spindle overheating"). Built
once over a small corpus and cached; guarded so that with no embedding service it
returns unavailable and the caller falls back to deterministic token-overlap.

For a bigger corpus this same interface swaps to pgvector/Qdrant — the callers
don't change.
"""

from __future__ import annotations

import logging
import math
import os
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)

_EMBED_MODEL = "models/text-embedding-004"


def embed_texts(texts: List[str]) -> Optional[List[List[float]]]:
    """Embed texts with Gemini. Returns None if no key / library / network."""
    try:
        import google.generativeai as genai
        from paaim.config import settings
        key = getattr(settings, "GEMINI_API_KEY", None) or os.getenv("GEMINI_API_KEY")
        if not key:
            return None
        genai.configure(api_key=key)
        out: List[List[float]] = []
        for t in texts:
            r = genai.embed_content(model=_EMBED_MODEL, content=t or " ")
            out.append(r["embedding"])
        return out
    except Exception as e:
        logger.info("Embeddings unavailable (%s) — RAG will fall back", e)
        return None


def _cosine(a: List[float], b: List[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


class EmbeddingIndex:
    """Tiny in-memory vector index. Build once, search many."""

    def __init__(self) -> None:
        self.vectors: Optional[List[List[float]]] = None
        self.available = False

    def build(self, texts: List[str]) -> None:
        vecs = embed_texts(texts)
        if vecs:
            self.vectors = vecs
            self.available = True
            logger.info("RAG index built over %d docs", len(vecs))

    def search(self, query: str, top_k: int = 3) -> List[Tuple[float, int]]:
        """Return [(similarity, doc_index)] for the top_k most similar docs."""
        if not self.available or not self.vectors:
            return []
        qv = embed_texts([query])
        if not qv:
            return []
        sims = [(_cosine(qv[0], v), i) for i, v in enumerate(self.vectors)]
        sims.sort(key=lambda x: x[0], reverse=True)
        return sims[:top_k]
