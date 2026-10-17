<!-- PRODUCT.md section 2 -->
# 2. Business goals and success criteria

1. Onboard and manage 160 employee accounts, with no employee able to log into company knowledge before admin approval.
2. Reduce time spent asking supervisors routine policy and script questions.
3. Provide source-linked, department-permitted answers from approved documents.
4. Let authorized admins maintain the knowledge library without code changes.
5. Detect unanswered questions and route them to knowledge owners.
6. Preserve approved knowledge changes, accountability, and rollback.

**Initial measurable targets** (validate during pilot): p95 chat response under 8 seconds for ordinary text queries (excluding external web search); p95 knowledge retrieval under 2 seconds; ≥95% of answers in the acceptance test cite an authorized document or explicitly state that no verified answer was found; 100% of pending users denied protected access; 0 unauthorized cross-department retrievals in the permission test suite; full reindex of a changed document visible to search within 60 seconds under normal load. Test 160 concurrent logged-in sessions and a 40-concurrent-chat baseline; load-test a 160-concurrent-chat burst before expansion. These are targets, not existing performance claims.
