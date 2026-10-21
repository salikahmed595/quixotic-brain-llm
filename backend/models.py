"""Plain data carriers shared across retrieval, reranking and generation."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from uuid import UUID


@dataclass
class Candidate:
    """A knowledge chunk returned by retrieval (PRD §7)."""
    chunk_id: UUID
    version_id: UUID
    item_id: UUID
    title: str
    section: Optional[str]
    version: int
    updated_at: Optional[datetime]
    text: str
    document_type: Optional[str] = None
    vector_score: Optional[float] = None     # cosine similarity
    keyword_score: Optional[float] = None    # sparse rank
    rerank_score: Optional[float] = None

    @property
    def best_score(self) -> Optional[float]:
        return self.rerank_score if self.rerank_score is not None else self.vector_score


@dataclass
class SalesCase:
    """A historical sales memory (PRD §16.2) retrieved for a question."""
    id: UUID
    scenario: Optional[str]
    customer_message: Optional[str]
    agent_response: Optional[str]
    outcome: Optional[str]
    similarity: float
    customer_objection: Optional[str] = None     # PRD §17.2 "Extract Objection"
    sales_stage: Optional[str] = None


@dataclass
class AnswerContext:
    knowledge: list[Candidate] = field(default_factory=list)
    sales_cases: list[SalesCase] = field(default_factory=list)
    history: list[tuple[str, str]] = field(default_factory=list)   # earlier (question, answer) pairs of this chat, oldest first
    asker: dict = field(default_factory=dict)         # who is asking, set by the system: {role, departments}
    preferences: dict = field(default_factory=dict)  # the asker's own style choices (Personalization), already sanitised
    user_language: str = ""                          # detected script of the question (english/urdu/roman_urdu/mixed)
    general_mode: bool = False                        # owner 2026-10-21: general assistant, company knowledge as context
    guidance_only: bool = False                       # owner 2026-10-21: no knowledge, no matching past chat -> careful reply advice
