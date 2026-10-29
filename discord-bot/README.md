# Quixotic Discord Sales Copilot — Runnable MVP

**Version:** 0.1.0 (developer starter, not production-ready)  
**Date:** 2026-10-29  
**Purpose:** Employees can right-click a Discord customer's message and get a private, source-aware suggested reply using previously accessible, consented chat history. The bot does **not** auto-send messages to customers.

## What is actually built

- Native Discord **Apps → Draft Sales Reply** message context-menu action.
- `/link-client`, `/consent`, `/revoke`, `/suggest`, and `/forget-client` commands.
- Transparent customer opt-in before any ticket history is stored; customer can revoke and remove the bot's local records.
- Restricted to one configured server and explicitly permitted channels or their child threads; staff-role checks on employees.
- Discord historical message backfill in 100-message pages, resumable over large histories, plus automatic ingestion of subsequent eligible messages while the bot is online.
- Persistent local SQLite store, raw message provenance, source-linked extracted observations, and a draft audit log **without full draft bodies**.
- Keyword-based *query → historical conversational key → corresponding human reply value* retrieval, recent chat, relevant older mentions, source-linked customer observations, and language/style heuristics.
- Configurable OpenAI-compatible inference endpoint so you can use an approved cloud model or your existing Office SLM gateway.
- A private **draft only**, with a basic rule-based guard against obvious invented delivery/payment commitments; employee must inspect/edit/copy/send.
- Node built-in test runner, 16 tests (unit, mocked Discord history pagination, synthetic 1,000-prompt computation).

### What is *not* built or validated

This is **not a deploy-ready autonomous CRM**. It has not been connected to your real Discord server or Office SLM, and no real Discord API, LLM-provider integration, live end-to-end journey, penetration test, or concurrent-user load test has been run. SQLite is a single-host developer datastore, not the intended final multi-tenant production backend. The promise validator is a simple heuristic and can miss unsafe commitments. Full production scope is in `CLAUDE_CODE_IMPLEMENTATION_PROMPT.md`.

## Discord limitations — read before installation

1. **The bot cannot secretly read private DMs between an employee and a customer if it is not a participant.** It can't join group DMs. Use a private ticket/channel/thread that includes the customer, employee(s) and the bot; only messages in that accessible channel are available. The bot cannot read employees' other private conversations.
2. **Do not use a self-bot or employee user token.** Automating normal Discord user accounts violates Discord's rules.
3. `VIEW_CHANNEL`, `READ_MESSAGE_HISTORY`, `SEND_MESSAGES`, and `MESSAGE_CONTENT` are necessary for this MVP. The Message Content intent is privileged, must be enabled in the Developer Portal, and may require Discord review for apps at the relevant scale.
4. Discord returns message history up to 100 messages per API page. The bot paginates. Large histories may have partial coverage until subsequent requests complete the backfill. Deleted messages, inaccessible threads, old messages outside the bot's access, and attachments not included in this MVP cannot be reconstructed.
5. The bot should run in a **dedicated customer ticket** containing only the customer and authorized staff. Never use a shared sales channel containing unrelated customers' conversations.
6. Customers must be informed of the storage and AI-assisted use of their messages. In the MVP they opt in using `/consent`; `/revoke` deletes the locally stored ticket data. Ensure your privacy policy, retention, handling of model-provider data, and company notices are appropriate to your real deployment.

Source documentation: [Discord Application Commands](https://docs.discord.com/developers/docs/interactions/slash-commands), [Get Channel Messages](https://github.com/discord/discord-api-docs/blob/main/developers/resources/message.mdx), [Privileged Intents](https://support-dev.discord.com/hc/en-us/articles/6207308062871-What-are-Privileged-Intents), [Self-Bots Prohibited](https://support.discord.com/hc/en-us/articles/115002192352-Automated-User-Accounts-Self-Bots).

## Local setup

**Prerequisites:** Node.js 22 or newer, npm, a test Discord server where you have permission to install an app, a dedicated ticket channel (or thread), and an approved LLM API endpoint.

```bash
npm install
cp .env.example .env
# Edit .env and insert the Discord bot token, app ID, test guild ID,
# allowed ticket parent channel ID, staff role ID, and AI provider settings.
npm run register
npm test
npm start
```

For Windows PowerShell, copy `.env.example` to `.env` with `Copy-Item .env.example .env`.

**Create the Discord application:**

1. Open https://discord.com/developers/applications → New Application → Bot; obtain a bot token and keep it secret.
2. Enable **Message Content Intent** on the Bot page, subject to Discord access rules.
3. Install to your test server using Discord's official installation/OAuth2 flow. Use `bot` and `applications.commands` scopes; grant the minimum channel permissions mentioned above. Never use Administrator unless separately justified.
4. Create a `sales-tickets` channel where the bot has access. Restrict real ticket threads so each thread contains exactly one customer and approved staff.
5. Place your server ID in `DISCORD_GUILD_ID`, ticket channel (or parent channel) ID in `ALLOWED_CHANNEL_IDS`, and the approved employee role ID in `STAFF_ROLE_IDS`.
6. `npm run register` creates commands in the test server. `npm start` runs the bot.

**AI provider:** Set `AI_API_BASE_URL` to the root `/v1` path of a compatible chat-completions endpoint, `AI_MODEL` to your deployed model ID, and `AI_API_KEY` to a valid key. For a local Office SLM gateway, configure its authenticated OpenAI-compatible endpoint. Model support for `temperature` and `max_tokens` may vary; adapt `src/ai.js` to your provider's documented contract.

## Everyday workflow

1. Authorized employee opens a **dedicated customer ticket**, types `/link-client`, and selects the customer. The bot posts an opt-in notice in that ticket.
2. Customer types `/consent`. The bot indexes accessible historical messages from the ticket; future eligible messages are stored automatically, without repeatedly pasting full chat history.
3. When the customer asks a question, employee right-clicks **that customer message → Apps → Draft Sales Reply**. Or they run `/suggest` in the ticket to reply to the most recent customer message.
4. The bot retrieves relevant verified-ish (source-linked but rule-extracted) observations, recent messages, old topical excerpts, and old **unreviewed** conversation→response pairs.
5. The configured AI generates one brief reply in the customer's observed style, for the employee's eyes only. The employee must verify any commitment and **manually** send it.
6. Customer can `/revoke` to delete local memory. Server managers may use `/forget-client` (with confirmation) to delete a ticket.

### Example

Customer: `yo bro remember that purple Valorant banner idea? my budget is $70 rn. can we still do smth?`

The AI *might* draft: `yo bro yeah, we could keep that purple cyberpunk Valorant vibe and start with a clean static banner 👀 lemme confirm the exact scope and price with the team first.`

This is an **illustrative** draft, not a tested live output or a guaranteed sales strategy.

## How PERSONA-CHAT informs this design

Paper: Zhang et al., *Personalizing Dialogue Agents: I have a dog, do you have pets too?*, ACL 2018, https://aclanthology.org/P18-1205/.

- **Profile Memory analogy:** Store and retrieve customer-specific facts (game, platform, confirmed artwork preferences, current stated budget) with references to source messages.
- **Key-Value Memory analogy:** Key = earlier customer message/dialogue context; Value = subsequent human employee reply. Retrieve relevant pairs for the current query.
- **Generation analogy:** Let the Office SLM draft a new response using both memory classes. Then validate and present it for human review.

**Scientific precision:** This project uses a lightweight *lexical retrieval approximation*, NOT the paper's trained neural profile attention and key-value memory-network weights. Using the same conceptual dataflow is not reproducing the published results. Historical employee replies aren't assumed successful; future production versions should use a reviewed example library and actual outcome labels.

## Testing results

The following local commands were executed on the supplied project files:

- `npm test`: **16/16 test cases passed**. Includes token retrieval, conflicts, source scoping, response guards, a multi-page history mock, resumable cursor mock and 1,000 *synthetic prompt builds*.
- `node --check src/*.js`: all source modules passed syntax checks.

These tests **do not** validate your live Discord permissions, provider response format, bot's actual API round trips, safe storage at scale, customer privacy/retention compliance, human-reviewed replies, or concurrent performance. The synthetic 1,000-prompt test is **not a 1,000-concurrent-user load test**.

## MVP known limitations / before-production checklist

- Basic lexical retrieval does not handle paraphrases nearly as well as hybrid BM25 + vector retrieval + reranking; implement that in the existing Quixotic RAG service.
- Memory extraction supports limited explicit budget/art-style/game observations. It does not implement a full evidence-backed extraction model, order-scoped conflict resolution, revision histories or human verification. Source-linked `observed` ≠ confirmed.
- Currently one customer per ticket, one Discord server, and one SQLite writer. Build PostgreSQL + permission-aware tenancy for full CRM usage.
- Fetching old history while a request is pending can exceed Discord interaction deadlines in very large tickets; add a durable background backfill worker and queue before scale-up.
- Live message indexing depends on bot uptime. The on-demand sync catches up on many missed messages, but a large gap can remain partial and needs monitoring.
- Current simple regex validation is insufficient for discounts, conditional deals, inferred guarantees, translations, fabricated social proof, and subtle false commitments; authoritative CRM validators must be added.
- The MVP does not read or analyze image attachments, voice notes, deleted messages, third-party DMs, or private channels it cannot access.
- Add retention expiry policies and data deletion propagation before production. Current database persists until explicit deletion.
- Ensure former employee role changes invalidate any cached membership/authorization promptly; role-cache invalidation and cross-channel checks require hardening.
- Conduct a provider-data and Discord Developer Policy review before using real customer data. Do not use Discord conversation API data as a general-purpose monetized dataset without permission and applicable policy compliance.

## Deployment suggestion

Use this starter in a test Discord server first. For the actual Quixotic Creative product, integrate the **Discord bot gateway** with the existing Quixotic Client Brain APIs, Office SLM, CRM orders/payment status and company knowledge layer; do **not** run a parallel unsynchronized customer database long-term. Follow `CLAUDE_CODE_IMPLEMENTATION_PROMPT.md` as an end-to-end integration brief.
