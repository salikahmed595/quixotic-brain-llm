<!-- PRODUCT.md section 3 -->
# 3. User roles and boundaries

| Role | Allowed | Not allowed |
|---|---|---|
| Employee | Register, view own account status, create/search/delete own chats, ask questions, view answers/sources allowed for assigned scope, report missing information | See admin routes, other employees' chats, secret documents, pending drafts, API keys, edit approved policies |
| Department Manager / Knowledge Reviewer (optional subrole) | All employee actions plus review assigned department's proposed updates | Approve outside assigned authority; manage system secrets |
| Knowledge Admin | Curate documents, proposals, taxonomy, knowledge gaps; publish when granted publisher permission | Bypass platform-wide security controls |
| System Admin | Approve/reject/suspend users, assign departments/roles, manage access, indexing, configuration, logs, and integrations | Read unrelated private user chats by default; disclose plaintext API keys |
| Founder / CEO (leadership authority) | Submit policy proposals over verified Telegram/Discord identities and approve governed changes within specified approval matrix | Automatically override an existing policy solely based on a conflicting chat message |

The UI has two main layouts: Employee and Admin, matching the screenshots. Manager/reviewer/leadership permissions may add limited features inside the Admin layout when approved. Enforce permissions on the server for every API call and every document retrieval, not only by hiding sidebar links. Multi-department membership must be supported. Use deny-by-default access.
