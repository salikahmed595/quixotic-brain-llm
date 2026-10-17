# P0 / Phase 1 — milestone plan

Scope is PRD §14 P0: exact shared and role-specific UI; signup and email verification; admin approval;
login/logout; role/department enforcement; employee chat and history; Obsidian-compatible approved document
import; citations; missing-answer behaviour; basic admin Users, Access requests, Documents, Departments; audit trail.

Rules for every milestone (PRD §16 "Implementation direction"): small and testable; each one ships its migration,
API contract (OpenAPI), seed data, unit + integration + permission tests, and a note in `docs/PRD_GAPS.md` for any
gap or implementation choice. Reuse working code (see `docs/PRD_GAPS.md` §0.4) rather than replacing it.

❓ items refer to the owner decisions in `docs/PRD_GAPS.md` §0. A milestone does not start until its ❓ items are
answered; work that does not depend on them goes first.

---

## M0 — Inputs from the owner (blocking)

| Needed | For | PRD |
|---|---|---|
| ~~The two reference screenshots~~ ✅ added (`UI images/reference/`); original mascot/icon/font files still welcome | M6, AT-08 | §4 |
| ~~Department list~~ ✅ PRD §8 list (`seed-departments`); still needed: who belongs where, who reviews what, sensitivity levels | M2, M3, seed data | §3, §8, §16 "Ask for real department rules" |
| Role mapping (contributor / manager / administrator → new roles) | M2 | §3 |
| Mail provider + sender address | M1 (verification, reset) | §5 FR-AUTH-02, FR-AUTH-06 |
| Admin MFA method | M1 | §5 FR-AUTH-06 |
| ✅ OpenAI now; DeepSeek key added later (provider ready) | M4 | §10 |
| ✅ One budget EC2 server: Docker Compose with Postgres + pgvector, Redis, API, worker, HTTPS proxy; S3 for originals | M7 | §11 |
| API path style (`/v1/chats` vs `/chats`) | M5 | §11 |
| ✅ Past-sales-chat answers OFF (`QB_SALES_HISTORY_ENABLED=false`) | M4 | §1, §7 |

## M1 — Accounts, sessions and the five account states

- Migration: `users.account_status` ∈ Pending / Active / Rejected / Suspended / Deactivated (§5 FR-AUTH-05), replacing `approval_status` + `is_active`; status-history table for "view account status history" (§5 FR-AUTH-07).
- Argon2id hashing; old scrypt hashes verified and rehashed on login (§5 FR-AUTH-06).
- Server-side `sessions` table (§12), HttpOnly Secure SameSite cookie, CSRF token on state-changing requests, session expiry, `POST /auth/logout`; suspend/reject/deactivate deletes the user's sessions (§5 FR-AUTH-05).
- Email verification + password reset by emailed one-time link, behind a `Mailer` interface that fails loudly until configured (§5 FR-AUTH-02).
- Signup: required fields per §5 FR-AUTH-01, no role self-selection, uniqueness, password policy, rate limit.
- One-time first-admin bootstrap that refuses once a system admin exists (§5 FR-AUTH-06).
- Admin MFA (method per M0).
- **Tests:** AT-01 (backend part), AT-02; every protected endpoint returns 401/403 for each non-Active state.

## M2 — Roles, departments, scopes (deny by default)

- Roles per §3: Employee, Department Reviewer, Knowledge Admin (+ publisher grant), System Admin. Founder/CEO reserved for Phase 2.
- Multi-department membership (exists); no implicit Company Wide (§4.2, §15).
- `GET` endpoint for the Company Knowledge dropdown returning only permitted scopes (§6 FR-CHAT-06); tampered scope values rejected server-side.
- Admin: Users (search/add/invite/edit/suspend/deactivate, last login, state, audit history), Departments (create/edit/disable, members, reviewers, document owners), Access requests (approve/reject with note, role + scope, timestamps) (§7).
- **Tests:** AT-05 permission suite across search, citations, chat, direct API calls, tampered dropdown values — no titles, counts or metadata leak.

## M3 — Document model, statuses and the Markdown vault

- Statuses Draft / Under Review / Approved / Published / Archived (§8). No migration of old knowledge rows — the owner starts fresh with new Obsidian knowledge (PRD_GAPS §0.4b).
- Fields per §8: category, department(s), sensitivity/access scope, owner, approving user, provenance, effective date, version ID, indexing checksum; `document_permissions` and ACL metadata on every chunk (§8, §12).
- Git-backed Obsidian-compatible vault on the server; publication writes the Markdown file and commits (§8). Front-matter keys per owner decision.
  Design it so a separate *proposals* area can receive the CEO's Obsidian Git sync later (owner, 2026-10-17; PRD_GAPS §0.7) — proposals never write the published vault.
- Import approved Obsidian Markdown files (P0 "Obsidian-compatible approved document import", §14); PDF/DOCX/TXT/MD upload already works — add parse review step and reject unreadable files (§7 Documents).
- Controlled publication transaction: new version indexed and permission-synced before it switches to Published; old chunks invalidated; previous version recoverable; fail closed if index and permissions disagree (§8).
- Retrieval filter: Published and not past expiry (§8). Admin reindex endpoint (`POST /admin/documents/{id}/reindex`, §11).
- **Tests:** draft/under-review text never retrievable; publish swap is atomic; old version recoverable (AT-06 backend part, without the P1 Approvals UI).

## M4 — Answers, citations, missing knowledge

- Exact not-found text from §6 FR-CHAT-04 and "Report missing information" → `knowledge_gaps` table, de-duplicated, assigned to the department owner (§9, §12).
- Citations show document title, section and effective/updated date + version (§6 FR-CHAT-04, AT-03).
- Permissions rechecked before returning answer and sources (§8).
- DeepSeek provider behind `generate_answer`, enabled only once approved (§10, §11); existing providers kept.
- Answer in the question's language without fabricating translated policy (§6 FR-CHAT-08).
- Past-sales-chat answers stay OFF (owner, 2026-10-17; done via `QB_SALES_HISTORY_ENABLED`).
- **Tests:** AT-03, AT-04 (no invented discount), prompt-injection documents ignored; evaluation set re-pointed to new citations.

## M5 — Chats and history

- §11 chat contract: `POST /chats`, `GET /chats`, `GET /chats/{id}`, `POST /chats/{id}/messages`, `DELETE /chats/{id}` (+ rename); path prefix per M0.
- Search own chat titles and messages; date-grouped history (§6 FR-CHAT-01); thumbs up/down (exists, §6 FR-CHAT-07).
- Strictly own chats only; admin analytics aggregate (§6 FR-CHAT-09).
- **Tests:** user A can never read, search, rename or delete user B's chats.

## M6 — Frontend rebuild with screenshot parity — ✅ built 2026-10-17

- Vite + React + TypeScript + Tailwind (§11), replacing `frontend/app.js`; same backend contract.
- Shared home screen per §4.1 (sidebar, hero, mascot, wave lines, pills, 960 px composer, four example cards, profile card); employee sidebar per §4.2; admin sidebar exact order per §4.3.
- Pages for P0: signup, verify, pending, rejected, login, reset; chat + sources drawer, loading/retry/unavailable states; admin Users, Access requests, Documents, Departments. Other admin items visible in the sidebar per §4.3 but open "coming in Phase 2" placeholders. ❓ confirm
- Web Search pill and microphone present but disabled until P1 (§4.1 vs §14). ❓ confirm
- Responsive + accessibility per §4.4 (drawer, 44 px targets, focus states, keyboard).
- **Tests:** Playwright visual regression at 1470 × 900 against both screenshots, role-based nav checks (AT-01 end-to-end, AT-08). ✅ `web/tests/visual.spec.ts`, `npm run test:visual` (AT-08).

## M7 — Audit, operations and release readiness

- Audit events for approvals, access-scope changes, document changes, publishing, exports; tamper-resistant (§10; proposed: append-only table + hash chain, to be listed as an implementation necessity).
- Single EC2 server (owner): Docker Compose with API, worker, PostgreSQL + pgvector, Redis queue (§11, replaces SQS), HTTPS reverse proxy, log collection; staging setup per owner (§11).
- Backup and tested restore (§16 g).
- Load tests: 160 sessions, 40-chat baseline, 160-chat burst; p95 targets from §2 (AT-09).
- Written deployment guide (§16).
- **Exit:** §16 definition of done items (a)–(i), with Hermes/Telegram/Discord explicitly out of scope.

---

Out of P0 (do not build now): Add information, Approvals UI, Knowledge browser, Sales memory UI, Dashboard/Insights
polish, Vocabulary UI changes, Web Search, voice questions (P1); Hermes + Telegram/Discord (P2). Existing code for
these stays in place but is not extended until its phase.

## After M3 — Hermes + Telegram knowledge updates (PRD §9; owner decisions in PRD_GAPS §0.7)

Starts once M3 is done; must not delay the §16 Phase 1 release. Full research and steps H0–H6: `docs/HERMES_TELEGRAM_OBSIDIAN_PLAN.md`.

- Hermes Agent as a Docker Compose service on the EC2 server; only backend tools via signed `POST /integrations/hermes/knowledge-proposals` (§11, §15).
- Telegram gateway: allowlisted IDs mapped to verified Founder/CEO / Knowledge Admin users (§9 step 1).
- Voice notes transcribed with OpenAI speech-to-text; uncertain segments flagged (§9 step 2).
- Intent (ask, add fact, edit rule, replace policy, report gap) → search approved docs → Markdown proposal with before/after diff (§9 steps 3–4).
- CEO approves in Telegram; high-impact topics also need a second approver (§9 step 5). On approval: new version, audit event, reindex, retrieval check, Telegram confirmation with the document link; on failure keep the old version and alert (§9 steps 6–7).
- Obsidian desktop + Git sync into the proposals area; each synced change becomes a proposal for the same approval flow.
- Knowledge-gap notifications to the owner on Telegram (§9 gap loop).
- **Tests:** unlisted Telegram ID rejected; nothing is published without approval; high-impact needs two approvals; failed reindex keeps the previous version; Hermes cannot reach any tool outside the allowlist.
