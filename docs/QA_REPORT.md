# QA audit 2026-10-19
Live tests ran on `qa_copy` (clone of the dev DB) via `scripts/qa_up.py` (:8010). The live DB was not modified. Rollback tag: `qa-rollback-20261019`.

**Verdict: NOT FULLY VERIFIED.** The core RAG, security and UI checks pass. Two things still block it:
- Performance fails on a 4-core laptop. It must be re-run on the production-size server.
- The chat-bot channel (removed 2026-10-21), DeepSeek and n8n were not testable here.

| Area | Result | Evidence |
|---|---|---|
| Unit / integration / AT-08 visual | PASS | 131 unit tests passed (42 skipped, 2 xfail), 48 integration (2 xfail), 8 visual tests |
| Admin pages, employee chat (new `web/tests/flows.spec.ts`) | PASS | 13 admin pages, 0 browser errors; chat answers |
| Sign-in for Pending, Suspended, Rejected users | PASS | 403 |
| No sign-in, CSRF, employee calling admin API | PASS | 401/403 |
| Signed integration endpoints when not configured | PASS | 404. A bad signature returns 401 (unit test) |
| Secrets in the frontend bundle | PASS | 0 hits in 307 KB |
| RAG: relevant answer with citation | PASS | "11:00 PM to 7:00 AM", confidence high, source cited |
| RAG: missing policy | PASS | Exact §6 refusal text and the Report missing information action |
| Prompt injection | PASS | Refused |
| Department isolation (Sales user asks about Finance-only documents) | PASS | 0 Finance sources; the admin control test reaches them |
| Database outage, then recovery | PASS (with a risk) | Recovers. During the outage `/v1/health` hangs instead of failing fast |
| Worker on an idle Redis queue | **FIXED** | It crashed after 5 s (redis-py 8 read timeout). Fixed in f74df1c |
| Overload | **FIXED** | 60 concurrent searches froze the API for more than 10 min, sign-in included. Fixed in 5fcd652: `QB_MODEL_QUEUE_TIMEOUT_SECONDS` returns a 503 and the API stays healthy (0.2 s) |
| 160 users signed in at once | PASS | 160/160 in 8 s |
| Search p95 < 2 s with 60 concurrent; answer p95 < 8 s | **FAIL (hardware)** | Fails on the 4-core laptop. Search takes 0.25–4.7 s with no other load, and the CPU reranker is the limit. Re-run the AT-09 test on 16 or more vCPU |
| Obsidian push | NOT TESTED live | Needs the server. Covered by test_contributors and the hook tests |
| DeepSeek | NOT TESTED | No key (OpenAI gpt-5-nano is in use and works) |
| n8n | N/A | Not built. It is optional under PRD §15 |
| Production EC2 / HTTPS / backups | NOT TESTED | Not deployed yet. The restore drill was tested earlier |

Owner to decide:
- Set `QB_MODEL_QUEUE_TIMEOUT_SECONDS` (e.g. 10).
- Choose the server size after AT-09.
- Revoke the bot token that was pasted in chat (the bot integration was removed 2026-10-21; the token stays valid until revoked).
- The dev DB has 160 deactivated `load_*` accounts. Delete them?

## Answer accuracy 2026-10-20 (qa_copy, gpt-5-nano)
- 18/18 answerable questions correct (10 English, 5 Roman Urdu, 2 Urdu, 1 mixed); the reply language matched the question (§6 FR-CHAT-08). 4/4 unanswerable questions got the exact refusal.
- Single-user answer time was 6.6–17 s (target p95 < 8 s, §2). Most of that is the answer model.
- **FIXED:** the first questions after a start got 503 "busy". The overload limit counted model run time, not only queue wait.
- Translating client messages is NOT a feature (not in the PRD). Text unrelated to company knowledge gets the refusal. Awaiting the owner's decision.
