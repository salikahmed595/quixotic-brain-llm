"""Real BGE-M3 embeddings and multilingual BGE reranker (CPU). Skips until the weights are in .models/."""
import math
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
M3, RR = ROOT / ".models" / "bge-m3", ROOT / ".models" / "bge-reranker-v2-m3"


def _ready(path, name):
    f = path / name
    return f.exists() and f.stat().st_size > 2_270_000_000


pytestmark = pytest.mark.skipif(not (_ready(M3, "pytorch_model.bin") and _ready(RR, "model.safetensors")),
                                reason="model weights not downloaded yet (scripts/download_models.sh)")

DOCS = {
    "discount": "Customers buying 3 or more artworks can receive up to 10% discount after manager approval.",
    "refund": "Refunds are reviewed against order status and delivery date before approval.",
    "leave": "Full-time employees receive annual leave per the HR leave policy.",
}


@pytest.fixture(scope="module")
def emb():
    from backend.retrieval.embeddings import BGEM3Embedder
    return BGEM3Embedder(str(M3))


def cos(a, b):
    return sum(x * y for x, y in zip(a, b))


def test_bge_m3_is_1024d_normalized_cpu(emb):
    v = emb.embed("refund policy")
    assert len(v) == emb.dim == 1024 and abs(math.sqrt(sum(x * x for x in v)) - 1) < 1e-3


@pytest.mark.parametrize("query,expected", [                       # PRD §22 / §58 example queries, all four language styles
    ("What is our refund policy?", "refund"),
    pytest.param("customer paise wapas mang raha hai", "refund", marks=pytest.mark.xfail(
        reason="MEASURED GAP: pure Roman Urdu 'paise wapas' scores refund 0.372 vs discount 0.397 on BGE-M3 (PRD §22/§23; see docs/PRD_GAPS.md)")),
    ("employee annual leave kitni hai?", "leave"),                 # Roman Urdu, §58
    ("can we give 20% discount?", "discount"),
    ("customer bol raha hai bohat expensive hai, discount de sakte hain?", "discount"),   # mixed
])
def test_cross_lingual_retrieval_picks_the_right_policy(emb, query, expected):
    q = emb.embed(query)
    scores = {k: cos(q, emb.embed(t)) for k, t in DOCS.items()}
    assert max(scores, key=scores.get) == expected, scores


def test_reranker_orders_relevant_first_and_works_on_cpu():
    from backend.reranking.base import CrossEncoderReranker
    rr = CrossEncoderReranker(str(RR))
    texts = list(DOCS.values())
    s = rr.score("how many days of annual leave do employees get", texts)
    assert texts[s.index(max(s))] == DOCS["leave"]
    s2 = rr.score("customer is asking for refund kya karun?", texts)          # mixed Roman Urdu + English works
    assert texts[s2.index(max(s2))] == DOCS["refund"]


@pytest.mark.xfail(reason="MEASURED GAP: the reranker gives no signal for pure Roman Urdu ('paise wapas'); see docs/PRD_GAPS.md")
def test_reranker_pure_roman_urdu():
    from backend.reranking.base import CrossEncoderReranker
    rr = CrossEncoderReranker(str(RR)); texts = list(DOCS.values())
    s = rr.score("customer paise wapas mang raha hai", texts)
    assert texts[s.index(max(s))] == DOCS["refund"]
