# Quixotic AI — Product Spec Index

`PRODUCT.md` (~6,997 tokens) is split into 16 section files in `docs/product/` (largest ~1155 tokens). Read this index, then open only the file(s) you need. Token counts are estimates (~4 chars/token).

## Quick lookup

| If you need… | Open |
|---|---|
| Vision, goals, targets | 01, 02 |
| Roles & permissions | 03, 10 |
| UI (screenshots, sidebars, responsive) | 04 |
| Signup, approval, login, account states | 05 |
| Chat behaviour, not-found text, Web Search | 06 |
| Admin pages | 07 |
| Documents, versions, retrieval pipeline | 08 |
| Telegram/Discord/Hermes, knowledge gaps | 09 |
| Stack & API contract | 11 |
| Data entities | 12 |
| Acceptance tests, phases, exclusions, done | 13–16 |

## Vision, goals & roles

| # | Section | File | ~Tok | Covers |
|---|---|---|---|---|
| 1 | Product vision | [01-product-vision.md](01-product-vision.md) | 194 | Permission-aware RAG assistant; never invent policies/prices/refunds; missing evidence -> knowledge-gap request |
| 2 | Business goals and success criteria | [02-business-goals-and-success-criteria.md](02-business-goals-and-success-criteria.md) | 309 | Six goals; targets: p95 chat < 8s, retrieval < 2s, >=95% cited, 0 cross-dept leaks, reindex < 60s, 160/40 load |
| 3 | User roles and boundaries | [03-user-roles-and-boundaries.md](03-user-roles-and-boundaries.md) | 391 | Employee, Dept Manager/Reviewer, Knowledge Admin, System Admin, Founder/CEO; server-side deny-by-default |

## UI

| # | Section | File | ~Tok | Covers |
|---|---|---|---|---|
| 4 | Reference UI — preserve the supplied screenshots | [04-reference-ui-preserve-the-supplied-screenshots.md](04-reference-ui-preserve-the-supplied-screenshots.md) | 1155 | Screenshot-exact UI: shared hero/composer/cards, employee vs admin sidebar order, responsive rules |

## Auth & chat

| # | Section | File | ~Tok | Covers |
|---|---|---|---|---|
| 5 | Registration, login, and admin approval | [05-registration-login-and-admin-approval.md](05-registration-login-and-admin-approval.md) | 466 | FR-AUTH-01..07: signup, email verification, Pending, admin approval, account states, Argon2id/sessions/MFA |
| 6 | Employee chatbot requirements | [06-employee-chatbot-requirements.md](06-employee-chatbot-requirements.md) | 554 | FR-CHAT-01..09: chats, voice, suggestion cards, Company Knowledge default, not-found text, Web Search, scopes |

## Admin & knowledge

| # | Section | File | ~Tok | Covers |
|---|---|---|---|---|
| 7 | Admin pages and requirements | [07-admin-pages-and-requirements.md](07-admin-pages-and-requirements.md) | 591 | Admin page table: Knowledge ... System minimum functionality |
| 8 | Knowledge structure and retrieval | [08-knowledge-structure-and-retrieval.md](08-knowledge-structure-and-retrieval.md) | 478 | Obsidian Markdown vault, document fields/statuses, ACL-first hybrid retrieval, DeepSeek, atomic publication |
| 9 | Hermes, Telegram, and Discord knowledge ingestion (Phase 2) | [09-hermes-telegram-and-discord-knowledge-ingestion-phase-2.md](09-hermes-telegram-and-discord-knowledge-ingestion-phase-2.md) | 462 | Phase 2: Hermes Telegram/Discord proposals, voice notes, diffs, approval, reindex; knowledge-gap loop |

## Security & architecture

| # | Section | File | ~Tok | Covers |
|---|---|---|---|---|
| 10 | Information security, privacy, and governance | [10-information-security-privacy-and-governance.md](10-information-security-privacy-and-governance.md) | 395 | RBAC + ABAC before retrieval, secrets server-side, audit, upload protection, provider approval, retention |
| 11 | Proposed technical architecture | [11-proposed-technical-architecture.md](11-proposed-technical-architecture.md) | 527 | React+TS+Tailwind, FastAPI, Postgres/pgvector, Redis worker, Docker; minimum API contract |
| 12 | Core data entities | [12-core-data-entities.md](12-core-data-entities.md) | 153 | Core data entities list; last indexed version + checksum; idempotent bot events |

## Acceptance, phases & done

| # | Section | File | ~Tok | Covers |
|---|---|---|---|---|
| 13 | User journey acceptance tests | [13-user-journey-acceptance-tests.md](13-user-journey-acceptance-tests.md) | 509 | AT-01..AT-09 acceptance journeys |
| 14 | Delivery phases and priorities | [14-delivery-phases-and-priorities.md](14-delivery-phases-and-priorities.md) | 253 | P0 Phase 1 ... P3 Later |
| 15 | Exclusions for v1 | [15-exclusions-for-v1.md](15-exclusions-for-v1.md) | 94 | Exclusions for v1 |
| 16 | Definition of done | [16-definition-of-done.md](16-definition-of-done.md) | 283 | Definition of done; implementation direction to Claude Code |

## Conventions

- Every file is self-contained and starts with a comment naming its section number.
- Cross-references use section numbers; jump to `NN-*.md`.
- Source of truth is `PRODUCT.md`; edit it, then re-run `python docs/product/split.py`.
