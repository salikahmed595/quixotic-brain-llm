-- Hermes + Telegram + Obsidian (docs/HERMES_TELEGRAM_OBSIDIAN_PLAN.md). PRD §9 (verified identities, allowlists, confirmations,
-- approvals, bot confirmation with link), §12 `integration_identities`, `ingestion_events` ("uniquely identify external bot events to
-- prevent duplicate writes"), §15 (no autonomous changes).

-- §9 step 1: platform account -> verified company user. Telegram: numeric user id. Obsidian: the Git proposals branch name.
CREATE TABLE integration_identities (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id    text NOT NULL DEFAULT 'quixotic',
    platform     text NOT NULL CHECK (platform IN ('telegram', 'discord', 'obsidian')),
    external_id  text NOT NULL,
    user_id      uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    label        text,
    created_by   uuid REFERENCES users (id),
    created_at   timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, platform, external_id)
);

-- §12 ingestion events: every bot / sync event once, with what it caused. Message text is not stored here (retention, §10).
CREATE TABLE integration_events (
    id            bigserial PRIMARY KEY,
    tenant_id     text NOT NULL DEFAULT 'quixotic',
    platform      text NOT NULL,
    event_id      text NOT NULL,
    kind          text NOT NULL,
    user_id       uuid REFERENCES users (id) ON DELETE SET NULL,
    proposal_id   uuid REFERENCES knowledge_proposals (id) ON DELETE SET NULL,
    received_at   timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, platform, event_id)
);

-- Proposals from a chat bot wait for the real sender's confirmation tap in the backend-owned approvals bot (§9 step 1/2).
ALTER TABLE knowledge_proposals DROP CONSTRAINT knowledge_proposals_status_check;
ALTER TABLE knowledge_proposals ADD CONSTRAINT knowledge_proposals_status_check CHECK (status IN
    ('awaiting_confirmation', 'open', 'changes_requested', 'approved', 'publishing', 'published', 'rejected', 'withdrawn', 'failed'));
ALTER TABLE knowledge_proposals ADD COLUMN transcript text;           -- a voice note's transcript, shown for confirmation (§9 step 2)

-- Telegram messages the approvals bot sent, so their buttons can be updated once a decision is made.
CREATE TABLE telegram_messages (
    id           bigserial PRIMARY KEY,
    proposal_id  uuid REFERENCES knowledge_proposals (id) ON DELETE CASCADE,
    chat_id      text NOT NULL,
    message_id   bigint NOT NULL,
    purpose      text NOT NULL CHECK (purpose IN ('confirm', 'review', 'info')),
    created_at   timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX telegram_messages_proposal ON telegram_messages (proposal_id);
