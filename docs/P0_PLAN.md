# P0 plan (PRD §14 P0)
History: git log -p docs/P0_PLAN.md

Each milestone ships migration, OpenAPI, seed data, unit+integration+permission tests, `docs/PRD_GAPS.md` note (§16). ❓ = owner decision in PRD_GAPS §0.

## Status
| M | Scope | Status |
|---|---|---|
| M0 | Owner inputs | Open ❓: role mapping (§3), mail provider/sender (§5), API path style done as `/v1/chats` |
| M1 | Accounts, sessions, 5 states (§5) | done |
| M2 | Roles, departments, scopes, admin Users/Access requests/Departments (§3, §7) | done |
| M3 | Doc model, statuses, Git vault, Obsidian import, publication (§8) | done |
| M4 | Answers, citations, not-found text, knowledge gaps (§6, §9) | done |
| M5 | Chats + history (§6, §11) | done |
| M6 | React frontend, screenshot parity, AT-08 `npm run test:visual` (§4) | done; ❓ placeholders for other admin pages ("coming in Phase 2"); Web Search pill + mic disabled until P1 |
| M7 | Audit chain, Redis, Compose+Caddy, backups, load test, `docs/DEPLOYMENT.md` | done; AT-09 must run on real server |
| Obsidian contributors | `docs/DEPLOYMENT.md` §6 (§9); chat-bot channel removed by owner 2026-10-21 | done |

Decisions: OpenAI now, DeepSeek later (§10); one EC2 with Compose (§11); past-sales answers OFF (`QB_SALES_HISTORY_ENABLED=false`).
Exit: §16 DoD (a)–(i).
Out of P0: Add information, Approvals UI, Knowledge browser, Sales memory UI, Dashboard/Insights polish, Web Search, voice (P1); Discord (P2).
