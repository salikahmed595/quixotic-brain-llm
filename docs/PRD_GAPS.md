# PRD gaps and implementation necessities

Rule (see `CLAUDE.md`): the PRD is the only source of truth and nothing is guessed. Where `PRODUCT.md` is silent
the backend either **requires an explicit setting / plug-in** (fails loudly if missing) or does the **smallest
thing needed** and lists it here so the owner can decide. Each item names the PRD section it relates to.

**Owner action:** items marked ❓ need a decision from you; until then the stated behaviour applies.

---

## 0. PRD replaced on 2026-10-17 — conflicts between the new PRD and the existing code

`PRODUCT.md` is now **Quixotic AI PRD v1.0 (16 Oct 2026)**, 16 sections. The earlier "Quixotic Brain" PRD (67
sections) is superseded and is kept only in `docs/archive/PRODUCT_quixotic_brain_v0.md`.

> **Old citations.** Every `PRD §N` in the code, in `docs/backend.md` and in **sections 1–6 and the dated owner
> sections below** refers to the *superseded* PRD. Look such numbers up in the archive file, not in `PRODUCT.md`.
> New work cites the new PRD (`PRD §5 FR-AUTH-03`, `PRD §13 AT-05`, …). Old citations are re-pointed as each
> module is touched in the P0 milestones (`docs/P0_PLAN.md`).

Nothing in the code has changed yet. Each row says what the new PRD requires, what the code does today, and what
P0 will do. ❓ = needs your decision before that milestone starts.

### 0.1 Accounts, auth and roles

| Area | New PRD | Code today | P0 handling |
|---|---|---|---|
| Account states | §5 FR-AUTH-05: Pending, Active, Rejected, Suspended, Deactivated | `approval_status` pending/approved/rejected + `is_active` boolean | Migrate to one `account_status` with the five PRD states (M1) |
| Email verification | §5 FR-AUTH-02: verify email or invite/OTP | none | Required in P0 (§14). ❓ **Which mail provider / sender address?** Until set, signup fails loudly with "email not configured" |
| Password hashing | §5 FR-AUTH-06: Argon2id preferred | `hashlib.scrypt` | Switch to Argon2id (`argon2-cffi`); verify old scrypt hashes and rehash on next login (M1) |
| Sessions | §5 FR-AUTH-06: HttpOnly secure session cookies, CSRF, expiry, logout; §5 FR-AUTH-05 suspension revokes sessions promptly | Stateless HS256 JWT bearer token in JS; no logout; no revocation | Server-side `sessions` table (§12), HttpOnly cookie, CSRF token, `POST /auth/logout`, revoke on suspend/reject (M1) |
| Password reset | §5 FR-AUTH-06 | only change-password while logged in | Add reset by emailed link (needs the mail provider above) |
| Admin MFA | §5 FR-AUTH-06 | none | ❓ **Method?** (TOTP authenticator app is the usual choice.) Not invented until you confirm |
| First admin | §5 FR-AUTH-06: one-time protected setup path, never via public signup | CLI `backend/cli.py` creates users | Keep the CLI as the one-time path; make it refuse once any system admin exists (M1). ❓ OK? |
| Signup fields | §5 FR-AUTH-01: full name, work email, password, confirm, requested department; employee ID/phone optional | employee ID required (`users.employee_id NOT NULL`) | ❓ **Do you use employee IDs / phone?** If not, make them optional |
| Roles | §3: Employee, Department Manager / Knowledge Reviewer, Knowledge Admin, System Admin, Founder/CEO | employee, contributor, manager, administrator | ❓ **Mapping:** proposed `manager → department_reviewer`, `administrator → system_admin`; `contributor` has no new-PRD equivalent (old PRD §9.2 let contributors upload; the new §3 lists no employee upload right and §9 says not all employees may write to the vault) — proposed: fold into `employee`. Knowledge Admin "publisher permission" needs to be a separate grant |
| Founder/CEO | §3, §9: authority over Telegram/Discord (Phase 2) | none | Phase 2 only; not built in P0 |
| "Company Wide" | §4.2, §15: never by default, never faked | already: no implicit visibility | Unchanged |
| Self-approval | §7 Approvals: prevent where policy requires | managers can approve own uploads | ❓ **Which changes need separation of duties?** P0 has no Approvals page (§14 puts it in P1) |

### 0.2 Knowledge, retrieval and answers

| Area | New PRD | Code today | P0 handling |
|---|---|---|---|
| Document statuses | §8: Draft / Under Review / Approved / Published / Archived | draft, submitted, pending_review, approved, active, rejected, archived, expired | Migrate: draft→Draft, submitted+pending_review→Under Review, approved→Approved, active→Published, archived→Archived. ❓ **`rejected` and `expired` are not PRD states** — keep as change-record outcomes, not statuses? (`§8` does say "unexpired content", so expiry exists as a date, not a state) |
| Document fields | §8: category, sensitivity/access scope, owner, approving user, provenance, effective date, version ID, indexing checksum | partial: no sensitivity, owner, effective date, checksum; `access_level` only a label | Add the missing columns + `document_permissions` (§12) (M3). ❓ **Sensitivity levels?** (names and who may see each) |
| Authoritative store | §8: Obsidian-compatible Markdown vault, server-side, Git-versioned | Postgres rows + raw files in S3 / local folder | Add a Git-backed vault directory on the server; publication writes the Markdown file and commits (M3). ❓ **Obsidian front-matter keys** for the §8 fields — none are specified |
| Retrieval filter | §8: "approved, unexpired" content | `status = 'active'` | Filter `Published` + not past expiry (M3) |
| LLM | §8, §11: DeepSeek or configured LLM; §10: no confidential data to any provider until the company approves it | Gemini / OpenAI / Claude / Bedrock behind `generate_answer` | **Owner (2026-10-17): will provide the API key.** Add a DeepSeek provider behind the same interface; keep the others. The key lives only in AWS Secrets Manager / server env, never in chat, the repo, Markdown or the frontend (§10). Generation stays off until the key is configured. ❓ **Which provider is the key for?** (PRD default: DeepSeek) |
| Not-found reply | §6 FR-CHAT-04: exact text "I couldn't find an approved answer in the company knowledge base." + Report missing information | different wording; failed questions logged | Use the exact text; add "Report missing information" → `knowledge_gaps` (M4) |
| Knowledge gaps | §9, §12: de-duplicated, assigned to department owner | `query_log` failed questions | New `knowledge_gaps` table, dedupe on normalized question + department. ❓ **De-dup rule** not specified — exact normalized text match until you say otherwise |
| Answers from past sales chats | §1: never invent policies/prices; §7 Sales memory = *approved* playbooks/objection examples; no unrestricted import of identifiable transcripts | commit 48939eb answers from imported past chats when no policy exists (labelled "history only") | **Conflict.** Proposed: turn off the history-only answer path for P0 (Sales memory is P1); keep the importer but only for reviewed, anonymized records. ❓ Confirm |
| Confidence | old PRD showed High/Medium/Low; new PRD silent | shown in UI | Keep (harmless), but no longer PRD-required. ❓ keep or remove? |
| Language | §6 FR-CHAT-08: answer in the question's language | language detected; answer language not instructed; Roman Urdu normalizer | Instruct the LLM to answer in the detected language; keep the Urdu/Roman Urdu work |
| Web Search | §6 FR-CHAT-05 (P1 governance, §14) | none | P0 shows the pill per §4.1 but disabled until P1. ❓ OK? |
| Voice questions | §6 FR-CHAT-02 (P1, §14) | none | P0 shows the microphone per §4.1, disabled until P1 |

### 0.3 Platform, API and UI

| Area | New PRD | Code today | P0 handling |
|---|---|---|---|
| API paths | §11 contract: `/auth/*`, `/chats/*`, `/admin/*`, `/knowledge/*` (marked "illustrative") | `/v1/auth`, `/v1/conversations`, `/v1/documents`, `/v1/ask` … | ❓ **Rename to the §11 paths, or keep `/v1/` prefix?** Proposed: `/v1` + §11 names (`/v1/chats`, `/v1/admin/access-requests`), old paths removed |
| Chat messages | §11: `POST /chats/{id}/messages` asks within a chat | `POST /v1/ask` with a conversation id | Add the §11 route; `/v1/ask` stays for internal apps (API keys) ❓ |
| Frontend stack | §11: React + TypeScript + Tailwind (Next.js or Vite) | vanilla `frontend/app.js` (976 lines) + `app.css` | Rebuild in Vite + React + TS + Tailwind (no Next.js server needed) (M6) |
| Reference screenshots | §4: `image(20261016-164021).png` (admin), `image(20261016-164058).png` (employee) | **Added 2026-10-17** in `UI images/reference/` (sizes match §4: 1468 × 901 and 1478 × 907). Older mock-ups in `UI images/` are superseded | Findings in §0.5 below. ❓ Original mascot / icon / font files, if they exist |
| Admin sidebar | §4.3 exact order incl. WORKSPACE group, Approvals, System | close but not identical | Match §4.3 exactly in M6 |
| Queue | §11: Redis + worker queue | Amazon SQS + ECS worker | **Owner (2026-10-17): hosted on AWS.** Per §11: Redis on Amazon ElastiCache replaces SQS (veto if you would rather keep SQS — it works today). Object storage stays S3 |
| Object storage | §11: private object storage for originals | S3 | Unchanged (any S3-compatible store) |
| Deployment | §11: Docker, HTTPS reverse proxy, backups, logs, staging + prod; §16: tested backup/restore | Dockerfile + compose for local; AWS notes | **AWS** (owner, 2026-10-17). Docker containers on AWS, RDS PostgreSQL + pgvector, S3, ElastiCache Redis, HTTPS load balancer, CloudWatch logs, RDS/S3 backups; deployment guide in M7. ❓ ECS/Fargate or a single EC2 host? |
| Load testing | §2, §13 AT-09: 160 sessions, 40 chats baseline, 160 burst | none | Add a load-test script (M7); tool choice listed under implementation necessities |
| Non-goals | old PRD §5 banned workflow automation & multi-agent systems; new §11 allows Hermes Agent (Phase 2) and optional n8n | `CLAUDE.md` Rule 1.4 cites the old list | `CLAUDE.md` now cites new §15 exclusions |

### 0.5 What the reference screenshots show (added 2026-10-17)

- **"Company Wide" in both cards.** The employee screenshot reads "Employee · Company Wide". §4.2 says to show it only when the employee truly has that access, and §15 bans a fake claim — so the card shows the user's real scope; the screenshot is treated as demo data.
- **"Web Search", with a space**, in both screenshots (§4.1 expected "WebSearch"). The UI uses "Web Search" as shown.
- **Admin sidebar:** WORKSPACE is a collapsible header (chevron) above the KNOWLEDGE, MANAGE and ADMINISTRATION groups; that block scrolls on its own (visible scrollbar), and chat history ("Previous 7 days") sits below it. Icons per item as shown.
- **Example cards:** the admin screenshot shows the first card with the orange outline — this is the hover/active state from §4.1, not a default selection.
- **Font:** a rounded geometric sans; it cannot be identified with certainty from a raster image. ❓ **Do you have the font name or files?** Until then M6 picks the closest match by visual comparison and lists it under implementation necessities (§4.1 "rather than guessing").
- **Mascot and icons:** no original files in the repo. §4 allows recreated SVGs reviewed against the screenshots; that is what M6 does unless you supply the originals.

### 0.4 What already works and is reused

Hybrid retrieval (Postgres FTS + pgvector) with permission filters **before** search; reranker interface; ingestion of
PDF/DOCX/TXT/MD with validation and size limits; versioning with one active version per item; signup → pending →
admin approve/reject with role + departments; per-user chats (create/list/rename/delete); audit log table; feedback
👍/👎; API keys (hashed, masked, revocable); vocabulary; dashboard/insights endpoints; prompt-injection guard
(documents are data); 4-provider LLM interface; evaluation harness; Docker Postgres launcher.

---

## 1. Required settings with no default (the app will not start without them)

| Setting | PRD § | What the PRD says | Note |
|---|---|---|---|
| `QB_CHUNK_SIZE`, `QB_CHUNK_OVERLAP` | 13.3 | "Chunk Content" | no strategy or size; both in characters ❓ |
| `QB_MAX_UPLOAD_BYTES` | 51 | "Upload size limits" | no number (the UI mock-up shows 50 MB) ❓ |
| `QB_CANDIDATE_COUNT` | 7, 27 | 20–40 candidates | range enforced; value is yours ❓ |
| `QB_FINAL_CHUNK_COUNT` | 7, 27 | best 5–8 | range enforced; value is yours ❓ |
| `QB_HISTORICAL_TOP_K` | 11.3, 30 | "17 similar cases" | no rule for how many cases count as "similar" ❓ |
| `QB_ROMAN_URDU_MIN_RATIO` | 22 | four languages | no boundary between Roman Urdu and mixed ❓ |
| `QB_CONFIDENCE_HIGH/MEDIUM` | 31, 32 | High / Medium / Low | no thresholds; scale depends on the chosen models — calibrate with §58–§59 ❓ |
| `QB_GENERATION_PROVIDER`, `QB_GENERATION_MODEL_ID` | 28, 44 | "External API or AWS Bedrock" | **Stack decision:** Gemini / OpenAI / Claude initially, Bedrock later (all four implemented). The *model id* is still yours to pick ❓; Claude also needs `QB_GENERATION_MAX_TOKENS` (the API demands a limit) |
| `QB_RERANKER_PROVIDER/MODEL` | 27 | "Multilingual reranker" | **Stack decision:** multilingual BGE reranker → `BAAI/bge-reranker-v2-m3`, CPU. No longer a gap |
| `QB_PRIORITY_TIERS_JSON` | 20 | four tiers | tiers named, but not which `document_type` belongs to which; empty = reranker order kept ❓ |
| `QB_SESSION_TTL_SECONDS` | 41 | email/employee ID + password | no session lifetime ❓ |
| `QB_SESSION_SECRET` | 41 | — | JWT signing key, ≥ 32 characters (stack: "JWT / Cognito"; HS256 JWT implemented, Cognito can replace token verification later) |

## 2. Plug-ins the PRD leaves undefined (job fails with a clear message until provided)

| Plug-in | PRD § | Missing definition |
|---|---|---|
| `ConversationParser` | 17 | the Discord JSON export schema, and how customer vs agent is told apart (§17.2 "Detect Customer / Agent") ❓ **send a sample export** |
| `MemoryExtractor` | 17.2, 16.2 | how objection, intent, sales stage, outcome, value and discount are extracted ❓ |
| `quality_score` | 16.2, 17.2 | "Calculate Quality Signals" is not defined → stored as `NULL` unless the extractor sets it ❓ |
| Anonymizer: addresses, customer IDs | 18 | formats unknown. Done: usernames, emails, phones, payment cards (Luhn), passwords/API keys/secrets. Pass `extra_patterns` for the rest ❓ |

## 3. Behaviour the PRD does not define — what the code does meanwhile

**Access & workflow**
- ❓ `access_level` (§12.2 "Sales + Managers", §14) is stored as a label. **Enforcement is by department only** (§10 "assign knowledge to one or more departments", §42). "+ Managers" is not enforced.
- ❓ "Company Wide" (§10) has no implicit visibility; users must be assigned to it like any department.
- ❓ §9.1 "Use sales recommendations **if permitted**": permitted = the user is authorized for the sales memory's `department_id`; sales history is added only in `mode = sales_coach` (§11.3 "when appropriate" is undefined).
- ❓ Sales memories get a required `department_id` (the PRD defines no access rule for them).
- Submit moves `draft → submitted → pending_review` in one action (§12.3 does not say who performs the second step). Both steps are in the history.
- Activating a version archives the item's previous active version (§15 "current information must always override old"); a DB constraint allows one active version per item.
- Administrator direct publish is allowed (§9.4 "add knowledge manually", §12.3 "where applicable"): every step of the chain is still checked and audited. Contributors' uploads always go to review (§9.2).
- ❓ No path to `expired` (§12.3 names the state, not how items expire).
- Managers act on departments where they are the **department manager** (`departments.manager_id`, §10).
- ❓ `DELETE /v1/documents/{id}` (§37): administrator only; removes the version, its chunks and the S3 object. Archiving (§9.4) is a separate transition.

**Retrieval & answers**
- Hybrid candidates (§26): union of both legs, de-duplicated, vector hit first; **no score-fusion formula** — ordering is left to the reranker (§27).
- ❓ Reranker priorities (§27: current, official, scenario similarity, department context): current-ness and permissions are hard filters before ranking; no extra weighting formula is invented.
- ❓ Keyword search (§25 "BM25 or equivalent"): PostgreSQL full-text (`simple` config, OR-query, `ts_rank_cd`). Not true BM25; no Urdu stemming.
- ❓ Confidence score = top reranker score (else top cosine similarity); see thresholds above. Low confidence **skips the LLM** (§32) and is logged as a failed question (§35).
- "Successful" historical case = `outcome == "closed"` (the §16.2 example value); no other rule exists.
- The answer language is not instructed (§22 defines query languages only).
- Source `section` comes from Markdown `#` headings and DOCX heading styles; PDF/TXT/JSON/CSV have none (§30 shows a section but not how to obtain it). JSON is pretty-printed, CSV kept as text.
- Sales memories are embedded on `customer_message` (fallback `scenario`) (§17.2 "Generate Embeddings").
- Language detection: Arabic script → `urdu`; Latin text matched against the Roman Urdu marker list (`data/roman_urdu_lexicon.json`, seeded only with words from the PRD examples) → `roman_urdu` / `mixed` by ratio; otherwise `english`. The normalization map holds only the §23 example. Extend the file with company vocabulary.
- ❓ Feedback (§21): stored with `validated = false`; the PRD does not say who validates or how validated experiences become searchable memory, so no such endpoint exists.

**Dashboard & insights (§34–§36)**
- ❓ "Retrieval Success" = share of the last 7 days' questions where knowledge was found; "Questions This Week" = rolling 7 days.
- ❓ "Most Asked Topics" and Knowledge Health's *No Owner Assigned*, *Potential Duplicates*, *Conflicting Policies* are returned as `null` with a reason — the PRD gives no way to compute them. *Outdated* = status `expired`; *Not reviewed > 6 months* = active versions whose last review/creation is older than 6 months.
- ❓ The dashboard needs `view_department_analytics` (manager and above); the PRD does not give Employees a dashboard.

**API (§37–§40)**
- ❓ Routes beyond the eight listed in §37 (auth, users, departments, knowledge, api-keys, jobs, dashboard, failed-questions, knowledge-health, audit-logs) are named by this implementation. `GET /v1/health` is unauthenticated (for load balancers).
- ❓ API-key permission names (`ask, search, documents, sales_memory, feedback`) and the rate-limit unit (**per minute**) are not in §40. The limiter is in-process: with several API tasks, a shared limiter would be needed.
- `/v1/ask` also returns `query_id` (needed by `/v1/feedback`) and `actions` (§32); `mode` ∈ `general | sales_coach` (§11.4; Search Only = `/v1/search`, Department Brain = the `department` field).
- `/v1/ask` sources contain `title, section, version, updated` (§30); `/v1/search` results contain exactly `text, score, source` (§39).

**Front-end (owner design: "Ask Quixotic AI")**
- ❓ The design shows **Web Search** and a **microphone**. The PRD says answers come only from retrieved company knowledge (§29) and lists voice as a later phase (§61), so both buttons are present but tell the user they are not available. Nothing is sent anywhere.
- ❓ The **+** button opens the PRD §11.4 modes (General, Sales coach, Search only); **Company Knowledge ▾** picks a department (Department Brain, §11.4).
- ❓ §32 lists "Ask Manager", but the PRD does not say how it is delivered, so it is not offered. "Report missing knowledge" (contributors and above) and "Search documents" are.
- Owner decisions: employees see no dashboard; the Sales Memory and Product Hub screens, and the Settings/Analytics mock-ups, were removed (no real data behind them).
- Necessity: `QB_FRONTEND_DIR` (serve the static front-end from the API) and `QB_CORS_ORIGINS` (host it elsewhere) are optional settings read directly from the environment.

**Owner decisions of 2026-10-04 (override the PRD example, recorded here so they are not mistaken for guesses)**
- API keys look like an LLM provider's keys: `qx_live_<random>` with **no app name inside the key** (PRD §40 shows `qx_live_callcenter_xxxxx`). The name is only a label in the admin screen.
- No per-minute limits in the UI. A key instead has a **lifetime**: 1 hour, 24 hours, 1 week, 1 month (30 days), 1 year, or never (until revoked). A rate limit remains available through the API (optional) because PRD §40 lists one.
- A key with no departments chosen covers **all departments**; a key used without `user_id` acts as **the administrator who created it** (so it works on its own, like an LLM key). With `user_id` it acts as that employee (PRD §38).
- Chat history (ChatGPT-style) is **saved on the server, private to each user**: administrators cannot read other people's chats (PRD §5: no employee surveillance). API-key calls do not create chats. Each question is still logged for analytics/failed questions (§35).

**Added by the 2026-10-05 RAG audit (each one fixes a measured or demonstrated defect)**
- Retrieved text is *neutralized* before it enters the prompt: anything that imitates our `<knowledge>` / `<historical_cases>` fence tags is defanged (PRD §52). Without it a document containing `</knowledge>` ended the data block and its remaining text was read as instructions.
- A file with no extractable text (scanned/image-only PDF, empty DOCX, headings-only Markdown) now ends as **failed** with an explanation, never "ready" with zero chunks. OCR is not implemented (the PRD does not mention it).
- Chunks end at sentence boundaries when one exists in the second half of the window, otherwise at whitespace (PRD §13.3 gives no strategy).
- Login is throttled: 10 failed attempts per identifier in 15 minutes -> HTTP 429 for the rest of the window (PRD §51 lists rate limiting, no numbers). Consequence: someone can lock a known account out for 15 minutes by failing deliberately; an IP-aware or CAPTCHA scheme would be the next step. An unknown account still costs one password hash, so response time does not reveal which accounts exist.
- Questions are limited to 4,000 characters and must not be blank (bounds embedding and LLM cost); new-user passwords need at least 8 characters.
- The embedding model and reranker load in a background thread at start-up (loading takes 1-2 minutes on CPU) behind a lock; `GET /v1/health` reports `"models": "loading" | "ready"`.
- SQS messages are received with a 900 s visibility timeout so a long upload is not handed to a second worker mid-processing.
- Chunk `metadata.status` is kept in sync when a version changes status (retrieval itself always reads the live status).

**More audit changes (2026-10-05) — measured with real BGE-M3 + bge-reranker-v2-m3 on a 134-chunk benchmark: 46 labelled questions in English, mixed, Roman Urdu and Urdu script, plus 10 unanswerable ones**
- Chunks are **embedded with their title and section** (`"Refund Policy - 2. Timeline
<text>"`); the stored/shown text is unchanged. Vector top-1 accuracy 0.76 -> 0.89. Existing content needs the admin *re-index* once.
- **Keyword leg ignores stopwords** (English list + the Roman Urdu marker words): keyword-only R@5 0.52 -> 0.74.
- **The reranker reads only the top `QB_RERANK_TOP_K` candidates** (new required setting, 8) and its ranking is **fused with the retrieval ranking** (Reciprocal Rank Fusion, k = 60). Measured: reading 6, 8, 12 or 20 candidates gave identical results while each costs ~0.5 s on CPU (30 candidates = 11-20 s per question); the reranker alone was slightly *worse* than the retrieval order at rank 1 (0.85 vs 0.89) and blind to pure Roman Urdu, fusion was best. ❓ PRD §27 says the reranker reduces 20-40 candidates to 5-8; retrieval still gathers `QB_CANDIDATE_COUNT` (20-40) but only the best 8 are reranked.
- **Confidence uses two signals, the better one counts**: reranker probability (`QB_CONFIDENCE_HIGH/MEDIUM`) and vector cosine similarity (`QB_CONFIDENCE_VECTOR_HIGH/MEDIUM`). Placeholders 0.30/0.01 and 0.65/0.55 answered 80% of answerable questions and let 0 of 10 unanswerable ones through. ❓ Re-calibrate on your real documents and questions (`python -m evaluation.run_eval`).
- **Roman Urdu phrase table** (`data/roman_urdu_lexicon.json` -> `expand`): the English meaning of known phrases is appended to the *search text* only. Seeded with the PRD §23 example (`paise wapas` -> `refund`). ❓ Pure Roman Urdu is still the weakest area (top-1 0.80, and about half of the pure-Roman-Urdu questions end as low confidence): grow this table with your staff's real vocabulary, or ask for an LLM "query interpretation" step (PRD §23 shows one).
- **DOCX tables are now extracted** (they were silently dropped, taking pricing/limit tables with them); PDF pages are merged into one block so a rule is not cut at a page break. ❓ PDFs get no section label in sources (headings cannot be detected reliably); scanned PDFs need OCR (not built).
- Database connections enable pgvector **iterative index scans**: without it a user in a small department received **zero** results whenever a bigger department held near-duplicate content (reproduced; needs pgvector >= 0.8, ignored on older versions).
- Measured latency on a 4-core CPU: embedding a question 0.3-0.5 s; searching a question end to end **4.1 s** (was 11-21 s); embedding documents ~0.7 s per chunk. The LLM call comes on top, so a full answer is realistically 7-9 s against the PRD's "5-8 s typical" target.

## 4. Implementation necessities (not product decisions — veto any of them)

scrypt password hashing · HS256 JWT bearer tokens (stack: JWT / Cognito) · SHA-256 hashed API keys (shown once) · `psycopg` 3 with plain SQL
(no ORM) and a plain `migrations/*.sql` runner · pgvector `vector(1024)` with an HNSW cosine index (BGE-M3 is 1024-d; changing
the model needs a migration + re-index, §24.2) · `sentence-transformers` for BGE-M3 and the cross-encoder · `pypdf`, `python-docx` ·
`boto3` (S3, SQS, Bedrock Converse API) · CPU-only PyTorch (stack: no GPU) · synchronous endpoints · Docker image `python:3.14-slim` (the version the tests ran on) ·
`tenant_id` column on business tables (§66) · `jobs` table for background-job progress (§47).

**Local development setup (2026-10-07; tooling only, no product behaviour)**
- `scripts/dev_up.py` drops trailing `# comments` from `.env` values (like python-dotenv) and stops with a clear message when `.env`
  is missing. Before, `QB_SESSION_TTL_SECONDS=28800  # PLACEHOLDER` reached the app verbatim and failed validation.
- `.env.example` is now a working local template: comments on their own lines, dummy `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY`
  for the moto stand-in (boto3 refuses to sign requests without credentials), `QB_RAW_STORAGE_DIR=.devstore`, `QB_FRONTEND_DIR=frontend`,
  and the models by Hugging Face id (`BAAI/bge-m3`, `BAAI/bge-reranker-v2-m3`) instead of a `.models/` folder that only the bash script creates.
- `requirements-dev.txt` installs `moto[server]` (needed by `dev_up.py`'s `moto.server`).
- `Start Quixotic AI.bat` uses the project's `.venv` Python when present and stops with a message when Docker is not running.

## 5. Deliberately not built

PRD §5 non-goals; §41 SSO/MFA ("potential later"); §13.1 Google Drive/website/Notion/Slack/email/CRM; §45 Qdrant migration; §61 Phase 5
(feedback-based improvement, knowledge-gap detection beyond failed questions, model benchmarking, fine-tuning, local LLM, voice, agents);
§55 CloudWatch dashboards and §54 backup configuration, §51 HTTPS/private RDS/private S3/Secrets Manager (infrastructure, not application
code — the PRD gives no IaC choice); §59 metrics other than Recall@5, Recall@10 and MRR (they need labelled data or logs the PRD does not define).

## 5b. Measured with the real models (BGE-M3 + `bge-reranker-v2-m3`, CPU)

- ❓ **Pure Roman Urdu retrieval is weak.** English and mixed phrasing work (`customer is asking for refund kya karun?` → refund, cosine 0.597 vs 0.447).
  Pure Roman Urdu does not: `customer paise wapas mang raha hai` scores *discount* 0.397 vs *refund* 0.372 on BGE-M3, and the reranker gives every
  candidate its floor score (no signal). PRD §22 requires such queries to work, and §23 shows a "semantic interpretation" step
  (`customer is requesting a refund`) but does not place it in the §7 retrieval pipeline. Options for you: (a) add an LLM query-interpretation step
  before retrieval (extra latency/cost), (b) grow `backend/data/roman_urdu_lexicon.json` with company vocabulary mapped to the words used in your
  documents, (c) both. Two tests (`test_models.py`) are marked *expected failure* so this stays visible.
- ❓ **Confidence thresholds need calibration.** The BGE reranker returns probabilities that are small for short, correct snippets
  (e.g. 0.01–0.5), so thresholds like 0.5 / 0.75 would call correct answers "low". Local `.env` uses placeholders (0.3 / 0.005) taken from a tiny
  sample. Run `python -m evaluation.run_eval` against real documents: it prints the score ranges of answerable vs unanswerable questions (§35's
  example is the unanswerable one) so the owner can pick the Medium/High boundaries.
- Necessity (measured): the reranker reads `title - section` together with the chunk text; this raised the relevant chunk's score on short policy
  snippets (refund −3.8 → −1.3 logit) without changing the ranking elsewhere.

## 6. Verification status (updated)

- **Run against a REAL PostgreSQL 16 + pgvector 0.8.7** (`QB_TEST_DATABASE_URL`, a fresh database per test): the migration, all SQL stores,
  permissions-before-retrieval, hybrid (vector + keyword) search, `status = active` filtering, archived-on-request, version supersession (§15) and
  the one-active-version DB constraint, ingestion with §14 chunk metadata, API keys, jobs with progress, query log, feedback, audit log,
  dashboard, sales-memory search, login by email or employee ID — and a full HTTP flow: JWT login → upload → S3 → SQS → worker → search → ask
  → feedback → failed question → audit → archive.
- **Run against mocked AWS (moto):** the S3 and SQS adapters, with the §46 paths.
- **Unit tests:** config rules, role matrix, workflow edges, language detection/normalization, extraction/chunking, anonymization, retrieval rules,
  prompt rules, credentials, API-key auth and rate limit.
- **Real models (run):** BGE-M3 and the BGE reranker run on CPU. Retrieval works for English and mixed Roman Urdu + English; pure Roman Urdu is a measured gap
  (§5b). The model-backed end-to-end test (upload → worker → search → ask → archive) passes.
- **Not run:** the Gemini / OpenAI / Claude / Bedrock calls (no API keys here; the e2e test uses a fake generator), Cognito, ECS, RDS and Secrets Manager.

## Owner-requested additions: faster + better Urdu / Roman Urdu (2026-10-05)

Not in the PRD as written; added at the owner's request ("core thing" = Urdu and Roman Urdu). Veto any of them here.

- **Prompt rule 8** (`backend/generation/prompt.py`): answer in the user's language and script (cites PRD §22; answer language is otherwise unspecified).
- **Query interpretation** (`QB_QUERY_INTERPRETATION=true`): one small LLM call, only for Urdu / Roman Urdu / mixed questions, restates the question in
  English and appends it to the search text (PRD §23 "semantic interpretation"; its place in the §7 pipeline is not specified). Cost: ~0.9 s and one
  extra LLM call per non-English question. The call never raises: on failure the plain search runs.
- **Vocabulary** (`/v1/vocabulary`, migration 003, admin-only `manage_vocabulary`, "Vocabulary" page): admins teach a phrase -> English meaning; it is
  added to the search text within 60 s. Failed questions have a "Teach a word" button. Audited.
- **Expanded Roman Urdu marker list** (186 words) in `backend/data/roman_urdu_lexicon.json`.
- **`QB_RERANK_SKIP_MARGIN=0.04`**: skip the reranker when the top vector hit leads the second by >= 0.04 (speed). **`QB_FINAL_CHUNK_COUNT=5`,
  `QB_RERANK_TOP_K=5`**. Values come from the synthetic benchmark (`docs/RAG_AUDIT.md`), not from the PRD; re-measure on real documents.
- **Answer model `gpt-4.1-mini`** chosen after a small bake-off on the synthetic set; change with `QB_GENERATION_MODEL_ID`.
- Still low-confidence on the synthetic set: 4 of 22 Urdu/Roman Urdu questions. Fix with taught Vocabulary entries; thresholds are placeholders.

## Fixes from the owner's first real document (2026-10-05)

First real upload: `Quixotix_Company_Knowledge_Base.pdf` (23 pages, 63 numbered sections). Findings and changes (all implementation necessities; veto any):

- **PDF cleaning** (`backend/ingestion/extract.py: pdf_blocks`): lines that repeat on most pages (page header/footer) and bare page numbers are dropped;
  bullet glyphs become `- `; lines wrapped by the page layout are re-joined; a numbered heading ("9. Department-Based Knowledge Access") starts a new
  section so sources can cite it (PRD §30 "Refund Policy -> Section 3"). Before: every chunk carried "QUIXOTIX / INTERNAL COMPANY KNOWLEDGE BASE / Page 16"
  and had no section. Heuristic: a short numbered line without final punctuation is a heading. Other PDFs without numbered headings stay section-less.
- **Reranker skip** now needs a clear lead AND a vector score >= `QB_CONFIDENCE_VECTOR_HIGH` (was: any score). A clear lead with score 0.52 ("Who is the
  founder?") was labelled *low* without the reranker. Measured on the real PDF: answerable questions score 0.52-0.73, unanswerable ones up to 0.56.
- **`QB_RERANK_TOP_K=3`** (was 5) and the setting may now be smaller than `QB_FINAL_CHUNK_COUNT`: the reranker reads 3 chunks, the other chunks follow in
  retrieval order so the answer model still gets 5 (PRD §27 "best 5-8"). Measured: right chunk in retrieval top-3 for 25/25 questions (top-1: 23/25). The
  reranker costs ~1.2 s per 1,000-character chunk on this 2-core i5-6200U; lower precision (bf16) was 10x slower and more threads did not help.
  A larger CPU on ECS/EC2 will be faster. Re-check on bigger corpora.
- **Prompt rules 9 and 10** + a per-question note when no historical conversations were retrieved: text introduced as "Example:" is not policy (the PDF's §30
  example "Customers can request a refund within the approved refund period" was being answered as the refund policy), and the model may not claim
  something "worked in past sales" without historical cases (PRD §19, §20, §29).
- **Worker no longer loads the reranker** (`build_services(warm_reranker=False)`): it held ~4.5 GB for nothing; with the API that was ~9 GB of models on a 16 GB machine.
- **`QB_RAW_STORAGE_DIR`** (local development only): the in-memory S3 emulator forgot every uploaded original on restart. With this set, originals are kept in a
  folder (`.devstore/`, git-ignored). Production keeps S3 (PRD §46).
- Admins get per-step `timings` (embed / database / rerank) in `/v1/search` debug output.
- Questions asked while a document is still processing find nothing and are logged as failed questions. Wait for the document to show as ready.

## Owner-requested: account menu, personalization, chat memory, access at scale (2026-10-05)

Not in the PRD as written (PRD §9 lists role capabilities, §41 login, §42 RBAC; none describes profiles or per-user answer settings). Added at the owner's request; veto any of it here.

- **Account menu** (sidebar, all roles): Personalization, Profile, Settings, Log out.
- **Profile** (`PATCH /v1/auth/profile`): own name and picture. Picture = PNG/JPEG/WebP data URL, resized to 256 px by the app, max ~300 KB, stored in `users.avatar`
  (SVG and links are refused). Migration 004. Role and departments cannot be changed here (administrators only, §9.4).
- **Settings** (`POST /v1/auth/password`): change own password (current one required, min 8 characters, wrong attempts throttled 10 / 15 min). Audited as
  `admin_action` (PRD §53 has no password event). "Delete all my chats" (`DELETE /v1/conversations`, own chats only).
- **Personalization** (`PUT /v1/auth/preferences`, `users.preferences`): answer length, tone, reply language, "about me", custom instructions. Only known values and
  <= 500 characters are stored/read (`clean_preferences`), they reach the model inside a fenced `<user_preferences>` block (`neutralize` applies) and prompt rule 12
  says they change style only and never override the rules or the sources (PRD §29, §52).
- **Role-tailored answers**: the model is told the asker's role and department names (`<asker>`, set by the system, rule 11). It tailors tone/depth; it never widens
  what may be used: visibility is still decided only by departments, applied before retrieval (PRD §42). API-key calls get neither asker nor preferences.
- **Who sees which knowledge** is the existing department model: an administrator creates departments (e.g. "Managers", "Employees", "Finance", "HR"), uploads
  knowledge to them and puts people in them. Users page now has search, role / department filters, and **bulk give / remove access** (`POST /v1/users/bulk-departments`,
  audited as `permission_change`). The PRD §10 seed list is unchanged; "Managers" / "Employees" groups are created by the administrator, not invented here.
- **Chat memory**: the last 6 exchanges (answers cut to 800 characters, was 2 / 600) go to the model in `<conversation>`; rule 7 now lets it use what the user said about
  their situation (e.g. a customer's name), still not as a source of company facts. A follow-up in a chat is restated as a standalone search query by one small model call
  (~1 s, any language; first questions of a chat need none). The reranker reads that clean restatement, not the original+restatement mix (measured 0.52 vs 0.01-0.18).
- PDF headings: a numbered top-level heading directly above its sub-headings ("6. Major Services" above "6.1 ...") is kept as a prefix of the sub-section labels.
- Confidence thresholds, calibrated on the owner's real PDF (30 answerable, 18 unanswerable questions): still the placeholders (reranker 0.01 / 0.3, vector 0.55 / 0.65).
  The groups overlap between reranker 0.004 and 0.01, so no threshold separates them perfectly; the answer prompt refuses to present non-answers. "What services do you
  sell?" is still labelled low although §6 answers it. Re-calibrate when more real documents exist.

## Owner-requested: self sign-up with approval (2026-10-05)

PRD §41 (V1 login = email or employee ID + password) says nothing about how accounts are created (only the owner's company document does). Added at the owner's request; veto any of it here.

- **Create an account** (login page link; `POST /v1/auth/register`, public): full name, own username (3-30 chars, lowercase letters / digits / `.` `-` `_`, stored in `employee_id`),
  email, password (min 8) and, optionally, the department they say they work in. Login accepts username or email, any case. The account is created **pending**
  (`approval_status`, `is_active = false`, role employee, no departments): it cannot sign in and sees no knowledge. Migration 005.
- **Pending / rejected sign-in** says why ("waiting for approval" / "not approved") but only after the correct password was given; a wrong password gets the usual generic 401.
- **Approval** (Access requests page, `GET/POST /v1/access-requests...`): an **administrator** approves anyone, any role, any departments. A **manager** sees only requests that asked for
  one of their own departments (or none), may approve **employee or contributor only**, and may give only departments **they belong to** (PRD §9.3 gives managers department-scoped
  review). At least one department is required: the approver decides what the person may see (PRD §42). Rejecting keeps the row (the person cannot sign in). Decisions are audited as
  `permission_change`; sign-up requests too.
- **Spam limits** (implementation necessities, per address, in memory): 5 accounts requested per hour, 30 attempts per hour (so usernames cannot be probed freely).
- `GET /v1/auth/signup-options` is public and returns department names only.
- Isolation is the existing department rule (permissions before retrieval, PRD §42), now covered by a test: a Finance user never retrieves Employee-only knowledge and the reverse,
  for search and for ask; giving someone both groups (admin, bulk) makes both visible.
- No email verification and no email notification exist yet (the PRD names no mail service): the approver sees requests in the app; the person tries signing in later.

## One answer by default (2026-10-05, owner request)

The chat showed a list of matching passages ("Matching knowledge") for Search-only mode and for the "Search documents" button on a low-confidence answer. Now: normal questions always return ONE written answer;
the search view shows the single **best match** and the others behind "Show N more matches" (PRD §11.4 Search Only and §32 `search_documents` stay available); under an answer, 2 sources are shown and
the rest behind "+N more sources"; "Search documents" is a one-off (the chat stays in normal mode), and opening an old search-only chat no longer keeps later questions in list mode.

## Owner-requested: the system learns from 👍 / 👎 (2026-10-05)

PRD §21 only says feedback is stored (and that new experiences become searchable memory *after validation*); "feedback-based improvements" is Phase 5. §5 forbids "automatic fine-tuning after every
interaction" and "autonomous agents modifying company data without approval". So the learning below changes **how things are ordered and phrased, never the knowledge itself**, is bounded, visible and
reversible. Veto any of it here. Migration 006. Switch: `QB_FEEDBACK_LEARNING=false` (ratings are still stored).

1. **Source quality nudges retrieval order** (`backend/learning/feedback.py`). Each person's latest 👍/👎 on a question counts once, credited to the first 2 passages of that answer. A passage with >= 3 ratings gets
   boost = (up - down) / (n + 5); the candidate order is shifted by 0.001 x boost on top of the rank-fusion score: 3 ratings move a passage about 1 place, a near-unanimous history at most ~4 places. Nothing is hidden,
   edited or deleted, a new version of a document starts with a clean slate (new chunk ids), and policy priority (§20) is untouched. The numbers are placeholders chosen to be mild.
2. **Personal style patterns.** From one person's own ratings the system looks for a contrast between liked and disliked answers (length, lists vs paragraphs; at least 3 liked and 2 disliked, 70% of each group on its
   own side) or repeated "Too long" / "Too short" reasons (>= 2). A person who only ever clicks 👍 gets no invented preference. The hint reaches the model as `learned from their thumbs: ...` (explicit Personalization choices win).
   Shown to the person in Personalization with "Forget what I learned" and a "Learn from my 👍 / 👎" switch; one person's ratings never affect another's answers.
3. **Rejected answers are marked in the chat**: a 👎 answer appears to the model as `assistant [not helpful]` so it is not repeated (prompt rule 13); `[helpful]` shows a style to keep.
4. **After 👎, optional reasons** (Wrong answer / Not what I asked / Too long / Too short / Missing information) are stored as notes with the feedback (PRD §21 stores feedback + note).
5. **Administrators** get Insights -> Answer quality: rated answers, helpful %, whether High / Medium / Low confidence really matches 👍 rates (useful to calibrate the thresholds), sources rated down / up, the recent 👎
   answers with reasons and an "Add missing knowledge" shortcut. No person is named. "Reset what it has learned" (admin) makes older ratings stop counting; nothing is deleted (audit trail intact; audited as `admin_action`).
- Not done on purpose: reusing a past answer for a similar question (it could leak knowledge the new asker may not see, and PRD §21 requires validation first); changing knowledge or confidence thresholds automatically.

## Owner-requested: past sales chats per department, answering from them when no policy exists (2026-10-08)

The owner uploaded 4,216 already-extracted sales chat records (one JSON object per customer message / agent reply, PRD §16.2 fields) as an ordinary document. It never became searchable: the worker
was stopped mid-job (jobs left `running` are not retried, see below), the file sat in Sales while the test employee only had Company Wide, and as a plain document the JSON would only be cut into text chunks.
The owner then asked that each department's chats answer that department's staff (Upseller and Fresh Seller chats kept apart), and that an answer be given from past chats when no approved policy covers a question,
clearly labelled. Veto any of it here. Migration 007.

1. **Structured import** (`backend/sales_memory/importer.py`, `parse_structured`). A JSON list of objects with `customer_message` / `agent_response` is stored as sales memories as-is, without the Discord
   parser/extractor plug-ins (which stay undefined, §2). Field names follow §16.2; `stage` is read as `sales_stage`; unknown fields are dropped. §17.2 steps still applied: anonymize (customer message, agent reply,
   objection), detect language when missing, embed (the customer message, as before), store. `customer_objection` gets its own column (§17.2 "Extract Objection"). Records are embedded 32 at a time.
2. **Per-department import screen** (Knowledge -> Sales memory, administrators, PRD §17.1 "Import Conversations"): choose the department, drop the JSON, see "Detected: N conversations, M messages", follow progress,
   see how many chats were stored and **remove an import** (`DELETE /v1/sales-memory/imports/{job_id}`, audited) when the wrong file or department was used. `GET /v1/sales-memory/imports` lists imports.
   Which chats belong to Upseller vs Fresh Seller is decided by the owner by uploading separate files; no automatic split rule exists.
3. **Past chats in every Ask mode + history-only answers** — only when `QB_SALES_HISTORY_MIN_SIMILARITY` is set (unset = PRD behaviour: history only in Sales Coach, never answering alone).
   - Past chats from the asker's own departments (same department filter as knowledge, §42) whose cosine similarity to the question is at least the setting are passed to the answer model in General mode too.
   - When no approved knowledge is found or confidence is low (§29, §32), an answer is written from those chats only. It always starts with the fixed line *"Based on past sales chats, not an official Quixotic
     policy. No approved policy or SOP covers this yet."* (PRD §19 distinction), prompt rule 14 forbids presenting it as policy or stating prices/discounts the chats do not show, its confidence comes from the
     chat similarity on the vector thresholds (§31), and it is still logged as a failed question (§35) so the missing policy shows up for administrators. §20 is unchanged: when policy exists it leads.
   - MEASURED on 800 of the owner's chats (BGE-M3): sales questions reach 0.58–0.72 similarity, but small talk matches chat lines even better ("hello" 0.97, "thanks" 0.88) and unrelated questions reach 0.49–0.68.
     Similarity therefore only pre-filters (placeholder **0.55**); the answer model must also confirm the chats are about the same situation, else it replies `NO_RELEVANT_HISTORY` and the PRD §29/§32 answer is shown.
     The check is a note placed right before the question (a rule in the system prompt alone was ignored: "hello" got "Hello! How can I assist you?"). MEASURED end to end with gpt-4o-mini on a 300-chat
     sample: 5/6 sales questions answered from the chats (incl. Roman Urdu), 6/6 off-topic questions ("hello", "thanks", leave days, password reset, a joke, a capital city) fell back to the PRD answer.
   - Import speed on this PC (Ryzen 5 2600, CPU): ~0.2 s per chat record to embed, so ~4,000 records take roughly 15-40 minutes; progress is shown on the Sales memory page.
4. Not fixed here (known gap): a job interrupted by stopping the worker stays `running` forever and its upload shows "Processing"; the local SQS stand-in (moto) also loses queued messages on restart. Re-upload in that case.
