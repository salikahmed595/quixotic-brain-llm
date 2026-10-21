"""Integration identities (Obsidian) and once-only events — PRD §9 step 1, §12 `integration_identities`, ingestion events."""
from __future__ import annotations

from typing import Optional
from uuid import UUID


class IntegrationStore:
    def __init__(self, pool, tenant_id: str) -> None:
        self.pool, self.tenant = pool, tenant_id

    # ---- identities (§9 step 1: allowlisted platform accounts mapped to verified company users) ----
    def identities(self, platform: Optional[str] = None) -> list[dict]:
        with self.pool.connection() as c:
            return c.execute("SELECT i.id, i.platform, i.external_id, i.label, i.user_id, i.created_at, u.full_name, u.email, u.role, "
                             "u.account_status FROM integration_identities i JOIN users u ON u.id=i.user_id "
                             "WHERE i.tenant_id=%s AND (%s::text IS NULL OR i.platform=%s) ORDER BY i.platform, u.full_name",
                             (self.tenant, platform, platform)).fetchall()

    def add_identity(self, platform: str, external_id: str, user_id: UUID, label: Optional[str], actor: Optional[UUID]) -> UUID:
        with self.pool.connection() as c:
            return c.execute("INSERT INTO integration_identities (tenant_id, platform, external_id, user_id, label, created_by) "
                             "VALUES (%s,%s,%s,%s,%s,%s) RETURNING id", (self.tenant, platform, external_id, user_id, label, actor)).fetchone()["id"]

    def remove_identity(self, identity_id: UUID) -> bool:
        with self.pool.connection() as c:
            return c.execute("DELETE FROM integration_identities WHERE tenant_id=%s AND id=%s", (self.tenant, identity_id)).rowcount > 0

    def user_for(self, platform: str, external_id: str) -> Optional[dict]:
        """The ACTIVE company user mapped to this platform account, or None (deny by default, §3)."""
        with self.pool.connection() as c:
            return c.execute("SELECT u.* FROM integration_identities i JOIN users u ON u.id=i.user_id WHERE i.tenant_id=%s AND i.platform=%s "
                             "AND i.external_id=%s AND u.account_status='active'", (self.tenant, platform, str(external_id))).fetchone()

    def external_ids_for(self, user_id: UUID, platform: str) -> list[str]:
        with self.pool.connection() as c:
            return [r["external_id"] for r in c.execute("SELECT external_id FROM integration_identities WHERE tenant_id=%s AND user_id=%s "
                                                        "AND platform=%s", (self.tenant, user_id, platform))]

    # ---- once-only events (§12 "uniquely identify external bot events to prevent duplicate writes") ----
    def record_event(self, platform: str, event_id: str, kind: str, user_id: Optional[UUID] = None,
                     proposal_id: Optional[UUID] = None) -> bool:
        """True the first time this event is seen; False for a duplicate delivery."""
        with self.pool.connection() as c:
            return c.execute("INSERT INTO integration_events (tenant_id, platform, event_id, kind, user_id, proposal_id) "
                             "VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                             (self.tenant, platform, str(event_id), kind, user_id, proposal_id)).rowcount > 0

    def activity(self, platform: str, limit: int = 200) -> list[dict]:
        """Recent events per linked person (pushes, proposals, view refreshes, conflicts) with the proposal's current state."""
        with self.pool.connection() as c:
            return c.execute("SELECT e.kind, e.event_id, e.received_at, e.proposal_id, u.full_name, u.email, p.status AS proposal_status, "
                             "p.title AS proposal_title, p.kind AS proposal_kind FROM integration_events e LEFT JOIN users u ON u.id=e.user_id "
                             "LEFT JOIN knowledge_proposals p ON p.id=e.proposal_id WHERE e.tenant_id=%s AND e.platform=%s "
                             "ORDER BY e.received_at DESC, e.id DESC LIMIT %s", (self.tenant, platform, limit)).fetchall()
