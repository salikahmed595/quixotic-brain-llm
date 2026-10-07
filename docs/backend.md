# Quixotic Brain — backend

Python + FastAPI (PRD §49). Built only from `PRODUCT.md`; anything the PRD does not define is listed in
[PRD_GAPS.md](PRD_GAPS.md). Read that file before deploying.

## Layout (PRD §50)

```
backend/
  api/            FastAPI routes (v1/), dependencies, service wiring, workflow helper
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
evaluation/       §58 question set, Recall@5/@10 and MRR runner                              (§59)
migrations/       001_init.sql
tests/            pytest suite
```

## Request flow for `POST /v1/ask` (PRD §7)

authenticate (Bearer token, or `X-API-Key` + `user_id`) → role check → **department scope** (administrator: all; others:
authorized departments; API key: intersection) → query normalization (original kept) → keyword + vector search, filtered
by `status = active` and scope **inside the SQL** → candidates (20–40) → reranker → best 5–8 → *(no evidence or low
confidence ⇒ PRD §29/§32 message, no LLM call)* → LLM with PRD rules → answer, confidence label, sources, historical cases.

## Endpoints

PRD §37 core: `POST /v1/ask`, `POST /v1/search`, `POST|GET /v1/documents`, `DELETE /v1/documents/{id}`,
`POST /v1/sales-memory`, `POST /v1/feedback`, `GET /v1/health`.
Added to support the PRD's modules (names are this implementation's — see PRD_GAPS §3): `/v1/auth/login|me`, `/v1/knowledge…`
(create, list, edit draft, transitions, new version), `/v1/sales-memory/imports`, `/v1/users`, `/v1/departments`, `/v1/api-keys`,
`/v1/jobs`, `/v1/admin/reindex`, `/v1/dashboard`, `/v1/failed-questions`, `/v1/knowledge-health`, `/v1/audit-logs`.
Interactive docs at `/docs` when running.

## Stack (as decided)

Frontend Next.js + Tailwind on Vercel · **Backend** Python FastAPI on ECS Fargate · **DB** RDS PostgreSQL + pgvector · documents S3 · queue SQS ·
background processing ECS worker · embeddings BGE-M3 on CPU · retrieval pgvector + keyword/hybrid · reranker multilingual BGE reranker ·
generation Gemini / OpenAI / Claude (Bedrock later) · auth JWT (Cognito later) · secrets AWS Secrets Manager · monitoring CloudWatch.
Not used: Kubernetes, GPUs, microservices, a vector cluster. One image runs both the API and the worker.

## Quick start on your machine

```bash
docker compose up -d postgres          # database (once)
python scripts/dev_up.py               # local S3/SQS stand-in + migrations + API + worker -> http://localhost:8000
python -m backend.cli create-user --employee-id admin --email you@your-company.com --name "Your Name" --role administrator
```
Open **http://localhost:8000** (never the `index.html` file directly: the page needs the API behind it). New people either use
*Create an account* on the login page (an approver then grants access) or are added by an administrator under *Users*. Settings live
in `.env` (git-ignored; template: `.env.example` — keep comments on their own lines).

## Windows quick start (PowerShell)

Needs Python 3.12+ and Docker Desktop. Docker needs hardware virtualization: if Docker Desktop says *Virtual Machine Platform
not enabled*, turn on **SVM Mode** (AMD) or **Intel VT-x** in the BIOS, then run `wsl --install --no-distribution` in an
administrator PowerShell and restart Windows.

```powershell
py -3 -m venv .venv                                        # or: python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
copy .env.example .env                                     # then set QB_SESSION_SECRET and, for answers, the model id + API key
docker compose up -d postgres
.\.venv\Scripts\python.exe scripts\dev_up.py               # moto S3/SQS + migrations + API + worker -> http://localhost:8000
```
In a second PowerShell, create the first administrator (prompts for the password):
```powershell
$env:QB_DATABASE_URL="postgresql://quixotic:quixotic@localhost:5432/quixotic_brain"
.\.venv\Scripts\python.exe -m backend.cli create-user --employee-id admin --email you@your-company.com --name "Your Name" --role administrator --department "Company Wide"
```
Afterwards, start everything by opening Docker Desktop and double-clicking **`Start Quixotic AI.bat`**. The models (BGE-M3 and the
reranker, ~4.6 GB) download on first start and are cached; `GET /v1/health` shows `"models": "ready"` once loaded (1–2 minutes).
`scripts/download_models.sh` is optional (bash only); the default `.env.example` loads the models by their Hugging Face ids.

## Run it locally (step by step)

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

Tests: `python -m pytest` (unit, no services needed). With the database up, also run the integration suite:
`QB_TEST_DATABASE_URL=postgresql://quixotic:quixotic@localhost:5432/postgres python -m pytest`
(creates and drops a throw-away database per test). Retrieval quality:
`python -m evaluation.run_eval --base-url http://localhost:8000 --api-key qx_live_... --user-id emp_001`.

Sales-memory import needs a `ConversationParser` and `MemoryExtractor` (the PRD defines neither). Pass them to
`build_services(settings, parser=..., extractor=...)`; until then the import job fails with an explanatory error.

## Front-end (`frontend/`)

Plain HTML + CSS + JS, no build step, **no mock data**: every screen reads from or writes to the API and shows an empty state when there is
nothing yet. Set `QB_FRONTEND_DIR=frontend` and the API serves it at `/` (same origin). To host it elsewhere (stack: Vercel), serve the three
files, set `window.QB_API` (or `?api=`) to the API URL, and set `QB_CORS_ORIGINS` on the API.

| Role | Sees |
|---|---|
| Employee | **Ask only** — the "Ask Quixotic AI" screen with a ChatGPT-style sidebar: New chat, search chats, previous chats. No dashboard. |
| Contributor | Ask · Knowledge · Add information · Documents |
| Manager | + Approvals · Dashboard |
| Administrator | + Insights · Users · Departments · API keys · System |

Everyone gets the chat sidebar (new chat, previous chats, rename, delete); staff also get a collapsible *Workspace* group.

Sales Memory and Product Hub screens were removed (the backend's sales-memory search still powers the *Sales coach* mode in Ask).

## Your answer-model key (OpenAI / Gemini / Claude)

Put it in the git-ignored **`.env`** file in the project folder, then restart the app:
```
QB_GENERATION_PROVIDER=openai        # or gemini / claude
QB_GENERATION_MODEL_ID=<model name from your account>
OPENAI_API_KEY=<your key>            # GEMINI_API_KEY / ANTHROPIC_API_KEY for the others (Claude also needs QB_GENERATION_MAX_TOKENS)
```
In AWS, put the key in Secrets Manager and inject it as the same environment variable. Never commit `.env`.

## Statuses of knowledge (PRD §12.3)

`draft → submitted → pending_review → approved → active`, plus `rejected`, `archived`, `expired`.
Contributors submit; the department manager or an administrator reviews; only administrators archive. Activating a version
archives the previous active one (§15). Retrieval sees `active` only unless `include_archived` is sent.
