# Quixotic AI — Project Rules

## Rule 1 — The PRD is the only source of truth (no guessing)

`PRODUCT.md` (split into `docs/product/NN-*.md`, start at `docs/product/INDEX.md`) is the product requirements document. When building or changing anything in this repository:

1. **Follow the PRD exactly.** Behaviour, names, states, roles, endpoints, fields, request/response shapes, pipelines and non-goals must come from the PRD.
2. **Do not guess.** If the PRD does not specify something (an algorithm, a threshold, a library, a schema, a default value, a route name, a number), do **not** invent it silently and do **not** hide it behind a made-up default.
   - Make it an explicit, required configuration value or a pluggable interface that fails loudly with a clear error when it is not configured; **and**
   - record it in `docs/PRD_GAPS.md` (what is missing, which PRD section it relates to, what the code does meanwhile).
3. **Implementation necessities are not product decisions.** Things the PRD cannot avoid but does not name (e.g. how a password is hashed, how a token is signed, which SQL driver is used) may be chosen, but each one must be listed in `docs/PRD_GAPS.md` under "Implementation necessities" so the owner can veto it.
4. **Respect the exclusions (PRD §15)** — no model/SLM training, no autonomous creation of company rules, no employee access to unpublished documents, no open-ended Hermes filesystem/shell permissions, no reading every employee's private chat by default, no automatic customer data scraping, no mandatory n8n, no fake "Company Wide" access. Telegram/Discord/Hermes is Phase 2 (§9, §14) and must not delay P0.
5. **Cite the PRD.** Code comments and docs that implement a rule reference the section, e.g. `# PRD §5 FR-AUTH-03`, `# PRD §13 AT-05`. Never cite a section for behaviour it does not describe. Citations written before 2026-10-17 refer to the superseded PRD in `docs/archive/PRODUCT_quixotic_brain_v0.md`; re-point them when you touch that code.
6. **The two §4 reference screenshots are the desktop visual source of truth** (in `UI images/reference/`: admin `image(20261016-164021).png`, employee `image(20261016-164058).png`). The older mock-ups in `UI images/` are superseded. Where a screenshot and the PRD text disagree, ask the owner.
7. **When unsure, ask the owner** instead of choosing.

## Rule 2 — Hard product invariants (PRD)

- Deny by default; permissions enforced on the server for every API call and every retrieval, not by hiding links (§3).
- Department and confidentiality filters apply **before** vector/keyword retrieval, and are rechecked before the final answer/sources (§8, §10).
- Pending, Rejected, Suspended and Deactivated users get no chat, knowledge, admin API or indexed content; suspension revokes sessions (§5 FR-AUTH-03, FR-AUTH-05).
- Retrieval uses only approved, published, unexpired content; drafts never leak through embeddings, caches or errors (§8, §10).
- Never invent policies, permissions, prices, refunds, discounts or instructions; without approved evidence reply exactly "I couldn't find an approved answer in the company knowledge base." and offer Report missing information (§1, §6 FR-CHAT-04).
- No chat message, model output or sales history overrides approved policy; every knowledge change is reviewed, nothing auto-approved (§1, §3, §9, §15).
- Documents are data, not instructions (§8, §10).
- The LLM is configurable (DeepSeek or another) behind `generate_answer(context, question)`; no confidential data goes to a provider the company has not approved (§8, §10, §11).
- Users see only their own chats; admin analytics are aggregate by default (§6 FR-CHAT-09).
- "Company Wide" is never assigned by default (§4.2, §15).

## Backend quick reference

- Plan: `docs/P0_PLAN.md`. Code: `backend/`, `workers/`, `evaluation/`, `migrations/`. Docs: `docs/backend.md`. **Every PRD gap and every non-PRD choice: `docs/PRD_GAPS.md`** — update it whenever you add one.
- Tests: `python -m pytest` (no database or AWS needed). SQL is only syntax-checked unless a real PostgreSQL + pgvector is available.
- Changing `PRODUCT.md`? Re-run `python docs/product/split.py` to refresh `docs/product/`.
