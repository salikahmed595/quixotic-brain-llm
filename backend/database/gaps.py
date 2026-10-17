"""Knowledge gaps — PRD §6 FR-CHAT-04, §9 knowledge gap loop, §11 `GET /admin/knowledge-gaps`, §12 `knowledge_gaps`."""
from __future__ import annotations

import re
import unicodedata
from typing import Optional, Sequence
from uuid import UUID


def normalize_question(text: str) -> str:
    """De-duplication key. The PRD asks for de-duplication without a rule: exact match after lower-casing, removing accents
    and punctuation and collapsing spaces (docs/PRD_GAPS.md §0.2)."""
    t = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode() or text
    t = re.sub(r"[^\w\s]", " ", t.lower(), flags=re.UNICODE)
    return " ".join(t.split())[:500]


class GapStore:
    def __init__(self, pool, tenant_id: str) -> None:
        self.pool, self.tenant = pool, tenant_id

    def record(self, question: str, department_id: Optional[UUID]) -> tuple[UUID, bool]:
        """One more unanswered occurrence. Returns (gap id, created now)."""
        key = normalize_question(question)
        with self.pool.connection() as c, c.transaction():
            row = c.execute(
                "UPDATE knowledge_gaps SET occurrences=occurrences+1, last_seen=now(), question=%s "
                "WHERE tenant_id=%s AND normalized=%s AND department_id IS NOT DISTINCT FROM %s AND status IN ('open','in_progress') "
                "RETURNING id", (question[:1000], self.tenant, key, department_id)).fetchone()
            if row:
                return row["id"], False
            gid = c.execute("INSERT INTO knowledge_gaps (tenant_id, normalized, question, department_id) VALUES (%s,%s,%s,%s) "
                            "RETURNING id", (self.tenant, key, question[:1000], department_id)).fetchone()["id"]
            return gid, True

    def report(self, gap_id: UUID, user_id: Optional[UUID], query_id: Optional[UUID], comment: Optional[str]) -> bool:
        with self.pool.connection() as c, c.transaction():
            added = c.execute("INSERT INTO knowledge_gap_reports (gap_id, user_id, query_id, comment) VALUES (%s,%s,%s,%s) "
                              "ON CONFLICT DO NOTHING", (gap_id, user_id, query_id, comment)).rowcount > 0
            if added:
                c.execute("UPDATE knowledge_gaps SET reports=reports+1, last_seen=now() WHERE id=%s", (gap_id,))
        return added

    def get(self, gap_id: UUID) -> Optional[dict]:
        with self.pool.connection() as c:
            return c.execute("SELECT g.*, d.name AS department FROM knowledge_gaps g LEFT JOIN departments d ON d.id=g.department_id "
                             "WHERE g.tenant_id=%s AND g.id=%s", (self.tenant, gap_id)).fetchone()

    def list(self, statuses: Sequence[str], department_ids: Optional[frozenset] = None, include_unassigned: bool = True,
             limit: int = 200) -> list[dict]:
        """`department_ids` None = all; otherwise only those departments (plus unassigned when allowed)."""
        where, params = ["g.tenant_id=%(t)s", "g.status = ANY(%(s)s)"], {"t": self.tenant, "s": list(statuses), "n": limit}
        if department_ids is not None:
            where.append("(g.department_id = ANY(%(d)s)" + (" OR g.department_id IS NULL)" if include_unassigned else ")"))
            params["d"] = list(department_ids)
        with self.pool.connection() as c:
            return c.execute(
                "SELECT g.id, g.question, g.department_id, d.name AS department, g.status, g.occurrences, g.reports, g.first_seen, "
                "g.last_seen, g.resolved_at, g.proposal_id, g.note, "
                "(SELECT array_agg(r.comment ORDER BY r.at DESC) FILTER (WHERE r.comment IS NOT NULL) FROM knowledge_gap_reports r "
                " WHERE r.gap_id=g.id) AS comments "
                "FROM knowledge_gaps g LEFT JOIN departments d ON d.id=g.department_id WHERE " + " AND ".join(where) +
                " ORDER BY (g.occurrences + 3*g.reports) DESC, g.last_seen DESC LIMIT %(n)s", params).fetchall()

    def update(self, gap_id: UUID, status: Optional[str] = None, department_id: Optional[UUID] = None, clear_department: bool = False,
               note: Optional[str] = None, actor: Optional[UUID] = None) -> bool:
        sets, params = [], []
        if status:
            sets.append("status=%s"); params.append(status)
            if status in ("resolved", "dismissed"):
                sets.append("resolved_at=now()"); sets.append("resolved_by=%s"); params.append(actor)
        if department_id is not None or clear_department:
            sets.append("department_id=%s"); params.append(department_id)
        if note is not None:
            sets.append("note=%s"); params.append(note)
        if not sets:
            return False
        with self.pool.connection() as c:
            return c.execute(f"UPDATE knowledge_gaps SET {', '.join(sets)} WHERE tenant_id=%s AND id=%s", (*params, self.tenant, gap_id)).rowcount > 0

    def resolve_by_proposal(self, proposal_id: UUID, gap_id: UUID, actor: Optional[UUID]) -> None:
        """§9: "Once approved new knowledge is published, mark the gap resolved"."""
        with self.pool.connection() as c:
            c.execute("UPDATE knowledge_gaps SET status='resolved', resolved_at=now(), resolved_by=%s, proposal_id=%s "
                      "WHERE id=%s AND status IN ('open','in_progress')", (actor, proposal_id, gap_id))

    def counts(self) -> dict:
        with self.pool.connection() as c:
            return {r["status"]: r["n"] for r in c.execute("SELECT status, count(*) AS n FROM knowledge_gaps WHERE tenant_id=%s GROUP BY status",
                                                           (self.tenant,))}
