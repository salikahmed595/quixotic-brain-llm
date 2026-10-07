"""Reranking — PRD §27: reduce ~20–40 hybrid candidates to the best 5–8.

The PRD asks the reranker to prioritize relevance, current information, official knowledge,
scenario similarity, permissions and department context. Permissions, current-ness (status=active)
and department context are enforced as retrieval filters BEFORE ranking; the model score covers
relevance. How to weight the rest is not specified (docs/PRD_GAPS.md), so no extra weighting is invented.
"""
from __future__ import annotations

import threading
from typing import Optional, Protocol, Sequence

from ..config import Settings
from ..models import Candidate


class Reranker(Protocol):
    def score(self, query: str, texts: Sequence[str]) -> list[float]: ...


class CrossEncoderReranker:
    """Cross-encoder reranker. Stack decision: multilingual BGE reranker (BAAI/bge-reranker-v2-m3), on CPU."""

    def __init__(self, model_name: str) -> None:
        self._name, self._model, self._lock = model_name, None, threading.Lock()

    def _load(self):
        with self._lock:
            if self._model is None:
                from sentence_transformers import CrossEncoder  # heavy; imported lazily
                self._model = CrossEncoder(self._name, device="cpu")
        return self._model

    def warm(self) -> None:
        self.score("warm up", ["warm up"])

    def score(self, query: str, texts: Sequence[str]) -> list[float]:
        return [float(s) for s in self._load().predict([(query, t) for t in texts])]


def get_reranker(settings: Settings) -> Optional[Reranker]:
    if not settings.reranker_provider:
        return None                                   # PRD Phase 1 has no reranker (§61)
    if settings.reranker_provider == "cross-encoder":
        return CrossEncoderReranker(settings.reranker_model)  # model presence validated in Settings
    raise NotImplementedError(f"reranker provider {settings.reranker_provider!r} is not implemented")


def rerank_text(c: Candidate) -> str:
    """What the reranker reads: title and section give a terse chunk its context (measured: raises the relevant
    chunk's score for short policy snippets; docs/PRD_GAPS.md)."""
    head = f"{c.title} - {c.section}" if c.section else c.title
    return f"{head}\n{c.text}"


RRF_K = 60     # the usual constant of Reciprocal Rank Fusion (implementation necessity, docs/PRD_GAPS.md)


def rerank(reranker: Optional[Reranker], query: str, candidates: list[Candidate], keep: int,
           top_k: Optional[int] = None) -> list[Candidate]:
    """Best `keep` chunks. Without a reranker the (hybrid) candidate order is kept.

    MEASURED (RAG audit, real BGE-M3 + bge-reranker-v2-m3, 46 labelled questions):
      * the reranker costs ~0.5 s per candidate on CPU, so reading all 30 candidates took 11-20 s per question;
      * reading only the top 6-20 gave identical results -> only the first `top_k` candidates are scored;
      * on its own the reranker's top choice was right slightly LESS often than the retrieval order (R@1 0.85 vs 0.89) and
        it was blind to pure Roman Urdu, while combining the two rankings (Reciprocal Rank Fusion) gave the best result
        (R@1 0.91). So the final order fuses the retrieval rank and the reranker rank instead of trusting either alone.
    """
    if reranker is None or not candidates:
        return candidates[:keep]
    pool = candidates[: top_k or len(candidates)]
    scores = reranker.score(query, [rerank_text(c) for c in pool])
    for c, s in zip(pool, scores):
        c.rerank_score = s
    by_rerank = {id(c): r for r, c in enumerate(sorted(pool, key=lambda c: c.rerank_score, reverse=True), 1)}
    fused = {id(c): 1 / (RRF_K + r) + 1 / (RRF_K + by_rerank[id(c)]) for r, c in enumerate(pool, 1)}
    best = sorted(pool, key=lambda c: fused[id(c)], reverse=True)[:keep]
    # Chunks the reranker did not read follow in retrieval order, so the answer model still gets `keep` chunks. MEASURED on the
    # owner's real PDF: the right chunk was in the top 3 of retrieval for 25 of 25 questions, so reading 3 is enough and
    # ~40% faster than reading 5 (the reranker costs ~1.2 s per 1,000-character chunk on this 2-core CPU).
    return best + candidates[len(pool): len(pool) + max(0, keep - len(best))]
