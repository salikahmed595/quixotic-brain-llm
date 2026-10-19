# Deploying Quixotic AI on one EC2 server

PRD §11 (Docker, HTTPS reverse proxy, backups, logs), §16 (written deployment guide; release only when (a)–(i) pass).
Owner decision (2026-10-17): one budget EC2 instance running everything with Docker Compose; uploaded originals in S3.

## 0. What runs where

`docker-compose.prod.yml` starts: **postgres** (PostgreSQL 16 + pgvector), **redis** (job queue), **api** (FastAPI + the web app),
**worker** (parsing, indexing, publication), **caddy** (HTTPS with Let's Encrypt). With `--profile hermes` also **quixotic-mcp**
and **hermes** (Telegram, PRD §9, optional). Only ports 80/443 are open. Data lives in Docker volumes plus `/srv/vault` (the Git
vault) and `/srv/hermes` (Hermes settings).

## 1. Server

1. **Instance.** Ubuntu 24.04 LTS, 100 GB gp3 disk, x86_64. Size it with the AT-09 load test (step 8). Measured on a 4-core
   laptop: 160 people signed in at once was fine, but a 40-question baseline reached p95 4.5 s for document search and a
   160-question burst 11.9 s (targets 2 s / 8 s). The CPU models are the limit, so start with **at least 16 vCPU / 32 GB**
   (for example c7i.4xlarge), run step 8, and go up or down from the result. Answers additionally depend on the AI provider.
2. **Security group.** Inbound 80 and 443 from anywhere, 22 from your office IP only.
3. **IAM role** on the instance with access to the S3 bucket (no AWS keys in `.env`). S3 bucket: private, default encryption on,
   versioning on, a lifecycle rule for `backups/` (e.g. 35 days).
4. **DNS.** An `A` record for your domain (e.g. `ai.yourcompany.com`) pointing at the instance's Elastic IP.
5. Install Docker:
   ```bash
   curl -fsSL https://get.docker.com | sudo sh && sudo usermod -aG docker ubuntu
   ```

## 2. Code and configuration

```bash
git clone https://github.com/salikahmed595/quixotic-brain-llm.git /opt/quixotic && cd /opt/quixotic
cp .env.example .env && chmod 600 .env
sudo install -d -o 10001 -g 10001 /srv/vault
```

Fill in every `>>> FILL IN <<<` in `.env` (explained in the file). In production in particular:
`QB_PUBLIC_URL=https://ai.yourcompany.com`, `QB_DOMAIN`, new random `QB_SESSION_SECRET` and `QB_FIELD_ENCRYPTION_KEY`,
`POSTGRES_PASSWORD`, `QB_MAIL_BACKEND=smtp` + SMTP values, `QB_S3_BUCKET`, `QB_AWS_REGION`, the answer model and its key,
`QB_ADMIN_MFA_REQUIRED=true`. **Delete** the four local-only lines (`QB_S3_ENDPOINT_URL`, `QB_SQS_ENDPOINT_URL`,
`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`) and `QB_RAW_STORAGE_DIR`. Keep secrets in AWS Secrets Manager and write `.env`
from there (PRD §10).

## 3. Start

```bash
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml logs -f api        # first start downloads the models (~4.6 GB), then "models: ready"
```

Open `https://ai.yourcompany.com` — Caddy gets the certificate automatically.

## 4. First administrator (PRD §5 FR-AUTH-06)

```bash
docker compose -f docker-compose.prod.yml exec api python -m backend.cli seed-departments
docker compose -f docker-compose.prod.yml exec api python -m backend.cli bootstrap-admin --email you@yourcompany.com --name "Your Name" --username you
```

It asks for a password and refuses once a System Admin exists. Sign in, set up two-step sign-in with your phone, then:
departments and reviewers (Departments), access levels check (System), first documents (Add information / Import Obsidian notes),
and classify any documents marked "Needs classification" (Documents).

## 5. Backups and the restore drill (PRD §16 g)

```bash
sudo crontab -e
# every night at 02:30: backup to S3; every Sunday: prove it restores
30 2 * * * cd /opt/quixotic && docker compose -f docker-compose.prod.yml exec -T api python -m backend.ops.backup create --dir /srv/vault/backups --s3 >> /var/log/quixotic-backup.log 2>&1
0 4 * * 0  cd /opt/quixotic && docker compose -f docker-compose.prod.yml exec -T api python -m backend.ops.backup drill --dir /srv/vault/backups >> /var/log/quixotic-backup.log 2>&1
```

A backup = database dump + vault archive + manifest (checksums, row counts, audit-log hash). The drill restores the newest backup
into a throw-away database and checks all of it; System shows the last backup and the last drill. Also enable **EBS snapshots**
(Data Lifecycle Manager, daily) for the whole disk. Restore for real (after stopping api and worker):

```bash
docker compose -f docker-compose.prod.yml stop api worker
docker compose -f docker-compose.prod.yml run --rm api python -m backend.ops.backup restore --file /srv/vault/backups/<file>.dump --yes-replace-the-database
docker compose -f docker-compose.prod.yml start api worker
```

## 6. Optional: Hermes + Telegram (PRD §9)

1. In Telegram, @BotFather → `/newbot` twice: **Quixotic Hermes** (people talk to it) and **Quixotic Approvals** (confirmations
   and approvals).
2. `.env`: `QB_TELEGRAM_BOT_TOKEN` (Approvals bot), `QB_TELEGRAM_WEBHOOK_SECRET`, `QB_HERMES_SHARED_SECRET`, `QUIXOTIC_MCP_TOKEN`
   (random values), optional `QUIXOTIC_DEFAULT_TELEGRAM_USER`.
3. Hermes settings:
   ```bash
   sudo install -d -m 700 /srv/hermes
   sudo cp deploy/hermes/config.yaml deploy/hermes/SOUL.md /srv/hermes/
   sudo cp deploy/hermes/hermes.env.example /srv/hermes/.env && sudo nano /srv/hermes/.env    # Hermes bot token, allowed ids, keys
   docker compose -f docker-compose.prod.yml --profile hermes up -d --build
   docker compose -f docker-compose.prod.yml exec api python -m backend.cli telegram-webhook
   ```
4. **H0 check (every Hermes upgrade):** `docker compose -f docker-compose.prod.yml run --rm -it hermes tools list --platform telegram`
   must show only `clarify` and the five `quixotic` tools. Also send a short voice note once and confirm it is transcribed.
5. Each person sends `/start` to the Approvals bot, gets their Telegram ID, and an admin links it in System → Integrations.
   Put the same IDs in `TELEGRAM_ALLOWED_USERS` in `/srv/hermes/.env`.

## 7. Optional: Obsidian sync for the CEO

```bash
sudo bash deploy/vault/setup-vault-git.sh
sudo nano /srv/vault/hooks.env                                  # your domain + QB_HERMES_SHARED_SECRET
sudo bash deploy/vault/add-vault-key.sh ceo "ssh-ed25519 AAAA... ceo-laptop"
echo "QB_VAULT_REMOTE=/srv/vault/vault.git" >> .env && docker compose -f docker-compose.prod.yml up -d
```

Link the branch name `ceo` to the CEO's account in System → Integrations (Obsidian branch). On the CEO's laptop: install Git and
Obsidian, `git clone vault@ai.yourcompany.com:/srv/vault/vault.git`, `git checkout -b proposals/ceo`, open the folder as a vault,
install the **Obsidian Git** plugin and turn on automatic commit-and-sync. Notes need `departments:` (and for new notes
`sensitivity:`) in their front matter; every pushed change becomes a proposal in Approvals.

## 8. Before go-live: acceptance (PRD §13, §16)

```bash
# AT-09 load test from any machine (search = no AI cost; answer = full answers, costs money)
LOAD_PASSWORD=<random> docker compose -f docker-compose.prod.yml exec -e LOAD_PASSWORD api python scripts/load_test.py prepare --users 160 --department Sales
LOAD_PASSWORD=<same> python scripts/load_test.py run --url https://ai.yourcompany.com --users 160 --baseline 40 --mode search
LOAD_PASSWORD=<same> python scripts/load_test.py run --url https://ai.yourcompany.com --users 160 --baseline 40 --mode answer
docker compose -f docker-compose.prod.yml exec api python scripts/load_test.py cleanup
```

If p95 misses the targets: a larger instance (the models use every core), `QB_RERANK_TOP_K=2`, or a higher `QB_RERANK_SKIP_MARGIN`
(fewer reranker calls), then re-run. The rest of §16: AT-08 visual test (`cd web && npm run test:visual`), the integration test
suite on a copy of the database, a restore drill, and the owner's sign-off that the AI provider is approved for company data (§10).

## 9. Updates

```bash
cd /opt/quixotic && git pull
docker compose -f docker-compose.prod.yml up -d --build          # migrations run automatically at start
```

Logs: `docker compose -f docker-compose.prod.yml logs --since 1h api worker` (rotated, 200 MB max per service). The audit log can
be verified any time: System → Audit log, or `GET /v1/admin/system/audit-verify`.
