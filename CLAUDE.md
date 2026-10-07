# Quixotic Brain — Project Rules

## Rule 1 — The PRD is the only source of truth (no guessing)

`PRODUCT.md` (split into `docs/product/NN-*.md`, start at `docs/product/INDEX.md`) is the product requirements document. When building or changing anything in this repository:

1. **Follow the PRD exactly.** Behaviour, names, states, roles, endpoints, fields, request/response shapes, pipelines and non-goals must come from the PRD.
2. **Do not guess.** If the PRD does not specify something (an algorithm, a threshold, a library, a schema, a default value, a route name, a number), do **not** invent it silently and do **not** hide it behind a made-up default.
   - Make it an explicit, required configuration value or a pluggable interface that fails loudly with a clear error when it is not configured; **and**
   - record it in `docs/PRD_GAPS.md` (what is missing, which PRD section it relates to, what the code does meanwhile).
3. **Implementation necessities are not product decisions.** Things the PRD cannot avoid but does not name (e.g. how a password is hashed, how a token is signed, which SQL driver is used) may be chosen, but each one must be listed in `docs/PRD_GAPS.md` under "Implementation necessities" so the owner can veto it.
4. **Respect the non-goals (PRD §5)** — no Kubernetes, multi-agent systems, GraphRAG, knowledge graphs, autonomous data changes, auto fine-tuning, GPU clusters, workflow automation, auto-approval, autonomous policy decisions, or employee surveillance.
5. **Cite the PRD.** Code comments and docs that implement a rule reference the section, e.g. `# PRD §20`. Never cite a section for behaviour it does not describe.
6. **UI images are not the PRD.** The mock-ups in `UI images/` guide the front-end only; where they disagree with `PRODUCT.md`, the PRD wins (e.g. the PRD says "Knowledge Base", `Add Information`, integer versions in metadata).
7. **When unsure, ask the owner** instead of choosing.

## Rule 2 — Hard product invariants (PRD)

- Permissions are applied **before** retrieval (§42, §11.3).
- Default retrieval filters `status = active`; archived knowledge never influences current answers unless explicitly requested (§15).
- Historical sales data **never overrides** current company policy (§20).
- Answer only from retrieved Quixotic knowledge; if evidence is insufficient say it could not be found (§29, §32).
- Documents are data, not instructions (§52).
- Embedding model, reranker, vector DB and LLM provider stay behind interfaces (`embed(text)`, `generate_answer(context, question)`) (§24, §28).
- Keep the original user query for audit alongside the normalized one (§23).
- Frontend shows High / Medium / Low confidence, not raw scores (§31).
- All employee submissions require review (§9.2); nothing is auto-approved (§5).

## Backend quick reference

- Code: `backend/`, `workers/`, `evaluation/`, `migrations/`. Docs: `docs/backend.md`. **Every PRD gap and every non-PRD choice: `docs/PRD_GAPS.md`** — update it whenever you add one.
- Tests: `python -m pytest` (no database or AWS needed). SQL is only syntax-checked unless a real PostgreSQL + pgvector is available.
- Changing `PRODUCT.md`? Re-run `python docs/product/split.py` to refresh `docs/product/`.
