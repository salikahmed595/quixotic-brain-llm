# QUIXOTIC AI — PRODUCT REQUIREMENTS DOCUMENT (PRD)

**Product:** Quixotic AI — Company Knowledge Assistant  
**Version:** 1.0 | **Date:** 16 October 2026  
**Initial user base:** 160 employees, plus authorized administrators  
**Platforms:** Responsive web app (desktop first), mobile browser; Telegram/Discord for authorized knowledge contributors (later phase)  
**Design mandate:** Reproduce the two supplied reference screenshots as closely as technically possible for their respective roles. The screenshots are the visual source of truth; no redesign or extra employee navigation.

---

## 1. Product vision

Quixotic AI is a permission-aware, retrieval-augmented generation (RAG) assistant that helps employees find verified company answers about scripts, objections, sales workflows, SOPs, policies, onboarding, and department procedures. Administrators manage employee access, documents, approvals, departments, AI configuration, and audit controls. The longer-term system allows authorized leadership to propose knowledge updates from Telegram/Discord text or voice messages, using Hermes Agent, with controlled approval and automatic reindexing.

**Non-negotiable:** The AI must not invent company policies, permissions, prices, refunds, discounts, or employee instructions. If approved evidence is missing, say so and create a reviewable knowledge-gap request.

---

## 2. Business goals and success criteria

1. Onboard and manage 160 employee accounts, with no employee able to log into company knowledge before admin approval.
2. Reduce time spent asking supervisors routine policy and script questions.
3. Provide source-linked, department-permitted answers from approved documents.
4. Let authorized admins maintain the knowledge library without code changes.
5. Detect unanswered questions and route them to knowledge owners.
6. Preserve approved knowledge changes, accountability, and rollback.

**Initial measurable targets** (validate during pilot): p95 chat response under 8 seconds for ordinary text queries (excluding external web search); p95 knowledge retrieval under 2 seconds; ≥95% of answers in the acceptance test cite an authorized document or explicitly state that no verified answer was found; 100% of pending users denied protected access; 0 unauthorized cross-department retrievals in the permission test suite; full reindex of a changed document visible to search within 60 seconds under normal load. Test 160 concurrent logged-in sessions and a 40-concurrent-chat baseline; load-test a 160-concurrent-chat burst before expansion. These are targets, not existing performance claims.

---

## 3. User roles and boundaries

| Role | Allowed | Not allowed |
|---|---|---|
| Employee | Register, view own account status, create/search/delete own chats, ask questions, view answers/sources allowed for assigned scope, report missing information | See admin routes, other employees' chats, secret documents, pending drafts, API keys, edit approved policies |
| Department Manager / Knowledge Reviewer (optional subrole) | All employee actions plus review assigned department's proposed updates | Approve outside assigned authority; manage system secrets |
| Knowledge Admin | Curate documents, proposals, taxonomy, knowledge gaps; publish when granted publisher permission | Bypass platform-wide security controls |
| System Admin | Approve/reject/suspend users, assign departments/roles, manage access, indexing, configuration, logs, and integrations | Read unrelated private user chats by default; disclose plaintext API keys |
| Founder / CEO (leadership authority) | Submit policy proposals over verified Telegram/Discord identities and approve governed changes within specified approval matrix | Automatically override an existing policy solely based on a conflicting chat message |

The UI has two main layouts: Employee and Admin, matching the screenshots. Manager/reviewer/leadership permissions may add limited features inside the Admin layout when approved. Enforce permissions on the server for every API call and every document retrieval, not only by hiding sidebar links. Multi-department membership must be supported. Use deny-by-default access.

---

## 4. Reference UI — preserve the supplied screenshots

Reference A: Admin screenshot (`image(20261016-164021).png`; 1468 × 901). Reference B: Employee screenshot (`image(20261016-164058).png`; 1478 × 907). Implement the desktop interface to be visually faithful at approximately 1470 × 900 viewport. Keep the same layout, information hierarchy, spacing, typography feel, copy, mascot, icons, colors, and interaction placements. Reuse original graphic assets if available; otherwise recreate equivalent SVG assets and review against screenshots. Exact pixel parity cannot be guaranteed solely from raster screenshots, so verify with side-by-side visual regression screenshots.

### 4.1 Shared desktop screen

- Fixed left sidebar, approximately 282–284 px wide, full viewport height; warm off-white background (sample near #FBF6F1), extremely light separator.
- Main content warm cream (sample #FFFAF6); white cards; bright orange emphasis (approximate #FF6B1A, confirm against source). Dark charcoal headings. Clean rounded sans-serif type; match exact font by inspecting original app assets if available rather than guessing.
- Top-left rounded orange app icon with white sparkle, followed by Quixotic AI text, where AI is orange; small collapse-sidebar icon on right.
- Sidebar links New chat and Search chats, with the same compact icons and typography.
- Centered prominent headline Ask Quixotic AI, with 'Quixotic AI' in orange and a small orange sparkle icon above/right.
- Centered subtitle: Get instant answers from your call center knowledge base — scripts, objections, SOPs, policies and more.
- Behind content: subtle pale-orange curved wave lines (decorative; pointer-events disabled). Center illustration: friendly orange/black headset AI mascot. Floating labeled pills: Scripts, Objections, Policies, and SOPs.
- Large white rounded question composer, approximately 960 px wide on desktop, with slight shadow. Placeholder: Ask Quixotic AI about scripts, objections, SOPs, and company knowledge...
- Composer bottom-left controls, in this order: circular + button; Web Search pill (screenshot reads 'WebSearch', preserve displayed text if strict parity required); Company Knowledge dropdown. Bottom-right: circular microphone icon, then pale-orange circular paper-plane send button.
- Below composer: label Try asking about... and exactly four horizontal example cards: Customer says too expensive, Booking script, Refund policy, Lead qualification. Match cards' icons, light borders, 15–18 px radius, orange arrow, and orange hover/active outline.
- Bottom-left fixed account profile card with avatar, username/role, scope subtitle, and ellipsis menu. Sidebar scroll is independent of main content.
- Homepage is intentionally spacious and not text-heavy. On entering a conversation, replace the hero area with message history, sources, and the pinned chat composer, while retaining the same visual system.

### 4.2 Employee layout — EXACT navigation scope

Employee sidebar contains: Quixotic AI, New chat, Search chats, date-grouped chat history (e.g. Previous 30 days), and the Employee profile card at bottom. No Workspace, Knowledge, Manage, or Administration navigation is visible. Profile subtitle shows Employee · [Authorized Scope]. Display 'Company Wide' only if the employee truly has that access; do not assign company-wide access by default.

### 4.3 Admin layout — EXACT sidebar structure and order

1. Quixotic AI / collapse toggle
2. New chat
3. Search chats
4. WORKSPACE (collapsible)
5. KNOWLEDGE: Knowledge; Add information; Documents; Sales memory
6. MANAGE: Approvals; Access requests; Dashboard; Insights
7. ADMINISTRATION: Users; Departments; Vocabulary; API keys; System
8. Date-grouped personal chat history
9. Fixed Administrator account card; subtitle Administrator · Company Wide when applicable.

Admin gets the same central Ask Quixotic AI home screen as the employee. Administrative pages open in the main panel without changing the sidebar design. Active item styling must remain understated and orange-accented.

### 4.4 Responsive design

At tablet widths, allow sidebar collapse. On mobile, put sidebar inside an accessible navigation drawer; retain brand, chat input, question examples (horizontal-scroll or stacked), and account status. Reflow mascot and floating labels rather than overlapping the composer. Maintain minimum 44 × 44 px touch targets, keyboard navigation, readable contrast, and visible focus states. The supplied screenshots define desktop appearance; mobile layouts must be derived consistently rather than assumed to have their own reference images.

---

## 5. Registration, login, and admin approval

**FR-AUTH-01 — Sign up:** Public registration page styled consistently with the screenshots. Required fields: full name, work email, password, confirm password, requested department; optional employee ID/phone if the company uses them. No self-selection of admin/CEO roles. Validate email uniqueness, password policy, and rate limits.

**FR-AUTH-02 — Email verification:** Verify email or issue company-specific invitations/OTP. A verified email is not equivalent to company employment approval.

**FR-AUTH-03 — Pending approval:** New account status is Pending. Show a clear pending page after signup. User cannot access chat, company knowledge, admin APIs, or indexed content while pending.

**FR-AUTH-04 — Review by admin:** Send a pending-user event to Admin → Access requests. An authorized admin can open the request, check identity/department, assign role and scope, then Approve or Reject with an optional note. Approval creates an audit record and activates access.

**FR-AUTH-05 — Account states:** Pending, Active, Rejected, Suspended, Deactivated. Suspending access revokes active sessions promptly. Rejected users are told how to contact an administrator without revealing internal data.

**FR-AUTH-06 — Login security:** Secure password hashing (Argon2id preferred), HttpOnly secure session cookies, CSRF protection as appropriate, login throttling, password reset, logout, session expiry, and admin MFA. Use an established authentication framework rather than inventing cryptography. Bootstrap the first system administrator through a one-time protected setup path; never via public signup.

**FR-AUTH-07 — Profile:** Employee can view name, department(s), effective access scope, and account settings; cannot escalate own role. Admin can update membership, disable users, and view account status history.

---

## 6. Employee chatbot requirements

**FR-CHAT-01:** New chat, send/edit input before sending, conversation persistence, rename/delete own conversations, recent history grouping, and search own conversation titles/messages.

**FR-CHAT-02:** Send typed questions and optional microphone voice questions (speech-to-text with consent, recording state, cancellation, and error handling). A generated answer is text by default.

**FR-CHAT-03:** Four suggestion cards populate/submit example questions according to product decision, without making them hardcoded answers.

**FR-CHAT-04:** Company Knowledge is the default retrieval mode; answers must use only currently approved, permitted, indexed company sources. Display cited document title, relevant section and effective/updated date where available. If no verified answer is found: “I couldn't find an approved answer in the company knowledge base.” Offer Report missing information.

**FR-CHAT-05:** Web Search, if enabled, is explicitly separate from company answers: clearly label external information, cite URLs, avoid presenting web pages as company policy, and do not send confidential company text to an external search provider without authorization. Admin can disable the feature globally or per role. Do not silently mix untrusted web results into official policy responses.

**FR-CHAT-06:** Company Knowledge dropdown shows only permitted scopes (e.g. My Department, Company General, other assigned departments). Never expose unauthorized departments in the selector or backend retrieval.

**FR-CHAT-07:** Answers may use bullets, tables, and short actionable steps but should be clear and simple for new call-center staff. Show response loading, retry, unavailable service, feedback thumbs up/down, and cited-source drawer.

**FR-CHAT-08:** The assistant detects question language and answers in that language where possible while preserving the meaning of approved source text. Do not fabricate a translated policy absent supporting evidence.

**FR-CHAT-09:** Users see only their own chat history. Default admin analytics are aggregate; accessing individual conversation content requires a documented legal/operational policy and separate authorization.

---

## 7. Admin pages and requirements

| Navigation item | Minimum functionality |
|---|---|
| Knowledge | Search/browse approved knowledge, department and category filters, source status, effective date, citations, versions; inspect knowledge gaps |
| Add information | Enter text or upload a document, select department/category/sensitivity, provide source and owner, preview parsed content, submit for validation and approval |
| Documents | Upload PDF, DOCX, TXT, MD; detect file type/size, extract text, review parse, classify permissions, approve, version, archive, reindex; reject unreadable files |
| Sales memory | Approved sales playbooks, objection examples, handoff rules, FAQ and lessons; no unrestricted import of identifiable customer conversation transcripts |
| Approvals | Queue for document changes/policy updates with diffs, references, conflicts, submitter, reviewer, approve/reject/request changes; prevent self-approval where policy requires separation |
| Access requests | Pending employee signup and access-scope changes; approve/reject, assign role/department, reason, timestamps |
| Dashboard | Approved users (target 160), pending accounts, active chats, answer volume, knowledge health, index status, unresolved gaps, queue counts |
| Insights | Top questions, zero-result queries, feedback, department usage, document coverage, response latency; aggregated/permission-aware reporting |
| Users | Search/add/invite/edit/suspend/deactivate users; roles, departments, last login, state, audit history; bulk import optionally |
| Departments | Create/edit/disable departments; assign members, reviewers, visibility rules and document owners |
| Vocabulary | Manage approved industry phrases/acronyms, customer objection terminology, aliases and synonyms for retrieval and presentation |
| API keys | Configure providers via server-side secret references; mask keys, rotate/revoke, scoped access; never return plaintext secrets to frontend |
| System | Model selection, RAG tuning, embeddings, indexing jobs, integration health, backup/restore, incident controls, audit/export, Web Search toggles |

Admin pages must share the screenshot's sidebar, cream canvas, white cards, orange accents, rounded corners, and low-density layout. Data tables/forms are allowed inside the main content; do not insert admin controls into the employee homepage.

---

## 8. Knowledge structure and retrieval

**Authoritative knowledge:** approved Obsidian-compatible Markdown files, plus curated file imports transformed into approved document records. For hosted production, the canonical vault must be synchronized on the server with version history; do not make an admin's laptop the only copy. Use Git or an equivalent versioned storage layer.

**Suggested hierarchy:** Company/, HR/, Sales/Fresh-Seller/, Sales/Upseller/, Production/, Marketing/, Customer-Support/, Leadership/, Training/, Glossary/, Archive/. Adapt to real departments, not invented policies.

Each published document needs: immutable ID, title, content, category, department(s), sensitivity/access scope, owner, approving user, source/provenance, effective date, created/updated timestamps, version ID, status (Draft/Under Review/Approved/Published/Archived), and an indexing checksum. Keep document ACL metadata with every chunk.

**Retrieval workflow:** Authenticate user → identify effective roles/departments → select eligible approved, unexpired content before search → run hybrid lexical and vector retrieval → rerank → supply bounded excerpts and source metadata to DeepSeek (or configured LLM) → generate sourced answer or safe 'not found' response → capture feedback/gaps. Embeddings and vector indexes use PostgreSQL + pgvector; keyword search uses PostgreSQL full-text search or equivalent. Recheck permissions before providing the final source/answer. Resist prompt injection inside documents; retrieved text is data, not system instructions.

**Document updates:** Preserve previous published version until replacement is validated, approved, and indexed. On successful publication, atomically switch the active version or use a controlled publication transaction; invalidate old chunks. Fail closed if the index and permissions are out of sync. All changes must have a reversible change record.

---

## 9. Hermes, Telegram, and Discord knowledge ingestion (Phase 2)

A single shared knowledge-update service accepts verified messages from authorized Founder, CEO, and Knowledge Admin through Hermes-connected Telegram/Discord bots. A leadership user can send plain text or a voice note from phone or laptop. Workflow:

1. Telegram/Discord gateway captures sender platform ID, message ID, channel, timestamp, and text/audio; allowlist IDs and verify mapped company identities.
2. Audio is transcribed, original message/source recorded according to retention policy, and uncertain transcript segments flagged for confirmation.
3. Hermes/LLM determines intent: ask question, add fact, edit rule, replace policy, or report knowledge gap.
4. Backend searches existing approved documents, checks source provenance and policy conflicts, and prepares a structured Markdown proposal with a before/after diff.
5. Correct reviewer/approver accepts, revises, or rejects based on department-specific rules. High-impact policies (HR, pay, discounts, refunds, customer payments, security) always require explicit confirmation and approval. A model's researched or generated answer is never itself an authoritative company policy.
6. On approval, backend writes a new version, records an audit event, reindexes affected chunks, verifies retrieval success, then sends Telegram/Discord confirmation with linked document/version.
7. On failure, maintain the previous active version, alert the owner, and allow retry/rollback.

**Knowledge gap loop:** An employee question with no approved answer creates a de-duplicated issue assigned to the correct department owner. Admin may notify the authorized owner on Telegram/Discord. Once approved new knowledge is published, mark the gap resolved. Do not allow all employees to write to the vault through the chat interface.

---

## 10. Information security, privacy, and governance

- Server-side RBAC plus document-level ABAC/ACL. Department and confidentiality filters apply before vector/keyword retrieval, not merely after generation.
- All secrets remain server-side (environment/secret manager); never in frontend bundles, Markdown, chat history, or screenshots.
- TLS everywhere; encryption at rest for sensitive data/backups; least-privilege database credentials; separate internal admin tools and employee public interfaces.
- Record account approvals, document changes, access-scope changes, publishing, administrative exports, and privileged bot actions in tamper-resistant audit logs.
- Published vs draft indexes are separate or strongly status-filtered; privileged drafts must not leak through shared embeddings, summaries, caches, or error messages.
- Protect upload paths: type validation, malware scanning where feasible, upload size limits, sandboxed text extraction, prompt-injection resistance, and document review.
- Apply request and token quotas, rate limits, monitoring, and abuse defenses against account enumeration, prompt injection, exfiltration, and denial of service.
- Do not upload confidential data to DeepSeek or any third-party model until the company approves the provider, retention settings, and data-handling terms. Support a configurable provider or private deployment later.
- Define chat/audio/document retention periods with company leadership before launch; minimize customer personal information in Sales memory. Support correction/deletion policies and access logs.

---

## 11. Proposed technical architecture

- **Frontend:** React + TypeScript (Next.js or Vite, based on existing repo) and Tailwind CSS. Preserve the existing screenshot-based UI; don't replace it with a generic dashboard kit.
- **API/backend:** Python FastAPI (or existing Node backend if already reliable), REST APIs, documented OpenAPI contract.
- **Auth/data:** PostgreSQL, secure sessions and an established auth library/provider; explicit account approval records.
- **RAG:** Postgres full-text + pgvector, embedding service, re-ranking, ACL-aware retrieval, DeepSeek as configurable answer LLM.
- **Files:** Versioned Markdown vault + private object storage for uploaded originals; scheduled synchronization and checksum validation.
- **Tasks:** Redis and worker queue for parsing, embedding, indexing, notifications, and retries.
- **Integrations:** Hermes Agent for optional Phase 2 Telegram/Discord + controlled backend tools; n8n optional for notifications/approvals, not an alternate permission authority.
- **Deployment:** Dockerized services, HTTPS reverse proxy, backups, log collection, staging and production environments.

### Minimum API contract (illustrative)

- `POST /auth/register`, `POST /auth/login`, `POST /auth/logout`, `GET /auth/me`
- `GET /admin/access-requests`, `POST /admin/access-requests/{id}/approve`, `POST /admin/access-requests/{id}/reject`
- `GET /admin/users`, `PATCH /admin/users/{id}`, `GET /admin/departments`
- `POST /chats`, `GET /chats`, `GET /chats/{id}`, `POST /chats/{id}/messages`, `DELETE /chats/{id}`
- `POST /knowledge/search`, `GET /knowledge/documents`, `POST /knowledge/proposals`, `GET /knowledge/proposals/{id}`
- `POST /admin/proposals/{id}/approve`, `POST /admin/proposals/{id}/reject`
- `POST /admin/documents/upload`, `POST /admin/documents/{id}/reindex`, `GET /admin/knowledge-gaps`
- `POST /integrations/hermes/knowledge-proposals` (signed service-to-service request, not a public untrusted write endpoint)

Every endpoint requires correct authentication, authorization, input validation, idempotency where relevant, and appropriate audit logging.

---

## 12. Core data entities

users, user_departments, roles, permissions, access_requests, sessions, departments, chats, chat_messages, feedback, knowledge_documents, document_versions, document_chunks, document_permissions, knowledge_proposals, approval_decisions, knowledge_gaps, integration_identities, ingestion_events, index_jobs, audit_events, system_settings, secret_references.

Store the last indexed document version and checksum; uniquely identify external bot events to prevent duplicate writes. Avoid a data model where one user's role or one document's department exists only as an LLM-generated label.

---

## 13. User journey acceptance tests

- **AT-01 — Employee signup:** Register a new account → verify email → status Pending → blocked from all chat/company content → admin sees Access request → admin assigns Sales/Fresh Seller and approves → user can log in → sees only Employee screenshot-style navigation and permitted content.
- **AT-02 — Rejection/suspension:** Reject a pending account or suspend an active one → all protected endpoints deny access; previously issued sessions are revoked.
- **AT-03 — Authorized answer:** Sales employee asks for the approved fresh-seller handoff process → chatbot returns a concise answer with the correct company document citation and version/date.
- **AT-04 — Missing knowledge:** Employee asks about an undocumented discount → chatbot explicitly says no approved policy was found and offers to report the gap; no invented percentage.
- **AT-05 — Department isolation:** A Sales-only employee tries to request restricted HR/leadership documents through search, citations, prompt injection, direct API calls, or tampered dropdown values → no title, content, counts, or metadata leaks.
- **AT-06 — Admin document update:** Admin uploads and proposes revised policy → designated reviewer sees clear before/after diff and approves → new version becomes searchable; old version is recoverable.
- **AT-07 — Bot update:** Verified leadership voice note creates a proposal → unapproved change never appears in employee answers → approval publishes it and reindexes it → bot confirms version and document link.
- **AT-08 — UI parity:** Visual regression test at ~1470 × 900 against both supplied screenshots: correct sidebar/nav for each role, hero composition, chips, composer, colors, mascot, account card; no employee exposure of admin controls. Manually check responsive behavior and accessibility.
- **AT-09 — Reliability:** Run load tests for 160 logged-in employees, 40 simultaneous chat questions baseline, and 160-chat burst; verify latency/error targets and recovery on model/database outages.

---

## 14. Delivery phases and priorities

- **P0 / Phase 1 — Employee product and safe RAG:** Exact shared/role-specific UI; signup/email verification; admin approval; login/logout; role/department enforcement; employee chat and history; Obsidian-compatible approved document import; citations; missing-answer behavior; basic admin Users, Access requests, Documents, Departments; audit trail.
- **P1 / Phase 2 — Managed knowledge:** Add information, Approvals, Knowledge, Sales memory, dashboard/insights, document versioning, automatic reindex, feedback/knowledge-gap queues, voice questions, vocabulary, Web Search governance.
- **P2 / Phase 3 — Leadership automation:** Hermes + Telegram/Discord, voice transcription, proposal generation, policy conflicts, authorized approval, audit/rollback, gap notifications and resolution tracking.
- **P3 / Later:** Advanced reporting, SSO, connectors to additional company systems, richer analytics, evaluation/benchmark automation, multilingual speech output if justified.

---

## 15. Exclusions for v1

No foundation-model or SLM training; no autonomous creation of company rules from guesses; no employee access to unpublished documents; no open-ended autonomous Hermes filesystem/shell permissions; no reading every employee's private chat by default; no automatic customer data scraping; no mandatory n8n dependency; no fake 'Company Wide' access claim.

---

## 16. Definition of done

Release only when: (a) the two screenshot-based views pass visual review; (b) registration and administrator approval function end-to-end; (c) permission tests pass at API, retrieval, and document levels; (d) approved answers are sourced and unsupported questions fail safely; (e) admins can manage accounts/documents/departments; (f) history and data are durable; (g) backups and restore have been tested; (h) model/data-provider usage is authorized; and (i) the system passes the agreed 160-employee load profile. Telegram/Discord/Hermes automation is a later milestone and must not delay a safe Phase 1 launch.

**Implementation direction to Claude Code:** Treat the supplied screenshots as non-negotiable desktop visual references. First audit the existing Quixotic AI repository and list what already works. Reuse rather than replace functioning components. Implement P0 in small, testable milestones with migrations, API contracts, seed data, unit/integration/E2E permission tests, screenshots, and a written deployment guide. Ask for real department rules and permissions instead of fabricating them.
