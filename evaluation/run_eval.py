"""Run the evaluation set against a live POST /v1/search (PRD §58, §59) and calibrate the confidence thresholds.

    python -m evaluation.run_eval --base-url http://localhost:8000 --api-key qx_live_...

The API key needs the `search` permission and must belong to an administrator (the key acts as its creator), because the
script asks for the raw scores (`debug: true`). Prints Recall@5, Recall@10, MRR and whether the V1 target (>= 90% in the top 5,
§59) is met, then the score ranges of answerable vs unanswerable questions for BOTH confidence signals so the owner can pick
QB_CONFIDENCE_* (PRD §31 gives no thresholds). Other §59 metrics (groundedness, citation correctness, language robustness,
latency, feedback) need labelled data or logs the PRD does not define and are not computed here.

eval_set.json: `questions` = [{question, expected_source}], `unanswerable` = [question, ...] (PRD §35 gives one example).
Write your own questions in your staff's real wording — English, Roman Urdu, Urdu, mixed.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import httpx

from .metrics import mrr, rank_of, recall_at

V1_TARGET_RECALL_AT_5 = 0.90          # PRD §59


def _top(results, key):
    vals = [x[key] for x in results if x.get(key) is not None]
    return max(vals) if vals else None


def _summary(name: str, values: list[float]) -> str:
    if not values:
        return f"{name}: n/a"
    v = sorted(values)
    return f"{name}: min={v[0]:.4f}  p25={v[len(v) // 4]:.4f}  median={v[len(v) // 2]:.4f}  max={v[-1]:.4f}  (n={len(v)})"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--api-key", required=True)
    ap.add_argument("--user-id", default=None, help="optional: act as this employee instead of the key's creator")
    ap.add_argument("--eval-set", default=str(Path(__file__).with_name("eval_set.json")))
    a = ap.parse_args()
    data = json.loads(Path(a.eval_set).read_text(encoding="utf-8"))
    questions, unanswerable = data["questions"], data.get("unanswerable", [])
    ranks = []
    sig = {"answerable": {"vector_score": [], "rerank_score": []}, "unanswerable": {"vector_score": [], "rerank_score": []}}

    def ask(c, text):
        body = {"question": text, "debug": True}
        if a.user_id:
            body["user_id"] = a.user_id
        r = c.post("/v1/search", json=body)
        r.raise_for_status()
        return r.json()["results"]

    with httpx.Client(base_url=a.base_url, headers={"X-API-Key": a.api_key}, timeout=120) as c:
        for q in questions:
            results = ask(c, q["question"])
            rank = rank_of(q["expected_source"], [x["source"] for x in results])
            ranks.append(rank)
            for k in ("vector_score", "rerank_score"):
                if (t := _top(results, k)) is not None:
                    sig["answerable"][k].append(t)
            print(f"{'OK  ' if rank and rank <= 5 else 'MISS'} rank={rank}  | {q['question']} -> {q['expected_source']}")
        for q in unanswerable:
            results = ask(c, q)
            for k in ("vector_score", "rerank_score"):
                if (t := _top(results, k)) is not None:
                    sig["unanswerable"][k].append(t)
            print(f"NONE  top vector={_top(results, 'vector_score')}  rerank={_top(results, 'rerank_score')}  | {q}")
    r5 = recall_at(ranks, 5)
    print(f"\nRecall@5={r5:.2f}  Recall@10={recall_at(ranks, 10):.2f}  MRR={mrr(ranks):.2f}  "
          f"V1 target (>= {V1_TARGET_RECALL_AT_5:.0%} @5): {'MET' if r5 >= V1_TARGET_RECALL_AT_5 else 'NOT MET'}")
    print("\nConfidence calibration (highest score among the returned chunks, per question)")
    for signal, setting in (("vector_score", "QB_CONFIDENCE_VECTOR_MEDIUM / _HIGH"), ("rerank_score", "QB_CONFIDENCE_MEDIUM / _HIGH")):
        print(f"\n  {signal}   ->  {setting}")
        print("   " + _summary("answerable  ", sig["answerable"][signal]))
        print("   " + _summary("unanswerable", sig["unanswerable"][signal]))
    print("\nA question is answered when EITHER signal reaches its Medium threshold. Put each Medium threshold just above the\n"
          "unanswerable maximum and below most of the answerable range; the owner decides where High begins.")
    return 0 if r5 >= V1_TARGET_RECALL_AT_5 else 1


if __name__ == "__main__":
    raise SystemExit(main())
