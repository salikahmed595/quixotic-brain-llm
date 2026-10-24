# PRD gaps and implementation necessities
History: git log -p docs/PRD_GAPS.md
Rule (`CLAUDE.md`): PRD is the only truth. Where silent, code requires an explicit setting/plug-in or does the smallest thing, listed here. ❓ = owner decision open (stated behaviour applies meanwhile). "veto" = owner may reject. Citations in code/older text may refer to the superseded PRD (`docs/archive/PRODUCT_quixotic_brain_v0.md`); new work cites the current PRD.

## 0. Current behaviour and decisions

### Accounts, auth, roles (M1–M2)
- Five account states (§5 FR-AUTH-05) in `users.account_status`; history in `account_status_history`; leaving Active revokes all sessions.
- Email verification required before approval; `QB_MAIL_BACKEND` = `smtp`|`console`. ❓ production SMTP service + sender.
- Argon2id (old scrypt rehashed on login). Server-side sessions, HttpOnly `qb_session` cookie, CSRF, `QB_SESSION_TTL_SECONDS`, `POST /v1/auth/logout`. Password reset: one-time link (`QB_ONE_TIME_LINK_TTL_SECONDS`), always 202.
- Admin MFA = TOTP (veto): required for Knowledge Admin, System Admin, Founder/CEO when `QB_ADMIN_MFA_REQUIRED=true` (keep true in prod); secret encrypted with `QB_FIELD_ENCRYPTION_KEY`.
- First admin: `python -m backend.cli bootstrap-admin` (refuses if a System Admin exists).
- Signup: full name, username, work email, password+confirm, requested department (required), optional phone; role always Employee.
- Roles (veto): contributor->employee, manager->department_reviewer, administrator->system_admin; plus `knowledge_admin` (publishes only with `can_publish`), `founder_ceo`. Page access per §7 page (`backend/permissions/roles.py`). Knowledge Admin, System Admin, Founder/CEO search all departments. ❓ confirm Founder/CEO pages.
- "Company Wide" never implicit (§4.2, §15).
- ❓ Self-approval: managers can approve own uploads; which changes need separation of duties?

### Knowledge, retrieval, answers
- Statuses Draft/Under Review/Approved/Published/Archived. ❓ old `rejected`/`expired` mapped to Archived; keep as change outcomes?
- Retrieval: Published, effective date reached, not expired.
- LLM: OpenAI now; DeepSeek later via `QB_GENERATION_PROVIDER=deepseek`, `DEEPSEEK_API_KEY` (`https://api.deepseek.com`, `openai` SDK). Keys only in Secrets Manager/server env (§10). Model ids required.
- Not-found: exactly "I couldn't find an approved answer in the company knowledge base." + Report missing information (internal word `NO_APPROVED_ANSWER`).
- Knowledge gaps: `knowledge_gaps`, `knowledge_gap_reports`; routing (veto): question's department, else asker's only dept, else unassigned; reviewers emailed; admins see counts/comments, never askers. ❓ de-dup = exact normalized text.
- Past sales chats OFF: `QB_SALES_HISTORY_ENABLED=false` gates all use. Optional history-only answers need `QB_SALES_HISTORY_MIN_SIMILARITY` (placeholder 0.55) and are labelled "Based on past sales chats, not an official Quixotic policy. No approved policy or SOP covers this yet." (rule 14; logged as failed question).
- Confidence label kept in UI (not PRD-required). ❓ keep or remove?
- Answer in question's language (prompt rule 8, §6 FR-CHAT-08).
- Web Search pill and microphone shown but disabled until P1. ❓ OK?

### Knowledge model (M3)
- Every change is a `knowledge_proposals` row with `approval_decisions`; metadata applies only at publication; reject/changes needs a note -> Draft.
- Who decides (veto): Department Reviewer for own departments; Knowledge Admin only with publisher grant; System Admin/Founder/CEO everywhere; publication needs >=1 publisher decision. ❓ approval matrix per department (§3).
- High impact (HR, pay/payroll/salary, discount, refund, customer payment, security) needs two different approvers (§9 step 5), applied everywhere; text detection can raise, never lower.
- Publication (worker): index -> write note to Git vault + commit -> switch version in one DB transaction -> verify retrieval -> on failure restore previous, email System Admins; admins can retry. `still_eligible()` rechecks at answer time.
- ❓ Sensitivity levels: required `QB_SENSITIVITY_LEVELS_JSON` (level -> roles; `.env.example` proposes internal/confidential/restricted). Pre-M3 docs are `unclassified` and not retrievable until classified (Documents -> "Classify now").
- Vault: Git at `QB_VAULT_DIR`; folder = first department (`Sales/Fresh-Seller/`); archived -> `Archive/`; one commit per publication. ❓ Front-matter keys (veto): `id, title, category, departments, sensitivity, owner, approved_by, source, effective_date, expires, version, status, checksum, updated`. Needs `git` on server.
- Obsidian import: `.md` or `.zip` (skips `.obsidian/`, `Archive/`); each note a proposal; re-import ignored.
- Uploads PDF/DOCX/TXT/MD; only never-published docs deletable, else archived.
- Dashboard/Insights/System figures aggregate only; "potential duplicates"/"conflicting policies" empty (no PRD rule). System has incident switch (pauses answers), read-only RAG settings, audited audit-log CSV export.
- ❓ Production sizing: laptop answer p95 15 s, search p95 4 s vs §2 targets 8 s/2 s; run AT-09.

### Departments (owner)
Company General, HR, Sales - Fresh Seller, Sales - Upseller, Production, Marketing, Customer Support, Leadership, Training via `python -m backend.cli seed-departments`. No hierarchy; Glossary/Archive are vault folders. ❓ clear old pre-M3 knowledge rows (irreversible) or keep?

### Owner-approved additions (not in the PRD)
- **Discord Slang Mode** (owner, 2026-10-24): per-user setting in Personalization, default off (`preferences.discord_slang`); when on, every AI-written message (answers, client messages, translations) is short, lowercase Discord-style slang matching the client's vibe; context, sales rules and company facts unchanged; verbosity low. Chat shows a 'Discord slang' chip with X to turn it off.
- **Images** (owner, 2026-10-24): paste (Ctrl+V), drop or attach up to 4 images per question (browser shrinks to 2048 px JPEG; server accepts PNG/JPEG/WEBP/GIF up to 8 MB each); sent to the answer model with the question, never stored (chat keeps '[N image(s) attached]'); text in images is data. **Create image**: mode or 'generate/create an image…' / 'tasveer banao'; `POST /v1/images`, `QB_IMAGE_MODEL=gpt-image-1-mini` (gpt-image-1 not available on this account), `QB_IMAGE_QUALITY`; optional reference images; result returned to the browser, not stored; audit `image_generation` (prompt length only).
- **Image QA upgrade** (owner request 2026-10-25 "make it according to the world best AI"; QA audit): images sent at `detail: high`; follow-ups resend the chat's last image from the browser for 3 messages (`images_earlier`, nothing stored); `[unclear]` for unreadable text; Image 1/2 numbering; screenshot replies start with 'What they're asking'; client messages never promise mockups, delivery times or revision counts; '(worked in past chats)' removed in code unless a closed past chat was retrieved. Image creation: art director returns an asset type, edit flag, fan-art flag and exact text; edits keep the source's size and background (gpt-image-1-mini rejects `input_fidelity`, measured); transparent stickers/emotes touching the frame are redrawn once, then padded; Twitch/YouTube banners and screens are cropped to the platform's exact size; emotes and badges get 112/56/28 and 72/36/18 px files (Discord emote 128); caption built from the measured output in the user's language; fan-art warning for existing characters; 'Final quality' button = quality `high`. Choices made here (sizes from the platforms' published specs, 4% edge margin, 3 follow-up messages) are owner-vetoable. Not done: several variations per request, OCR check of the lettering, brand/style memory, vector export, gallery.
- **Composer and client tone** (owner 2026-10-25): Slang Mode is a quick toggle in the composer (same saved per-user setting as Personalization); Web Search moved into the Company Knowledge menu ('+ Web' on the pill, chip with ✕ while on). Create image mode with a picture attached sends `prefer_image` to /v1/ask and the model decides: draw (CREATE_IMAGE) or read / reply. A pasted message that reads like a client's is treated as client communication (always in scope): reply options in the client's language and script, mirroring their tone (formal, funny, slang; flirty/'romantic' = warm and playful but professional, never flirting back), aimed at selling the artwork without pressure.
- **Web Search toggle** (owner, 2026-10-24; PRD §14 had it as governed P1): off until the user switches it on in the chat; then OpenAI's built-in web_search answers any question (office-only scope lifted for that question) with source links. Quixotic's own facts still only from approved knowledge; web pages are data. `QB_WEB_SEARCH_ENABLED`; logged with confidence `web` (migration 016).
- **Answer model gpt-5-mini** (owner, 2026-10-21; was gpt-5-nano): measured on the same 3-turn chat, nano skipped follow-up questions and wrote client messages in Roman Urdu at times (37-157 s); mini followed the format every turn in 6-23 s.
- **Follow-up questions + 3 options** (owner, 2026-10-21): unclear client situations get 2-3 short questions first (once per situation), then 3 options modelled on closed past chats.
- **General assistant** (owner, 2026-10-21, `QB_GENERAL_ASSISTANT=true`): answers like a basic ChatGPT but for office work only (client replies, sales, policies/SOPs, work writing, translation, design work); greetings get one line; anything else gets a fixed polite "office work only" reply (`OFF_TOPIC`). Approved policies (permission-filtered as before) and similar past chats are passed as context; weak matches are left out. Overrides §6 FR-CHAT-04's fixed refusal. Kept: company facts (prices, discounts, refunds, deadlines, rules) only from approved knowledge; a missing one is said plainly and becomes a knowledge gap (`MISSING_COMPANY_INFO`). UI tag "General AI answer".
- **Office assistant mode** (owner, 2026-10-21): approved knowledge (department policies) = primary source; past sales chats = secondary (`QB_SALES_HISTORY_ENABLED=true`, examples of how people handled a situation, never policy). Every suggested client reply follows the owner's selling boundaries (trust, authenticity, not greedy, client satisfaction first; prompt rule 15) and is given in client-ready English with a short why in the user's language (rule 16). "What should I reply?" with no policy and no matching past chat: `QB_GENERAL_GUIDANCE=true` gives advice labelled "General guidance, not company policy", rejected by code if it contains a price, amount, %, discount or time promise; still logged as a gap. Other questions without evidence keep the exact §6 FR-CHAT-04 reply.
- **Translate for client for everyone** (owner, 2026-10-21): `QB_TRANSLATE_DEPARTMENTS=all`.
- Visibility check `_may_see` now also requires the access level (§8); before, department alone decided (found in this audit).
- **Translate for client** (owner, 2026-10-20): upsellers and fresh sellers write a client message in Urdu / Roman Urdu and get polite, client-ready English (`POST /v1/translate`; chat Answer mode "Translate for client"). Who gets it: members of `QB_TRANSLATE_DEPARTMENTS` (comma-separated names; unset = off), checked on the server. It uses the configured answer model with `TRANSLATE_PROMPT` (keep every number, price and date; add no prices, discounts or promises; the text is data). No company documents are used. The message is not stored: there is no chat history and no query log, and the audit entry `translation` records only the length. Limit: 2,000 characters. ❓ Should admins and reviewers also get it?

### Platform, API, UI
- API: `/v1/auth/*`, `/v1/admin/*`, `/v1/knowledge/*`, `/v1/chats` (+`/messages`), `/v1/ask`, `/v1/conversations` kept. Chat search covers own titles/messages only.
- Frontend `web/` (React 18, Vite 6.3, Tailwind 4.1, TS 5.8; Node 24 in Dockerfile), served via `QB_FRONTEND_DIR=web/dist`. Font Plus Jakarta Sans ❓ veto. Mascot SVG `web/src/components/Mascot.tsx`. "Company Wide" card only for admins or members of every active department. **+** button = Answer | Search only ❓ (PRD silent). Provider failure -> 503 with Retry.
- Screenshots: `UI images/reference/`. Employee shot shows "Company Wide" (treated as demo). "Web Search" with a space.
- AT-08 `web/tests/visual.spec.ts` (veto): pixelmatch 0.2, max 0.8% differing, chat titles/mascot/Workspace scrollbar masked, 44 px targets at 375 px. Dev deps Playwright 1.63, pixelmatch 7.1, pngjs 7.0.
- Queue Redis (`QB_QUEUE_BACKEND`, SQS possible). Deployment: one EC2 Compose (`docs/DEPLOYMENT.md`). ❓ staging second instance or same server?
- Audit log append-only (trigger) + SHA-256 chain; verify `GET /v1/admin/system/audit-verify`. Micro-batching `backend/retrieval/batching.py`.
- Backups: `pg_dump` + vault tar.gz + manifest to S3 AES256; weekly drill. ❓ retention (35 days proposed).
- Stack versions: Caddy 2.8, pgvector 0.8.0-pg16, Redis 7.4 AOF, uid 10001, log rotation 10×20 MB, Docker `python:3.14-slim`. Obsidian hook calls signed with `QB_VAULT_HOOK_SECRET` (HMAC-SHA256, >= 32 chars, 5-min window); unset = push endpoint off.

### Obsidian (§9)
- Hermes agent and Telegram removed by owner 2026-10-21 (PRD §9/§14 Phase 2 channel not used); Obsidian sync kept, hooks signed with QB_VAULT_HOOK_SECRET. Migration 014 withdraws proposals still waiting for a bot confirmation (versions back to draft).
- Obsidian (owner 2026-10-20, 3 contributors): one private repo per person (`QB_VAULT_CONTRIBUTORS_DIR/<name>.git`); `main` = published, in-force notes their account may see (departments + sensitivity), rewritten after each publication, link, access change; inactive/unlinked = empty. SSH forced command `vault-shell` = only own repo, only pull/push; hooks: push only `proposals/<name>`, no delete/force. Push -> proposal per changed note (create/update/archive); editing a note outside their view refused; same content proposed once; one open change per document; `main` merged into their branch (`-X theirs`), failed merge = `conflict` event, branch untouched. Missed hook calls: worker reconcile every 300 s. Activity: `GET /v1/admin/integrations/obsidian/activity`. Old single shared repo (`QB_VAULT_REMOTE` for contributors) removed: it gave everyone every note.
- ❓ second approver for high-impact (proposed Knowledge Admin); ❓ rejected Obsidian edit (now stays on branch; proposed revert); ❓ Discord now or later.

## 1. Required settings, no default
| Setting | PRD § | Note |
|---|---|---|
| `QB_CHUNK_SIZE`, `QB_CHUNK_OVERLAP` | 13.3 | characters ❓ |
| `QB_MAX_UPLOAD_BYTES` | 51 | ❓ |
| `QB_CANDIDATE_COUNT` | 7, 27 | 20–40 ❓ |
| `QB_FINAL_CHUNK_COUNT` | 7, 27 | 5–8 (5) ❓ |
| `QB_HISTORICAL_TOP_K` | 11.3, 30 | ❓ |
| `QB_ROMAN_URDU_MIN_RATIO` | 22 | ❓ |
| `QB_CONFIDENCE_HIGH/MEDIUM`, `QB_CONFIDENCE_VECTOR_HIGH/MEDIUM` | 31, 32 | placeholders reranker 0.30/0.01, vector 0.65/0.55 ❓ calibrate |
| `QB_GENERATION_PROVIDER`, `QB_GENERATION_MODEL_ID` | 28, 44 | `gpt-4.1-mini` now ❓; Claude needs `QB_GENERATION_MAX_TOKENS` |
| `QB_RERANKER_PROVIDER/MODEL` | 27 | `BAAI/bge-reranker-v2-m3` CPU |
| `QB_RERANK_TOP_K` (3), `QB_RERANK_SKIP_MARGIN` (0.04) | 27 | skip also needs vector >= `QB_CONFIDENCE_VECTOR_HIGH`; others follow in retrieval order |
| `QB_PRIORITY_TIERS_JSON` | 20 | empty = reranker order ❓ |
| `QB_SESSION_TTL_SECONDS`, `QB_SESSION_SECRET` (>=32 chars) | 41 | ❓ TTL |
| `QB_QUERY_INTERPRETATION` | 23 | true: small LLM restatement for non-English questions |
| `QB_FEEDBACK_LEARNING` | 21 | false disables learning |
| `QB_RAW_STORAGE_DIR` | 46 | local dev only |
| `QB_FRONTEND_DIR`, `QB_CORS_ORIGINS` | — | optional |

## 2. Undefined plug-ins (job fails clearly until provided)
`ConversationParser` (§17 Discord export schema ❓ send sample), `MemoryExtractor` (§17.2, §16.2 ❓), `quality_score` (NULL ❓), anonymizer extras for addresses/customer IDs (§18 ❓; done: usernames, emails, phones, cards, secrets; `extra_patterns`).

## 3. Undefined behaviour — what code does
**Access/workflow**
- ❓ `access_level` is a label; enforcement by department only (§10, §42). ❓ no "Company Wide" implicit. ❓ sales memories need `department_id`; sales history only in `sales_coach` (when enabled).
- Submit goes draft->submitted->pending_review in one action. Activating archives the previous active version. Admin direct publish allowed (chain still audited); contributor uploads go to review.
- ❓ No path to `expired`. Managers act via `departments.manager_id`. ❓ `DELETE /v1/documents/{id}` admin only.

**Retrieval/answers**
- Hybrid: union of vector+keyword, de-duplicated; no fusion formula; reranker ranking fused with retrieval (RRF k=60). Current-ness/permissions are hard filters.
- ❓ Keyword = PostgreSQL FTS (`simple`, OR, `ts_rank_cd`), stopwords ignored, not BM25.
- ❓ Confidence = better of reranker probability and vector cosine; low skips LLM (§32), logged as failed question (§35).
- "Successful" historical case = `outcome == "closed"`.
- Section from Markdown/DOCX headings; PDFs: numbered headings only (repeated headers/footers dropped, numbered top heading prefixes sub-sections). ❓ scanned PDFs need OCR (not built); files with no text end failed.
- Chunks: sentence boundary, embedded with title+section (re-index after change); DOCX tables extracted.
- Language: Arabic script -> `urdu`; Latin vs `backend/data/roman_urdu_lexicon.json` markers (186) -> `roman_urdu`/`mixed`/`english`. Phrase table `expand` appends English meaning to search text. ❓ pure Roman Urdu weak: grow lexicon / Vocabulary (`/v1/vocabulary`, admin, taught within 60 s, "Teach a word" on failed questions).
- Follow-ups restated by one small model call; last 6 exchanges (answers cut to 800 chars) in `<conversation>`; reranker reads clean restatement.
- Prompt rules: 7 (user's stated situation, not company facts), 8 language, 9–10 ("Example:" text is not policy; no "worked in past sales" without cases), 11 `<asker>` role/departments tailor tone only, 12 preferences style only, 13 `[not helpful]` answers not repeated, 14 history-only labelling. Retrieved text defanged of fence tags (§52).
- pgvector iterative index scan enabled (needs >= 0.8). Worker does not load reranker. `/v1/search` debug gives `timings` for admins. Questions during processing find nothing.
- ❓ Feedback stored `validated=false`, no validation endpoint.
- Dashboard: ❓ Retrieval Success = last 7 days found share; "Most Asked Topics", No Owner Assigned, Potential Duplicates, Conflicting Policies = null; Outdated = `expired`; not reviewed > 6 months. ❓ dashboard needs `view_department_analytics`.

**API**
- ❓ routes beyond §37 are ours; `GET /v1/health` unauthenticated (`models`: loading|ready). ❓ key permissions `ask, search, documents, sales_memory, feedback`; rate limit per minute in-process.
- `/v1/ask` returns `query_id`, `actions`; mode `general|sales_coach`; sources `title, section, version, updated`; `/v1/search` returns `text, score, source`.
- API keys `qx_live_<random>` (no app name), lifetime 1 h/24 h/1 week/1 month/1 year/never; no departments = all; without `user_id` acts as creating admin; no chats from key calls.
- Chats private per user; admins can't read.
- Login throttle 10 failed/identifier/15 min (lockout possible; next step IP/CAPTCHA); signup limits per IP 5/hour accounts, 30 attempts, 5 emails; question <=4,000 chars; password >=8, not containing name/username/email, >=4 distinct chars. SQS visibility 900 s. Models load in background thread.

**Front-end**
- ❓ Web Search and mic disabled; ❓ **+** modes; ❓ "Ask Manager" not offered; "Report missing knowledge" and "Search documents" are. Employees have no dashboard; Sales Memory/Product Hub screens removed.
- One answer by default: search view shows best match, others behind "Show N more matches"; 2 sources then "+N more".

**Self sign-up/approval**
- `POST /v1/auth/register` public; username 3–30 chars `[a-z0-9._-]` in `employee_id`; pending until approved; correct-password sign-in says "waiting for approval"/"not approved". `GET /v1/auth/signup-options` public.
- Admin approves anyone; manager sees requests for own departments, approves employee/contributor only, grants only own departments; >=1 department required; audited `permission_change`.

**Account menu/personalization**
- Profile `PATCH /v1/auth/profile` (name, picture PNG/JPEG/WebP <=~300 KB, 256 px), password `POST /v1/auth/password`, preferences `PUT /v1/auth/preferences` (<=500 chars, fenced `<user_preferences>`), `DELETE /v1/conversations`. Bulk access `POST /v1/users/bulk-departments`.

**Feedback learning** (`backend/learning/feedback.py`, migration 006; changes order/phrasing, never knowledge)
- Source boost (up−down)/(n+5) for passages with >=3 ratings, shift 0.001×boost; personal style hints (>=3 liked, >=2 disliked, 70%) with "Forget what I learned" switch; optional 👎 reasons; admin Insights -> Answer quality and "Reset what it has learned". Not done: reusing past answers, auto-changing knowledge/thresholds.

**Sales memory**
- Structured JSON import (`backend/sales_memory/importer.py`) stored as-is (field names §16.2, `stage`->`sales_stage`, anonymized, embedded 32/batch); import screen per department; remove via `DELETE /v1/sales-memory/imports/{job_id}`; `GET /v1/sales-memory/imports`. Known gap: interrupted job stays `running`; re-upload.

## 4. Implementation necessities (veto)
`argon2-cffi`; sessions with SHA-256-hashed 32-byte tokens; `pyotp`+`segno`; Fernet (`cryptography`); SHA-256 API keys; `psycopg` 3 plain SQL + `migrations/*.sql` runner; pgvector `vector(1024)` HNSW cosine (model change = migration + re-index); `sentence-transformers`; `pypdf`, `python-docx`; `boto3`; CPU-only PyTorch; synchronous endpoints; `tenant_id` on business tables; `jobs` table; Caddy HTTPS; Redis queue (60 s socket timeout, blocking wait capped below it; worker loop retries after 5 s on errors); model micro-batch wait bounded by optional `QB_MODEL_QUEUE_TIMEOUT_SECONDS` → 503 + Retry-After 5, abandoned work dropped (❓ owner: value; unset = no limit); `scripts/obsidian_local.py` local contributor repos + Obsidian Git settings (`autoSaveInterval` 2, `autoPullInterval` 5); Obsidian reconcile interval 300 s; `scripts/qa_up.py` QA instance on :8010 against a DB copy; local dev: `scripts/dev_up.py` strips `.env` trailing comments, `.env.example` is a working local template, `requirements-dev.txt` has `moto[server]`; `pillow` (in `requirements-images.txt`, own Docker layer) for image post-processing.

## 5. Not built
PRD §5 non-goals; SSO; Google Drive/website/Notion/Slack/email/CRM sources; Qdrant; Phase 5 (fine-tuning, local LLM, voice, agents); CloudWatch dashboards; infra-as-code; §59 metrics other than Recall@5/@10, MRR.

## 6. Verification
Real PostgreSQL 16 + pgvector 0.8.7 integration (`QB_TEST_DATABASE_URL`), moto AWS, unit tests, real BGE models run. Not run: Gemini/OpenAI/Claude/Bedrock calls (fake generator), Cognito, ECS, RDS, Secrets Manager. Pure Roman Urdu = measured gap (two expected-failure tests in `test_models.py`); calibrate thresholds with `python -m evaluation.run_eval`.
