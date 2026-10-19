# P0 / Phase 1 plan
Scope PRD §14 P0: shared + role UI; signup/email verify; admin approval; login/logout; role/department enforcement; employee chat + history; Obsidian-compatible approved doc import; citations; missing-answer behaviour; admin Users, Access requests, Documents, Departments; audit trail.

Per milestone (§16): small, testable; ships migration, OpenAPI contract, seed data, unit+integration+permission tests, `docs/PRD_GAPS.md` note for any gap/choice. Reuse working code (PRD_GAPS §0.4). ❓ = owner decisions in PRD_GAPS §0; milestone doesn't start until its ❓ answered; independent work first.

## M0 — Owner inputs (blocking)
| Needed | For | PRD |
|---|---|---|
| ✅ Two reference screenshots (`UI images/reference/`); original mascot/icon/font files still welcome | M6, AT-08 | §4 |
| ✅ Dept list = PRD §8 (`seed-departments`); still needed: membership, reviewers, sensitivity levels | M2, M3, seed | §3, §8, §16 |
| Role mapping (contributor/manager/administrator -> new roles) | M2 | §3 |
| Mail provider + sender | M1 | §5 FR-AUTH-02, FR-AUTH-06 |
| Admin MFA method | M1 | §5 FR-AUTH-06 |
| ✅ OpenAI now; DeepSeek key later (provider ready) | M4 | §10 |
| ✅ One budget EC2: Compose with Postgres+pgvector, Redis, API, worker, HTTPS proxy; S3 originals | M7 | §11 |
| API path style (`/v1/chats` vs `/chats`) | M5 | §11 |
| ✅ Past-sales-chat answers OFF (`QB_SALES_HISTORY_ENABLED=false`) | M4 | §1, §7 |

## M1 — Accounts, sessions, 5 account states ✅ 2026-10-17
- `users.account_status` Pending/Active/Rejected/Suspended/Deactivated (§5 FR-AUTH-05) replaces `approval_status`+`is_active`; status-history table (§5 FR-AUTH-07).
- Argon2id; old scrypt verified + rehashed on login (§5 FR-AUTH-06).
- Server-side `sessions` (§12), HttpOnly Secure SameSite cookie, CSRF on state changes, expiry, `POST /auth/logout`; suspend/reject/deactivate deletes sessions.
- Email verify + password reset via one-time link, `Mailer` interface fails loudly until configured (§5 FR-AUTH-02).
- Signup per §5 FR-AUTH-01: no role self-select, uniqueness, password policy, rate limit.
- One-time first-admin bootstrap, refuses once a system admin exists (§5 FR-AUTH-06). Admin MFA (per M0).
- Tests: AT-01 (backend), AT-02; every protected endpoint 401/403 for each non-Active state.

## M2 — Roles, departments, scopes (deny by default) ✅ roles, users, access requests, departments 2026-10-17
- Roles §3: Employee, Department Reviewer, Knowledge Admin (+publisher grant), System Admin. Founder/CEO reserved for Phase 2.
- Multi-department membership; no implicit Company Wide (§4.2, §15).
- Company Knowledge dropdown endpoint returns only permitted scopes (§6 FR-CHAT-06); tampered scopes rejected server-side.
- Admin (§7): Users (search/add/invite/edit/suspend/deactivate, last login, state, audit history), Departments (create/edit/disable, members, reviewers, doc owners), Access requests (approve/reject with note, role+scope, timestamps).
- Tests: AT-05 across search, citations, chat, direct API, tampered dropdown; no title/count/metadata leak.

## M3 — Doc model, statuses, Markdown vault ✅ 2026-10-17 (proposals, approvals, Git vault, Obsidian import)
- Statuses Draft/Under Review/Approved/Published/Archived (§8). No migration of old rows; owner starts fresh (PRD_GAPS §0.4b).
- Fields §8: category, department(s), sensitivity/scope, owner, approver, provenance, effective date, version ID, index checksum; `document_permissions` + ACL metadata on every chunk (§8, §12).
- Git-backed Obsidian vault; publication writes Markdown + commits (§8). Front-matter keys per owner. Separate *proposals* area for CEO Obsidian Git sync (owner 2026-10-17; PRD_GAPS §0.7); proposals never write published vault.
- Import approved Obsidian Markdown (§14); PDF/DOCX/TXT/MD upload exists; added parse review + reject unreadable (§7 Documents).
- Publication transaction: new version indexed + permission-synced before Published; old chunks invalidated; previous version recoverable; fail closed on index/permission mismatch (§8).
- Retrieval: Published and unexpired (§8). `POST /admin/documents/{id}/reindex` (§11).
- Tests: draft/under-review never retrievable; atomic swap; old version recoverable (AT-06 backend).

## M4 — Answers, citations, missing knowledge ✅ 2026-10-17 (AT-03/04/05)
- Exact not-found text §6 FR-CHAT-04; "Report missing information" -> `knowledge_gaps` (de-duplicated, assigned to dept owner) (§9, §12).
- Citations: title, section, effective/updated date + version (§6 FR-CHAT-04, AT-03).
- Permissions rechecked before answer + sources (§8).
- DeepSeek behind `generate_answer`, enabled once approved (§10, §11); existing providers kept.
- Answer in question's language, no fabricated translated policy (§6 FR-CHAT-08).
- Past-sales answers OFF (`QB_SALES_HISTORY_ENABLED`).
- Tests: AT-03, AT-04 (no invented discount), injection docs ignored; eval set re-pointed.

## M5 — Chats and history ✅ 2026-10-17
- §11 contract: `POST /chats`, `GET /chats`, `GET /chats/{id}`, `POST /chats/{id}/messages`, `DELETE /chats/{id}` (+rename); prefix per M0 (built as `/v1/chats`).
- Search own titles + messages; date-grouped history (§6 FR-CHAT-01); thumbs (§6 FR-CHAT-07).
- Own chats only; admin analytics aggregate (§6 FR-CHAT-09).
- Tests: user A can't read/search/rename/delete B's chats.

## M6 — Frontend with screenshot parity ✅ 2026-10-17
- Vite+React+TS+Tailwind (§11) replacing `frontend/app.js`; same backend contract.
- Home §4.1 (sidebar, hero, mascot, wave lines, pills, 960 px composer, 4 example cards, profile card); employee sidebar §4.2; admin sidebar order §4.3.
- P0 pages: signup, verify, pending, rejected, login, reset; chat + sources drawer, loading/retry/unavailable; admin Users, Access requests, Documents, Departments. Other admin items shown per §4.3 with "coming in Phase 2" placeholders. ❓ confirm
- Web Search pill + microphone present but disabled until P1 (§4.1 vs §14). ❓ confirm
- Responsive/a11y §4.4 (drawer, 44 px targets, focus, keyboard).
- Tests: Playwright visual at 1470×900 vs both screenshots, role nav (AT-01 e2e, AT-08). ✅ `web/tests/visual.spec.ts`, `npm run test:visual`.

## M7 — Audit, ops, release readiness ✅ 2026-10-18 (audit chain, Redis, Compose+Caddy, backups+drill, load test, docs/DEPLOYMENT.md); AT-09 must run on real server
- Audit events for approvals, scope changes, doc changes, publishing, exports; tamper-resistant (§10; append-only table + hash chain, listed as implementation necessity).
- Single EC2: Compose with API, worker, Postgres+pgvector, Redis queue (§11, replaces SQS), HTTPS proxy, logs; staging per owner (§11).
- Backup + tested restore (§16 g).
- Load tests: 160 sessions, 40-chat baseline, 160-chat burst; p95 targets §2 (AT-09).
- Written deployment guide (§16).
- Exit: §16 DoD (a)–(i); Hermes/Telegram/Discord out of scope.

Out of P0 (don't build now): Add information, Approvals UI, Knowledge browser, Sales memory UI, Dashboard/Insights polish, Vocabulary UI changes, Web Search, voice questions (P1); Hermes + Telegram/Discord (P2). Existing code stays, not extended until its phase.

## After M3 — Hermes + Telegram knowledge updates ✅ 2026-10-17 (PRD §9; PRD_GAPS §0.7)
Must not delay §16 Phase 1 release. Research + steps H0–H6: `docs/HERMES_TELEGRAM_OBSIDIAN_PLAN.md`.
- Hermes Agent as Compose service on EC2; only backend tools via signed `POST /integrations/hermes/knowledge-proposals` (§11, §15).
- Telegram gateway: allowlisted IDs mapped to verified Founder/CEO / Knowledge Admin users (§9 step 1).
- Voice notes transcribed by OpenAI STT; uncertain segments flagged (§9 step 2).
- Intent (ask, add fact, edit rule, replace policy, report gap) -> search approved docs -> Markdown proposal with before/after diff (§9 steps 3–4).
- CEO approves in Telegram; high-impact topics need second approver (§9 step 5). On approval: new version, audit event, reindex, retrieval check, Telegram confirmation with doc link; on failure keep old version + alert (§9 steps 6–7).
- Obsidian desktop + Git sync into proposals area; each synced change = proposal in same flow.
- Gap notifications to owner on Telegram (§9 gap loop).
- Tests: unlisted Telegram ID rejected; nothing published without approval; high-impact needs two approvals; failed reindex keeps previous version; Hermes can't reach non-allowlisted tools.
