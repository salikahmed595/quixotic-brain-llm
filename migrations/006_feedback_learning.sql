-- Owner request (2026-10-05): the system learns from 👍 / 👎 (PRD §21 stores the feedback; "feedback-based improvements" is PRD Phase 5).
-- Learning NEVER edits company knowledge and never trains a model (PRD §5 non-goals). It only (1) nudges the ORDER of retrieved passages,
-- (2) tells the answer model a person's style patterns, (3) marks rejected answers inside a chat, (4) feeds a report for administrators.
-- "Forget": feedback older than a reset time is ignored (nothing is deleted, so the audit trail stays intact).
ALTER TABLE users ADD COLUMN learning_reset_at timestamptz;          -- a person forgets what was learned about their style

CREATE TABLE learning_state (                                        -- one row per tenant: an administrator resets all learned signals
    tenant_id  text PRIMARY KEY,
    reset_at   timestamptz,
    reset_by   uuid REFERENCES users (id)
);

CREATE INDEX feedback_query ON feedback (query_id);
