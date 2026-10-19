# Hermes + Telegram + Obsidian (PRD §9) — built 2026-10-17
History: git log -p docs/HERMES_TELEGRAM_OBSIDIAN_PLAN.md
Setup: `docs/DEPLOYMENT.md` §6–7. Decisions: `docs/PRD_GAPS.md` §0.7. Optional; must not delay §16 Phase 1.

## Flow
Telegram -> Bot 1 "Quixotic Hermes" (Hermes Agent) -> `quixotic-mcp` sidecar (signed) -> `POST /integrations/hermes/knowledge-proposals` -> proposal -> Bot 2 "Quixotic Approvals" (backend-owned) -> approver taps (Telegram ID checked by backend) -> new version, audit, reindex, retrieval check, confirmation. CEO Obsidian: git push `proposals/ceo` -> post-receive hook -> proposals; `main` written only by backend.

Rules: nothing becomes knowledge without approval (§1, §9, §15); approval never via AI (Hermes has no approve tool); Hermes locked down (no terminal/file/web/browser/code/memory/skills; only `clarify` + 4 quixotic tools).

## Where
| Piece | Path |
|---|---|
| Signed endpoints | `backend/api/v1/integrations.py` (`tests/integration/test_hermes.py`) |
| Approvals bot (Confirm/Cancel, Approve/Reject, `/start`, `/pending`); webhook `POST /v1/integrations/telegram/webhook`; poller `python -m workers.telegram_poll` | `backend/integrations/approvals_bot.py` |
| MCP sidecar | `integrations/mcp/` |
| Hermes config | `deploy/hermes/{config.yaml,SOUL.md,hermes.env.example}` |
| Vault sync | `backend/knowledge/vault_sync.py`, `deploy/vault/*` |
| Account linking | Admin -> System -> Integrations |

Tools: `search_approved_knowledge`, `create_knowledge_proposal`, `get_proposal_status`, `report_knowledge_gap`. HMAC-signed, replay-rejected, internal network only. A Hermes proposal waits as `awaiting_confirmation` until the linked Telegram account confirms.

## H0 check (every Hermes upgrade)
`docker compose -f docker-compose.prod.yml run --rm -it hermes tools list --platform telegram` must list only `clarify` + five `quixotic` tools; unlisted Telegram user gets no reply; no new files under `skills/` or `memories/`; voice note transcribed.

## Obsidian
Server: `vault` user (git-shell), bare repo `/srv/vault/vault.git`, hook: CEO key may push only `refs/heads/proposals/ceo`, no force-push, no `main`. After publication `main` merges into linked branches. Notes need `departments:` (+ `sensitivity:` for new) front matter. CEO laptop: Git + Obsidian + Obsidian Git plugin (auto commit-sync ~10 min).

## Tests (H6)
Unlisted ID ignored; unmapped refused; no publish without approval tap; non-approver tap refused; high-impact needs two approvers; Hermes can't use non-allowlisted tools; MCP rejects unsigned/replayed; failed reindex keeps previous version; `main`/force push refused; voice transcript confirmed before proposal.

## Open ❓
- O4 second approver for high-impact (proposed: Knowledge Admin in web Approvals).
- O5 retention of original messages/audio (§9 step 2).
- O6 rejected Obsidian edit (now stays on branch; proposed: revert + explain).
- O9 Discord now or later (plan: Telegram only).

## Fallback
If Hermes can't be locked down: small Python Telegram bot in backend (needs owner approval; §11 names Hermes).
