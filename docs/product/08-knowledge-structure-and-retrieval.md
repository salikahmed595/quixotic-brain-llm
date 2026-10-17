<!-- PRODUCT.md section 8 -->
# 8. Knowledge structure and retrieval

**Authoritative knowledge:** approved Obsidian-compatible Markdown files, plus curated file imports transformed into approved document records. For hosted production, the canonical vault must be synchronized on the server with version history; do not make an admin's laptop the only copy. Use Git or an equivalent versioned storage layer.

**Suggested hierarchy:** Company/, HR/, Sales/Fresh-Seller/, Sales/Upseller/, Production/, Marketing/, Customer-Support/, Leadership/, Training/, Glossary/, Archive/. Adapt to real departments, not invented policies.

Each published document needs: immutable ID, title, content, category, department(s), sensitivity/access scope, owner, approving user, source/provenance, effective date, created/updated timestamps, version ID, status (Draft/Under Review/Approved/Published/Archived), and an indexing checksum. Keep document ACL metadata with every chunk.

**Retrieval workflow:** Authenticate user → identify effective roles/departments → select eligible approved, unexpired content before search → run hybrid lexical and vector retrieval → rerank → supply bounded excerpts and source metadata to DeepSeek (or configured LLM) → generate sourced answer or safe 'not found' response → capture feedback/gaps. Embeddings and vector indexes use PostgreSQL + pgvector; keyword search uses PostgreSQL full-text search or equivalent. Recheck permissions before providing the final source/answer. Resist prompt injection inside documents; retrieved text is data, not system instructions.

**Document updates:** Preserve previous published version until replacement is validated, approved, and indexed. On successful publication, atomically switch the active version or use a controlled publication transaction; invalidate old chunks. Fail closed if the index and permissions are out of sync. All changes must have a reversible change record.
