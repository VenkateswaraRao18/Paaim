"""
Log Historian — retrieves "what fixed this before" from messy maintenance logs.

Real maintenance logs are full of shorthand, typos and abbreviations
("spndl ovrheat 0x4F3 agn - clnt flow low"). This captures the tribal knowledge
of technicians who may have since left. The historian matches a current failure
to similar past entries so the SOP Dispatcher can reuse proven fixes.

Retrieval is intentionally simple/deterministic (machine + signal filter, then
token-overlap scoring) so it runs offline with no embedding service — the
MaintNet corpus can be swapped in by pointing at a bigger CSV.
"""

from __future__ import annotations

import csv
import os
import re
from functools import lru_cache
from typing import Dict, List, Optional

_LOG_PATH = os.path.join(os.path.dirname(__file__), "..", "..",
                         "data_adapters", "maintenance_logs_sample.csv")

_STOP = {"the", "a", "an", "on", "in", "of", "to", "and", "agn", "again"}


def _tokens(text: str) -> set:
    return {t for t in re.findall(r"[a-z0-9]+", (text or "").lower()) if t not in _STOP and len(t) > 1}


class LogHistorian:
    def __init__(self, path: str = _LOG_PATH):
        self.logs: List[Dict] = []
        if os.path.exists(path):
            with open(path, newline="") as fh:
                self.logs = list(csv.DictReader(fh))
        self._index = None      # lazy-built RAG embedding index
        self._built = False

    def _ensure_index(self) -> None:
        """Build the embedding index once, on first use (guarded)."""
        if self._built:
            return
        self._built = True
        try:
            from paaim.semantic.rag import EmbeddingIndex
            docs = [f"{l.get('raw_note','')} {l.get('resolution','')}" for l in self.logs]
            idx = EmbeddingIndex()
            idx.build(docs)
            self._index = idx if idx.available else None
        except Exception:
            self._index = None

    def _format(self, log: Dict, score: float, how: str) -> Dict:
        return {
            "log_id": log.get("log_id"),
            "date": log.get("date"),
            "machine_id": log.get("machine_id"),
            "raw_note": log.get("raw_note"),
            "resolution": log.get("resolution"),
            "downtime_min": log.get("downtime_min"),
            "technician": log.get("technician"),
            "match_score": round(score, 3),
            "retrieved_by": how,
        }

    def search(self, machine_id: str, signal_name: str,
               query: str = "", limit: int = 3) -> List[Dict]:
        """Find past log entries most similar to the current failure.

        Prefers semantic (embedding) retrieval so shorthand/typos still match;
        falls back to deterministic token-overlap if embeddings are unavailable.
        Machine/signal matches boost the score either way.
        """
        self._ensure_index()

        # ── RAG path (semantic) ──
        if self._index is not None:
            q = f"{signal_name} {query}".strip()
            hits = self._index.search(q, top_k=max(limit * 3, 6))
            scored = []
            for sim, i in hits:
                log = self.logs[i]
                boost = (2.0 if log.get("machine_id") == machine_id else 0.0) \
                        + (3.0 if log.get("signal_name") == signal_name else 0.0)
                scored.append((sim * 5.0 + boost, log))
            scored.sort(key=lambda x: x[0], reverse=True)
            return [self._format(log, s, "semantic") for s, log in scored[:limit]]

        # ── Fallback path (token-overlap) ──
        q_tokens = _tokens(f"{signal_name} {query}")
        scored = []
        for log in self.logs:
            score = 0.0
            if log.get("machine_id") == machine_id:
                score += 2.0
            if log.get("signal_name") == signal_name:
                score += 3.0
            overlap = q_tokens & _tokens(log.get("raw_note", ""))
            score += len(overlap) * 0.5
            if score > 0:
                scored.append((score, log))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [self._format(log, s, "keyword") for s, log in scored[:limit]]

    def stats(self) -> Dict:
        self._ensure_index()
        return {"total_logs": len(self.logs), "rag_enabled": self._index is not None}


@lru_cache(maxsize=1)
def get_historian() -> LogHistorian:
    return LogHistorian()
