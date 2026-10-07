"""Knowledge items, versions, workflow and chunks — PRD §12, §13, §14, §15."""
from __future__ import annotations

from typing import Optional, Sequence
from uuid import UUID

from pgvector import Vector
from psycopg.types.json import Jsonb

from ..permissions.workflow import ACTIVE, APPROVED, ARCHIVED, REJECTED

_VERSION_SELECT = """
SELECT v.id, v.item_id, v.version, v.status, v.body, v.language, v.access_level, v.source_file_id,
       v.created_by, v.created_at, v.reviewed_by, v.reviewed_at, v.updated_by, v.updated_at,
       i.title, i.category, i.document_type,
       COALESCE((SELECT array_agg(d.id ORDER BY d.name) FROM item_departments idp
                 JOIN departments d ON d.id=idp.department_id WHERE idp.item_id=i.id), '{}') AS department_ids,
       COALESCE((SELECT array_agg(d.name ORDER BY d.name) FROM item_departments idp
                 JOIN departments d ON d.id=idp.department_id WHERE idp.item_id=i.id), '{}') AS departments,
       f.filename, f.extension, f.size_bytes, f.s3_key, f.processing_status, f.processing_error
FROM knowledge_versions v
JOIN knowledge_items i ON i.id=v.item_id
LEFT JOIN source_files f ON f.id=v.source_file_id
"""


class KnowledgeStore:
    def __init__(self, pool, tenant_id: str) -> None:
        self.pool, self.tenant = pool, tenant_id

    # ---- create / read ----
    def create_item_with_first_version(self, title: str, category: Optional[str], document_type: Optional[str],
                                       department_ids: Sequence[UUID], body: Optional[str], language: Optional[str],
                                       access_level: Optional[str], source_file_id: Optional[UUID],
                                       actor_id: UUID) -> tuple[UUID, UUID]:
        with self.pool.connection() as c:
            item = c.execute("INSERT INTO knowledge_items (tenant_id, title, category, document_type, created_by) "
                             "VALUES (%s,%s,%s,%s,%s) RETURNING id",
                             (self.tenant, title, category, document_type, actor_id)).fetchone()["id"]
            for d in department_ids:
                c.execute("INSERT INTO item_departments (item_id, department_id) VALUES (%s,%s)", (item, d))
            vid = self._insert_version(c, item, 1, body, language, access_level, source_file_id, actor_id)
        return item, vid

    def create_new_version(self, item_id: UUID, body: Optional[str], language: Optional[str],
                           access_level: Optional[str], source_file_id: Optional[UUID], actor_id: UUID) -> UUID:
        """§15: a new version of an existing item (e.g. Discount Policy V2)."""
        with self.pool.connection() as c:
            n = c.execute("SELECT COALESCE(MAX(version),0)+1 AS n FROM knowledge_versions WHERE item_id=%s",
                          (item_id,)).fetchone()["n"]
            return self._insert_version(c, item_id, n, body, language, access_level, source_file_id, actor_id)

    @staticmethod
    def _insert_version(c, item_id, version, body, language, access_level, source_file_id, actor_id) -> UUID:
        vid = c.execute(
            "INSERT INTO knowledge_versions (item_id, version, body, language, access_level, source_file_id, "
            "created_by, updated_by) VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
            (item_id, version, body, language, access_level, source_file_id, actor_id, actor_id)).fetchone()["id"]
        c.execute("INSERT INTO knowledge_status_history (version_id, from_status, to_status, actor_id) "
                  "VALUES (%s,NULL,'draft',%s)", (vid, actor_id))
        return vid

    def get_version(self, version_id: UUID) -> Optional[dict]:
        with self.pool.connection() as c:
            return c.execute(_VERSION_SELECT + " WHERE i.tenant_id=%s AND v.id=%s", (self.tenant, version_id)).fetchone()

    def list_versions(self, statuses: Optional[Sequence[str]] = None, department_ids: Optional[frozenset[UUID]] = None,
                      only_files: bool = False, limit: int = 50, offset: int = 0) -> list[dict]:
        where, params = ["i.tenant_id=%(t)s"], {"t": self.tenant, "limit": limit, "offset": offset}
        if statuses:
            where.append("v.status = ANY(%(st)s)"); params["st"] = list(statuses)
        if department_ids is not None:     # None = unrestricted (administrator)
            where.append("EXISTS (SELECT 1 FROM item_departments x WHERE x.item_id=i.id AND x.department_id = ANY(%(d)s))")
            params["d"] = list(department_ids)
        if only_files:
            where.append("v.source_file_id IS NOT NULL")
        with self.pool.connection() as c:
            return c.execute(_VERSION_SELECT + " WHERE " + " AND ".join(where) +
                             " ORDER BY v.updated_at DESC LIMIT %(limit)s OFFSET %(offset)s", params).fetchall()

    def update_draft(self, version_id: UUID, actor_id: UUID, body: Optional[str] = None,
                     access_level: Optional[str] = None) -> None:
        with self.pool.connection() as c:
            c.execute("UPDATE knowledge_versions SET body=COALESCE(%s,body), access_level=COALESCE(%s,access_level), "
                      "updated_by=%s, updated_at=now() WHERE id=%s AND status='draft'",
                      (body, access_level, actor_id, version_id))

    # ---- workflow (§12.3) ----
    def transition(self, version_id: UUID, to_status: str, actor_id: Optional[UUID], note: Optional[str] = None) -> str:
        """Move a version to `to_status` atomically. Returns the previous status.
        §15: activating a version archives the item's previously active version."""
        with self.pool.connection() as c, c.transaction():
            row = c.execute("SELECT status, item_id FROM knowledge_versions WHERE id=%s FOR UPDATE", (version_id,)).fetchone()
            prev = row["status"]
            if to_status == ACTIVE:
                for old in c.execute("SELECT id FROM knowledge_versions WHERE item_id=%s AND status='active' AND id<>%s "
                                     "FOR UPDATE", (row["item_id"], version_id)).fetchall():
                    c.execute("UPDATE knowledge_versions SET status='archived', updated_at=now(), updated_by=%s WHERE id=%s",
                              (actor_id, old["id"]))
                    c.execute("INSERT INTO knowledge_status_history (version_id, from_status, to_status, actor_id, note) "
                              "VALUES (%s,'active','archived',%s,%s)", (old["id"], actor_id, "superseded by a newer active version"))
            reviewed = to_status in (APPROVED, REJECTED)
            c.execute("UPDATE knowledge_versions SET status=%s, updated_at=now(), updated_by=%s, "
                      "reviewed_by=CASE WHEN %s THEN %s ELSE reviewed_by END, "
                      "reviewed_at=CASE WHEN %s THEN now() ELSE reviewed_at END WHERE id=%s",
                      (to_status, actor_id, reviewed, actor_id, reviewed, version_id))
            c.execute("INSERT INTO knowledge_status_history (version_id, from_status, to_status, actor_id, note) "
                      "VALUES (%s,%s,%s,%s,%s)", (version_id, prev, to_status, actor_id, note))
            c.execute("UPDATE chunks SET metadata = jsonb_set(metadata, '{status}', to_jsonb(%s::text)) WHERE version_id=%s",
                      (to_status, version_id))      # PRD §14 metadata snapshot must not show a stale status
        return prev

    def history(self, version_id: UUID) -> list[dict]:
        with self.pool.connection() as c:
            return c.execute("SELECT from_status, to_status, actor_id, note, at FROM knowledge_status_history "
                             "WHERE version_id=%s ORDER BY id", (version_id,)).fetchall()

    def delete_version(self, version_id: UUID) -> Optional[dict]:
        """Remove a version (and its chunks). If it was the item's only version the item goes too.
        Returns the source file row (so the caller can delete the S3 object)."""
        with self.pool.connection() as c, c.transaction():
            v = c.execute("SELECT item_id, source_file_id FROM knowledge_versions WHERE id=%s", (version_id,)).fetchone()
            if not v:
                return None
            f = (c.execute("SELECT * FROM source_files WHERE id=%s", (v["source_file_id"],)).fetchone()
                 if v["source_file_id"] else None)
            c.execute("DELETE FROM knowledge_versions WHERE id=%s", (version_id,))
            if not c.execute("SELECT 1 FROM knowledge_versions WHERE item_id=%s", (v["item_id"],)).fetchone():
                c.execute("DELETE FROM knowledge_items WHERE id=%s", (v["item_id"],))
            if f:
                c.execute("DELETE FROM source_files WHERE id=%s", (f["id"],))
        return f

    # ---- source files (§13, §46) ----
    def create_source_file(self, file_id: UUID, filename: str, extension: str, size_bytes: int, s3_key: str,
                           uploaded_by: UUID) -> None:
        with self.pool.connection() as c:
            c.execute("INSERT INTO source_files (id, tenant_id, filename, extension, size_bytes, s3_key, uploaded_by) "
                      "VALUES (%s,%s,%s,%s,%s,%s,%s)", (file_id, self.tenant, filename, extension, size_bytes, s3_key, uploaded_by))

    def set_file_status(self, file_id: UUID, status: str, error: Optional[str] = None) -> None:
        with self.pool.connection() as c:
            c.execute("UPDATE source_files SET processing_status=%s, processing_error=%s WHERE id=%s", (status, error, file_id))

    # ---- ingestion support ----
    def version_bundle(self, version_id: UUID) -> dict:
        v = self.get_version(version_id)
        if v is None:
            raise LookupError(f"knowledge version {version_id} not found")
        return {**v, "source_file_id": v["source_file_id"]}

    def replace_chunks(self, version_id: UUID, rows: Sequence[dict]) -> None:
        with self.pool.connection() as c, c.transaction():
            c.execute("DELETE FROM chunks WHERE version_id=%s", (version_id,))
            for r in rows:
                c.execute("INSERT INTO chunks (tenant_id, version_id, chunk_index, section, text, metadata, embedding, "
                          "embedding_model) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                          (self.tenant, version_id, r["chunk_index"], r["section"], r["text"], Jsonb(r["metadata"]),
                           Vector(r["embedding"]), r["embedding_model"]))

    def all_version_ids_with_content(self) -> list[UUID]:
        """For §24.2 re-indexing after an embedding-model change."""
        with self.pool.connection() as c:
            return [r["id"] for r in c.execute(
                "SELECT v.id FROM knowledge_versions v JOIN knowledge_items i ON i.id=v.item_id "
                "WHERE i.tenant_id=%s AND (v.body IS NOT NULL OR v.source_file_id IS NOT NULL) ORDER BY v.created_at",
                (self.tenant,))]
