# Quixotic Discord Sales Copilot (thin client)

Staff right-click a customer's message in an approved ticket channel and get a **private reply draft from Quixotic AI**.
The bot never sends anything to the customer; the employee reviews, edits and sends by hand.

Owner decision 2026-10-29: the bot is a thin client of Quixotic AI. It has **no database, no LLM of its own, no history
backfill and no consent/link commands**. Permissions, department filters and the approved-evidence rule stay in
Quixotic AI (`POST /v1/ask` with `X-API-Key` + the employee's `user_id`). The sales-copilot use is not in the PRD
(§9 describes Discord only for leadership knowledge proposals); see `docs/PRD_GAPS.md`.
`CLAUDE_CODE_IMPLEMENTATION_PROMPT.md` is the original starter brief, kept for reference only and superseded here.

## Commands
- **Apps → Draft Sales Reply** (message context menu): drafts a reply to the right-clicked customer message.
- **/suggest**: drafts a reply to the latest customer message among the channel's last 50 messages.

Both only work in `ALLOWED_CHANNEL_IDS` (or their threads) in `DISCORD_GUILD_ID`, for members with a `STAFF_ROLE_IDS`
role (or Manage Server). A Discord account missing from `STAFF_USER_MAP` is refused, never run as the key's owner.
Drafts promising delivery/deadlines or claiming payment status are blocked (`src/guard.js`); `@everyone`/`@here` are stripped.

## Setup
Node.js 22+. Copy `.env.example` to `.env` (never commit it) and fill in the Discord IDs, the Quixotic AI URL,
an API key with the `ask` permission, and the staff map. In the Discord Developer Portal enable the
**Message Content** intent; install with `bot` + `applications.commands` scopes and View Channel / Read Message History.

```bash
npm install
npm test
npm run register
npm start
```

`npm test` needs no `npm install` (tests use only Node built-ins).
