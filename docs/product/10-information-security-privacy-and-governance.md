<!-- PRODUCT.md section 10 -->
# 10. Information security, privacy, and governance

- Server-side RBAC plus document-level ABAC/ACL. Department and confidentiality filters apply before vector/keyword retrieval, not merely after generation.
- All secrets remain server-side (environment/secret manager); never in frontend bundles, Markdown, chat history, or screenshots.
- TLS everywhere; encryption at rest for sensitive data/backups; least-privilege database credentials; separate internal admin tools and employee public interfaces.
- Record account approvals, document changes, access-scope changes, publishing, administrative exports, and privileged bot actions in tamper-resistant audit logs.
- Published vs draft indexes are separate or strongly status-filtered; privileged drafts must not leak through shared embeddings, summaries, caches, or error messages.
- Protect upload paths: type validation, malware scanning where feasible, upload size limits, sandboxed text extraction, prompt-injection resistance, and document review.
- Apply request and token quotas, rate limits, monitoring, and abuse defenses against account enumeration, prompt injection, exfiltration, and denial of service.
- Do not upload confidential data to DeepSeek or any third-party model until the company approves the provider, retention settings, and data-handling terms. Support a configurable provider or private deployment later.
- Define chat/audio/document retention periods with company leadership before launch; minimize customer personal information in Sales memory. Support correction/deletion policies and access logs.
