# Backend
History: git log -p docs/backend.md
Python+FastAPI. Gaps/choices: `docs/PRD_GAPS.md`. Deploy: `docs/DEPLOYMENT.md`. Settings: `.env.example`.

## Layout
`backend/{api,auth,permissions,ingestion,retrieval,reranking,generation,sales_memory,database,analytics,knowledge,ops}`, `workers/`, `evaluation/`, `migrations/`, `web/` (React+Vite+Tailwind), `deploy/`, `scripts/`, `tests/`.

## Ask flow
auth -> role -> department scope -> query normalization -> keyword+vector search (status/scope filtered in SQL) -> rerank -> best 5 -> (no evidence/low confidence: not-found text, no LLM) -> LLM -> answer + sources. API docs at `/docs`; main routes `/v1/auth/*`, `/v1/admin/*`, `/v1/knowledge/*`, `/v1/chats`, `/v1/ask`, `/v1/search`, `/v1/health`.

## Run locally
```bash
docker compose up -d postgres
python scripts/dev_up.py               # S3/SQS stand-in + migrations + API + worker -> http://localhost:8000
python -m backend.cli create-user --employee-id admin --email you@your-company.com --name "Your Name" --role administrator
```
Windows:
```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
copy .env.example .env                                     # set QB_SESSION_SECRET, model id + API key
docker compose up -d postgres
.\.venv\Scripts\python.exe scripts\dev_up.py
$env:QB_DATABASE_URL="postgresql://quixotic:quixotic@localhost:5432/quixotic_brain"
.\.venv\Scripts\python.exe -m backend.cli create-user --employee-id admin --email you@your-company.com --name "Your Name" --role administrator --department "Company Wide"
```
Later: `Start Quixotic AI.bat` (Docker Desktop running). Models ~4.6 GB download on first start; `/v1/health` shows `"models": "ready"`. Docker needs virtualization (SVM/VT-x in BIOS; `wsl --install --no-distribution`).

Manual: `pip install -r requirements-dev.txt`; `python -m backend.cli migrate`; `uvicorn backend.main:app`; `python -m workers.worker`; `moto_server -p 5000`.

Answer key in `.env` (never commit):
```
QB_GENERATION_PROVIDER=openai        # or gemini / claude / deepseek
QB_GENERATION_MODEL_ID=<model>
OPENAI_API_KEY=<key>                 # GEMINI_API_KEY / ANTHROPIC_API_KEY (+QB_GENERATION_MAX_TOKENS) / DEEPSEEK_API_KEY
```

## Tests
- `python -m pytest`; integration: `QB_TEST_DATABASE_URL=postgresql://quixotic:quixotic@localhost:5432/postgres python -m pytest`; Redis: `QB_TEST_REDIS_URL=redis://host:6379/0`.
- Quality: `python -m evaluation.run_eval --base-url http://localhost:8000 --api-key qx_live_... --user-id emp_001`.
- Load (AT-09): `scripts/load_test.py`. Backups: `python -m backend.ops.backup`.

## Frontend `web/`
```bash
cd web && npm ci && npm run build      # -> web/dist; API serves it with QB_FRONTEND_DIR=web/dist
```
Dev: `npm run dev` (5173, proxies :8000). Elsewhere: set `window.QB_API` (or `?api=`) and `QB_CORS_ORIGINS`. No mock data. Layout follows `UI images/reference/` (§4).

Visual test AT-08 (`web/tests/visual.spec.ts`): needs admin named `Administrator` and employee named `Employee` in every active department; creds via `QA_ADMIN_USER`, `QA_EMPLOYEE_USER`, `QA_PASSWORD`, optional `QA_BASE_URL`, or gitignored `web/.env.visual`.
```bash
python -m backend.cli create-user --employee-id qa_visual_admin --email qa.visual.admin@example.com --name Administrator --role administrator --department "Company Wide"
```
```bash
cd web && npm ci && npx playwright install chromium && npm run build
```
```bash
cd web && npm run test:visual
```
Failures: `web/test-results/`, `web/playwright-report/`.

## Knowledge statuses (§8)
Draft / Under Review / Approved / Published / Archived. Retrieval: Published and unexpired only.

Sales-memory import needs `ConversationParser` + `MemoryExtractor` via `build_services(settings, parser=..., extractor=...)` (undefined by PRD).
