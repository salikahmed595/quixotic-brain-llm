"""Knowledge documents, versions, proposals, approval decisions and chunks — PRD §7, §8, §12.

Documents (`knowledge_items`) carry the access metadata (departments, sensitivity) that retrieval filters on. Every change is a
proposal (`knowledge_proposals`) that publishes one version; a document has at most one Published version (§8)."""
from __future__ import annotations

from typing import Optional, Sequence
from uuid import UUID

from pgvector import Vector
from psycopg.types.json import Jsonb

DRAFT, UNDER_REVIEW, APPROVED, PUBLISHED, ARCHIVED = "draft", "under_review", "approved", "published", "archived"
STATUSES = (DRAFT, UNDER_REVIEW, APPROVED, PUBLISHED, ARCHIVED)          # PRD §8

_DEPTS = """COALESCE((SELECT array_agg(d.id ORDER BY d.name) FROM item_departments x JOIN departments d ON d.id=x.department_id
                     WHERE x.item_id=i.id), '{}') AS department_ids,
            COALESCE((SELECT array_agg(d.name ORDER BY d.name) FROM item_departments x JOIN departments d ON d.id=x.department_id
                     WHERE x.item_id=i.id), '{}') AS departments"""

_VERSION_SELECT = f"""
SELECT v.id, v.item_id, v.version, v.status, v.body, v.language, v.source_file_id, v.effective_date, v.expires_at,
       v.checksum, v.indexed_checksum, v.indexed_at, v.change_note, v.vault_commit,
       v.created_by, v.created_at, v.approved_by, v.approved_at, v.published_by, v.published_at, v.updated_at,
       i.title, i.category, i.document_type, i.sensitivity, i.owner_id, i.provenance, i.vault_path, {_DEPTS},
       f.filename, f.extension, f.size_bytes, f.s3_key, f.processing_status, f.processing_error,
       (SELECT count(*) FROM chunks c WHERE c.version_id=v.id) AS chunk_count
FROM knowledge_versions v
JOIN knowledge_items i ON i.id=v.item_id
LEFT JOIN source_files f ON f.id=v.source_file_id
"""

_PROPOSAL_SELECT = """
SELECT p.*, s.full_name AS submitted_by_name,
       v.version, v.status AS version_status, v.body, v.source_file_id, v.effective_date, v.expires_at, v.checksum, v.indexed_checksum,
       f.filename, f.processing_status, f.processing_error,
       COALESCE((SELECT array_agg(d.name ORDER BY d.name) FROM item_departments x JOIN departments d ON d.id=x.department_id
                 WHERE x.item_id=p.item_id), '{}') AS current_departments
FROM knowledge_proposals p
JOIN knowledge_versions v ON v.id=p.version_id
LEFT JOIN users s ON s.id=p.submitted_by
LEFT JOIN source_files f ON f.id=v.source_file_id
"""


class KnowledgeStore:
    def __init__(self, pool, tenant_id: str) -> None:
        self.pool, self.tenant = pool, tenant_id

    # ---- documents and versions ----
    def create_document(self, title: str, category: Optional[str], department_ids: Sequence[UUID], sensitivity: str,
                        owner_id: Optional[UUID], provenance: Optional[str], actor_id: Optional[UUID],
                        document_type: Optional[str] = None) -> UUID:
        with self.pool.connection() as c, c.transaction():
            item = c.execute("INSERT INTO knowledge_items (tenant_id, title, category, document_type, sensitivity, owner_id, provenance, "
                             "created_by) VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
                             (self.tenant, title, category, document_type, sensitivity, owner_id, provenance, actor_id)).fetchone()["id"]
            for d in department_ids:
                c.execute("INSERT INTO item_departments (item_id, department_id) VALUES (%s,%s)", (item, d))
        return item

    def apply_meta(self, c, item_id: UUID, meta: dict) -> None:
        """Proposed metadata takes effect only when its proposal is published (inside the publication transaction)."""
        for col in ("title", "category", "sensitivity", "provenance", "document_type"):
            if col in meta and meta[col] is not None:
                c.execute(f"UPDATE knowledge_items SET {col}=%s WHERE id=%s", (meta[col], item_id))
        if "owner_id" in meta:
            c.execute("UPDATE knowledge_items SET owner_id=%s WHERE id=%s", (meta["owner_id"], item_id))
        if meta.get("department_ids"):
            c.execute("DELETE FROM item_departments WHERE item_id=%s", (item_id,))
            for d in meta["department_ids"]:
                c.execute("INSERT INTO item_departments (item_id, department_id) VALUES (%s,%s)", (item_id, d))

    def create_version(self, item_id: UUID, body: Optional[str], source_file_id: Optional[UUID], actor_id: Optional[UUID],
                       effective_date=None, expires_at=None, change_note: Optional[str] = None, language: Optional[str] = None,
                       checksum: Optional[str] = None, status: str = DRAFT) -> UUID:
        with self.pool.connection() as c, c.transaction():
            c.execute("SELECT id FROM knowledge_items WHERE id=%s FOR UPDATE", (item_id,))
            n = c.execute("SELECT COALESCE(MAX(version),0)+1 AS n FROM knowledge_versions WHERE item_id=%s", (item_id,)).fetchone()["n"]
            vid = c.execute(
                "INSERT INTO knowledge_versions (item_id, version, status, body, language, source_file_id, effective_date, expires_at, "
                "change_note, checksum, created_by, updated_by) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
                (item_id, n, status, body, language, source_file_id, effective_date, expires_at, change_note, checksum,
                 actor_id, actor_id)).fetchone()["id"]
            c.execute("INSERT INTO knowledge_status_history (version_id, from_status, to_status, actor_id) VALUES (%s,NULL,%s,%s)",
                      (vid, status, actor_id))
        return vid

    def get_version(self, version_id: UUID) -> Optional[dict]:
        with self.pool.connection() as c:
            return c.execute(_VERSION_SELECT + " WHERE i.tenant_id=%s AND v.id=%s", (self.tenant, version_id)).fetchone()

    def get_item(self, item_id: UUID) -> Optional[dict]:
        with self.pool.connection() as c:
            return c.execute(f"SELECT i.*, {_DEPTS}, o.full_name AS owner_name FROM knowledge_items i "
                             "LEFT JOIN users o ON o.id=i.owner_id WHERE i.tenant_id=%s AND i.id=%s", (self.tenant, item_id)).fetchone()

    def published_version(self, item_id: UUID) -> Optional[dict]:
        with self.pool.connection() as c:
            return c.execute(_VERSION_SELECT + " WHERE i.tenant_id=%s AND v.item_id=%s AND v.status='published'",
                             (self.tenant, item_id)).fetchone()

    def versions_of(self, item_id: UUID) -> list[dict]:
        with self.pool.connection() as c:
            return c.execute("SELECT v.id, v.version, v.status, v.created_at, v.published_at, v.change_note, v.effective_date, v.expires_at, "
                             "v.checksum, v.vault_commit, a.full_name AS approved_by_name, p.full_name AS published_by_name "
                             "FROM knowledge_versions v LEFT JOIN users a ON a.id=v.approved_by LEFT JOIN users p ON p.id=v.published_by "
                             "WHERE v.item_id=%s ORDER BY v.version DESC", (item_id,)).fetchall()

    def list_documents(self, department_ids: Optional[frozenset] = None, levels: Optional[frozenset] = None, *,
                       status: Optional[str] = None, q: Optional[str] = None, category: Optional[str] = None,
                       department_id: Optional[UUID] = None, limit: int = 100, offset: int = 0) -> list[dict]:
        """Documents with their published version (or newest version when none is published). `department_ids` / `levels`
        None = unrestricted; otherwise only documents in those departments and sensitivity levels (§3 deny by default)."""
        where, params = ["i.tenant_id=%(t)s"], {"t": self.tenant, "limit": limit, "offset": offset}
        if department_ids is not None:
            where.append("EXISTS (SELECT 1 FROM item_departments x WHERE x.item_id=i.id AND x.department_id = ANY(%(d)s))")
            params["d"] = list(department_ids)
        if levels is not None:
            where.append("i.sensitivity = ANY(%(lv)s)"); params["lv"] = list(levels)
        if department_id is not None:
            where.append("EXISTS (SELECT 1 FROM item_departments x WHERE x.item_id=i.id AND x.department_id=%(dd)s)")
            params["dd"] = department_id
        if category:
            where.append("lower(i.category)=lower(%(cat)s)"); params["cat"] = category
        if q:
            where.append("(i.title ILIKE %(q)s OR v.body ILIKE %(q)s)"); params["q"] = f"%{q}%"
        if status:
            where.append("v.status=%(st)s"); params["st"] = status
        sql = (f"""SELECT DISTINCT ON (i.id) i.id AS item_id, i.title, i.category, i.sensitivity, i.owner_id, i.provenance, i.vault_path,
                   {_DEPTS}, v.id AS version_id, v.version, v.status, v.effective_date, v.expires_at, v.published_at, v.updated_at,
                   v.indexed_checksum = v.checksum AS indexed, f.filename, f.processing_status, o.full_name AS owner_name,
                   (SELECT count(*) FROM knowledge_proposals p WHERE p.item_id=i.id AND p.status IN ('open','approved','publishing')) AS open_proposals
                   FROM knowledge_items i JOIN knowledge_versions v ON v.item_id=i.id
                   LEFT JOIN source_files f ON f.id=v.source_file_id LEFT JOIN users o ON o.id=i.owner_id
                   WHERE {' AND '.join(where)}
                   ORDER BY i.id, (v.status='published') DESC, v.version DESC""")
        with self.pool.connection() as c:
            rows = c.execute(f"SELECT * FROM ({sql}) d ORDER BY d.title LIMIT %(limit)s OFFSET %(offset)s", params).fetchall()
        return rows

    def classify_unclassified(self, item_ids: Sequence[UUID], sensitivity: str) -> int:
        """Give documents that were never classified (created before M3) their first access level. Only 'unclassified' rows
        change; chunk ACL snapshots follow."""
        with self.pool.connection() as c, c.transaction():
            ids = [r["id"] for r in c.execute("UPDATE knowledge_items SET sensitivity=%s WHERE tenant_id=%s AND id = ANY(%s) "
                                             "AND sensitivity='unclassified' RETURNING id", (sensitivity, self.tenant, list(item_ids)))]
            if ids:
                c.execute("UPDATE chunks SET metadata = metadata || jsonb_build_object('sensitivity', %s::text) "
                          "FROM knowledge_versions v WHERE chunks.version_id=v.id AND v.item_id = ANY(%s)", (sensitivity, ids))
        return len(ids)

    def categories(self) -> list[str]:
        with self.pool.connection() as c:
            return [r["category"] for r in c.execute("SELECT DISTINCT category FROM knowledge_items WHERE tenant_id=%s AND category IS NOT NULL "
                                                     "ORDER BY category", (self.tenant,))]

    def update_draft(self, version_id: UUID, actor_id: UUID, body: Optional[str], checksum: Optional[str],
                     effective_date=None, expires_at=None, change_note: Optional[str] = None) -> bool:
        with self.pool.connection() as c:
            return c.execute("UPDATE knowledge_versions SET body=COALESCE(%s,body), checksum=COALESCE(%s,checksum), "
                             "effective_date=%s, expires_at=%s, change_note=COALESCE(%s,change_note), indexed_checksum=NULL, "
                             "updated_by=%s, updated_at=now() WHERE id=%s AND status='draft'",
                             (body, checksum, effective_date, expires_at, change_note, actor_id, version_id)).rowcount > 0

    def set_text(self, version_id: UUID, body: str, checksum: str) -> None:
        """Extracted text of an uploaded file (reviewers read and diff it; the vault stores it)."""
        with self.pool.connection() as c:
            c.execute("UPDATE knowledge_versions SET body=%s, checksum=%s WHERE id=%s", (body, checksum, version_id))

    def mark_indexed(self, version_id: UUID, checksum: Optional[str]) -> None:
        with self.pool.connection() as c:
            c.execute("UPDATE knowledge_versions SET indexed_checksum=%s, indexed_at=now() WHERE id=%s", (checksum, version_id))

    def set_status(self, version_id: UUID, to_status: str, actor_id: Optional[UUID], note: Optional[str] = None,
                   c=None) -> str:
        def run(conn):
            prev = conn.execute("SELECT status FROM knowledge_versions WHERE id=%s FOR UPDATE", (version_id,)).fetchone()["status"]
            conn.execute("UPDATE knowledge_versions SET status=%s, updated_at=now(), updated_by=%s WHERE id=%s", (to_status, actor_id, version_id))
            conn.execute("INSERT INTO knowledge_status_history (version_id, from_status, to_status, actor_id, note) VALUES (%s,%s,%s,%s,%s)",
                         (version_id, prev, to_status, actor_id, note))
            conn.execute("UPDATE chunks SET metadata = jsonb_set(metadata, '{status}', to_jsonb(%s::text)) WHERE version_id=%s",
                         (to_status, version_id))
            return prev
        if c is not None:
            return run(c)
        with self.pool.connection() as conn, conn.transaction():
            return run(conn)

    def history(self, version_id: UUID) -> list[dict]:
        with self.pool.connection() as c:
            return c.execute("SELECT h.from_status, h.to_status, h.note, h.at, u.full_name AS actor FROM knowledge_status_history h "
                             "LEFT JOIN users u ON u.id=h.actor_id WHERE h.version_id=%s ORDER BY h.id", (version_id,)).fetchall()

    def switch_published(self, item_id: UUID, version_id: Optional[UUID], actor_id: Optional[UUID], meta: dict,
                         vault_path: Optional[str], vault_commit: Optional[str], approved_by: Optional[UUID]) -> Optional[UUID]:
        """PRD §8 controlled publication transaction: the previous published version is archived and `version_id` becomes the
        only published one, in ONE transaction, together with the proposed metadata. `version_id` None archives the document.
        Returns the version that was published before (for rollback)."""
        with self.pool.connection() as c, c.transaction():
            c.execute("SELECT id FROM knowledge_items WHERE id=%s FOR UPDATE", (item_id,))
            old = c.execute("SELECT id FROM knowledge_versions WHERE item_id=%s AND status='published'", (item_id,)).fetchone()
            old_id = old["id"] if old else None
            if old_id and old_id != version_id:
                self.set_status(old_id, ARCHIVED, actor_id, "replaced by a newer version" if version_id else "document archived", c=c)
            if version_id and old_id != version_id:
                self.set_status(version_id, PUBLISHED, actor_id, "published", c=c)
                c.execute("UPDATE knowledge_versions SET published_by=%s, published_at=now(), approved_by=COALESCE(%s, approved_by), "
                          "approved_at=COALESCE(approved_at, now()), vault_commit=%s WHERE id=%s",
                          (actor_id, approved_by, vault_commit, version_id))
            self.apply_meta(c, item_id, meta)
            c.execute("UPDATE knowledge_items SET vault_path=COALESCE(%s, vault_path) WHERE id=%s", (vault_path, item_id))
            if version_id:                                    # chunk ACL snapshot follows the published metadata (§8)
                c.execute("UPDATE chunks SET metadata = metadata || jsonb_build_object('sensitivity', i.sensitivity) "
                          "FROM knowledge_versions v JOIN knowledge_items i ON i.id=v.item_id WHERE chunks.version_id=v.id AND v.id=%s",
                          (version_id,))
        return old_id

    def restore_published(self, item_id: UUID, previous: Optional[UUID], failed: Optional[UUID], actor_id: Optional[UUID]) -> None:
        """Undo a publication whose retrieval check failed: the previous version is published again (§8 fail closed)."""
        with self.pool.connection() as c, c.transaction():
            c.execute("SELECT id FROM knowledge_items WHERE id=%s FOR UPDATE", (item_id,))
            if failed:
                self.set_status(failed, APPROVED, actor_id, "publication rolled back", c=c)
            if previous:
                self.set_status(previous, PUBLISHED, actor_id, "restored after a failed publication", c=c)

    def delete_draft_document(self, item_id: UUID) -> Optional[dict]:
        """Removes a document that was never published (all versions drafts). Returns its source file rows' keys."""
        with self.pool.connection() as c, c.transaction():
            if c.execute("SELECT 1 FROM knowledge_versions WHERE item_id=%s AND status IN ('published','archived')", (item_id,)).fetchone():
                return None
            files = c.execute("SELECT f.id, f.s3_key FROM knowledge_versions v JOIN source_files f ON f.id=v.source_file_id "
                              "WHERE v.item_id=%s", (item_id,)).fetchall()
            c.execute("DELETE FROM knowledge_items WHERE id=%s", (item_id,))
            for f in files:
                c.execute("DELETE FROM source_files WHERE id=%s", (f["id"],))
            return {"files": files}

    # ---- proposals and decisions (§7 Approvals, §12) ----
    def create_proposal(self, *, kind: str, item_id: UUID, version_id: UUID, base_version_id: Optional[UUID], title: str,
                        summary: Optional[str], meta: dict, source: str, source_ref: Optional[str], submitted_by: Optional[UUID],
                        high_impact: bool, required_approvals: int, gap_id: Optional[UUID] = None) -> UUID:
        with self.pool.connection() as c:
            return c.execute(
                "INSERT INTO knowledge_proposals (tenant_id, kind, item_id, version_id, base_version_id, title, summary, meta, source, "
                "source_ref, submitted_by, high_impact, required_approvals, gap_id) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                "RETURNING id",
                (self.tenant, kind, item_id, version_id, base_version_id, title, summary, Jsonb(meta), source, source_ref, submitted_by,
                 high_impact, required_approvals, gap_id)).fetchone()["id"]

    def proposal_by_ref(self, source: str, source_ref: str) -> Optional[dict]:
        with self.pool.connection() as c:
            return c.execute("SELECT * FROM knowledge_proposals WHERE tenant_id=%s AND source=%s AND source_ref=%s",
                             (self.tenant, source, source_ref)).fetchone()

    def get_proposal(self, proposal_id: UUID) -> Optional[dict]:
        with self.pool.connection() as c:
            return c.execute(_PROPOSAL_SELECT + " WHERE p.tenant_id=%s AND p.id=%s", (self.tenant, proposal_id)).fetchone()

    def list_proposals(self, statuses: Optional[Sequence[str]] = None, item_id: Optional[UUID] = None, limit: int = 200) -> list[dict]:
        where, params = ["p.tenant_id=%(t)s"], {"t": self.tenant, "limit": limit}
        if statuses:
            where.append("p.status = ANY(%(s)s)"); params["s"] = list(statuses)
        if item_id:
            where.append("p.item_id=%(i)s"); params["i"] = item_id
        with self.pool.connection() as c:
            return c.execute(_PROPOSAL_SELECT + " WHERE " + " AND ".join(where) + " ORDER BY p.submitted_at DESC LIMIT %(limit)s",
                             params).fetchall()

    def set_proposal_status(self, proposal_id: UUID, status: str, error: Optional[str] = None, expect: Optional[Sequence[str]] = None) -> bool:
        with self.pool.connection() as c:
            return c.execute(
                "UPDATE knowledge_proposals SET status=%s, error=%s, "
                "decided_at=CASE WHEN %s IN ('approved','rejected','changes_requested','withdrawn') THEN now() ELSE decided_at END, "
                "published_at=CASE WHEN %s='published' THEN now() ELSE published_at END "
                "WHERE id=%s AND (%s::text[] IS NULL OR status = ANY(%s::text[]))",
                (status, error, status, status, proposal_id, list(expect) if expect else None, list(expect) if expect else None)).rowcount > 0

    def add_decision(self, proposal_id: UUID, user_id: UUID, decision: str, note: Optional[str], via: str) -> bool:
        with self.pool.connection() as c:
            return c.execute("INSERT INTO approval_decisions (proposal_id, decided_by, decision, note, via) VALUES (%s,%s,%s,%s,%s) "
                             "ON CONFLICT DO NOTHING", (proposal_id, user_id, decision, note, via)).rowcount > 0

    def decisions(self, proposal_id: UUID) -> list[dict]:
        with self.pool.connection() as c:
            return c.execute("SELECT d.decided_by, u.full_name, u.role, u.can_publish, d.decision, d.note, d.via, d.at "
                             "FROM approval_decisions d JOIN users u ON u.id=d.decided_by WHERE d.proposal_id=%s ORDER BY d.at",
                             (proposal_id,)).fetchall()

    def open_proposals_for_version(self, version_id: UUID) -> list[dict]:
        with self.pool.connection() as c:
            return c.execute("SELECT * FROM knowledge_proposals WHERE version_id=%s AND status='open'", (version_id,)).fetchall()

    def raise_to_high_impact(self, proposal_id: UUID) -> None:
        """Only ever raises the review requirement (a parsed file revealed a high-impact topic); never lowers it."""
        with self.pool.connection() as c:
            c.execute("UPDATE knowledge_proposals SET high_impact=true, required_approvals=GREATEST(required_approvals, 2) "
                      "WHERE id=%s AND status='open'", (proposal_id,))

    def open_proposal_for(self, item_id: UUID) -> Optional[dict]:
        with self.pool.connection() as c:
            return c.execute("SELECT * FROM knowledge_proposals WHERE item_id=%s AND status IN ('open','approved','publishing') "
                             "ORDER BY submitted_at DESC LIMIT 1", (item_id,)).fetchone()

    # ---- source files ----
    def create_source_file(self, file_id: UUID, filename: str, extension: str, size_bytes: int, s3_key: str,
                           uploaded_by: Optional[UUID]) -> None:
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
        return v

    def replace_chunks(self, version_id: UUID, rows: Sequence[dict]) -> None:
        with self.pool.connection() as c, c.transaction():
            c.execute("DELETE FROM chunks WHERE version_id=%s", (version_id,))
            for r in rows:
                c.execute("INSERT INTO chunks (tenant_id, version_id, chunk_index, section, text, metadata, embedding, "
                          "embedding_model) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                          (self.tenant, version_id, r["chunk_index"], r["section"], r["text"], Jsonb(r["metadata"]),
                           Vector(r["embedding"]), r["embedding_model"]))

    def all_version_ids_with_content(self) -> list[UUID]:
        """Versions to rebuild after an embedding-model change: published ones and those waiting for review."""
        with self.pool.connection() as c:
            return [r["id"] for r in c.execute(
                "SELECT v.id FROM knowledge_versions v JOIN knowledge_items i ON i.id=v.item_id "
                "WHERE i.tenant_id=%s AND v.status IN ('published','under_review','approved') "
                "AND (v.body IS NOT NULL OR v.source_file_id IS NOT NULL) ORDER BY v.created_at", (self.tenant,))]

    def first_chunk(self, version_id: UUID) -> Optional[dict]:
        with self.pool.connection() as c:
            return c.execute("SELECT id, text, embedding FROM chunks WHERE version_id=%s ORDER BY chunk_index LIMIT 1", (version_id,)).fetchone()

    def related_documents(self, version_id: UUID, department_ids: Optional[frozenset], levels: frozenset, limit: int = 3) -> list[dict]:
        """Published documents whose passages are closest to this version's — shown to reviewers as possible conflicts or
        duplicates (§7 Approvals "references, conflicts"; §9 step 4). No threshold: the reviewer judges. Only documents the
        reviewer may see are listed (`department_ids` None = every department), so titles never leak (§13 AT-05)."""
        with self.pool.connection() as c:
            return c.execute(
                """SELECT i.id AS item_id, i.title, v.version, max(1 - (o.embedding <=> c.embedding)) AS similarity
                   FROM chunks c
                   JOIN knowledge_versions me ON me.id = c.version_id
                   JOIN chunks o ON o.version_id <> c.version_id AND o.embedding_model = c.embedding_model
                   JOIN knowledge_versions v ON v.id = o.version_id AND v.status = 'published' AND v.item_id <> me.item_id
                   JOIN knowledge_items i ON i.id = v.item_id
                   WHERE c.version_id = %(v)s AND i.sensitivity = ANY(%(lv)s)
                     AND (%(all)s OR EXISTS (SELECT 1 FROM item_departments x WHERE x.item_id = i.id AND x.department_id = ANY(%(d)s)))
                   GROUP BY i.id, i.title, v.version ORDER BY similarity DESC LIMIT %(n)s""",
                {"v": version_id, "lv": list(levels), "all": department_ids is None, "d": list(department_ids or []), "n": limit}).fetchall()
