"""In-memory stand-ins used by retrieval and API tests (no database, S3, SQS or models)."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from backend.models import Candidate, SalesCase


def cand(title="Sales Pricing Policy", text="up to 10% discount", score=0.9, section="4.2 Discount Approval",
         doc_type="policy", version=3, **kw) -> Candidate:
    return Candidate(chunk_id=uuid4(), version_id=kw.pop("version_id", uuid4()), item_id=uuid4(), title=title,
                     section=section, version=version, updated_at=datetime(2026, 9, 1, tzinfo=timezone.utc), text=text,
                     document_type=doc_type, vector_score=score, **kw)


class FakeEmbedder:
    name, dim = "fake-embed", 3
    def embed(self, text): return [1.0, 0.0, 0.0]
    def embed_many(self, texts): return [self.embed(t) for t in texts]


class FakeStore:
    """RetrievalStore. Applies the department filter like the SQL does so tests can prove it is applied first."""
    def __init__(self, vec=(), kw=(), sales=()):
        self.vec, self.kw, self.sales = list(vec), list(kw), list(sales)
        self.calls = []

    def vector_search(self, embedding, model, department_ids, statuses, limit):
        self.calls.append(("vector", frozenset(department_ids), tuple(statuses), limit))
        return self.vec[:limit] if department_ids else []

    def keyword_search(self, query, model, department_ids, statuses, limit):
        self.calls.append(("keyword", frozenset(department_ids), tuple(statuses), limit))
        return self.kw[:limit] if department_ids else []

    def sales_search(self, embedding, model, department_ids, limit):
        self.calls.append(("sales", frozenset(department_ids), limit))
        return self.sales[:limit]


class FakeGenerator:
    def __init__(self): self.calls = []
    def generate_answer(self, context, question):
        self.calls.append((context, question))
        return "First acknowledge the concern and explain the value before discussing a discount."


def sales_case(outcome="closed") -> SalesCase:
    return SalesCase(uuid4(), "price objection", "too expensive", "I understand...", outcome, 0.9)
