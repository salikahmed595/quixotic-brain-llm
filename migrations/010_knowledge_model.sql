-- M3 (docs/P0_PLAN.md): document model, statuses, proposals and approval decisions.
-- PRD §8 (published document fields, statuses Draft/Under Review/Approved/Published/Archived, controlled publication),
-- §7 Approvals (diffs, references, conflicts, submitter, reviewer), §12 knowledge_proposals / approval_decisions / index jobs.

-- §8 statuses. Old values map: active -> published, submitted/pending_review -> under_review, rejected/expired -> archived.
ALTER TABLE knowledge_versions DROP CONSTRAINT knowledge_versions_status_check;
DROP INDEX one_active_version_per_item;
UPDATE knowledge_versions SET status = CASE status
    WHEN 'active' THEN 'published' WHEN 'submitted' THEN 'under_review' WHEN 'pending_review' THEN 'under_review'
    WHEN 'rejected' THEN 'archived' WHEN 'expired' THEN 'archived' ELSE status END;
ALTER TABLE knowledge_versions ADD CONSTRAINT knowledge_versions_status_check
    CHECK (status IN ('draft', 'under_review', 'approved', 'published', 'archived'));
-- One published version per document: the switch on publication is atomic (§8).
CREATE UNIQUE INDEX one_published_version_per_item ON knowledge_versions (item_id) WHERE status = 'published';
UPDATE chunks c SET metadata = jsonb_set(c.metadata, '{status}', to_jsonb(v.status)) FROM knowledge_versions v WHERE v.id = c.version_id;

-- §8 published document fields
ALTER TABLE knowledge_items ADD COLUMN sensitivity text NOT NULL DEFAULT 'unclassified';  -- access scope; existing rows must be classified
ALTER TABLE knowledge_items ADD COLUMN owner_id uuid REFERENCES users (id);               -- document owner (§7 Departments)
ALTER TABLE knowledge_items ADD COLUMN provenance text;                                  -- source / provenance
ALTER TABLE knowledge_items ADD COLUMN vault_path text;                                  -- path in the Markdown vault (§8, §11)
ALTER TABLE knowledge_versions ADD COLUMN effective_date date;
ALTER TABLE knowledge_versions ADD COLUMN expires_at timestamptz;
ALTER TABLE knowledge_versions ADD COLUMN checksum text;                                 -- SHA-256 of the content
ALTER TABLE knowledge_versions ADD COLUMN indexed_checksum text;                         -- §12 "last indexed ... checksum"
ALTER TABLE knowledge_versions ADD COLUMN indexed_at timestamptz;
ALTER TABLE knowledge_versions ADD COLUMN approved_by uuid REFERENCES users (id);        -- §8 "approving user"
ALTER TABLE knowledge_versions ADD COLUMN approved_at timestamptz;
ALTER TABLE knowledge_versions ADD COLUMN published_by uuid REFERENCES users (id);
ALTER TABLE knowledge_versions ADD COLUMN published_at timestamptz;
ALTER TABLE knowledge_versions ADD COLUMN vault_commit text;                             -- Git commit that recorded it (§8 reversible change record)
ALTER TABLE knowledge_versions ADD COLUMN change_note text;
UPDATE knowledge_versions SET published_at = updated_at WHERE status = 'published';

-- §12 knowledge_proposals: every change to knowledge is a proposal that people review (§1, §3, §9, §15: nothing auto-approved).
CREATE TABLE knowledge_proposals (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id        text NOT NULL DEFAULT 'quixotic',
    kind             text NOT NULL CHECK (kind IN ('create', 'update', 'archive', 'restore')),
    item_id          uuid NOT NULL REFERENCES knowledge_items (id) ON DELETE CASCADE,
    version_id       uuid NOT NULL REFERENCES knowledge_versions (id) ON DELETE CASCADE,   -- the version this proposal would publish/archive
    base_version_id  uuid REFERENCES knowledge_versions (id),                              -- published version when proposed (diff "before")
    title            text NOT NULL,
    summary          text,
    meta             jsonb NOT NULL DEFAULT '{}',          -- proposed title/category/departments/sensitivity/owner/provenance
    source           text NOT NULL CHECK (source IN ('web', 'upload', 'import', 'obsidian', 'telegram', 'discord', 'api')),
    source_ref       text,                                                                  -- e.g. bot message id, file name
    submitted_by     uuid REFERENCES users (id),
    submitted_at     timestamptz NOT NULL DEFAULT now(),
    status           text NOT NULL DEFAULT 'open'
        CHECK (status IN ('open', 'changes_requested', 'approved', 'publishing', 'published', 'rejected', 'withdrawn', 'failed')),
    high_impact      boolean NOT NULL DEFAULT false,                                        -- §9 step 5
    required_approvals integer NOT NULL DEFAULT 1 CHECK (required_approvals BETWEEN 1 AND 5),
    decided_at       timestamptz,
    published_at     timestamptz,
    error            text,
    UNIQUE (tenant_id, source, source_ref)                                                  -- §12 bot events never write twice
);
CREATE INDEX knowledge_proposals_open ON knowledge_proposals (status, submitted_at DESC);

-- §12 approval_decisions
CREATE TABLE approval_decisions (
    id           bigserial PRIMARY KEY,
    proposal_id  uuid NOT NULL REFERENCES knowledge_proposals (id) ON DELETE CASCADE,
    decided_by   uuid NOT NULL REFERENCES users (id),
    decision     text NOT NULL CHECK (decision IN ('approve', 'reject', 'request_changes')),
    note         text,
    via          text NOT NULL DEFAULT 'web' CHECK (via IN ('web', 'telegram', 'cli')),
    at           timestamptz NOT NULL DEFAULT now(),
    UNIQUE (proposal_id, decided_by, decision)
);
