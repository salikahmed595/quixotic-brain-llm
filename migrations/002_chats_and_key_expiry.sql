-- Owner request (2026-10-04): ChatGPT-style chat history, and API keys that expire instead of being rate-limited per minute.

-- Chats are private to the user who had them (PRD §5: no employee surveillance).
CREATE TABLE conversations (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id     text NOT NULL DEFAULT 'quixotic',
    user_id       uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    title         text NOT NULL,
    mode          text,
    department_id uuid REFERENCES departments (id),
    created_at    timestamptz NOT NULL DEFAULT now(),
    updated_at    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX conversations_user_recent ON conversations (user_id, updated_at DESC);

CREATE TABLE conversation_messages (
    id              bigserial PRIMARY KEY,
    conversation_id uuid NOT NULL REFERENCES conversations (id) ON DELETE CASCADE,
    role            text NOT NULL CHECK (role IN ('user', 'assistant')),
    content         jsonb NOT NULL,
    created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX conversation_messages_conv ON conversation_messages (conversation_id, id);

-- API keys: optional rate limit (NULL = none), optional expiry (NULL = until revoked), last 4 characters for display.
ALTER TABLE api_keys ALTER COLUMN rate_limit_per_minute DROP NOT NULL;
ALTER TABLE api_keys ADD COLUMN expires_at timestamptz;
ALTER TABLE api_keys ADD COLUMN last4 text NOT NULL DEFAULT '';
