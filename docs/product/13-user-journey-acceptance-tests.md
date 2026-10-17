<!-- PRODUCT.md section 13 -->
# 13. User journey acceptance tests

- **AT-01 — Employee signup:** Register a new account → verify email → status Pending → blocked from all chat/company content → admin sees Access request → admin assigns Sales/Fresh Seller and approves → user can log in → sees only Employee screenshot-style navigation and permitted content.
- **AT-02 — Rejection/suspension:** Reject a pending account or suspend an active one → all protected endpoints deny access; previously issued sessions are revoked.
- **AT-03 — Authorized answer:** Sales employee asks for the approved fresh-seller handoff process → chatbot returns a concise answer with the correct company document citation and version/date.
- **AT-04 — Missing knowledge:** Employee asks about an undocumented discount → chatbot explicitly says no approved policy was found and offers to report the gap; no invented percentage.
- **AT-05 — Department isolation:** A Sales-only employee tries to request restricted HR/leadership documents through search, citations, prompt injection, direct API calls, or tampered dropdown values → no title, content, counts, or metadata leaks.
- **AT-06 — Admin document update:** Admin uploads and proposes revised policy → designated reviewer sees clear before/after diff and approves → new version becomes searchable; old version is recoverable.
- **AT-07 — Bot update:** Verified leadership voice note creates a proposal → unapproved change never appears in employee answers → approval publishes it and reindexes it → bot confirms version and document link.
- **AT-08 — UI parity:** Visual regression test at ~1470 × 900 against both supplied screenshots: correct sidebar/nav for each role, hero composition, chips, composer, colors, mascot, account card; no employee exposure of admin controls. Manually check responsive behavior and accessibility.
- **AT-09 — Reliability:** Run load tests for 160 logged-in employees, 40 simultaneous chat questions baseline, and 160-chat burst; verify latency/error targets and recovery on model/database outages.
