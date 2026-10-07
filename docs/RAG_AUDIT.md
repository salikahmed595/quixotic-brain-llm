# RAG audit — 2026-10-05

How it was measured: the real models (BGE-M3 embeddings, `bge-reranker-v2-m3`) on CPU, the real PostgreSQL + pgvector, the product's own
ingestion / search / confidence code. Benchmark: 134 chunks (15 realistic policy / SOP / script documents + 30 unrelated distractor
documents), **46 labelled questions** (English 20, mixed Roman Urdu + English 8, pure Roman Urdu 10, Urdu script 4, short 2, typos 2) and
**10 unanswerable questions**. It is a *synthetic* corpus and a *small* sample (one question = 2 points of accuracy): treat gaps below
~0.05 as noise and re-measure on your real documents with `python -m evaluation.run_eval`.

## Result

| | before the audit | after |
|---|---|---|
| Right document at rank 1 | 0.76 | **0.91** |
| Right document in top 5 | 0.98 | 0.96 |
| MRR | 0.85 | **0.93** |
| Pure Roman Urdu, rank 1 | 0.50 | **0.80** |
| Follow-up questions (“and how long does it take?”) found | 8 / 12, always "confident" | **12 / 12** |
| Unanswerable questions let through as answerable | not measurable | **0 / 10** |
| Answerable questions answered (not "low confidence") | — | 37 / 46 (80%) — every miss is Roman Urdu or mixed |
| Search time per question (4-core CPU) | 11–21 s | **4.1 s** |

## Defects found and fixed (each has a test)

1. **Prompt break-out (PRD §52).** A document containing `</knowledge>` ended the data fence; the rest of its text was read as instructions. Fence tags in retrieved text are now defanged.
2. **Silent empty uploads.** Scanned/blank PDFs, empty DOCX and headings-only files ended as "ready" with 0 chunks. They now fail with an explanation.
3. **DOCX tables were dropped** (pricing/limit tables vanished from answers). Now extracted in document order.
4. **A small department could get zero results** when a bigger one held near-duplicate content (HNSW filtered search; reproduced). Iterative index scan enabled.
5. **First question after start-up took ~90 s** (model loading). Models now warm up in the background; `/v1/health` reports `models: loading | ready`.
6. **Follow-up questions ignored the chat** and were answered from the wrong document with full confidence. Short follow-ups are now searched with the previous question, and the model receives the last two turns as *context, not facts*.
7. **Reranker cost / quality.** 30 candidates took 11–20 s and gave no better top-1 than plain retrieval. Now only the top 8 are scored (identical results from 6 to 20) and its ranking is fused with the retrieval ranking.
8. **Keyword leg searched on stopwords** (“is | our | what”): keyword R@5 0.52 → 0.74.
9. **Chunks lacked context**: embedding title + section with the text raised vector top-1 from 0.76 to 0.89.
10. **Chunks cut mid-sentence**; PDF pages cut rules in half at page breaks. Sentence-aware chunking; PDF pages merged.
11. **Confidence from one score** let correct Roman Urdu answers through as "low" and unanswerable ones as "medium". Now two signals (reranker probability, vector similarity), the better counts.
12. Smaller hardening: login brute-force throttle (10 failures / 15 min) and constant-time unknown-user path; question length limit 4,000; password ≥ 8 characters; SQS visibility timeout 900 s; chunk metadata status kept in sync.

## Still open — in priority order

1. **Pure Roman Urdu is the weakest area** (about half of those questions end as "low confidence"). Grow `backend/data/roman_urdu_lexicon.json` (`expand`) with your staff's real phrases, and/or add an LLM "query interpretation" step (PRD §23 shows one). The first is cheap and testable now.
2. **The answer model has never been evaluated** (no API key was available): groundedness, citations, refusal wording, answer language. Do this first once a key is set.
3. **Latency**: retrieval ~4 s + the LLM call ≈ 7–9 s against the PRD's 5–8 s. Options: more CPU, a smaller reranker, or skipping the reranker when retrieval is decisive (cascade tested: needs it for ~35–45% of questions at the same quality). int8 quantization was tried and is incompatible with the installed transformers version.
4. **Sources list every retrieved chunk** (up to 6) even if the answer used one. Better: have the model cite `[n]` and show only cited sources.
5. **Memory**: each API process holds both models (~5 GB RAM) and each worker the embedding model (~2.3 GB): size ECS tasks accordingly.
6. PDFs carry no section label in sources; scanned PDFs need OCR.
7. Failed background jobs are not retried; the login throttle and key rate limit are per process (a lockout can also be triggered on purpose against a known account).
8. Only 46 questions on a synthetic corpus: confidence thresholds (`.env`) are placeholders until calibrated on real data.

## 7. Final-config benchmark: AI query interpretation (2026-10-05)

Real models + real PostgreSQL + gpt-4.1-mini, 46 answerable + 10 unanswerable questions (synthetic corpus), final 5 chunks, skip margin 0.04.

| | interpretation OFF | interpretation ON |
|---|---|---|
| Overall R@1 / MRR | 0.93 / 0.94 | 0.96 / 0.97 |
| Pure Roman Urdu R@1 / R@5 | 0.80 / 0.80 | 0.90 / 1.00 |
| Answered (not low) overall | 36/46 | 42/46 |
| Answered, Urdu/Roman Urdu/mixed | 12/22 | 18/22 |
| Unanswerable leaked | 0/10 | 0/10 |

Cost: +0.9 s per non-English question. Still low: delivery time, payment methods, commission, work from home (Roman Urdu) -> teach via Vocabulary.
Full test suite: 109 passed, 2 xfailed. Thresholds remain placeholders until calibrated on real documents.

## 8. First real document (2026-10-05)

`Quixotix_Company_Knowledge_Base.pdf`, 66 chunks, 63 sections. 25 real questions: right section first for 23, within the top 3 for 25.
Unanswerable probes (France, salaries, premium price, office address, leave policy) are answered "not found" or "restricted / not stated".
Fixed: PDF headers in every chunk, no sections, reranker skip mislabelling a correct answer low, example text answered as policy,
"worked in past sales" claims, 9 GB of models resident. Search step costs: embed 0.3 s, database 0.02 s, reranker ~1.2 s per chunk (3 chunks).

## 9. Reranker reads the clean restatement; chat memory; calibration on the real PDF (2026-10-05)

Synthetic Urdu / Roman Urdu benchmark, interpretation ON, final config (rerank top 3, skip margin 0.04):
before -> after the reranker reads the English restatement instead of the original+restatement mix:
R@1 0.96 -> 0.98, MRR 0.97 -> 0.99, pure Roman Urdu R@1 0.90 -> 1.00, Urdu/Roman Urdu/mixed answered 18/22 -> 22/22, all 46 answerable answered;
unanswerable labelled non-low 0/10 -> 1/10 (the answer prompt still refuses). Search 2.7 s mean incl. the 1.3 s restatement call.
Real PDF, 30 answerable / 18 unanswerable: groups overlap at reranker 0.004-0.010; thresholds unchanged (see docs/PRD_GAPS.md).
Chat memory: a follow-up that is longer than 8 words ("What should I say to Ali if he still refuses?") was low confidence; restating it with the chat so far fixed it (reranker 0.009 -> 0.0185+, answer uses "Ali").
