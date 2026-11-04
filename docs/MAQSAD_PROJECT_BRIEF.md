# Maqsad (Quixotic AI) — Project Brief for the Portal Team

**Written for:** the session/team building **portal.quixoticcreatives.com**
**About:** **maqsad.quixoticcreatives.com** (repo `Quixotic-brain-llm`, product name in code: "Quixotic AI")
**Goal behind this brief:** Employees signed in to the Portal should be able to sign in to Maqsad as well.
**Status:** Facts below come from reading the code on 2026-11-04. Maqsad has **no SSO or Portal integration today**. Section 6 lists the ways it could be connected; none has been chosen yet.

---

## 1. What Maqsad is

Maqsad is an internal **company knowledge assistant** for Quixotic Creatives. It uses RAG (retrieval-augmented generation): employees ask questions about scripts, objections, SOPs, policies, onboarding and department procedures, and get answers drawn only from **approved company documents**, with the sources shown.

- About **160 employees** at the start, plus admins.
- **Two layouts:** Employee (chat) and Admin (users, access requests, documents, approvals, departments, knowledge gaps, insights, API keys, system).
- **Hard rules:**
  - The AI never makes up policies, prices, refunds, discounts or permissions.
  - With no approved evidence it replies exactly: "I couldn't find an approved answer in the company knowledge base." It then offers a "Report missing information" option.
  - Access is denied by default. Department and confidentiality filters are applied on the server **before** retrieval, and checked again before the answer is shown.
  - Accounts that are Pending, Rejected, Suspended or Deactivated get no access at all.
  - Every knowledge change is reviewed by a person. Nothing is approved automatically.
- The source of truth is the PRD in `PRODUCT.md` (also split into `docs/product/`). Project rules are in `CLAUDE.md`. Every choice the PRD doesn't cover is recorded in `docs/PRD_GAPS.md`.

## 2. Tech stack

| Layer | Technology |
|---|---|
| Backend API | **Python 3.14, FastAPI**, Uvicorn, Pydantic v2 / pydantic-settings |
| Database | **PostgreSQL 16 + pgvector** (psycopg 3 with a connection pool). Schema is managed with plain SQL migrations in `migrations/001…017_*.sql` (no ORM) |
| Queue / worker | **Redis**, or AWS SQS. Background worker in `workers/worker.py` handles parsing, embedding, indexing and publishing |
| File storage | **AWS S3** (boto3) for uploaded originals. Approved knowledge is also kept as a versioned Markdown (Obsidian-style) vault in Git |
| Search / AI | Postgres full-text search + pgvector. Embeddings and reranking run locally with sentence-transformers / PyTorch on CPU (default embedding model `bge-m3`). The answer LLM is configurable: OpenAI, Anthropic or Google GenAI clients are installed, and DeepSeek is planned |
| Document parsing | pypdf, python-docx, PyYAML, Pillow |
| Auth / security | Argon2id passwords (argon2-cffi), server-side sessions, CSRF tokens, TOTP admin MFA (pyotp + segno for the QR code), Fernet field encryption (cryptography), PyJWT (HS256 helper for service-to-service tokens, never used as a user login), HMAC-SHA256 signed webhooks |
| Frontend | **React 18.3 + TypeScript 5.8 + Vite 6 + Tailwind CSS 4**, a single-page app in `web/` |
| Tests | pytest for the backend; Playwright + pixelmatch for visual regression tests of the frontend |
| Deployment | Docker in two stages (Node 24 builds the web app, then `python:3.14-slim` runs the API and serves the built web files). Production runs `docker-compose.prod.yml` on **one AWS EC2 server**: postgres, redis, api, worker and **Caddy** (HTTPS with Let's Encrypt). Only ports 80 and 443 are open |

## 3. API shape

- REST endpoints under `/v1`. FastAPI publishes an OpenAPI description automatically.
- Route prefixes: `/v1/auth`, `/v1/chats`, `/v1/conversations`, `/v1/knowledge`, `/v1/sales-memory`, `/v1/clients`, `/v1/vocabulary`, `/v1/integrations`, `/v1/admin`, `/v1/admin/system`, `/v1/admin/integrations`.
- The web app and the API are served from the **same origin** (Caddy → `api:8000`). CORS is off unless `QB_CORS_ORIGINS` is set.

## 4. How sign-in works today (the part the Portal needs most)

### 4.1 Accounts
- Table `users` (tenant `quixotic`), with these key columns:
  - `id` (uuid)
  - `employee_id` (text, unique per tenant, e.g. `emp_104`, also used as the username)
  - `email` (unique per tenant)
  - `full_name`
  - `password_hash`
  - `role`
  - `account_status`
  - `email_verified_at`
  - `mfa_secret_enc`, `mfa_enabled_at`
  - `can_publish`
  - `last_login_at`
- A person can belong to several departments through `user_departments` (user ↔ department, many-to-many).
- **Account states:** `pending` → `active` | `rejected`; an active account can later become `suspended` or `deactivated`. Only `active` accounts can do anything. Every change is logged in `account_status_history`.
- **Roles** (`backend/permissions/roles.py`): `employee`, `department_reviewer`, `knowledge_admin`, `system_admin`, `founder_ceo`. Each role has a fixed set of permissions, checked on the server for every request.
  - `knowledge_admin`, `system_admin` and `founder_ceo` see all departments. Everyone else sees only their own departments.
  - "Company Wide" access is never given by default.

### 4.2 Sign-up and approval
- `POST /v1/auth/register` always creates an `employee` with status `pending`. The person must verify their email, and then an admin approves them under Admin → Access requests, choosing the role and departments.
- The first System Admin is created only from the server command line (`python -m backend.cli bootstrap-admin`).

### 4.3 Login and sessions
- `POST /v1/auth/login` with `{identifier, password}`. The identifier can be the email or the employee_id.
- On success the server creates a row in `sessions` (only the SHA-256 hash of the token is stored) and sets two cookies:
  - `qb_session`: HttpOnly, `SameSite=Lax`, `Secure` when the site is on HTTPS, `path=/`, **no `Domain` attribute** (so it only works on Maqsad's own host)
  - `qb_csrf`: readable by the page; it must be sent back in the `X-CSRF-Token` header on every write request
- Non-browser clients can send the same session token as `Authorization: Bearer <token>`.
- Every request checks that the session is valid **and** that the account is still `active`. If an account is suspended or deactivated, its sessions end immediately.
- **Admin MFA:** knowledge admins, system admins and the founder/CEO must pass a TOTP check (`/v1/auth/mfa/setup|enable|verify`) before they can use the session.
- Other endpoints: `/logout`, `/me`, `/session`, `/password-reset`, `/verify-email`, `/status-history`, `/profile`, `/preferences`, `/password`.
- Failed logins are throttled: 10 failures in 15 minutes blocks that identifier (counted per process).

### 4.4 Machine access that already exists
- **Internal API keys** (`qx_live_…`, only the SHA-256 hash is stored, created in Admin → API keys). Another internal app sends `X-API-Key` and names the employee with `user_id` = their `employee_id`. Maqsad then acts with that employee's permissions, and only if the account is active.
  - Keys have permissions (`ask`, `search`, `documents`, `sales_memory`, `feedback`), an optional department limit, an optional rate limit and an optional expiry date.
  - This lets the Portal **call Maqsad's API** for a user. It does **not** sign the user in to Maqsad's web app.
- `/v1/integrations/...` (today only the Obsidian vault push from the Git hook) takes service-to-service requests signed with HMAC-SHA256. They carry `X-Quixotic-Timestamp` (accepted within ±300 seconds) and `X-Quixotic-Signature` = HMAC of `"<timestamp>." + body`. The same pattern could be reused for Portal → Maqsad calls.

## 5. Things the SSO design has to respect (from the PRD)

1. **Users who aren't approved get no access.** A Portal login must not skip Maqsad's account states. Pending, Rejected, Suspended and Deactivated users stay locked out.
2. **Roles and departments live in Maqsad.** They are assigned by a Maqsad admin, a user can never raise their own role, and "Company Wide" is never given by default. If the Portal is going to send roles or departments, the owner has to approve that first.
3. **Admin MFA** is required for the admin roles (§5 FR-AUTH-06).
4. **Use an established authentication library or provider**, not home-made cryptography (§5 FR-AUTH-06, §11).
5. **Every login is audit-logged**: `USER_LOGIN` on success, `FAILED_AUTHENTICATION` on failure.
6. Any new mechanism has to be recorded in `docs/PRD_GAPS.md`, because the PRD currently doesn't mention the Portal or SSO.

## 6. Ways to connect them (not decided yet; needs the owner)

| Option | What the Portal would provide | What Maqsad would add |
|---|---|---|
| **A. OIDC / OAuth2 — Portal is the identity provider** (most standard) | An OIDC provider: authorize, token and JWKS endpoints, plus a client registered for `https://maqsad.quixoticcreatives.com/...callback`. ID tokens with a stable user id, email, and ideally `employee_id` | A "Sign in with Portal" button and a callback that checks the ID token with an OIDC library, finds the Maqsad user (by email or employee_id, or a new link table), checks they are `active`, then creates the usual `qb_session` |
| **B. Signed one-time hand-off link** | A "Open Maqsad" link carrying a short-lived signed token (asymmetric signature such as RS256/EdDSA, or HS256 with a shared secret, about 60 seconds, single use) | An endpoint that checks the signature, that it hasn't expired and hasn't been used before, finds the user, checks they are `active`, then creates the `qb_session` |
| **C. Shared parent-domain cookie** | Session cookie set on `.quixoticcreatives.com`, plus a session-introspection API | Calls the Portal on each request or at login. This ties the two apps tightly together; **not recommended** |

Questions for the Portal side, whichever option is chosen:
- Which field identifies a person in both apps: **email**, **employee_id**, or a Portal user id? Do the Portal's employee IDs match Maqsad's `employee_id` (e.g. `emp_104`)?
- Should Portal users who aren't in Maqsad yet be **created automatically as `pending`** (still needing approval), or should they be **refused** until a Maqsad admin adds them?
- Does the Portal already have MFA? Even if it does, Maqsad's admin MFA rule still applies unless the owner changes it.
- What is the Portal built with (framework, language, auth library)? That decides whether option A or B is easier.
- Logout: should signing out of the Portal also end Maqsad sessions (back-channel logout), or should each app manage its own?

## 7. Where things are in this repo

```
backend/        FastAPI app (main.py, config.py, api/v1/*, auth/security.py, permissions/, database/, retrieval/, generation/, ...)
workers/        background worker
migrations/     SQL schema (001_init … 017_client_memory)
web/            React + Vite + Tailwind single-page app
deploy/         Caddyfile, vault
docs/           backend.md, DEPLOYMENT.md, PRD_GAPS.md, product/ (PRD split)
PRODUCT.md      the PRD (source of truth)
CLAUDE.md       project rules for AI agents
```

Configuration comes only from environment variables with the `QB_` prefix (see `.env.example`). The ones that matter for sign-in:
- `QB_PUBLIC_URL`: an https URL turns on Secure cookies
- `QB_DOMAIN`
- `QB_SESSION_SECRET`
- `QB_SESSION_TTL_SECONDS`
- `QB_ADMIN_MFA_REQUIRED`
- `QB_FIELD_ENCRYPTION_KEY`
- `QB_CORS_ORIGINS`
