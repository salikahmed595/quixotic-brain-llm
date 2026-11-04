# Quixotic

This repo holds two products:

| Product | What it is | Where |
|---|---|---|
| **Quixotic AI** | The company knowledge assistant: API, portal, workers and database | `backend/`, `web/`, `workers/`, `migrations/`, `evaluation/`, `tests/`, `scripts/`, `deploy/`, plus the Docker and requirements files in this folder |
| **Quixotic Extension** | The Chrome side panel that drafts private replies for the chat an employee has open; it calls Quixotic AI and never sends anything | `quixotic-extension/` (see its `README.md`) |

Shared documents: `PRODUCT.md` (the PRD, split into `docs/product/`), `docs/`, `UI images/` and `CLAUDE.md`.

The old Discord bot, replaced by the extension, is kept for reference in `quixotic-extension/old-discord-bot/`.

## Tests

```bash
python -m pytest
```

```bash
npm --prefix quixotic-extension test
```
