"""Chat history (owner request: ChatGPT-style "new chat" and "previous chats"). Every query is scoped to the owner."""
from __future__ import annotations

from typing import Optional
from uuid import UUID

from psycopg.types.json import Jsonb


class ConversationStore:
    def __init__(self, pool, tenant_id: str) -> None:
        self.pool, self.tenant = pool, tenant_id

    def create(self, user_id: UUID, title: str, mode: Optional[str], department_id: Optional[UUID]) -> UUID:
        with self.pool.connection() as c:
            return c.execute("INSERT INTO conversations (tenant_id, user_id, title, mode, department_id) "
                             "VALUES (%s,%s,%s,%s,%s) RETURNING id",
                             (self.tenant, user_id, title, mode, department_id)).fetchone()["id"]

    def owns(self, user_id: UUID, conversation_id: UUID) -> bool:
        with self.pool.connection() as c:
            return c.execute("SELECT 1 FROM conversations WHERE tenant_id=%s AND id=%s AND user_id=%s",
                             (self.tenant, conversation_id, user_id)).fetchone() is not None

    def add_exchange(self, conversation_id: UUID, user_content: dict, assistant_content: dict) -> None:
        with self.pool.connection() as c, c.transaction():
            c.execute("INSERT INTO conversation_messages (conversation_id, role, content) VALUES (%s,'user',%s)",
                      (conversation_id, Jsonb(user_content)))
            c.execute("INSERT INTO conversation_messages (conversation_id, role, content) VALUES (%s,'assistant',%s)",
                      (conversation_id, Jsonb(assistant_content)))
            c.execute("UPDATE conversations SET updated_at=now() WHERE id=%s", (conversation_id,))

    def list(self, user_id: UUID, limit: int = 200) -> list[dict]:
        with self.pool.connection() as c:
            return c.execute("SELECT id, title, mode, created_at, updated_at FROM conversations "
                             "WHERE tenant_id=%s AND user_id=%s ORDER BY updated_at DESC LIMIT %s",
                             (self.tenant, user_id, limit)).fetchall()

    def search(self, user_id: UUID, query: str, limit: int = 50) -> list[dict]:
        """PRD §6 FR-CHAT-01 "search own conversation titles/messages". Only the owner's chats are ever searched (FR-CHAT-09)."""
        term = "".join(ch for ch in query if ch not in r"\%_").strip()      # LIKE wildcards and escapes are not special
        if not term:
            return []
        q = f"%{term}%"
        with self.pool.connection() as c:
            return c.execute(
                """WITH m AS (
                       SELECT m.conversation_id, m.id,
                              concat_ws(' ', m.content->>'text', m.content->>'answer',
                                        jsonb_path_query_array(m.content, '$.results[*].text')::text) AS body
                       FROM conversation_messages m JOIN conversations c2 ON c2.id = m.conversation_id
                       WHERE c2.tenant_id=%(t)s AND c2.user_id=%(u)s)
                   SELECT cv.id, cv.title, cv.mode, cv.created_at, cv.updated_at,
                          (SELECT left(m.body, 160) FROM m WHERE m.conversation_id = cv.id AND m.body ILIKE %(q)s
                            ORDER BY m.id DESC LIMIT 1) AS snippet
                   FROM conversations cv
                   WHERE cv.tenant_id=%(t)s AND cv.user_id=%(u)s
                     AND (cv.title ILIKE %(q)s OR EXISTS (SELECT 1 FROM m WHERE m.conversation_id = cv.id AND m.body ILIKE %(q)s))
                   ORDER BY cv.updated_at DESC LIMIT %(n)s""", {"q": q, "t": self.tenant, "u": user_id, "n": limit}).fetchall()

    def get(self, user_id: UUID, conversation_id: UUID) -> Optional[dict]:
        with self.pool.connection() as c:
            conv = c.execute("SELECT id, title, mode, department_id, created_at, updated_at FROM conversations "
                             "WHERE tenant_id=%s AND id=%s AND user_id=%s", (self.tenant, conversation_id, user_id)).fetchone()
            if not conv:
                return None
            conv["messages"] = c.execute("SELECT role, content, created_at FROM conversation_messages "
                                         "WHERE conversation_id=%s ORDER BY id", (conversation_id,)).fetchall()
            return conv

    def rename(self, user_id: UUID, conversation_id: UUID, title: str) -> bool:
        with self.pool.connection() as c:
            return c.execute("UPDATE conversations SET title=%s WHERE tenant_id=%s AND id=%s AND user_id=%s",
                             (title, self.tenant, conversation_id, user_id)).rowcount > 0

    def delete(self, user_id: UUID, conversation_id: UUID) -> bool:
        with self.pool.connection() as c:
            return c.execute("DELETE FROM conversations WHERE tenant_id=%s AND id=%s AND user_id=%s",
                             (self.tenant, conversation_id, user_id)).rowcount > 0

    def delete_all(self, user_id: UUID) -> int:
        with self.pool.connection() as c:
            return c.execute("DELETE FROM conversations WHERE tenant_id=%s AND user_id=%s", (self.tenant, user_id)).rowcount
