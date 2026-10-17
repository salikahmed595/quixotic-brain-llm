<!-- PRODUCT.md section 11 -->
# 11. Proposed technical architecture

- **Frontend:** React + TypeScript (Next.js or Vite, based on existing repo) and Tailwind CSS. Preserve the existing screenshot-based UI; don't replace it with a generic dashboard kit.
- **API/backend:** Python FastAPI (or existing Node backend if already reliable), REST APIs, documented OpenAPI contract.
- **Auth/data:** PostgreSQL, secure sessions and an established auth library/provider; explicit account approval records.
- **RAG:** Postgres full-text + pgvector, embedding service, re-ranking, ACL-aware retrieval, DeepSeek as configurable answer LLM.
- **Files:** Versioned Markdown vault + private object storage for uploaded originals; scheduled synchronization and checksum validation.
- **Tasks:** Redis and worker queue for parsing, embedding, indexing, notifications, and retries.
- **Integrations:** Hermes Agent for optional Phase 2 Telegram/Discord + controlled backend tools; n8n optional for notifications/approvals, not an alternate permission authority.
- **Deployment:** Dockerized services, HTTPS reverse proxy, backups, log collection, staging and production environments.

### Minimum API contract (illustrative)

- `POST /auth/register`, `POST /auth/login`, `POST /auth/logout`, `GET /auth/me`
- `GET /admin/access-requests`, `POST /admin/access-requests/{id}/approve`, `POST /admin/access-requests/{id}/reject`
- `GET /admin/users`, `PATCH /admin/users/{id}`, `GET /admin/departments`
- `POST /chats`, `GET /chats`, `GET /chats/{id}`, `POST /chats/{id}/messages`, `DELETE /chats/{id}`
- `POST /knowledge/search`, `GET /knowledge/documents`, `POST /knowledge/proposals`, `GET /knowledge/proposals/{id}`
- `POST /admin/proposals/{id}/approve`, `POST /admin/proposals/{id}/reject`
- `POST /admin/documents/upload`, `POST /admin/documents/{id}/reindex`, `GET /admin/knowledge-gaps`
- `POST /integrations/hermes/knowledge-proposals` (signed service-to-service request, not a public untrusted write endpoint)

Every endpoint requires correct authentication, authorization, input validation, idempotency where relevant, and appropriate audit logging.
