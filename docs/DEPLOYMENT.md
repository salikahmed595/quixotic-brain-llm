# Deploy Quixotic AI on one EC2 server
PRD §11 (Docker, HTTPS proxy, backups, logs), §16 (release only when (a)–(i) pass). Owner decision 2026-10-17: one budget EC2 + Docker Compose; originals in S3.

## 0. Services
`docker-compose.prod.yml`: postgres (PG16+pgvector), redis (queue), api (FastAPI+web), worker (parse/index/publish), caddy (HTTPS, Let's Encrypt). `--profile hermes` adds quixotic-mcp + hermes (Telegram, §9, optional). Only 80/443 open. Data: Docker volumes, `/srv/vault` (Git vault), `/srv/hermes`.

## 1. Server
1. Ubuntu 24.04, 100 GB gp3, x86_64. Size via AT-09 load test (§8). 4-core laptop: 160 users signed in OK; 40-q baseline p95 4.5 s doc search, 160-q burst 11.9 s (targets 2 s / 8 s); CPU models are the limit. Start **>=16 vCPU / 32 GB** (c7i.4xlarge), adjust. Answers also depend on AI provider.
2. Security group: 80/443 anywhere, 22 office IP only.
3. IAM role with S3 access (no AWS keys in `.env`). Bucket: private, encrypted, versioned, lifecycle on `backups/` (~35 d).
4. DNS `A` record (e.g. `ai.yourcompany.com`) -> Elastic IP.
5. Docker:
   ```bash
   curl -fsSL https://get.docker.com | sudo sh && sudo usermod -aG docker ubuntu
   ```

## 2. Code and config
```bash
git clone https://github.com/salikahmed595/quixotic-brain-llm.git /opt/quixotic && cd /opt/quixotic
cp .env.example .env && chmod 600 .env
sudo install -d -o 10001 -g 10001 /srv/vault
```
Fill every `>>> FILL IN <<<` in `.env`. Production: `QB_PUBLIC_URL=https://ai.yourcompany.com`, `QB_DOMAIN`, new random `QB_SESSION_SECRET` + `QB_FIELD_ENCRYPTION_KEY`, `POSTGRES_PASSWORD`, `QB_MAIL_BACKEND=smtp` + SMTP values, `QB_S3_BUCKET`, `QB_AWS_REGION`, answer model + key, `QB_ADMIN_MFA_REQUIRED=true`. **Delete** `QB_S3_ENDPOINT_URL`, `QB_SQS_ENDPOINT_URL`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `QB_RAW_STORAGE_DIR`. Keep secrets in AWS Secrets Manager; write `.env` from it (§10).

## 3. Start
```bash
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml logs -f api        # first start downloads models (~4.6 GB), then "models: ready"
```
Open `https://ai.yourcompany.com` (Caddy gets cert automatically).

## 4. First admin (§5 FR-AUTH-06)
```bash
docker compose -f docker-compose.prod.yml exec api python -m backend.cli seed-departments
docker compose -f docker-compose.prod.yml exec api python -m backend.cli bootstrap-admin --email you@yourcompany.com --name "Your Name" --username you
```
Prompts for password; refuses once a System Admin exists. Then: sign in, set up 2-step with phone, Departments + reviewers, System access-level check, first documents (Add information / Import Obsidian notes), classify "Needs classification" docs (Documents).

## 5. Backups + restore drill (§16 g)
```bash
sudo crontab -e
# every night at 02:30: backup to S3; every Sunday: prove it restores
30 2 * * * cd /opt/quixotic && docker compose -f docker-compose.prod.yml exec -T api python -m backend.ops.backup create --dir /srv/vault/backups --s3 >> /var/log/quixotic-backup.log 2>&1
0 4 * * 0  cd /opt/quixotic && docker compose -f docker-compose.prod.yml exec -T api python -m backend.ops.backup drill --dir /srv/vault/backups >> /var/log/quixotic-backup.log 2>&1
```
Backup = DB dump + vault archive + manifest (checksums, row counts, audit-log hash). Drill restores newest into a throw-away DB and checks; System shows last backup/drill. Also enable daily EBS snapshots (Data Lifecycle Manager). Real restore:
```bash
docker compose -f docker-compose.prod.yml stop api worker
docker compose -f docker-compose.prod.yml run --rm api python -m backend.ops.backup restore --file /srv/vault/backups/<file>.dump --yes-replace-the-database
docker compose -f docker-compose.prod.yml start api worker
```

## 6. Optional: Hermes + Telegram (§9)
1. @BotFather `/newbot` twice: **Quixotic Hermes** (chat) and **Quixotic Approvals** (confirm/approve).
2. `.env`: `QB_TELEGRAM_BOT_TOKEN` (Approvals bot), `QB_TELEGRAM_WEBHOOK_SECRET`, `QB_HERMES_SHARED_SECRET`, `QUIXOTIC_MCP_TOKEN` (random), optional `QUIXOTIC_DEFAULT_TELEGRAM_USER`.
3. Hermes settings:
   ```bash
   sudo install -d -m 700 /srv/hermes
   sudo cp deploy/hermes/config.yaml deploy/hermes/SOUL.md /srv/hermes/
   sudo cp deploy/hermes/hermes.env.example /srv/hermes/.env && sudo nano /srv/hermes/.env    # Hermes bot token, allowed ids, keys
   docker compose -f docker-compose.prod.yml --profile hermes up -d --build
   docker compose -f docker-compose.prod.yml exec api python -m backend.cli telegram-webhook
   ```
4. **H0 check (every Hermes upgrade):** `docker compose -f docker-compose.prod.yml run --rm -it hermes tools list --platform telegram` must show only `clarify` + the five `quixotic` tools. Also send a voice note once; confirm transcription.
5. Each person sends `/start` to Approvals bot, gets Telegram ID; admin links it in System -> Integrations. Same IDs go in `TELEGRAM_ALLOWED_USERS` in `/srv/hermes/.env`.

## 7. Optional: Obsidian sync for CEO
```bash
sudo bash deploy/vault/setup-vault-git.sh
sudo nano /srv/vault/hooks.env                                  # your domain + QB_HERMES_SHARED_SECRET
sudo bash deploy/vault/add-vault-key.sh ceo "ssh-ed25519 AAAA... ceo-laptop"
echo "QB_VAULT_REMOTE=/srv/vault/vault.git" >> .env && docker compose -f docker-compose.prod.yml up -d
```
Link branch `ceo` to CEO's account in System -> Integrations (Obsidian branch). CEO laptop: install Git + Obsidian, `git clone vault@ai.yourcompany.com:/srv/vault/vault.git`, `git checkout -b proposals/ceo`, open as vault, install **Obsidian Git** plugin with auto commit-and-sync. Notes need front matter `departments:` (new notes also `sensitivity:`); each pushed change becomes an Approvals proposal.

## 8. Go-live acceptance (§13, §16)
```bash
# AT-09 load test from any machine (search = no AI cost; answer = full answers, costs money)
LOAD_PASSWORD=<random> docker compose -f docker-compose.prod.yml exec -e LOAD_PASSWORD api python scripts/load_test.py prepare --users 160 --department Sales
LOAD_PASSWORD=<same> python scripts/load_test.py run --url https://ai.yourcompany.com --users 160 --baseline 40 --mode search
LOAD_PASSWORD=<same> python scripts/load_test.py run --url https://ai.yourcompany.com --users 160 --baseline 40 --mode answer
docker compose -f docker-compose.prod.yml exec api python scripts/load_test.py cleanup
```
p95 misses: bigger instance, `QB_RERANK_TOP_K=2`, or higher `QB_RERANK_SKIP_MARGIN`; re-run. Rest of §16: AT-08 visual (`cd web && npm run test:visual`), integration suite on a DB copy, restore drill, owner sign-off that AI provider is approved for company data (§10).

## 9. Updates
```bash
cd /opt/quixotic && git pull
docker compose -f docker-compose.prod.yml up -d --build          # migrations run automatically at start
```
Logs: `docker compose -f docker-compose.prod.yml logs --since 1h api worker` (rotated, 200 MB max/service). Verify audit log: System -> Audit log or `GET /v1/admin/system/audit-verify`.

## 10. Test Obsidian sync on one PC (no server, no Telegram)
```bash
python scripts/obsidian_local.py setup --email you@yourcompany.com --name ceo    # then restart the app
```
Creates `.obsidian-remote.git` (stands in for the server, same hook rules) and `obsidian-vault/` on `proposals/ceo`; sets `QB_VAULT_REMOTE` + `QB_HERMES_SHARED_SECRET` in `.env`; links branch `ceo` to that user. Open `obsidian-vault/` in Obsidian, add a note with `departments:` + `sensitivity:` front matter, commit + push (Obsidian Git plugin or `git push`) -> Approvals -> approve -> ask.
