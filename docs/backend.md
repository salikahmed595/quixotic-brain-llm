# Quixotic Brain — backend
Python + FastAPI (PRD §49; § numbers in this file follow the old PRD). Built from `PRODUCT.md`; undefined items in [PRD_GAPS.md](PRD_GAPS.md) (read before deploying).

## Layout (§50)
```
backend/
  api/            FastAPI routes (v1/), deps, service wiring, workflow helper
  auth/           password hashing, signed tokens, API keys, rate limit        (§40, §41)
  permissions/    roles & capabilities (§9), department scope (§42), approval workflow (§12.3)
  ingestion/      validate → extract → clean → chunk → embed → store; S3/SQS adapters   (§13, §46, §47)
  retrieval/      language + Roman Urdu normalization, embeddings, hybrid search, ask   (§7, §22–§26, §29–§32)
  reranking/      reranker interface + cross-encoder                                   (§27)
  generation/     LLM interface, prompt rules, Bedrock provider                        (§28, §29, §52)
  sales_memory/   §16.2 record, anonymizer (§18), Discord importer (§17)
  database/       pool + migrations runner, SQL stores (PostgreSQL + pgvector)         (§45)
  analytics/      dashboard (§34), knowledge health (§36), audit events (§53)
workers/          SQS consumer (document.process, knowledge.index, discord.import, reindex)   (§47)
evaluation/       §58 question set, Recall@5/@10 + MRR runner                                 (§59)
migrations/       001_init.sql
tests/            pytest
```

## `POST /v1/ask` flow (§7)
authenticate (Bearer, or `X-API-Key`+`user_id`) -> role check -> **department scope** (admin: all; others: authorized depts; API key: intersection) -> query normalization (original kept) -> keyword+vector search filtered by `status = active` and scope **inside the SQL** -> 20–40 candidates -> reranker -> best 5–8 -> (no evidence/low confidence => §29/§32 message, no LLM call) -> LLM with PRD rules -> answer, confidence label, sources, historical cases.

## Endpoints
§37 core: `POST /v1/ask`, `POST /v1/search`, `POST|GET /v1/documents`, `DELETE /v1/documents/{id}`, `POST /v1/sales-memory`, `POST /v1/feedback`, `GET /v1/health`.
Added (names ours, PRD_GAPS §3): `/v1/auth/login|me`, `/v1/knowledge…` (create, list, edit draft, transitions, new version), `/v1/sales-memory/imports`, `/v1/users`, `/v1/departments`, `/v1/api-keys`, `/v1/jobs`, `/v1/admin/reindex`, `/v1/dashboard`, `/v1/failed-questions`, `/v1/knowledge-health`, `/v1/audit-logs`. Docs at `/docs`.

## Stack
Frontend Next.js+Tailwind on Vercel · backend FastAPI on ECS Fargate · RDS PostgreSQL+pgvector · S3 docs · SQS · ECS worker · BGE-M3 CPU embeddings · pgvector+keyword hybrid · multilingual BGE reranker · generation Gemini/OpenAI/Claude (Bedrock later) · JWT (Cognito later) · AWS Secrets Manager · CloudWatch. Not used: Kubernetes, GPUs, microservices, vector cluster. One image runs API and worker. (Current deploy: single EC2, see DEPLOYMENT.md.)

## Quick start
```bash
docker compose up -d postgres          # database (once)
python scripts/dev_up.py               # local S3/SQS stand-in + migrations + API + worker -> http://localhost:8000
python -m backend.cli create-user --employee-id admin --email you@your-company.com --name "Your Name" --role administrator
```
Open **http://localhost:8000** (never `index.html` directly). New people use *Create an account* (approver grants access) or an admin adds them under *Users*. Settings in git-ignored `.env` (template `.env.example`; comments on their own lines).

## Windows (PowerShell)
Needs Python 3.12+ and Docker Desktop. If Docker says *Virtual Machine Platform not enabled*: enable **SVM Mode** (AMD) / **Intel VT-x** in BIOS, run `wsl --install --no-distribution` in admin PowerShell, restart.
```powershell
py -3 -m venv .venv                                        # or: python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
copy .env.example .env                                     # then set QB_SESSION_SECRET and, for answers, the model id + API key
docker compose up -d postgres
.\.venv\Scripts\python.exe scripts\dev_up.py               # moto S3/SQS + migrations + API + worker -> http://localhost:8000
```
Second PowerShell, first admin (prompts for password):
```powershell
$env:QB_DATABASE_URL="postgresql://quixotic:quixotic@localhost:5432/quixotic_brain"
.\.venv\Scripts\python.exe -m backend.cli create-user --employee-id admin --email you@your-company.com --name "Your Name" --role administrator --department "Company Wide"
```
Later: open Docker Desktop, double-click **`Start Quixotic AI.bat`**. Models (BGE-M3 + reranker, ~4.6 GB) download on first start; `GET /v1/health` shows `"models": "ready"` after 1–2 min. `scripts/download_models.sh` optional (bash); default `.env.example` loads models by HF id.

## Run locally step by step
```bash
pip install -r requirements-dev.txt                 # CPU PyTorch, sentence-transformers, SDKs, test tools
docker compose up -d postgres                       # PostgreSQL + pgvector (or point QB_DATABASE_URL at RDS)
scripts/download_models.sh                          # optional: BGE-M3 + BGE reranker (~4.6 GB) into .models/ (else downloaded on first use)
cp .env.example .env                                # review every value (PRD_GAPS §1); add GEMINI_API_KEY / OPENAI_API_KEY / ANTHROPIC_API_KEY
moto_server -p 5000                                 # local S3 + SQS stand-in (create the bucket and queue named in .env)
python -m backend.cli migrate
QB_NEW_USER_PASSWORD=... python -m backend.cli create-user --employee-id emp_001 --email you@quixotic.ai     --name "Your Name" --role administrator --department "Company Wide"
uvicorn backend.main:app                            # API  (docs at /docs)
python -m workers.worker                            # background worker (documents, indexing, imports, re-index)
```
Tests: `python -m pytest` (unit, no services). Integration (DB up): `QB_TEST_DATABASE_URL=postgresql://quixotic:quixotic@localhost:5432/postgres python -m pytest` (throw-away DB per test). Retrieval quality: `python -m evaluation.run_eval --base-url http://localhost:8000 --api-key qx_live_... --user-id emp_001`.

Sales-memory import needs `ConversationParser` + `MemoryExtractor` (PRD defines neither): pass to `build_services(settings, parser=..., extractor=...)`; until then the import job fails with an explanatory error.

## Front-end (`web/`)
React+TS+Tailwind on Vite (PRD §11), **no mock data** (every screen uses the API, shows empty states). Desktop layout follows the two §4 screenshots in `UI images/reference/`.
```bash
cd web && npm ci && npm run build      # -> web/dist
```
`QB_FRONTEND_DIR=web/dist` makes the API serve it at `/`; `scripts/dev_up.py` builds it if missing. Live edit: `npm run dev` in `web/` (port 5173, API proxied to :8000). Elsewhere: serve `web/dist`, set `window.QB_API` (or `?api=`) to API URL, set `QB_CORS_ORIGINS` on API.

| Role | Sees |
|---|---|
| Employee | Ask only (ChatGPT-style sidebar: New chat, search, previous chats); no dashboard |
| Contributor | Ask · Knowledge · Add information · Documents |
| Manager | + Approvals · Dashboard |
| Administrator | + Insights · Users · Departments · API keys · System |

Everyone: chat sidebar (new, previous, rename, delete); staff also get collapsible *Workspace* group.

### Visual regression (§13 AT-08)
`web/tests/visual.spec.ts` (Playwright/Chromium), signs in as employee + admin on the **running local stack**, checks:
- Home at 1478×907 (employee) / 1468×901 (admin) vs the §4 screenshots (history titles, mascot, Workspace scrollbar masked; <=4 px offsets and anti-aliasing tolerated; self-check proves 10 px drift fails).
- Employee sidebar has no Workspace/Knowledge/Manage/Administration items (§4.2).
- Admin sidebar groups/items in exact §4.3 order.
- At 375 px (drawer closed/open): no horizontal scroll, controls >=44×44 px (§4.4).

Needs one admin and one employee in **every** active department (card reads "Company Wide"), named `Administrator` and `Employee`. Credentials from env (`QA_ADMIN_USER`, `QA_EMPLOYEE_USER`, `QA_PASSWORD`, optional `QA_BASE_URL` default `http://localhost:8000`) or gitignored `web/.env.visual` (`KEY=value`). Never commit.
```bash
python -m backend.cli create-user --employee-id qa_visual_admin --email qa.visual.admin@example.com --name Administrator --role administrator --department "Company Wide"
```
```bash
cd web && npm ci && npx playwright install chromium && npm run build
```
```bash
cd web && npm run test:visual
```
(`create-user`: set `QB_NEW_USER_PASSWORD` or type at prompt; employee the same with `--role employee` and one `--department` per active department.) Failures leave `actual`/`expected`/`diff` PNGs in `web/test-results/`, HTML report in `web/playwright-report/`.

Sales Memory and Product Hub screens removed (backend sales-memory search still powers *Sales coach* mode in Ask).

## Answer-model key
In git-ignored `.env`, then restart:
```
QB_GENERATION_PROVIDER=openai        # or gemini / claude
QB_GENERATION_MODEL_ID=<model name from your account>
OPENAI_API_KEY=<your key>            # GEMINI_API_KEY / ANTHROPIC_API_KEY for the others (Claude also needs QB_GENERATION_MAX_TOKENS)
```
In AWS: Secrets Manager injected as the same env var. Never commit `.env`.

## Knowledge statuses (§12.3)
`draft -> submitted -> pending_review -> approved -> active`, plus `rejected`, `archived`, `expired`. Contributors submit; dept manager or admin reviews; only admins archive. Activating archives the previous active (§15). Retrieval sees `active` only unless `include_archived`.

## Production and ops
- EC2 deploy, backups, Hermes/Telegram/Obsidian setup, updates: `docs/DEPLOYMENT.md`. Settings: `.env.example`.
- Load test (AT-09): `scripts/load_test.py`. Backups/drill: `python -m backend.ops.backup`.
- Hermes/Telegram/Obsidian design + status: `docs/HERMES_TELEGRAM_OBSIDIAN_PLAN.md`.
- Tests: `python -m pytest`; PostgreSQL+pgvector: `QB_TEST_DATABASE_URL=postgresql://user:pw@host:5432/postgres python -m pytest tests/integration`; Redis: `QB_TEST_REDIS_URL=redis://host:6379/0`; UI parity: `cd web && npm run test:visual`.
