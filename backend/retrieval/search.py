"""Hybrid retrieval — PRD §7, §25, §26, §27.

    query -> normalize -> keyword search (§25) + vector search (§24) -> hybrid candidates (20–40)
          -> reranker -> best 5–8 chunks

Permissions/department filtering happens inside the store queries BEFORE ranking (§42, §51);
status = active is the default filter (§15).
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional, Protocol, Sequence
from uuid import UUID

from ..config import Settings
from ..learning.feedback import reorder
from ..models import Candidate, SalesCase
from ..reranking.base import Reranker, rerank
from .embeddings import Embedder
from .language import LanguageService, NormalizedQuery

FOLLOW_UP_MAX_WORDS = 8         # a question this short is treated as a follow-up when the chat has a previous question
ACTIVE_ONLY = ("active",)
WITH_ARCHIVED = ("active", "archived")      # §15: archived only "when explicitly requested"


class RetrievalStore(Protocol):
    def vector_search(self, embedding: Sequence[float], model: str, department_ids: frozenset[UUID],
                      statuses: Sequence[str], limit: int) -> list[Candidate]: ...
    def keyword_search(self, query: str, model: str, department_ids: frozenset[UUID],
                       statuses: Sequence[str], limit: int) -> list[Candidate]: ...
    def sales_search(self, embedding: Sequence[float], model: str, department_ids: frozenset[UUID],
                     limit: int) -> list[SalesCase]: ...


def confidence_label(score: Optional[float], high: float, medium: float) -> str:
    """PRD §31: backend scores internally; frontend shows High / Medium / Low."""
    if score is None:
        return "low"
    return "high" if score >= high else "medium" if score >= medium else "low"


def interleave_merge(vector_hits: list[Candidate], keyword_hits: list[Candidate], limit: int) -> list[Candidate]:
    """Hybrid candidate set (§26): union of both result lists, vector hit first, de-duplicated,
    capped at `limit`. Ordering between the two legs is left to the reranker (§27); the PRD
    defines no score-fusion formula."""
    merged: dict[UUID, Candidate] = {}
    for a, b in zip_longest_pairs(vector_hits, keyword_hits):
        for c in (a, b):
            if c is None:
                continue
            if c.chunk_id in merged:
                m = merged[c.chunk_id]
                m.vector_score = m.vector_score if m.vector_score is not None else c.vector_score
                m.keyword_score = m.keyword_score if m.keyword_score is not None else c.keyword_score
            elif len(merged) < limit:
                merged[c.chunk_id] = c
    return list(merged.values())


def zip_longest_pairs(a: list, b: list):
    for i in range(max(len(a), len(b))):
        yield (a[i] if i < len(a) else None), (b[i] if i < len(b) else None)


@dataclass
class SearchOutcome:
    query: NormalizedQuery
    embedding: Optional[list[float]]
    candidates: list[Candidate]           # final best chunks
    confidence_score: Optional[float]
    confidence: str
    timings: dict = field(default_factory=dict)    # seconds per step (embed / vector / keyword / rerank), for admins


class SearchService:
    def __init__(self, store: RetrievalStore, embedder: Embedder, reranker: Optional[Reranker],
                 language: LanguageService, settings: Settings, feedback_signals=None) -> None:
        self.store, self.embedder, self.reranker = store, embedder, reranker
        self.language, self.settings = language, settings
        self.feedback_signals = feedback_signals       # callable(chunk_ids) -> {chunk_id: boost}; learned from 👍/👎, see learning/feedback.py

    def search(self, question: str, department_ids: frozenset[UUID], include_archived: bool = False,
               previous_question: Optional[str] = None, extra_search_text: str = "") -> SearchOutcome:
        q = self.language.process(question)
        s = self.settings
        if not department_ids:                                  # nothing authorized -> nothing to search
            return SearchOutcome(q, None, [], None, "low")
        text = q.search_text
        if previous_question and len(question.split()) <= FOLLOW_UP_MAX_WORDS:
            # A short follow-up ("and how long does it take?") means nothing alone. MEASURED on 12 follow-ups: searching it
            # alone found the right document 8/12 times and was never flagged low-confidence; with the previous question
            # in front it found it 12/12.
            text = f"{previous_question} {text}"
        if extra_search_text:                                   # e.g. the English restatement of a Roman Urdu question
            text = f"{text} {extra_search_text}"
        t0 = time.perf_counter()
        emb = self.embedder.embed(text)
        t1 = time.perf_counter()
        statuses = WITH_ARCHIVED if include_archived else ACTIVE_ONLY
        vec = self.store.vector_search(emb, self.embedder.name, department_ids, statuses, s.candidate_count)
        kw = self.store.keyword_search(self.language.keyword_terms(text), self.embedder.name, department_ids, statuses,
                                       s.candidate_count)
        t2 = time.perf_counter()
        candidates = interleave_merge(vec, kw, s.candidate_count)
        if self.feedback_signals and len(candidates) > 1:
            try:                                                 # learning must never be able to break a search
                candidates = reorder(candidates, self.feedback_signals([c.chunk_id for c in candidates]))
            except Exception:
                pass
        reranker = self.reranker
        if reranker is not None and s.rerank_skip_margin > 0 and len(vec) >= 2:
            lead = (vec[0].vector_score or 0) - (vec[1].vector_score or 0)
            # Decisive = a clear lead AND a vector score that is HIGH on its own. A clear lead with a weaker score still needs the
            # reranker: "Who is the founder?" (0.52) was labelled low without it, and on the owner's real PDF unanswerable
            # questions also reach 0.56 ("employee salaries") while real answers score 0.52-0.73.
            if lead >= s.rerank_skip_margin and (vec[0].vector_score or 0) >= s.confidence_vector_high:
                reranker = None                                 # retrieval is decisive: save the reranker's ~0.5 s per candidate
        # The reranker reads ONE clean question. When the AI restated the question in English, that restatement is far cleaner than
        # the original+restatement mix used for the embedding (MEASURED on a restated follow-up: reranker score 0.52 vs 0.01-0.18).
        final = rerank(reranker, extra_search_text or text, candidates, s.final_chunk_count, top_k=s.rerank_top_k)
        score, label = self.confidence(final)
        t3 = time.perf_counter()
        return SearchOutcome(q, emb, final, score, label, {"embed": round(t1 - t0, 2), "database": round(t2 - t1, 2),
                                                            "rerank": round(t3 - t2, 2), "reranker_used": reranker is not None})

    def confidence(self, final: list[Candidate]) -> tuple[Optional[float], str]:
        """Two independent signals, the better one counts (PRD §31: scores stay in the backend, the UI shows High/Medium/Low).

        MEASURED (RAG audit): the reranker is blind to pure Roman Urdu (probability ~0 even for the right chunk) while vector
        similarity still sees it; for English the reranker separates answerable from unanswerable questions better. Rule
        "vector >= 0.55 OR rerank >= 0.01" answered 80% of answerable questions and let 0% of unanswerable ones through."""
        s = self.settings
        rr = max((c.rerank_score for c in final if c.rerank_score is not None), default=None)
        vs = max((c.vector_score for c in final if c.vector_score is not None), default=None)
        labels = [confidence_label(rr, s.confidence_high, s.confidence_medium) if rr is not None else "low",
                  confidence_label(vs, s.confidence_vector_high, s.confidence_vector_medium) if vs is not None else "low"]
        best = max(labels, key=("low", "medium", "high").index)
        return (rr if rr is not None else vs), best
