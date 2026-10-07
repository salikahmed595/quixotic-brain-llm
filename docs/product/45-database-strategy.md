<!-- PRODUCT.md section 45 -->
# 45. Database Strategy

Initial recommendation:

**PostgreSQL + pgvector**

Store:

- Users
- Departments
- Roles
- Permissions
- Documents
- Chunks
- Metadata
- Embeddings
- Sales memories
- Feedback
- API keys
- Analytics events
- Audit logs

Potential future migration:

```text
PostgreSQL + pgvector
          ↓
Large-scale vector workload
          ↓
Qdrant
```
