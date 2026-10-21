-- Owner decision 2026-10-21: the Hermes agent and the Telegram integration are removed (PRD §9 / §14 Phase 2 channel not used;
-- docs/PRD_GAPS.md). Obsidian contributor sync stays: integration_identities (platform 'obsidian') and integration_events are kept.

-- Telegram account links can no longer be used by anything.
DELETE FROM integration_identities WHERE platform = 'telegram';

-- Proposals that waited for a Telegram confirmation tap can never be confirmed now: withdraw them (nothing was published) and put
-- their proposed versions back to draft, as a normal withdrawal does (§8 statuses).
INSERT INTO knowledge_status_history (version_id, from_status, to_status, actor_id, note)
SELECT v.id, v.status, 'draft', NULL, 'proposal withdrawn: Telegram confirmations removed'
FROM knowledge_proposals p JOIN knowledge_versions v ON v.id = p.version_id
WHERE p.status = 'awaiting_confirmation' AND p.kind IN ('create', 'update') AND v.status = 'under_review';
UPDATE chunks c SET metadata = jsonb_set(c.metadata, '{status}', to_jsonb('draft'::text))
FROM knowledge_proposals p JOIN knowledge_versions v ON v.id = p.version_id
WHERE c.version_id = v.id AND p.status = 'awaiting_confirmation' AND p.kind IN ('create', 'update') AND v.status = 'under_review';
UPDATE knowledge_versions v SET status = 'draft', updated_at = now()
FROM knowledge_proposals p
WHERE v.id = p.version_id AND p.status = 'awaiting_confirmation' AND p.kind IN ('create', 'update') AND v.status = 'under_review';
UPDATE knowledge_proposals SET status = 'withdrawn' WHERE status = 'awaiting_confirmation';

-- Bot message tracking and voice-note transcripts were only used by the Telegram approvals bot.
DROP TABLE IF EXISTS telegram_messages;
ALTER TABLE knowledge_proposals DROP COLUMN IF EXISTS transcript;
