-- M1 (docs/P0_PLAN.md): accounts, sessions and the five account states.
-- PRD §5 FR-AUTH-02 (email verification), FR-AUTH-03/05 (states), FR-AUTH-06 (sessions, reset, admin MFA, bootstrap),
-- FR-AUTH-07 (account status history); PRD §12 entities `sessions`, `access_requests`, `system_settings`.

-- PRD §5 FR-AUTH-05: Pending, Active, Rejected, Suspended, Deactivated replace approval_status + is_active.
ALTER TABLE users ADD COLUMN account_status text;
UPDATE users SET account_status = CASE
    WHEN approval_status = 'pending'  THEN 'pending'
    WHEN approval_status = 'rejected' THEN 'rejected'
    WHEN is_active                    THEN 'active'
    ELSE 'deactivated' END;
ALTER TABLE users ALTER COLUMN account_status SET NOT NULL;
ALTER TABLE users ALTER COLUMN account_status SET DEFAULT 'pending';
ALTER TABLE users ADD CONSTRAINT users_account_status_check
    CHECK (account_status IN ('pending', 'active', 'rejected', 'suspended', 'deactivated'));
-- Read-only views of the state for older queries; they can never disagree with account_status.
ALTER TABLE users DROP COLUMN is_active;
ALTER TABLE users ADD COLUMN is_active boolean GENERATED ALWAYS AS (account_status = 'active') STORED;
ALTER TABLE users DROP COLUMN approval_status;
ALTER TABLE users ADD COLUMN approval_status text GENERATED ALWAYS AS (
    CASE account_status WHEN 'pending' THEN 'pending' WHEN 'rejected' THEN 'rejected' ELSE 'approved' END) STORED;

ALTER TABLE users ADD COLUMN phone text;                                   -- FR-AUTH-01 optional
ALTER TABLE users ADD COLUMN email_verified_at timestamptz;                -- FR-AUTH-02
UPDATE users SET email_verified_at = created_at;                           -- people already in the system were added by an admin
ALTER TABLE users ADD COLUMN last_login_at timestamptz;                    -- PRD §7 Users "last login"
ALTER TABLE users ADD COLUMN mfa_secret_enc text;                          -- FR-AUTH-06 admin MFA (TOTP secret, encrypted)
ALTER TABLE users ADD COLUMN mfa_enabled_at timestamptz;
ALTER TABLE users ADD COLUMN decision_note text;                           -- FR-AUTH-04 "optional note"

-- FR-AUTH-07 "view account status history"
CREATE TABLE account_status_history (
    id          bigserial PRIMARY KEY,
    user_id     uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    from_status text,
    to_status   text NOT NULL,
    actor_id    uuid REFERENCES users (id),
    note        text,
    at          timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX account_status_history_user ON account_status_history (user_id, at);
INSERT INTO account_status_history (user_id, from_status, to_status, note, at)
    SELECT id, NULL, account_status, 'state when account states were introduced', now() FROM users;

-- PRD §12 `sessions`: server-side sessions so suspension revokes access at once (FR-AUTH-05). Only hashes are stored.
CREATE TABLE sessions (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id     text NOT NULL DEFAULT 'quixotic',
    user_id       uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    token_hash    text NOT NULL UNIQUE,
    csrf_token    text NOT NULL,
    mfa_passed    boolean NOT NULL DEFAULT false,
    created_at    timestamptz NOT NULL DEFAULT now(),
    last_seen_at  timestamptz NOT NULL DEFAULT now(),
    expires_at    timestamptz NOT NULL,
    revoked_at    timestamptz,
    ip            text,
    user_agent    text
);
CREATE INDEX sessions_user ON sessions (user_id) WHERE revoked_at IS NULL;

-- One-time links: email verification and password reset (FR-AUTH-02, FR-AUTH-06). Only hashes are stored.
CREATE TABLE auth_tokens (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    purpose     text NOT NULL CHECK (purpose IN ('verify_email', 'reset_password')),
    token_hash  text NOT NULL UNIQUE,
    created_at  timestamptz NOT NULL DEFAULT now(),
    expires_at  timestamptz NOT NULL,
    used_at     timestamptz
);

-- PRD §12 `system_settings` (also records the one-time first-administrator bootstrap, FR-AUTH-06).
CREATE TABLE system_settings (
    tenant_id   text NOT NULL DEFAULT 'quixotic',
    key         text NOT NULL,
    value       jsonb NOT NULL,
    updated_at  timestamptz NOT NULL DEFAULT now(),
    updated_by  uuid REFERENCES users (id),
    PRIMARY KEY (tenant_id, key)
);
