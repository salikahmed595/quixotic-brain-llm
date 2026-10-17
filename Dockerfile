# One image for the API (ECS Fargate) and the background worker (ECS):
#   api (default)   uvicorn backend.main:app
#   worker          python -m workers.worker
# CPU-only. Python 3.14 is the version the test-suite was run with.
# PRD §11 front-end: build web/ once, copy the static files into the API image.
FROM node:24-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web ./
RUN npm run build

FROM python:3.14-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend ./backend
COPY workers ./workers
COPY migrations ./migrations
COPY --from=web /web/dist ./web/dist
ENV QB_FRONTEND_DIR=web/dist
EXPOSE 8000
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
