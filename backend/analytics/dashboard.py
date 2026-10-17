"""Dashboard (PRD §34) and Knowledge Health (PRD §36) queries.

Only figures that can be computed from stored data are returned. Where the PRD names a figure but not
how to compute it, the value is None with a reason (docs/PRD_GAPS.md) instead of an invented formula."""
from __future__ import annotations

from typing import Optional
from uuid import UUID


class AnalyticsStore:
    def __init__(self, pool, tenant_id: str) -> None:
        self.pool, self.tenant = pool, tenant_id

    def _scope(self, alias: str, dept_ids: Optional[frozenset[UUID]], params: dict) -> str:
        """None = all departments (administrator, §9.4); otherwise restrict to the given departments (§9.3)."""
        if dept_ids is None:
            return ""
        params["scope"] = list(dept_ids)
        return (f" AND EXISTS (SELECT 1 FROM item_departments x WHERE x.item_id={alias}.id "
                f"AND x.department_id = ANY(%(scope)s))")

    def dashboard(self, dept_ids: Optional[frozenset[UUID]] = None) -> dict:
        p: dict = {"t": self.tenant}
        scope_items = self._scope("i", dept_ids, p)
        with self.pool.connection() as c:
            one = lambda sql: c.execute(sql, p).fetchone()["n"]
            chunks = one("SELECT count(*) AS n FROM chunks ch JOIN knowledge_versions v ON v.id=ch.version_id "
                         "JOIN knowledge_items i ON i.id=v.item_id WHERE ch.tenant_id=%(t)s AND v.status='published'" + scope_items)
            pending = one("SELECT count(*) AS n FROM knowledge_versions v JOIN knowledge_items i ON i.id=v.item_id "
                          "WHERE i.tenant_id=%(t)s AND v.status='under_review'" + scope_items)
            memories = one("SELECT count(*) AS n FROM sales_memories WHERE tenant_id=%(t)s" +
                           ("" if dept_ids is None else " AND department_id = ANY(%(scope)s)"))
            depts = one("SELECT count(*) AS n FROM departments WHERE tenant_id=%(t)s AND status='active'")
            week = c.execute("SELECT count(*) AS n, count(*) FILTER (WHERE knowledge_found) AS ok FROM query_log "
                             "WHERE tenant_id=%(t)s AND created_at > now() - interval '7 days'", p).fetchone()
            recent = c.execute("SELECT id, original_query, knowledge_found, confidence, created_at FROM query_log "
                               "WHERE tenant_id=%(t)s ORDER BY created_at DESC LIMIT 10", p).fetchall()
            updated = c.execute("SELECT i.title, v.version, v.updated_at FROM knowledge_versions v "
                                "JOIN knowledge_items i ON i.id=v.item_id WHERE i.tenant_id=%(t)s AND v.status='published'" +
                                scope_items + " ORDER BY v.updated_at DESC LIMIT 10", p).fetchall()
            sources = c.execute("SELECT s->>'title' AS title, count(*) AS uses FROM query_log q, "
                                "jsonb_array_elements(q.retrieved) s WHERE q.tenant_id=%(t)s GROUP BY 1 "
                                "ORDER BY uses DESC LIMIT 10", p).fetchall()
        return {
            "knowledge_chunks": chunks, "sales_memories": memories, "departments": depts,
            "questions_this_week": week["n"],                      # rolling last 7 days
            "retrieval_success": (week["ok"] / week["n"]) if week["n"] else None,   # share of questions with knowledge found
            "pending_approvals": pending,
            "recent_questions": recent, "recently_updated_knowledge": updated, "most_used_sources": sources,
            "failed_questions_endpoint": "/v1/failed-questions",
            "most_asked_topics": None, "most_asked_topics_reason": "PRD §34 lists the widget but not how topics are derived",
        }

    def knowledge_health(self) -> dict:
        p = {"t": self.tenant}
        with self.pool.connection() as c:
            active = c.execute("SELECT count(*) AS n FROM knowledge_versions v JOIN knowledge_items i ON i.id=v.item_id "
                               "WHERE i.tenant_id=%(t)s AND v.status='published'", p).fetchone()["n"]
            stale = c.execute("SELECT count(*) AS n FROM knowledge_versions v JOIN knowledge_items i ON i.id=v.item_id "
                              "WHERE i.tenant_id=%(t)s AND v.status='published' "
                              "AND COALESCE(v.reviewed_at, v.created_at) < now() - interval '6 months'", p).fetchone()["n"]
            expired = c.execute("SELECT count(*) AS n FROM knowledge_versions v JOIN knowledge_items i ON i.id=v.item_id "
                                "WHERE i.tenant_id=%(t)s AND v.status='expired'", p).fetchone()["n"]
        why = "PRD §36 lists this figure but not how it is detected"
        return {
            "active_documents": active, "outdated_documents": expired, "not_reviewed_over_6_months": stale,
            "no_owner_assigned": None, "potential_duplicates": None, "conflicting_policies": None,
            "not_computed_reason": why,
        }
