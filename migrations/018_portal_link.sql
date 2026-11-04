-- Portal SSO (docs/PRD_GAPS.md "Portal SSO"). Not in the PRD. The Portal authenticates; Maqsad only trusts its signed hand-off.
-- portal_user_id is the stable link between a Maqsad user and a Portal user (employee_id may change when the Portal renames).
ALTER TABLE users ADD COLUMN portal_user_id bigint;
-- True only while the account is deactivated BECAUSE the Portal said so. Any other status change clears it, so a Maqsad
-- administrator's deactivation can never be undone by the Portal's next hand-off.
ALTER TABLE users ADD COLUMN deactivated_by_portal boolean NOT NULL DEFAULT false;
CREATE UNIQUE INDEX users_portal_user ON users (tenant_id, portal_user_id) WHERE portal_user_id IS NOT NULL;

-- Each hand-off token (jti) may be used once. Rows are purged once the token could no longer verify anyway.
CREATE TABLE portal_handoffs (
    jti              text PRIMARY KEY,
    portal_user_id   bigint NOT NULL,
    expires_at       timestamptz NOT NULL
);

-- Office-only: a session made from a Portal hand-off in a browser is bound to the IP and User-Agent the Portal saw.
-- NULL = an ordinary Maqsad session. kind = 'portal' (browser) or 'portal_server' (Portal server's bearer token, not IP-bound).
ALTER TABLE sessions ADD COLUMN bound_ip text, ADD COLUMN bound_ua_hash text, ADD COLUMN kind text;
