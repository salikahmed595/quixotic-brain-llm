<!-- PRODUCT.md section 7 -->
# 7. RAG Retrieval Architecture

```text
User Question
      ↓
Authentication
      ↓
Permission Check
      ↓
Metadata Filtering
      ↓
Query Normalization
      ↓
 ┌──────────────┬──────────────┐
 ↓                             ↓
BM25                        BGE-M3
Keyword Search              Vector Search
 ↓                             ↓
 └──────────────┬──────────────┘
                ↓
          Hybrid Search
                ↓
         Top 20–40 Chunks
                ↓
             Reranker
                ↓
          Best 5–8 Chunks
                ↓
               LLM
                ↓
      Grounded Answer + Sources
```
