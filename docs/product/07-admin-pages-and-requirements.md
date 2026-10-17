<!-- PRODUCT.md section 7 -->
# 7. Admin pages and requirements

| Navigation item | Minimum functionality |
|---|---|
| Knowledge | Search/browse approved knowledge, department and category filters, source status, effective date, citations, versions; inspect knowledge gaps |
| Add information | Enter text or upload a document, select department/category/sensitivity, provide source and owner, preview parsed content, submit for validation and approval |
| Documents | Upload PDF, DOCX, TXT, MD; detect file type/size, extract text, review parse, classify permissions, approve, version, archive, reindex; reject unreadable files |
| Sales memory | Approved sales playbooks, objection examples, handoff rules, FAQ and lessons; no unrestricted import of identifiable customer conversation transcripts |
| Approvals | Queue for document changes/policy updates with diffs, references, conflicts, submitter, reviewer, approve/reject/request changes; prevent self-approval where policy requires separation |
| Access requests | Pending employee signup and access-scope changes; approve/reject, assign role/department, reason, timestamps |
| Dashboard | Approved users (target 160), pending accounts, active chats, answer volume, knowledge health, index status, unresolved gaps, queue counts |
| Insights | Top questions, zero-result queries, feedback, department usage, document coverage, response latency; aggregated/permission-aware reporting |
| Users | Search/add/invite/edit/suspend/deactivate users; roles, departments, last login, state, audit history; bulk import optionally |
| Departments | Create/edit/disable departments; assign members, reviewers, visibility rules and document owners |
| Vocabulary | Manage approved industry phrases/acronyms, customer objection terminology, aliases and synonyms for retrieval and presentation |
| API keys | Configure providers via server-side secret references; mask keys, rotate/revoke, scoped access; never return plaintext secrets to frontend |
| System | Model selection, RAG tuning, embeddings, indexing jobs, integration health, backup/restore, incident controls, audit/export, Web Search toggles |

Admin pages must share the screenshot's sidebar, cream canvas, white cards, orange accents, rounded corners, and low-density layout. Data tables/forms are allowed inside the main content; do not insert admin controls into the employee homepage.
