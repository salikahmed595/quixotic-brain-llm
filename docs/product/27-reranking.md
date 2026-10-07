<!-- PRODUCT.md section 27 -->
# 27. Reranking

Hybrid search should return approximately:

```text
20–40 candidate chunks
```

The reranker should reduce this to:

```text
5–8 best chunks
```

The reranker must prioritize:

- Direct relevance
- Current information
- Official knowledge
- Scenario similarity
- User permissions
- Department context
