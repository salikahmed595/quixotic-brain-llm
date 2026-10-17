"""Dashboard and Insights figures — PRD §7 Dashboard ("approved users (target 160), pending accounts, active chats, answer volume,
knowledge health, index status, unresolved gaps, queue counts") and Insights ("top questions, zero-result queries, feedback,
department usage, document coverage, response latency; aggregated/permission-aware reporting").

Everything is aggregate (§6 FR-CHAT-09): counts and question texts, never who asked. Where the PRD names a figure without a way to
compute it, the value is None with a reason instead of an invented formula (CLAUDE.md Rule 1)."""
from __future__ import annotations

from typing import Optional
from uuid import UUID

TARGET_USERS = 160              # PRD §2 goal 1 / §7 Dashboard "Approved users (target 160)"


class AnalyticsStore:
    def __init__(self, pool, tenant_id: str) -> None:
        self.pool, self.tenant = pool, tenant_id

    def _scope(self, alias: str, dept_ids: Optional[frozenset[UUID]], params: dict) -> str:
        """None = all departments; otherwise only documents in the given departments."""
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
            users = {r["account_status"]: r["n"] for r in c.execute(
                "SELECT account_status, count(*) AS n FROM users WHERE tenant_id=%(t)s GROUP BY account_status", p)}
            active_chats = one("SELECT count(DISTINCT id) AS n FROM conversations WHERE tenant_id=%(t)s AND updated_at > now() - interval '24 hours'")
            signed_in = one("SELECT count(DISTINCT user_id) AS n FROM sessions WHERE tenant_id=%(t)s AND revoked_at IS NULL AND expires_at > now() "
                            "AND last_seen_at > now() - interval '15 minutes'")
            chunks = one("SELECT count(*) AS n FROM chunks ch JOIN knowledge_versions v ON v.id=ch.version_id "
                         "JOIN knowledge_items i ON i.id=v.item_id WHERE ch.tenant_id=%(t)s AND v.status='published'" + scope_items)
            published = one("SELECT count(*) AS n FROM knowledge_versions v JOIN knowledge_items i ON i.id=v.item_id "
                            "WHERE i.tenant_id=%(t)s AND v.status='published'" + scope_items)
            not_indexed = one("SELECT count(*) AS n FROM knowledge_versions v JOIN knowledge_items i ON i.id=v.item_id "
                              "WHERE i.tenant_id=%(t)s AND v.status='published' AND v.indexed_checksum IS DISTINCT FROM v.checksum" + scope_items)
            unclassified = one("SELECT count(*) AS n FROM knowledge_items i WHERE i.tenant_id=%(t)s AND i.sensitivity='unclassified'" + scope_items)
            proposals = one("SELECT count(*) AS n FROM knowledge_proposals WHERE tenant_id=%(t)s AND status IN ('open')")
            failed_pub = one("SELECT count(*) AS n FROM knowledge_proposals WHERE tenant_id=%(t)s AND status='failed'")
            gaps = one("SELECT count(*) AS n FROM knowledge_gaps WHERE tenant_id=%(t)s AND status IN ('open','in_progress')" +
                       ("" if dept_ids is None else " AND (department_id = ANY(%(scope)s) OR department_id IS NULL)"))
            jobs = {r["status"]: r["n"] for r in c.execute(
                "SELECT status, count(*) AS n FROM jobs WHERE tenant_id=%(t)s AND (status IN ('queued','running') "
                "OR updated_at > now() - interval '24 hours') GROUP BY status", p)}
            volume = c.execute("SELECT count(*) FILTER (WHERE created_at > now() - interval '24 hours') AS day, "
                               "count(*) FILTER (WHERE created_at > now() - interval '7 days') AS week, "
                               "count(*) FILTER (WHERE created_at > now() - interval '7 days' AND knowledge_found) AS week_found "
                               "FROM query_log WHERE tenant_id=%(t)s", p).fetchone()
            updated = c.execute("SELECT i.id, i.title, v.version, v.published_at AS updated_at FROM knowledge_versions v "
                                "JOIN knowledge_items i ON i.id=v.item_id WHERE i.tenant_id=%(t)s AND v.status='published'" +
                                scope_items + " ORDER BY v.published_at DESC NULLS LAST LIMIT 8", p).fetchall()
            sources = c.execute("SELECT s->>'title' AS title, count(*) AS uses FROM query_log q, "
                                "jsonb_array_elements(q.retrieved) s WHERE q.tenant_id=%(t)s AND q.created_at > now() - interval '30 days' "
                                "GROUP BY 1 ORDER BY uses DESC LIMIT 8", p).fetchall()
        return {
            "approved_users": users.get("active", 0), "target_users": TARGET_USERS,
            "pending_accounts": users.get("pending", 0), "suspended_accounts": users.get("suspended", 0),
            "signed_in_now": signed_in, "active_chats": active_chats,                         # chats with activity in the last 24 h
            "answers_today": volume["day"], "questions_this_week": volume["week"],
            "answered_rate": (volume["week_found"] / volume["week"]) if volume["week"] else None,
            "published_documents": published, "knowledge_chunks": chunks,
            "index_not_current": not_indexed, "unclassified_documents": unclassified,
            "pending_approvals": proposals, "failed_publications": failed_pub, "unresolved_gaps": gaps,
            "jobs": {"queued": jobs.get("queued", 0), "running": jobs.get("running", 0), "failed_24h": jobs.get("failed", 0),
                     "done_24h": jobs.get("succeeded", 0)},
            "recently_updated_knowledge": updated, "most_used_sources": sources,
        }

    def insights(self, days: int = 30) -> dict:
        """§7 Insights, aggregate only."""
        p = {"t": self.tenant, "d": days}
        with self.pool.connection() as c:
            top = c.execute("SELECT lower(normalized_query) AS question, count(*) AS asked, "
                            "count(*) FILTER (WHERE NOT knowledge_found) AS unanswered FROM query_log "
                            "WHERE tenant_id=%(t)s AND created_at > now() - make_interval(days => %(d)s) AND api_key_id IS NULL "
                            "GROUP BY 1 ORDER BY asked DESC LIMIT 15", p).fetchall()
            zero = c.execute("SELECT g.question, g.occurrences, g.reports, d.name AS department, g.last_seen FROM knowledge_gaps g "
                             "LEFT JOIN departments d ON d.id=g.department_id WHERE g.tenant_id=%(t)s AND g.status IN ('open','in_progress') "
                             "ORDER BY g.occurrences + 3*g.reports DESC LIMIT 15", p).fetchall()
            usage = c.execute("SELECT COALESCE(d.name, 'All my departments') AS department, count(*) AS questions, "
                              "count(*) FILTER (WHERE q.knowledge_found) AS answered FROM query_log q LEFT JOIN departments d ON d.id=q.department_id "
                              "WHERE q.tenant_id=%(t)s AND q.created_at > now() - make_interval(days => %(d)s) GROUP BY 1 ORDER BY questions DESC", p).fetchall()
            coverage = c.execute("SELECT d.name AS department, count(DISTINCT i.id) FILTER (WHERE v.status='published') AS published "
                                 "FROM departments d LEFT JOIN item_departments x ON x.department_id=d.id "
                                 "LEFT JOIN knowledge_items i ON i.id=x.item_id LEFT JOIN knowledge_versions v ON v.item_id=i.id "
                                 "WHERE d.tenant_id=%(t)s AND d.status='active' GROUP BY d.name ORDER BY published, d.name", p).fetchall()
            latency = c.execute("SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY latency_ms) AS p50, "
                                "percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms) AS p95, count(*) AS n FROM query_log "
                                "WHERE tenant_id=%(t)s AND created_at > now() - make_interval(days => %(d)s) AND latency_ms IS NOT NULL "
                                "AND mode <> 'search_only'", p).fetchone()
            search_latency = c.execute("SELECT percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms) AS p95 FROM query_log "
                                       "WHERE tenant_id=%(t)s AND created_at > now() - make_interval(days => %(d)s) AND mode='search_only'", p).fetchone()
            fb = c.execute("SELECT count(*) FILTER (WHERE helpful) AS up, count(*) FILTER (WHERE helpful = false) AS down FROM feedback "
                           "WHERE tenant_id=%(t)s AND created_at > now() - make_interval(days => %(d)s)", p).fetchone()
        return {"days": days, "top_questions": top, "zero_result": zero, "department_usage": usage, "coverage": coverage,
                "latency_ms": {"answer_p50": latency["p50"], "answer_p95": latency["p95"], "answers": latency["n"],
                               "search_p95": search_latency["p95"],
                               "targets": {"answer_p95": 8000, "retrieval_p95": 2000}},             # PRD §2 targets
                "feedback": {"up": fb["up"], "down": fb["down"]}}

    def knowledge_health(self) -> dict:
        p = {"t": self.tenant}
        with self.pool.connection() as c:
            one = lambda sql: c.execute(sql, p).fetchone()["n"]
            active = one("SELECT count(*) AS n FROM knowledge_versions v JOIN knowledge_items i ON i.id=v.item_id "
                         "WHERE i.tenant_id=%(t)s AND v.status='published'")
            stale = one("SELECT count(*) AS n FROM knowledge_versions v JOIN knowledge_items i ON i.id=v.item_id "
                        "WHERE i.tenant_id=%(t)s AND v.status='published' AND COALESCE(v.published_at, v.created_at) < now() - interval '6 months'")
            expired = one("SELECT count(*) AS n FROM knowledge_versions v JOIN knowledge_items i ON i.id=v.item_id "
                          "WHERE i.tenant_id=%(t)s AND v.status='published' AND v.expires_at IS NOT NULL AND v.expires_at <= now()")
            expiring = one("SELECT count(*) AS n FROM knowledge_versions v JOIN knowledge_items i ON i.id=v.item_id "
                           "WHERE i.tenant_id=%(t)s AND v.status='published' AND v.expires_at > now() AND v.expires_at < now() + interval '30 days'")
            no_owner = one("SELECT count(*) AS n FROM knowledge_items i WHERE i.tenant_id=%(t)s AND i.owner_id IS NULL "
                           "AND EXISTS (SELECT 1 FROM knowledge_versions v WHERE v.item_id=i.id AND v.status='published')")
            unclassified = one("SELECT count(*) AS n FROM knowledge_items i WHERE i.tenant_id=%(t)s AND i.sensitivity='unclassified' "
                               "AND EXISTS (SELECT 1 FROM knowledge_versions v WHERE v.item_id=i.id AND v.status='published')")
        return {"active_documents": active, "outdated_documents": expired, "expiring_in_30_days": expiring,
                "not_reviewed_over_6_months": stale, "no_owner_assigned": no_owner, "unclassified": unclassified,
                "potential_duplicates": None, "conflicting_policies": None,
                "not_computed_reason": "The PRD gives no rule for duplicates or conflicts; reviewers see related documents for each change in Approvals"}
