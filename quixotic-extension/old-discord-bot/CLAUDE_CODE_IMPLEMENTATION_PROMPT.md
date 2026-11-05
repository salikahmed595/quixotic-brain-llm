# Quixotic Discord Sales Copilot — Claude Code Implementation Directive

**Date:** 2026-10-29  
**Project:** Quixotic Creative — Client Brain + Office SLM + Discord Sales Assistant  
**Status:** Architecture + code starter; production work requires reading, modifying and testing the actual Quixotic repository.  
**Scope:** 2D gamer/streamer artwork sales: characters, banners, static/animated emotes and streaming overlays. No 3D.

## Mission

Build an authorized, **human-in-the-loop Discord sales copilot** inside the existing Quixotic ecosystem. Staff should select a specific customer chat or right-click a customer message, and the AI should:

1. Fetch accessible history **without asking the employee to paste it again**.
2. Maintain a durable, customer-isolated, time-aware knowledge base of relevant messages and verified sales information.
3. Identify what the customer asks **right now** and combine their current request with relevant earlier statements.
4. Apply **PERSONA-CHAT-inspired profile memory** and **query → key → value conversation retrieval**.
5. Draft an authentic, non-robotic, customer-aligned reply that matches **their observable tone, language, interest, detail and slang level**; prefer direct relevance over artificial personalization.
6. When asked for an artwork idea or pitch, give a specific 2D concept tied to real preferences, game, streaming platform and previous artwork, rather than generic fluff.
7. Use observed objections, confirmed budget for the relevant order, prior design choices, revision requests, status and verified purchases to suggest **appropriate offers**, not invented urgency or guesses about psychological vulnerabilities.
8. Validate against current CRM/order/payment/pricing/scheduling policies, surface uncertainty, and deliver the suggestion **privately to an authorized employee**.
9. Require employee review/approval before any customer-facing message. Never spam, silently message, or claim a sale without event evidence.
10. Retain the full audit trail, knowledge provenance, customer corrections, consent/revocation state, and permission checks.

**Do not rebuild or break:** existing Quixotic CRM, Discord workflow, Office SLM, Quixotic Brain RAG, Fresh Seller/Upseller logic, knowledge governance, RBAC, or company branding. Integrate through existing APIs after inspecting the repository. The attached Node starter is a reference implementation, not an order to replace production infrastructure.

## Discord API reality and requirements

A normal Discord bot can read messages in authorized guild channels/threads where it has `View Channel`, `Read Message History`, and approved `Message Content` access. It **cannot** spy on a pre-existing DM between an employee and a customer, cannot join group DMs, and must not use employee tokens/self-bots. Message context-menu commands can open a one-click action on an existing message. Backfill historical messages in pages of up to 100; respect Discord's API rate limits and message-content access policies. Restrict to designated customer ticket threads with transparent customer notice and consent/appropriate legal basis. Source references are in `README.md`.

### User interaction

```text
Employee opens authorized Quixotic customer ticket
  → Discord message: right-click / Apps / Draft Sales Reply
  OR /suggest inside the linked ticket
  → backend checks guild, staff role, channel, client linkage, customer consent
  → historical messages are already indexed; fetch incremental missed events
  → query analysis (intent + latest customer message)
  → profile-memory retrieval + relevant old excerpts + approved Key/Value examples
  → business knowledge/pricing/order retrieval
  → Office SLM drafts reply matching observed customer style
  → structured policy/factual validator checks output
  → private employee preview, source links and flags
  → employee edits / sends manually
  → feedback event + approved memory update
```

Do not repost an entire chat to a model on every click. **Store all accessible authorized chat messages durably, retrieve a relevant context window, and disclose when older history is incomplete.** Long chats should use background ingestion rather than synchronous backfill in the interaction lifecycle.

## Memory architecture — adapt PERSONA-CHAT accurately

Paper: Zhang et al. (2018), *Personalizing Dialogue Agents: I have a dog, do you have pets too?*, https://aclanthology.org/P18-1205/.

### Layer A — Conversation timeline

Each message: guild ID, channel/thread ID, client UUID, Discord author ID, Discord message ID, ISO timestamp, text/authorized attachment descriptions, source link, deletion/edit state, origin. Use unique constraints and idempotent event processing; support edits and deletes; never cross customer/tenant boundaries. Restrict accessible staff authors.

### Layer B — Evidence-backed customer memory

- Verified preference: 'Customer explicitly prefers purple cyberpunk streamer art', with source message ID.
- Artwork ownership: link to verified Quixotic order (not just an AI guess).
- Relevant platform/game: Valorant, Twitch, Discord, YouTube where explicitly mentioned.
- Communication style: observed language, message length, slang level; descriptive and adjustable, never inferred immutable personality.
- Current project budget: `$70` if confirmed in the current thread; do not replace an entirely separate order's budget.
- Objections: pricing, quality, originality, revision limits, timing, payment trust, delivery, etc., source-backed.
- Sales state: Fresh Seller vs Upseller from actual CRM/payment events and existing handoff rules.
- Commitments: only when actually made by staff and verified; support due date, owner and completion status.

For every memory store category, value, confidence/status, who said it, source ID, observed time, valid time, order scope, supersession link and access scope. When older `$300` conflicts with newer `$70`, keep the older claim as historical evidence but use the newer value **for the applicable order**.

Do **not** invent income tier, social class, MBTI type, emotional vulnerability, psychological profile, private attributes, or purchasing capacity from a customer's text. Do not equate a user's enthusiasm with willingness to pay. Any spending signals should be sourced to actual purchases, explicit budget statements or customer-requested options.

### Layer C — Key-Value reply memory

`Query`: latest request plus short recent context and current intent.  
`Key`: historical customer utterance/dialogue window similar to today's situation.  
`Value`: the human reply or approved sales response following that situation.  
`Metadata`: customer/order scope, language, channel, artwork type, verified outcome (when available), recency, quality review, policy version, employee ID, source IDs.

Extract conversation-response pairs with correct role/speaker alignment. Do not assume the immediately next message always belongs to the seller or is an actual answer; use threaded sequencing, reply references, timestamps, and speaker tags. Do not conflate the paper's learned neural KV memory network with a modern RAG implementation: this engineering plan **adapts the concept**, using BM25/vector retrieval + reranker + LLM generation; it does not reproduce the original trained weights or performance.

Retrieve, in this order: (1) verified client/order facts; (2) exact latest message and recent chronological context; (3) semantically relevant older excerpts; (4) **quality-reviewed** historical conversations; (5) current authorized product/pricing/delivery policies. Filter by customer/tenant permissions before retrieval. Add a source link for material personalization.

### Layer D — Generative drafting

Use the existing Office SLM via authenticated backend gateway. Make generation a constrained process:

- Customer's latest intent **first**; don't dump memory into the reply.
- Observed customer style: match English/Roman Urdu/Urdu, casual vs formal, typical length, sparing gamer slang/emojis; never imitate unrelated identity claims or over-personalize.
- Friendly, specific, low-friction replies rather than generic messages such as 'we offer premium quality art'.
- For gamer artwork idea requests, explain focal subject, composition, design motif, color scheme, streamer identity and how personalization ties to their interest. For direct replies, keep to 1–3 concise Discord sentences.
- No false guarantees of deadlines, verified budget approvals, prices, discounts, refund outcomes, payment receipt or availability. If unknown, propose checking.
- No manipulative artificial scarcity or fear. Support informed customer choices, not pressure tactics.
- Enforce the official **current policy** and source facts as authoritative; historical sales examples are untrusted.
- Prevent prompt injection by isolating data from instructions and validating any command/action outside the model.
- When unable to support a key fact, state exactly what must be confirmed.

### Proposed generation output schema

```json
{
  "draft": "yo bro, we could keep that purple cyberpunk look for your banner 👀 lemme check the exact scope and delivery timing with the artist first",
  "evidence_ids": ["discord-message-id"],
  "intent": "budget_objection_and_delivery_question",
  "tone": "short_casual_english",
  "artwork_idea": null,
  "unknowns": ["approved_price", "delivery_schedule"],
  "verification_flags": ["needs_employee_price_check", "needs_delivery_check"],
  "reason": "Customer explicitly prefers purple cyberpunk artwork and asked for feasibility at their stated budget."
}
```

This schema is a **production target**. The attached runnable MVP currently outputs only `{draft, why}` and a simple heuristic validator.

## Sales workflow behavior

**Fresh Seller:** qualify artwork needs, give concepts, handle objections, present authorized options, respect the existing payment-link handoff trigger.  
**Upseller:** use verified historical purchases and relationship continuity; suggest genuinely complementary upgrades only when relevant.  
**Returning customer:** keep their verified art history and style in view; route to existing Upseller rules.  
**Negative outcomes:** allow annoyed/ghosted/blocked/seen outcomes; never force a positive sale or misclassify ghosting as conversion.

### Pitch format when appropriate

```
1. Acknowledge exactly what the customer just said (do not restate everything).
2. Use 1–2 real customer-specific details from source-linked memory.
3. Offer one interesting concrete art direction/value relevant to their game or streaming brand.
4. If a genuine objection exists, address it without fabricated assurances.
5. Finish with one small relevant question or next action, not a pushy CTA.
```

**Example input:**

```
Customer: yo bruh that purple valorant emote set was sick. i need a banner but $70 is all i can do rn
Verified order: one purple Valorant emote set purchased
Verified current stated budget: $70 for this banner
Unknown: current price catalog / scope / artist availability
```

**Example draft:**

```
yo bro, imagine your Valorant tag in that same purple neon style as your emotes, with a slick cyberpunk backdrop 👀 would make the channel look super consistent. lemme check what banner scope we can do around your $70 budget.
```

**Anti-example:**

```
Bro this is your only chance, premium delivery is guaranteed tomorrow, and I know you can afford $250.
```

## Architecture to implement in the current repo

```text
Discord Bot (Gateway + application commands)
   └── Auth / roles / channel+customer binding / consent
           └── Async message ingestion + incremental history sync
                   └── Durable queue (e.g. Redis Streams / managed jobs)
                           └── PostgreSQL (messages, customer memory, linkage, audits)
                           └── pgvector / existing Quixotic hybrid RAG index
                           └── Quixotic CRM (orders, payments, pricing, commitments)
                                   └── Retrieval + latest-intent extraction
                                           └── Key/Value example reranking
                                           └── Office SLM / secured LLM gateway
                                           └── Schema validation + deterministic policy engine
                                                   └── Private employee draft + evidence
                                                           └── Human review / feedback / CRM update
```

Suggested API boundaries (adapt to actual existing routes):

- `POST /internal/discord/events` — signed/authorized webhook or service-to-service event.
- `POST /internal/client-brain/{clientId}/sync-history` — queue resumable history ingestion.
- `POST /internal/client-brain/{clientId}/suggest-reply` — authorized request, returns structured draft with evidence.
- `GET /internal/client-brain/{clientId}/memories` — scoped facts with timestamps/correction status.
- `POST /internal/client-brain/{clientId}/feedback` — approved/rejected/edit events.
- `POST /internal/client-brain/{clientId}/handover` — source-backed handover notes.
- `DELETE /internal/client-brain/{clientId}/discord-scope` — revoke consent and propagate deletion.

Production auth: service credentials, minimal scopes, guild ID + ticket channel ID + customer ID + staff RBAC checks on **every request**; deny by default. Scope RAG retrieval by tenant and authorized client **before** searching the index; never trust a client ID supplied by a browser without authorization. Do not share one customer's memory with another customer.

## UI requirements

- Preserve Quixotic white / orange / black theme in the existing Client Brain / CRM.
- **Discord**: Message context-menu action, plus `/suggest`; ephemeral response visible only to employee, with source links, confidence/unknowns, and editable text (where supported by client UI).
- **CRM Client Brain**: Current active order, purchased art, verified interests, message-backed memory timeline, current objections, conversation examples, human-approved suggestions, and correction controls.
- **Answer With AI**: Three options `Quick reply`, `Artwork idea`, `Sales pitch`. These must be task modes, not separate data silos.
- **Style**: `Match customer`, `Short casual`, `Friendly`, `Professional`, `Roman Urdu`, `English`, with explicit employee override.
- **Employee Handover**: One-click summary: last need, commitments, due dates, paid orders, previous designs, next step, source citations.
- **Audit**: who requested the draft, input version, model/parameter version, rule status, whether sent manually, feedback, policy/source IDs; minimize full text logging of sensitive content.

## Mandatory TDD + verification workflow

For each feature slice: (1) define acceptance criteria, (2) write failing tests, (3) implement minimal code, (4) run tests, (5) integration-test with mock Discord/CRM/SLM, (6) conduct user journey E2E, (7) review permissions and privacy, (8) profile performance and load, (9) report only observed results and remaining failures.

**Required unit and integration tests:**

- Message ID idempotency; edits/deletes; pagination, restarts, API rate limits, large backfill continuation and gap detection.
- Bot channel access, staff role changes, customer consent/revocation, one-customer-per-ticket enforcement, tenant/client isolation and attempts to access other customer threads.
- Old budget `$300` vs current order budget `$70`; old but relevant art interests remain retrievable; order scopes never cross.
- Profile memory selection; query→key→value ranking; cases with weak/no matches; historical promises are never treated as company policy.
- Role-aware conversation pair extraction; staff/customer turns; threads; multi-message responses.
- Customer language/style: slang, short vs long, English/Urdu/Roman Urdu, request intent first, no weird forced greetings.
- Product ideas tied to confirmed client preferences; avoid generic output; no fake production abilities.
- Critical-policy blocker tests for invented timelines, payment confirmation, refunds, discounts, prices, delivery promises, unsolicited messages, pressure tactics.
- Prompt-injection attempts in Discord messages and retrieved examples; quote-like instructions; exfiltration attempts; cross-client leakage.
- Fresh Seller → payment-link handoff; Upseller returning-customer rules; employee departure handover accuracy.
- Regression evaluation against annotated, *held-out* historical conversations, including negative outcomes; avoid splitting the same customer's conversations between training and test.
- Synthetic load for 1k+ concurrent sessions, not just sequential prompt-building; measure p50/p95, errors, queue delay, DB contention, Discord limits, token cost, model throttling, recovery.

**Proposed gated acceptance values, not claims of existing performance:**

| Category | Initial acceptance target |
|---|---|
| Unauthorized customer-memory access | Zero in access-control test suite |
| Message ingestion correctness | 100% of accessible, consented messages in test fixtures; explicit partial-coverage status |
| Unsupported hard promises | Zero in critical test scenarios; fail closed |
| Relevant memory recall | ≥95% on labeled cases, stratified by conversation type |
| Human relevance/naturalness | ≥4/5 on blinded evaluation |
| Sales workflow routing | ≥99% against verified events |
| Translation meaning preservation | ≥95% on reviewed EN/UR/Roman UR test cases |
| Employee source verification | Evidence links for each asserted material memory |
| Business uplift | Demonstrate through consented, controlled pilot with statistical uncertainty; do not assume |
| Performance | Agree p95 SLO and per-message cost before rollout; measure with actual infrastructure |

## Implementation order

### Slice 0 — Audit and baseline

Inspect current repos and actual Discord/CRM/Office SLM code. Identify existing APIs, queues, RBAC, data models, dashboards, model endpoints, pricing/catalog sources and deployment constraints. Produce a **gap analysis** rather than replacing everything with greenfield code. Obtain authorization and customer data/consent requirements.

### Slice 1 — Bot binding, permission checks and privacy

Deliver a guild-only prototype with an approved ticket parent, one customer/ticket, transparent opt-in, history backfill, `/revoke`, `/forget-client`, message context-menu invocation, and data isolation tests.

### Slice 2 — Durable memory and retrieval

Event ingestion, source IDs, edits/deletes, order-scoped profile facts and conflict resolution, keyword+semantic retrieval, reranker, key/value conversation pairs, verified outcome labels, and missing-context warnings.

### Slice 3 — Customer-style drafting and safeguards

Real Office SLM integration, style controller, artwork idea mode, business-rule validator, employee preview, feedback collection, and review logging.

### Slice 4 — CRM continuity and employee handover

Order/payments, Fresh Seller/Upseller, verified product offers, outstanding customer promises, and human-reviewable handover summaries.

### Slice 5 — Evaluation, security, scaling, pilot

Offline held-out tests, source-grounding metrics, security/prompt injection review, Discord provider acceptance tests, thousands-of-users *concurrent* load test, human review, then cautious monitored rollout with rollback.

## Required reporting format from Claude Code

At the end of each vertical slice, report only:

1. Files changed and behavioral change.
2. Tests actually executed, with passed/failed/skipped counts and reproduction commands.
3. Known gaps, risks and observed latency/cost.
4. Evidence from complete user journeys and permission checks.
5. Exactly what should be improved next and whether it is safe for staged deployment.

**Never say 'complete', 'perfect', 'tested', 'secure' or 'ready for production' without evidence. If dependencies, Discord credentials or staging infrastructure are missing, leave explicit TODOs and say which tests were not run.**

## First action to take

Read `README.md` and the existing Quixotic PRD, inspect the current repository, then execute the existing test suites. Report a gap analysis and implement **Slice 1** with tests before proceeding. Preserve existing CRM/SLM functionality throughout.
