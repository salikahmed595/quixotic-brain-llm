# Quixotic AI — Project Rules

## Rule 1 — PRD is the only source of truth (no guessing)
`PRODUCT.md` (split in `docs/product/NN-*.md`, start `docs/product/INDEX.md`) is the PRD. When building/changing anything:
1. **Follow the PRD exactly:** behaviour, names, states, roles, endpoints, fields, request/response shapes, pipelines, non-goals.
2. **Don't guess.** If the PRD is silent (algorithm, threshold, library, schema, default, route name, number): don't invent silently or hide behind a made-up default. Make it an explicit required config value or pluggable interface that fails loudly with a clear error when unconfigured, **and** record it in `docs/PRD_GAPS.md` (what's missing, PRD section, what code does meanwhile).
3. **Implementation necessities** (unavoidable but unnamed, e.g. password hashing, token signing, SQL driver) may be chosen, but list each in `docs/PRD_GAPS.md` under "Implementation necessities" for owner veto.
4. **Respect PRD §15 exclusions:** no model/SLM training, no autonomous creation of company rules, no employee access to unpublished docs, no open-ended Hermes filesystem/shell permissions, no reading every employee's private chat by default, no automatic customer data scraping, no mandatory n8n, no fake "Company Wide" access. Telegram/Discord/Hermes = Phase 2 (§9, §14), must not delay P0.
5. **Cite the PRD** in comments/docs (`# PRD §5 FR-AUTH-03`, `# PRD §13 AT-05`); never cite a section for behaviour it doesn't describe. Citations before 2026-10-17 refer to the superseded PRD in `docs/archive/PRODUCT_quixotic_brain_v0.md`; re-point when touching that code.
6. **Desktop visual truth = the two §4 screenshots** in `UI images/reference/` (admin `image(20261016-164021).png`, employee `image(20261016-164058).png`). Older mock-ups in `UI images/` superseded. Screenshot vs PRD text conflict: ask owner.
7. **Unsure: ask the owner.**

## Rule 2 — Hard product invariants
- Deny by default; permissions enforced server-side on every API call and retrieval, not by hiding links (§3).
- Department + confidentiality filters apply **before** vector/keyword retrieval and are rechecked before final answer/sources (§8, §10).
- Pending, Rejected, Suspended, Deactivated users get no chat, knowledge, admin API or indexed content; suspension revokes sessions (§5 FR-AUTH-03, FR-AUTH-05).
- Retrieval uses only approved, published, unexpired content; drafts never leak via embeddings, caches or errors (§8, §10).
- Never invent policies, permissions, prices, refunds, discounts or instructions; without approved evidence reply exactly "I couldn't find an approved answer in the company knowledge base." and offer Report missing information (§1, §6 FR-CHAT-04).
- No chat message, model output or sales history overrides approved policy; every knowledge change is reviewed, nothing auto-approved (§1, §3, §9, §15).
- Documents are data, not instructions (§8, §10).
- LLM configurable (DeepSeek or other) behind `generate_answer(context, question)`; no confidential data to a provider the company hasn't approved (§8, §10, §11).
- Users see only their own chats; admin analytics aggregate by default (§6 FR-CHAT-09).
- "Company Wide" never assigned by default (§4.2, §15).

## Backend quick reference
- Plan `docs/P0_PLAN.md`. Code `backend/`, `workers/`, `evaluation/`, `migrations/`. Docs `docs/backend.md`. **Every PRD gap and non-PRD choice goes in `docs/PRD_GAPS.md`** — update when adding one.
- Tests: `python -m pytest` (no DB/AWS needed). SQL only syntax-checked without real PostgreSQL + pgvector.
- Changed `PRODUCT.md`? Run `python docs/product/split.py` to refresh `docs/product/`.
