# Quixotic Reply Assistant (Chrome extension)

Open a Discord chat on **discord.com** in Chrome, click **Draft reply** in the side panel, and get a private
Quixotic AI draft of the next staff message, written in the customer's tone and language. Copy it, check it,
and send it yourself. The extension never types into Discord, never sends, and stores no chat.

How it works: `reader.js` reads the messages on screen (no Discord token, no Discord API) → staff names typed in the
panel decide who is Staff, everyone else (not a bot) is the Customer → `lib/conversation.js` packs the recent chat into
one question → `POST /v1/ask` on `https://maqsad.quixoticcreatives.com` as the signed-in employee (their own
permissions) → `lib/guard.js` blocks invented delivery/payment promises → draft with **Copy**.
Owner decision 2026-10-29; not in the PRD. See `docs/PRD_GAPS.md` ("Discord reply extension").

## Install (developer mode)
```bash
npm run pack
```
1. Chrome → `chrome://extensions` → switch on **Developer mode** (top right).
2. **Load unpacked** → choose the `discord-extension/dist` folder.
3. Pin **Quixotic Reply Assistant** from the puzzle-piece menu.
4. Reload any open discord.com tab once.

After changing code: `npm run pack`, then press the reload ↻ icon on the extension card.

## Try it
1. Open a chat on discord.com, click the extension icon. The side panel opens.
2. Sign in with your own Quixotic AI username/email and password. Two-step (admin MFA) accounts are not supported yet.
3. Type the staff names exactly as Discord shows them, e.g. `Sara | Quixotic, Bilal`.
4. Click **Draft reply**, check the draft, **Copy**, paste into Discord, edit, send.

Only the chat Discord has loaded on screen is read; scroll up first to include older messages.

## Limits
- Discord web in Chrome/Edge only; not the Discord desktop app.
- Depends on Discord's page layout; when Discord changes it, fix `reader.js` (tests use a synthetic page sample).
- Discord's terms discourage client modifications; this only reads what you already see.

## Tests
`npm install` then `npm test` (Node 22+; jsdom is a test-only dependency).

## Developing: auto-update the copy loaded in Chrome

```
npm run dev -- C:\path\to\folder-loaded-in-chrome --watch
```

This copies the extension into that folder plus `dev-reload.js`. Click **Reload** on the extension card once; after that,
the open panel reloads itself when panel files change, and the whole extension reloads when the manifest, background or
content scripts change (then refresh the Discord tab). The employee download (`npm run pack`, the portal zip) never
includes `dev-reload.js`. Icons are drawn by `npm run icons`.
