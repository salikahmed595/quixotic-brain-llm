"""Jobs (§47), API keys (§40), query log / feedback (§21, §35), audit log (§53), sales memories (§16)."""
from __future__ import annotations

from typing import Optional, Sequence
from uuid import UUID

from pgvector import Vector
from psycopg.types.json import Jsonb


class OpsStore:
    def __init__(self, pool, tenant_id: str) -> None:
        self.pool, self.tenant = pool, tenant_id

    # ---- jobs (§47: frontend shows progress) ----
    def create_job(self, job_type: str, payload: dict, created_by: Optional[UUID], total: Optional[int] = None) -> UUID:
        with self.pool.connection() as c:
            return c.execute("INSERT INTO jobs (tenant_id, type, payload, created_by, progress_total) "
                             "VALUES (%s,%s,%s,%s,%s) RETURNING id",
                             (self.tenant, job_type, Jsonb(payload), created_by, total)).fetchone()["id"]

    def get_job(self, job_id: UUID) -> Optional[dict]:
        with self.pool.connection() as c:
            return c.execute("SELECT * FROM jobs WHERE tenant_id=%s AND id=%s", (self.tenant, job_id)).fetchone()

    def list_jobs(self, limit: int = 50) -> list[dict]:
        with self.pool.connection() as c:
            return c.execute("SELECT * FROM jobs WHERE tenant_id=%s ORDER BY created_at DESC LIMIT %s",
                             (self.tenant, limit)).fetchall()

    def update_job(self, job_id: UUID, status: Optional[str] = None, done: Optional[int] = None,
                   total: Optional[int] = None, error: Optional[str] = None) -> None:
        with self.pool.connection() as c:
            c.execute("UPDATE jobs SET status=COALESCE(%s,status), progress_done=COALESCE(%s,progress_done), "
                      "progress_total=COALESCE(%s,progress_total), error=COALESCE(%s,error), updated_at=now() WHERE id=%s",
                      (status, done, total, error, job_id))

    # ---- API keys (§40) ----
    def create_api_key(self, name: str, prefix: str, key_hash: str, last4: str, permissions: Sequence[str],
                       department_ids: Sequence[UUID], rate_limit: Optional[int], expires_at, created_by: UUID) -> UUID:
        """`name` is only a label for the admin (the key itself carries no name). Empty `department_ids` = all
        departments the acting user may see. `rate_limit` None = no limit; `expires_at` None = until revoked."""
        with self.pool.connection() as c:
            return c.execute(
                "INSERT INTO api_keys (tenant_id, app_name, key_prefix, key_hash, last4, permissions, allowed_department_ids, "
                "rate_limit_per_minute, expires_at, created_by) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
                (self.tenant, name, prefix, key_hash, last4, list(permissions), list(department_ids), rate_limit,
                 expires_at, created_by)).fetchone()["id"]

    def api_key_by_hash(self, key_hash: str) -> Optional[dict]:
        """Returns the key whatever its state, so the caller can say *why* it was refused (revoked / expired)."""
        with self.pool.connection() as c:
            return c.execute("SELECT * FROM api_keys WHERE tenant_id=%s AND key_hash=%s",
                             (self.tenant, key_hash)).fetchone()

    def touch_api_key(self, key_id: UUID) -> None:
        with self.pool.connection() as c:
            c.execute("UPDATE api_keys SET last_used_at=now() WHERE id=%s", (key_id,))

    def list_api_keys(self) -> list[dict]:
        with self.pool.connection() as c:     # never returns key_hash
            return c.execute("SELECT id, app_name, key_prefix, last4, permissions, allowed_department_ids, "
                             "rate_limit_per_minute, expires_at, status, created_at, last_used_at, revoked_at "
                             "FROM api_keys WHERE tenant_id=%s ORDER BY created_at DESC", (self.tenant,)).fetchall()

    def revoke_api_key(self, key_id: UUID) -> bool:
        with self.pool.connection() as c:
            return c.execute("UPDATE api_keys SET status='revoked', revoked_at=now() "
                             "WHERE tenant_id=%s AND id=%s AND status='active'", (self.tenant, key_id)).rowcount > 0

    # ---- query log & feedback (§21, §35) ----
    def log_query(self, *, user_id: Optional[UUID], api_key_id: Optional[UUID], department_id: Optional[UUID],
                  mode: str, original: str, normalized: str, language: str, confidence: Optional[str],
                  score: Optional[float], found: bool, retrieved: list, answer: Optional[str],
                  latency_ms: Optional[int], gap_id: Optional[UUID] = None) -> UUID:
        with self.pool.connection() as c:
            return c.execute(
                "INSERT INTO query_log (tenant_id, user_id, api_key_id, department_id, mode, original_query, "
                "normalized_query, language, confidence, confidence_score, knowledge_found, retrieved, answer, latency_ms, gap_id) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
                (self.tenant, user_id, api_key_id, department_id, mode, original, normalized, language, confidence,
                 score, found, Jsonb(retrieved), answer, latency_ms, gap_id)).fetchone()["id"]

    def get_query(self, query_id: UUID) -> Optional[dict]:
        with self.pool.connection() as c:
            return c.execute("SELECT * FROM query_log WHERE tenant_id=%s AND id=%s", (self.tenant, query_id)).fetchone()

    def add_feedback(self, query_id: UUID, user_id: Optional[UUID], helpful: Optional[bool], outcome: Optional[str],
                     agent_action: Optional[str], note: Optional[str]) -> UUID:
        with self.pool.connection() as c:
            return c.execute("INSERT INTO feedback (tenant_id, query_id, user_id, helpful, outcome, agent_action, note) "
                             "VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id",
                             (self.tenant, query_id, user_id, helpful, outcome, agent_action, note)).fetchone()["id"]

    def failed_questions(self, limit: int = 100) -> list[dict]:
        with self.pool.connection() as c:
            return c.execute("SELECT id, original_query, normalized_query, language, confidence, knowledge_found, created_at "
                             "FROM query_log WHERE tenant_id=%s AND NOT knowledge_found ORDER BY created_at DESC LIMIT %s",
                             (self.tenant, limit)).fetchall()

    # ---- vocabulary: company Urdu / Roman Urdu phrases -> English meaning (PRD §23) ----
    def list_vocabulary(self) -> list[dict]:
        with self.pool.connection() as c:
            return c.execute("SELECT id, phrase, meaning, created_at FROM vocabulary WHERE tenant_id=%s ORDER BY lower(phrase)",
                             (self.tenant,)).fetchall()

    def add_vocabulary(self, phrase: str, meaning: str, created_by: Optional[UUID]) -> UUID:
        with self.pool.connection() as c:     # saving the same phrase again replaces its meaning
            return c.execute("INSERT INTO vocabulary (tenant_id, phrase, meaning, created_by) VALUES (%s,%s,%s,%s) "
                             "ON CONFLICT (tenant_id, lower(phrase)) DO UPDATE SET meaning=EXCLUDED.meaning RETURNING id",
                             (self.tenant, phrase, meaning, created_by)).fetchone()["id"]

    def delete_vocabulary(self, vocab_id: UUID) -> bool:
        with self.pool.connection() as c:
            return c.execute("DELETE FROM vocabulary WHERE tenant_id=%s AND id=%s", (self.tenant, vocab_id)).rowcount > 0

    # ---- learning from 👍 / 👎 (owner request; docs/PRD_GAPS.md). Only the LATEST rating of a person on a question counts. ----
    _LATEST = ("SELECT DISTINCT ON (f.query_id, f.user_id) f.query_id, f.user_id, f.helpful, f.created_at FROM feedback f "
               "WHERE f.tenant_id=%(t)s AND f.helpful IS NOT NULL AND (%(since)s::timestamptz IS NULL OR f.created_at > %(since)s) "
               "{extra} ORDER BY f.query_id, f.user_id, f.created_at DESC")

    def learning_since(self):
        """Ratings older than this are ignored (an administrator pressed 'reset'). None = every rating counts."""
        with self.pool.connection() as c:
            row = c.execute("SELECT reset_at FROM learning_state WHERE tenant_id=%s", (self.tenant,)).fetchone()
        return row["reset_at"] if row else None

    def reset_learning(self, admin_id: Optional[UUID]) -> None:
        with self.pool.connection() as c:
            c.execute("INSERT INTO learning_state (tenant_id, reset_at, reset_by) VALUES (%s, now(), %s) "
                      "ON CONFLICT (tenant_id) DO UPDATE SET reset_at=now(), reset_by=EXCLUDED.reset_by", (self.tenant, admin_id))

    def reset_user_learning(self, user_id: UUID) -> None:
        with self.pool.connection() as c:
            c.execute("UPDATE users SET learning_reset_at=now() WHERE tenant_id=%s AND id=%s", (self.tenant, user_id))

    def chunk_votes(self, chunk_ids: Sequence[UUID], top_positions: int, since=None) -> dict:
        """chunk_id -> (up, down): ratings given to answers in which the chunk was among the first `top_positions` passages."""
        if not chunk_ids:
            return {}
        sql = ("WITH latest AS (" + self._LATEST.format(extra="") + ") "
               "SELECT (r.elem->>'chunk_id')::uuid AS chunk_id, count(*) FILTER (WHERE l.helpful) AS up, "
               "count(*) FILTER (WHERE NOT l.helpful) AS down FROM latest l JOIN query_log q ON q.id=l.query_id, "
               "LATERAL jsonb_array_elements(q.retrieved) WITH ORDINALITY AS r(elem, pos) "
               "WHERE r.pos <= %(top)s AND (r.elem->>'chunk_id')::uuid = ANY(%(ids)s) GROUP BY 1")
        with self.pool.connection() as c:
            rows = c.execute(sql, {"t": self.tenant, "since": since, "top": top_positions, "ids": list(chunk_ids)}).fetchall()
        return {r["chunk_id"]: (r["up"], r["down"]) for r in rows}

    def rated_answers(self, user_id: UUID, since=None, limit: int = 60) -> list[dict]:
        """One person's rated answers, newest first: {helpful, answer, reasons}. `reasons` are the short notes sent with the rating."""
        with self.pool.connection() as c:
            rows = c.execute(
                "SELECT * FROM (SELECT DISTINCT ON (f.query_id) f.query_id, f.helpful, q.answer, f.created_at FROM feedback f "
                "JOIN query_log q ON q.id=f.query_id WHERE f.tenant_id=%(t)s AND f.user_id=%(u)s AND f.helpful IS NOT NULL "
                "AND (%(since)s::timestamptz IS NULL OR f.created_at > %(since)s) ORDER BY f.query_id, f.created_at DESC) x "
                "ORDER BY created_at DESC LIMIT %(n)s", {"t": self.tenant, "u": user_id, "since": since, "n": limit}).fetchall()
            notes = c.execute("SELECT query_id, lower(btrim(note)) AS note FROM feedback WHERE tenant_id=%s AND user_id=%s AND note IS NOT NULL "
                              "AND query_id = ANY(%s)", (self.tenant, user_id, [r["query_id"] for r in rows])).fetchall() if rows else []
        by_q: dict = {}
        for n in notes:
            by_q.setdefault(n["query_id"], []).append(n["note"])
        return [{"helpful": r["helpful"], "answer": r["answer"] or "", "reasons": by_q.get(r["query_id"], [])} for r in rows]

    def helpful_by_query(self, user_id: UUID, query_ids: Sequence[UUID]) -> dict:
        """query_id -> latest rating (True / False) by this person, for the questions of one chat."""
        if not query_ids:
            return {}
        with self.pool.connection() as c:
            rows = c.execute("SELECT DISTINCT ON (query_id) query_id, helpful FROM feedback WHERE tenant_id=%s AND user_id=%s AND helpful IS NOT NULL "
                             "AND query_id = ANY(%s) ORDER BY query_id, created_at DESC", (self.tenant, user_id, list(query_ids))).fetchall()
        return {r["query_id"]: r["helpful"] for r in rows}

    def answer_quality(self, days: int = 30, top_positions: int = 2, since=None) -> dict:
        """Patterns in the ratings, for administrators. No person is named: the report is about answers and sources, not about staff."""
        p = {"t": self.tenant, "since": since, "days": days, "top": top_positions}
        latest = "WITH latest AS (" + self._LATEST.format(extra="AND f.created_at > now() - make_interval(days => %(days)s)") + ") "
        with self.pool.connection() as c:
            tot = c.execute(latest + "SELECT count(*) FILTER (WHERE helpful) AS up, count(*) FILTER (WHERE NOT helpful) AS down FROM latest", p).fetchone()
            by_conf = c.execute(latest + "SELECT coalesce(q.confidence,'?') AS k, count(*) FILTER (WHERE l.helpful) AS up, count(*) FILTER (WHERE NOT l.helpful) AS down "
                                "FROM latest l JOIN query_log q ON q.id=l.query_id GROUP BY 1 ORDER BY 1", p).fetchall()
            by_lang = c.execute(latest + "SELECT q.language AS k, count(*) FILTER (WHERE l.helpful) AS up, count(*) FILTER (WHERE NOT l.helpful) AS down "
                                "FROM latest l JOIN query_log q ON q.id=l.query_id GROUP BY 1 ORDER BY 2+3 DESC", p).fetchall()
            sources = c.execute(latest + "SELECT r.elem->>'title' AS title, r.elem->>'section' AS section, count(*) FILTER (WHERE l.helpful) AS up, "
                                "count(*) FILTER (WHERE NOT l.helpful) AS down FROM latest l JOIN query_log q ON q.id=l.query_id, "
                                "LATERAL jsonb_array_elements(q.retrieved) WITH ORDINALITY AS r(elem, pos) WHERE r.pos <= %(top)s "
                                "GROUP BY 1, 2", p).fetchall()
            bad = c.execute(latest + "SELECT q.id, q.original_query, left(coalesce(q.answer,''), 240) AS answer, q.confidence, q.language, l.created_at, "
                            "(SELECT string_agg(DISTINCT f2.note, '; ') FROM feedback f2 WHERE f2.query_id=q.id AND f2.note IS NOT NULL) AS note "
                            "FROM latest l JOIN query_log q ON q.id=l.query_id WHERE NOT l.helpful ORDER BY l.created_at DESC LIMIT 20", p).fetchall()
        return {"days": days, "up": tot["up"], "down": tot["down"], "by_confidence": by_conf, "by_language": by_lang,
                "weakest_sources": sorted([s for s in sources if s["down"]], key=lambda s: (-s["down"], s["up"]))[:10],
                "best_sources": sorted([s for s in sources if s["up"]], key=lambda s: (-s["up"], s["down"]))[:10],
                "recent_not_helpful": bad}

    # ---- audit log (§53) ----
    def audit(self, event: str, actor_id: Optional[UUID], actor_label: Optional[str], detail: dict) -> None:
        with self.pool.connection() as c:
            c.execute("INSERT INTO audit_logs (tenant_id, actor_id, actor_label, event, detail) VALUES (%s,%s,%s,%s,%s)",
                      (self.tenant, actor_id, actor_label, event, Jsonb(detail)))

    def list_audit(self, limit: int = 200, event: Optional[str] = None) -> list[dict]:
        with self.pool.connection() as c:
            return c.execute("SELECT id, at, actor_id, actor_label, event, detail FROM audit_logs "
                             "WHERE tenant_id=%s AND (%s::text IS NULL OR event=%s) ORDER BY id DESC LIMIT %s",
                             (self.tenant, event, event, limit)).fetchall()

    def verify_audit_chain(self) -> dict:
        """PRD §10 tamper-resistant audit log: recompute every row's hash and follow the prev_hash links. Any edited, removed or
        inserted-in-between row breaks it. The tip hash is also written to each backup manifest as an outside anchor."""
        with self.pool.connection() as c:
            rows = c.execute("SELECT id, prev_hash, hash, audit_row_hash(prev_hash, tenant_id, at, actor_id, actor_label, event, detail) "
                             "AS expected FROM audit_logs ORDER BY id").fetchall()
        problems, hashes, used = [], {r["hash"] for r in rows}, {}
        for r in rows:
            if r["hash"] != r["expected"]:
                problems.append({"id": r["id"], "problem": "content changed"})
            if r["prev_hash"] != "genesis" and r["prev_hash"] not in hashes:
                problems.append({"id": r["id"], "problem": "previous entry missing"})
            if r["prev_hash"] in used:
                problems.append({"id": r["id"], "problem": f"chain forks (also follows entry {used[r['prev_hash']]})"})
            used[r["prev_hash"]] = r["id"]
        tips = [r for r in rows if r["hash"] not in used]
        if rows and len(tips) != 1:
            problems.append({"id": None, "problem": f"{len(tips)} chain ends instead of 1"})
        return {"ok": not problems, "entries": len(rows), "tip": tips[0]["hash"] if len(tips) == 1 else None, "problems": problems[:50]}

    def audit_for_user(self, user_id: UUID, limit: int = 100) -> list[dict]:
        """PRD §7 Users "audit history": what this person did and what was done to their account."""
        with self.pool.connection() as c:
            return c.execute("SELECT id, at, actor_id, actor_label, event, detail FROM audit_logs WHERE tenant_id=%s "
                             "AND (actor_id=%s OR detail->>'user'=%s) ORDER BY id DESC LIMIT %s",
                             (self.tenant, user_id, str(user_id), limit)).fetchall()

    # ---- sales memories (§16.2) ----
    def sales_memory_imports(self, limit: int = 50) -> list[dict]:
        """§17.1 import UI: each import with its department and how many memories it stored."""
        with self.pool.connection() as c:
            return c.execute(
                "SELECT j.id, j.status, j.progress_done, j.progress_total, j.error, j.created_at, j.updated_at, "
                "j.payload->>'filename' AS filename, d.name AS department, "
                "(SELECT count(*) FROM sales_memories m WHERE m.import_job_id = j.id) AS stored "
                "FROM jobs j LEFT JOIN departments d ON d.id::text = j.payload->>'department_id' "
                "WHERE j.tenant_id=%s AND j.type='discord.import' ORDER BY j.created_at DESC LIMIT %s",
                (self.tenant, limit)).fetchall()

    def delete_sales_memory_import(self, job_id: UUID) -> int:
        """Remove the memories one import stored (a wrong file or department). The job row stays for the audit trail."""
        with self.pool.connection() as c:
            return c.execute("DELETE FROM sales_memories WHERE tenant_id=%s AND import_job_id=%s",
                             (self.tenant, job_id)).rowcount

    def insert_sales_memory(self, rec: dict, embedding: Sequence[float], model: str, department_id: UUID,
                            job_id: Optional[UUID] = None) -> UUID:
        with self.pool.connection() as c:
            return c.execute(
                "INSERT INTO sales_memories (tenant_id, department_id, conversation_id, channel, scenario, customer_intent, "
                "customer_message, agent_response, sales_stage, product, outcome, sale_value, discount_given, currency, "
                "language, quality_score, customer_objection, embedding, embedding_model, import_job_id) "
                "VALUES (%(t)s,%(dept)s,%(conversation_id)s,%(channel)s,%(scenario)s,%(customer_intent)s,%(customer_message)s,"
                "%(agent_response)s,%(sales_stage)s,%(product)s,%(outcome)s,%(sale_value)s,%(discount_given)s,%(currency)s,"
                "%(language)s,%(quality_score)s,%(customer_objection)s,%(emb)s,%(model)s,%(job)s) RETURNING id",
                {**{k: rec.get(k) for k in ("conversation_id", "channel", "scenario", "customer_intent", "customer_message",
                                            "agent_response", "sales_stage", "product", "outcome", "sale_value",
                                            "discount_given", "currency", "language", "quality_score", "customer_objection")},
                 "t": self.tenant, "dept": department_id, "emb": Vector(list(embedding)), "model": model,
                 "job": job_id}).fetchone()["id"]
