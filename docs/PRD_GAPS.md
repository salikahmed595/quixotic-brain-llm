# PRD gaps and implementation necessities
Rule (`CLAUDE.md`): PRD = only truth, nothing guessed. Where `PRODUCT.md` is silent, backend either **requires an explicit setting/plug-in** (fails loudly) or does the **smallest thing** and lists it here. ❓ = owner decision needed; stated behaviour applies meanwhile. "veto if needed" = owner may reject.

## 0. PRD replaced 2026-10-17
`PRODUCT.md` = Quixotic AI PRD v1.0 (16 Oct 2026), 16 sections. Old "Quixotic Brain" PRD (67 sections) superseded, kept in `docs/archive/PRODUCT_quixotic_brain_v0.md`.
> **Old citations:** every `PRD §N` in code, `docs/backend.md`, §1–6 and the dated owner sections below = the *superseded* PRD (look up in archive). New work cites new PRD (`PRD §5 FR-AUTH-03`, `PRD §13 AT-05`); re-point as modules are touched.

### 0.1 Accounts, auth, roles
| Area | New PRD | Status / handling |
|---|---|---|
| Account states | §5 FR-AUTH-05: Pending, Active, Rejected, Suspended, Deactivated | **Done M1:** `users.account_status` (migration 008); `is_active`/`approval_status` read-only generated; changes in `account_status_history` (FR-AUTH-07); suspend/deactivate/reactivate on Users; leaving Active revokes all sessions |
| Email verification | §5 FR-AUTH-02 | **Done M1:** one-time link at sign-up; admin approves only after verification (AT-01). Required `QB_MAIL_BACKEND` = `smtp` (SES, Google Workspace, M365…) or `console` (link in log). ❓ Production SMTP service + sender |
| Password hashing | §5 FR-AUTH-06 Argon2id | **Done M1:** `argon2-cffi` defaults; old scrypt hashes verify once then rehash |
| Sessions | §5 FR-AUTH-06 | **Done M1:** server-side `sessions` (token hashes only), HttpOnly `qb_session` cookie (Secure if `QB_PUBLIC_URL` https), SameSite=Lax, per-session CSRF on cookie writes, `POST /v1/auth/logout`, expiry `QB_SESSION_TTL_SECONDS`; suspend/reject/deactivate/reset revoke. Non-browser clients may send token as Bearer |
| Password reset | §5 FR-AUTH-06 | **Done M1:** emailed one-time link (`QB_ONE_TIME_LINK_TTL_SECONDS`), always 202 (no account leak); signs out all devices |
| Admin MFA | §5 FR-AUTH-06 | **Done M1, proposed (veto if needed):** TOTP (RFC 6238, `pyotp`), QR enrol at first sign-in, secret encrypted with `QB_FIELD_ENCRYPTION_KEY`; required for Knowledge Admin, System Admin, Founder/CEO when `QB_ADMIN_MFA_REQUIRED=true` (true in prod); admins reset lost phone in Users |
| First admin | §5 FR-AUTH-06 | **Done M1:** `python -m backend.cli bootstrap-admin`; refuses once a System Admin exists |
| Signup fields | §5 FR-AUTH-01 | **Done M1:** full name, username (owner 2026-10-05), work email, password+confirm, requested department (required), optional phone; role always Employee |
| Roles | §3 | **Done M2 (migration 009), mapping proposed (veto if needed):** contributor->employee, manager->department_reviewer, administrator->system_admin; added `knowledge_admin`, `founder_ceo`. Knowledge Admin publishes only with separate `can_publish` grant (System Admins always). Page access = one permission per §7 page (`backend/permissions/roles.py`). Knowledge Admin, System Admin, Founder/CEO search every department; others only their own. ❓ Confirm Founder/CEO pages (Knowledge, Add information, Approvals, Dashboard, Insights) |
| Founder/CEO | §3, §9 | Role exists (M2); Telegram/Hermes authority in Hermes milestone |
| "Company Wide" | §4.2, §15 never default/fake | no implicit visibility; unchanged |
| Self-approval | §7 Approvals | managers can approve own uploads. ❓ Which changes need separation of duties? (P0 has no Approvals page; §14 puts it in P1) |

### 0.2 Knowledge, retrieval, answers
| Area | New PRD | Status / handling |
|---|---|---|
| Statuses | §8 Draft/Under Review/Approved/Published/Archived | Old draft->Draft, submitted+pending_review->Under Review, approved->Approved, active->Published, archived->Archived. ❓ `rejected`/`expired` not PRD states (§8 says "unexpired" = date, not state): keep as change-record outcomes? |
| Fields | §8: category, sensitivity/scope, owner, approver, provenance, effective date, version ID, index checksum | Added missing columns + `document_permissions` (§12) (M3). ❓ Sensitivity levels |
| Store | §8 Obsidian-compatible Markdown vault, server-side, Git | Git vault dir; publication writes Markdown + commits (M3). ❓ Front-matter keys (none specified) |
| Retrieval filter | §8 approved, unexpired | `Published` + not past expiry |
| LLM | §8, §11 DeepSeek/configured; §10 no confidential data to unapproved provider | **Owner 2026-10-17: OpenAI now; DeepSeek key added later, then default.** `deepseek` provider added (`QB_GENERATION_PROVIDER=deepseek`, `DEEPSEEK_API_KEY`). Keys only in AWS Secrets Manager/server env (§10). Model ids required settings |
| Not-found reply | §6 FR-CHAT-04 | **Done M4:** no passages / low confidence / model says insufficient (internal word `NO_APPROVED_ANSWER`) -> exactly "I couldn't find an approved answer in the company knowledge base." + Report missing information |
| Knowledge gaps | §9, §12 | **Done M4:** `knowledge_gaps` + `knowledge_gap_reports`; every unanswered employee question records/counts a gap; Report adds comment. Routing (veto if needed): dept question asked in, else asker's only dept, else unassigned for Knowledge Admins; dept reviewers emailed for new gap. Admin views show counts/comments, never asker (FR-CHAT-09). Linked proposal resolves gap on publication. ❓ De-dup = exact normalized text |
| Past sales chats | §1, §7 sales memory = approved playbooks | **Owner 2026-10-17: OFF.** `QB_SALES_HISTORY_ENABLED` (default false) gates all use of past chats; code kept |
| Confidence | new PRD silent | Kept in UI (not PRD-required). ❓ keep or remove? |
| Language | §6 FR-CHAT-08 | LLM instructed to answer in detected language; Urdu/Roman Urdu work kept |
| Web Search | §6 FR-CHAT-05 (P1) | pill shown, disabled until P1. ❓ OK? |
| Voice | §6 FR-CHAT-02 (P1) | microphone shown, disabled until P1 |

### 0.3 Platform, API, UI
| Area | Status / handling |
|---|---|
| API paths (§11 "illustrative") | **Done M2–M5:** `/v1` + `/v1/auth/*`, `/v1/admin/*` (users, access requests, departments, proposals, documents, knowledge gaps, API keys, jobs), `/v1/knowledge/*` (documents, proposals, search alias), `/v1/chats` + `POST /v1/chats/{id}/messages`. `/v1/conversations`, `/v1/ask` stay (internal apps) |
| Chat messages (§11) | **Done M5:** answer or search mode; chat search covers titles, questions, answers, search results of own chats only |
| Frontend (§11) | **Done M6:** `web/` Vite+React 18+TS+Tailwind 4; old `frontend/` removed; built to `web/dist`, served by API (`QB_FRONTEND_DIR=web/dist`) |
| Screenshots (§4) | Added 2026-10-17 in `UI images/reference/` (admin `image(20261016-164021).png`, employee `image(20261016-164058).png`); older mock-ups superseded. Owner: no mascot file, recreate as SVG |
| Admin sidebar (§4.3) | match exactly (M6) |
| Queue (§11 Redis) | **Owner 2026-10-17: one budget EC2.** Redis container on that server (no ElastiCache); replaced SQS in M7 |
| Object storage | S3 (any S3-compatible) unchanged |
| Deployment (§11, §16) | **Owner: single cheapest EC2.** Proposed (veto): Compose with API, worker, PostgreSQL+pgvector, Redis, Caddy/Let's Encrypt; originals in S3; nightly `pg_dump` + EBS snapshots to S3. Size from load test. ❓ Staging: second small instance or same server? |
| Load test (§2, AT-09) | script in M7 (160 sessions, 40 baseline, 160 burst) |
| Non-goals | `CLAUDE.md` cites new §15 |

### 0.4 Reused
Hybrid retrieval (Postgres FTS + pgvector) with permission filters before search; reranker interface; PDF/DOCX/TXT/MD ingestion with validation/size limits; versioning with one active version; signup->pending->approve/reject; per-user chats; audit log; 👍/👎 feedback; hashed/masked/revocable API keys; vocabulary; dashboard/insights endpoints; prompt-injection guard; 4-provider LLM interface; evaluation harness; Docker Postgres launcher.

### 0.4b Knowledge and departments (owner 2026-10-17)
- Previous knowledge not carried over; M3 builds new model without migrating old rows (no code deletes them). ❓ Clear old rows (irreversible) or keep until new tables replace them?
- Departments (owner, PRD §8 hierarchy): Company General, HR, Sales - Fresh Seller, Sales - Upseller, Production, Marketing, Customer Support, Leadership, Training. `python -m backend.cli seed-departments` (idempotent). Sales sub-teams separate (no hierarchy in schema). §8 "Glossary/", "Archive/" are vault folders. Existing departments ("Company Wide", "Administration") untouched.
- "Company General" = §6 FR-CHAT-06 scope name; admin card "Company Wide" (§4.3) = access to all departments.

### 0.5 Reference screenshots (2026-10-17)
- Employee shot reads "Employee · Company Wide": per §4.2/§15 card shows real scope; screenshot treated as demo data.
- "Web Search" (with space) in both shots (§4.1 said "WebSearch"); UI uses "Web Search".
- Admin sidebar: WORKSPACE collapsible header (chevron) above KNOWLEDGE, MANAGE, ADMINISTRATION; block scrolls with visible scrollbar; chat history ("Previous 7 days") below.
- Admin shot's first example card has orange outline = hover/active (§4.1), not default.
- Font: rounded geometric sans, unidentifiable from raster. ❓ Font name/files? Until then closest match listed as necessity.
- Mascot/icons: no files; recreated as SVG, reviewed vs screenshots.

### 0.6 Front-end rebuild (M6)
- Parity at 1468×901 within ~5 px (headline, subtitle, mascot, labels, composer, cards); admin sidebar rows/group gaps/profile card tuned. **AT-08 automated:** `web/tests/visual.spec.ts` (Playwright) compares both homes with references + §4.2/§4.3 nav + §4.4 375 px rules (run: `docs/backend.md`). PRD gives no tolerance; choices (veto): pixel differs only if pixelmatch (threshold 0.2) flags it and no similar colour (±48/channel) within 4 px in other image; max 0.8% differing (measured employee 0.10%, admin 0.42%; 10 px drift >=1.3%). Masked: chat history titles (personal data), mascot (animated), Workspace scrollbar (Windows classic in reference). Test accounts named "Administrator"/"Employee"; employee in every active department.
- Touch targets fixed by AT-08: in <=900 px drawer, brand link, Close sidebar button, WORKSPACE header were 32–40 px, now 44 px (§4.4).
- Font **Plus Jakarta Sans** (Google Fonts; the screenshots' app font). ❓ Veto if company has another.
- Mascot SVG: `web/src/components/Mascot.tsx`.
- "Company Wide" on profile card only for admins or members of every active department (§4.2, §15).
- **+** button opens answer mode: *Answer* or *Search only*; "Sales coach" removed from UI (past chats off). PRD doesn't say what + does ❓.
- Web Search pill + mic shown (§4.1) but only explain they come later (§14 P1: FR-CHAT-05, FR-CHAT-02).
- Search chats: browser filter of titles; FR-CHAT-01 also wants message text (backend endpoint; later built in M5).
- Report missing information (FR-CHAT-04): contributors+ go to Add information; employees send feedback "Missing information" (superseded by M4 `knowledge_gaps`).
- Sign-in stored bearer token in browser; M1 replaced with HttpOnly cookies.
- Provider failures return 503 "The answer service is unavailable right now" (not 500); chat shows Retry (FR-CHAT-07); provider message stays in server log.
- Necessities: React 18.3, Vite 6.3, Tailwind 4.1, TypeScript 5.8 (`web/package.json`); Node 24 build stage in Dockerfile. Test-only: Playwright 1.63, pixelmatch 7.1, pngjs 7.0.

### 0.6b Knowledge model (M3, 2026-10-17) — choices to veto
- **Statuses:** Draft/Under Review/Approved/Published/Archived; one Published version per document (DB index). Old: active->published, submitted/pending review->under review, rejected/expired->archived.
- **Every change is a proposal** (§1, §3, §7, §12): new doc, new version, archive, restore = `knowledge_proposals` with `approval_decisions`. Proposed departments/sensitivity/owner apply only at publication. Reviewers see line diff, metadata changes, related published docs (possible conflicts/duplicates; only ones they may see), earlier decisions. Reject/changes-requested needs a note; version returns to Draft.
- **Who decides (veto):** Department Reviewer only for departments they review; Knowledge Admin only with publisher grant; System Admins and Founder/CEO everywhere. Publication needs >=1 decision by a publisher (reviewer approval alone never publishes). ❓ Approval matrix per department (§3) — this rule until given.
- **High impact (§9 step 5):** title/category/department/text mentioning HR, pay/payroll/salary, discount, refund, (customer) payment or security needs **two different approvers** (owner decision for Telegram, applied everywhere). Parsed file text can raise it after upload; nothing lowers it.
- **Controlled publication (§8):** worker job: (re)index -> write note to Git vault + commit -> switch published version + metadata in one DB transaction -> verify first passage returns from employee search -> on failure restore previous version, mark proposal failed, email System Admins (§9 step 7); admins can retry.
- **Sensitivity ❓ (§8, §10):** no levels in PRD. Required `QB_SENSITIVITY_LEVELS_JSON` maps level -> roles that may see it; retrieval filters on it before ranking. `.env.example` proposes internal/confidential/restricted — tell us real levels. Pre-M3 documents are `unclassified`, **not retrievable until admin classifies** (fail closed).
- **Effective date/expiry (§8):** retrievable only from effective date until expiry.
- **Recheck (§8):** `still_eligible()` re-checks cited versions at answer time (M4).
- **Vault (§8, §11):** Git repo at `QB_VAULT_DIR`; folder = first department ("Sales - Fresh Seller" -> `Sales/Fresh-Seller/`); archived notes move to `Archive/`; one commit per publication naming approver. Front-matter keys (veto): `id, title, category, departments, sensitivity, owner, approved_by, source, effective_date, expires, version, status, checksum, updated`. Necessity: `git` on server.
- **Obsidian import (§14 P0):** `.md` or `.zip` vault (skips `.obsidian/`, `Archive/`); front matter fills fields; each note a proposal; a publisher may record own approval at import (high-impact still needs second person); re-import ignored (duplicate key).
- **Uploads:** PDF/DOCX/TXT/MD; extracted text stored on version for review/diff and vault.
- **Deleting:** only never-published documents; published ones archived.
- **First classification:** pre-M3 docs get first access level in bulk by a publisher (Documents -> "Classify now"), recorded as permission change; afterwards via reviewed proposals.
- **Dashboard/Insights/System (§7):** figures computed from stored data (aggregate only). "Potential duplicates" and "conflicting policies" have no PRD rule -> empty (reviewers see related docs per change). "Published over 6 months ago" info only. System shows models/RAG settings read-only (server config), integration health, last backup, vault commit, **incident switch** pausing all answers with a message (search keeps working), audited CSV export of audit log (§10).
- **Measured on owner's laptop (CPU, real models):** answer p95 15 s, search p95 4 s over 27 questions, above §2 targets (8 s / 2 s); production sizing + AT-09 (M7) must fix (docs/backend.md).

### 0.7 Hermes, Telegram, Obsidian (owner 2026-10-17)
**Built 2026-10-17** after M3. PRD §9 flow; §14 puts it in P2/Phase 3, §16 says must not delay Phase 1 — optional, off until settings filled. Plan: `docs/HERMES_TELEGRAM_OBSIDIAN_PLAN.md`.

Design choices (veto if needed):
- **Sender confirmation:** Hermes can't prove who talks to it, so every Hermes proposal waits until the *linked Telegram account* taps Confirm in backend-owned approvals bot. `QUIXOTIC_DEFAULT_TELEGRAM_USER` may name the one Hermes-bot user.
- **Telegram approvals** follow web rules (reviewers for their departments, publisher approval, two people for high-impact; CEO counts as publisher, so CEO + one more publishes a refund rule).
- **Obsidian:** push to `proposals/<name>` (SSH key restricted by server hook) -> proposals for every note changed since branch split from `main`; same content proposed once. Notes need `departments:` and (new) `sensitivity:` front matter; person told when a note wasn't sent. After publication `main` merged into each linked branch (`-X theirs`) so official note replaces theirs. ❓ O6: a *rejected* note stays on their branch until changed/deleted (no auto revert).
- **Retention:** backend stores only proposal text, voice transcript, event ids; Telegram text not kept elsewhere. ❓ O5 retention period open.
- **Two bots** (Hermes chats; backend-owned Approvals takes Approve taps, ID checked by backend not AI); Hermes self-written **skills and memory disabled** (§15); CEO vault pushes over SSH to `proposals/ceo` only, `main` written only by backend after approval.

| Topic | PRD | Owner decision |
|---|---|---|
| When | §14 P2, §16 | Build after M3; beside M4–M7 only if no delay to §16 release |
| Deployment | §11 Hermes optional Phase 2 | Same EC2, Compose service |
| Obsidian | §8, §1/§9 | CEO uses Obsidian desktop + Git sync to separate *proposals* area, never published vault; each change = Draft/Under Review proposal with diff |
| Approval | §3, §9 step 5 | CEO confirms in Telegram (diff; Approve/Revise/Reject). High-impact (HR, pay, discounts, refunds, customer payments, security) also needs second approver — proposed Knowledge Admin in web Approvals ❓ confirm |
| Voice | §9 step 2, §10 | OpenAI speech-to-text; uncertain segments flagged |
| Hermes permissions | §15, §11 signed `POST /integrations/hermes/knowledge-proposals` | Only backend tools (search approved docs, create proposal, proposal status) via signed endpoint; no shell/files/direct vault writes |
| Senders | §9 step 1 | Allowlisted Telegram IDs mapped to company users with Founder/CEO or Knowledge Admin authority |

Still open ❓: bot token + allowlisted IDs (AWS Secrets Manager/server env only, §10); retention of messages/audio (§9 step 2); Discord now or later; pinned Hermes version (necessity); rejected Obsidian edit handling (proposed: revert on CEO's branch + Telegram explanation).

---

## 1. Required settings with no default (app won't start without)
| Setting | PRD § | Note |
|---|---|---|
| `QB_CHUNK_SIZE`, `QB_CHUNK_OVERLAP` | 13.3 | no strategy/size; characters ❓ |
| `QB_MAX_UPLOAD_BYTES` | 51 | no number (mock-up 50 MB) ❓ |
| `QB_CANDIDATE_COUNT` | 7, 27 | 20–40 enforced; value yours ❓ |
| `QB_FINAL_CHUNK_COUNT` | 7, 27 | 5–8 enforced; value yours ❓ |
| `QB_HISTORICAL_TOP_K` | 11.3, 30 | no rule for "similar" ❓ |
| `QB_ROMAN_URDU_MIN_RATIO` | 22 | no Roman Urdu/mixed boundary ❓ |
| `QB_CONFIDENCE_HIGH/MEDIUM` | 31, 32 | no thresholds; calibrate (§58–§59) ❓ |
| `QB_GENERATION_PROVIDER`, `QB_GENERATION_MODEL_ID` | 28, 44 | Stack: Gemini/OpenAI/Claude, Bedrock later (all 4 implemented). Model id yours ❓; Claude needs `QB_GENERATION_MAX_TOKENS` |
| `QB_RERANKER_PROVIDER/MODEL` | 27 | `BAAI/bge-reranker-v2-m3` CPU; no longer a gap |
| `QB_PRIORITY_TIERS_JSON` | 20 | tiers named, not which `document_type` fits; empty = reranker order ❓ |
| `QB_SESSION_TTL_SECONDS` | 41 | no lifetime ❓ |
| `QB_SESSION_SECRET` | 41 | JWT key >=32 chars (HS256; Cognito can replace later) |

## 2. Undefined plug-ins (job fails clearly until provided)
| Plug-in | PRD § | Missing |
|---|---|---|
| `ConversationParser` | 17 | Discord JSON export schema; customer vs agent detection (§17.2) ❓ send sample export |
| `MemoryExtractor` | 17.2, 16.2 | extraction of objection, intent, stage, outcome, value, discount ❓ |
| `quality_score` | 16.2, 17.2 | undefined -> `NULL` unless extractor sets it ❓ |
| Anonymizer: addresses, customer IDs | 18 | formats unknown. Done: usernames, emails, phones, cards (Luhn), passwords/API keys/secrets. Pass `extra_patterns` for rest ❓ |

## 3. Undefined behaviour — what code does meanwhile
**Access & workflow**
- ❓ `access_level` (§12.2 "Sales + Managers", §14) is a label; **enforcement by department only** (§10, §42); "+ Managers" not enforced.
- ❓ "Company Wide" (§10) no implicit visibility; assign like any department.
- ❓ §9.1 "sales recommendations if permitted": permitted = user authorized for memory's `department_id`; sales history added only in `mode = sales_coach` (§11.3 "when appropriate" undefined).
- ❓ Sales memories require `department_id` (no PRD access rule).
- Submit moves `draft -> submitted -> pending_review` in one action (§12.3 silent on who does step 2); both in history.
- Activating a version archives previous active (§15); DB constraint: one active per item.
- Admin direct publish allowed (§9.4, §12.3): chain still checked/audited. Contributor uploads always go to review (§9.2).
- ❓ No path to `expired` (§12.3).
- Managers act on departments where they are `departments.manager_id` (§10).
- ❓ `DELETE /v1/documents/{id}` (§37): admin only; removes version, chunks, S3 object. Archiving (§9.4) separate.

**Retrieval & answers**
- Hybrid candidates (§26): union of both legs, de-duplicated, vector hit first; no score-fusion formula; reranker orders (§27).
- ❓ Reranker priorities (§27): current-ness and permissions are hard filters before ranking; no extra weighting.
- ❓ Keyword search (§25): PostgreSQL FTS (`simple`, OR-query, `ts_rank_cd`); not BM25; no Urdu stemming.
- ❓ Confidence = top reranker score (else top cosine); low confidence **skips LLM** (§32), logged as failed question (§35).
- "Successful" historical case = `outcome == "closed"` (§16.2 example).
- Source `section` from Markdown `#` headings and DOCX heading styles; PDF/TXT/JSON/CSV none (§30). JSON pretty-printed, CSV kept as text.
- Sales memories embedded on `customer_message` (fallback `scenario`) (§17.2).
- Language detection: Arabic script -> `urdu`; Latin matched vs Roman Urdu marker list (`data/roman_urdu_lexicon.json`) -> `roman_urdu`/`mixed` by ratio; else `english`. Normalization map holds only §23 example; extend with company vocabulary.
- ❓ Feedback (§21) stored `validated = false`; no validation endpoint (PRD silent).

**Dashboard & insights (§34–§36)**
- ❓ "Retrieval Success" = share of last 7 days' questions where knowledge found; "Questions This Week" = rolling 7 days.
- ❓ "Most Asked Topics", *No Owner Assigned*, *Potential Duplicates*, *Conflicting Policies* return `null` + reason. *Outdated* = status `expired`; *Not reviewed > 6 months* = active versions last reviewed/created > 6 months ago.
- ❓ Dashboard needs `view_department_analytics` (manager+); PRD gives Employees none.

**API (§37–§40)**
- ❓ Routes beyond §37's eight (auth, users, departments, knowledge, api-keys, jobs, dashboard, failed-questions, knowledge-health, audit-logs) are ours. `GET /v1/health` unauthenticated.
- ❓ API-key permission names (`ask, search, documents, sales_memory, feedback`) and rate-limit unit (**per minute**) not in §40. Limiter in-process (several API tasks need shared limiter).
- `/v1/ask` also returns `query_id` (for `/v1/feedback`) and `actions` (§32); `mode` ∈ `general | sales_coach` (§11.4; Search Only = `/v1/search`, Department Brain = `department` field).
- `/v1/ask` sources: `title, section, version, updated` (§30); `/v1/search` results exactly `text, score, source` (§39).

**Front-end (owner design "Ask Quixotic AI")**
- ❓ Design shows **Web Search** and **microphone**; PRD says answers only from company knowledge (§29), voice later (§61): buttons present but say not available; nothing sent.
- ❓ **+** opens §11.4 modes (General, Sales coach, Search only); **Company Knowledge ▾** picks department (Department Brain).
- ❓ §32 "Ask Manager" delivery undefined -> not offered. "Report missing knowledge" (contributors+) and "Search documents" are.
- Owner: employees no dashboard; Sales Memory, Product Hub, Settings/Analytics mock-ups removed (no real data).
- Necessity: optional `QB_FRONTEND_DIR`, `QB_CORS_ORIGINS` read from environment.

**Owner decisions 2026-10-04 (override PRD example)**
- API keys `qx_live_<random>`, no app name inside (PRD §40 shows `qx_live_callcenter_xxxxx`); name is a label.
- No per-minute limits in UI; key has **lifetime**: 1 hour, 24 hours, 1 week, 1 month (30 d), 1 year, or never. Rate limit still available via API (optional, §40).
- Key with no departments covers **all**; key without `user_id` acts as **the creating admin**; with `user_id` acts as that employee (§38).
- Chat history saved server-side, private per user; admins can't read others' chats (§5). API-key calls create no chats. Each question still logged for analytics/failed questions (§35).

**2026-10-05 RAG audit fixes (measured/demonstrated defects)**
- Retrieved text *neutralized*: lookalike `<knowledge>`/`<historical_cases>` fence tags defanged (§52).
- Files with no extractable text (scanned PDF, empty DOCX, headings-only MD) end **failed** with explanation; no OCR (PRD silent).
- Chunks end at sentence boundary if one in second half of window, else whitespace (§13.3).
- Login throttle: 10 failed/identifier/15 min -> 429 for rest of window (§51 gives no numbers). Consequence: deliberate lockout of known account for 15 min; next step IP-aware/CAPTCHA. Unknown account still costs one password hash (timing doesn't reveal accounts).
- Question limit 4,000 chars, not blank; new-user passwords >=8 chars.
- Models load in background thread at start (1–2 min CPU) behind a lock; `GET /v1/health` `"models": "loading" | "ready"`.
- SQS 900 s visibility timeout.
- Chunk `metadata.status` synced on status change (retrieval reads live status).

**More audit changes (2026-10-05)** (real BGE-M3 + bge-reranker-v2-m3, 134 chunks, 46 labelled q + 10 unanswerable)
- Chunks **embedded with title and section** (`"Refund Policy - 2. Timeline\n<text>"`); stored/shown text unchanged. Vector top-1 0.76->0.89. Existing content needs admin *re-index* once.
- **Keyword leg ignores stopwords** (English + Roman Urdu markers): keyword R@5 0.52->0.74.
- **Reranker reads only top `QB_RERANK_TOP_K`** (required, 8) and ranking **fused with retrieval** (RRF, k=60). Measured: 6/8/12/20 candidates identical, each ~0.5 s on CPU (30 = 11–20 s/question); reranker alone slightly worse at rank 1 (0.85 vs 0.89) and blind to pure Roman Urdu; fusion best. ❓ §27 says reranker cuts 20–40 to 5–8; retrieval still gathers `QB_CANDIDATE_COUNT` but only best 8 reranked.
- **Confidence uses two signals, better counts:** reranker probability (`QB_CONFIDENCE_HIGH/MEDIUM`) and vector cosine (`QB_CONFIDENCE_VECTOR_HIGH/MEDIUM`). Placeholders 0.30/0.01 and 0.65/0.55 answered 80% of answerable, 0/10 unanswerable through. ❓ Re-calibrate (`python -m evaluation.run_eval`).
- **Roman Urdu phrase table** (`data/roman_urdu_lexicon.json` -> `expand`): English meaning appended to *search text* only; seeded with §23 example (`paise wapas` -> `refund`). ❓ Pure Roman Urdu weakest (top-1 0.80; ~half end low): grow table or add LLM query interpretation (§23).
- **DOCX tables extracted** (were dropped); PDF pages merged so rules aren't cut at page breaks. ❓ PDFs no section label (headings unreliable); scanned PDFs need OCR (not built).
- DB connections enable pgvector **iterative index scans** (small dept got **zero** results beside bigger dept's near-duplicates; needs pgvector >= 0.8, ignored on older).
- Latency 4-core CPU: embed question 0.3–0.5 s; search end to end **4.1 s** (was 11–21 s); docs ~0.7 s/chunk. With LLM a full answer 7–9 s vs PRD 5–8 s.

## 4. Implementation necessities (veto any)
- **DeepSeek client (2026-10-17):** OpenAI-compatible `https://api.deepseek.com` via `openai` SDK; key `DEEPSEEK_API_KEY` (§8, §11).
- Argon2id (`argon2-cffi`) · server-side sessions: 32-byte random tokens stored as SHA-256, HttpOnly cookie + per-session CSRF · TOTP MFA (`pyotp`, QR via `segno`), secret encrypted with Fernet (`cryptography`) · password policy: >=8 chars, no name/username/email, >=4 distinct chars · abuse limits per IP: 5 sign-ups, 30 attempts, 5 emails/hour; 10 failed logins/identifier/15 min · SHA-256 hashed API keys (shown once) · `psycopg` 3 plain SQL (no ORM) + plain `migrations/*.sql` runner · pgvector `vector(1024)` HNSW cosine (BGE-M3 1024-d; model change = migration + re-index, §24.2) · `sentence-transformers` (BGE-M3, cross-encoder) · `pypdf`, `python-docx` · `boto3` (S3, SQS, Bedrock Converse) · CPU-only PyTorch · synchronous endpoints · Docker `python:3.14-slim` · `tenant_id` on business tables (§66) · `jobs` table (§47).

**M7 release readiness (2026-10-18)**
- Audit log (§10): append-only (UPDATE/DELETE refused by trigger) + SHA-256 hash chain; System -> "Verify audit log" / `GET /v1/admin/system/audit-verify`; chain tip in every backup manifest.
- Job queue (§11): Redis list + processing list (survives worker crash); SQS possible (`QB_QUEUE_BACKEND`).
- CPU model micro-batching (`backend/retrieval/batching.py`, 10 ms window, 64 items): concurrent questions share embedder/reranker calls. 4-core laptop: 20-request burst p95 4.5 s -> 1.7 s.
- AT-09 on that laptop (search only): 160 sessions OK; 40-concurrent baseline p95 4.5 s, 160 burst p95 11.9 s, above 2 s target -> size server with `scripts/load_test.py` (docs/DEPLOYMENT.md §8).
- Production: Compose on one EC2 (owner); Caddy 2.8 HTTPS (Let's Encrypt) + HSTS/security headers; pgvector 0.8.0-pg16; Redis 7.4 AOF; container uid 10001; JSON log rotation 10×20 MB.
- Backups (§16 g): `pg_dump` custom + vault tar.gz + SHA-256 manifest to S3 with AES256; weekly drill restores into throw-away DB and checks rows, checksums, audit chain. Retention by S3 lifecycle ❓ (35 days proposed).
- Hermes image pinned by digest (v0.22.2), verified locked down: only `clarify` + five quixotic tools (`computer_use`, `connections` had to be disabled explicitly).

**Local dev setup (2026-10-07; tooling only)**
- `scripts/dev_up.py` drops trailing `# comments` from `.env` values (like python-dotenv), stops clearly if `.env` missing (before, `QB_SESSION_TTL_SECONDS=28800  # PLACEHOLDER` failed validation).
- `.env.example` working local template: comments on own lines, dummy `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` for moto, `QB_RAW_STORAGE_DIR=.devstore`, `QB_FRONTEND_DIR=web/dist`, models by HF id (`BAAI/bge-m3`, `BAAI/bge-reranker-v2-m3`).
- `requirements-dev.txt` installs `moto[server]`.
- `Start Quixotic AI.bat` uses project `.venv` Python if present; stops with message if Docker not running.

## 5. Deliberately not built
PRD §5 non-goals; SSO; §13.1 Google Drive/website/Notion/Slack/email/CRM; §45 Qdrant migration; §61 Phase 5 (feedback-based improvement, gap detection beyond failed questions, model benchmarking, fine-tuning, local LLM, voice, agents); §55 CloudWatch dashboards, §54 backup config, §51 HTTPS/private RDS/S3/Secrets Manager (infrastructure, no IaC choice in PRD); §59 metrics other than Recall@5, Recall@10, MRR (need labelled data/logs undefined).

## 5b. Measured with real models (BGE-M3 + `bge-reranker-v2-m3`, CPU)
- ❓ **Pure Roman Urdu retrieval weak.** English/mixed work (`customer is asking for refund kya karun?` -> refund, cosine 0.597 vs 0.447). Pure fails: `customer paise wapas mang raha hai` scores *discount* 0.397 vs *refund* 0.372; reranker gives every candidate floor score. §22 requires it; §23 shows "semantic interpretation" but not in §7 pipeline. Options: (a) LLM query interpretation (latency/cost), (b) grow `backend/data/roman_urdu_lexicon.json`, (c) both. Two `test_models.py` tests marked expected-failure to keep it visible.
- ❓ **Confidence thresholds need calibration.** BGE reranker probabilities small for short correct snippets (0.01–0.5), so 0.5/0.75 would call correct answers "low". Local `.env` placeholders 0.3/0.005 from tiny sample. `python -m evaluation.run_eval` on real docs prints score ranges answerable vs unanswerable to pick Medium/High.
- Necessity (measured): reranker reads `title - section` with chunk text (relevant chunk −3.8 -> −1.3 logit on short snippets, ranking elsewhere unchanged).

## 6. Verification status
- **Real PostgreSQL 16 + pgvector 0.8.7** (`QB_TEST_DATABASE_URL`, fresh DB per test): migration, SQL stores, permissions-before-retrieval, hybrid search, `status = active` filter, archived-on-request, version supersession (§15) + one-active DB constraint, ingestion with §14 chunk metadata, API keys, jobs, query log, feedback, audit log, dashboard, sales-memory search, login by email or employee ID; full HTTP flow JWT login -> upload -> S3 -> SQS -> worker -> search -> ask -> feedback -> failed question -> audit -> archive.
- **Mocked AWS (moto):** S3/SQS adapters with §46 paths.
- **Unit:** config rules, role matrix, workflow edges, language detection/normalization, extraction/chunking, anonymization, retrieval rules, prompt rules, credentials, API-key auth + rate limit.
- **Real models:** BGE-M3 and reranker on CPU; English and mixed work, pure Roman Urdu measured gap (§5b); model-backed e2e passes.
- **Not run:** Gemini/OpenAI/Claude/Bedrock calls (no keys; e2e uses fake generator), Cognito, ECS, RDS, Secrets Manager.

## Owner-requested: faster + better Urdu/Roman Urdu (2026-10-05)
Not in PRD; veto any.
- **Prompt rule 8** (`backend/generation/prompt.py`): answer in user's language and script (§22).
- **Query interpretation** (`QB_QUERY_INTERPRETATION=true`): one small LLM call for Urdu/Roman Urdu/mixed only; restates in English, appended to search text (§23; place in §7 unspecified). ~0.9 s + one LLM call per non-English q; never raises (falls back to plain search).
- **Vocabulary** (`/v1/vocabulary`, migration 003, admin-only `manage_vocabulary`, "Vocabulary" page): admins teach phrase -> English; in search text within 60 s. Failed questions have "Teach a word". Audited.
- Marker list expanded to 186 words in `backend/data/roman_urdu_lexicon.json`.
- **`QB_RERANK_SKIP_MARGIN=0.04`**: skip reranker when top vector hit leads second by >=0.04. **`QB_FINAL_CHUNK_COUNT=5`, `QB_RERANK_TOP_K=5`**. From synthetic benchmark (`docs/RAG_AUDIT.md`), not PRD; re-measure on real docs.
- Answer model `gpt-4.1-mini` (small bake-off); change via `QB_GENERATION_MODEL_ID`.
- 4 of 22 Urdu/Roman Urdu synthetic questions still low; fix via Vocabulary; thresholds placeholders.

## Fixes from owner's first real document (2026-10-05)
`Quixotix_Company_Knowledge_Base.pdf` (23 pages, 63 numbered sections). Necessities; veto any.
- **PDF cleaning** (`backend/ingestion/extract.py: pdf_blocks`): lines repeating on most pages (header/footer) and bare page numbers dropped; bullets -> `- `; wrapped lines re-joined; numbered heading ("9. Department-Based Knowledge Access") starts new section so sources cite it (§30). Before: every chunk carried "QUIXOTIX / INTERNAL COMPANY KNOWLEDGE BASE / Page 16", no section. Heuristic: short numbered line without final punctuation = heading; PDFs without numbered headings stay section-less.
- **Reranker skip** needs clear lead AND vector score >= `QB_CONFIDENCE_VECTOR_HIGH` (was any score; "Who is the founder?" lead with 0.52 was labelled low). Real PDF: answerable 0.52–0.73, unanswerable up to 0.56.
- **`QB_RERANK_TOP_K=3`** (was 5), may be smaller than `QB_FINAL_CHUNK_COUNT`: reranker reads 3, others follow in retrieval order so model still gets 5 (§27). Right chunk in retrieval top-3 for 25/25 (top-1 23/25). Reranker ~1.2 s per 1,000-char chunk on 2-core i5-6200U; bf16 10x slower, more threads no help. Bigger CPU faster; re-check on larger corpora.
- **Prompt rules 9 and 10** + per-question note when no historical conversations retrieved: text introduced as "Example:" is not policy (§30 example "Customers can request a refund within the approved refund period" was answered as refund policy); model may not claim "worked in past sales" without historical cases (§19, §20, §29).
- **Worker no longer loads reranker** (`build_services(warm_reranker=False)`): saved ~4.5 GB (API+worker were ~9 GB on 16 GB machine).
- **`QB_RAW_STORAGE_DIR`** (local dev only): in-memory S3 emulator lost originals on restart; originals kept in `.devstore/` (git-ignored). Production S3 (§46).
- Admins get per-step `timings` (embed/database/rerank) in `/v1/search` debug output.
- Questions asked while a document is processing find nothing and log as failed questions; wait until ready.

## Owner-requested: account menu, personalization, chat memory, access at scale (2026-10-05)
Not in PRD (§9, §41, §42 describe none); veto any.
- **Account menu** (sidebar, all roles): Personalization, Profile, Settings, Log out.
- **Profile** (`PATCH /v1/auth/profile`): own name + picture (PNG/JPEG/WebP data URL, resized to 256 px, max ~300 KB, `users.avatar`; SVG/links refused). Migration 004. Role/departments admin only (§9.4).
- **Settings** (`POST /v1/auth/password`): change own password (current required, min 8, wrong attempts throttled 10/15 min); audited `admin_action` (§53 has no password event). "Delete all my chats" (`DELETE /v1/conversations`, own only).
- **Personalization** (`PUT /v1/auth/preferences`, `users.preferences`): answer length, tone, reply language, "about me", custom instructions. Only known values, <=500 chars (`clean_preferences`); reach model in fenced `<user_preferences>` (`neutralize` applies); rule 12: style only, never overrides rules/sources (§29, §52).
- **Role-tailored answers:** model told asker's role + department names (`<asker>`, set by system, rule 11); tailors tone/depth only; visibility decided by departments before retrieval (§42). API-key calls get neither asker nor preferences.
- **Who sees what** = department model: admin creates departments (e.g. "Managers", "Employees", "Finance", "HR"), uploads knowledge, assigns people. Users page: search, role/department filters, **bulk give/remove access** (`POST /v1/users/bulk-departments`, audited `permission_change`). §10 seed list unchanged; "Managers"/"Employees" created by admin.
- **Chat memory:** last 6 exchanges (answers cut to 800 chars; was 2/600) in `<conversation>`; rule 7 lets model use user's stated situation (e.g. customer's name), not as company facts. Follow-ups restated as standalone search query by one small model call (~1 s, any language; first questions none). Reranker reads that clean restatement (measured 0.52 vs 0.01–0.18).
- PDF headings: numbered top-level heading above sub-headings ("6. Major Services" above "6.1 ...") kept as prefix of sub-section labels.
- Confidence thresholds on real PDF (30 answerable, 18 unanswerable): placeholders unchanged (reranker 0.01/0.3, vector 0.55/0.65). Groups overlap reranker 0.004–0.01; answer prompt refuses non-answers. "What services do you sell?" still low though §6 answers it. Re-calibrate with more docs.

## Owner-requested: self sign-up with approval (2026-10-05)
§41 silent on account creation; veto any.
- **Create an account** (login link; public `POST /v1/auth/register`): full name, username (3–30 chars lowercase letters/digits/`.` `-` `_`, in `employee_id`), email, password (min 8), optional department. Login accepts username or email, any case. Created **pending** (`approval_status`, `is_active=false`, role employee, no departments): can't sign in, sees nothing. Migration 005.
- Pending/rejected sign-in says why ("waiting for approval"/"not approved") only after correct password; wrong password gets generic 401.
- **Approval** (Access requests page, `GET/POST /v1/access-requests...`): **administrator** approves anyone, any role/departments. **Manager** sees only requests for own departments (or none), approves **employee/contributor only**, grants only departments **they belong to** (§9.3). >=1 department required (§42). Rejecting keeps row. Decisions audited `permission_change`; so are sign-ups.
- **Spam limits** (per address, in memory): 5 accounts/hour, 30 attempts/hour.
- `GET /v1/auth/signup-options` public, department names only.
- Isolation = department rule (permissions before retrieval, §42), tested: Finance user never retrieves Employee-only knowledge and reverse, search + ask; both groups (admin, bulk) -> both visible.
- (Superseded by M1) no email verification/notification originally.

## One answer by default (2026-10-05, owner)
Chat showed "Matching knowledge" list for Search-only and "Search documents" on low confidence. Now normal questions return ONE written answer; search view shows single **best match**, others behind "Show N more matches" (§11.4 Search Only, §32 `search_documents` stay); under answer 2 sources, rest behind "+N more sources"; "Search documents" is one-off (chat stays normal mode); opening old search-only chat no longer keeps later questions in list mode.

## Owner-requested: learning from 👍/👎 (2026-10-05)
§21 only stores feedback (new experiences searchable *after validation*); "feedback-based improvements" = Phase 5; §5 forbids "automatic fine-tuning after every interaction" and "autonomous agents modifying company data without approval". So learning changes **ordering and phrasing, never knowledge**, bounded, visible, reversible. Veto any. Migration 006. Switch `QB_FEEDBACK_LEARNING=false` (ratings still stored).
1. **Source quality nudges order** (`backend/learning/feedback.py`): each person's latest 👍/👎 per question counts once, credited to first 2 passages. Passage with >=3 ratings: boost=(up−down)/(n+5); candidate order shifted by 0.001×boost atop rank-fusion: 3 ratings ≈ 1 place, near-unanimous ≤ ~4 places. Nothing hidden/edited/deleted; new document version starts clean (new chunk ids); policy priority (§20) untouched. Numbers are mild placeholders.
2. **Personal style patterns:** from own ratings, contrast liked vs disliked (length, lists vs paragraphs; >=3 liked, >=2 disliked, 70% of each group on own side) or repeated "Too long"/"Too short" (>=2). Only-👍 users get no invented preference. Hint reaches model as `learned from their thumbs: ...` (explicit Personalization wins). Shown in Personalization with "Forget what I learned" and "Learn from my 👍 / 👎" switch; one person's ratings never affect another's.
3. **Rejected answers marked:** 👎 answer shown to model as `assistant [not helpful]` (rule 13); `[helpful]` = style to keep.
4. **After 👎 optional reasons** (Wrong answer / Not what I asked / Too long / Too short / Missing information) stored as notes (§21).
5. **Admins:** Insights -> Answer quality: rated answers, helpful %, whether High/Medium/Low matches 👍 rates (calibration aid), sources rated down/up, recent 👎 with reasons + "Add missing knowledge". No person named. "Reset what it has learned" (admin) makes older ratings stop counting; nothing deleted; audited `admin_action`.
- Not done on purpose: reusing past answer for similar question (could leak knowledge new asker can't see; §21 requires validation); auto-changing knowledge or thresholds.

## Owner-requested: past sales chats per department (2026-10-08) — answering from them when no policy exists
Owner uploaded 4,216 extracted sales chat records (JSON object per customer message/agent reply, §16.2 fields) as an ordinary document; never searchable (worker stopped mid-job; jobs left `running` aren't retried; file in Sales while test employee had only Company Wide; plain JSON would only be text-chunked). Owner then asked each department's chats answer that department's staff (Upseller/Fresh Seller apart) and answer from past chats when no policy covers a question, clearly labelled. (Overall gated by `QB_SALES_HISTORY_ENABLED`, OFF since 2026-10-17.) Veto any. Migration 007.
1. **Structured import** (`backend/sales_memory/importer.py`, `parse_structured`): JSON list of objects with `customer_message`/`agent_response` stored as sales memories as-is, without Discord parser/extractor plug-ins (still undefined, §2). Field names per §16.2; `stage` read as `sales_stage`; unknown fields dropped. §17.2 applied: anonymize (customer message, agent reply, objection), detect language if missing, embed customer message, store. `customer_objection` own column (§17.2). Embedded 32 at a time.
2. **Per-department import screen** (Knowledge -> Sales memory, admins, §17.1): choose department, drop JSON, see "Detected: N conversations, M messages", progress, stored count, **remove import** (`DELETE /v1/sales-memory/imports/{job_id}`, audited). `GET /v1/sales-memory/imports` lists. Upseller vs Fresh Seller split by owner uploading separate files; no auto split rule.
3. **Past chats in every Ask mode + history-only answers** only when `QB_SALES_HISTORY_MIN_SIMILARITY` set (unset = PRD behaviour: history only in Sales Coach, never answering alone).
   - Past chats from asker's departments (same filter as knowledge, §42) with cosine >= setting go to answer model in General mode too.
   - No approved knowledge or low confidence (§29, §32): answer from those chats only, always starting *"Based on past sales chats, not an official Quixotic policy. No approved policy or SOP covers this yet."* (§19). Rule 14: never present as policy or state prices/discounts chats don't show; confidence from chat similarity on vector thresholds (§31); still logged as failed question (§35). §20 unchanged: policy leads when it exists.
   - MEASURED (800 chats, BGE-M3): sales questions 0.58–0.72; small talk matches better ("hello" 0.97, "thanks" 0.88); unrelated 0.49–0.68. Similarity only pre-filters (placeholder **0.55**); model must confirm chats match situation else `NO_RELEVANT_HISTORY` and §29/§32 answer shown. Check is a note right before the question (system-prompt rule alone ignored: "hello" got "Hello! How can I assist you?"). End to end gpt-4o-mini, 300 chats: 5/6 sales questions answered (incl. Roman Urdu); 6/6 off-topic (hello, thanks, leave days, password reset, joke, capital city) fell back to PRD answer.
   - Import speed (Ryzen 5 2600 CPU): ~0.2 s/record; ~4,000 records ≈ 15–40 min; progress on Sales memory page.
4. Known gap: job interrupted by stopping worker stays `running` forever (upload shows "Processing"); local moto SQS loses queued messages on restart. Re-upload.
