<!-- PRODUCT.md section 39 -->
# 39. Search API

Search-only endpoint returns raw retrieval results without LLM generation.

```json
{
  "results": [
    {
      "text": "When customers object to pricing...",
      "score": 0.92,
      "source": "Sales Playbook"
    }
  ]
}
```

Purpose:

- Internal apps can use Quixotic Brain as a knowledge engine
- Lower cost
- Faster retrieval
- More flexible downstream workflows
