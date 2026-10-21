"""Owner 2026-10-21: each chat remembers about the last 1,000 words (questions + answers), so the assistant keeps the whole
situation; the fixed refusal is not remembered as an answer."""
from types import SimpleNamespace
from uuid import uuid4

from backend.api.v1.ask import CHAT_MEMORY_WORDS, _history
from backend.retrieval.ask import NOT_FOUND_TEXT


def _svc(messages):
    class Conv:
        def get(self, uid, cid): return {"messages": messages}
    return SimpleNamespace(conversations=Conv(), settings=SimpleNamespace(feedback_learning=False), ops=None)


def _pair(q, a, actions=None):
    return [{"role": "user", "content": {"text": q}},
            {"role": "assistant", "content": {"kind": "ask", "answer": a, "query_id": str(uuid4()), "actions": actions}}]


def test_history_keeps_about_1000_words_newest_first_and_answers_that_flagged_missing_info():
    caller = SimpleNamespace(key=None, principal=SimpleNamespace(user_id=uuid4()))
    words = lambda n: " ".join(["w"] * n)
    msgs = []
    for i in range(12):                                         # 12 turns x 200 words = 2,400 words
        msgs += _pair(f"q{i} " + words(99), words(100))
    msgs += _pair("refund?", "Not in the knowledge base yet.", actions=["report_missing_information"])
    msgs += _pair("hello", NOT_FOUND_TEXT)
    h = _history(_svc(msgs), caller, uuid4())
    assert CHAT_MEMORY_WORDS == 1000
    assert h[-1][0] == "hello" and h[-1][1] == ""                    # the fixed refusal is not remembered as an answer
    assert h[-2][1] == "Not in the knowledge base yet."              # kept now (was dropped when it had actions)
    total = sum(len(q.split()) + len(a.split()) for q, a, _ in h)
    assert 800 <= total <= 1000 and h[0][0].startswith("q")           # oldest turns beyond ~1,000 words are left out
