-- M4 (docs/P0_PLAN.md): missing knowledge. PRD §6 FR-CHAT-04 (Report missing information), §9 knowledge gap loop
-- ("de-duplicated issue assigned to the correct department owner ... mark the gap resolved" once knowledge is published),
-- §12 `knowledge_gaps`.
CREATE TABLE knowledge_gaps (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id        text NOT NULL DEFAULT 'quixotic',
    normalized       text NOT NULL,                          -- de-duplication key (docs/PRD_GAPS.md: exact normalized text)
    question         text NOT NULL,                          -- the latest wording
    department_id    uuid REFERENCES departments (id),       -- NULL = not yet assigned (Knowledge Admins triage)
    status           text NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'in_progress', 'resolved', 'dismissed')),
    occurrences      integer NOT NULL DEFAULT 1,             -- how often it was asked without an approved answer
    reports          integer NOT NULL DEFAULT 0,             -- how often someone pressed "Report missing information"
    first_seen       timestamptz NOT NULL DEFAULT now(),
    last_seen        timestamptz NOT NULL DEFAULT now(),
    resolved_at      timestamptz,
    resolved_by      uuid REFERENCES users (id),
    proposal_id      uuid,                                    -- the change that answered it
    note             text
);
-- One open issue per question and department (§9 "de-duplicated").
CREATE UNIQUE INDEX knowledge_gaps_dedupe ON knowledge_gaps (tenant_id, normalized, COALESCE(department_id, '00000000-0000-0000-0000-000000000000'::uuid))
    WHERE status IN ('open', 'in_progress');
CREATE INDEX knowledge_gaps_status ON knowledge_gaps (status, last_seen DESC);

-- Individual reports and the comment the employee wrote. Kept for counting only: admin views show counts, not names
-- (§6 FR-CHAT-09 aggregate by default).
CREATE TABLE knowledge_gap_reports (
    id         bigserial PRIMARY KEY,
    gap_id     uuid NOT NULL REFERENCES knowledge_gaps (id) ON DELETE CASCADE,
    user_id    uuid REFERENCES users (id) ON DELETE SET NULL,
    query_id   uuid REFERENCES query_log (id) ON DELETE SET NULL,
    comment    text,
    at         timestamptz NOT NULL DEFAULT now(),
    UNIQUE (gap_id, user_id, query_id)
);

ALTER TABLE knowledge_proposals ADD COLUMN gap_id uuid REFERENCES knowledge_gaps (id) ON DELETE SET NULL;
ALTER TABLE knowledge_gaps ADD FOREIGN KEY (proposal_id) REFERENCES knowledge_proposals (id) ON DELETE SET NULL;
ALTER TABLE query_log ADD COLUMN gap_id uuid REFERENCES knowledge_gaps (id) ON DELETE SET NULL;
