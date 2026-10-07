<!-- PRODUCT.md section 24 -->
# 24. Embedding Layer

## 24.1 Initial Model

Initial recommended model to evaluate:

**BGE-M3**

Reasons:

- Multilingual
- Suitable for English
- Suitable for multilingual retrieval
- Good fit for Urdu-related queries
- Strong retrieval capabilities
- Appropriate for hybrid RAG experimentation

## 24.2 Embedding Model Requirements

The embedding interface must be abstracted.

Example internal method:

```python
embed(text)
```

The rest of the application must not directly depend on one specific model.

This allows future migration to:

- multilingual E5
- GTE multilingual
- Qwen embedding models
- future embedding models

Changing the embedding model requires document re-indexing.
