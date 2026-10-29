"""Client Brain S1 store: clients, typed memories with supersession, append-only events (owner spec 2026-10-29 §3, §4;
docs/CLIENT_BRAIN_GAP_ANALYSIS.md). Access is department-wide (owner default): `departments` is the caller's department set,
None = administrators (all departments). Every read and write checks it server-side."""
from __future__ import annotations

import json
from typing import Optional
from uuid import UUID

import psycopg

from ..client_memory.rules import current_facts, superseded_by, validate_memory
from ..permissions.access import PermissionDenied

_FIELDS = ("order_ref", "category", "statement", "value", "status", "source_type", "source_id", "source_text", "valid_until",
           "supersedes_memory_id")


class ClientMemoryStore:
    def __init__(self, pool, tenant_id: str) -> None:
        self.pool, self.tenant = pool, tenant_id

    # ---- clients ----
    def create_client(self, department_id: UUID, display_name: str, discord_handle: Optional[str], actor: Optional[UUID]) -> UUID:
        name = " ".join((display_name or "").split())[:120]
        if not name:
            raise ValueError("display name is required")
        handle = (discord_handle or "").strip()[:120] or None
        try:
            with self.pool.connection() as c:
                return c.execute("INSERT INTO clients (tenant_id, department_id, display_name, discord_handle, created_by) "
                                 "VALUES (%s,%s,%s,%s,%s) RETURNING id", (self.tenant, department_id, name, handle, actor)).fetchone()["id"]
        except psycopg.errors.UniqueViolation:
            raise ValueError("a client with this Discord handle already exists in this department") from None

    def _client(self, c, client_id: UUID, departments: Optional[set], lock: bool = False) -> dict:
        row = c.execute("SELECT * FROM clients WHERE tenant_id=%s AND id=%s" + (" FOR UPDATE" if lock else ""),
                        (self.tenant, client_id)).fetchone()
        if not row or (departments is not None and row["department_id"] not in departments):
            raise PermissionDenied("client not found")        # same answer for "missing" and "not yours": no existence leak
        return row

    def find_clients(self, text: str, departments: Optional[set], limit: int = 20) -> list[dict]:
        q = f"%{(text or '').strip().lower()}%"
        where, params = "tenant_id=%s AND (lower(display_name) LIKE %s OR lower(coalesce(discord_handle,'')) LIKE %s)", [self.tenant, q, q]
        if departments is not None:
            where += " AND department_id = ANY(%s)"
            params.append(list(departments))
        with self.pool.connection() as c:
            return c.execute(f"SELECT id, department_id, display_name, discord_handle, created_at FROM clients WHERE {where} "
                             f"ORDER BY display_name, created_at LIMIT %s", (*params, limit)).fetchall()

    # ---- memories ----
    def _event(self, c, client_id, memory_id, event, actor, detail=None) -> None:
        c.execute("INSERT INTO client_memory_events (tenant_id, client_id, memory_id, event, actor, detail) VALUES (%s,%s,%s,%s,%s,%s)",
                  (self.tenant, client_id, memory_id, event, actor, json.dumps(detail or {})))

    def add_memory(self, client_id: UUID, data: dict, actor: Optional[UUID], departments: Optional[set]) -> UUID:
        m = validate_memory({k: data.get(k) for k in _FIELDS if k in data})
        with self.pool.connection() as c, c.transaction():
            self._client(c, client_id, departments, lock=True)     # one writer per client at a time: supersession stays consistent
            existing = c.execute("SELECT * FROM client_memories WHERE client_id=%s AND superseded_by IS NULL AND deleted_at IS NULL",
                                 (client_id,)).fetchall()
            cols = [k for k in _FIELDS if m.get(k) is not None]
            mid = c.execute(f"INSERT INTO client_memories (tenant_id, client_id, created_by, {', '.join(cols)}) "
                            f"VALUES (%s,%s,%s,{', '.join(['%s'] * len(cols))}) RETURNING id",
                            (self.tenant, client_id, actor, *[m[k] for k in cols])).fetchone()["id"]
            self._event(c, client_id, mid, "created", actor, {"category": m["category"], "status": m["status"]})
            for old in superseded_by({**m, "id": mid}, existing):
                c.execute("UPDATE client_memories SET superseded_by=%s WHERE id=%s", (mid, old))
                self._event(c, client_id, old, "superseded", actor, {"by": str(mid)})
        return mid

    def _memory(self, c, memory_id: UUID, departments: Optional[set]) -> dict:
        row = c.execute("SELECT * FROM client_memories WHERE tenant_id=%s AND id=%s", (self.tenant, memory_id)).fetchone()
        if not row:
            raise PermissionDenied("memory not found")
        self._client(c, row["client_id"], departments, lock=True)
        return row

    def confirm_memory(self, memory_id: UUID, actor: Optional[UUID], departments: Optional[set]) -> None:
        with self.pool.connection() as c, c.transaction():
            row = self._memory(c, memory_id, departments)
            if row["deleted_at"] or row["superseded_by"]:
                raise ValueError("only a current fact can be confirmed")
            c.execute("UPDATE client_memories SET status='confirmed', reviewed_by=%s WHERE id=%s", (actor, memory_id))
            self._event(c, row["client_id"], memory_id, "confirmed", actor)

    def delete_memory(self, memory_id: UUID, actor: Optional[UUID], departments: Optional[set]) -> None:
        """Deletion request: the content is blanked everywhere it is stored; the row and an event without content remain."""
        with self.pool.connection() as c, c.transaction():
            row = self._memory(c, memory_id, departments)
            c.execute("UPDATE client_memories SET statement='', value='', source_text='', source_id='', deleted_at=now() "
                      "WHERE id=%s", (memory_id,))
            self._event(c, row["client_id"], memory_id, "deleted", actor)

    def history(self, client_id: UUID, departments: Optional[set]) -> list[dict]:
        with self.pool.connection() as c:
            self._client(c, client_id, departments)
            return c.execute("SELECT * FROM client_memories WHERE client_id=%s ORDER BY observed_at, created_at", (client_id,)).fetchall()

    def current(self, client_id: UUID, departments: Optional[set], order_ref: Optional[str] = None) -> list[dict]:
        return current_facts(self.history(client_id, departments), order_ref)

    def events(self, client_id: UUID, departments: Optional[set]) -> list[dict]:
        with self.pool.connection() as c:
            self._client(c, client_id, departments)
            return c.execute("SELECT * FROM client_memory_events WHERE client_id=%s ORDER BY id", (client_id,)).fetchall()
