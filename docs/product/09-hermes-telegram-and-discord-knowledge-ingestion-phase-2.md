<!-- PRODUCT.md section 9 -->
# 9. Hermes, Telegram, and Discord knowledge ingestion (Phase 2)

A single shared knowledge-update service accepts verified messages from authorized Founder, CEO, and Knowledge Admin through Hermes-connected Telegram/Discord bots. A leadership user can send plain text or a voice note from phone or laptop. Workflow:

1. Telegram/Discord gateway captures sender platform ID, message ID, channel, timestamp, and text/audio; allowlist IDs and verify mapped company identities.
2. Audio is transcribed, original message/source recorded according to retention policy, and uncertain transcript segments flagged for confirmation.
3. Hermes/LLM determines intent: ask question, add fact, edit rule, replace policy, or report knowledge gap.
4. Backend searches existing approved documents, checks source provenance and policy conflicts, and prepares a structured Markdown proposal with a before/after diff.
5. Correct reviewer/approver accepts, revises, or rejects based on department-specific rules. High-impact policies (HR, pay, discounts, refunds, customer payments, security) always require explicit confirmation and approval. A model's researched or generated answer is never itself an authoritative company policy.
6. On approval, backend writes a new version, records an audit event, reindexes affected chunks, verifies retrieval success, then sends Telegram/Discord confirmation with linked document/version.
7. On failure, maintain the previous active version, alert the owner, and allow retry/rollback.

**Knowledge gap loop:** An employee question with no approved answer creates a de-duplicated issue assigned to the correct department owner. Admin may notify the authorized owner on Telegram/Discord. Once approved new knowledge is published, mark the gap resolved. Do not allow all employees to write to the vault through the chat interface.
