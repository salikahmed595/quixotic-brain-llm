# Client Brain upgrade — gap analysis and slice plan

Source: owner-supplied `QUIXOTIC_CLIENT_BRAIN_UPGRADE_SPEC.md` v1.0 (2026-10-29), "the spec" below. Compared with the code on
2026-10-29 (commit 775b92d). Status words: **EXISTS**, **PARTIAL**, **MISSING**, **CONFLICT** (with PRD / CLAUDE.md, owner decision needed).

## 1. What the repository is today

Quixotic AI is a permission-aware RAG office assistant (FastAPI + PostgreSQL/pgvector + React). Employees ask questions,
paste client messages or screenshots, and get reply drafts which they copy and send themselves. There is **no CRM, no
client / order / payment records and no Discord bot or webhook** in this repository (Discord is PRD Phase 2, §14; Hermes and
Telegram were removed by the owner, CLAUDE.md Rule 1.4).

## 2. Spec vs code

| Spec item | Status | What exists / what is missing |
|---|---|---|
| §1.5 employee reviews every AI draft before sending | EXISTS | Nothing is sent automatically; the employee copies the `>>` message. No "approve and send" step or send audit (there is no send channel). |
| §1.4 / §10 documents and messages are data, prompt injection | EXISTS | Fenced `<knowledge>`, `<historical_cases>`, `<conversation>` blocks; tests in `tests/test_security_and_api.py`. |
| §2 P0 deterministic checks: prices, discounts | EXISTS | `_invented_money`, `_drop_term_offers` (payment plans, discounts, refunds) in `backend/retrieval/ask.py`. |
| §2 P0 deterministic checks: delivery promises, priority | PARTIAL | `_PROMISES` removes priority / rush / free mockups; a promised **date** ("by Friday", "tomorrow") is only forbidden in the prompt, not checked in code. |
| §6 structured output (reply, evidence IDs, unresolved facts, risk flags, blocked-promise reason) | MISSING | `/v1/ask` returns answer + sources + confidence; guards remove text silently, no risk flags. |
| §6 payment / order status claims | MISSING | No order or payment data exists, so any claimed status is unsupported; no code check. |
| §3 ClientMemory (typed, timestamped, sourced, superseded) | MISSING | Only per-chat history (~1000 words, `_history`). Nothing per client across chats. |
| §3 ConversationExample with real outcome | PARTIAL | `sales_memories` (customer message, agent response, outcome, quality_score, language, department-scoped). "(worked in past chats)" only with outcome `closed`. No review status or client link. |
| §3 Fresh Seller / Upseller routing on CRM events | MISSING / CONFLICT | No CRM or payment events to route on. Knowledge folders `Sales/Fresh-Seller`, `Sales/Upseller` exist (PRD §8). |
| §4 Discord/CRM ingestion, dedup, idempotency | MISSING / CONFLICT | Discord = PRD Phase 2; "no automatic customer data scraping" (PRD §15). |
| §5 client-scoped retrieval, filters before retrieval | PARTIAL | Department + confidentiality filters before retrieval and rechecked (PRD §8). No client scope (no clients). |
| §7 language, slang toggle, translation | EXISTS | English / Urdu / Roman Urdu detection, Slang Mode, Translate mode with direction check (V2). Spec adds: amounts, dates and negation preserved, checked in code — MISSING. |
| §8 artwork ideas from catalog (2D only) | PARTIAL | Task router + idea rules (V2). No product catalog or 2D-only scope check (a 3D request is not refused). |
| §9 employee handover summary | MISSING | Depends on client memory. |
| §10 evaluation benchmark | PARTIAL | `evaluation/quality_v2` (27 live cases, judge). Not built from anonymized history, no client/time split. |
| §11 load tests | PARTIAL | PRD §2 target 160/40 users; earlier load runs exist in docs. No k6/Locust script for the new flows. |

## 3. Owner decisions (2026-10-29)

1. **Client records: approved** ("begin with verified client memory, retrieval accuracy, and response validation").
   Visibility was not specified: default **department-wide** (everyone in the client's department, plus admins), owner-vetoable,
   recorded in docs/PRD_GAPS.md.
2. **Facts come from pasted chats, confirmed**: the AI suggests facts from client messages an employee pastes; a fact is saved
   only after the employee confirms it. Employees can also type facts.
3. **Sales routing: employee marks it** ("payment link requested", "paid"), logged with who and when.
4. **3D is also sold**: no 2D-only refusal (the spec's test 10 does not apply).

## 4. Slice plan (owner priority: client memory -> retrieval -> validation; one slice per turn, TDD)

| # | Slice | Size |
|---|---|---|
| S1 | **Client + ClientMemory store**: migration (clients, client_memories, client_memory_events), store with provenance, supersession ($300 -> $70 for the order, old value kept as superseded), department-scoped access, alias collision kept apart. Unit tests + SQL syntax check. | Medium |
| S2 | **API**: create / find client, list current facts, add / confirm / correct / delete a fact (server-side permission checks, audit). Integration tests. | Medium |
| S3 | **Capture from pasted chats**: AI suggests typed candidate facts with the exact source text; nothing saved until confirmed; no inferred income / class / personality. | Medium |
| S4 | **Client-scoped retrieval into answers**: Ask with a selected client adds its current confirmed facts (fenced as data) and its relevant past chat excerpts; never another client's. | Medium |
| S5 | **Promise validator in code**: delivery dates, availability, payment / order status in `>>` messages removed unless stated by the employee, a confirmed fact or approved knowledge; `risk_flags` in `/v1/ask`. | Small |
| S6 | UI: client picker in the composer, facts panel with confirm / correct, risk flags on the answer card. E2E test. | Medium |
| S7 | Translation fidelity check (amounts, dates, names, negation). | Small |
| S8 | Handover summary (source-linked, open commitments). | Medium |
| S9 | Fresh Seller -> Upseller marks with audit. | Small |
| S10 | Benchmark from anonymized `sales_memories` (client/time split) + load script for `/v1/ask`. | Medium |

Each slice report follows spec §14: Changed / Tests run / Risks / Performance / Next actions.
