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

## 3. Decisions the owner must take (PRD is silent or conflicts)

1. **Client records.** Client memory needs a new "client" entity (name / Discord handle, owner, department). The PRD has no
   such entity (§12). Approve adding it? Who may see a client's memory: the whole department, or the assigned employee + managers?
2. **Where client facts come from.** Without a Discord bot or CRM (Phase 2 / §15 "no automatic scraping"), memories can only
   come from what an employee pastes or types in chat. OK to extract candidate memories from pasted client messages, saved
   only after the employee confirms them?
3. **Fresh Seller / Upseller routing.** Needs payment / order events. Is there an external CRM to connect (which one, API?),
   or should the employee mark "payment link requested" / "paid" by hand?
4. **2D-only scope (§11 test 10).** Confirm the studio sells only 2D (characters, banners, overlays, static / animated
   emotes) and that a 3D request should be declined politely.

## 4. Slice plan (small vertical slices, TDD, one per session turn)

Slices that need no new PRD scope go first.

| # | Slice | Needs owner decision | Size |
|---|---|---|---|
| S1 | **Promise validator in code**: delivery dates ("tomorrow", "by Friday", "in 2 days"), availability, payment / order status claims in `>>` client messages are removed or rewritten to "I'll confirm with the team", unless the employee or approved knowledge stated them. Returns `risk_flags` in `/v1/ask`. Spec §6 example + test "delivery tomorrow but schedule unknown". | No | Small |
| S2 | **Risk flags in the UI**: the answer card shows what was blocked and why ("delivery date removed: not confirmed"). | No | Small |
| S3 | **2D-only scope** rule + test (3D request declined, 2D alternative offered). | Decision 4 | Small |
| S4 | **Translation fidelity check**: amounts, dates, names and negation in the source must appear in the translation; retry once, else flag. | No | Small |
| S5 | **Client entity + ClientMemory schema** (migration, events, supersession, provenance) + unit tests ($300 → $70, alias collision). | Decisions 1–2 | Medium |
| S6 | Memory capture from pasted messages with employee confirmation; client-scoped retrieval into the answer. | Decisions 1–2 | Medium |
| S7 | Handover summary (source-linked, open commitments). | After S5–S6 | Medium |
| S8 | Sales routing (Fresh Seller → Upseller) on recorded events. | Decision 3 | Medium |
| S9 | Benchmark from anonymized `sales_memories`, client/time split; load script for `/v1/ask`. | No | Medium |

Each slice report follows spec §14: Changed / Tests run / Risks / Performance / Next actions.
