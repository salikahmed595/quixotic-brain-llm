# One image for the API and the background worker (PRD §11 "Dockerized services"):
#   api (default)   uvicorn backend.main:app
#   worker          python -m workers.worker
# CPU-only. The web app (web/) is built in the first stage and served by the API.
FROM node:24-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web ./
RUN npm run build

FROM python:3.14-slim
# git: the knowledge vault (PRD §8); postgresql-client: backups and restore drills (PRD §16 g); curl: health checks.
RUN apt-get update && apt-get install -y --no-install-recommends git postgresql-client curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --retries 10 --timeout 120 -r requirements.txt
COPY requirements-images.txt .
RUN pip install --no-cache-dir --retries 10 --timeout 120 -r requirements-images.txt
COPY backend ./backend
COPY workers ./workers
COPY migrations ./migrations
COPY scripts ./scripts
COPY --from=web /web/dist ./web/dist
ENV QB_FRONTEND_DIR=web/dist PYTHONUNBUFFERED=1
RUN useradd --create-home --uid 10001 quixotic && mkdir -p /srv/vault /home/quixotic/.cache/huggingface && chown -R quixotic /srv/vault /home/quixotic
USER quixotic
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=120s CMD curl -fsS http://127.0.0.1:8000/v1/health || exit 1
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
