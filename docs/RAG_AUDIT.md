# RAG audit (2026-10-05, summary)
History: git log -p docs/RAG_AUDIT.md

Benchmark: 134 chunks, 46 labelled q (EN/mixed/Roman Urdu/Urdu), 10 unanswerable; synthetic, small. Re-measure: `python -m evaluation.run_eval`.

Latest (query interpretation ON, rerank top 3, skip margin 0.04): R@1 0.98, MRR 0.99, pure Roman Urdu R@1 1.00, 46/46 answered, unanswerable non-low 1/10 (prompt still refuses), search 2.7 s. Real PDF (30 answerable/18 unanswerable): reranker score groups overlap 0.004–0.010; thresholds unchanged.

Fixed (tested): fence-tag break-out (§52), empty/scanned uploads fail with explanation, DOCX tables, HNSW filtered-search zero results (iterative scan), model warm-up (`/v1/health` `models`), follow-ups use chat, reranker top-K + fusion, keyword stopwords, title+section embedded, sentence-aware chunking, two-signal confidence, login throttle 10/15 min.

Open (priority):
1. ❓ Pure Roman Urdu weakest: grow `backend/data/roman_urdu_lexicon.json` / Vocabulary page.
2. ❓ Answer model groundedness/citations/refusal/language never evaluated with real key.
3. ❓ Latency ~7–9 s vs PRD 5–8 s (more CPU, smaller reranker, skip reranker).
4. Sources list all retrieved chunks (<=6); better: model cites `[n]`.
5. Memory: API ~5 GB, worker ~2.3 GB.
6. PDFs lack section labels; scanned PDFs need OCR.
7. Failed jobs not retried; throttles per process.
8. ❓ Confidence thresholds (`.env`) are placeholders until calibrated on real data.
