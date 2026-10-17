"""Server-side sessions, one-time links and system settings — PRD §5 FR-AUTH-02/05/06, §12 `sessions`, `system_settings`.

Only SHA-256 hashes of session tokens and one-time links are stored, so a database copy cannot be used to sign in."""
from __future__ import annotations

import secrets
from typing import Any, Optional
from uuid import UUID

from psycopg.types.json import Jsonb

from ..auth.security import new_token, token_hash


class SessionStore:
    def __init__(self, pool, tenant_id: str) -> None:
        self.pool, self.tenant = pool, tenant_id

    def create(self, user_id: UUID, ttl_seconds: int, mfa_passed: bool, ip: Optional[str] = None,
               user_agent: Optional[str] = None) -> tuple[str, str]:
        """Returns (session_token, csrf_token). The session token is only ever sent in an HttpOnly cookie."""
        token, csrf = new_token(), secrets.token_urlsafe(24)
        with self.pool.connection() as c:
            c.execute("INSERT INTO sessions (tenant_id, user_id, token_hash, csrf_token, mfa_passed, expires_at, ip, user_agent) "
                      "VALUES (%s,%s,%s,%s,%s, now() + make_interval(secs => %s), %s, %s)",
                      (self.tenant, user_id, token_hash(token), csrf, mfa_passed, ttl_seconds, ip, (user_agent or "")[:300]))
        return token, csrf

    def lookup(self, token: str) -> Optional[dict]:
        """A live session (not revoked, not expired), or None."""
        with self.pool.connection() as c:
            return c.execute("UPDATE sessions SET last_seen_at=now() WHERE tenant_id=%s AND token_hash=%s "
                             "AND revoked_at IS NULL AND expires_at > now() "
                             "RETURNING id, user_id, csrf_token, mfa_passed, expires_at",
                             (self.tenant, token_hash(token))).fetchone()

    def mark_mfa_passed(self, session_id: UUID) -> None:
        with self.pool.connection() as c:
            c.execute("UPDATE sessions SET mfa_passed=true WHERE id=%s", (session_id,))

    def revoke(self, session_id: UUID) -> None:
        with self.pool.connection() as c:
            c.execute("UPDATE sessions SET revoked_at=now() WHERE id=%s AND revoked_at IS NULL", (session_id,))

    def revoke_user(self, user_id: UUID, except_session: Optional[UUID] = None) -> int:
        """PRD §5 FR-AUTH-05: suspending (or rejecting, deactivating, resetting a password) revokes sessions at once."""
        with self.pool.connection() as c:
            return c.execute("UPDATE sessions SET revoked_at=now() WHERE tenant_id=%s AND user_id=%s AND revoked_at IS NULL "
                             "AND id IS DISTINCT FROM %s", (self.tenant, user_id, except_session)).rowcount

    def active_count(self) -> int:
        with self.pool.connection() as c:
            return c.execute("SELECT count(DISTINCT user_id) AS n FROM sessions WHERE tenant_id=%s AND revoked_at IS NULL "
                             "AND expires_at > now()", (self.tenant,)).fetchone()["n"]


class OneTimeTokenStore:
    """Email verification and password reset links (PRD §5 FR-AUTH-02, FR-AUTH-06)."""

    def __init__(self, pool) -> None:
        self.pool = pool

    def issue(self, user_id: UUID, purpose: str, ttl_seconds: int) -> str:
        token = new_token()
        with self.pool.connection() as c, c.transaction():
            # Only the newest link of each kind works.
            c.execute("UPDATE auth_tokens SET used_at=now() WHERE user_id=%s AND purpose=%s AND used_at IS NULL", (user_id, purpose))
            c.execute("INSERT INTO auth_tokens (user_id, purpose, token_hash, expires_at) "
                      "VALUES (%s,%s,%s, now() + make_interval(secs => %s))", (user_id, purpose, token_hash(token), ttl_seconds))
        return token

    def consume(self, token: str, purpose: str) -> Optional[UUID]:
        """The user id if the link is valid, unused and unexpired; it can never be used twice."""
        with self.pool.connection() as c:
            row = c.execute("UPDATE auth_tokens SET used_at=now() WHERE token_hash=%s AND purpose=%s AND used_at IS NULL "
                            "AND expires_at > now() RETURNING user_id", (token_hash(token), purpose)).fetchone()
        return row["user_id"] if row else None


class SystemSettingsStore:
    """PRD §12 `system_settings`: small JSON values changed from the admin System page."""

    def __init__(self, pool, tenant_id: str) -> None:
        self.pool, self.tenant = pool, tenant_id

    def get(self, key: str, default: Any = None) -> Any:
        with self.pool.connection() as c:
            row = c.execute("SELECT value FROM system_settings WHERE tenant_id=%s AND key=%s", (self.tenant, key)).fetchone()
        return row["value"] if row else default

    def set(self, key: str, value: Any, actor: Optional[UUID]) -> None:
        with self.pool.connection() as c:
            c.execute("INSERT INTO system_settings (tenant_id, key, value, updated_by) VALUES (%s,%s,%s,%s) "
                      "ON CONFLICT (tenant_id, key) DO UPDATE SET value=EXCLUDED.value, updated_at=now(), updated_by=EXCLUDED.updated_by",
                      (self.tenant, key, Jsonb(value), actor))

    def all(self) -> dict:
        with self.pool.connection() as c:
            return {r["key"]: r["value"] for r in c.execute("SELECT key, value FROM system_settings WHERE tenant_id=%s", (self.tenant,))}
