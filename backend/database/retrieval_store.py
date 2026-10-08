"""SQL retrieval — PRD §7, §15, §24–§26, §42.

Every query filters BEFORE ranking by: tenant, department authorization (§42), status (§15) and the
active embedding model (so vectors from different models are never compared, §24.2)."""
from __future__ import annotations

import re
from typing import Optional, Sequence
from uuid import UUID

from pgvector import Vector

from ..models import Candidate, SalesCase

_BASE = """
FROM chunks c
JOIN knowledge_versions v ON v.id = c.version_id
JOIN knowledge_items i ON i.id = v.item_id
WHERE c.tenant_id = %(tenant)s
  AND c.embedding_model = %(model)s
  AND v.status = ANY(%(statuses)s)
  AND EXISTS (SELECT 1 FROM item_departments d WHERE d.item_id = i.id AND d.department_id = ANY(%(depts)s))
"""
_COLS = """c.id AS chunk_id, c.version_id, i.id AS item_id, i.title, c.section, v.version, v.updated_at,
           c.text, i.document_type"""


def _candidate(r: dict, vec: Optional[float] = None, kw: Optional[float] = None) -> Candidate:
    return Candidate(chunk_id=r["chunk_id"], version_id=r["version_id"], item_id=r["item_id"], title=r["title"],
                     section=r["section"], version=r["version"], updated_at=r["updated_at"], text=r["text"],
                     document_type=r["document_type"], vector_score=vec, keyword_score=kw)


def sparse_query(text: str) -> str:
    """OR-query for the sparse (keyword) leg: any matching word counts, ranking sorts them out."""
    words = {w.lower() for w in re.findall(r"\w+", text, flags=re.UNICODE)}
    return " | ".join(sorted(words))


class RetrievalSQLStore:
    def __init__(self, pool, tenant_id: str) -> None:
        self.pool, self.tenant = pool, tenant_id

    def vector_search(self, embedding: Sequence[float], model: str, department_ids: frozenset[UUID],
                      statuses: Sequence[str], limit: int) -> list[Candidate]:
        sql = (f"SELECT {_COLS}, 1 - (c.embedding <=> %(emb)s) AS score " + _BASE +
               " ORDER BY c.embedding <=> %(emb)s LIMIT %(limit)s")
        with self.pool.connection() as conn:
            rows = conn.execute(sql, {"emb": Vector(list(embedding)), "tenant": self.tenant, "model": model,
                                      "statuses": list(statuses), "depts": list(department_ids), "limit": limit}).fetchall()
        return [_candidate(r, vec=float(r["score"])) for r in rows]

    def keyword_search(self, query: str, model: str, department_ids: frozenset[UUID],
                       statuses: Sequence[str], limit: int) -> list[Candidate]:
        q = sparse_query(query)
        if not q:
            return []
        sql = (f"SELECT {_COLS}, ts_rank_cd(c.tsv, to_tsquery('simple', %(q)s)) AS score " + _BASE +
               " AND c.tsv @@ to_tsquery('simple', %(q)s) ORDER BY score DESC LIMIT %(limit)s")
        with self.pool.connection() as conn:
            rows = conn.execute(sql, {"q": q, "tenant": self.tenant, "model": model, "statuses": list(statuses),
                                      "depts": list(department_ids), "limit": limit}).fetchall()
        return [_candidate(r, kw=float(r["score"])) for r in rows]

    def sales_search(self, embedding: Sequence[float], model: str, department_ids: frozenset[UUID],
                     limit: int) -> list[SalesCase]:
        with self.pool.connection() as conn:
            rows = conn.execute(
                "SELECT id, scenario, customer_message, agent_response, outcome, customer_objection, sales_stage, "
                "1 - (embedding <=> %(emb)s) AS sim "
                "FROM sales_memories WHERE tenant_id=%(t)s AND embedding_model=%(m)s AND department_id = ANY(%(d)s) "
                "ORDER BY embedding <=> %(emb)s LIMIT %(n)s",
                {"emb": Vector(list(embedding)), "t": self.tenant, "m": model, "d": list(department_ids), "n": limit}).fetchall()
        return [SalesCase(r["id"], r["scenario"], r["customer_message"], r["agent_response"], r["outcome"], float(r["sim"]),
                          r["customer_objection"], r["sales_stage"])
                for r in rows]
