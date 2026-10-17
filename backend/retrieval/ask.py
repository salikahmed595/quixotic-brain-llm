"""Ask Brain orchestration — PRD §7 (flow), §11, §20, §29, §30, §32.

Authentication and the permission check happen before this service is called; it receives the
already-resolved department scope.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Sequence
from uuid import UUID

from ..config import Settings
from ..generation.base import GenerationProvider
from ..models import AnswerContext, Candidate
from .language import NormalizedQuery
from .search import SearchService, confidence_label

# PRD §29 (no evidence at all) and §32 (low confidence) — wording is the PRD's.
NOT_FOUND_TEXT = (
    "I could not find an approved Quixotic policy covering this situation.\n\n"
    "Please ask your manager or submit missing knowledge."
)
LOW_CONFIDENCE_TEXT = "I could not find enough reliable Quixotic information to answer this confidently."
LOW_CONFIDENCE_ACTIONS = ["ask_manager", "report_missing_knowledge", "search_documents"]   # §32
# Owner request (2026-10-08): an answer written only from past sales chats always starts with this line (PRD §19: keep
# historical correlation and official policy clearly distinguishable).
# MEASURED on 800 of the owner's chats: "hello" (0.97) and "thanks" (0.88) match chat lines more closely than real sales
# questions do (0.58-0.72), so similarity alone cannot decide; the answer model also confirms the chats are on topic.
NO_RELEVANT_HISTORY = "NO_RELEVANT_HISTORY"
HISTORY_ONLY_LABEL = ("Based on past sales chats, not an official Quixotic policy. "
                      "No approved policy or SOP covers this yet.")
SUCCESSFUL_OUTCOME = "closed"        # §16.2 example outcome value; PRD defines no other success rule


def order_by_priority(chunks: list[Candidate], tiers: dict[str, int]) -> list[Candidate]:
    """§20 hierarchy. Tier numbers per document_type come from configuration (the PRD names the
    tiers, not the mapping). Unmapped types sit between tier 3 and the historical tier 4; with no
    mapping configured the reranker order is kept."""
    if not tiers:
        return chunks
    return sorted(chunks, key=lambda c: tiers.get(c.document_type or "", 3.5))      # stable sort


def source_of(c: Candidate) -> dict:
    """PRD §30: title, section, version, updated."""
    return {"title": c.title, "section": c.section, "version": c.version,
            "updated": c.updated_at.isoformat() if c.updated_at else None}


@dataclass
class AskResult:
    answer: str
    confidence: str
    confidence_score: Optional[float]
    found: bool                                           # False -> a "failed question" (§35)
    sources: list[dict] = field(default_factory=list)
    historical_cases: Optional[dict] = None               # §30 "17 similar cases / 12 successful outcomes"
    actions: list[str] = field(default_factory=list)
    query: Optional[NormalizedQuery] = None
    retrieved: list[Candidate] = field(default_factory=list)


NON_ENGLISH = ("roman_urdu", "urdu", "mixed")


class AskService:
    def __init__(self, search: SearchService, generator: GenerationProvider, settings: Settings) -> None:
        self.search, self.generator, self.settings = search, generator, settings

    def _interpret(self, question: str, history: Sequence[tuple[str, str]]) -> str:
        """PRD §23 'semantic interpretation': for Urdu / Roman Urdu / mixed questions and for follow-ups in a chat; a first English
        question needs no extra call, so it stays fast."""
        if not self.settings.query_interpretation or not hasattr(self.generator, "interpret_query"):
            return ""
        # A follow-up inside a chat ("what should I say to Ali if he still refuses?") is restated as a standalone query using
        # the chat so far, in any language. MEASURED on the owner's first chats: without it this 10-word follow-up found nothing.
        if not history and self.search.language.detect(question) not in NON_ENGLISH:
            return ""
        return self.generator.interpret_query(question, list(history)[-1:]) or ""

    def ask(self, question: str, department_ids: frozenset[UUID], include_sales_history: bool = False,
            sales_department_ids: frozenset[UUID] = frozenset(), include_archived: bool = False,
            history: Sequence[tuple[str, str]] = (), asker: Optional[dict] = None,
            preferences: Optional[dict] = None) -> AskResult:
        """`history`: earlier (question, answer) pairs of the same chat, oldest first. Used only to understand what a short
        follow-up refers to, never as a source of facts."""
        previous = history[-1][0] if history else None
        interpretation = self._interpret(question, history)
        out = self.search.search(question, department_ids, include_archived, previous_question=previous,
                                 extra_search_text=interpretation)
        base = dict(confidence=out.confidence, confidence_score=out.confidence_score, query=out.query,
                    retrieved=out.candidates)
        min_sim = self.settings.sales_history_min_similarity
        cases = []
        if (self.settings.sales_history_enabled and (include_sales_history or min_sim is not None)   # owner: OFF (2026-10-17)
                and sales_department_ids and out.embedding is not None):
            cases = self.search.store.sales_search(out.embedding, self.search.embedder.name,
                                                   sales_department_ids, self.settings.historical_top_k)
            if min_sim is not None:
                cases = [c for c in cases if c.similarity >= min_sim]
        if not out.candidates or out.confidence == "low":
            if cases and min_sim is not None:                                         # owner request: history-only answer
                res = self._history_only(out, cases, history, asker, preferences)
                if res is not None:
                    return res
            if not out.candidates:                                                    # §29
                return AskResult(answer=NOT_FOUND_TEXT, found=False, actions=LOW_CONFIDENCE_ACTIONS, **base)
            return AskResult(answer=LOW_CONFIDENCE_TEXT, found=False, actions=LOW_CONFIDENCE_ACTIONS, **base)   # §32: no LLM call

        context = AnswerContext(knowledge=order_by_priority(out.candidates, self.settings.priority_tiers),
                                sales_cases=cases, history=list(history),
                                asker=asker or {}, preferences=preferences or {})
        answer = self.generator.generate_answer(context, out.query.original)
        hist = ({"similar": len(cases), "successful": sum(c.outcome == SUCCESSFUL_OUTCOME for c in cases)}
                if cases else None)
        seen, sources = set(), []
        for c in context.knowledge:
            key = (c.version_id, c.section)
            if key not in seen:
                seen.add(key)
                sources.append(source_of(c))
        return AskResult(answer=answer, found=True, sources=sources, historical_cases=hist, **base)

    def _history_only(self, out, cases, history, asker, preferences) -> Optional[AskResult]:
        """No approved knowledge matched: answer from similar past sales chats only, labelled as such. Still counted as a
        knowledge gap (found=False) so administrators see that a policy/SOP is missing (§35). Confidence comes from how close
        the past chats are, on the same vector thresholds as knowledge (§31). None when the answer model finds them off topic."""
        context = AnswerContext(knowledge=[], sales_cases=cases, history=list(history),
                                asker=asker or {}, preferences=preferences or {})
        text = self.generator.generate_answer(context, out.query.original)
        if NO_RELEVANT_HISTORY in text:                      # the past chats are not about this question -> PRD §29/§32 answer
            return None
        answer = f"{HISTORY_ONLY_LABEL}\n\n{text}"
        top = max(c.similarity for c in cases)
        s = self.settings
        hist = {"similar": len(cases), "successful": sum(c.outcome == SUCCESSFUL_OUTCOME for c in cases)}
        return AskResult(answer=answer, found=False, historical_cases=hist, confidence_score=top,
                         confidence=confidence_label(top, s.confidence_vector_high, s.confidence_vector_medium),
                         query=out.query, retrieved=out.candidates)
