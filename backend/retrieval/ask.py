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
from .search import SearchService

# PRD §29 (no evidence at all) and §32 (low confidence) — wording is the PRD's.
NOT_FOUND_TEXT = (
    "I could not find an approved Quixotic policy covering this situation.\n\n"
    "Please ask your manager or submit missing knowledge."
)
LOW_CONFIDENCE_TEXT = "I could not find enough reliable Quixotic information to answer this confidently."
LOW_CONFIDENCE_ACTIONS = ["ask_manager", "report_missing_knowledge", "search_documents"]   # §32
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
        if not out.candidates:                                                        # §29
            return AskResult(answer=NOT_FOUND_TEXT, found=False, actions=LOW_CONFIDENCE_ACTIONS, **base)
        if out.confidence == "low":                                                   # §32: no LLM call
            return AskResult(answer=LOW_CONFIDENCE_TEXT, found=False, actions=LOW_CONFIDENCE_ACTIONS, **base)

        cases = []
        if include_sales_history and sales_department_ids and out.embedding is not None:
            cases = self.search.store.sales_search(out.embedding, self.search.embedder.name,
                                                   sales_department_ids, self.settings.historical_top_k)
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
