# RAG audit 2026-10-05
Method: real models (BGE-M3, `bge-reranker-v2-m3`) on CPU, real PostgreSQL+pgvector, product's own ingestion/search/confidence code. 134 chunks (15 policy/SOP/script docs + 30 distractors), **46 labelled questions** (EN 20, mixed Roman Urdu+EN 8, pure Roman Urdu 10, Urdu script 4, short 2, typos 2) + **10 unanswerable**. Synthetic, small (1 q = 2 pts): gaps <~0.05 are noise; re-measure with `python -m evaluation.run_eval`.

## Result (before -> after)
| Metric | before | after |
|---|---|---|
| Right doc rank 1 | 0.76 | **0.91** |
| Right doc top 5 | 0.98 | 0.96 |
| MRR | 0.85 | **0.93** |
| Pure Roman Urdu rank 1 | 0.50 | **0.80** |
| Follow-ups found | 8/12 (always "confident") | **12/12** |
| Unanswerable let through | n/a | **0/10** |
| Answerable answered (not low) | — | 37/46 (80%); misses all Roman Urdu/mixed |
| Search time/question (4-core) | 11–21 s | **4.1 s** |

## Defects fixed (each has a test)
1. Prompt break-out (§52): `</knowledge>` in a doc ended the data fence -> fence tags defanged.
2. Scanned/blank PDFs, empty DOCX, headings-only files ended "ready" with 0 chunks -> now fail with explanation.
3. DOCX tables dropped -> extracted in order.
4. Small department got 0 results beside near-duplicate bigger one (HNSW filtered) -> iterative index scan.
5. First question after start ~90 s -> background warm-up; `/v1/health` `models: loading | ready`.
6. Follow-ups ignored chat -> short follow-ups searched with previous question; model gets last 2 turns as context, not facts.
7. Reranker 30 candidates 11–20 s, no better top-1 -> top 8 only, ranking fused with retrieval.
8. Keyword leg searched stopwords: R@5 0.52 -> 0.74.
9. Embedding title+section with text: vector top-1 0.76 -> 0.89.
10. Mid-sentence cuts / PDF page-break splits -> sentence-aware chunking, pages merged.
11. Single-score confidence -> two signals (reranker prob, vector sim), better counts.
12. Hardening: login throttle (10 fails/15 min), constant-time unknown-user path, question limit 4,000, password >=8, SQS visibility 900 s, chunk status kept in sync.

## Still open (priority order)
1. Pure Roman Urdu weakest (~half "low"): grow `backend/data/roman_urdu_lexicon.json` (`expand`) with real staff phrases and/or LLM query interpretation (PRD §23). Lexicon is cheap, testable now.
2. Answer model never evaluated (no key): groundedness, citations, refusal wording, language. Do first once key set.
3. Latency retrieval ~4 s + LLM ≈ 7–9 s vs PRD 5–8 s. Options: more CPU, smaller reranker, skip reranker when decisive (cascade needs it for ~35–45% q at same quality). int8 incompatible with installed transformers.
4. Sources list all retrieved chunks (<=6); better: model cites `[n]`, show only cited.
5. Memory: API process ~5 GB (both models), worker ~2.3 GB: size ECS tasks.
6. PDFs lack section label in sources; scanned PDFs need OCR.
7. Failed background jobs not retried; login throttle and key rate limit per process (lockout can be triggered on purpose).
8. Confidence thresholds (`.env`) are placeholders until calibrated on real data.

## §7 Final config: AI query interpretation (2026-10-05)
Real models+PG+gpt-4.1-mini, 46+10 q, final 5 chunks, skip margin 0.04.
| | OFF | ON |
|---|---|---|
| R@1 / MRR | 0.93 / 0.94 | 0.96 / 0.97 |
| Pure Roman Urdu R@1 / R@5 | 0.80 / 0.80 | 0.90 / 1.00 |
| Answered overall | 36/46 | 42/46 |
| Answered Urdu/RU/mixed | 12/22 | 18/22 |
| Unanswerable leaked | 0/10 | 0/10 |
Cost +0.9 s per non-English q. Still low: delivery time, payment methods, commission, work from home (RU) -> teach via Vocabulary. Suite: 109 passed, 2 xfailed.

## §8 First real doc (2026-10-05)
`Quixotix_Company_Knowledge_Base.pdf`, 66 chunks, 63 sections. 25 real q: right section first 23, top 3 25. Unanswerable probes (France, salaries, premium price, office address, leave policy) -> "not found"/"restricted". Fixed: PDF headers in every chunk, no sections, reranker skip mislabelling correct answer low, example text answered as policy, "worked in past sales" claims, 9 GB models resident. Costs: embed 0.3 s, DB 0.02 s, reranker ~1.2 s/chunk (3 chunks).

## §9 Reranker reads clean restatement; chat memory; real-PDF calibration (2026-10-05)
Synthetic Urdu/RU benchmark, interpretation ON, rerank top 3, skip 0.04; reranker reads English restatement instead of original+restatement: R@1 0.96->0.98, MRR 0.97->0.99, pure RU R@1 0.90->1.00, Urdu/RU/mixed answered 18/22->22/22, all 46 answered; unanswerable non-low 0/10->1/10 (answer prompt still refuses). Search 2.7 s mean incl. 1.3 s restatement. Real PDF 30 answerable/18 unanswerable: groups overlap at reranker 0.004–0.010; thresholds unchanged (docs/PRD_GAPS.md). Chat memory: follow-up >8 words ("What should I say to Ali if he still refuses?") was low; restating with chat fixed (reranker 0.009->0.0185+, answer uses "Ali").
