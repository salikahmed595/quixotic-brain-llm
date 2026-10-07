<!-- PRODUCT.md section 14 -->
# 14. Metadata Model

Each knowledge chunk must contain metadata.

Example:

```json
{
  "company": "quixotic",
  "department": "sales",
  "document_type": "sales_policy",
  "category": "pricing",
  "access_level": "sales",
  "status": "active",
  "version": 4,
  "language": "english",
  "created_at": "2026-10-03",
  "updated_at": "2026-10-03"
}
```

Metadata is used for:

- Access control
- Search filtering
- Version filtering
- Department filtering
- Document type filtering
- Active/archived state
- Language hints
- Analytics
